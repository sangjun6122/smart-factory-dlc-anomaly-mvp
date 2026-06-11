"""시각화·리포트 모듈 (MVP 기능 3).

[설계 단계] 인터페이스만 정의하며, 구현은 2단계(구현·검증)에서 진행한다.
"""
from __future__ import annotations

import pandas as pd


def plot_sensor_timeline(df: pd.DataFrame, anomalies: pd.DataFrame,
                         sensor_id: str, out_path: str) -> str:
    """센서 1개의 시계열 라인차트를 PNG로 저장한다.

    - phase 경계는 세로 점선 + phase명 라벨
    - 이상점은 빨간 마커
    Returns: 저장된 파일 경로.
    """
    raise NotImplementedError  # TODO(2단계)


def save_anomaly_report(anomalies: pd.DataFrame, out_path: str) -> str:
    """이상치 목록을 CSV로 저장하고 경로를 반환한다."""
    raise NotImplementedError  # TODO(2단계)


def print_summary(anomalies: pd.DataFrame) -> None:
    """phase·센서·규칙별 이상치 건수를 콘솔에 요약 출력한다."""
    raise NotImplementedError  # TODO(2단계)
