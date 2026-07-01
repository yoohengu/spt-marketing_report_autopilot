"""
output/insight_report.md 갱신용 원클릭 스크립트.
정제·집계(pipeline.py) -> 예산 재배분 계산(budget_proposal.py)을 순서대로 실행한다.

사용법:
    python src/regenerate.py [csv_path]   # csv_path 생략 시 data/marketing_performance.csv

실행이 끝나면 Claude에게 "이 결과로 output/insight_report.md 갱신해줘"라고 요청하면 된다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import DEFAULT_CSV, JSON_OUT as METRICS_JSON  # noqa: E402
from pipeline import run as run_pipeline  # noqa: E402
from budget_proposal import JSON_OUT as PROPOSAL_JSON  # noqa: E402
from budget_proposal import run as run_budget_proposal  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

    print(f"[1/2] 정제·집계 실행: {csv_path}")
    run_pipeline(csv_path, METRICS_JSON)

    print(f"\n[2/2] 예산 재배분 계산 실행: {METRICS_JSON}")
    run_budget_proposal(METRICS_JSON, PROPOSAL_JSON)

    print("\n[regenerate] 완료. 다음 단계: Claude에게 "
          "'이 결과로 output/insight_report.md 갱신해줘'라고 요청하세요.")


if __name__ == '__main__':
    main()
