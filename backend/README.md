# TeamPlus 백엔드

FastAPI 기반 API 서버입니다. 프론트(KW Meet 앱)의 로그인·모임·초대·시간표·공강·장소 기능을 서버에서 제공하고,
집현전 예약 현황과 사용자 조건을 합쳐 시간·장소를 추천합니다. 규칙은 프론트 `frontend/src/domain`과 같습니다. AI(Claude)는 **해석과 설명만** 하고, 계산과 판단은 모두 코드가 합니다
(AI 핸드오프 문서의 설계 원칙).

| 작업 | 담당 | 위치 |
|---|---|---|
| 자연어 조건 → 구조화 (프롬프트 1) | AI | 프롬프트: `ai/test_prompts.py`, 호출: `app/ai/service.py` |
| 과제 공지 → 회의 단계 추출 (프롬프트 2) | AI | `app/ai/service.py` |
| 추천 이유 문장 (프롬프트 3) | AI | `app/ai/service.py` |
| 공통 공강 계산 | 코드 | `app/services/availability.py` |
| 예약 가능 기간(오늘부터 7일) | 코드 | `app/services/booking.py` |
| 후보 점수·상태 산정 | 코드 | `app/services/scoring.py` |
| 회의 단계 날짜 배치 | 코드 | `app/services/stage_planner.py` |
| time_preference 해석 | 코드 | `app/services/time_preference.py` |
| 로그인 (비밀번호 해시·토큰) | 코드 | `app/services/auth.py`, `app/routers/auth.py` |
| 메일 (비밀번호 찾기·초대) | 코드 | `app/services/mail.py` |

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
- PostgreSQL로도 같은 테스트를 돌릴 수 있습니다: `TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/teamplus_test pytest`
- DB 구조가 바뀌면(예: 로그인 추가) 예전 `backend/teamplus.db`를 지우고 다시 실행하세요. 아직 마이그레이션 도구가 없습니다.

## 배포 (Docker)

백엔드는 AI 담당의 `ai/test_prompts.py`를 읽으므로 **저장소 최상위에서 빌드**합니다.
이미지에는 `backend/`와 `ai/`만 들어가고 `.env`·DB 파일·`frontend/`는 빠집니다 (`Dockerfile.dockerignore`).

```bash
# 방법 1: docker compose (서버 한 대 또는 내 PC)
cd backend
cp .env.example .env                 # ANTHROPIC_API_KEY 입력
docker compose up -d --build         # http://서버주소:8000/docs
docker compose logs -f               # 로그
docker compose down                  # 끄기 (DB는 teamplus-data 볼륨에 남음)

# 방법 2: 직접 빌드·실행
cd TeamPlus                          # 저장소 최상위
docker build -f backend/Dockerfile -t teamplus-backend .
docker run -d -p 8000:8000 --env-file backend/.env -v teamplus-data:/data teamplus-backend
```

| 항목 | 값 |
|---|---|
| 포트 | `PORT` 환경변수 (기본 8000). Render·Railway·Cloud Run처럼 PORT를 주는 곳은 자동으로 맞춰짐 |
| DB | `/data/teamplus.db` (SQLite). **`/data`에 영구 디스크(볼륨)를 꼭 연결** — 없으면 재시작 때 회원·모임이 사라짐 |
| 비밀값 | `ANTHROPIC_API_KEY`는 호스팅 서비스의 환경변수(Secret) 설정에 넣기. 이미지·저장소에 넣지 않음 |
| 웹에서 호출 | Expo 웹 미리보기 등 브라우저에서 부르면 `CORS_ORIGINS`에 그 주소 추가. Android 앱은 상관없음 |
| HTTPS | 로그인 토큰이 오가므로 실제 서비스는 HTTPS 주소로. 호스팅 서비스가 앞단에서 처리 (`--proxy-headers` 적용됨) |
| 상태 확인 | `GET /api/health` → `{"status":"ok"}` (Docker HEALTHCHECK도 이 주소 사용) |

