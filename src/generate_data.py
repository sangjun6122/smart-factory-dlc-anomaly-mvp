"""합성 DLC batch 데이터 생성기 (테스트용 부가 기능).

실제 사내 데이터는 보안상 사용하지 않는다. 대신 실제 공정 로그의
구조적 특징만 모사한다:
  - 제어(closed-loop) 변수: 전류·전압·가스유량 → CV 0.1% 미만으로 안정
  - 자유응답(free-response) 변수: 챔버 압력·온도 → drift 존재 (CV 수 %)
  - 이상 시나리오: 펌핑 지연(누설 모사), 압력 스파이크, 온도 drift 가속

[설계 단계] 인터페이스만 정의하며, 구현은 2단계(구현·검증)에서 진행한다.
"""
from __future__ import annotations

import pandas as pd

SEED = 42  # 재현성: 시드 고정

# 센서 정의: (sensor_id, 종류, 정상 평균, 정상 표준편차)
SENSORS = [
    ("current_spt1", "closed_loop", 8.0, 0.004),    # A
    ("voltage_bias", "closed_loop", 100.0, 0.012),  # V
    ("mfc_ar", "closed_loop", 50.0, 0.03),          # sccm
    ("pressure_p1", "free_response", 0.4, 0.02),    # Pa
    ("temp_chamber", "free_response", 35.0, 1.5),   # degC
]


def generate_normal_batch(duration_s: int = 3600, hz: int = 1,
                          seed: int = SEED) -> pd.DataFrame:
    """정상 batch 1개를 생성한다 (phase 5단계 포함).

    Returns:
        컬럼 timestamp, phase, sensor_id, value 의 long-format DataFrame.
    """
    raise NotImplementedError  # TODO(2단계)


def inject_anomaly(df: pd.DataFrame, kind: str = "pressure_spike",
                   seed: int = SEED) -> pd.DataFrame:
    """정상 batch에 이상 시나리오를 주입한다.

    Args:
        kind: "pumping_delay" | "pressure_spike" | "temp_drift"
    """
    raise NotImplementedError  # TODO(2단계)


def save_sample_files(out_dir: str = "data") -> list[str]:
    """정상 1개 + 이상 3종 batch CSV를 data/에 저장하고 경로 목록 반환."""
    raise NotImplementedError  # TODO(2단계)
