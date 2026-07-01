"""
/generate 1단계 — data/marketing_performance.csv 정제 + 핵심 지표 계산
합계·ROI·전주대비 변화율은 전부 이 스크립트(Python)에서 계산한다. Claude는 이 스크립트의
출력(JSON)을 근거로 해석만 담당한다.

이 스크립트는 "네이버광고 W7"처럼 특정 채널·주차를 하드코딩하지 않는다.
어떤 채널·어떤 주차에 결측일이 생기더라도(중복 입력으로 인한 결측 포함) 아래 로직이
같은 방식으로 자동 탐지하도록 설계했다 — 새 CSV를 넣어도 동일하게 동작해야 하기 때문.
"""
import json
import sys

import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

pd.set_option('display.width', 140)
pd.set_option('display.max_columns', None)

CSV_PATH = 'data/marketing_performance.csv'
OUT_PATH = 'output/calculated_metrics.json'
NUM_COLS = ['impressions', 'clicks', 'spend', 'conversions', 'revenue']


def detect_revenue_outliers(df, iqr_multiplier=1.5):
    """
    채널·날짜를 하드코딩하지 않고 매출 이상치를 통계적으로 탐지한다.
    기준: 채널별 객단가(AOV=revenue/conversions) 분포에서 Tukey's fence(Q3 + 1.5*IQR)를 넘는 행.
    같은 채널 내에서 유독 튀는 매출만 잡아내므로, 채널마다 평균 단가가 달라도 오탐이 적다.
    """
    df = df.copy()
    df['aov'] = df['revenue'] / df['conversions']

    flagged_idx = []
    thresholds = {}
    for channel, g in df.groupby('channel'):
        aov = g['aov'].dropna()
        if len(aov) < 4:
            continue  # 표본이 너무 적으면 IQR이 불안정하므로 스킵
        q1, q3 = aov.quantile(0.25), aov.quantile(0.75)
        upper = q3 + iqr_multiplier * (q3 - q1)
        thresholds[channel] = round(upper, 1)
        flagged_idx += list(g[g['aov'] > upper].index)

    outliers = df.loc[flagged_idx, ['date', 'channel', 'conversions', 'revenue', 'aov']].copy()
    outliers['threshold_aov'] = outliers['channel'].map(thresholds)
    return outliers


def load_and_clean(path):
    """CSV 로드 -> 숫자형 변환 -> 완전 중복 행 제거 -> 매출 이상치 행 제거. 채널·날짜 하드코딩 없음."""
    df = pd.read_csv(path)
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    before = len(df)
    dup_rows = df[df.duplicated(keep='first')]
    df = df.drop_duplicates(keep='first').reset_index(drop=True)
    removed = before - len(df)
    dup_info = dup_rows[['date', 'channel', 'week']].to_dict('records')
    print(f"[정제] 완전 중복 행 {removed}건 제거: {dup_info}")

    outliers = detect_revenue_outliers(df)
    outlier_info = outliers.to_dict('records')
    if len(outliers):
        df = df.drop(index=outliers.index).reset_index(drop=True)
        print(f"[정제] 매출 이상치(채널별 AOV Tukey's fence 초과) {len(outliers)}건 제거: {outlier_info}")
    else:
        print("[정제] 매출 이상치 없음")

    return df, {'count': removed, 'rows': dup_info}, {'count': len(outliers), 'rows': outlier_info}


def detect_missing_values(df):
    """
    개별 셀 결측치(NaN)를 하드코딩 없이 탐지한다.
    completely-duplicate/전체-날짜-결측과는 별개로, 행은 존재하지만 특정 컬럼 값만 비어있는 경우를 잡는다.
    """
    missing = []
    for col in NUM_COLS:
        na_rows = df[df[col].isna()]
        for _, row in na_rows.iterrows():
            missing.append({
                'date': row['date'],
                'channel': row['channel'],
                'week': row['week'],
                'missing_column': col,
            })
    if missing:
        print(f"[결측 탐지] 개별 셀 결측 {len(missing)}건 발견: {missing}")
    else:
        print("[결측 탐지] 개별 셀 결측 없음")
    return missing


