"""detect 모듈 단위 테스트 — 뼈대 (구현은 15주차).

실행: python -m pytest tests/
"""


def test_threshold_flags_out_of_range():
    """고정 임계값을 벗어난 값이 정확히 탐지되는지."""
    # TODO(15주차): 작은 합성 DataFrame으로 검증
    ...


def test_rolling_sigma_respects_phase_boundary():
    """롤링 계산이 phase 경계를 넘지 않는지."""
    ...


def test_reproducibility_same_seed_same_output():
    """같은 시드 → 같은 합성 데이터 → 같은 탐지 결과."""
    ...
