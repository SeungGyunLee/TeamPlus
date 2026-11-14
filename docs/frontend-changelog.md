# KW Meet 프론트엔드 개발 이력

| 날짜 (한국 시간) | 작업 | 변경 내용 | 구현 상태 | PR |
|---|---|---|---|---|
| 2026-11-02 | Android 로컬 MVP 병합 | 9개 화면, 모임·시간표·공강·가상 예약, 테마, AsyncStorage, 테스트 12개와 작업보고서 | 기존 에뮬레이터 시연·테스트 확인 | [#4](https://github.com/SeungGyunLee/TeamPlus/pull/4) |
| 2026-11-13 | 팀 앱 플로우 참고 자료 병합 | 앱 화면 이동 설계도 추가 | 설계 자료 | [#8](https://github.com/SeungGyunLee/TeamPlus/pull/8) |
| 2026-11-14 | 서버 연결 및 추천·과제 분석 UI | 기존 화면의 모임·팀원·시간표·공강·장소 API 연결, 자연어·추가 질문·추천, 과제 마감일·회의 단계, 도서관과 일정 작성 | HTTP 및 Android 번들 검증 완료, 기기 조작과 실제 Claude 확인 필요 | [Issue #9 및 연결 PR](https://github.com/SeungGyunLee/TeamPlus/issues/9) |

주요 파일은 `frontend/src/data/api.ts`, `frontend/src/state/apiHooks.ts`, `frontend/app/recommend/`, `frontend/app/recommend-results/`, `frontend/app/assignments/`, `frontend/app/assignment/`, `frontend/app/calendar.tsx`입니다.

2026-11-14에는 타입 검사, 프론트 테스트 12개, HTTP 통합 검사, 기존 백엔드 테스트 96개와 Android JS 번들 생성을 확인했습니다. 워크플로와 기능별 검증 범위는 [개발 명세서](frontend.md), [앱 플로우](frontend-flow.md)에 기록했습니다.
