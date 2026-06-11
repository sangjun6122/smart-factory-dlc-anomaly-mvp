"""룰 기반 이상치 탐지 모듈 (MVP 기능 2).

[설계 단계] 인터페이스만 정의하며, 구현은 2단계(구현·검증)에서 진행한다.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class DetectConfig:
    """탐지 파라미터. phase·센서별로 다르게 줄 수 있다."""
    rolling_window: int = 60          # 이동평균 윈도 (초)
    k_sigma: float = 3.0              # 이동평균 ±k·σ 배수
    abs_limits: dict | None = None    # {sensor_id: (low, high)} 고정 임계값


def detect_threshold(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """고정 임계값 규칙: value가 (low, high) 범위를 벗어난 행을 반환.

    Returns:
        컬럼 timestamp, phase, sensor_id, value, rule="threshold",
        threshold(위반한 경계값) 의 DataFrame.
    """
    raise NotImplementedError  # TODO(2단계)


def detect_rolling_sigma(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """이동평균 ±k·σ 규칙: 롤링 평균에서 k·σ 이상 벗어난 행을 반환.

    phase 경계를 넘어 롤링하지 않도록 phase별로 독립 계산한다.
    """
    raise NotImplementedError  # TODO(2단계)


def run_all_rules(df: pd.DataFrame, config: DetectConfig) -> pd.DataFrame:
    """모든 규칙을 실행하고 중복 제거 후 timestamp순으로 합친 결과 반환."""
    raise NotImplementedError  # TODO(2단계)
