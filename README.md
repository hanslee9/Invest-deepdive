# 포트폴리오 백테스트 & 투자 종목 정밀진단 (Investment Deep Dive)

한국(KOSPI/KOSDAQ) + 미국 주식/ETF 혼합, 최대 20종목까지 백테스트 및 투자 종목 정밀진단을 제공하는 Streamlit 앱입니다.

## 📁 파일 구조 (최종 - 1안 적용)
```
portfolio-back-test/
├── app.py                          # 메인: 포트폴리오 백테스트
├── requirements.txt                # 클라우드 자동 설치용
├── README.md                       # 설명서
└── pages/
    └── 2_Investment_Deep_Dive.py   # 신규: 투자 종목 정밀진단 (Investment Deep Dive) - 영문 파일명
```

> GitHub/Streamlit 호환성을 위해 파일명은 영문 `2_Investment_Deep_Dive.py`를 사용하고, 화면 타이틀은 `투자 종목 정밀진단 (Investment Deep Dive)`로 표시됩니다.

## 🚀 주요 기능

### [Tab 1] 포트폴리오 백테스트 (기존)
- 최대 20종목, 벤치마크, 배당재투자, 리밸런싱
- 18개 성과지표, Drawdown, Rolling Returns

### [Tab 2] 투자 종목 정밀진단 (Investment Deep Dive) - 신규
- **대상:** 개별 주식 + ETF (AAPL, NVDA, QQQ, 005930.KS 모두 가능)
- **지표:** PER, Forward PER, PBR, ROE, 영업이익률, 배당수익률, 배당성향, 부채비율
- **비교:** 현재 값 vs 동종 섹터 평균 vs S&P500 평균
- **분석 요약:** 🟢 저평가/우수, 🟡 적정/보통, 🔴 고평가/주의 자동 판정
- **차트:** PER/ROE/배당수익률 비교 Bar Chart

### [Tab 3] 뉴스 & 애널리스트 브리핑 (예정)
- 뉴스 Sentiment + 애널리스트 목표가 Upside

## 🛠️ 데이터 소스
- 주가/재무: `yfinance` (무료, 키 불필요)
- 섹터 평균: 1차 하드코딩, 2차 FMP/Finnhub API로 교체 예정

## 🔧 배포 방법
1. `pages/` 폴더에 `2_Investment_Deep_Dive.py` 넣기
2. 최상단에 `requirements.txt`, `README.md` 넣기
3. GitHub Push → Streamlit Cloud 자동 재배포

---
Title Finalized: 투자 종목 정밀진단 (Investment Deep Dive) - 1안
