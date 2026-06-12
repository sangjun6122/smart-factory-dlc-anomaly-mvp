# CLAUDE.md — 프로젝트 메모리 (Claude Code 상주 컨텍스트)

이 파일은 모든 세션에 자동 주입되는 프로젝트 메모리다. 매 요청에서 재설명하지 않는다.

## 프로젝트

DLC 코팅 공정 센서 이상 탐지 MVP. **명세의 유일한 진실 원천(SSOT)은 PRD.md** — 충돌 시 PRD가 우선한다. 정량 목표는 PRD §4의 G1~G4.

## 설계 원칙 (모든 코드에 강제)

1. 이동 통계량은 phase 경계를 넘지 않는다 — `groupby(["phase","sensor_id"])`로 구조적으로 차단
2. ±k·σ 규칙은 자유응답 변수(`pressure_p1`, `temp_chamber`)에만 적용 (정보 비대칭 설계)
3. 시드 42 고정 — 동일 입력 → 동일 출력 (재현성 G3)
4. 의존성은 pandas/matplotlib만. 실데이터·고객 정보 절대 포함 금지

## 명령어

```bash
python -m pytest tests/ -q                  # 단위 테스트
python -m src.generate_data                 # 합성 데이터 4종 + labels.json
python -m src.main data/<batch>.csv --out results/<batch>   # 파이프라인
```

## 게이트 — 이 순서를 통과해야 다음 단계로 진행

`py_compile` → pytest 3종(T1 임계값 정확성 / T2 phase 경계 불침범 / T3 재현성) → 4종 batch 무오류 실행 → ground-truth 집계(G1~G4 판정)

## 작업 규칙

- 구현 착수 전 함수 단위 작은 계획을 5줄 이내로 먼저 제시
- 시그니처 변경·명세 밖 기능 추가 금지. 출력은 코드만(설명 최소화)
- 실패 시 해당 함수만 수정(전체 재생성 금지), 수정 후 해당 테스트 재실행 보고
- 동일 실패 2회면 중단하고 증거 패키지(함수명·재현 입력·기대/실제)로 사람에게 보고
