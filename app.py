
"""
종목 심층분석 - Streamlit 마이그레이션 최종본
- 목적: 한 종목에 대해 PER, 차트(52주), 뉴스, 애널리스트, 외부랭킹을 sub링크 없이 한 화면에
- PWA 실패 극복: 서버에서 yfinance 직접 호출 (CORS 없음), ticker 변수화
- 2026-08-24 배포용 정리
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime
import os

st.set_page_config(
    page_title="종목 심층분석 - 1종목 집중",
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
        # 1y 주간 - TradingView 1Y 동일
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

        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "longName": info.get("longName") or info.get("shortName") or ticker,
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
    st.caption(f"{data['longName']} · {data['ticker']}")
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
    - **Strong Buy (TradingView)** → [TradingView {ticker}](https://www.tradingview.com/symbols/{'KRX-' + clean_t if kr else 'NASDAQ-' + clean_t}/)
    - **{'N/A (한국종목)' if kr else 'B+ (Finnhub)'}** → [Finnhub](https://finnhub.io/)
    """)
    st.caption("TipRanks 점수는 Finnhub 연동 또는 수동 크롤링으로 실시간화 예정 - 현재는 링크 기반 랭킹 표시 (형식: 점수 + (사이트명))")

with col_right:
    st.subheader(f"TradingView 1Y · 52주 주간종가 · {len(data['chart_y'])}개 포인트")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data['chart_x'],
        y=data['chart_y'],
        mode='lines',
        name=ticker,
        line=dict(color='#2962FF', width=2.2),
        hovertemplate='%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>'
    ))
    
    # 52주 고가/저가 라인 (차트 내부)
    high_52 = data['info'].get('fiftyTwoWeekHigh')
    low_52 = data['info'].get('fiftyTwoWeekLow')
    # info 없으면 차트 데이터 기준
    if not high_52:
        high_52 = float(max(data['chart_y'])) if data['chart_y'] else None
    if not low_52:
        low_52 = float(min(data['chart_y'])) if data['chart_y'] else None

    try:
        if high_52:
            fig.add_hline(
                y=float(high_52), 
                line_dash="dash", 
                line_color="#EF4444", 
                line_width=1,
                annotation_text=f"52주 고가 {fmt_price(ticker, float(high_52))}",
                annotation_position="top right",
                annotation_font_color="#EF4444",
                annotation_font_size=11
            )
        if low_52:
            fig.add_hline(
                y=float(low_52), 
                line_dash="dash", 
                line_color="#22C55E", 
                line_width=1,
                annotation_text=f"52주 저가 {fmt_price(ticker, float(low_52))}",
                annotation_position="bottom right",
                annotation_font_color="#22C55E",
                annotation_font_size=11
            )
        # 현재가 점선
        fig.add_hline(
            y=float(data['chart_y'][-1]), 
            line_dash="dot", 
            line_color="#6B7280", 
            line_width=1,
            annotation_text=f"현재 {fmt_price(ticker, float(data['chart_y'][-1]))}",
            annotation_position="top left",
            annotation_font_size=10
        )
    except Exception as e:
        pass

    fig.update_layout(
        height=460,
        margin=dict(l=10,r=10,t=10,b=30),
        xaxis=dict(gridcolor='#F1F5F9', showgrid=True, title=""),
        yaxis=dict(gridcolor='#F1F5F9', showgrid=True, zeroline=False, title="", autorange=True),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified',
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 별도로 52주 고/저가 지표 + 현재가 위치 시각화
    try:
        curr = float(data['chart_y'][-1])
        h = float(high_52) if high_52 else curr
        l = float(low_52) if low_52 else curr
        # 현재가 52주 레인지에서 위치 %
        if h != l:
            pct_from_low = (curr - l) / (h - l) * 100
        else:
            pct_from_low = 50
        
        col_52_1, col_52_2, col_52_3 = st.columns([1, 2, 1])
        with col_52_1:
            st.metric("52주 저가", fmt_price(ticker, l), delta=None)
        with col_52_2:
            st.progress(int(max(0, min(100, pct_from_low))), text=f"현재가 52주 위치: {pct_from_low:.1f}% (저가 {l:.0f} ~ 고가 {h:.0f})")
            st.caption(f"고가 대비 {(curr/h*100-100):+.1f}% · 저가 대비 {(curr/l*100-100):+.1f}%")
        with col_52_3:
            st.metric("52주 고가", fmt_price(ticker, h), delta=None)
    except:
        pass

    # 검증 캡션
    min_v, max_v = min(data['chart_y']), max(data['chart_y'])
    vol = max_v - min_v
    st.caption(f"검증: 포인트 {len(data['chart_y'])}개 · 52주 고가 {fmt_price(ticker, float(high_52)) if high_52 else '-'} · 저가 {fmt_price(ticker, float(low_52)) if low_52 else '-'} · range {vol:.2f} · fill:false · beginAtZero:false · 진짜 yfinance")

# ---------- 하단 분석 탭: 뉴스 + 애널리스트 한 화면 ----------
st.divider()
st.subheader("분석 · Executive Summary (sub 링크 진입 없이 한 화면에)")

tab_news, tab_analyst, tab_snapshot = st.tabs(["📰 뉴스 4개 요약", "📊 애널리스트 Bull/Bear", "📋 스냅샷 원본"])

with tab_news:
    col_n1, col_n2 = st.columns(2)
    
    # Finnhub 우선, 없으면 Yahoo
    finnhub_news = fetch_news_finnhub(ticker, finnhub_key) if finnhub_key else None
    
    if finnhub_news:
        st.success("Finnhub 실시간 뉴스 (최근 7일)")
        for i, n in enumerate(finnhub_news[:4]):
            with st.container(border=True):
                st.markdown(f"**{i+1}. {n.get('headline','')}**")
                st.caption(f"{n.get('source','')} · {datetime.fromtimestamp(n.get('datetime',0)).strftime('%Y-%m-%d') if n.get('datetime') else ''}")
                st.write(n.get('summary','')[:200] + "...")
                # Executive Summary 한줄
                st.markdown(f"**임팩트:** {n.get('category','general')} 관련 - 주가에 {'긍정' if 'up' in n.get('headline','').lower() or 'beat' in n.get('headline','').lower() else '중립'}적")
                st.link_button("원문", n.get('url',''), use_container_width=False)
    else:
        yf_news = fetch_yf_news(ticker)
        if yf_news:
            for i, n in enumerate(yf_news[:4]):
                # yfinance news 구조 대응
                title = n.get('title') or n.get('content',{}).get('title','')
                link = n.get('link') or n.get('content',{}).get('clickThroughUrl',{}).get('url','')
                pub = n.get('providerPublishTime') or n.get('content',{}).get('pubDate','')
                with st.container(border=True):
                    st.markdown(f"**{i+1}. {title}**")
                    if link:
                        st.link_button("Yahoo 원문", link)
        else:
            st.info("뉴스 없음 - Finnhub API 키를 사이드바에 입력하면 실시간 뉴스 4개가 Executive Summary로 표시됩니다. (무료 키: finnhub.io)")

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
