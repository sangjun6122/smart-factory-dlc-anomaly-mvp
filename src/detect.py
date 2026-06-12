"""룰 기반 이상치 탐지 모듈 (MVP 기능 2).

설계 원칙 (PRD 4절):
  - phase별 독립 계산: 이동 통계량이 phase 경계를 넘지 않음 (단계 전환 오경보 제거)
  - 정보 비대칭 반영: 이동평균 ±k·σ 규칙은 자유응답 변수에만 적용 (신호 희석 방지)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# 고정 임계값 사양: {(phase, sensor_id): (low, high, skip_first_s)}
#   skip_first_s: phase 시작 후 해당 초까지는 판정 제외 (예: 펌핑 초기 고압 구간)
DEFAULT_LIMITS: dict = {
    ("pumping", "pressure_p1"): (None, 2.0, 420),     # 베이스 진공 도달 사양
    ("main_dlc", "pressure_p1"): (0.2, 0.7, 0),       # 공정압 운전 범위
    ("main_dlc", "temp_chamber"): (None, 37.0, 0),    # 챔버 온도 상한
}

# 이동평균 ±k·σ 적용 대상: 자유응답 변수 (정보 비대칭 설계)
FREE_RESPONSE_SENSORS = ["pressure_p1", "temp_chamber"]


@dataclass
class DetectConfig:
    """탐지 파라미터. phase·센서별로 다르게 줄 수 있다."""
    rolling_window: int = 120         # 이동평균 윈도 (초)
    k_sigma: float = 4.5              # 이동평균 ±k·σ 배수 (칼리브레이션 세트에서 산정)
    abs_limits: dict = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    target_sensors: list = field(default_factory=lambda: list(FREE_RESPONSE_SENSORS))


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["timestamp", "phase", "sensor_id",
                                 "value", "rule", "threshold"])


def detect_threshold(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """고정 임계값 규칙: value가 (low, high) 범위를 벗어난 행을 반환."""
    out = []
    for (phase, sensor), (low, high, skip) in config.abs_limits.items():
        g = df[(df["phase"].astype(str) == phase) & (df["sensor_id"] == sensor)]
        if g.empty:
            continue
        elapsed = (g["timestamp"] - g["timestamp"].iloc[0]).dt.total_seconds()
        g = g[elapsed >= skip]
        if low is not None:
            v = g[g["value"] < low].copy()
            v["rule"], v["threshold"] = "threshold", low
            out.append(v)
        if high is not None:
            v = g[g["value"] > high].copy()
            v["rule"], v["threshold"] = "threshold", high
            out.append(v)
    if not out:
        return _empty()
    return pd.concat(out)[_empty().columns].sort_values("timestamp")


def detect_rolling_sigma(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """이동평균 ±k·σ 규칙: 롤링 평균에서 k·σ 이상 벗어난 행을 반환.

    phase 경계를 넘어 롤링하지 않도록 phase별로 독립 계산한다.
    """
    out = []
    target = df[df["sensor_id"].isin(config.target_sensors)]
    for (_ph, _sid), g in target.groupby(["phase", "sensor_id"], observed=True):
        g = g.sort_values("timestamp")
        w = config.rolling_window
        if len(g) < w:
            continue
        roll = g["value"].rolling(w, min_periods=w)
        mean, std = roll.mean(), roll.std().clip(lower=1e-9)
        dev = (g["value"] - mean).abs()
        hit = g[dev > config.k_sigma * std].copy()
        if hit.empty:
            continue
        hit["rule"] = "rolling_sigma"
        hit["threshold"] = (mean + config.k_sigma * std)[hit.index].round(4)
        out.append(hit)
    if not out:
        return _empty()
    return pd.concat(out)[_empty().columns].sort_values("timestamp")


def run_all_rules(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """모든 규칙을 실행하고 중복 제거 후 timestamp순으로 합친 결과 반환."""
    parts = [r for r in (detect_threshold(df, config),
                         detect_rolling_sigma(df, config)) if not r.empty]
    if not parts:
        return _empty()
    res = pd.concat(parts, ignore_index=True)
    res = res.drop_duplicates(subset=["timestamp", "sensor_id", "rule"])
    return res.sort_values("timestamp").reset_index(drop=True)
