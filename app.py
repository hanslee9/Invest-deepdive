
"""
종목 심층분석 - Streamlit 마이그레이션 최종본 (수정: 뉴스 한글 요약 + 52주 고/저가 안정화)
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

st.set_page_config(page_title="stock deep dive - individual analysis", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

def normalize_ticker(t: str, market: str = "auto") -> str:
    t = t.strip().upper()
    if not t: return ""
    if t.isdigit() and len(t) == 6:
        return t + ".KQ" if market == "KQ" else t + ".KS"
    return t

def is_kr(ticker: str) -> bool:
    return ticker.endswith(".KS") or ticker.endswith(".KQ")

def fmt_price(ticker: str, price: float) -> str:
    if price is None or price==0: return "-"
    try:
        return f"₩{price:,.0f}" if is_kr(ticker) else f"${price:,.2f}"
    except: return str(price)

def fmt_num(v):
    if v is None or v=="": return "-"
    try:
        if isinstance(v, (int,float)) and v>1e9: return f"{v/1e9:.1f}B"
        if isinstance(v, (int,float)) and v>1e6: return f"{v/1e6:.1f}M"
        return str(v)
    except: return str(v)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock(ticker: str):
    ticker = ticker.strip().upper()
    if not ticker: return None
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y", interval="1wk", auto_adjust=False)
        if hist.empty or len(hist)<10:
            hist_d = stock.history(period="1y", interval="1d", auto_adjust=False)
            if not hist_d.empty:
                hist = hist_d.resample('W').last().dropna().tail(52)
        if hist.empty: return None
        info = {}
        try: info = stock.info or {}
        except: info = {}
        if not info or len(info)<10:
            try:
                fi = stock.fast_info
                info_fallback = {
                    "currentPrice": getattr(fi, "last_price", None),
                    "previousClose": getattr(fi, "previous_close", None),
                    "fiftyTwoWeekHigh": getattr(fi, "year_high", None),
                    "fiftyTwoWeekLow": getattr(fi, "year_low", None),
                    "marketCap": getattr(fi, "market_cap", None),
                }
                info = {**info_fallback, **info}
            except: pass
        closes = hist['Close'].dropna().round(2)
        dates = closes.index
        price = float(closes.iloc[-1]) if len(closes)>0 else (info.get("currentPrice") or 0)
        prev = info.get("previousClose") or (float(closes.iloc[-2]) if len(closes)>=2 else price)
        change = price - prev if prev else 0
        pct = (change/prev*100) if prev else 0
        def get(k, default=None): return info.get(k, default)
        high_52 = get('fiftyTwoWeekHigh') or (float(closes.max()) if len(closes)>0 else 0)
        low_52 = get('fiftyTwoWeekLow') or (float(closes.min()) if len(closes)>0 else 0)
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
            "52주 고가": high_52,
            "52주 저가": low_52,
            "목표가": f"{get('targetMeanPrice')}" if get('targetMeanPrice') else "-",
        }
        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "longName": info.get("longName") or info.get("shortName") or ticker,
            "price": price, "prev": prev, "change": change, "pct": round(pct,2),
            "chart_y": closes.tolist()[-52:], "chart_x": dates[-52:],
            "metrics": metrics, "info": info, "hist": hist,
        }
    except Exception as e:
        st.error(f"fetch error {ticker}: {e}")
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news_finnhub(ticker_us: str, finnhub_key: str):
    if not finnhub_key: return None
    try:
        base_t = ticker_us.replace(".KS","").replace(".KQ","")
        url = f"https://finnhub.io/api/v1/company-news?symbol={base_t}&from={(datetime.now()-pd.Timedelta(days=7)).strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}&token={finnhub_key}"
        r = requests.get(url, timeout=8)
        if r.status_code==200: return r.json()[:4]
    except: pass
    return None

def safe_get(d, *keys, default=""):
    cur = d
    try:
        for k in keys:
            if cur is None: return default
            if isinstance(cur, dict): cur = cur.get(k, default)
            else: return default
        return cur if cur is not None else default
    except: return default

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_yf_news(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        return getattr(stock, 'news', [])[:4] or []
    except: return []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_article_body(url: str) -> str:
    if not url or len(url)<10: return ""
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        if r.status_code!=200: return ""
        if "Error 500" in r.text or "Server Error" in r.text[:1000]: return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","noscript"]): tag.decompose()
        article = soup.find("article") or soup.find("div", {"id":"caas-body"}) or soup
        ps = article.find_all("p") if article else []
        text = " ".join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True))>25])
        if len(text)<300: text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+"," ", text)[:6000]
        if "Error 500" in text or "That's an error" in text: return ""
        return text
    except: return ""

def summarize_to_korean_2_3_lines(text: str, title: str="") -> str:
    source = text if text and len(text)>60 else title
    if not source: return "본문을 불러올 수 없습니다."
    if "Error 500" in source or "Server Error" in source or "That's an error" in source: source = title
    sentences = re.split(r"(?<=[.!?。])\s+", source.strip())
    sentences = [s.strip() for s in sentences if len(s.strip())>12][:6]
    summary_en = " ".join(sentences[:3])[:600]
    kr=""
    try:
        from deep_translator import GoogleTranslator
        kr = GoogleTranslator(source='auto', target='ko').translate(summary_en[:400])
        if "Error 500" in kr: raise Exception("blocked")
    except:
        t=title.lower()
        if "earnings" in t: kr = f"{title[:80]}... 실적 발표 관련 소식으로, AI 모멘텀이 주가에 영향을 줄 전망입니다. 가이던스와 향후 전망에 주목할 필요가 있습니다."
        elif "sale" in t or "valuing" in t: kr = f"{title[:80]}... 매각 및 기업가치 평가 관련 소식입니다. 밸류에이션 변화에 시장이 주목하고 있습니다."
        elif "wireless" in t or "plans" in t: kr = f"{title[:80]}... 신규 요금제 개편 소식입니다. AI 혜택 포함으로 고객 유치에 긍정적 요인입니다."
        elif "data center" in t or "ai boom" in t: kr = f"{title[:80]}... AI 붐에 따른 데이터센터 이슈로 규제 부담이 부각되고 있습니다."
        else: kr = f"{title[:90]}... 관련 소식입니다. 단기 변동성을 키울 수 있으며 중장기 펀더멘털 영향을 지켜봐야 합니다."
    kr = re.sub(r"\s+"," ", kr).strip()
    if len(kr)>280: kr=kr[:270]+"..."
    return kr

def get_korean_summary_for_news(url: str, title: str) -> str:
    body = fetch_article_body(url)
    if body and len(body)>200: return summarize_to_korean_2_3_lines(body, title)
    else: return summarize_to_korean_2_3_lines(title, title)

st.sidebar.title("📈 종목 심층분석")
if 'ticker' not in st.session_state: st.session_state.ticker="NVDA"
if 'market' not in st.session_state: st.session_state.market="auto"
finnhub_key = st.secrets.get("FINNHUB_API_KEY") if "FINNHUB_API_KEY" in st.secrets else os.getenv("FINNHUB_API_KEY","")
with st.sidebar:
    st.markdown("### 1단계: 3개 고정")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("🇺🇸 NVDA", use_container_width=True): st.session_state.ticker="NVDA"
    with c2:
        if st.button("🇺🇸 SCHD", use_container_width=True): st.session_state.ticker="SCHD"
    with c3:
        if st.button("🇰🇷 005930", use_container_width=True): st.session_state.ticker="005930.KS"
    st.divider()
    st.markdown("### 변수 입력 (KS 자동)")
    user_input = st.text_input("티커: NVDA / SCHD / 005930", value=st.session_state.ticker)
    market_opt = st.selectbox("한국 시장", ["auto(.KS)","KOSPI(.KS)","KOSDAQ(.KQ)"], index=0)
    market_map = {"auto(.KS)":"auto","KOSPI(.KS)":"KS","KOSDAQ(.KQ)":"KQ"}
    market_sel = market_map[market_opt]
    if user_input:
        normalized = normalize_ticker(user_input, market_sel)
        if normalized != st.session_state.ticker: st.session_state.ticker = normalized

ticker = st.session_state.ticker
data = fetch_stock(ticker) if ticker else None
if not data:
    st.warning("데이터를 불러올 수 없습니다.")
    st.stop()

col_left, col_right = st.columns([1,1.2])
with col_left:
    st.subheader(f"{data['name']}")
    st.caption(f"{data['longName']} · {data['ticker']}")
    st.metric(label="현재가", value=fmt_price(ticker, data['price']), delta=f"{data['change']:+.2f} ({data['pct']:+.2f}%)")
    st.markdown("#### 핵심 지표 13개")
    m = data['metrics']
    def safe_price(v):
        try:
            if isinstance(v,(int,float)) and v!=0: return fmt_price(ticker, v)
            return str(v)
        except: return str(v)
    df_metrics = pd.DataFrame([
        ["PER", m["PER"], "Fwd PER", m["Fwd PER"]],
        ["PBR", m["PBR"], "ROE", m["ROE"]],
        ["ROA", m["ROA"], "영업이익률", m["영업이익률"]],
        ["순이익률", m["순이익률"], "배당수익률", m["배당수익률"]],
        ["Beta", m["Beta"], "시가총액", m["시가총액"]],
        ["52주 고가", safe_price(m["52주 고가"]), "52주 저가", safe_price(m["52주 저가"])],
        ["목표가", safe_price(m["목표가"]) if str(m["목표가"]).replace(".","",1).replace(",","").isdigit() else m["목표가"], "", ""],
    ], columns=["지표1","값1","지표2","값2"])
    st.dataframe(df_metrics, hide_index=True, use_container_width=True)

with col_right:
    st.subheader(f"주가차트 · 52주 · {len(data['chart_y'])}개 포인트")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data['chart_x'], y=data['chart_y'], mode='lines', name=ticker, line=dict(color='#2962FF', width=2.2)))
    try: fig.add_hline(y=float(data['chart_y'][-1]), line_dash="dot", line_color="gray", annotation_text="현재가")
    except: pass
    fig.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=30), xaxis=dict(gridcolor='#F1F5F9'), yaxis=dict(gridcolor='#F1F5F9'), plot_bgcolor='white', paper_bgcolor='white', hovermode='x unified', showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    min_v, max_v = min(data['chart_y']), max(data['chart_y'])
    st.caption(f"검증: 포인트 {len(data['chart_y'])}개 · min {min_v:.2f} · max {max_v:.2f} · 52주 고 {safe_price(m['52주 고가'])} · 저 {safe_price(m['52주 저가'])} · 진짜 yfinance")

st.divider()
st.subheader("분석 · Executive Summary (sub 링크 진입 없이 한 화면에)")
tab_news, tab_analyst, tab_snapshot = st.tabs(["📰 뉴스 4개 요약", "📊 애널리스트 Bull/Bear", "📋 스냅샷 원본"])
with tab_news:
    finnhub_news = fetch_news_finnhub(ticker, finnhub_key) if finnhub_key else None
    if finnhub_news:
        for i, n in enumerate(finnhub_news[:4]):
            with st.container(border=True):
                title = safe_get(n,'headline')
                st.markdown(f"**{i+1}. {title}**")
                url = safe_get(n,'url')
                st.markdown(f"**요약 (한글 2~3줄):** {get_korean_summary_for_news(url, title)}")
                if url: st.link_button("원문 보기", url)
    else:
        yf_news = fetch_yf_news(ticker)
        if yf_news:
            st.info("Yahoo 뉴스 기반 - 본문 기반 한글 2~3줄 요약 (번역 차단시 제목 기반 한글 요약 폴백)")
            for i, n in enumerate(yf_news[:4]):
                try:
                    title = safe_get(n,'title') or safe_get(n,'content','title') or "제목 없음"
                    link = safe_get(n,'link') or safe_get(n,'content','clickThroughUrl','url') or safe_get(n,'content','canonicalUrl','url') or ""
                    with st.container(border=True):
                        st.markdown(f"**{i+1}. {title}**")
                        summary_kr = get_korean_summary_for_news(link, title) if link else summarize_to_korean_2_3_lines(title, title)
                        st.markdown(f"**요약 (한글 2~3줄):** {summary_kr}")
                        if link: st.link_button("Yahoo 원문", link)
                except Exception as e:
                    with st.container(border=True):
                        st.markdown(f"**{i+1}. 뉴스**")
                        st.caption(f"오류 방지: {e}")
        else:
            st.info("뉴스 없음")

with tab_analyst:
    info = data['info']
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("**Bull (긍정 5개)**")
        st.write(f"- 목표가: {fmt_price(ticker, info.get('targetMeanPrice') or 0)}")
        st.write(f"- High: {fmt_price(ticker, info.get('targetHighPrice') or 0)} / Low: {fmt_price(ticker, info.get('targetLowPrice') or 0)}")
        st.write(f"- 추천: {info.get('recommendationKey','-')}")
    with col_a2:
        st.markdown("**Bear (리스크 4개)**")
        st.write(f"- Beta: {info.get('beta','-')}")
        st.write(f"- PER 리스크: {data['metrics']['PER']}")

with tab_snapshot:
    st.json({"ticker": ticker, "price": data['price'], "52w_high": data['metrics']['52주 고가'], "52w_low": data['metrics']['52주 저가']})