def detect_missing_dates(df):
    """
    채널×주차 결측일을 하드코딩 없이 탐지한다.
    기준: 같은 주차(week)에 '다른 채널들'은 존재하는데 특정 채널에만 없는 날짜 = 결측일.
    (모든 채널이 동시에 쉬는 날은 이 방식으로는 못 잡으므로, 전체 캘린더 기준 결측도 별도 확인한다.)
    """
    flags = []
    for week, week_df in df.groupby('week'):
        all_dates_in_week = sorted(week_df['date'].unique())
        for channel, ch_df in week_df.groupby('channel'):
            channel_dates = set(ch_df['date'])
            missing = [d for d in all_dates_in_week if d not in channel_dates]
            if missing:
                flags.append({
                    'channel': channel,
                    'week': week,
                    'expected_days': len(all_dates_in_week),
                    'actual_days': len(channel_dates),
                    'missing_dates': missing,
                })

    # 전체 채널이 동시에 비는 날짜(캘린더 상 완전 공백) 별도 점검
    full_calendar = pd.date_range(df['date'].min(), df['date'].max()).astype(str)
    dates_present_anywhere = set(df['date'].unique())
    calendar_gaps = sorted(set(full_calendar) - dates_present_anywhere)

    if flags:
        print(f"[결측 탐지] 채널별 결측일 {len(flags)}건 발견:")
        for f in flags:
            print(f"  - {f['channel']} {f['week']}: {f['actual_days']}/{f['expected_days']}일 "
                  f"(결측: {f['missing_dates']})")
    else:
        print("[결측 탐지] 채널별 결측일 없음")

    if calendar_gaps:
        print(f"[결측 탐지] 전체 채널 공통 공백일(캘린더 기준): {calendar_gaps}")

    return flags, calendar_gaps


def weekly_channel_metrics(df):
    """채널×주차 합계 + ROI. 결측이 있는 채널·주차는 실제 존재하는 행만으로 합산(임의 보정 없음)."""
    grouped = df.groupby(['channel', 'week']).agg(
        actual_days=('date', 'nunique'),
        spend=('spend', 'sum'),
        revenue=('revenue', 'sum'),
        conversions=('conversions', 'sum'),
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
    ).reset_index()
    grouped['roi_pct'] = grouped.apply(
        lambda r: round(r['revenue'] / r['spend'] * 100, 1) if r['spend'] > 0 else None, axis=1
    )
    return grouped


def attach_missing_flags(weekly_df, flags):
    flag_map = {(f['channel'], f['week']): f for f in flags}
    weekly_df = weekly_df.copy()
    weekly_df['is_incomplete'] = weekly_df.apply(
        lambda r: (r['channel'], r['week']) in flag_map, axis=1
    )
    weekly_df['missing_dates'] = weekly_df.apply(
        lambda r: flag_map.get((r['channel'], r['week']), {}).get('missing_dates', []), axis=1
    )
    return weekly_df


def week_over_week_changes(weekly_df, week_order):
    """채널별로 직전 주차 대비 변화율(%) 계산. 두 주 중 하나라도 결측이 있으면 caveat 표시."""
    metrics = ['spend', 'revenue', 'conversions', 'roi_pct']
    changes = []
    for channel, ch_df in weekly_df.groupby('channel'):
        ch_df = ch_df.set_index('week').reindex(week_order)
        for i in range(1, len(week_order)):
            cur_wk, prev_wk = week_order[i], week_order[i - 1]
            cur, prev = ch_df.loc[cur_wk], ch_df.loc[prev_wk]
            if pd.isna(cur.get('actual_days')) or pd.isna(prev.get('actual_days')):
                continue  # 해당 채널이 그 주차 자체에 데이터가 없는 경우(오가닉 등 구조적 차이 제외)
            row = {'channel': channel, 'week': cur_wk, 'prev_week': prev_wk}
            for m in metrics:
                cur_v, prev_v = cur.get(m), prev.get(m)
                if pd.isna(cur_v) or pd.isna(prev_v) or prev_v == 0:
                    row[f'{m}_change_pct'] = None
                else:
                    row[f'{m}_change_pct'] = round((cur_v - prev_v) / prev_v * 100, 1)
            row['caveat'] = bool(cur.get('is_incomplete') or prev.get('is_incomplete'))
            changes.append(row)
    return changes


def overall_week_over_week(df, week_order, missing_date_flags):
    """마지막 두 주차의 '전체(모든 채널 합산)' 전주 대비 변화율.
    리포트 '전체 합산 전주 대비' 줄(지출·매출·전환·CTR 등)의 출처 — 손계산이 아니라 여기서 계산한다.
    비교 대상 두 주차에 결측일이 있는 채널×주차가 있으면 caveat로 표시(예: 네이버광고 W7 6/7일).
    주차 라벨을 하드코딩하지 않고 week_order의 마지막 두 개를 자동으로 사용한다."""
    if len(week_order) < 2:
        return None
    prev_wk, cur_wk = week_order[-2], week_order[-1]

    def agg(wk):
        w = df[df['week'] == wk]
        spend, revenue, conversions = w['spend'].sum(), w['revenue'].sum(), w['conversions'].sum()
        impressions, clicks = w['impressions'].sum(), w['clicks'].sum()
        return {
            'spend': spend, 'revenue': revenue, 'conversions': conversions,
            'ctr_pct': clicks / impressions * 100 if impressions else None,
            'cvr_pct': conversions / clicks * 100 if clicks else None,
            'roi_pct': revenue / spend * 100 if spend else None,
        }

    cur, prev = agg(cur_wk), agg(prev_wk)

    def pct(c, p):
        if c is None or p is None or pd.isna(c) or pd.isna(p) or p == 0:
            return None
        return round((c - p) / p * 100, 1)

    affected = [f for f in missing_date_flags if f['week'] in (prev_wk, cur_wk)]
    return {
        'prev_week': prev_wk,
        'week': cur_wk,
        'spend_change_pct': pct(cur['spend'], prev['spend']),
        'revenue_change_pct': pct(cur['revenue'], prev['revenue']),
        'conversions_change_pct': pct(cur['conversions'], prev['conversions']),
        'ctr_change_pct': pct(cur['ctr_pct'], prev['ctr_pct']),
        'cvr_change_pct': pct(cur['cvr_pct'], prev['cvr_pct']),
        'roi_change_pct': pct(cur['roi_pct'], prev['roi_pct']),
        'caveat': bool(affected),
        'caveat_detail': [
            {'channel': f['channel'], 'week': f['week'],
             'actual_days': f['actual_days'], 'expected_days': f['expected_days']}
            for f in affected
        ],
    }