SQLite는 서버 한 대 + 영구 디스크용입니다. Cloud Run처럼 컨테이너 파일이 사라지는 곳은 PostgreSQL을 쓰고
`DATABASE_URL`만 바꾸면 됩니다 (드라이버 `psycopg` 포함, 테이블은 처음 뜰 때 자동 생성).

### Google Cloud (Cloud Run + Cloud SQL)

시연 서버는 Cloud Run에 이미지를 올리고 DB는 Cloud SQL PostgreSQL에 둡니다. HTTPS 주소가 자동으로 나오고
재배포·재시작해도 회원·모임이 남습니다. 처음부터 끝까지의 명령은 [`deploy/GCP.md`](deploy/GCP.md)에 있습니다.

| 파일 | 역할 |
|---|---|
| `deploy/GCP.md` | 프로젝트 준비 → Cloud SQL → Secret Manager → 이미지 빌드 → Cloud Run 배포 → 확인·정리 (PowerShell) |
| `deploy/cloudbuild.yaml` | Cloud Build로 이미지 만들어 Artifact Registry에 올리기 |
| `deploy/gcloudignore` | Cloud Build에 `backend/`와 `ai/`만 올리기 (`.env`·DB 파일 제외) |

## API

모든 경로 앞에 `/api`가 붙습니다. 요청·응답은 프론트와 같은 **camelCase**(`groupId`, `updatedAt` 등)이고,
필드 구성은 `frontend/src/domain/model.ts`의 Group·Member·Reservation·Place·Room과 같습니다.
화면 번호는 `docs/app_flow.png`(와이어프레임) 기준입니다.

### 로그인 (와이어프레임 1~3B)

이메일 + 비밀번호 + 닉네임만 받습니다 (학번·실명 없음). 가입·로그인 응답의 `accessToken`을 저장해 두고,
이후 모든 요청에 **`Authorization: Bearer <accessToken>`** 헤더를 붙입니다. 토큰은 30일(`TOKEN_TTL_DAYS`) 유효하고,
만료·로그아웃되면 401 → 로그인 화면으로 보내면 됩니다. Swagger(`/docs`) 오른쪽 위 **Authorize**에 토큰을 넣으면 바로 호출해볼 수 있습니다.

| 메서드 | 경로 | 설명 | 화면 |
|---|---|---|---|
| POST | `/auth/check-email` | 가입된 이메일인지 (`exists` true → 3A 로그인, false → 3B 가입) | 2 |
| POST | `/auth/signup` | 회원가입 (`email`, `password` 8자 이상, `passwordConfirm` 선택, `nickname`) → 201 | 3B |
| POST | `/auth/login` | 로그인. 실패하면 401 "이메일 또는 비밀번호가 맞지 않아요." | 3A |
| POST | `/auth/logout` | 지금 토큰 무효화 → 204 | - |
| GET / PATCH | `/auth/me` | 내 정보 / 닉네임 변경 (모임 안의 내 이름도 함께 바뀜) | - |
| POST | `/auth/password-reset/request` | 비밀번호 찾기 1: `email` → 6자리 인증 코드 메일 (가입 여부와 상관없이 같은 응답, 202) | 3A 링크 |
| POST | `/auth/password-reset/confirm` | 비밀번호 찾기 2: `email`, `code`, `newPassword` → 바뀌면 바로 로그인 응답 | (새 화면) |

비밀번호 찾기: 코드는 10분(`PASSWORD_RESET_MINUTES`) 유효, 5번 틀리면 잠겨서 다시 받아야 하고, 1분 안에는 다시 보내지 않습니다.
재설정하면 다른 기기의 로그인도 모두 끊깁니다. 코드·새 비밀번호를 입력하는 화면은 와이어프레임에 없어서 프론트에 추가가 필요합니다.

### 모임·초대 (로그인 필요)

모임을 만든 사람은 자동으로 첫 번째 팀원(`status: joined`, `userId` = 내 id)이 됩니다. 팀원은 세 종류입니다.

