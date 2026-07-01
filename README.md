# 📊 마케팅 성과 인사이트 리포트 자동 생성기

> raw 마케팅 성과 CSV 하나를 넣으면 **정제 → 계산 → 해석 → 리포트(.md·HTML)** 까지 자동으로 생성하는 파이프라인.
> 핵심 설계는 **"계산은 Python(정확), 해석은 Claude(인사이트)"** 의 역할 분리입니다.

`AX 해커톤 · DA 공통 과제` | Python(pandas) + Claude Code

---

## 개요

데이터 분석가(DA)는 매주·매월 마케팅 성과 리포트를 만듭니다. 그런데 그 과정이 매번 **데이터 추출 → 계산 → 요약**의 수작업 반복이라, 반나절이 들고 ROI·변화율 계산에서 오류가 나며, 결과물은 "수치 나열"에 그치기 쉽습니다.

이 프로젝트는 그 반복을 자동화합니다:

- **합계·ROI·변화율 계산은 Python으로** → 수식 오류 없이 재현 가능
- **수치 해석·리포트 서술은 Claude로** → "그래서 무엇을 해야 하는가"까지 담은 인사이트
- **새 CSV를 넣어도 동일 품질로 재생성** → 채널명·날짜를 하드코딩하지 않아 매 주기 재사용 가능

## ✨ 핵심 설계 원칙 — 계산과 해석의 분리

| 역할 | 담당 | 이유 |
|------|------|------|
| 정제·합계·ROI·변화율·예산 계산 | **Python (pandas)** | 280행 집계·예외처리를 손으로 하면 누락·오류 발생. 코드는 누구나 재실행해 검증 가능 |
| 이슈 선정·비즈니스 영향·권장 조치 서술 | **Claude** | 검증된 수치를 입력받아 해석·권고에 집중 |

스크립트는 숫자와 이슈 "후보"까지만 만들고(→ JSON), 최종 이슈 선정과 해석 문장은 그 JSON을 근거로 작성합니다.

## 🔧 주요 기능

- **데이터 정제 (통계 기준 자동 탐지, 하드코딩 없음)**
  - 완전 중복 행 제거
  - 매출 이상치 탐지 — 채널별 객단가(AOV) 분포의 Tukey's fence(Q3 + 1.5×IQR) 초과 행
  - 개별 셀 결측 / 채널×주차 결측일 자동 탐지 (0으로 채우지 않고 합계서 제외 + caveat 표기)
  - 광고비 0원(오가닉) 채널 ROI "측정 불가" 예외 처리
- **핵심 지표 계산** — 총지출·총매출·전체 ROI·총전환 + 채널별 ROI/ROAS/CTR/CVR + 전체 CTR/CVR
- **채널별 ROI 순위** (ROI = 매출 / 광고비 × 100)
- **전주 대비(WoW) 변화율** — 채널별 + 전체 합산(마지막 두 주차 자동 선택, 결측일 caveat 포함)
- **이슈 후보 자동 탐지** — 전주 대비 ±50% 급증·급락 + 무비용 고성과 채널
- **예산 재배분 기획안** — 최저 ROI 유료 채널을 자동 선정해 상위 ROI 채널로 재배분(ROAS 비례), 자체 설계한 우선순위 점수로 P0/P1 분류
- **재현 파이프라인** — 새 CSV 하나로 위 전 과정을 재실행
- **HTML 렌더링** — `.md`(정본)를 스타일 HTML로 자동 변환(드리프트 없음)

## 📂 프로젝트 구조

