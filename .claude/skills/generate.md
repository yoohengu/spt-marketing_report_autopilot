# Skill: /generate — 리포트 생성

/insight 완료 후 실행. **Python으로 수치를 계산**하고 `output/insight_report.md`를 생성합니다.

⚠️ **업데이트**: 이 프로젝트에는 이제 정제·계산을 자동화한 재현 파이프라인(`src/pipeline.py`, `src/budget_proposal.py`)이 있습니다. 채널명·날짜를 하드코딩한 1회성 계산 코드를 직접 짜지 말고, 아래처럼 그 스크립트를 실행하세요 — 어떤 CSV를 넣어도 동일한 방식으로 정제·집계·이슈 탐지·예산 재배분까지 재현됩니다.

---

## Step 1: 파이프라인 실행 (필수)

⚠️ 아래 스크립트를 직접 실행하세요. 수치를 손/머리로 계산하거나, 특정 채널·날짜를 하드코딩한 즉석 코드를 짜지 마세요.
Claude는 이 스크립트들의 **출력(JSON)을 받아 해석·서술**만 합니다.

```
python src/regenerate.py [csv_path]   # csv_path 생략 시 data/marketing_performance.csv
```

이 한 줄이 순서대로 실행하는 것:
1. `src/pipeline.py` — 완전 중복 행 제거, 채널별 AOV(Tukey's fence) 기준 매출 이상치 제거, 개별 셀 결측치·채널×주차 결측일 탐지(전부 통계적 기준으로 자동 탐지, 특정 채널·날짜 하드코딩 없음), 채널×주차/전체 합계·ROI/ROAS/CTR/CVR, 최근 2주 WoW 변화율, 이슈 후보(±50% 급증·급락, 무비용 고성과) 자동 탐지 → `output/calculated_metrics.json`
2. `src/budget_proposal.py` — 채널 성과를 다시 스캔해 예산 재배분 대상·목적지 채널을 자동으로 찾고, 재배분 금액·예상 매출·우선순위 점수 계산 → `output/budget_proposal.json`

---

## Step 2: output/insight_report.md 작성

두 JSON(`calculated_metrics.json`, `budget_proposal.json`)을 근거로 `output/template.md` 형식에 맞춰 `output/insight_report.md`를 작성/갱신합니다.

작성 규칙:
- 모든 수치는 JSON에 있는 값을 그대로 사용 ("약 XXX", "대략 YYY" 같은 추정 표현 금지)
- 전체 합계 CTR/CVR는 `overall_totals`의 `overall_ctr_pct`/`overall_cvr_pct`를, "전체 합산 전주 대비"(마지막 두 주차)는 `overall_week_over_week`(지출·매출·전환·CTR·CVR·ROI 변화율 + 결측일 `caveat`/`caveat_detail`)를 **그대로 인용** — 채널별 값을 손으로 합산·재계산하지 말 것
- 중복·이상치·결측·오가닉ROI 처리 방법을 수치 옆에 명시 (JSON의 `duplicates_removed`/`revenue_outliers_removed`/`missing_value_flags`/`missing_date_flags` 참고)
- 이슈 3가지는 JSON의 `issue_candidates_wow`/`issue_candidates_zero_spend`를 1차 후보로 삼되, 단일 지표 ±50% 기준으로는 못 잡는 복합 신호가 있을 수 있으니 원본 CSV도 함께 훑어보고 비즈니스 영향이 큰 3가지를 최종 선정 — 각각 근거 수치 + 비즈니스 영향 + 권장 조치 포함
- 예산 재배분 기획안은 `budget_proposal.json`의 `proposal_1`/`proposal_2`를 그대로 사용 (`_skipped_reason`이 있으면 해당 기획안은 생성하지 않고 사유를 명시)
- **시각화 차트(이미지)는 만들지 않음** — 텍스트 리포트만

---

## Step 2.5: HTML 렌더 (insight_report.md 갱신 직후)

`output/insight_report.md`를 작성/갱신했으면 아래를 실행해 HTML을 동기화합니다. `.html`을 손으로 만들지 마세요 — `.md`가 정본이고 이 스크립트가 `.md`를 읽어 같은 내용의 스타일 HTML을 생성하므로 두 파일이 어긋나지 않습니다.

```
python src/render_html.py    # output/insight_report.md -> output/insight_report.html
```

---

## Step 3: decisions.md 업데이트

아래 항목 기록:
- 완전 중복/결측/이상치 자동 탐지 결과 및 처리 방법 (JSON 기준)
- 오가닉(또는 spend=0 채널) ROI "측정 불가" 처리 방침
- 이슈 3가지 선정 근거 (자동 후보 vs 수동 검토 결과 포함)
- 예산 재배분 대상·목적지 채널 선정 근거, 우선순위 점수 산정 방식

---

## 완료 기준
- [ ] `src/regenerate.py` 실행 완료 (오류 없음)
- [ ] output/insight_report.md 파일 존재
- [ ] `src/render_html.py` 실행해 output/insight_report.html 동기화 완료
- [ ] Executive Summary + 핵심 수치(총지출·총매출·전체ROI·총전환) 포함
- [ ] 채널별 ROI 순위표 포함 (오가닉/spend=0 채널 측정 불가 표기)
- [ ] 이슈 3가지 (근거 수치 포함)
- [ ] 전주 대비 변화율 표 포함
- [ ] 예산 재배분 기획안 포함 (또는 생성 불가 사유 명시)
- [ ] decisions.md 업데이트 완료

→ 완료 후 /review 실행
