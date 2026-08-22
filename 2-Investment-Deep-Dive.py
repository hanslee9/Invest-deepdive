import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Investment Deep Dive", layout="wide")

SECTOR_AVG = {
    "Technology": {"PER": 28.4, "Forward PER": 24.1, "PBR": 8.2, "ROE": 25.0, "ROIC": 18.0, "배당수익률": 1.10, "배당성향": 35.0, "영업이익률": 28.0, "부채비율": 60.0},
    "Financial Services": {"PER": 12.5, "Forward PER": 11.2, "PBR": 1.5, "ROE": 12.0, "ROIC": 8.0, "배당수익률": 2.8, "배당성향": 40.0, "영업이익률": 35.0, "부채비율": 250.0},
    "Healthcare": {"PER": 24.0, "Forward PER": 20.5, "PBR": 4.5, "ROE": 18.0, "ROIC": 12.0, "배당수익률": 1.5, "배당성향": 38.0, "영업이익률": 22.0, "부채비율": 70.0},
    "Consumer Cyclical": {"PER": 22.0, "Forward PER": 19.0, "PBR": 5.5, "ROE": 20.0, "ROIC": 13.0, "배당수익률": 1.8, "배당성향": 35.0, "영업이익률": 12.0, "부채비율": 90.0},
}
SP500_AVG = {"PER": 22.1, "Forward PER": 19.5, "PBR": 4.1, "ROE": 18.0, "ROIC": 11.0, "배당수익률": 1.45, "배당성향": 32.0, "영업이익률": 15.5, "부채비율": 85.0}

def get_fundamentals(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info or {}
    data = {
        "티커": ticker_symbol.upper(),
        "이름": info.get('longName', ticker_symbol.upper()),
        "현재가": info.get('currentPrice', info.get('regularMarketPrice', 0)),
        "섹터": info.get('sector', 'Technology'),
        "산업": info.get('industry', ''),
        "PER": info.get('trailingPE', None),
        "Forward PER": info.get('forwardPE', None),
        "PBR": info.get('priceToBook', None),
        "ROE": (info.get('returnOnEquity', 0) * 100) if info.get('returnOnEquity') else None,
        "배당수익률": (info.get('dividendYield', 0) * 100) if info.get('dividendYield') else 0,
        "배당성향": (info.get('payoutRatio', 0) * 100) if info.get('payoutRatio') else 0,
        "영업이익률": (info.get('operatingMargins', 0) * 100) if info.get('operatingMargins') else None,
        "부채비율": (info.get('debtToEquity', 0)) if info.get('debtToEquity') else None,
        "시가총액": info.get('marketCap', None),
    }
    return data, info

def analyze_metric(metric_name, value, sector_avg, sp_avg):
    if value is None:
        return "데이터 없음", "⚪", "데이터 없음"
    try:
        if metric_name in ["PER", "Forward PER", "PBR", "부채비율"]:
            if value < sector_avg * 0.9:
                return "저평가", "🟢", f"섹터({sector_avg}) 대비 낮음"
            elif value > sector_avg * 1.2:
                return "고평가", "🔴", f"섹터({sector_avg}) 대비 {((value/sector_avg-1)*100):.0f}% 높음"
            else:
                return "적정", "🟡", "섹터 평균 수준"
        elif metric_name in ["ROE", "영업이익률"]:
            if value > sector_avg * 1.2:
                return "우수", "🟢", f"섹터({sector_avg}%) 대비 우수"
            elif value < sector_avg * 0.8:
                return "주의", "🔴", f"섹터({sector_avg}%) 대비 낮음"
            else:
                return "보통", "🟡", "섹터 평균 수준"
        elif metric_name in ["배당수익률"]:
            if value > sector_avg:
                return "고배당", "🟢", f"섹터({sector_avg}%)보다 높음"
            elif value < 0.5:
                return "저배당", "⚪", "성장/자사주 선호"
            else:
                return "보통", "🟡", "평균 수준"
        else:
            return "보통", "🟡", "-"
    except:
        return "보통", "🟡", "-"

# --- UI Title: 1안 적용 ---
st.title("투자 종목 정밀진단 (Investment Deep Dive)")
st.caption("Tab 2 | 단일 종목 및 ETF 재무제표 비교 | yfinance 기반, API 키 불필요 | 예: AAPL, NVDA, QQQ, 005930.KS")

ticker_input = st.text_input("티커 입력 (Ticker)", value="AAPL").upper().strip()

if st.button("🔍 분석 실행 (Analyze)", type="primary") and ticker_input:
    with st.spinner(f"{ticker_input} 데이터 로딩..."):
        data, raw_info = get_fundamentals(ticker_input)
    
    sector = data.get("섹터", "Technology")
    if sector not in SECTOR_AVG:
        sector = "Technology"
    sector_avg = SECTOR_AVG[sector]
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("종목 / Ticker", f"{data['티커']} - {data['이름'][:25]}", f"{sector}")
    c2.metric("현재가 / Price", f"${data['현재가']:.2f}" if data['현재가'] else "N/A")
    c3.metric("시가총액 / Market Cap", f"${data['시가총액']/1e12:.2f}T" if data['시가총액'] else "N/A")

    st.subheader("주요 재무지표 현황 및 분석 / Key Financials")
    rows = []
    for metric in ["PER", "Forward PER", "PBR", "ROE", "영업이익률", "배당수익률", "배당성향", "부채비율"]:
        val = data.get(metric)
        s_avg = sector_avg.get(metric, 0)
        sp_avg = SP500_AVG.get(metric, 0)
        status, icon, comment = analyze_metric(metric, val, s_avg, sp_avg)
        if val is None:
            val_str = "-"
        elif metric in ["ROE", "영업이익률", "배당수익률", "배당성향"]:
            val_str = f"{val:.2f}%"
        elif metric == "부채비율":
            val_str = f"{val:.0f}%"
        else:
            val_str = f"{val:.2f}"
        rows.append({
            "지표 / Metric": metric,
            f"{data['티커']} 현재": val_str,
            "분석 요약 / Summary": f"{icon} {status}",
            f"{sector} Avg": f"{s_avg}",
            "S&P500 Avg": f"{sp_avg}",
            "코멘트 / Comment": comment,
        })
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("비교 차트 / Comparison Chart")
    chart_df = pd.DataFrame([
        {"구분": data['티커'], "PER": data.get("PER", 0) or 0, "ROE": data.get("ROE", 0) or 0, "배당수익률": data.get("배당수익률", 0) or 0},
        {"구분": f"{sector} Avg", "PER": sector_avg["PER"], "ROE": sector_avg["ROE"], "배당수익률": sector_avg["배당수익률"]},
        {"구분": "S&P500 Avg", "PER": SP500_AVG["PER"], "ROE": SP500_AVG["ROE"], "배당수익률": SP500_AVG["배당수익률"]},
    ])
    t1, t2, t3 = st.tabs(["PER", "ROE", "배당수익률 / Dividend Yield"])
    with t1:
        st.bar_chart(chart_df, x="구분", y="PER")
    with t2:
        st.bar_chart(chart_df, x="구분", y="ROE")
    with t3:
        st.bar_chart(chart_df, x="구분", y="배당수익률")

    with st.expander("Raw info (디버깅)"):
        st.json(raw_info)
