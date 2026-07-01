"""
Standard 파이프라인 — 새 CSV 하나만 넣으면 정제→계산→이슈 후보 탐지를 자동으로 수행한다.

사용법:
    python src/pipeline.py [csv_path]        # csv_path 생략 시 data/marketing_performance.csv

이 스크립트가 자동으로 하는 일 (전부 Python 계산, `src/calculate.py`의 함수를 그대로 재사용):
  1. 정제  : 완전 중복 제거 + 채널별 AOV 기준 매출 이상치 제거 + 결측일 탐지 (하드코딩 없음)
  2. 계산  : 채널×주차 합계/ROI, 채널 전체 합계·ROI 순위, 최근 2주 WoW 변화율
  3. 이슈 후보 탐지: context/company-info.md가 정의한 "전주 대비 ±50% 이상 변화" 기준으로
             모든 채널×주차를 자동 스캔해 급증/급락 후보를 임팩트 크기순으로 랭킹.
             + 광고비 0원인데 매출·전환이 있는 "무비용 고성과" 채널도 별도로 랭킹.
  4. 산출  : output/calculated_metrics.json 하나에 위 결과를 전부 저장

"계산은 Python, 해석은 Claude" 원칙(CLAUDE.md)을 지키기 위해 이 스크립트는 숫자와 이슈 후보
"랭킹"까지만 만든다. 이슈 3가지 최종 선정, 비즈니스 영향·권장 조치 해석 문장은 이 JSON을 근거로
사람(Claude)이 직접 `output/insight_report.md`에 작성한다. 중간 초안 파일은 두지 않는다 —
JSON 자체에 표·문장을 만들 재료가 다 있고, 별도 산출물이 늘어나면 "제출해야 할 파일이 뭔지"가
헷갈리기 때문.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from calculate import (  # noqa: E402
    channel_totals_ranked,
    detect_missing_dates,
    detect_missing_values,
    load_and_clean,
    overall_totals,
    week_over_week_changes,
    weekly_channel_metrics,
)

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_CSV = 'data/marketing_performance.csv'
JSON_OUT = 'output/calculated_metrics.json'
SPIKE_THRESHOLD_PCT = 50  # context/company-info.md: "전주 대비 ±50% 이상 변화 → 이슈로 분류"


def detect_wow_issue_candidates(wow, threshold=SPIKE_THRESHOLD_PCT):
    """전주 대비 ±threshold% 이상 변한 채널×주차를 급증/급락 후보로 자동 탐지. 채널·주차 하드코딩 없음."""
    metric_labels = {'spend_change_pct': '광고비', 'revenue_change_pct': '매출', 'conversions_change_pct': '전환수'}
    candidates = []
    for row in wow:
        for metric, label in metric_labels.items():
            val = row.get(metric)
            if val is not None and abs(val) >= threshold:
                candidates.append({
                    'candidate_type': '급증' if val > 0 else '급락',
                    'channel': row['channel'],
                    'week': row['week'],
                    'prev_week': row['prev_week'],
                    'metric': label,
                    'change_pct': val,
                    'roi_change_pct': row.get('roi_pct_change_pct'),
                    'caveat': row['caveat'],
                    'impact_score': abs(val),
                })
    candidates.sort(key=lambda c: c['impact_score'], reverse=True)
    return candidates


def detect_zero_spend_opportunities(channel_totals):
    """광고비 0원인데 매출·전환이 발생한 채널을 자동 탐지 (오가닉 하드코딩 없음)."""
    revenue_rank = sorted(channel_totals, key=lambda r: r['revenue'], reverse=True)
    conv_rank = sorted(channel_totals, key=lambda r: r['conversions'], reverse=True)
    revenue_pos = {r['channel']: i + 1 for i, r in enumerate(revenue_rank)}
    conv_pos = {r['channel']: i + 1 for i, r in enumerate(conv_rank)}

    opportunities = []
    for r in channel_totals:
        if r['spend'] == 0 and r['revenue'] > 0:
            opportunities.append({
                'candidate_type': '무비용고성과',
                'channel': r['channel'],
                'revenue': r['revenue'],
                'conversions': r['conversions'],
                'revenue_rank_overall': revenue_pos[r['channel']],
                'conversions_rank_overall': conv_pos[r['channel']],
            })
    return opportunities


def run(csv_path, json_out=JSON_OUT):
    df, dup_info, outlier_info = load_and_clean(csv_path)
    missing_values = detect_missing_values(df)
    flags, calendar_gaps = detect_missing_dates(df)

    weekly = weekly_channel_metrics(df)
    week_order = sorted(df['week'].unique(), key=lambda w: int(w[1:]))
    wow = week_over_week_changes(weekly, week_order)

    ranked_totals = channel_totals_ranked(df).to_dict('records')
    overall = overall_totals(df)

    wow_candidates = detect_wow_issue_candidates(wow)
    zero_spend_ops = detect_zero_spend_opportunities(ranked_totals)

    result = {
        'source_csv': csv_path,
        'duplicates_removed': dup_info,
        'revenue_outliers_removed': outlier_info,
        'missing_value_flags': missing_values,
        'missing_date_flags': flags,
        'calendar_wide_gaps': calendar_gaps,
        'weekly_channel_metrics': weekly.to_dict('records'),
        'week_over_week_changes': wow,
        'channel_totals_ranked': ranked_totals,
        'overall_totals': overall,
        'issue_candidates_wow': wow_candidates,
        'issue_candidates_zero_spend': zero_spend_ops,
    }
    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"[pipeline] 계산 결과 저장: {json_out}")
    print(f"[pipeline] 급증/급락 이슈 후보 {len(wow_candidates)}건, 무비용 고성과 후보 {len(zero_spend_ops)}건 탐지")
    print("[pipeline] 다음 단계: 이 JSON을 근거로 Claude에게 'output/insight_report.md 작성/갱신해줘' 요청")


if __name__ == '__main__':
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    json_out_arg = sys.argv[2] if len(sys.argv) > 2 else JSON_OUT
    run(csv_arg, json_out_arg)
