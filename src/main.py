"""CLI 엔트리포인트.

사용 예:
    python -m src.generate_data            # 합성 샘플 생성 (data/)
    python -m src.main data/batch_ng_pressure_spike.csv --out results/spike
"""
from __future__ import annotations

import argparse
import os

from src.detect import DetectConfig, run_all_rules
from src.load import load_batch_csv, validate_schema
from src.visualize import plot_sensor_timeline, print_summary, save_anomaly_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DLC 공정 센서 이상치 탐지 MVP")
    parser.add_argument("csv_path", help="입력 공정 로그 CSV")
    parser.add_argument("--out", default="results", help="출력 폴더")
    parser.add_argument("--window", type=int, default=120, help="롤링 윈도(초)")
    parser.add_argument("--k", type=float, default=4.5, help="k·σ 배수 (칼리브레이션 산정값)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """파이프라인: load → detect → report/plot."""
    args = build_parser().parse_args(argv)
    df = load_batch_csv(args.csv_path)
    for w in validate_schema(df):
        print("경고:", w)
    config = DetectConfig(rolling_window=args.window, k_sigma=args.k)
    anomalies = run_all_rules(df, config)
    os.makedirs(args.out, exist_ok=True)
    save_anomaly_report(anomalies, os.path.join(args.out, "anomalies.csv"))
    for sensor in df["sensor_id"].unique():
        plot_sensor_timeline(df, anomalies, sensor,
                             os.path.join(args.out, f"{sensor}.png"))
    print(f"[{os.path.basename(args.csv_path)}] 이상치 {len(anomalies)}건")
    print_summary(anomalies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
