# Skill: /report-refresh — 마케팅 인사이트 리포트 재생성

**트리거 예시**: "새 CSV로 리포트 갱신해줘", "리포트 업데이트해줘", "이 데이터로 인사이트 리포트 다시 만들어줘", `/report-refresh data/new_week.csv`

새 마케팅 성과 CSV가 들어올 때마다, 정제 → 집계 → 예산 재배분 계산 → `output/insight_report.md` 갱신 → `output/insight_report.html` 동기화까지 한 번에 재현합니다. 채널명·날짜를 하드코딩하지 않으므로 어떤 CSV를 넣어도 동일 절차로 동작합니다.

**입력**: CSV 파일 경로 (생략 시 `data/marketing_performance.csv`)
**출력**: `output/calculated_metrics.json`, `output/budget_proposal.json`, `output/insight_report.md`, `output/insight_report.html`

---

## 절차 체크리스트

- [ ] **Step 1 — 계산 파이프라인 실행**
  ```
  python src/regenerate.py [csv_path]
  ```
  내부적으로 `src/pipeline.py`(중복 제거, Tukey's fence 이상치 제거, 결측 탐지, 채널×주차/전체 합계·ROI/ROAS/CTR/CVR, WoW 변화율, 이슈 후보 탐지) → `src/budget_proposal.py`(재배분 대상·목적지·예상 매출·우선순위 계산) 순서로 실행됨.

- [ ] **Step 2 — `output/insight_report.md` 갱신**
  두 JSON(`calculated_metrics.json`, `budget_proposal.json`)의 값만 사용해 `output/template.md` 형식대로 재작성. 숫자·표는 JSON 값 그대로, 이슈 3가지·해석 문장만 새로 씀 (JSON의 `issue_candidates_wow`/`issue_candidates_zero_spend`를 1차 후보로 삼되 원본 CSV도 훑어 비즈니스 영향이 큰 3가지 최종 선정).

- [ ] **Step 3 — HTML 동기화**
  ```
  python src/render_html.py
  ```
  `.md`가 정본이며 이 스크립트가 그 내용을 그대로 HTML로 렌더링함. `.html`을 손으로 편집하지 않음.

- [ ] **Step 4 — decisions.md 기록**
  이번 실행에서 자동 탐지된 중복/결측/이상치 처리 결과, 이슈 3가지 선정 근거, 예산 재배분 산정 근거를 기록.

## 완료 기준
- [ ] `insight_report.md`의 Executive Summary·채널별 ROI 표·이슈 3가지·전주 대비 변화율·예산 재배분안이 최신 JSON 값과 일치
- [ ] `insight_report.html`이 `insight_report.md`와 동기화됨 (같은 날 재생성)
- [ ] decisions.md에 이번 실행 근거 기록 완료

---

## 입출력 예시

**입력**: `/report-refresh data/marketing_performance.csv`

**출력 (요약)**:
```
총 지출 50,683,819원 / 총 매출 439,553,059원 / 전체 ROI 867.2%
채널 순위: 이메일(1042.2%) > 네이버(658.6%) > 카카오(343.3%) > 메타(258.7%) | 오가닉(측정불가)
이슈 3가지: 메타 W5 광고비 급등→ROI급락 / 카카오 W4 급락 / 오가닉 무비용 고전환
→ output/insight_report.md, output/insight_report.html 갱신 완료
```
