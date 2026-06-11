"""시각화·리포트 모듈 (MVP 기능 3)."""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

UNITS = {"current_spt1": "A", "voltage_bias": "V", "mfc_ar": "sccm",
         "pressure_p1": "Pa", "temp_chamber": "degC"}


def plot_sensor_timeline(df: pd.DataFrame, anomalies: pd.DataFrame,
                         sensor_id: str, out_path: str) -> str:
    """센서 1개의 시계열 라인차트를 PNG로 저장한다.

    - phase 경계는 세로 점선 + phase명 라벨
    - 이상점은 빨간 마커
    """
    g = df[df["sensor_id"] == sensor_id].sort_values("timestamp")
    a = anomalies[anomalies["sensor_id"] == sensor_id]
    fig, ax = plt.subplots(figsize=(11, 3.2), dpi=130)
    ax.plot(g["timestamp"], g["value"], lw=0.7, color="#1f4e79", label=sensor_id)
    if not a.empty:
        ax.scatter(a["timestamp"], a["value"], s=12, color="red",
                   zorder=5, label=f"anomaly (n={len(a)})")
    # phase 경계 표시
    for ph, gp in g.groupby("phase", observed=True):
        t0 = gp["timestamp"].iloc[0]
        ax.axvline(t0, color="gray", ls="--", lw=0.6)
        ax.text(t0, ax.get_ylim()[1], f" {ph}", fontsize=7, va="top", color="gray")
    if sensor_id == "pressure_p1":
        ax.set_yscale("log")
    ax.set_xlabel("time")
    ax.set_ylabel(f"{sensor_id} [{UNITS.get(sensor_id, '-')}]")
    ax.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def save_anomaly_report(anomalies: pd.DataFrame, out_path: str) -> str:
    """이상치 목록을 CSV로 저장하고 경로를 반환한다."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    anomalies.to_csv(out_path, index=False)
    return out_path


def print_summary(anomalies: pd.DataFrame) -> None:
    """phase·센서·규칙별 이상치 건수를 콘솔에 요약 출력한다."""
    if anomalies.empty:
        print("이상치 없음")
        return
    summary = (anomalies.groupby(["phase", "sensor_id", "rule"], observed=True)
               .size().rename("count").reset_index())
    print(summary.to_string(index=False))
