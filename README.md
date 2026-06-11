# smart-factory-dlc-anomaly-mvp

> https://github.com/sangjun6122/smart-factory-dlc-anomaly-mvp

DLC 코팅 공정 센서 로그의 phase-aware 룰 기반 이상치 탐지 MVP.
**AI Coding Tools 활용 프로그래밍** 최종 프로젝트 (14주차: PRD + 뼈대 코드).

| 문서 | 내용 |
|---|---|
| [PRD.md](PRD.md) | 요구사항 1쪽 (문제·목표·MVP 3기능·제약) |
| [REPORT.md](REPORT.md) | 기술보고서 (매뉴얼·분석 포함, 15주차 완성) |
| [PROMPTS.md](PROMPTS.md) | AI 도구 프롬프트 로그 (구현 전체 과정) |

## 무엇을 만드나

8시간+ 걸리는 DLC 코팅 batch의 불량은 종료 후 검사에서야 발견된다. 이 도구는 공정 센서 로그(CSV)를 phase(펌핑→전처리→중간층→본 증착→벤팅)별로 나눠 임계값·이동평균±kσ 규칙으로 이상치를 찾고, 차트와 알람 목록을 출력한다. 실데이터 대신 공정 구조를 모사한 합성 데이터를 사용한다.

## 실행 (15주차 구현 후)

```bash
pip install -r requirements.txt
python -m src.generate_data                                  # 합성 샘플 생성
python -m src.main data/batch_ng_pressure_spike.csv --out results/
```

상세 매뉴얼은 [REPORT.md 부록 A](REPORT.md) 참조.

## 현재 상태 (14주차 제출분)

- [x] PRD 1쪽 (PDF 포함)
- [x] 뼈대 코드 — 폴더 구조 + 함수 시그니처 (`python -m py_compile` 통과)
- [x] 보고서 초안 (서론·방법 작성, 구현·결과는 15주차)
- [x] 프롬프트 로그 (PROMPTS.md)
- [ ] 기능 구현·결과 분석 (15주차)

## 간단 메모 (과제 요구사항)

**사용한 AI 도구**: Claude (Cowork) — PRD·뼈대 코드·문서 초안 생성, Claude Code — 15주차 기능 구현 예정.

**떠오른 질문 3가지**

1. 룰 기반(±kσ)으로는 여러 변수가 각자 정상 범위 안에 있으면서 조합으로만 나타나는 이상을 잡을 수 없는데, 이런 다변량 패턴을 가장 가볍게 잡는 방법은 무엇인가? (Mahalanobis 거리 정도면 충분한가?)
2. 합성 데이터로 검증한 탐지 규칙·파라미터(k, 윈도)가 실데이터에 그대로 통할까? 합성→실데이터 간극을 줄이는 데이터 생성 요령이 있는가?
3. phase 경계가 명확하지 않은 로그(라벨 없는 경우)에서 phase를 자동 분할하려면 이벤트 기록과 변화점 탐지 중 무엇을 우선해야 하는가?