| 팀원 | `userId` | `email` | `status` | 화면 표시 |
|---|---|---|---|---|
| 계정이 연결된 팀원 | 있음 | 있음 | `joined` | 참여완료 (내 `userId`와 같으면 '나') |
| 이메일로 초대만 된 팀원 | `null` | 있음 | `invited` | 대기중 |
| 이름만 있는 팀원 | `null` | `null` | `joined` | 계정 없이 시간표를 대신 입력 |

공강·추천 인원 계산과 팀원 수(`memberCount`)에는 `joined`만 들어가고, 초대 대기중인 사람은 빠집니다.

| 메서드 | 경로 | 설명 | 화면 |
|---|---|---|---|
| POST | `/groups` | 모임 만들기 (`name`, 선택: 이름만 있는 팀원 `memberNames`) | 4 |
| GET | `/groups` | 내가 참여한 모임 목록 (최근 수정 순) | 4 |
| GET / PATCH / DELETE | `/groups/{groupId}` | 조회 / 이름 변경 / 삭제(만든 사람만) | 4 |
| POST | `/groups/{groupId}/invites` | 이메일로 초대 → `invited` 팀원 생성 + 초대 메일 발송 | 5A |
| POST | `/groups/{groupId}/members` | 이름만 있는 팀원 추가 | - |
| PATCH | `/groups/{groupId}/members/{memberId}` | 이름·시간표(`busy`) 수정 (본인 또는 이름만 있는 팀원) | 6 |
| DELETE | `/groups/{groupId}/members/{memberId}` | 초대 취소 · 팀원 내보내기 · 모임 나가기 | - |
| GET | `/invites` | 나에게 온 초대: `groupName`, `inviterName`(초대한 사람), `memberCount`(참여자만) | 4 · 5B |
| POST | `/invites/{memberId}/accept` · `/decline` | 초대 수락(참여완료) / 거절 | - |
| GET | `/groups/{groupId}/availability` | 공통 공강 30칸 (참석 인원 많은 순) | 7 |

권한: 남의 모임은 404(있는지도 알려주지 않음). 모임 삭제와 다른 계정 팀원 내보내기는 만든 사람만(403).
만든 사람은 나갈 수 없고 모임을 삭제해야 합니다. 팀원은 대기중 포함 최대 12명.

### 장소·추천·AI

| 메서드 | 경로 | 설명 | 로그인 |
|---|---|---|---|
| GET | `/places`, `/places/{placeId}` | 장소 목록·상세 | 불필요 |
| GET | `/rooms` | 집현전 그룹학습실 11개 (1~9·12·13실) | 불필요 |
| GET | `/rooms/availability?date=&groupId=` | 호실별 1시간 슬롯 상태 (오늘부터 7일) | `groupId`를 줄 때만 |
| POST | `/groups/{groupId}/conditions` | 자연어 조건 해석 (프롬프트 1) | 필요 |
| POST | `/groups/{groupId}/recommendations` | 시간·호실 추천 (점수화 + 프롬프트 3) | 필요 |
| POST / GET | `/groups/{groupId}/assignments` | 과제 공지 → 회의 단계 (프롬프트 2) | 필요 |
| PUT | `/groups/{groupId}/assignments/{id}/deadline` | 마감일 확인·수정 → 단계 날짜 재계산 | 필요 |

요청·응답 예시는 `/docs`에서 바로 확인하고 호출해볼 수 있습니다.
실제 예약은 중앙도서관 앱에서 하므로 이 서버에는 예약 기능이 없습니다 (가상 예약 API는 팀 결정으로 삭제).

### 프론트 연동 시 참고

- **로그인 헤더**: `Authorization: Bearer <accessToken>`. 401이면 토큰을 지우고 로그인 화면으로.
- **시각**: `updatedAt`·`createdAt`·`expiresAt`은 모두 시간대가 붙은 ISO 문자열(`…+09:00`)이라 `new Date()`로 바로 읽힙니다.
- **시간표 키**: `busy`는 프론트와 같은 `"요일-교시"` 문자열 목록 (`"0-0"` = 월요일 1교시). 수정할 땐 전체 목록을 보냅니다.
- **날짜 범위**: 도서관 예약 기준으로 오늘부터 7일(오늘~6일 뒤)만 다룹니다. 호실 현황은 그 밖의 날짜면 422.
  추천은 범위가 7일을 벗어나면 7일 안으로 잘라서 찾고, 실제로 찾은 기간을 응답의 `dateFrom`·`dateTo`로 돌려줍니다.
  (과제 회의 단계의 권장 기간을 그대로 넘겨도 됨. 기간 전체가 7일 밖이면 422)
