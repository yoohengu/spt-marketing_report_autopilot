"""
/analyze — data/marketing_performance.csv 데이터 품질 점검
컬럼·기간 확인, 결측/중복/이상치 위치를 실제로 확인한다.
계산 전용 스크립트 — 해석(인사이트)은 이 스크립트의 출력을 근거로 Claude가 작성한다.
"""
import sys
import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

pd.set_option('display.width', 140)
pd.set_option('display.max_columns', None)

CSV_PATH = 'data/marketing_performance.csv'
NUM_COLS = ['impressions', 'clicks', 'spend', 'conversions', 'revenue']

df = pd.read_csv(CSV_PATH)

print("=" * 60)
print("Step 0: 로드 & 형태 확인")
print("=" * 60)
print("행수:", len(df))
print("컬럼:", list(df.columns))
print("기간:", df['date'].min(), "~", df['date'].max())
print("주차:", sorted(df['week'].unique()))
print("채널:", list(df['channel'].unique()))

print("\n" + "=" * 60)
print("Step 1: 숫자형 변환")
print("=" * 60)
for c in NUM_COLS:
    df[c] = pd.to_numeric(df[c], errors='coerce')
print(df[NUM_COLS].dtypes)

print("\n" + "=" * 60)
print("Step 2: 결측치 확인")
print("=" * 60)
print("컬럼별 결측 개수:")
print(df[NUM_COLS].isna().sum())
missing_rows = df[df[NUM_COLS].isna().any(axis=1)]
print(f"\n결측 포함 행 ({len(missing_rows)}건):")
print(missing_rows[['date', 'channel', 'week'] + NUM_COLS])

print("\n" + "=" * 60)
print("Step 3: 완전 중복 행 탐지")
print("=" * 60)
dups = df[df.duplicated(keep=False)]
print(f"완전 중복 행 ({len(dups)}건, {len(dups)//2}쌍):")
print(dups.sort_values(list(df.columns)))
before = len(df)
df = df.drop_duplicates()
after = len(df)
print(f"\n중복 제거: {before}행 -> {after}행 (제거 {before - after}건)")

print("\n" + "=" * 60)
print("Step 4(a): 매출 이상치 — 객단가(AOV) 기준")
print("=" * 60)
df['aov'] = df['revenue'] / df['conversions']
print("객단가 상위 5건 (이상치 후보):")
print(df.sort_values('aov', ascending=False)[['date', 'channel', 'conversions', 'revenue', 'aov']].head())

print("\n" + "=" * 60)
print("Step 4(b): 채널 x 주차 광고비 — 급증/급락 스캔")
print("=" * 60)
wk_spend = df.groupby(['channel', 'week'])['spend'].sum().unstack()
print(wk_spend.round(0))

print("\n채널별 주차 spend 평균 대비 편차가 큰 지점 (|편차| > 50%):")
for ch in wk_spend.index:
    row = wk_spend.loc[ch]
    avg = row.mean()
    if avg == 0:
        continue
    for week, val in row.items():
        dev = (val - avg) / avg * 100
        if abs(dev) >= 50:
            print(f"  {ch} {week}: {val:,.0f}원 (평균 대비 {dev:+.1f}%)")

print("\n" + "=" * 60)
print("Step 4(c): 오가닉 spend 확인 (0으로 나누기 방지)")
print("=" * 60)
organic_spend = df[df['channel'] == '오가닉']['spend'].sum()
print("오가닉 광고비 합계:", organic_spend, "-> ROI/ROAS 측정 불가, 별도 표기 필요")

print("\n" + "=" * 60)
print("Step 5: 채널 x 주차 데이터 완전성 점검 (정상=7행/주)")
print("=" * 60)
pivot = df.pivot_table(index='week', columns='channel', values='spend', aggfunc='count')
print(pivot)

print("\n완료: 위 출력을 근거로 결측/중복/이상치 처리 방침을 decisions.md에 기록하세요.")
