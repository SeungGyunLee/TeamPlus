# TeamPlus Frontend · KW Meet Android MVP

광운대학교 학생들의 모임 일정 조율과 장소 탐색을 위한 React Native 앱입니다. 현재 앱 표시명은 **KW Meet**이며, 백엔드 없이 기기 내부의 시연 데이터로 동작합니다.

## 구현 범위

- 홈, 모임·팀원 관리, 팀원별 시간표, 공통 공강, 장소 목록·상세, 집현전 가상 예약, 예약·취소 내역, 설정의 9개 화면.
- 새 모임의 기본 팀원 건우·승균·휘서. 이름 편집, 팀원 추가·삭제, 모임 삭제와 확인 모달.
- 월~금 × 6교시의 반복 시간표. 09:00~18:00를 90분씩 구분하며 팀원별로 저장합니다.
- 시간대별 참석·불참 인원과 명단, 참석 가능 인원 내림차순 정렬. 동률은 요일·교시순입니다.
- 더미 장소 검색·분류 및 상세 정보. 장소 데이터는 시연용이며 AI 추천 점수는 제공하지 않습니다.
- 집현전 가상 예약: 모임·호실·날짜·1시간 슬롯 선택, 확인, 예약 완료와 취소.
- 방 중복, 같은 모임의 동시간 다른 방 예약, 정원 초과, 과거·잘못된 날짜·시간을 검증합니다.
- AsyncStorage 저장·복원, 쓰기 직렬화, 저장 실패 안내·재시도 및 손상 데이터 원본 보존.
- 라이트 기본값, 다크, 시스템 테마. Pretendard·의미별 색상 토큰·Reanimated 효과.

실제 로그인·그룹 초대·REST API·클라우드 동기화·AI 추천·지도·푸시·학교 시설 예약은 미구현입니다. 가상 예약에는 실제 예약 효력이 없습니다.

## 설치 및 실행

Node.js LTS와 pnpm 10.28.2를 준비하고 저장소 루트에서 실행합니다.

```powershell
cd frontend
npm install --global pnpm@10.28.2
pnpm install --frozen-lockfile
pnpm start
```

