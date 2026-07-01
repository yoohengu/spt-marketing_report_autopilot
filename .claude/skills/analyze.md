# Skill: /analyze — 데이터 파악

마케팅 성과 raw CSV를 로드하고, 분석 전 데이터 품질 문제를 전부 파악합니다.
데이터: `data/marketing_performance.csv` (280행 = 8주 W1~W8 × 5채널 × 7일, 최초 제공 데이터 기준).
컬럼: date, channel, impressions, clicks, spend, conversions, revenue, week — **모두 raw 지표** (CTR/CVR/ROAS 없음, 직접 계산).

⚠️ **업데이트**: 아래는 새 CSV를 처음 받았을 때 눈으로 훑어보는 탐색 절차입니다. 실제 정제·집계는 이제 `src/pipeline.py`가 통계적 기준(하드코딩 없음)으로 자동 수행하고 `output/calculated_metrics.json`에 결과를 저장합니다. 리포트를 다시 만드는 게 목적이라면 이 단계를 건너뛰고 바로 `python src/regenerate.py [csv_path]`를 실행해도 됩니다. 이 스킬은 새 CSV의 전반적인 형태를 처음 눈으로 확인하고 싶을 때 참고하세요.

---

## Step 0: 로드 & 형태 확인

```python
import pandas as pd
df = pd.read_csv('data/marketing_performance.csv')
print("행수:", len(df))                 # 280이어야 정상
print("주차:", sorted(df['week'].unique()))   # W1~W8
print("채널:", df['channel'].unique())        # 네이버광고/메타광고/카카오광고/오가닉/이메일
print(df.head())
```

---

## Step 1: 숫자형 변환

```python
num_cols = ['impressions','clicks','spend','conversions','revenue']
for c in num_cols:
    df[c] = pd.to_numeric(df[c], errors='coerce')   # 빈 셀/문자는 NaN
print(df[num_cols].dtypes)
```

---

## Step 2: 결측치 확인 (3건 존재)

```python
print("컬럼별 결측 개수:")
print(df[num_cols].isna().sum())
print("\n결측 포함 행:")
print(df[df[num_cols].isna().any(axis=1)][['date','channel','week'] + num_cols])
```
→ 처리: 결측 행은 합산 시 자동 제외(groupby는 NaN을 빼고 더함). 0으로 채우지 말고 리포트에 "데이터 없음" 명시.

---

## Step 3: 완전 중복 행 탐지 (1쌍 존재)

```python
dups = df[df.duplicated(keep=False)]
print("완전 중복 행:")
print(dups.sort_values(list(df.columns)))
print("\n중복 제거 전:", len(df), "→ 제거 후:", len(df.drop_duplicates()))
df = df.drop_duplicates()   # 집계 전 반드시 제거 (안 하면 매출·전환 부풀려짐)
```

---

## Step 4: 이상치 탐지

### (a) 매출 이상치 — 전환수 대비 비현실적 매출
```python
df['aov'] = df['revenue'] / df['conversions']     # 객단가
print("객단가 상위 5건 (이상치 후보):")
print(df.sort_values('aov', ascending=False)[['date','channel','conversions','revenue','aov']].head())
```
→ 이메일 특정 일자(2026-04-26)의 매출이 같은 채널 평소의 ~9배. 입력 오류 의심 → 제외 또는 별도 표기.

### (b) 광고비 이상치 — 주별 급등/급락
```python
wk = df.groupby(['channel','week'])['spend'].sum().unstack()
print("채널 × 주차 광고비:")
print(wk.round(0))
```
→ 메타광고 W5 광고비가 평소의 ~3.5배(예산 과집행), 카카오광고 W4가 평소의 ~0.6배(급락) 등 확인.

### (c) spend=0인 채널 확인 (정상이지만 ROI 계산 시 주의)
```python
print("채널별 광고비 합계:")
print(df.groupby('channel')['spend'].sum())   # 0인 채널이 있는지 확인 (이 데이터에서는 오가닉)
```
→ ROI = revenue/spend 에서 0으로 나누기 발생. spend>0 채널만 ROI 산출하고 spend=0 채널은 "측정 불가" 처리.

---

## Step 5: 채널 × 주차 데이터 완전성 점검

```python
pivot = df.pivot_table(index='week', columns='channel', values='spend', aggfunc='count')
print("채널별 주차 행 수 (정상=7, 결측/중복 영향 행은 다를 수 있음):")
print(pivot)
```

---

## 완료 기준 (최초 제공 데이터 기준 — 새 CSV는 값이 다를 수 있음)
- [ ] 전체 행수 확인 (중복 제거 전, 최초 데이터는 280)
- [ ] 결측치 위치 파악 완료 (최초 데이터는 3건)
- [ ] 완전 중복 행 식별·제거 완료 (최초 데이터는 1쌍)
- [ ] 매출 이상치 식별 완료 (최초 데이터는 이메일 1건)
- [ ] spend=0인 채널 확인 (ROI 측정 불가 처리 방침 결정, 최초 데이터는 오가닉)
- [ ] 주별 급등·급락 패턴 확인 (최초 데이터는 메타 W5 급등·카카오 W4 급락)

→ 완료 후 /insight 실행
