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
    ("pumping", "press_highvac"): (None, 0.2, 540),       # 베이스 진공 도달 사양
    ("dlc_coating", "press_highvac"): (1.0, 3.0, 0),      # 공정압 운전 범위
    ("dlc_coating", "temp_substrate"): (None, 170.0, 0),  # 기판 온도 상한
}

# 이동평균 ±k·σ 적용 대상: 자유응답 변수 (정보 비대칭 설계)
# 게이지 유효 측정 범위 — 범위 밖(포화) 샘플은 rolling 판정에서 제외
# (저진공 게이지는 0.5 Pa 플로어, 고진공 게이지는 10 Pa 상한에서 포화)
VALID_RANGE: dict = {
    "press_lowvac": (0.6, None),
    "press_highvac": (None, 9.0),
}

# 감시 대상 = ② 종속 응답 변수 + ③ 자유응답 변수 (제어 변수는 사양 임계값만)
FREE_RESPONSE_SENSORS = [
    "press_lowvac", "press_highvac",            # 자유응답: 진공 게이지
    "temp_substrate", "temp_chamber", "temp_coolant",  # 자유응답: 온도
    "iongun_current", "sputter_voltage", "sputter_power",  # 종속 응답
    "pecvd_voltage", "pecvd_power", "bias_current",
]


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
    for (_ph, sid), g in target.groupby(["phase", "sensor_id"], observed=True):
        g = g.sort_values("timestamp")
        lo, hi = VALID_RANGE.get(sid, (None, None))
        if lo is not None:
            g = g[g["value"] >= lo]
        if hi is not None:
            g = g[g["value"] <= hi]
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


def anomaly_scores(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """감시 채널별 정규화 이상 강도 점수 (히트맵용).

    score = |value - rolling_mean| / (k·σ) — 1.0이 경보 임계.
    바이너리 판정이 아니라 '어느 채널의 어느 시점이 얼마나 이상한가'를
    연속 강도로 제공하여 작업자의 pass/stop 판단을 보조한다.
    임계값 규칙 위반 구간은 score를 최소 1.0 이상으로 끌어올린다.
    """
    out = []
    target = df[df["sensor_id"].isin(config.target_sensors)]
    for (_ph, sid), g in target.groupby(["phase", "sensor_id"], observed=True):
        g = g.sort_values("timestamp").copy()
        lo, hi = VALID_RANGE.get(sid, (None, None))
        if lo is not None:
            g = g[g["value"] >= lo]
        if hi is not None:
            g = g[g["value"] <= hi]
        w = config.rolling_window
        if len(g) < w:
            continue
        roll = g["value"].rolling(w, min_periods=w)
        mean, std = roll.mean(), roll.std().clip(lower=1e-9)
        g["score"] = (g["value"] - mean).abs() / (config.k_sigma * std)
        out.append(g[["timestamp", "phase", "sensor_id", "score"]])
    scores = (pd.concat(out, ignore_index=True) if out
              else pd.DataFrame(columns=["timestamp", "phase", "sensor_id", "score"]))
    # 임계값 규칙 위반은 강도 1.0 이상 보장
    th = detect_threshold(df, config)
    if not th.empty:
        key = scores.set_index(["timestamp", "sensor_id"]).index
        vio = pd.MultiIndex.from_frame(th[["timestamp", "sensor_id"]])
        mask = key.isin(vio)
        scores.loc[mask, "score"] = scores.loc[mask, "score"].clip(lower=1.0)
        # 점수 프레임에 없는 (제어 변수 등) 위반은 1.5로 추가
        missing = th[~pd.MultiIndex.from_frame(th[["timestamp", "sensor_id"]]).isin(key)]
        if not missing.empty:
            add = missing[["timestamp", "phase", "sensor_id"]].copy()
            add["score"] = 1.5
            scores = pd.concat([scores, add], ignore_index=True)
    return scores
