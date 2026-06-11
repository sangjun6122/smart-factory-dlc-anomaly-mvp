"""detect 모듈 단위 테스트.

실행: python -m pytest tests/
"""
import numpy as np
import pandas as pd

from src.detect import DetectConfig, detect_rolling_sigma, detect_threshold
from src.generate_data import generate_normal_batch, inject_anomaly


def _frame(phase, sensor, values, t0="2026-06-01 08:00:00"):
    ts = pd.Timestamp(t0) + pd.to_timedelta(np.arange(len(values)), unit="s")
    return pd.DataFrame({"timestamp": ts, "phase": phase,
                         "sensor_id": sensor, "value": values})


def test_threshold_flags_out_of_range():
    """고정 임계값을 벗어난 값이 정확히 탐지되는지 (skip_first_s 포함)."""
    vals = [5.0] * 500 + [3.0] * 100   # 420초 이후에도 2.0 Pa 초과
    df = _frame("pumping", "pressure_p1", vals)
    cfg = DetectConfig(abs_limits={("pumping", "pressure_p1"): (None, 2.0, 420)})
    hits = detect_threshold(df, cfg)
    assert len(hits) == 180            # 420초 이후 전부
    assert (hits["rule"] == "threshold").all()


def test_rolling_sigma_respects_phase_boundary():
    """롤링 계산이 phase 경계를 넘지 않는지 — 단계 전환 점프는 오경보가 아니어야 한다."""
    rng = np.random.default_rng(0)
    a = _frame("pumping", "pressure_p1", 1.0 + rng.normal(0, 0.01, 300))
    b = _frame("main_dlc", "pressure_p1", 100.0 + rng.normal(0, 0.01, 300),
               t0="2026-06-01 08:05:00")
    df = pd.concat([a, b], ignore_index=True)
    cfg = DetectConfig(rolling_window=120, k_sigma=4.0)
    hits = detect_rolling_sigma(df, cfg)
    assert hits.empty                  # 경계를 넘어 계산했다면 점프가 탐지됐을 것


def test_reproducibility_same_seed_same_output():
    """같은 시드 → 같은 합성 데이터 → 같은 탐지 결과."""
    d1, _ = inject_anomaly(generate_normal_batch(seed=42), "pressure_spike", seed=42)
    d2, _ = inject_anomaly(generate_normal_batch(seed=42), "pressure_spike", seed=42)
    pd.testing.assert_frame_equal(d1, d2)
    from src.detect import run_all_rules
    r1, r2 = run_all_rules(d1, DetectConfig()), run_all_rules(d2, DetectConfig())
    pd.testing.assert_frame_equal(r1, r2)
