# [09] DA 공통 — 비즈니스 인사이트 리포트 자동 생성기

당신은 마케팅 성과를 책임지는 회사의 데이터 분석가(DA)입니다.
마케팅팀·경영진이 매주 받아보는 성과 리포트를, 데이터에서 직접 계산하고 해석해 만들어 주세요.

## 기업 컨텍스트
→ context/company-info.md 와 context/industry-news.md 를 먼저 읽으세요.
특히 핵심 지표 정의(CTR·CVR·ROI·ROAS)와 **계산은 Python으로, 해석은 Claude로** 나누는 이유를 숙지하세요.

## 미션 요약
마케팅 성과 raw CSV(일별·채널별 지표)를 분석하여, 핵심 수치 요약 + 채널별 ROI 비교 + 이슈 3가지 + 전주 대비 변화율을 담은 인사이트 리포트(`insight_report.md`)를 생성하세요.
레벨(Basic → Standard → Challenge)은 본인 수준에 맞게 선택합니다. 위 단계는 아래 단계를 포함하는 누적형입니다.

## 권장 접근 순서
1. /analyze  → data/marketing_performance.csv 파악: 컬럼·기간 확인, 결측·중복·이상치 탐지
2. /insight  → 채널별 성과 패턴·이슈 3가지 기준 설계 + 전주 대비 비교 관점 도출
3. /generate → **Python으로 합계·ROI·변화율 계산** → output/template.md 형식으로 `insight_report.md` 생성
4. /review   → 제출 전 자가 점검 (수치 정확성·이슈 근거·변화율 포함)

> **파이프라인 구축 완료 (Standard/Challenge)**: 위 4단계는 최초 1회 수행 방식이며, 이후 `src/pipeline.py`(정제·집계·이슈탐지) + `src/budget_proposal.py`(예산 재배분)가 동일 로직을 스크립트로 자동화했습니다. **새 CSV로 리포트를 다시 만들 때는 이 4단계를 수동으로 반복하지 말고, 아래 순서를 그대로 따르세요** — 채널명·날짜를 하드코딩하지 않아 새 데이터에도 동일 품질로 재현됩니다:
> 1. `python src/regenerate.py [csv_path]` — 정제·집계·예산 재배분 계산 → `output/calculated_metrics.json`, `output/budget_proposal.json`
> 2. 위 두 JSON을 근거로 `output/insight_report.md`를 갱신 (숫자·표는 JSON 값 그대로, 이슈·해석 문장만 작성)
> 3. `python src/render_html.py` — 갱신된 `.md`를 `output/insight_report.html`로 렌더(내용 동기화, `.md`가 정본)
>
> **Skill로 한 번에 실행**: 위 1~3단계는 `.claude/skills/report-refresh.md`로 패키징되어 있습니다. Claude Code 채팅에서 `/report-refresh [csv_path]` 한 줄이면 정제→계산→리포트 갱신→HTML 렌더까지 자동 수행됩니다 (csv_path 생략 시 `data/marketing_performance.csv`).
>
> 사용법 상세는 `output/insight_report.md`의 "리포트 재생성 가이드" 섹션 참고.

## 의사결정 로깅 규칙
날짜·결측 처리 방법, 이상치 처리 기준, 이슈 3가지 선정 근거, ROI/변화율 계산 공식 등 중요 결정은
반드시 decisions.md 에 기록하세요.
→ "이 결정을 decisions.md에 기록해줘" 입력 시 자동 기록됩니다.

## 채점 기준 (누적형)

### 🟢 Basic — 100점 만점 (필수)
- 핵심 수치 요약 정확도 (30점): 총지출·총매출·전체 ROI·총전환수 + 채널별 합계 — **Python 계산값** 사용
- 채널별 ROI 비교 (30점): 5개 채널 ROI 순위표 완성 (ROI = 매출 / 광고비 × 100) + 순위 해석
- 이슈 3가지 (30점): 급증·급락·이상치·결측 중 비즈니스 영향이 큰 3가지 — 단순 수치 나열 아닌 해석 + 근거 수치 + 권장 조치
- 제출 형식 (10점): 노션 또는 구글 독스 공개 링크로 제출 (또는 output/insight_report.md)

### 🟡 Standard 가산 — +30점
- 파이프라인 재현성 (15점): 새 성과 CSV를 넣어도 정제→계산→해석→리포트가 동일 품질로 자동 생성 (/명령 또는 스크립트)
- 주간 리포트 설계 (15점): 리포트 섹션·지표·형식을 본인이 직접 기획 + 마케팅팀·경영진 관점 근거 설명

### 🔴 Challenge 가산 — +30점
- 예산 재배분 기획안 실효성 (20점): 채널 ROI·이슈 근거로 예산 이동 제안 1—2건 (문제 정의·근거 데이터·재배분안·우선순위)
- 양식·우선순위 설계 (10점): 기획안 양식과 우선순위 판단 기준을 본인이 설계 + 근거 설명

> 최소 합격선: Basic 60점 이상 (핵심 수치 + 채널별 ROI 비교 완성)
> 레벨별 만점: Basic 100 / Standard 130 / Challenge 160

## 제약 조건
- Claude Code (터미널) 또는 Cowork (채팅) 만 사용
- 별도 API 키 없음 — Claude Code 대화 안에서 직접 계산·분석 완료
- ⚠️ **합계·ROI·변화율은 반드시 Python 스크립트로 계산** — Claude에게 "3+5는?" 식 수기 계산 위임 시 감점 (Claude는 계산 완료 수치로 인사이트 해석만)
- 실시간 광고플랫폼 API 연동 제외 (제공된 marketing_performance.csv만 사용)
- 시각화 차트(Matplotlib/Plotly 이미지) 제외 — **텍스트 리포트(.md)만** 산출
- 예측 모델링·대시보드·웹 UI 구현 제외
- Cowork 사용 시: 배포 URL 대신 Skill(/명령) 패키징으로 제출 가능
