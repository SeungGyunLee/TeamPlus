# TeamPlus 백엔드

FastAPI 기반 API 서버입니다. 프론트(KW Meet 앱)의 모임·시간표·공강·장소·가상 예약 기능을 서버에서 제공하고,
집현전 예약 현황과 사용자 조건을 합쳐 시간·장소를 추천합니다. 규칙은 프론트 `frontend/src/domain`과 같습니다. AI(Claude)는 **해석과 설명만** 하고, 계산과 판단은 모두 코드가 합니다
(AI 핸드오프 문서의 설계 원칙).

| 작업 | 담당 | 위치 |
|---|---|---|
| 자연어 조건 → 구조화 (프롬프트 1) | AI | 프롬프트: `ai/test_prompts.py`, 호출: `app/ai/service.py` |
| 과제 공지 → 회의 단계 추출 (프롬프트 2) | AI | `app/ai/service.py` |
| 추천 이유 문장 (프롬프트 3) | AI | `app/ai/service.py` |
| 공통 공강 계산 | 코드 | `app/services/availability.py` |
| 가상 예약 검증 | 코드 | `app/services/booking.py` |
| 후보 점수·상태 산정 | 코드 | `app/services/scoring.py` |
| 회의 단계 날짜 배치 | 코드 | `app/services/stage_planner.py` |
| time_preference 해석 | 코드 | `app/services/time_preference.py` |

## 실행

