
"""
종목 심층분석 Streamlit - 1종목 집중 - 변수 ticker
PWA 실패 원인: 브라우저 CORS로 Yahoo Finance 실시간 호출 불가
Streamlit 해결: 서버에서 yfinance 직접 호출, ticker 변수 가능

Usage:
  pip install streamlit yfinance plotly pandas
  streamlit run app.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="종목 심층분석 - 1종목 집중", layout="wide")

def normalize_ticker(t: str) -> str:
    """한국종목 005930 -> 005930.KS 자동"""
    t = t.strip().upper()
    if not t:
        return ""
    # 숫자 6자리만 입력시 .KS 자동 추가
    if t.isdigit() and len(t) == 6:
        return t + ".KS"
    return t

def is_kr(ticker: str) -> bool:
    return ".KS" in ticker or ".KQ" in ticker

def fmt_price(ticker: str, price: float) -> str:
    if is_kr(ticker):
        return f"₩{price:,.0f}"
    return f"${price:,.2f}"

@st.cache_data(ttl=3600)
def fetch_stock(ticker: str):
    ticker = normalize_ticker(ticker)
    if not ticker:
        return None
    
    try:
        stock = yf.Ticker(ticker)
        # 1년 주간 데이터 - TradingView 동일 52주
        hist = stock.history(period="1y", interval="1wk", auto_adjust=False)
        if hist.empty:
            hist = stock.history(period="1y", interval="1d")
            hist = hist.resample('W').last().tail(52)
        
        info = stock.info
        
        # 차트 데이터 52개
        closes = hist['Close'].dropna().round(2).tolist()[-52:]
        dates = hist.index[-52:]
        
        # 메트릭
        price = float(closes[-1]) if closes else info.get('currentPrice', 0)
        prev = info.get('previousClose', price)
        change = price - prev
        pct = (change / prev * 100) if prev else 0
        
        metrics = {
            "PER": round(info.get('trailingPE', 0), 1) if info.get('trailingPE') else "-",
            "Fwd PER": round(info.get('forwardPE', 0), 1) if info.get('forwardPE') else "-",
            "PBR": round(info.get('priceToBook', 0), 1) if info.get('priceToBook') else "-",
            "ROE": f"{info.get('returnOnEquity', 0)*100:.1f}%" if info.get('returnOnEquity') else "-",
            "영업이익률": f"{info.get('operatingMargins', 0)*100:.1f}%" if info.get('operatingMargins') else "-",
            "배당수익률": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "-",
            "시가총액": f"{info.get('marketCap', 0):,}" if info.get('marketCap') else "-",
            "52주 고가": info.get('fiftyTwoWeekHigh', 0),
            "52주 저가": info.get('fiftyTwoWeekLow', 0),
            "Beta": info.get('beta', 0),
        }
        
        return {
            "ticker": ticker,
            "name": info.get('shortName', ticker),
            "longName": info.get('longName', ticker),
            "price": price,
            "change": change,
            "pct": round(pct, 2),
            "chart": closes,
            "dates": dates,
            "metrics": metrics,
            "info": info,
        }
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}")
        return None

# UI
st.title("종목 심층분석 PWA → Streamlit 마이그레이션")
st.caption("1종목 집중 · 한 화면에 모든 데이터 · ticker는 변수 · KS 자동 처리")

# Sidebar - 3개 고정 + 변수 입력
st.sidebar.header("관심종목 (3개 고정)")
col1, col2, col3 = st.sidebar.columns(3)
# 3개 고정 버튼
if 'ticker' not in st.session_state:
    st.session_state.ticker = "NVDA"

if st.sidebar.button("🇺🇸 NVDA\n(미국종목)", use_container_width=True):
    st.session_state.ticker = "NVDA"
if st.sidebar.button("🇺🇸 SCHD\n(미국ETF)", use_container_width=True):
    st.session_state.ticker = "SCHD"
if st.sidebar.button("🇰🇷 005930\n(한국종목)", use_container_width=True):
    st.session_state.ticker = "005930.KS"

st.sidebar.divider()
st.sidebar.subheader("변수 입력 (KS 자동)")
user_input = st.sidebar.text_input(
    "티커 입력: NVDA / SCHD / 005930 → 005930.KS 자동 변환",
    value=st.session_state.ticker,
    placeholder="예: 005930 입력시 자동 .KS"
)

ticker = normalize_ticker(user_input) if user_input else st.session_state.ticker

# 검증 정보
st.sidebar.info(f"""
**검증:**
- 입력: {user_input} → 정규화: {ticker}
- KS 자동: {'✓' if ticker.endswith('.KS') else '미국종목/ETF'}
- 변수 ticker: {ticker} (코딩 입장에서는 변수)
""")

# Main content
if ticker:
    with st.spinner(f"{ticker} 데이터 가져오는 중... (yfinance 서버 직접 호출 - CORS 없음)"):
        data = fetch_stock(ticker)
    
    if data:
        # Header
        col_price, col_chart = st.columns([1, 2])
        
        with col_price:
            st.subheader(f"{data['name']} ({ticker})")
            st.metric(
                label=f"{ticker} · {data.get('longName','')}",
                value=fmt_price(ticker, data['price']),
                delta=f"{data['pct']:.2f}%"
            )
            
            # Metrics
            st.write("**핵심 지표**")
            metrics_df = pd.DataFrame(list(data['metrics'].items()), columns=["지표", "값"])
            st.dataframe(metrics_df, hide_index=True, use_container_width=True)
            
            # External links
            st.write("**🏆 외부 랭킹**")
            st.markdown(f"""
            - [TipRanks {ticker.replace('.KS','')}](https://www.tipranks.com/stocks/{ticker.replace('.KS','')})
            - [Yahoo Finance {ticker} 분석](https://finance.yahoo.com/quote/{ticker}/analysis)
            - [TradingView {ticker}](https://www.tradingview.com/symbols/{'KRX-' + ticker.replace('.KS','') if is_kr(ticker) else 'NASDAQ-' + ticker}/)
            """)
        
        with col_chart:
            st.subheader(f"TradingView 1Y 52주 주간종가 · {len(data['chart'])}개 포인트")
            
            # Plotly chart - TradingView 스타일
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data['dates'],
                y=data['chart'],
                mode='lines',
                name=ticker,
                line=dict(color='#2962FF', width=2),
                fill=None,
            ))
            
            fig.update_layout(
                height=400,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(
                    gridcolor='#F1F5F9',
                    showgrid=True,
                    title="",
                ),
                yaxis=dict(
                    gridcolor='#F1F5F9',
                    showgrid=True,
                    zeroline=False,
                    title="",
                    autorange=True,  # beginAtZero:false
                ),
                plot_bgcolor='white',
                paper_bgcolor='white',
                hovermode='x unified',
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Verification
            min_val = min(data['chart'])
            max_val = max(data['chart'])
            st.caption(f"검증: 포인트 {len(data['chart'])}개 · min {min_val} · max {max_val} · range {max_val-min_val:.1f} · 변동성 {'높음 ✓' if (max_val-min_val)>20 else '낮음'} · TradingView 1Y 주간 동일 · fill 없음 · beginAtZero:false · 진짜 yfinance 데이터")

        # Analysis tab (mock - can be replaced with real news/analyst from Finnhub)
        st.divider()
        st.subheader("분석 · 한 화면에 Executive Summary (sub 링크 진입 없음)")
        
        col_news, col_analyst = st.columns(2)
        with col_news:
            st.write("**최신 뉴스 · Executive Summary**")
            st.info("Finnhub API 연동시 실시간 뉴스 표시 - 현재는 yfinance info 기반")
            st.write(f"**{data['name']}** 관련 뉴스 (Finnhub 연동 필요)")
        
        with col_analyst:
            st.write("**애널리스트 · Bull/Bear**")
            st.write(f"Yahoo Finance 목표가: {data['info'].get('targetMeanPrice', '-')}")

else:
    st.warning("티커를 입력하세요: NVDA / SCHD / 005930 (KS 자동)")
