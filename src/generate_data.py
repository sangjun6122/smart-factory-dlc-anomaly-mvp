"""합성 DLC batch 데이터 생성기.

실제 사내 데이터는 보안상 사용하지 않는다. 대신 실제 공정 로그의
구조적 특징만 모사한다:
  - 제어(closed-loop) 변수: 전류·전압·가스유량 → CV 0.1% 미만으로 안정
  - 자유응답(free-response) 변수: 챔버 압력·온도 → drift 존재 (CV 수 %)
  - 이상 시나리오: 펌핑 지연(누설 모사), 압력 스파이크, 온도 drift 가속

시간 축은 실제 8시간+ 공정을 1시간으로 축소(비율 유지)한 모형이다.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

SEED = 42  # 재현성: 시드 고정

# phase 계획: (phase, 길이[초]) — 1Hz 샘플링
PHASE_PLAN = [
    ("pumping", 600),
    ("pretreatment", 600),
    ("interlayer", 600),
    ("main_dlc", 1500),
    ("venting", 300),
]

# 센서 정의: (sensor_id, 종류)
SENSORS = [
    ("current_spt1", "closed_loop"),    # A
    ("voltage_bias", "closed_loop"),    # V
    ("mfc_ar", "closed_loop"),          # sccm
    ("pressure_p1", "free_response"),   # Pa
    ("temp_chamber", "free_response"),  # degC
]


def _profile(sensor: str, phase: str, n: int, rng: np.random.Generator) -> np.ndarray:
    """phase별 정상 거동 프로파일. 제어 변수는 설정값 추종(CV<0.1%),
    자유응답 변수는 곡선·drift·잡음(CV 수 %)을 가진다."""
    t = np.arange(n, dtype=float)
    if sensor == "current_spt1":
        base = {"pumping": 0.0, "pretreatment": 2.0, "interlayer": 4.0,
                "main_dlc": 8.0, "venting": 0.0}[phase]
        return base + rng.normal(0, 0.004, n) * (base > 0)
    if sensor == "voltage_bias":
        base = {"pumping": 0.0, "pretreatment": 100.0, "interlayer": 100.0,
                "main_dlc": 100.0, "venting": 0.0}[phase]
        return base + rng.normal(0, 0.012, n) * (base > 0)
    if sensor == "mfc_ar":
        base = {"pumping": 0.0, "pretreatment": 50.0, "interlayer": 50.0,
                "main_dlc": 50.0, "venting": 0.0}[phase]
        return base + rng.normal(0, 0.03, n) * (base > 0)
    if sensor == "pressure_p1":
        if phase == "pumping":      # 대기압 → 베이스 진공 (지수 감쇠)
            v = 100.0 * np.exp(-t / 70.0) + 0.4
        elif phase == "pretreatment":
            v = np.full(n, 0.8)
        elif phase == "interlayer":
            v = np.full(n, 0.5)
        elif phase == "main_dlc":   # 공정압 + 미세 drift
            v = 0.4 + 2e-5 * t
        else:                       # venting: 대기 복귀
            v = 0.4 + (t / n) ** 2 * 1000.0
        return v * (1 + rng.normal(0, 0.012, n))
    if sensor == "temp_chamber":
        if phase == "pumping":
            v = np.full(n, 25.0)
        elif phase == "pretreatment":
            v = 25.0 + 7.0 * t / n
        elif phase == "interlayer":
            v = 32.0 + 2.0 * t / n
        elif phase == "main_dlc":   # 완만한 열 누적
            v = 34.0 + 1.5 * t / n
        else:
            v = 35.5 - 2.0 * t / n
        return v + rng.normal(0, 0.3, n)
    raise ValueError(f"unknown sensor: {sensor}")


def generate_normal_batch(seed: int = SEED) -> pd.DataFrame:
    """정상 batch 1개를 생성한다 (phase 5단계 포함).

    Returns:
        컬럼 timestamp, phase, sensor_id, value 의 long-format DataFrame.
    """
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp("2026-06-01 08:00:00")
    rows, offset = [], 0
    for phase, dur in PHASE_PLAN:
        ts = t0 + pd.to_timedelta(np.arange(offset, offset + dur), unit="s")
        for sensor, _kind in SENSORS:
            vals = _profile(sensor, phase, dur, rng)
            rows.append(pd.DataFrame({"timestamp": ts, "phase": phase,
                                      "sensor_id": sensor, "value": vals}))
        offset += dur
    return pd.concat(rows, ignore_index=True)


def inject_anomaly(df: pd.DataFrame, kind: str = "pressure_spike",
                   seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    """정상 batch에 이상 시나리오를 주입한다.

    Args:
        kind: "pumping_delay" | "pressure_spike" | "temp_drift"

    Returns:
        (주입된 DataFrame, 주입 구간 메타데이터 — 검증용 ground truth)
    """
    df = df.copy()
    rng = np.random.default_rng(seed + 1)
    meta = {"kind": kind, "sensor_id": None, "phase": None, "windows": []}

    if kind == "pumping_delay":   # 미세 누설 → 베이스 진공 미달(압력 플로어 상승)
        m = (df["phase"] == "pumping") & (df["sensor_id"] == "pressure_p1")
        n = int(m.sum())
        t = np.arange(n, dtype=float)
        leak = 100.0 * np.exp(-t / 70.0) + 4.0   # 정상 플로어 0.4 → 4.0 Pa
        df.loc[m, "value"] = leak * (1 + rng.normal(0, 0.012, n))
        ts = df.loc[m, "timestamp"]
        meta.update(sensor_id="pressure_p1", phase="pumping",
                    windows=[[str(ts.iloc[420]), str(ts.iloc[-1])]])

    elif kind == "pressure_spike":  # 본 증착 중 압력 스파이크 3회 (아킹·가스 이상 모사)
        m = (df["phase"] == "main_dlc") & (df["sensor_id"] == "pressure_p1")
        idx = df.index[m]
        n = len(idx)
        for c in [int(n * 0.25), int(n * 0.55), int(n * 0.8)]:
            width = 15
            lo, hi = max(0, c - width), min(n, c + width)
            bump = 0.18 * np.exp(-0.5 * ((np.arange(lo, hi) - c) / 6.0) ** 2)
            df.loc[idx[lo:hi], "value"] += bump
            ts = df.loc[idx, "timestamp"]
            meta["windows"].append([str(ts.iloc[lo]), str(ts.iloc[hi - 1])])
        meta.update(sensor_id="pressure_p1", phase="main_dlc")

    elif kind == "temp_drift":     # 냉각 이상 모사 → 온도 drift 가속
        m = (df["phase"] == "main_dlc") & (df["sensor_id"] == "temp_chamber")
        n = int(m.sum())
        t = np.arange(n, dtype=float)
        df.loc[m, "value"] += 6.5 * (t / n) ** 1.5   # 종반 +6.5°C
        ts = df.loc[m, "timestamp"]
        # 냉각 이상(결함)은 phase 시작부터 존재 — ground truth는 phase 전 구간
        meta.update(sensor_id="temp_chamber", phase="main_dlc",
                    windows=[[str(ts.iloc[0]), str(ts.iloc[-1])]])
    else:
        raise ValueError(f"unknown anomaly kind: {kind}")
    return df, meta


def save_sample_files(out_dir: str = "data") -> list[str]:
    """정상 1개 + 이상 3종 batch CSV와 ground-truth 라벨을 저장한다."""
    os.makedirs(out_dir, exist_ok=True)
    paths, labels = [], {}
    normal = generate_normal_batch()
    p = os.path.join(out_dir, "batch_normal.csv")
    normal.to_csv(p, index=False)
    paths.append(p)
    labels["batch_normal"] = None
    for kind in ["pumping_delay", "pressure_spike", "temp_drift"]:
        dfa, meta = inject_anomaly(normal, kind)
        p = os.path.join(out_dir, f"batch_ng_{kind}.csv")
        dfa.to_csv(p, index=False)
        paths.append(p)
        labels[f"batch_ng_{kind}"] = meta
    with open(os.path.join(out_dir, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    return paths


if __name__ == "__main__":
    for path in save_sample_files():
        print("saved:", path)
