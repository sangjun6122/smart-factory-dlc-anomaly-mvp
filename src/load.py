"""CSV 파싱·phase 분리 모듈 (MVP 기능 1)."""
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
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")
    unknown = set(df["phase"].unique()) - set(PHASES)
    if unknown:
        raise ValueError(f"알 수 없는 phase: {sorted(unknown)}")
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["value"] = df["value"].astype(float)
    except (ValueError, TypeError) as e:
        raise ValueError(f"타입 변환 실패: {e}") from e
    if df["value"].isna().all():
        raise ValueError("value가 전부 결측입니다")
    df["phase"] = pd.Categorical(df["phase"], categories=PHASES, ordered=True)
    return df.sort_values("timestamp", kind="stable").reset_index(drop=True)


def split_by_phase(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """phase별 DataFrame으로 분리해 {phase: df} 딕셔너리를 반환한다."""
    return {str(ph): g.reset_index(drop=True)
            for ph, g in df.groupby("phase", observed=True)}


def validate_schema(df: pd.DataFrame) -> list[str]:
    """스키마·결측·중복 타임스탬프를 점검하고 경고 메시지 목록을 반환한다."""
    warnings = []
    n_na = int(df["value"].isna().sum())
    if n_na:
        warnings.append(f"결측 value {n_na}건")
    dup = int(df.duplicated(subset=["timestamp", "sensor_id"]).sum())
    if dup:
        warnings.append(f"중복 (timestamp, sensor_id) {dup}건")
    for ph in PHASES:
        if ph not in set(df["phase"].astype(str)):
            warnings.append(f"phase 누락: {ph}")
    return warnings
