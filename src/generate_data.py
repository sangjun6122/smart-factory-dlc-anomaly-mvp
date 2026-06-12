"""합성 DLC batch 데이터 생성기 — 실제 공정·제어 구조를 모사한 모델.

실데이터는 보안상 사용하지 않는다. 실제 장비·공정의 구조적 특징을 모사한다.

공정 (실제 8시간+ 를 1시간으로 축소, 비율 유지):
  pumping(600s) → heating(600s) → cleaning(500s) → buffer(200s)
  → dlc_coating(1500s) → venting(200s)

시스템 구성 (실장비: 다종 플라즈마 소스, 가스 10계통 내외, 복수 히터,
공자전 턴테이블, 전용 바이어스 전원 — 총 수십 채널):
  - 플라즈마 소스 4기: 이온건(클리닝)/스퍼터(중간층)/PECVD(본 증착)/
    FCVA(장착, 본 레시피 미사용=상시 0), 각 V·I·P 3채널
  - 바이어스 전원(V·I), 히터 2기(P), 공자전 턴테이블(rpm)
  - MFC 8계통(Ar·H2·TMS·C2H2·CH4·N2퍼지·O2/He 미사용)
  - 진공 게이지 2종(저진공 0.5 Pa~대기 / 고진공 ~10 Pa 이하), 온도 3점

변수의 3분류 (제어 구조의 핵심):
  ① 제어 변수 — 레시피 설정값을 폐루프로 추종 (CV<0.1%, 정보 거의 없음)
     예: 전류 제어 소스의 전류, 바이어스 전압, MFC 유량, 히터 전력, 회전수
  ② 종속 응답 변수 — 같은 소스의 비제어 파라미터. 챔버 압력(가스량)·타겟
     소모·장입물(수량·재질) 등에 의해 결정됨 → 장비·공정 상태 정보 보유
     예: 전류 제어 소스의 전압·전력, 전압 제어 소스의 전류, 바이어스 전류
  ③ 자유응답 변수 — 제어되지 않는 시스템 응답 (압력·온도)
  → 이상 감시 대상은 ②+③ (①은 사양 임계값만)

batch 간 자연 편차: 공정 중 압력은 펌프 성능, 챔버 오염, 기밀도, 제품
아웃개싱·표면 오염 등으로 batch마다 조금씩 다르다 — 본 모델은 batch별
무작위 편차(펌핑 시정수·베이스 진공·공정압 레벨·탈가스량·온도 도달치)를
포함한다. 이 편차가 고정 규칙 기반 감시의 민감도 상한을 만든다.

레시피 주: DLC는 응용 분야에 따라 증착 방법·레시피가 다양하다. 본 모델은
범용 레시피 1종을 모사하며, 레시피 다양성 일반화는 후속 연구 과제로 둔다.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

SEED = 42

PHASE_PLAN = [
    ("pumping", 600), ("heating", 600), ("cleaning", 500),
    ("buffer", 200), ("dlc_coating", 1500), ("venting", 200),
]

# ① 제어 변수: {sensor: {phase: 설정값}} — 미기재 phase는 0
CONTROLLED = {
    "iongun_voltage":  {"cleaning": 1500.0},   # 이온건: 전압 제어
    "sputter_current": {"buffer": 4.0},        # 스퍼터: 전류 제어
    "pecvd_current":   {"dlc_coating": 8.0},   # PECVD: 전류 제어
    "fcva_voltage": {}, "fcva_current": {}, "fcva_power": {},  # 미사용
    "bias_voltage":  {"cleaning": 600.0, "buffer": 150.0, "dlc_coating": 120.0},
    "heater1_power": {"heating": 4.0, "cleaning": 2.0, "buffer": 2.0, "dlc_coating": 1.5},
    "heater2_power": {"heating": 3.5, "cleaning": 1.8, "buffer": 1.8, "dlc_coating": 1.3},
    "rotation_speed": {ph: 3.0 for ph, _ in PHASE_PLAN},  # 공자전, 공정 내내
    "mfc_ar":   {"cleaning": 30.0, "buffer": 50.0, "dlc_coating": 20.0},
    "mfc_h2":   {"cleaning": 20.0, "dlc_coating": 5.0},
    "mfc_tms":  {"buffer": 10.0},
    "mfc_c2h2": {"dlc_coating": 40.0},
    "mfc_ch4":  {"dlc_coating": 15.0},
    "mfc_n2":   {"venting": 800.0},
    "mfc_o2": {}, "mfc_he": {},                # 장착, 본 레시피 미사용
}
# ② 종속 응답 변수 (소스 물리로 계산) ③ 자유응답 변수
DEPENDENT = ["iongun_current", "sputter_voltage", "sputter_power",
             "pecvd_voltage", "pecvd_power", "bias_current"]
FREE = ["press_lowvac", "press_highvac",
        "temp_substrate", "temp_chamber", "temp_coolant"]
SENSORS = [(s, "controlled") for s in CONTROLLED] + \
          [(s, "dependent") for s in DEPENDENT] + [(s, "free") for s in FREE]

# 공칭 공정압 (종속 변수 결합 기준)
P_NOM = {"cleaning": 1.0, "buffer": 0.5, "dlc_coating": 2.0}
TEMP_NOISE = {"temp_substrate": 0.8, "temp_chamber": 0.5, "temp_coolant": 0.2}


def _batch_factors(rng: np.random.Generator) -> dict:
    """batch 간 자연 편차 — 펌프 성능·오염·기밀·아웃개싱·온도 도달치."""
    return {
        "tau": 35.0 + rng.normal(0, 1.2),          # 펌핑 시정수 (펌프 성능·기밀)
        "base": 0.005 * rng.lognormal(0, 0.25),    # 베이스 진공 (오염·기밀)
        "outgas": 0.03 * rng.lognormal(0, 0.3),    # 탈가스량 (제품 표면 상태)
        "p_lvl": 1.0 + rng.normal(0, 0.02),        # 공정압 레벨 (가스·배기 균형)
        "t_ramp": rng.normal(0, 1.0),              # 온도 도달치 편차
        "wear": rng.uniform(0, 1),                 # 타겟 소모 진행도 (스퍼터)
    }


def _true_pressure(phase: str, n: int, f: dict, leak: bool = False) -> np.ndarray:
    t = np.arange(n, dtype=float)
    base = 0.5 if leak else f["base"]
    if phase == "pumping":
        return 1e5 * np.exp(-t / f["tau"]) + base
    if phase == "heating":
        return base + f["outgas"] * np.exp(-t / 100.0)
    if phase in P_NOM:
        drift = 2e-5 * t if phase == "dlc_coating" else 0.0
        return np.full(n, P_NOM[phase] * f["p_lvl"]) + drift
    return f["base"] + (t / n) ** 2 * 1e5        # venting


def _temp(sensor: str, phase: str, n: int, f: dict) -> np.ndarray:
    x = np.arange(n, dtype=float) / n
    d = f["t_ramp"]
    prof = {
        "temp_substrate": {"pumping": 25 + 0 * x, "heating": 25 + (125 + d) * x,
                           "cleaning": 150 + d + 5 * x, "buffer": 155 + d + 0 * x,
                           "dlc_coating": 155 + d + 8 * x, "venting": 163 + d - 25 * x},
        "temp_chamber":   {"pumping": 25 + 0 * x, "heating": 25 + 40 * x,
                           "cleaning": 65 + 3 * x, "buffer": 68 + 0 * x,
                           "dlc_coating": 68 + 4 * x, "venting": 72 - 15 * x},
        "temp_coolant":   {"pumping": 22 + 0 * x, "heating": 22 + 0 * x,
                           "cleaning": 22 + 2 * x, "buffer": 24 + 0 * x,
                           "dlc_coating": 24 + 3 * x, "venting": 27 - 3 * x},
    }
    return prof[sensor][phase]


def _dependent(phase: str, n: int, p: np.ndarray, f: dict,
               rng: np.random.Generator) -> dict[str, np.ndarray]:
    """종속 응답 변수 — 제어 모드의 비제어 파라미터는 압력·타겟 소모·장입물에
    의해 결정된다 (예: 전류 제어 소스의 전압은 압력이 오르면 떨어짐)."""
    z = np.zeros(n)
    out = {s: z.copy() for s in DEPENDENT}
    x = np.arange(n, dtype=float) / max(n, 1)
    if phase == "cleaning":   # 이온건(전압 제어) → 전류가 압력에 응답
        i = 0.8 * (p / P_NOM["cleaning"]) ** 0.5 * (1 + rng.normal(0, 0.008, n))
        out["iongun_current"] = i
        out["bias_current"] = 1.5 * (p / P_NOM["cleaning"]) ** 0.4 * (1 + rng.normal(0, 0.008, n))
    elif phase == "buffer":   # 스퍼터(전류 제어) → 전압이 압력·타겟 소모에 응답
        v = 450.0 * (P_NOM["buffer"] / p) ** 0.3 * (1 + 0.04 * f["wear"]) \
            * (1 + rng.normal(0, 0.006, n))
        out["sputter_voltage"] = v
        out["sputter_power"] = v * 4.0 / 1000.0
        out["bias_current"] = 3.0 * (p / P_NOM["buffer"]) ** 0.3 * (1 + rng.normal(0, 0.008, n))
    elif phase == "dlc_coating":  # PECVD(전류 제어) → 전압이 압력·장입물에 응답
        v = 700.0 * (P_NOM["dlc_coating"] / p) ** 0.25 * (1 + rng.normal(0, 0.006, n))
        out["pecvd_voltage"] = v
        out["pecvd_power"] = v * 8.0 / 1000.0
        out["bias_current"] = 5.0 * (p / P_NOM["dlc_coating"]) ** 0.3 * (1 + rng.normal(0, 0.008, n))
    return out


def generate_normal_batch(seed: int = SEED) -> pd.DataFrame:
    """정상 batch 1개 (6 phase × 29채널, 1Hz, long-format)."""
    rng = np.random.default_rng(seed)
    f = _batch_factors(rng)
    t0 = pd.Timestamp("2026-06-01 08:00:00")
    frames, offset = [], 0
    for phase, dur in PHASE_PLAN:
        ts = t0 + pd.to_timedelta(np.arange(offset, offset + dur), unit="s")
        p_true = _true_pressure(phase, dur, f)
        ch: dict[str, np.ndarray] = {}
        ch["press_lowvac"] = np.maximum(0.5, p_true) * (1 + rng.normal(0, 0.015, dur))
        ch["press_highvac"] = np.minimum(10.0, p_true) * (1 + rng.normal(0, 0.015, dur))
        for s in TEMP_NOISE:
            ch[s] = _temp(s, phase, dur, f) + rng.normal(0, TEMP_NOISE[s], dur)
        ch.update(_dependent(phase, dur, p_true, f, rng))
        for s, plan in CONTROLLED.items():
            sp = plan.get(phase, 0.0)
            ch[s] = sp + rng.normal(0, 5e-4 * sp, dur) * (sp > 0)
        n_ch = len(ch)
        frames.append(pd.DataFrame({
            "timestamp": np.tile(ts, n_ch),
            "phase": phase,
            "sensor_id": np.repeat(list(ch.keys()), dur),
            "value": np.concatenate(list(ch.values())),
        }))
        offset += dur
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["timestamp", "sensor_id"], kind="stable").reset_index(drop=True)


def inject_anomaly(df: pd.DataFrame, kind: str = "pressure_spike",
                   seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    """이상 시나리오 주입. Returns (df, ground-truth meta)."""
    df = df.copy()
    rng = np.random.default_rng(seed + 1)
    meta = {"kind": kind, "sensor_id": None, "phase": None, "windows": []}

    if kind == "pumping_delay":   # 미세 누설 → 베이스 진공 미달
        m = (df["phase"] == "pumping") & (df["sensor_id"] == "press_highvac")
        n = int(m.sum())
        t = np.arange(n, dtype=float)
        p_leak = 1e5 * np.exp(-t / 35.0) + 0.5
        df.loc[m, "value"] = np.minimum(10.0, p_leak) * (1 + rng.normal(0, 0.015, n))
        ts = df.loc[m, "timestamp"].sort_values()
        meta.update(sensor_id="press_highvac", phase="pumping",
                    windows=[[str(ts.iloc[540]), str(ts.iloc[-1])]])

    elif kind == "pressure_spike":  # 본 증착 중 압력 스파이크 3회 — 종속 변수도 응답
        mp = (df["phase"] == "dlc_coating") & (df["sensor_id"] == "press_highvac")
        mv = (df["phase"] == "dlc_coating") & (df["sensor_id"] == "pecvd_voltage")
        mw = (df["phase"] == "dlc_coating") & (df["sensor_id"] == "pecvd_power")
        ip = df.index[mp.values][np.argsort(df.loc[mp, "timestamp"].values)]
        iv = df.index[mv.values][np.argsort(df.loc[mv, "timestamp"].values)]
        iw = df.index[mw.values][np.argsort(df.loc[mw, "timestamp"].values)]
        n = len(ip)
        ts = df.loc[ip, "timestamp"].sort_values().reset_index(drop=True)
        for c in [int(n * 0.25), int(n * 0.55), int(n * 0.8)]:
            lo, hi = max(0, c - 15), min(n, c + 15)
            bump = 0.9 * np.exp(-0.5 * ((np.arange(lo, hi) - c) / 6.0) ** 2)
            df.loc[ip[lo:hi], "value"] += bump
            # 전류 제어 모드: 압력 상승 → 전압·전력 하강 (물리적 결합)
            ratio = (2.0 / (2.0 + bump)) ** 0.25
            df.loc[iv[lo:hi], "value"] *= ratio
            df.loc[iw[lo:hi], "value"] *= ratio
            meta["windows"].append([str(ts.iloc[lo]), str(ts.iloc[hi - 1])])
        meta.update(sensor_id="press_highvac", phase="dlc_coating")

    elif kind == "temp_drift":     # 냉각 이상 → 기판 온도 drift 가속
        m = (df["phase"] == "dlc_coating") & (df["sensor_id"] == "temp_substrate")
        n = int(m.sum())
        idx = df.index[m.values][np.argsort(df.loc[m, "timestamp"].values)]
        t = np.arange(n, dtype=float)
        df.loc[idx, "value"] += 12.0 * (t / n) ** 1.5
        ts = df.loc[idx, "timestamp"].sort_values()
        meta.update(sensor_id="temp_substrate", phase="dlc_coating",
                    windows=[[str(ts.iloc[0]), str(ts.iloc[-1])]])
    else:
        raise ValueError(f"unknown anomaly kind: {kind}")
    return df, meta


def save_sample_files(out_dir: str = "data") -> list[str]:
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
    with open(os.path.join(out_dir, "labels.json"), "w", encoding="utf-8") as fjs:
        json.dump(labels, fjs, ensure_ascii=False, indent=2)
    return paths


if __name__ == "__main__":
    for path in save_sample_files():
        print("saved:", path)