- **슬롯 상태**(`/rooms/availability`의 `state`): `past`(지난 시간) · `occupied`(예약됨) · `available`(예약 가능).
  `selectable`이 `true`인 슬롯만 선택 가능하게 하면 됩니다.
- `inviteCode`는 프론트 Group 형식을 맞추려고 남겨둔 필드로 항상 `null`입니다 (초대는 이메일로).

#### 지금 프론트 코드에서 바꿀 곳 (2026-11-24, main + PR #16 기준으로 대조)

프론트의 `api.ts`는 토큰 헤더만 붙이면 이 백엔드에서 그대로 동작합니다(로컬 검증 서버 + `api.integration.ts`로 확인,
기대값 두 줄만 아래 2번에 맞게 바꿈).

| 프론트 위치 | 바꿀 점 |
|---|---|
| `src/data/api.ts`의 `request()` | 로그인 뒤 모든 요청에 `Authorization: Bearer <accessToken>`. `/auth/*`, `/places`, `/rooms`, `/health`는 없어도 됨. 401이면 토큰을 지우고 로그인 화면으로 |
| `createGroup` | 만든 사람이 자동으로 첫 팀원이 됨. `memberNames`는 계정 없는 팀원을 같이 넣을 때만 쓰고 보통 `[]`. 지금처럼 기본 이름 3개를 보내면 이름만 있는 팀원 3명이 더 생김 |
| `Member` 타입 (`domain/model.ts`) | `email`, `status`(`joined` / `invited`) 추가. 대기중 팀원은 공강·추천·인원 수에서 빠짐 |
| 초대 화면 | `POST /groups/{id}/invites {email}`, `GET /invites`, `POST /invites/{memberId}/accept`, `POST /invites/{memberId}/decline` |
| `domain/apiDates.ts`의 `recommendationRangeError` | 30일 → 7일(오늘~6일 뒤). 과제 단계 권장 기간처럼 일부만 겹쳐도 서버가 7일 안으로 잘라서 찾으므로, 오늘~6일 뒤와 하루라도 겹치면 보내도 됨 |
| `RoomAvailability.state` | `mine`·`group_conflict`는 더 이상 오지 않음 (`past`·`occupied`·`available`) |
| 호실 표시 | 호실은 J01~J13(`집현전 1실`~`13실`, 11개). 예전 `집현전 201호` 같은 이름은 사라짐 |
| `tests/api.integration.ts` | 시작할 때 회원가입(또는 로그인)으로 토큰 받기. 만든 사람이 팀원 목록 첫 번째로 들어가는 것 반영 |
| `frontend/.env.local` | `EXPO_PUBLIC_API_URL`에 배포 주소(https, 끝에 `/api` 없이) |

## 집현전 실제 현황 연동

학교 비공개 API, 사용 전 확인 필요. 도서관·정보통신처 사용 허락은 팀장이 확인 중이라 **기본값은 시연용(`mock`)**입니다.
조회만 하고(로그인·학번 없음), 실제 예약은 사용자가 중앙도서관 앱에서 합니다.

**켜는 법** (`backend/.env`):

```
RESERVATION_PROVIDER=jiphyeonjeon
JIPHYEONJEON_STATUS_URL=<연동 안내 문서의 방별 현황 주소>
JIPHYEONJEON_MAP_URL=<연동 안내 문서의 예약 가능 맵 주소>
```

주소는 저장소(코드·README·.env.example)에 절대 쓰지 않고 `.env`에만 둡니다.

