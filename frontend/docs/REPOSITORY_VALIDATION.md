# 저장소 반영 검증 기록

검증일: 2026-11-02 (Asia/Seoul)
관련 이슈: [#3](https://github.com/SeungGyunLee/TeamPlus/issues/3)
작업 브랜치: `feature/frontend-android-mvp`

## 반영 범위

- 로컬에서 구현하고 사용자 수동 테스트까지 진행한 Android MVP를 `frontend/`에 복사했습니다.
- 원본 소스·잠금 파일·필수 에셋·테스트·라이선스를 포함했습니다. 생성된 네이티브 프로젝트, SDK·AVD, 캐시, 설치된 의존성 및 사용자 앱 데이터는 포함하지 않습니다.
- 팀원용 README와 로컬 산출물 제외 규칙을 정리했습니다.
- 실행기의 에뮬레이터 백그라운드 시작에 `-WindowStyle Hidden`을 지정했습니다.
- `tsconfig.json`의 `types`에 `expo/types`를 명시했습니다. `.gitignore`로 제외되는 자동 생성 `expo-env.d.ts`가 없어도 `global.css` 가져오기를 타입 검사할 수 있습니다.

## 수행한 검사

업로드용 `frontend/` 디렉터리에서 `Start-KWMeet.ps1 -Task check`를 실행했습니다.

| 검사 | 결과 |
|---|---|
| TypeScript `tsc --noEmit` | 통과 |
| 도메인·예약·저장소 자동 테스트 | 12/12 통과, 실패 0 |
| Expo `install --check` | Dependencies are up to date |
| PowerShell 실행기 구문 분석 | 오류 없음 |
| 복사한 구현·테스트·에셋의 SHA-256 비교 | 원본과 일치 |
| 수정 TXT 보고서의 SHA-256 비교 | 현재 바탕화면 파일과 일치 |

README·저장소 제외 규칙·실행기·타입 설정은 위에 설명한 제출 준비용 변경 대상입니다. 화면·공강 계산·예약·저장소 구현과 테스트 코드는 원본에서 변경하지 않았습니다.

의존성 설치는 기존 PC의 `node_modules`를 Git에서 제외되는 로컬 디렉터리 연결로 재사용했습니다. `package.json`과 `pnpm-lock.yaml`이 기존 프로젝트와 동일함을 확인하고, 저장소에 복사한 소스에 대해 검사를 실행했습니다. 별도 신규 의존성 설치 시도는 중단했으므로 완전한 새 PC에서의 설치 성공까지 검증한 것은 아닙니다. 팀원은 README의 `pnpm install --frozen-lockfile`로 의존성을 설치해야 합니다.

자동 테스트는 계산·검증 및 메모리 저장소를 대상으로 합니다. 실제 AsyncStorage와 Android UI 전체를 조작하는 E2E 테스트는 아닙니다.

## 사용자 수정 보고서 보존

파일: `TeamPlus_프론트엔드_작업보고서_2026-11-01.txt`

SHA-256:

```text
B76E7B62A25B3051EEF1D03B80D42FA63769329F14CC1BC23061F72361B07250
```

사용자가 수정한 바탕화면 파일을 그대로 포함합니다. 본문·BOM·줄바꿈을 수정하지 않았으며 `.gitattributes`로 해당 TXT의 Git 줄바꿈 변환을 끕니다. 문서 안의 업로드 전 상태는 작성 당시 기록이고, 실제 업로드·리뷰 진행 상태는 연결된 Issue와 PR을 기준으로 확인합니다.

## 기존 실행 기록과 미검증 범위

2026-11-01에 Android 16/API 36 에뮬레이터의 Expo Go 57.0.9 실행과 Android 개발 번들 생성을 확인했고 사용자가 앱 수동 조작이 정상이라고 확인했습니다. 기존 PC의 기록은 [TEST_REPORT.md](../TEST_REPORT.md)에 있습니다.

이번 저장소 반영 과정에서 앱을 다시 실행하거나 사용자 데이터를 조작하지 않았습니다. 실물 기기·독립 APK·릴리스 FPS·접근성 전체 항목 및 새 PC 설치는 추가 검증 대상입니다. 실제 로그인·서버·AI·학교 예약 연동은 미구현입니다.
