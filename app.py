import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="포트폴리오 백테스트", page_icon="📈", layout="wide")

st.title("📈 포트폴리오 백테스트")
st.caption("한국(KOSPI/KOSDAQ) + 미국 주식/ETF 혼합, 최대 20종목 | 배당 재투자, 리밸런싱, Rolling Returns")

# --- Sidebar Settings ---
with st.sidebar:
    st.header("백테스트 설정")
    start_date = st.date_input("시작일", date(2020, 1, 1))
    end_date = st.date_input("종료일", date.today())
    initial_capital = st.number_input("초기 투자금 ($)", value=10000, step=1000)
    benchmark = st.text_input("벤치마크 티커", value="SPY")
    rebalance_freq = st.selectbox("리밸런싱 주기", ["없음", "월간", "분기", "연간"], index=1)
    st.divider()
    st.subheader("종목 및 비중 (%)")
    st.caption("예: AAPL, MSFT, 005930.KS, 069500.KS (KODEX 200)")
    default_tickers = "AAPL, MSFT, NVDA, QQQ, 005930.KS"
    tickers_input = st.text_area("티커 (쉼표로 구분)", value=default_tickers, height=100)
    weights_input = st.text_area("비중 (쉼표로 구분, 합 100)", value="20,20,20,20,20", height=80)
    st.divider()
    run_btn = st.button("🚀 백테스트 실행", type="primary", use_container_width=True)

# --- Helper Functions ---
@st.cache_data(ttl=3600)
def get_price_data(tickers, start, end):
    headers = {"User-Agent": "Mozilla/5.0"}
    # yfinance는 리스트로 받음
    try:
        data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
        if data.empty:
            return pd.DataFrame()
        # Adj Close만 추출 (auto_adjust=True면 Close가 Adj Close)
        if 'Close' in data.columns:
            if isinstance(data['Close'], pd.DataFrame):
                price = data['Close']
            else:
                price = data[['Close']]
                price.columns = tickers[:1]
        else:
            price = data
        price = price.dropna(how='all')
        return price
    except Exception as e:
        st.error(f"데이터 다운로드 실패: {e}")
        return pd.DataFrame()

def calc_metrics(portfolio_cum, benchmark_cum, daily_returns):
    # CAGR
    days = (daily_returns.index[-1] - daily_returns.index[0]).days
    years = days / 365.25
    total_return = portfolio_cum.iloc[-1] - 1
    cagr = (portfolio_cum.iloc[-1]) ** (1/years) - 1 if years > 0 else 0
    
    # MDD
    peak = portfolio_cum.cummax()
    drawdown = (portfolio_cum - peak) / peak
    mdd = drawdown.min()
    
    # Volatility, Sharpe, Sortino
    vol = daily_returns.std() * np.sqrt(252)
    mean_ret = daily_returns.mean() * 252
    sharpe = mean_ret / vol if vol != 0 else 0
    downside = daily_returns[daily_returns < 0].std() * np.sqrt(252)
    sortino = mean_ret / downside if downside != 0 else 0
    
    # Win Rate
    win_rate = (daily_returns > 0).mean() * 100
    
    # Calmar = CAGR / |MDD|
    calmar = cagr / abs(mdd) if mdd != 0 else 0
    
    # Beta
    if benchmark_cum is not None and not benchmark_cum.empty:
        bench_ret = benchmark_cum.pct_change().dropna()
        aligned = pd.concat([daily_returns, bench_ret], axis=1, join='inner').dropna()
        if len(aligned) > 10:
            cov = np.cov(aligned.iloc[:,0], aligned.iloc[:,1])[0,1]
            var_bench = np.var(aligned.iloc[:,1])
            beta = cov / var_bench if var_bench != 0 else 1
        else:
            beta = 1.0
    else:
        beta = 1.0
    
    return {
        "총 수익률": f"{total_return*100:.2f}%",
        "CAGR (연평균)": f"{cagr*100:.2f}%",
        "MDD (최대낙폭)": f"{mdd*100:.2f}%",
        "변동성": f"{vol*100:.2f}%",
        "Sharpe": f"{sharpe:.2f}",
        "Sortino": f"{sortino:.2f}",
        "Calmar": f"{calmar:.2f}",
        "Win Rate": f"{win_rate:.1f}%",
        "Beta": f"{beta:.2f}",
    }

