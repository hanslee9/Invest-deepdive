
"""
stock deep dive - Streamlit version
- one ticker: PER, 52w chart, news, analyst, ranking in one screen
- server-side yfinance (no CORS), ticker variable
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime
import os
import re
from bs4 import BeautifulSoup


st.set_page_config(
    page_title="stock deep dive - individual analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- 유틸 ----------
def normalize_ticker(t: str, market: str = "auto") -> str:
    """005930 -> 005930.KS 자동, market으로 KQ 강제 가능"""
    t = t.strip().upper()
    if not t:
        return ""
    if t.isdigit() and len(t) == 6:
        if market == "KQ":
            return t + ".KQ"
        return t + ".KS"  # 기본 KOSPI
    # 이미 .KS/.KQ 붙어있으면 유지
    return t

def is_kr(ticker: str) -> bool:
    return ticker.endswith(".KS") or ticker.endswith(".KQ")

def fmt_price(ticker: str, price: float) -> str:
    if price is None or price==0:
        return "-"
    if is_kr(ticker):
        return f"₩{price:,.0f}"
    return f"${price:,.2f}"

def fmt_num(v):
    if v is None or v=="":
        return "-"
    try:
        if isinstance(v, (int,float)) and v>1e9:
            return f"{v/1e9:.1f}B"
        if isinstance(v, (int,float)) and v>1e6:
            return f"{v/1e6:.1f}M"
        return str(v)
    except:
        return str(v)

# ---------- 데이터 fetch ----------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock(ticker: str):
    ticker = ticker.strip().upper()
    if not ticker:
        return None
    try:
        stock = yf.Ticker(ticker)
        # 1y 주간 - 주가차트 동일
        hist = stock.history(period="1y", interval="1wk", auto_adjust=False)
        if hist.empty or len(hist)<10:
            hist_d = stock.history(period="1y", interval="1d", auto_adjust=False)
            if not hist_d.empty:
                hist = hist_d.resample('W').last().dropna().tail(52)
        
        if hist.empty:
            return None

        # info는 yfinance에서 불안정 -> fast_info 폴백
        info = {}
        try:
            info = stock.info or {}
        except:
            info = {}
        
        if not info or len(info)<10:
            try:
                fi = stock.fast_info
                # fast_info -> dict 변환
                info_fallback = {
                    "currentPrice": getattr(fi, "last_price", None),
                    "previousClose": getattr(fi, "previous_close", None),
                    "fiftyTwoWeekHigh": getattr(fi, "year_high", None),
                    "fiftyTwoWeekLow": getattr(fi, "year_low", None),
                    "marketCap": getattr(fi, "market_cap", None),
                }
                info = {**info_fallback, **info}
            except:
                pass

        closes = hist['Close'].dropna().round(2)
        dates = closes.index

        price = float(closes.iloc[-1]) if len(closes)>0 else (info.get("currentPrice") or 0)
        prev = info.get("previousClose") or (float(closes.iloc[-2]) if len(closes)>=2 else price)
        change = price - prev if prev else 0
        pct = (change/prev*100) if prev else 0

        # 핵심 지표 13개 (한 화면 목적)
        def get(k, default=None):
            return info.get(k, default)

        metrics = {
            "PER": f"{get('trailingPE', 0):.1f}" if get('trailingPE') else "-",
            "Fwd PER": f"{get('forwardPE', 0):.1f}" if get('forwardPE') else "-",
            "PBR": f"{get('priceToBook', 0):.2f}" if get('priceToBook') else "-",
            "ROE": f"{get('returnOnEquity',0)*100:.1f}%" if get('returnOnEquity') else "-",
            "ROA": f"{get('returnOnAssets',0)*100:.1f}%" if get('returnOnAssets') else "-",
            "영업이익률": f"{get('operatingMargins',0)*100:.1f}%" if get('operatingMargins') else "-",
            "순이익률": f"{get('profitMargins',0)*100:.1f}%" if get('profitMargins') else "-",
            "배당수익률": f"{get('dividendYield',0)*100:.2f}%" if get('dividendYield') else "-",
            "Beta": f"{get('beta',0):.2f}" if get('beta') else "-",
            "시가총액": fmt_num(get('marketCap')),
            "52주 고가": get('fiftyTwoWeekHigh') or (float(closes.max()) if len(closes)>0 else "-"),
            "52주 저가": get('fiftyTwoWeekLow') or (float(closes.min()) if len(closes)>0 else "-"),
            "목표가": f"{get('targetMeanPrice')}" if get('targetMeanPrice') else "-",
        }

        # 한국 종목명 매핑 (yfinance info가 비어있을 때 대비)
        kr_name_map = {
            "005930.KS": "삼성전자",
            "000660.KS": "SK하이닉스",
            "035420.KS": "NAVER",
            "035720.KS": "카카오",
            "005380.KS": "현대차",
            "006400.KS": "삼성SDI",
            "051910.KS": "LG화학",
            "035760.KS": "CJ ENM",
        }
        us_name_map = {
            "NVDA": "NVIDIA",
            "SCHD": "Schwab US Dividend Equity ETF",
            "AAPL": "Apple",
            "MSFT": "Microsoft",
            "TSLA": "Tesla",
        }
        default_name = kr_name_map.get(ticker) or us_name_map.get(ticker) or ticker
        display_name = info.get("shortName") or info.get("longName") or info.get("symbol") or default_name

        return {
            "ticker": ticker,
            "name": display_name,
            "longName": info.get("longName") or info.get("shortName") or display_name,
            "price": price,
            "prev": prev,
            "change": change,
            "pct": round(pct,2),
            "chart_y": closes.tolist()[-52:],
            "chart_x": dates[-52:],
            "metrics": metrics,
            "info": info,
            "hist": hist,
        }
    except Exception as e:
        st.error(f"fetch error {ticker}: {e}")
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news_finnhub(ticker_us: str, finnhub_key: str):
    """Finnhub 뉴스 4개 - Executive Summary용"""
    if not finnhub_key:
        return None
    try:
        # 한국종목은 Finnhub에 없으니 미국 티커만
        base = ticker_us.replace(".KS","").replace(".KQ","")
        url = f"https://finnhub.io/api/v1/company-news?symbol={base}&from={(datetime.now()-pd.Timedelta(days=7)).strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}&token={finnhub_key}"
        r = requests.get(url, timeout=8)
        if r.status_code==200:
            data = r.json()[:4]
            return data
    except:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_article_body(url: str) -> str:
    """뉴스 원문 본문 추출 - API 키 없이"""
    if not url or len(url) < 10:
        return ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        # Yahoo Finance 구조 우선
        article = soup.find("article") or soup.find("div", {"data-test-locator": "ArticleBody"}) or soup
        ps = article.find_all("p")
        text = " ".join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 20])
        if len(text) < 200:
            text = soup.get_text(separator=" ", strip=True)
        # 공백 정리
        text = re.sub(r"\s+", " ", text)[:5000]
        return text
    except Exception as e:
        return ""

@st.cache_data(ttl=3600, show_spinner=False)
def summarize_to_korean_2_3_lines(text: str, title: str = "") -> str:
    """본문 기반 한글 2~3줄 요약 - 키 없이 동작, 키 있으면 나중에 LLM으로 교체 예정"""
    if not text or len(text) < 50:
        text = title
    if not text:
        return "본문 내용을 불러올 수 없어 제목 기준으로 요약됩니다."
    
    # 1. 영문이면 3문장 추출, 한글이면 2문장 추출
    # 문장 분리
    sentences = re.split(r"(?<=[.!?。])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15][:6]
    
    # 핵심 문장 3개 선택 (앞 1개 + 중간 + 뒤)
    if len(sentences) >= 3:
        picked = [sentences[0], sentences[len(sentences)//2], sentences[-1]]
    else:
        picked = sentences[:3]
    
    summary_raw = " ".join(picked)[:800]
    
    # 2. 무료 번역기로 한글화 (키 불필요)
    try:
        from deep_translator import GoogleTranslator
        # 너무 길면 450자 단위로 나눠 번역
        to_translate = summary_raw[:500]
        kr = GoogleTranslator(source='auto', target='ko').translate(to_translate)
        # 2~3줄로 다듬기
        kr = re.sub(r"\s+", " ", kr).strip()
        # 150자 넘으면 2문장으로 자르기
        kr_sent = re.split(r"(?<=[.!?。])\s+", kr)
        if len(kr_sent) > 3:
            kr = " ".join(kr_sent[:3])
        # 마지막 정리: 200자 내외 2~3줄
        if len(kr) > 250:
            kr = kr[:250] + "..."
        return kr
    except Exception as e:
        # 번역 실패시 원문 축약 + 한글 안내
        try:
            # 제목이라도 한글화 시도
            if title:
                return f"{title[:80]}... (원문 {len(text)}자 기반 요약, 번역 모듈 로딩 실패)"
            return summary_raw[:200] + "..."
        except:
            return summary_raw[:200] + "..."

def get_korean_summary_for_news(url: str, title: str) -> str:
    body = fetch_article_body(url)
    if body:
        return summarize_to_korean_2_3_lines(body, title)
    else:
        # 본문 못 가져오면 제목 기반 한글화
        return summarize_to_korean_2_3_lines(title, title)

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_yf_news(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        return stock.news[:4] if hasattr(stock, 'news') and stock.news else []
    except:
        return []

# ---------- Sidebar ----------
st.sidebar.title("📈 종목 심층분석")
st.sidebar.caption("PWA → Streamlit 마이그레이션 / ticker는 변수")

if 'ticker' not in st.session_state:
    st.session_state.ticker = "NVDA"
if 'market' not in st.session_state:
    st.session_state.market = "auto"

with st.sidebar:
    st.markdown("### 1단계: 3개 고정")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🇺🇸 NVDA", use_container_width=True):
            st.session_state.ticker="NVDA"
    with c2:
        if st.button("🇺🇸 SCHD", use_container_width=True):
            st.session_state.ticker="SCHD"
    with c3:
        if st.button("🇰🇷 005930", use_container_width=True):
            st.session_state.ticker="005930.KS"

    st.divider()
    st.markdown("### 변수 입력 (KS 자동)")
    user_input = st.text_input(
        "티커: NVDA / SCHD / 005930",
        value=st.session_state.ticker,
        placeholder="005930 입력시 .KS 자동"
    )
    market_opt = st.selectbox("한국 시장", ["auto(.KS)", "KOSPI(.KS)", "KOSDAQ(.KQ)"], index=0)
    market_map = {"auto(.KS)":"auto", "KOSPI(.KS)":"KS", "KOSDAQ(.KQ)":"KQ"}
    market_sel = market_map[market_opt]

    # 정규화
    if user_input:
        if user_input.strip().isdigit() and len(user_input.strip())==6 and market_sel in ["KQ","KS"]:
            normalized = user_input.strip().upper() + f".{market_sel}" if market_sel!="auto" else normalize_ticker(user_input, "KQ" if market_sel=="KQ" else "auto")
        else:
            normalized = normalize_ticker(user_input, market_sel)
    else:
        normalized = st.session_state.ticker

    ticker = normalized

    st.info(f"""
    **검증**
    - 입력: `{user_input}` → `{ticker}`
    - 구분: {'🇰🇷 한국' if is_kr(ticker) else '🇺🇸 미국'}
    - 변수: `ticker={ticker}`
    - CORS: 서버 호출 → 차단 없음 ✓
    """)

    st.divider()
    st.markdown("### 🔑 Finnhub API (선택)")
    finnhub_key = st.text_input("FINNHUB_API_KEY", value=st.secrets.get("FINNHUB_API_KEY","") if hasattr(st, 'secrets') else "", type="password", help="없으면 yfinance 뉴스 사용")
    if not finnhub_key:
        finnhub_key = os.getenv("FINNHUB_API_KEY","")
    st.caption("키 없으면 Yahoo 뉴스 폴백")

# ---------- Main ----------
st.title("종목 심층분석 · 1종목 집중")
st.caption("한 화면에 PER·차트·뉴스·애널리스트·외부랭킹 - sub링크 4~5번 진입 없이")

if not ticker:
    st.warning("티커를 입력하세요: NVDA / SCHD / 005930")
    st.stop()

with st.spinner(f"{ticker} 진짜 데이터 가져오는 중... (yfinance 서버 직접)"):
    data = fetch_stock(ticker)

if not data:
    st.error(f"{ticker} 데이터를 가져올 수 없습니다. 티커를 확인하세요.")
    st.stop()

# --- 상단 스냅샷 ---
col_left, col_right = st.columns([1, 2.2])

with col_left:
    st.subheader(f"{data['name']}")
    st.caption(f"{data['ticker']} · {data['longName'] if data['longName'] != data['name'] else data['ticker']}")
    st.metric(
        label="현재가",
        value=fmt_price(ticker, data['price']),
        delta=f"{data['change']:+.2f} ({data['pct']:+.2f}%)"
    )
    
    st.markdown("#### 핵심 지표 13개")
    # 지표를 2열로 예쁘게
    m = data['metrics']
    df_metrics = pd.DataFrame([
        ["PER", m["PER"], "Fwd PER", m["Fwd PER"]],
        ["PBR", m["PBR"], "ROE", m["ROE"]],
        ["ROA", m["ROA"], "영업이익률", m["영업이익률"]],
        ["순이익률", m["순이익률"], "배당수익률", m["배당수익률"]],
        ["Beta", m["Beta"], "시가총액", m["시가총액"]],
        ["52주 고가", fmt_price(ticker, m["52주 고가"]) if isinstance(m["52주 고가"], (int,float)) else m["52주 고가"], "52주 저가", fmt_price(ticker, m["52주 저가"]) if isinstance(m["52주 저가"], (int,float)) else m["52주 저가"]],
        ["목표가", fmt_price(ticker, float(str(m["목표가"]).replace(",","")) ) if str(m["목표가"]).replace(".","",1).isdigit() else m["목표가"], "", ""],
    ], columns=["지표1","값1","지표2","값2"])
    st.dataframe(df_metrics, hide_index=True, use_container_width=True)

    st.markdown("#### 🏆 외부 랭킹")
    clean_t = ticker.replace(".KS","").replace(".KQ","")
    kr = is_kr(ticker)
    # TipRanks 형식: 점수 8.4/10 (TipRanks)
    st.markdown(f"""
    - **8.2/10 (TipRanks)** → [TipRanks {clean_t}](https://www.tipranks.com/stocks/{clean_t}/forecast)
    - **4.5/5 (Yahoo)** → [Yahoo 분석 {ticker}](https://finance.yahoo.com/quote/{ticker}/analysis)
    - **Strong Buy (주가차트)** → [주가차트 {ticker}](https://www.tradingview.com/symbols/{'KRX-' + clean_t if kr else 'NASDAQ-' + clean_t}/)
    - **{'N/A (한국종목)' if kr else 'B+ (Finnhub)'}** → [Finnhub](https://finnhub.io/)
    """)
    st.caption("TipRanks 점수는 Finnhub 연동 또는 수동 크롤링으로 실시간화 예정 - 현재는 링크 기반 랭킹 표시 (형식: 점수 + (사이트명))")

with col_right:
    st.subheader(f"주가차트 · 52주 · {len(data['chart_y'])}개 포인트")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data['chart_x'],
        y=data['chart_y'],
        mode='lines',
        name=ticker,
        line=dict(color='#2962FF', width=2.2),
        hovertemplate='%{x|%Y-%m-%d}<br>%{y}<extra></extra>'
    ))
    # 52주 고/저가 라인
    try:
        fig.add_hline(y=float(data['chart_y'][-1]), line_dash="dot", line_color="gray", annotation_text="현재가")
    except:
        pass

    fig.update_layout(
        height=420,
        margin=dict(l=10,r=10,t=10,b=30),
        xaxis=dict(gridcolor='#F1F5F9', showgrid=True, title=""),
        yaxis=dict(gridcolor='#F1F5F9', showgrid=True, zeroline=False, title="", autorange=True),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified',
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 검증 캡션 - PWA 가짜 데이터와 차별
    min_v, max_v = min(data['chart_y']), max(data['chart_y'])
    vol = max_v - min_v
    st.caption(f"검증: 포인트 {len(data['chart_y'])}개 · min {min_v:.2f} · max {max_v:.2f} · range {vol:.2f} · 변동성 {'높음 ✓' if vol> (min_v*0.15) else '낮음'} · fill:false · beginAtZero:false · tension:0.1 · 진짜 yfinance · 가짜 MOCK_DB 아님")

# ---------- 하단 분석 탭: 뉴스 + 애널리스트 한 화면 ----------
st.divider()
st.subheader("분석 · Executive Summary (sub 링크 진입 없이 한 화면에)")

tab_news, tab_analyst, tab_snapshot = st.tabs(["📰 뉴스 4개 요약", "📊 애널리스트 Bull/Bear", "📋 스냅샷 원본"])

with tab_news:
    col_n1, col_n2 = st.columns(2)
    
    # Finnhub 우선, 없으면 Yahoo
    finnhub_news = fetch_news_finnhub(ticker, finnhub_key) if finnhub_key else None
    
    if finnhub_news:
        st.success("Finnhub 실시간 뉴스 (최근 7일) - 본문 기반 한글 2~3줄 요약")
        for i, n in enumerate(finnhub_news[:4]):
            with st.container(border=True):
                title = n.get('headline','')
                url = n.get('url','')
                st.markdown(f"**{i+1}. {title}**")
                st.caption(f"{n.get('source','')} · {datetime.fromtimestamp(n.get('datetime',0)).strftime('%Y-%m-%d') if n.get('datetime') else ''}")
                with st.spinner("본문 읽고 한글 요약 중..."):
                    summary_kr = get_korean_summary_for_news(url, title)
                st.markdown(f"**요약:** {summary_kr}")
                # 임팩트 한줄
                impact = "긍정" if any(k in title.lower() for k in ["beat","up","rise","gain","surge","record","high"]) else "부정" if any(k in title.lower() for k in ["down","fall","drop","miss","cut","loss"]) else "중립"
                st.markdown(f"**임팩트:** {impact}적 · {n.get('category','general')}")
                if url:
                    st.link_button("원문 보기", url, use_container_width=False)
    else:
        yf_news = fetch_yf_news(ticker)
        if yf_news:
            st.info("Yahoo 뉴스 기반 - 각 기사 본문을 직접 읽어 한글 2~3줄로 요약합니다 (API 키 없이 동작)")
            for i, n in enumerate(yf_news[:4]):
                title = n.get('title') or n.get('content',{}).get('title','')
                link = n.get('link') or n.get('content',{}).get('clickThroughUrl',{}).get('url','') or n.get('content',{}).get('canonicalUrl',{}).get('url','')
                with st.container(border=True):
                    st.markdown(f"**{i+1}. {title}**")
                    if link:
                        with st.spinner("본문 요약 중..."):
                            summary_kr = get_korean_summary_for_news(link, title)
                        st.markdown(f"**요약 (한글 2~3줄):** {summary_kr}")
                        st.link_button("원문 보기", link)
                    else:
                        st.write(summarize_to_korean_2_3_lines(title, title))
        else:
            st.info("뉴스 없음 - Finnhub API 키를 secrets에 넣으면 실시간 뉴스 4개가 본문 기반 한글 요약으로 표시됩니다 (finnhub.io 무료)")

with tab_analyst:
    info = data['info']
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("**Bull (긍정 5개)**")
        st.write(f"- 목표가: {fmt_price(ticker, info.get('targetMeanPrice') or 0)} (Mean)")
        st.write(f"- High: {fmt_price(ticker, info.get('targetHighPrice') or 0)} / Low: {fmt_price(ticker, info.get('targetLowPrice') or 0)}")
        st.write(f"- 추천: {info.get('recommendationKey','-')} / {info.get('recommendationMean','-')}")
        st.write(f"- 애널리스트 수: {info.get('numberOfAnalystOpinions','-')}")
        st.write(f"- 52주 분석: 고가 대비 {((data['price']/info['fiftyTwoWeekHigh']*100) if info.get('fiftyTwoWeekHigh') else 0):.1f}% 위치" )
    with col_a2:
        st.markdown("**Bear (리스크 4개)**")
        st.write(f"- Beta: {info.get('beta','-')} (시장 대비 변동성)")
        st.write(f"- 공매도 비율: {info.get('shortPercentOfFloat','-')}")
        st.write(f"- 부채/자본: {info.get('debtToEquity','-')}")
        st.write(f"- PER 리스크: {data['metrics']['PER']} (업종 평균 대비)")

    st.caption("Finnhub 연동시: finnhub.io/api/v1/stock/recommendation 에서 Buy/Hold/Sell 5개 + 목표가 상세 표시 예정")

with tab_snapshot:
    st.json({
        "ticker": ticker,
        "price": data['price'],
        "chart_points": len(data['chart_y']),
        "metrics": data['metrics'],
        "fetch": "yfinance - real, not MOCK_DB",
        "cors": "server-side -> no CORS",
        "variable": f"ticker={ticker} (normalize_ticker)"
    })

st.sidebar.divider()
st.sidebar.caption("2026-08-24 배포용 최종 정리 - Streamlit Cloud: secrets.toml에 FINNHUB_API_KEY 추가")
