"""CSV 파싱·phase 분리 모듈 (MVP 기능 1).

[뼈대 코드] 14주차 과제 — 시그니처만 정의, 구현은 15주차.
"""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "phase", "sensor_id", "value"]

# DLC 공정 단계 (실제 공정 순서 모사)
PHASES = ["pumping", "pretreatment", "interlayer", "main_dlc", "venting"]


def load_batch_csv(path: str) -> pd.DataFrame:
    """공정 로그 CSV를 읽어 검증된 DataFrame을 반환한다.

    Args:
        path: 입력 CSV 경로 (컬럼: timestamp, phase, sensor_id, value)

    Returns:
        timestamp(datetime64) 오름차순 정렬, phase는 PHASES 범주형,
        value는 float로 변환된 DataFrame.

    Raises:
        ValueError: 필수 컬럼 누락, 알 수 없는 phase, 타입 변환 실패 시.
    """
    raise NotImplementedError  # TODO(15주차)


def split_by_phase(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """phase별 DataFrame으로 분리해 {phase: df} 딕셔너리를 반환한다."""
    raise NotImplementedError  # TODO(15주차)


def validate_schema(df: pd.DataFrame) -> list[str]:
    """스키마·결측·중복 타임스탬프를 점검하고 경고 메시지 목록을 반환한다."""
    raise NotImplementedError  # TODO(15주차)