Android 폰과 PC를 같은 네트워크에 연결하고 **Expo SDK 57을 지원하는 Android Expo Go**로 QR을 스캔합니다. 호환 클라이언트는 [Expo Go 다운로드 페이지](https://expo.dev/go)에서 확인할 수 있습니다. 이 앱의 Expo 버전은 57.0.31입니다.

Windows에서는 `Start-KWMeet.cmd`로 실행할 수도 있습니다. 이 실행기는 일반 Node.js 설치를 우선 사용하며, 기존 개발 PC에서는 번들 런타임을 보조 경로로 찾습니다.

### PC Android 에뮬레이터

Android Studio에서 SDK와 가상 기기를 준비하고 `ANDROID_HOME` 및 필요한 Java 환경을 설정한 뒤 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\Start-KWMeet.ps1 -Task emulator
```

또는 `Run-Android.cmd`를 실행합니다. 실행기는 기존 가상 기기를 사용하고, 없으면 `KW_Meet_API_36` 또는 첫 번째 AVD를 선택합니다. localhost는 IPv4 우선으로 사용합니다. 개발 서버는 앱을 사용하는 동안 유지해야 합니다.

기존 개발 PC의 SDK·AVD·개발 서버나 가상폰의 사용자 데이터는 저장소에 포함하지 않습니다. 새 PC에서는 별도로 준비해야 합니다. PC별 메모리·GPU·하드웨어 가속 설정에 따라 실행 속도가 달라집니다.

## 검증

```powershell
pnpm typecheck
pnpm test
pnpm check:expo
pnpm bundle:android
```

Windows 통합 검사는 `powershell -ExecutionPolicy Bypass -File .\Start-KWMeet.ps1 -Task check`로 실행합니다.

공강 계산·예약 검증·저장소 테스트는 12개입니다. 저장소 단위 테스트에는 메모리 저장소를 사용하며 Android UI E2E 테스트는 아닙니다. Android 에뮬레이터 실행과 사용자 수동 조작을 확인했으며 실물 기기, 독립 APK, 접근성 전체 항목 및 릴리스 성능은 추가 검증 대상입니다.

- [저장소 반영 시 검증 기록](docs/REPOSITORY_VALIDATION.md)
- [앞선 개발 PC 검증 기록](TEST_REPORT.md): 2026-11-01 시점의 기록입니다. 당시의 미업로드 상태·개인 PC 경로는 역사적 기록입니다.
- [Android 수동 체크리스트](docs/ANDROID_QA.md): 모든 항목의 자동 통과를 뜻하지 않습니다.

Android JS 번들 생성은 APK 생성·설치와 별개입니다. `pnpm android`는 Android 네이티브 개발 빌드를 시도하며 SDK/JDK/NDK 등 별도 도구가 필요합니다. `eas.json`은 빌드 설정 예시이며 EAS 업로드나 스토어 배포는 수행하지 않았습니다.

## 코드 구조

```text
app/                 Expo Router 화면 및 탭·스택
src/components/      공통 UI·시간표 그리드·확인 모달
src/theme/           라이트·다크 테마 토큰
src/domain/          타입·공강 계산·예약 검증
src/data/            시드 데이터·StoragePort·LocalRepository
src/state/           전역 상태·복원·저장·재시도
tests/               도메인 및 저장소 테스트
docs/                보고서 및 검증 문서
assets/              앱 아이콘·Pretendard 폰트
licenses/            외부 라이선스 원문
```

시간표 수정은 화면 → `AppProvider.update()` → `LocalRepository.save()` → AsyncStorage 순서로 반영됩니다. 공강은 `availability()`와 `rankedAvailability()`로 계산하고, 예약은 `book()`에서 검증한 뒤 상태에 반영합니다. `cancel()`은 기록을 남긴 채 취소 상태로 바꿉니다.

`ownerId`, `inviteCode`, 선택적 `userId`는 확장을 위한 필드입니다. 인증·권한 검사나 초대 기능은 연결하지 않았습니다. `StoragePort`는 키-값 저장 인터페이스이며 완성된 서버 API 명세는 아닙니다. 여러 기기의 동시 예약에는 별도의 서버 검증·트랜잭션이 필요합니다.

## 작업보고서

[2026-11-01 프론트엔드 작업보고서](docs/TeamPlus_프론트엔드_작업보고서_2026-11-01.txt)는 **사용자가 수정한 바탕화면 파일을 바이트 그대로 복사한 문서**입니다. 주요 함수, 구현 범위, 미구현 기능과 협업 계획을 설명합니다. 작성 당시의 업로드 전 상태도 그대로 보존했으며, 이후 실제 진행 상태는 [Issue #3](https://github.com/SeungGyunLee/TeamPlus/issues/3)과 연결된 PR에서 확인합니다.

보고서 TXT의 BOM·줄바꿈을 유지하도록 `.gitattributes`에서 해당 파일의 줄바꿈 변환을 끕니다.

## 기술·라이선스

Expo 57.0.31, React Native 0.86.3, React 19.2.3, TypeScript 6.0.3, NativeWind 4.2.7, Reanimated 4.5.1, AsyncStorage 2.2.0을 사용합니다. 해석된 의존성은 `pnpm-lock.yaml`에 고정합니다.

React Native Reusables의 MIT 버튼 소스를 앱의 토큰·폰트·API에 맞게 수정했습니다. Pretendard는 SIL OFL 1.1, Lucide는 ISC입니다. 외부 소스 원문과 고지는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 및 `licenses/`에 보존합니다.

## 알려진 제한

- 데이터는 기기 단위이며 앱 제거·데이터 초기화 후 복구와 기기 간 공유는 제공하지 않습니다.
- 새 모임은 생성 즉시 저장됩니다. 편집 화면에서 돌아가는 동작은 생성 취소가 아닙니다.
- 수업은 주간 90분 블록, 예약은 날짜별 1시간 슬롯이며 자동 매핑하지 않습니다.
- 예약 시작 시각은 09~18시로 마지막 슬롯은 18:00~19:00입니다. 여러 시간을 한 번에 예약하지 않습니다.
- 저장 실패 시 안내와 재시도를 제공하지만 저장 전 앱을 닫으면 변경이 유실될 수 있습니다.
- 시설 이름·호실·인원·위치·운영 정보는 예시이며 실제 현황을 조회하지 않습니다.
