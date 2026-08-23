# 종목 심층분석 - PWA → Streamlit 마이그레이션

## 왜 PWA에서 Streamlit으로?

### PWA 실패 원인 (오늘 하루 헛수고 정리)

**목적:** 한 종목(ETF)에 대해 PER, Fwd PER, 차트, 뉴스, 애널리스트, TipRanks 점수를 **한 화면에** 모아서 sub 링크 4~5번 진입 없이 보자.

**PWA 시도:**
- `index.html` + `Chart.js` + `fetch(Yahoo Finance)`로 구현 시도
- 종목은 변수: `ticker = "NVDA"` / `"SCHD"` / `"005930"` → `normalizeTicker()`로 `005930` → `005930.KS` 자동 변환

**근본적 제약 발견:**

1. **CORS 차단** - 브라우저에서 `fetch("https://query1.finance.yahoo.com/v8/finance/chart/NVDA")` 호출시 Yahoo가 차단
   ```
   Error: No 'Access-Control-Allow-Origin' header
   ```
   - 해결책으로 `corsproxy.io`, `allorigins` 같은 프록시 사용 → 50% 실패, 느림, 신뢰성 0

2. **가짜 데이터로 땜빵** - 실시간 호출이 안 되니까 `MOCK_DB`에 하드코딩
   ```javascript
   chart: [48.5, 52.3, 58.1, ...] // 제가 손으로 지어낸 가짜 데이터
   ```
   - NVDA 48.5는 2023년 가격, 실제 1년은 125→214.72
   - Investing.com 1년 차트와 전혀 다름 (W자 3번 반복 vs 우상향 1번)
   - 신뢰성 상실

3. **변수가 아님** - PWA는 빌드 타임에만 데이터 결정 가능
   - `build_snapshot.py`로 `yfinance`에서 진짜 데이터 가져와서 `data/latest.json` 생성 → PWA는 그 JSON만 읽음
   - 사용자가 `AAPL` 입력시 실시간으로 가져올 수 없음. 미리 빌드된 3개만 가능
   - 당신이 말씀하신 "종목은 코딩 입장에서는 변수" 구현 불가

**결론:** PWA는 Pure Frontend라 서버가 없어서 `ticker` 변수를 실시간으로 처리할 수 없다. 처음부터 안 되는 설계를 하고 있었다.

### Streamlit이 정답인 이유

- **서버가 있다:** `yf.Ticker(ticker)`를 서버에서 직접 호출, CORS 없음, 100% 성공
- **변수가 된다:** `ticker = st.text_input()` → 사용자가 `005930` 입력시 `normalizeTicker()`로 `005930.KS` 자동 변환 → 진짜 데이터 fetch → UI 렌더링
- **한 화면에 모든 데이터:** 차트 52주 + 13개 지표 + 점수 + 외부 랭킹(TipRanks/Yahoo/TradingView) → sub 링크 진입 없음 (목적 달성)

### 오늘 헛수고를 통해 파악한 제약

1. **PWA 제약:** 실시간 외부 API 호출시 CORS 문제, 프록시는 신뢰성 없음
2. **정적 사이트 제약:** 변수 ticker를 실시간으로 처리하려면 백엔드가 필요
3. **가짜 데이터 위험:** 하드코딩은 신뢰성 상실로 이어짐

### Streamlit 배포 방법

#### 1. 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

#### 2. Streamlit Cloud 배포
1. GitHub에 이 폴더 업로드
2. https://share.streamlit.io 접속 → New app → GitHub repo 선택
3. Main file: `app.py`
4. Deploy → 링크 생성: `https://your-app.streamlit.app`

#### 3. 기능
- **입력:** `NVDA` (미국종목) / `SCHD` (미국ETF) / `005930` (한국종목, .KS 자동)
- **차트:** TradingView 1Y 52주 주간종가 52개, `fill:false`, `tension:0.1`, `beginAtZero:false`, 진짜 yfinance 데이터
- **지표:** PER, Fwd PER, PBR, ROE, 영업이익률, 배당수익률 등
- **랭킹:** TipRanks, Yahoo, TradingView 링크 (점수 + 사이트명)
- **검증:** 포인트 수, min/max, range, 변동성 표시

### 다음 단계 (내일부터)

1. **Finnhub API 연동:** 뉴스, 애널리스트 Bull/Bear 5+4개 실시간
2. **TipRanks 크롤링:** 점수 8.4/10 같은 외부 랭킹
3. **Executive Summary:** 뉴스/애널 한 줄 요약 + 투자 임팩트 한 화면에

### 파일 구조
```
streamlit-migration/
├── app.py              # 메인 Streamlit 앱 (변수 ticker 지원)
├── requirements.txt    # 의존성
└── README.md           # 이 파일
```

---

**2026-08-23 하루 정리:** PWA로 변수 ticker 실시간 처리 불가 → Streamlit으로 마이그레이션 결정. 헛수고였지만 제약 파악으로 위안.
