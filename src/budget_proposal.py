"""
Challenge — 예산 재배분 기획안 계산.

`output/calculated_metrics.json`(Basic/Standard 단계에서 이미 계산된 채널별 합계·ROI/ROAS)을
입력으로 받아, 두 재배분 시나리오의 예상 매출 증감과 자체 설계한 우선순위 점수를 계산한다.
"계산은 Python, 해석은 Claude" 원칙을 Challenge 단계에도 동일하게 적용 — 재배분 금액·예상
매출·우선순위 점수는 전부 이 스크립트가 계산하고, "그래서 무엇을 해야 하는가"라는 해석 문장만
사람이 insight_report.md에 작성한다.

이 스크립트는 "메타광고"·"카카오광고" 같은 특정 채널명을 하드코딩하지 않는다. 대신:
  - 기획안 1 대상 = spend>0인 채널 중 ROI 최저 채널 (동률이면 spend가 큰 채널 우선 — 절대
    임팩트가 더 크므로)
  - 기획안 1 재배분 목적지 = 대상 채널을 제외한 유료 채널 중 ROI 상위 최대 2개, ROAS 비례로 배분
  - 기획안 2 목적지 = spend=0이면서 revenue>0인 채널 중 매출이 가장 큰 채널
  - 기획안 2 재원 채널 = 기획안 1 대상을 제외한 유료 채널 중 CVR 최저 채널 (동률이면 spend가
    큰 채널 우선)
따라서 새 CSV에서 최악의 채널이 바뀌어도 코드 수정 없이 같은 방식으로 재계산된다. 컷 비율
(20%/15%)과 난이도 점수(1/3)는 데이터로 유도할 수 없는 정책적 재량치라 상수로 유지한다.

사용법:
    python src/budget_proposal.py [metrics_json_path] [json_out_path]
    # metrics_json_path 생략 시 output/calculated_metrics.json
"""
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_METRICS = 'output/calculated_metrics.json'
JSON_OUT = 'output/budget_proposal.json'

CUT_RATE_PRIMARY = 0.20     # 기획안 1: 최악 ROI 유료 채널 예산 축소 비율
CUT_RATE_SECONDARY = 0.15   # 기획안 2: 재원 채널 예산 축소 비율
MAX_REALLOCATION_DESTINATIONS = 2


def find_worst_paid_channel(totals):
    """spend>0인 채널 중 ROI 최저 채널. 동률이면 spend가 큰 채널 우선(절대 임팩트가 큼)."""
    paid = [c for c in totals.values() if c['spend'] > 0]
    if not paid:
        return None
    return min(paid, key=lambda c: (round(c['roi_pct'], 1), -c['spend']))


def find_reallocation_destinations(totals, exclude_channel, max_n=MAX_REALLOCATION_DESTINATIONS):
    """제외 채널 외 유료 채널 중 ROI 상위 max_n개. 배분 비율은 ROAS 비례."""
    candidates = [c for c in totals.values() if c['channel'] != exclude_channel and c['spend'] > 0]
    candidates.sort(key=lambda c: c['roi_pct'], reverse=True)
    destinations = candidates[:max_n]
    if not destinations:
        return []
    total_roas = sum(c['roas'] for c in destinations)
    return [
        {'channel': c['channel'], 'share': c['roas'] / total_roas, 'roi_pct': c['roi_pct'], 'roas': c['roas']}
        for c in destinations
    ]


def find_zero_spend_channel(totals):
    """spend=0이면서 revenue>0인 채널 중 매출이 가장 큰 채널(가장 검증된 무비용 수요)."""
    candidates = [c for c in totals.values() if c['spend'] == 0 and c['revenue'] > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c['revenue'])


def find_secondary_target_channel(totals, exclude_channels):
    """exclude_channels 제외 유료 채널 중 CVR 최저 채널. 동률이면 spend가 큰 채널 우선."""
    candidates = [c for c in totals.values() if c['channel'] not in exclude_channels and c['spend'] > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (round(c['cvr_pct'], 2), -c['spend']))