```
marketing_report_autopilot/
├── data/
│   └── marketing_performance.csv    # raw 성과 데이터 (280행 = 8주 × 5채널 × 7일)
├── context/
│   ├── company-info.md              # 지표 정의(CTR/CVR/ROI/ROAS)·채널 특성
│   └── industry-news.md             # 채널 벤치마크·리포팅 트렌드
├── src/
│   ├── analyze.py                   # 데이터 품질 탐색 (초기 1회용)
│   ├── calculate.py                 # 정제 + 집계 핵심 계산 로직
│   ├── pipeline.py                  # 정제 → 계산 → 이슈 후보 탐지 → JSON
│   ├── budget_proposal.py           # 예산 재배분 기획안 계산 → JSON
│   ├── regenerate.py                # 원클릭 재생성 (pipeline + budget_proposal)
│   └── render_html.py               # insight_report.md → insight_report.html 렌더
├── output/
│   ├── insight_report.md            # ⭐ 최종 리포트 (정본)
│   ├── insight_report.html          # HTML 렌더본 (배포용)
│   ├── template.md                  # 빈 리포트 양식
│   ├── calculated_metrics.json      # 계산 결과 (중간 산출물)
│   └── budget_proposal.json         # 예산 재배분 계산 결과
├── .claude/skills/                  # /analyze /insight /generate /review 스킬
├── decisions.md                     # 의사결정 로그 (정제·이슈 선정·공식 근거)
├── vercel.json                      # 배포 설정 (루트 → 리포트)
└── CLAUDE.md                        # Claude Code용 프로젝트 지침
```

## 🚀 사용법

### 설치
```bash
pip install pandas
```

### 새 CSV로 리포트 재생성
```bash
# 1) 정제·계산·예산 재배분 → output/*.json
python src/regenerate.py data/marketing_performance.csv

# 2) Claude Code가 JSON을 근거로 output/insight_report.md 갱신

# 3) 갱신된 .md → output/insight_report.html 렌더
python src/render_html.py
```

> **Claude Code 채팅에서는** `data/새CSV.csv로 리포트 갱신해줘` 한마디면 Claude가 위 3단계(JSON 계산 → `.md` 작성 → HTML 렌더)를 순서대로 대신 실행합니다.

## 📑 리포트 구성

경영진은 최상단 요약만 읽고, 마케팅팀은 아래로 내려가며 근거를 드릴다운하도록 설계했습니다.

1. **Executive Summary** — 한 줄 결론 + 핵심 수치 4개 + 채널 순위 + 이슈 3가지 + 권장 액션
2. **채널 성과 랭킹 & ROI 비교** — 5개 채널 ROI/ROAS/CTR/CVR 순위표
3. **이슈 3가지 상세** — 현상 / 근거 수치 / 비즈니스 영향 / 권장 조치
4. **채널별 최근 변화 (WoW)** — 전주 대비 지출·매출·전환·ROI 변화
5. **예산 재배분 기획안** — 문제 정의 / 근거 데이터 / 재배분안 / 우선순위
6. **데이터 신뢰도 노트** — 정제 내역 투명 공개
7. **의사결정 로그 · 재생성 가이드**

## 📈 결과 예시 (샘플 데이터 기준)

| 지표 | 값 |
|------|-----|
| 총 지출 | 50,683,819원 |
| 총 매출 | 439,553,059원 |
| 전체 ROI | 867.2% |
| 총 전환수 | 22,694건 |

**채널 ROI 순위**: 이메일(1042.2%) > 네이버광고(658.6%) > 카카오광고(343.3%) > 메타광고(258.7%) · 오가닉(광고비 0, ROI 측정 불가)

> 전체 리포트는 [`output/insight_report.md`](output/insight_report.md) / [`output/insight_report.html`](output/insight_report.html) 참고.

## 🛠 기술 스택

- **Python 3.13** + **pandas** — 정제·집계·계산
- **Claude Code** (Anthropic) — 인사이트 해석·리포트 작성·파이프라인 오케스트레이션
- **Vercel** — 정적 HTML 리포트 배포

## 📌 과제 레벨 (누적형)

- 🟢 **Basic** — 핵심 수치 요약 + 채널별 ROI 비교 + 이슈 3가지 + 전주 대비 변화율
- 🟡 **Standard** — 새 CSV로도 동일 품질 자동 생성하는 재현 파이프라인 + 주간 리포트 설계
- 🔴 **Challenge** — 채널 ROI·이슈 근거 예산 재배분 기획안 + 우선순위 설계

---

*계산은 Python으로 정확하게, 해석은 Claude로 풍부하게 — 마케팅 리포팅 자동화 파이프라인.*
