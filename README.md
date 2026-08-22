# 투자 종목 정밀진단 (Investment Deep Dive)

한국(KOSPI/KOSDAQ) + 미국 주식/ETF 개별 종목과 포트폴리오를 정밀진단하는 Streamlit 앱입니다.

## 📁 파일 구조
```
Invest-deepdive/
├── app.py                          # 메인: 포트폴리오 백테스트
├── requirements.txt                # 클라우드 자동 설치용
├── README.md                       # 설명서
└── pages/
    └── 2_Investment_Deep_Dive.py   # 투자 종목 정밀진단 (Investment Deep Dive)
```

## 🚀 주요 기능

### [1] 포트폴리오 백테스트
- 최대 20종목 (AAPL + 005930.KS 혼합 가능), 벤치마크(SPY), 배당재투자, 리밸런싱
- 18개 성과지표, Drawdown, Rolling Returns

### [2] 투자 종목 정밀진단 (Investment Deep Dive) - 핵심
- **대상:** 개별 주식 + ETF (AAPL, NVDA, QQQ, SCHD, 005930.KS 모두 가능)
- **지표:** PER, Forward PER, PBR, ROE, 영업이익률, 배당수익률, 배당성향, 부채비율
- **비교:** 현재 값 vs 동종 섹터 평균 vs S&P500 평균
- **분석 요약:** 🟢 저평가/우수, 🟡 적정/보통, 🔴 고평가/주의 자동 판정
- **차트:** PER/ROE/배당수익률 비교 Bar Chart

## 🛠️ 데이터 소스
- 주가/재무: `yfinance` (무료, 키 불필요)
- 섹터 평균: 1차 하드코딩, 2차 FMP/Finnhub API로 교체 예정

## 🔧 배포
1. `app.py`, `requirements.txt`, `README.md`는 최상단
2. `2_Investment_Deep_Dive.py`는 `pages/` 폴더 안
3. GitHub Push → Streamlit Cloud 자동 재배포