| 동작 | 내용 |
|---|---|
| 쓰는 곳 | `/rooms/availability`(호실 현황)와 `/groups/{id}/recommendations`(추천)가 실제 '예약 불가' 시간을 반영 |
| 방 번호 | `data/places.json` 호실의 `source_room_no`. 없으면 이름의 숫자(집현 4실 → `4`) |
| 시간 | 학교 맵은 09~22시 1시간 칸(`09000955` = 09:00~09:55). 값이 `0`인 칸만 예약 가능, `5` 예약됨·`7` 사용 중·`10` 지난 시간·모르는 값은 예약 불가. 맵에 없는 시간도 불가 |
| 호출 수 | 방 종류 번호(방별 현황의 4·6·10)로 조회하면 그 종류의 방들이 한 번에 옴: 4 → 4~9실, 6 → 2·3·12실, 10 → 1·13실. 날짜당 3번 + 현황 1번 |
| 알 수 없는 방 | 4인실 10·11실은 한 번에 6칸까지만 와서 이 API로 안 나옴 → 호실 목록에서 일단 뺌 (다른 조회 방법은 확인 중) |
| 캐시 | 같은 방·날짜는 3분(`JIPHYEONJEON_CACHE_SECONDS`) 동안 다시 부르지 않음. 동시에 같은 요청이 와도 학교 서버는 1번만 호출 |
| 학교 서버 장애 | 15분 안의 지난 값이 있으면 그걸로 응답. 없으면 503 "집현전 예약 현황을 불러오지 못했어요." 실패 후 1분간은 학교 서버를 다시 부르지 않음 |
| 형식이 다르면 | 학교 응답 구조가 바뀌면 추측하지 않고 503 + 서버 로그에 원인 기록 |

응답 형식은 2026-11-17·18 실제 응답과 도서관 앱 화면을 대조해서 확인했습니다(자세한 설명은 `app/places/jiphyeonjeon.py` 맨 위).
실제 방은 4인실 4~11실, 6인실 2·3·12실, 10인실 1·13실(총 13개)이고, `data/places.json`에는 현황을 알 수 있는
11개(J01~J09·J12·J13)를 넣었습니다. 모든 방에 콘센트·노트북 공간이 있고 대화 가능한 공간(소음 보통)입니다.

형식 확인·문제 확인용 스크립트 (학교 서버를 2번만 호출, 원본 XML은 `backend/.probe/`에 저장되고 커밋 안 됨):

```bash
python scripts/probe_jiphyeonjeon.py 6 2026-11-19   # 종류 번호(4·6·10)의 시간 × 방 표 출력
```

출력된 표를 도서관 앱의 같은 날짜 화면과 비교하면 맞는지 바로 알 수 있습니다.

## 규칙 (프론트와 동일)

- **시간표**: 월~금 × 6교시, 09:00부터 90분씩 (마지막 16:30~18:00). 매주 반복
- **공통 공강**: 30칸마다 `count/total`과 명단. 정렬은 참석 인원 내림차순 → 요일 → 교시.
  `level`은 전원 `full` / 일부 `partial` / 없음 `none`. `fullCount` = 전원 가능 칸 수
- **예약 시간**: 1시간 슬롯(시작 09~18시), 오늘부터 7일. 오늘이면 현재 시(時)와 같거나 이른 슬롯은 지난 시간.
  팀 인원 > 정원인 방은 선택 불가
- **시연용 점유**: 프론트 `isSeedOccupied()`와 같은 계산식이라 앱과 서버의 '예약됨'이 일치 (`tests/test_frontend_rules.py`에서 확인)
- **장소·호실 데이터**: `data/places.json`. 집현전 호실은 실제 그룹학습실 기준(2026-11-18 확인). 라운지·커피룸 장소는 프론트 `PLACES`와 같은 시연용
- **추천**: 예약과 같은 1시간 슬롯 단위. 전원 가능 + 조건 충족 = 초록, 1명 조정 또는 일부 조건 미충족 = 주황,
  예약됨·인원 부족은 제외. 정원은 '말한 인원'과 '팀 인원' 중 큰 값 기준