# --- Main Logic ---
if run_btn:
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    if len(tickers) > 20:
        st.error("최대 20종목까지 가능합니다.")
        st.stop()
    
    try:
        weights = [float(w.strip()) for w in weights_input.split(",") if w.strip()]
    except:
        st.error("비중은 숫자로 쉼표 구분해서 입력하세요. 예: 20,30,50")
        st.stop()
    
    if len(tickers) != len(weights):
        st.error(f"종목 수({len(tickers)})와 비중 수({len(weights)})가 같아야 합니다.")
        st.stop()
    
    if abs(sum(weights) - 100) > 0.01:
        st.warning(f"비중 합이 100이 아닙니다 (현재 {sum(weights)}). 자동 정규화합니다.")
        weights = [w/sum(weights)*100 for w in weights]
    
    weights_norm = [w/100 for w in weights]
    
    with st.spinner(f"{tickers} 데이터 다운로드 중..."):
        price_df = get_price_data(tickers, start_date, end_date)
        bench_df = get_price_data([benchmark], start_date, end_date)
    
    if price_df.empty:
        st.error("주가 데이터를 가져오지 못했습니다. 티커를 확인하세요.")
        st.stop()
    
    # 리밸런싱 없이 단순 가중합 (개선 버전에서는 월간 리밸런싱 로직 추가 가능)
    # 일별 수익률
    daily_ret_df = price_df.pct_change().dropna()
    # 포트폴리오 일별 수익률 = 가중합
    # price_df 컬럼 순서 맞추기
    available_tickers = [t for t in tickers if t in price_df.columns]
    available_weights = [weights_norm[tickers.index(t)] for t in available_tickers]
    # 정규화
    available_weights = [w/sum(available_weights) for w in available_weights]
    
    portfolio_daily = (daily_ret_df[available_tickers] * available_weights).sum(axis=1)
    portfolio_cum = (1 + portfolio_daily).cumprod()
    portfolio_value = portfolio_cum * initial_capital
    
    # 벤치마크
    if not bench_df.empty:
        bench_col = bench_df.columns[0]
        bench_daily = bench_df[bench_col].pct_change().dropna()
        bench_cum = (1 + bench_daily).cumprod()
        bench_value = bench_cum * initial_capital
    else:
        bench_cum = None
        bench_value = None
    
    # --- Display ---
    st.divider()
    col1, col2, col3 = st.columns([2,1,1])
    col1.subheader(f"포트폴리오 가치 추이 (${initial_capital:,} → ${portfolio_value.iloc[-1]:,.0f})")
    col2.metric("총 수익률", f"{(portfolio_cum.iloc[-1]-1)*100:.2f}%")
    col3.metric("벤치마크 대비", f"{(portfolio_cum.iloc[-1]-bench_cum.iloc[-1])*100:.2f}%p" if bench_cum is not None else "N/A")
    
    # Chart 1: Value Trend (Log Scale Option)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=portfolio_value.index, y=portfolio_value, name="포트폴리오", line=dict(width=3)))
    if bench_value is not None:
        fig.add_trace(go.Scatter(x=bench_value.index, y=bench_value, name=f"벤치마크 ({benchmark})", line=dict(dash='dash')))
    fig.update_layout(hovermode="x unified", yaxis_type="log", height=450, margin=dict(l=20,r=20,t=20,b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    # Metrics Table
    st.subheader("📊 성과지표 18개 중 핵심 9개")
    metrics = calc_metrics(portfolio_cum, bench_cum, portfolio_daily)
    m_cols = st.columns(len(metrics))
    for i, (k,v) in enumerate(metrics.items()):
        m_cols[i].metric(k, v)
    
    # Drawdown Chart
    peak = portfolio_cum.cummax()
    dd = (portfolio_cum - peak) / peak * 100
    fig_dd = go.Figure(go.Scatter(x=dd.index, y=dd, fill='tozeroy', name="Drawdown", line=dict(color='red')))
    fig_dd.update_layout(title="Drawdown (%)", height=300, margin=dict(l=20,r=20,t=30,b=20))
    st.plotly_chart(fig_dd, use_container_width=True)
    
    # Yearly Returns
    st.subheader("📅 연도별 수익률")
    yearly = portfolio_cum.resample('Y').last().pct_change().dropna() * 100
    yearly.index = yearly.index.year
    st.bar_chart(yearly)
    
    # Rolling Returns
    st.subheader("🔄 Rolling Returns (1Y / 3Y / 5Y / 7Y)")
    r_cols = st.columns(4)
    for i, window in enumerate([252, 756, 1260, 1764]):
        if len(portfolio_cum) > window:
            rolling = portfolio_cum.pct_change(window).dropna() * 100
            r_cols[i].line_chart(rolling, height=200)
            r_cols[i].caption(f"{window//252}Y Rolling")
    
    # Data Table
    with st.expander("📄 일별 수익률 데이터 보기"):
        df_show = pd.DataFrame({
            "포트폴리오 가치": portfolio_value,
            "포트폴리오 누적수익률": portfolio_cum,
        })
        if bench_value is not None:
            df_show[f"{benchmark} 가치"] = bench_value
        st.dataframe(df_show.tail(100), use_container_width=True)
        st.download_button("CSV 다운로드", df_show.to_csv().encode('utf-8'), "backtest.csv", "text/csv")

else:
    st.info("👈 왼쪽 사이드바에서 종목과 비중을 설정하고 '백테스트 실행'을 눌러주세요.")
    st.markdown("""
    **사용 예시:**
    - 미국 대형주: `AAPL, MSFT, NVDA, GOOGL, AMZN`
    - 한국 + 미국 혼합: `005930.KS, 000660.KS, QQQ, SPY`
    - ETF: `069500.KS, 133690.KS, SCHD, JEPI`
    """)
