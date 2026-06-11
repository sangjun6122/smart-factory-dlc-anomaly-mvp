"""CLI 엔트리포인트.

사용 예 (구현 완료 후):
    python -m src.generate_data            # 합성 샘플 생성
    python -m src.main data/batch_ng_pressure_spike.csv --out results/

[설계 단계] 흐름만 정의하며, 구현은 2단계(구현·검증)에서 진행한다.
"""
from __future__ import annotations

import argparse

from src.detect import DetectConfig, run_all_rules
from src.load import load_batch_csv
from src.visualize import plot_sensor_timeline, print_summary, save_anomaly_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DLC 공정 센서 이상치 탐지 MVP")
    parser.add_argument("csv_path", help="입력 공정 로그 CSV")
    parser.add_argument("--out", default="results", help="출력 폴더")
    parser.add_argument("--window", type=int, default=60, help="롤링 윈도(초)")
    parser.add_argument("--k", type=float, default=3.0, help="k·σ 배수")
    return parser


def main(argv: list[str] | None = None) -> int:
    """파이프라인: load → detect → report/plot.

    TODO(2단계): 아래 흐름 구현
      1. df = load_batch_csv(args.csv_path)
      2. anomalies = run_all_rules(df, config)
      3. save_anomaly_report(...) / plot_sensor_timeline(...) / print_summary(...)
    """
    raise NotImplementedError  # TODO(2단계)


if __name__ == "__main__":
    raise SystemExit(main())