- **점수(0~100, 정렬용)**: 시간 일치 60 × (참석 인원/팀 인원) + 조건 충족 40 × (충족/요청 조건 수)
- **회의 단계 배치**: 마감 전날까지. 중간발표 관련 단계는 그 직전 3일, 마지막 단계는 마감 직전 3일, 나머지는 순서대로 나눔
- **timePreference**: "목요일 저녁", "오후 3시 이후", "주말", "11/4" 등을 코드가 해석. 못 알아들으면 시간 조건 없이 추천

## 메일 발송 (비밀번호 찾기·초대 메일)

기본값(`MAIL_BACKEND=console`)은 메일을 실제로 보내지 않고 **서버 로그에 내용을 찍습니다.** 개발 중에는 로그에서 인증 코드를 보면 됩니다.
실제로 보내려면 `backend/.env`에 SMTP 계정을 넣습니다. Gmail 예시:

```
MAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=팀용-gmail-주소@gmail.com
SMTP_PASSWORD=<Google 계정의 '앱 비밀번호' 16자리>
MAIL_FROM=팀용-gmail-주소@gmail.com
```

- Gmail은 계정 비밀번호가 아니라 **앱 비밀번호**(2단계 인증을 켠 뒤 Google 계정 → 보안 → 앱 비밀번호)를 씁니다.
- 개인 계정 말고 팀용 계정을 하나 만드는 걸 권장합니다. 계정·비밀번호는 `.env`에만 두고 저장소에 올리지 않습니다.
- 메일은 응답을 돌려준 뒤 백그라운드에서 보냅니다. 보내다 실패해도 API는 정상 응답하고 서버 로그에 "메일 발송 실패"가 남습니다.

## 남은 일

- [ ] 집현전 실제 연동: 응답 형식·호실 반영 완료. 학교 사용 허락 확인 후 `RESERVATION_PROVIDER=jiphyeonjeon`
- [ ] 4인실 10·11실 조회 방법 확인 (지금 API는 4인실을 9실까지만 줌)
- [ ] 실제로 보낼 메일 계정(SMTP) 정하기. 비밀번호 찾기 코드 입력 화면을 프론트·와이어프레임에 추가
- [ ] 회원 탈퇴
- [ ] Google Calendar 연동(11): 와이어프레임에서 '예정'
- [ ] 운영 DB(Cloud SQL)의 테이블 구조를 바꿀 일이 생기면 Alembic 마이그레이션 도입 (지금은 시작할 때 `create_all`이라 기존 테이블의 컬럼은 안 바뀜)

## 폴더 구조

```
backend/
├── app/
│   ├── main.py            # FastAPI 앱, 라우터 등록
│   ├── config.py          # 설정 (.env)
│   ├── timetable.py       # 교시·예약 시간 규칙 (프론트 model.ts와 동일)
│   ├── occupancy.py       # 호실 점유 = 시연용 점유 또는 집현전 실제 현황
│   ├── db.py, models.py   # DB 연결, 테이블
│   ├── schemas.py         # API 요청·응답 형식
│   ├── deps.py            # 의존성 (DB, LLM, 메일, 로그인 사용자, 모임 권한, 예약 현황 조회기)
│   ├── routers/           # 엔드포인트
│   ├── services/          # 계산 로직 (순수 함수, 단위 테스트 대상)
│   ├── places/            # 장소·호실 데이터, 예약 현황 (시연용 / 집현전 실제 조회: jiphyeonjeon.py)
│   └── ai/                # 응답 스키마, Claude 호출 (프롬프트 원문은 저장소의 ai/)
├── data/places.json       # 장소·호실 (집현전 호실은 실제 그룹학습실)
├── scripts/
│   ├── smoke_llm.py           # 실제 API 키로 프롬프트 확인
│   └── probe_jiphyeonjeon.py  # 집현전 실제 응답을 시간 × 방 표로 확인
├── tests/
├── deploy/                # Google Cloud 배포 (GCP.md, cloudbuild.yaml, gcloudignore)
├── Dockerfile             # 배포 이미지 (저장소 최상위에서 빌드)
├── Dockerfile.dockerignore
└── docker-compose.yml
```
