"""평가 프로토콜: 칼리브레이션/시험 세트 분리 (데이터 누수 방지).

방법론
  1) 칼리브레이션 세트: 정상 batch 20개 (시드 42~61)
     → 오탐 0을 만족하는 최소 k를 산정 (파라미터는 여기서만 결정)
  2) 시험 세트 (칼리브레이션과 시드 분리):
     - 정상 batch 20개 (시드 100~119) → 오탐률(FAR) 평가
     - 이상 batch 3종 × 5시드 (시드 200~204) → 구간 검출률 평가
  파라미터 산정에 쓰인 데이터는 성능 보고에 사용하지 않는다.

실행: python -m src.evaluate
"""
from __future__ import annotations

import pandas as pd

from src.detect import DetectConfig, run_all_rules
from src.generate_data import generate_normal_batch, inject_anomaly

CALIB_SEEDS = range(42, 62)        # 칼리브레이션: 정상 20
TEST_NORMAL_SEEDS = range(100, 120)  # 시험: 정상 20 (시드 분리)
TEST_ANOMALY_SEEDS = range(200, 205)  # 시험: 이상 3종 × 5시드
K_GRID = [3.0, 3.5, 4.0, 4.5, 5.0]
ANOMALY_KINDS = ["pumping_delay", "pressure_spike", "temp_drift"]


def calibrate() -> tuple[float, pd.DataFrame]:
    """칼리브레이션 세트에서 오탐 0을 만족하는 최소 k를 산정한다."""
    rows = []
    for k in K_GRID:
        total = sum(len(run_all_rules(generate_normal_batch(seed=s),
                                      DetectConfig(k_sigma=k)))
                    for s in CALIB_SEEDS)
        rows.append({"k": k, "calib_fp_total": total,
                     "calib_batches": len(list(CALIB_SEEDS))})
    table = pd.DataFrame(rows)
    ok = table[table["calib_fp_total"] == 0]
    k_star = float(ok["k"].min()) if not ok.empty else float(K_GRID[-1])
    return k_star, table


def _windows(meta: dict) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    return [(pd.Timestamp(s), pd.Timestamp(e)) for s, e in meta["windows"]]


def evaluate_test(k_star: float) -> pd.DataFrame:
    """시험 세트(칼리브레이션과 분리된 시드)에서 FAR·검출률을 평가한다."""
    cfg = DetectConfig(k_sigma=k_star)
    rows = []
    # 정상 시험 세트 — 오탐률
    fp = [len(run_all_rules(generate_normal_batch(seed=s), cfg))
          for s in TEST_NORMAL_SEEDS]
    rows.append({"세트": "시험-정상", "batch 수": len(fp),
                 "검출 구간": "—", "오탐 합계": sum(fp),
                 "오탐 있는 batch": sum(1 for n in fp if n > 0)})
    # 이상 시험 세트 — 구간 검출률 + 구간 외 오탐
    for kind in ANOMALY_KINDS:
        det, tot, fp_out = 0, 0, 0
        for s in TEST_ANOMALY_SEEDS:
            df, meta = inject_anomaly(generate_normal_batch(seed=s), kind, seed=s)
            a = run_all_rules(df, cfg)
            wins = _windows(meta)
            tot += len(wins)
            det += sum(bool(((a["timestamp"] >= w0) & (a["timestamp"] <= w1)
                             ).any()) for w0, w1 in wins)
            in_any = a["timestamp"].apply(
                lambda t: any(w0 <= t <= w1 for w0, w1 in wins))
            fp_out += int((~in_any).sum())
        rows.append({"세트": f"시험-이상({kind})",
                     "batch 수": len(list(TEST_ANOMALY_SEEDS)),
                     "검출 구간": f"{det}/{tot}", "오탐 합계": fp_out,
                     "오탐 있는 batch": "—"})
    return pd.DataFrame(rows)


def main() -> int:
    k_star, calib = calibrate()
    print("== 칼리브레이션 (정상 20 batch, 시드 42~61) ==")
    print(calib.to_string(index=False))
    print(f"\n산정된 k* = {k_star} (오탐 0을 만족하는 최소 k)\n")
    test = evaluate_test(k_star)
    print("== 시험 세트 (시드 분리: 정상 100~119, 이상 200~204) ==")
    print(test.to_string(index=False))
    calib.to_csv("results/calibration.csv", index=False)
    test.to_csv("results/evaluation_summary.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
