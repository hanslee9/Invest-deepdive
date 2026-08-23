# 개별종목 심층분석

한 종목(미국종목/미국ETF/한국종목)에 대해 PER, Fwd PER, 차트, 뉴스, 애널리스트, 외부 랭킹을 sub 링크 4~5번 진입 없이 한 화면에 모아보는 서비스.

## 기능
- **입력**: NVDA / SCHD / 005930 → 005930.KS 자동 변환
- **차트**: 52주 주간종가 52개, TradingView 스타일 (fill:false, beginAtZero:false)
- **지표 13개**: PER, Fwd PER, PBR, ROE, ROA, 영업이익률, 순이익률, 배당수익률, Beta, 시가총액, 52주고/저, 목표가
- **외부 랭킹**: 8.2/10 (TipRanks) 형식
- **뉴스**: 4개 Executive Summary + 임팩트 한줄
- **애널리스트**: Bull/Bear 분석

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 배포
Streamlit Cloud: Main file `app.py`, Secrets에 FINNHUB_API_KEY (선택)

finnhub.io 무료 가입시 뉴스 실시간