Python 3.12 이상이 필요합니다.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env        # ANTHROPIC_API_KEY 입력 (절대 커밋하지 말 것)
uvicorn app.main:app --reload
```

- API 문서(Swagger): http://localhost:8000/docs
- 키 동작 확인: `python scripts/smoke_llm.py` (프롬프트 3개를 실제로 호출, `1`/`2`/`3`으로 하나만도 가능)
- 테스트: `pytest` / 린트: `ruff check . && ruff format --check .`
- 테스트는 가짜 LLM을 쓰므로 API 키 없이 돌아가고, CI(GitHub Actions)에서도 실제 API를 부르지 않습니다.

## API

모든 경로 앞에 `/api`가 붙습니다. 요청·응답은 프론트와 같은 **camelCase**(`inviteCode`, `groupId`, `updatedAt` 등)이고,
필드 구성은 `frontend/src/domain/model.ts`의 Group·Member·Reservation·Place·Room과 같습니다.

| 메서드 | 경로 | 설명 | 프론트 화면 |
|---|---|---|---|
| POST | `/groups` | 모임 만들기 (팀원 비우면 짱구·철수·훈이) | 홈 · 새 모임 |
| GET | `/groups` | 모임 목록 (최근 수정 순) | 홈 |
| GET / PATCH / DELETE | `/groups/{groupId}` | 조회 / 이름 변경 / 삭제 (예약은 취소 처리) | 모임 관리 |
| POST | `/groups/{groupId}/members` | 팀원 추가 | 모임 관리 |
| PATCH / DELETE | `/groups/{groupId}/members/{memberId}` | 이름·시간표(`busy`) 수정 / 삭제 | 모임 관리 · 시간표 |
| GET | `/groups/by-invite/{code}` | 초대코드로 모임 찾기 (초대 기능 준비용) | - |
| GET | `/groups/{groupId}/availability` | 공통 공강 30칸 (참석 인원 많은 순) | 공통 공강 |
| GET | `/places`, `/places/{placeId}` | 장소 목록·상세 | 장소 |
| GET | `/rooms` | 집현전 호실 (201·202·301·302호) | 예약 |
| GET | `/rooms/availability?date=&groupId=` | 호실별 1시간 슬롯 상태 | 예약 · 시간 선택 |
| POST | `/reservations` | 가상 예약 | 예약 |
| GET | `/reservations?groupId=&status=` | 예약 내역 | 내 예약 |
| POST | `/reservations/{id}/cancel` | 예약 취소 | 내 예약 |
| POST | `/groups/{groupId}/conditions` | 자연어 조건 해석 (프롬프트 1) | (추후) |
| POST | `/groups/{groupId}/recommendations` | 시간·호실 추천 (점수화 + 프롬프트 3) | (추후) |
| POST / GET | `/groups/{groupId}/assignments` | 과제 공지 → 회의 단계 (프롬프트 2) | (추후) |
| PUT | `/groups/{groupId}/assignments/{id}/deadline` | 마감일 확인·수정 → 단계 날짜 재계산 | (추후) |

요청·응답 예시는 `/docs`에서 바로 확인하고 호출해볼 수 있습니다.

### 프론트 연동 시 참고

- **시간표 키**: `busy`는 프론트와 같은 `"요일-교시"` 문자열 목록 (`"0-0"` = 월요일 1교시). 수정할 땐 전체 목록을 보냅니다.
- **예약 슬롯 상태**(`/rooms/availability`의 `state`): `past`(지난 시간) · `mine`(내 예약) · `occupied`(예약됨) ·
  `group_conflict`(모임 예약 있음) · `available`(예약 가능). 우선순위와 문구는 프론트 예약 화면과 같습니다.
  `selectable`이 `true`인 슬롯만 선택 가능하게 하면 됩니다.
- **예약 오류**: 400 응답의 `detail`이 프론트 `book()`과 같은 문구라 그대로 보여주면 됩니다.
  동시에 같은 슬롯을 예약하면 409.
- **추천 결과**의 `room.id`·`date`·`hour`는 `/reservations`에 그대로 넣을 수 있습니다.

## 규칙 (프론트와 동일)

- **시간표**: 월~금 × 6교시, 09:00부터 90분씩 (마지막 16:30~18:00). 매주 반복
- **공통 공강**: 30칸마다 `count/total`과 명단. 정렬은 참석 인원 내림차순 → 요일 → 교시.
  `level`은 전원 `full` / 일부 `partial` / 없음 `none`. `fullCount` = 전원 가능 칸 수
- **예약**: 1시간 슬롯(시작 09~18시), 오늘부터 30일. 오늘이면 현재 시(時)와 같거나 이른 슬롯은 지난 시간.
  팀 인원 > 정원, 이미 찬 슬롯, 같은 모임의 같은 시간 다른 예약은 불가. 모임을 지우면 그 모임 예약은 취소됨
- **시연용 점유**: 프론트 `isSeedOccupied()`와 같은 계산식이라 앱과 서버의 '예약됨'이 일치 (`tests/test_frontend_rules.py`에서 확인)
- **장소·호실 데이터**: `data/places.json` = 프론트 `PLACES`·`ROOMS`. 호실의 콘센트·소음·노트북 공간은 AI 추천용으로 백엔드가 추가한 예시값
- **추천**: 예약과 같은 1시간 슬롯 단위. 전원 가능 + 조건 충족 = 초록, 1명 조정 또는 일부 조건 미충족 = 주황,
  예약됨·인원 부족·모임 예약 있음은 제외. 정원은 '말한 인원'과 '팀 인원' 중 큰 값 기준
- **점수(0~100, 정렬용)**: 시간 일치 60 × (참석 인원/팀 인원) + 조건 충족 40 × (충족/요청 조건 수)
- **회의 단계 배치**: 마감 전날까지. 중간발표 관련 단계는 그 직전 3일, 마지막 단계는 마감 직전 3일, 나머지는 순서대로 나눔
- **timePreference**: "목요일 저녁", "오후 3시 이후", "주말", "11/4" 등을 코드가 해석. 못 알아들으면 시간 조건 없이 추천

## 남은 일

- [ ] 집현전 실제 연동: `app/places/provider.py`의 `JiphyeonjeonProvider` 구현 후 `RESERVATION_PROVIDER=jiphyeonjeon`
- [ ] `data/places.json`의 장소·호실은 프론트와 같은 시연용 값. 실제 정보가 확정되면 프론트와 함께 교체
- [ ] 로그인·모임 소유권: 지금은 모임 ID만 알면 누구나 조회·수정 가능 (프론트도 아직 인증 없음)
- [ ] 프롬프트는 백엔드에 복사본 없이 AI 담당의 `ai/test_prompts.py`에서 `PROMPT_1·2·3`을 바로 읽어 씀
  (파일 위치는 `.env`의 `AI_PROMPTS_FILE`로 바꿀 수 있음. 서버 배포 시 `ai/` 폴더도 같이 있어야 함)
- [ ] PostgreSQL로 바꾸면 Alembic 마이그레이션 도입 (지금은 시작할 때 `create_all`)
- [ ] Docker 실행 환경 (서버 담당과 협의)

## 폴더 구조

```
backend/
├── app/
│   ├── main.py            # FastAPI 앱, 라우터 등록
│   ├── config.py          # 설정 (.env)
│   ├── timetable.py       # 교시·예약 시간 규칙 (프론트 model.ts와 동일)
│   ├── occupancy.py       # 호실 점유 = 시연용 점유 + 예약 DB
│   ├── db.py, models.py   # DB 연결, 테이블
│   ├── schemas.py         # API 요청·응답 형식
│   ├── deps.py            # 의존성 (DB, LLM, 장소, 예약 조회기)
│   ├── routers/           # 엔드포인트
│   ├── services/          # 계산 로직 (순수 함수, 단위 테스트 대상)
│   ├── places/            # 장소·호실 데이터, 예약 현황 어댑터 (시연용 / 집현전)
│   └── ai/                # 응답 스키마, Claude 호출 (프롬프트 원문은 저장소의 ai/)
├── data/places.json       # 장소·호실 (프론트 PLACES·ROOMS와 동일)
├── scripts/smoke_llm.py   # 실제 API 키로 프롬프트 확인
└── tests/
```