def channel_totals_ranked(df):
    """채널 전체 기간 합계 + ROI/ROAS/CTR/CVR (ROI = 매출/광고비 * 100). 오가닉(광고비 0)은 ROI/ROAS 별도 표기."""
    totals = df.groupby('channel').agg(
        spend=('spend', 'sum'), revenue=('revenue', 'sum'), conversions=('conversions', 'sum'),
        impressions=('impressions', 'sum'), clicks=('clicks', 'sum'),
    ).reset_index()
    totals['roi_pct'] = totals.apply(
        lambda r: round(r['revenue'] / r['spend'] * 100, 1) if r['spend'] > 0 else None, axis=1
    )
    totals['roas'] = totals.apply(
        lambda r: round(r['revenue'] / r['spend'], 2) if r['spend'] > 0 else None, axis=1
    )
    totals['ctr_pct'] = round(totals['clicks'] / totals['impressions'] * 100, 2)
    totals['cvr_pct'] = round(totals['conversions'] / totals['clicks'] * 100, 2)
    ranked = totals.sort_values('roi_pct', ascending=False, na_position='last').reset_index(drop=True)
    ranked.index += 1
    return ranked


def overall_totals(df):
    """전체 합계 + 전체 ROI/CTR/CVR. CTR/CVR도 손계산이 아니라 여기서 Python으로 계산한다
    (리포트 채널 랭킹표 '합계' 행의 CTR/CVR 출처). 노출·클릭이 0이면 CTR/CVR은 측정 불가."""
    impressions = df['impressions'].sum()
    clicks = df['clicks'].sum()
    conversions = df['conversions'].sum()
    return {
        'total_spend': int(df['spend'].sum()),
        'total_revenue': int(df['revenue'].sum()),
        'total_conversions': int(conversions),
        'total_impressions': int(impressions),
        'total_clicks': int(clicks),
        'overall_roi_pct': round(df['revenue'].sum() / df['spend'].sum() * 100, 1),
        'overall_ctr_pct': round(clicks / impressions * 100, 2) if impressions else None,
        'overall_cvr_pct': round(conversions / clicks * 100, 2) if clicks else None,
    }


def main():
    df, dup_info, outlier_info = load_and_clean(CSV_PATH)
    missing_values = detect_missing_values(df)
    flags, calendar_gaps = detect_missing_dates(df)

    weekly = weekly_channel_metrics(df)
    weekly = attach_missing_flags(weekly, flags)

    week_order = sorted(df['week'].unique(), key=lambda w: int(w[1:]))
    wow = week_over_week_changes(weekly, week_order)
    overall_wow = overall_week_over_week(df, week_order, flags)

    ranked_totals = channel_totals_ranked(df)
    overall = overall_totals(df)

    print("\n" + "=" * 60)
    print("채널 ROI 순위 (전체 기간)")
    print("=" * 60)
    print(ranked_totals)

    print("\n" + "=" * 60)
    print("전체 합계")
    print("=" * 60)
    print(overall)

    result = {
        'duplicates_removed': dup_info,
        'revenue_outliers_removed': outlier_info,
        'missing_value_flags': missing_values,
        'missing_date_flags': flags,
        'calendar_wide_gaps': calendar_gaps,
        'weekly_channel_metrics': weekly.to_dict('records'),
        'week_over_week_changes': wow,
        'overall_week_over_week': overall_wow,
        'channel_totals_ranked': ranked_totals.to_dict('records'),
        'overall_totals': overall,
    }

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n계산 결과 저장: {OUT_PATH}")
    print("다음 단계(/generate): 이 JSON을 근거로 insight_report.md 해석 작성")


if __name__ == '__main__':
    main()