def build_proposal_1(totals):
    """최악 ROI 유료 채널 예산을 축소해 ROI 상위 채널로 재배분."""
    worst = find_worst_paid_channel(totals)
    if worst is None:
        return None, '유료 채널(spend>0)이 없어 기획안 1을 생성할 수 없음'

    destinations = find_reallocation_destinations(totals, worst['channel'])
    if not destinations:
        return None, f"{worst['channel']} 외에 재배분할 유료 채널이 없어 기획안 1을 생성할 수 없음"

    cut_amount = round(worst['spend'] * CUT_RATE_PRIMARY)
    allocations, revenue_gain_total, weighted_roi_numerator = [], 0, 0
    for d in destinations:
        amount = round(cut_amount * d['share'])
        allocations.append({'channel': d['channel'], 'amount': amount, 'share_pct': round(d['share'] * 100, 1)})
        revenue_gain_total += amount * d['roas']
        weighted_roi_numerator += amount * d['roi_pct']

    revenue_loss = cut_amount * worst['roas']
    net_revenue_change = revenue_gain_total - revenue_loss
    weighted_target_roi = weighted_roi_numerator / cut_amount if cut_amount else 0
    roi_improvement = weighted_target_roi - worst['roi_pct']

    scale = cut_amount / 1_000_000
    difficulty = 1  # 예산 티어 조정만 필요, 즉시 실행 가능(대상 채널과 무관하게 항상 성립)
    priority_score = round(roi_improvement * scale / difficulty, 1)

    dest_names = '·'.join(d['channel'] for d in destinations)
    proposal = {
        'name': f"{worst['channel']} 예산 {int(CUT_RATE_PRIMARY * 100)}% 축소 → {dest_names} 재배분",
        'target_channel': worst['channel'],
        'target_channel_roi_pct': worst['roi_pct'],
        'cut_amount': cut_amount,
        'allocations': allocations,
        'target_revenue_loss_est': round(revenue_loss),
        'destination_revenue_gain_est': round(revenue_gain_total),
        'net_revenue_change_est': round(net_revenue_change),
        'weighted_target_roi_pct': round(weighted_target_roi, 1),
        'roi_improvement_pct_pt': round(roi_improvement, 1),
        'priority_scale': round(scale, 2),
        'difficulty': difficulty,
        'priority_score': priority_score,
    }
    return proposal, None


def build_proposal_2(totals, wow_changes, exclude_channels):
    """유료 채널(exclude_channels 제외) 중 CVR 최저 채널 예산을 축소해, 무비용 고성과 채널의
    콘텐츠/SEO 투자로 전환. 목적지 채널의 CVR이 재원 채널보다 낮으면(투자 논리가 성립하지 않으면)
    기획안을 생성하지 않는다."""
    zero_spend = find_zero_spend_channel(totals)
    if zero_spend is None:
        return None, '광고비 0원인 무비용 고성과 채널이 없어 기획안 2를 생성할 수 없음'

    source = find_secondary_target_channel(totals, exclude_channels)
    if source is None:
        return None, '재원으로 삼을 유료 채널이 없어 기획안 2를 생성할 수 없음'

    efficiency_gap = zero_spend['cvr_pct'] - source['cvr_pct']
    if efficiency_gap <= 0:
        return None, (f"{zero_spend['channel']}의 CVR({zero_spend['cvr_pct']}%)이 "
                       f"{source['channel']}({source['cvr_pct']}%)보다 낮거나 같아 콘텐츠 투자 논리가 성립하지 않음")

    cut_amount = round(source['spend'] * CUT_RATE_SECONDARY)
    revenue_loss_breakeven = round(cut_amount * source['roas'])

    dest_wow = [w for w in wow_changes if w['channel'] == zero_spend['channel']]
    avg_growth = round(sum(w['revenue_change_pct'] for w in dest_wow) / len(dest_wow), 1) if dest_wow else None

    scale = cut_amount / 1_000_000
    difficulty = 3  # 콘텐츠 제작·SEO는 즉시 효과가 나지 않고 성과 측정에 시간이 걸림(재원 채널과 무관하게 항상 성립)
    priority_score = round(efficiency_gap * scale / difficulty, 2)

    proposal = {
        'name': f"{source['channel']} 예산 {int(CUT_RATE_SECONDARY * 100)}% → {zero_spend['channel']} 콘텐츠/SEO 신규 투자",
        'source_channel': source['channel'],
        'destination_channel': zero_spend['channel'],
        'cut_amount': cut_amount,
        'revenue_loss_breakeven': revenue_loss_breakeven,
        'destination_avg_wow_growth_pct_baseline': avg_growth,
        'efficiency_gap_cvr_pct_pt': round(efficiency_gap, 2),
        'priority_scale': round(scale, 2),
        'difficulty': difficulty,
        'priority_score': priority_score,
    }
    return proposal, None


def run(metrics_path, json_out=JSON_OUT):
    with open(metrics_path, encoding='utf-8') as f:
        m = json.load(f)

    totals = {c['channel']: c for c in m['channel_totals_ranked']}

    proposal_1, skip_reason_1 = build_proposal_1(totals)
    exclude = {proposal_1['target_channel']} if proposal_1 else set()
    proposal_2, skip_reason_2 = build_proposal_2(totals, m['week_over_week_changes'], exclude)

    result = {
        'source_metrics': metrics_path,
        'priority_formula': '우선순위 점수 = (ROI 개선폭 또는 대체 효율지표) × (재배분 금액 규모, 백만원) ÷ (실행 난이도 1~3)',
        'proposal_1': proposal_1,
        'proposal_2': proposal_2,
    }
    if skip_reason_1:
        result['proposal_1_skipped_reason'] = skip_reason_1
    if skip_reason_2:
        result['proposal_2_skipped_reason'] = skip_reason_2

    result['ranking'] = sorted(
        [{'name': p['name'], 'priority_score': p['priority_score']} for p in (proposal_1, proposal_2) if p],
        key=lambda r: r['priority_score'], reverse=True,
    )

    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[budget_proposal] 계산 결과 저장: {json_out}")


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_METRICS
    out_path = sys.argv[2] if len(sys.argv) > 2 else JSON_OUT
    run(path, out_path)
