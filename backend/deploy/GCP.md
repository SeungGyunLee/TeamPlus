# Google Cloud 배포 (Cloud Run + Cloud SQL)

시연용 서버를 Google Cloud에 올리는 순서다. 서버는 **Cloud Run**(Docker 이미지 실행, HTTPS 주소 자동 발급), DB는 **Cloud SQL PostgreSQL**에 둔다. Cloud Run 컨테이너 안의 파일은 재시작·재배포 때 사라지기 때문에 SQLite로는 회원·모임이 유지되지 않는다.

```
앱(Android) ──HTTPS──▶ Cloud Run: teamplus-api ──소켓──▶ Cloud SQL: teamplus-db (PostgreSQL 16)
                              │
                              └─ Secret Manager: DB 주소, Claude 키, 학교 API 주소, SMTP 비밀번호
```

- 지역은 서울(`asia-northeast3`). 학교 API를 부르기에도 가깝다.
- 비용: Cloud SQL 가장 작은 사양(`db-f1-micro`)이 서울 기준 월 약 $10이고 저장공간 10GB는 따로 든다. Cloud Run은 시연 정도 사용량이면 무료 한도 안이다. 정확한 값은 [Cloud SQL 가격](https://cloud.google.com/sql/pricing) 참고. 시연이 끝나면 10단계로 DB를 멈추거나 지운다.
- 아래 명령은 Windows PowerShell 기준이다. 모두 **저장소 최상위(`TeamPlus/`)** 에서 실행한다.

## 0. 준비 (처음 한 번)

1. [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)를 설치한다.
2. Google Cloud 콘솔에서 프로젝트를 만들고 결제 계정을 연결한다.
3. 로그인하고 사용할 API를 켠다.

```powershell
gcloud auth login
$PROJECT_ID = "여기에-프로젝트-ID"
$REGION = "asia-northeast3"
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
```

PowerShell 창을 새로 열 때마다 `$PROJECT_ID`, `$REGION` 같은 변수는 다시 넣어야 한다.

## 1. 이미지 저장소 만들기

```powershell
gcloud artifacts repositories create teamplus --repository-format=docker --location=$REGION
```

## 2. Cloud SQL(PostgreSQL) 만들기 — 5~10분 걸림

PostgreSQL 16부터는 기본 사양이 비싼 Enterprise Plus라서 `--edition=enterprise --tier=db-f1-micro`를 꼭 붙인다.

```powershell
gcloud sql instances create teamplus-db --database-version=POSTGRES_16 --edition=enterprise --tier=db-f1-micro --region=$REGION --storage-size=10

# DB와 접속 계정 (비밀번호는 영문·숫자만 24자로 자동 생성)
$DB_PASS = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
gcloud sql databases create teamplus --instance=teamplus-db
gcloud sql users create teamplus --instance=teamplus-db --password=$DB_PASS

$SQL_CONN = gcloud sql instances describe teamplus-db --format="value(connectionName)"
$SQL_CONN   # 예: 프로젝트ID:asia-northeast3:teamplus-db
```

테이블은 서버가 처음 뜰 때 자동으로 만든다(직접 만들 필요 없음).

## 3. 비밀값을 Secret Manager에 넣기

비밀값은 이미지나 저장소가 아니라 Secret Manager에 둔다. 아래 함수는 값 끝에 줄바꿈이 붙지 않게 파일로 넣는다.

```powershell
function Set-Secret($name, $value) {
  $f = (New-TemporaryFile).FullName
  [IO.File]::WriteAllText($f, $value)
  gcloud secrets describe $name *> $null
  if ($LASTEXITCODE -eq 0) { gcloud secrets versions add $name --data-file=$f }
  else { gcloud secrets create $name --data-file=$f --replication-policy=automatic }
  Remove-Item $f
}

# 필수: DB 주소 (Cloud Run은 /cloudsql/ 소켓으로 Cloud SQL에 붙는다)
Set-Secret teamplus-database-url "postgresql://teamplus:$DB_PASS@/teamplus?host=/cloudsql/$SQL_CONN"

# 선택: Claude 키 (없으면 조건 해석·과제 분석 API가 503, 추천 이유는 기본 문구)
Set-Secret teamplus-anthropic-key "sk-ant-..."

# 선택: 집현전 실제 현황 (학교 비공개 API, 사용 전 확인 필요. backend/.env의 값과 같게)
Set-Secret teamplus-jiphyeonjeon-status-url "https://..."
Set-Secret teamplus-jiphyeonjeon-map-url "https://..."
```

`$DB_PASS`를 잃어버려도 DB 주소는 Secret Manager에 남아 있다. 새로 정하려면 `gcloud sql users set-password teamplus --instance=teamplus-db --password=새비밀번호` 후 `Set-Secret`을 다시 실행한다.

## 4. Cloud Run이 DB·비밀값을 쓸 수 있게 권한 주기

Cloud Run은 기본으로 Compute Engine 기본 서비스 계정으로 실행된다.

```powershell
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

## 5. 이미지 만들기 (Cloud Build)

PC에 Docker가 없어도 된다. `backend/`와 `ai/`만 올라간다(`.env`·DB 파일·`frontend/`는 제외, `backend/deploy/gcloudignore`).

```powershell
gcloud builds submit --config=backend/deploy/cloudbuild.yaml --ignore-file=backend/deploy/gcloudignore .
$IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/teamplus/backend:latest"
```

PC의 Docker Desktop으로 만들어 올려도 된다.

```powershell
gcloud auth configure-docker "$REGION-docker.pkg.dev"
docker build -f backend/Dockerfile -t $IMAGE .
docker push $IMAGE
```

## 6. Cloud Run에 배포

```powershell
gcloud run deploy teamplus-api `
  --image=$IMAGE `
  --region=$REGION `
  --allow-unauthenticated `
  --add-cloudsql-instances=$SQL_CONN `
  --set-secrets="DATABASE_URL=teamplus-database-url:latest,ANTHROPIC_API_KEY=teamplus-anthropic-key:latest" `
  --set-env-vars="RESERVATION_PROVIDER=mock,MAIL_BACKEND=console" `
  --max-instances=2 `
  --memory=512Mi
```

- Claude 키를 아직 안 넣었으면 `--set-secrets`에서 `ANTHROPIC_API_KEY=...` 부분을 뺀다.
- `--max-instances=2`: 가장 작은 DB는 동시 연결이 25개 정도라서 서버 수를 묶어 둔다(서버 한 대당 최대 10개 연결).
- 집현전 실제 현황을 켤 때:

```powershell
gcloud run services update teamplus-api --region=$REGION `
  --update-secrets="JIPHYEONJEON_STATUS_URL=teamplus-jiphyeonjeon-status-url:latest,JIPHYEONJEON_MAP_URL=teamplus-jiphyeonjeon-map-url:latest" `
  --update-env-vars="RESERVATION_PROVIDER=jiphyeonjeon"
```

## 7. 확인하고 프론트에 주소 알려주기

```powershell
$URL = gcloud run services describe teamplus-api --region=$REGION --format="value(status.url)"
$URL                                   # 예: https://teamplus-api-xxxxx-du.a.run.app
Invoke-RestMethod "$URL/api/health"    # status = ok
```

- 브라우저에서 `$URL/docs`를 열면 모든 API를 직접 호출해 볼 수 있다.
- 프론트는 `frontend/.env.local`의 `EXPO_PUBLIC_API_URL`에 이 주소를 넣는다(끝에 `/api`는 붙이지 않음).
- 회원가입하고 모임을 만든 뒤 8단계로 다시 배포해도 그 계정으로 로그인되고 모임이 보이면 DB가 유지되는 것이다.

## 8. 코드를 고친 뒤 다시 배포

```powershell
gcloud builds submit --config=backend/deploy/cloudbuild.yaml --ignore-file=backend/deploy/gcloudignore .
gcloud run deploy teamplus-api --image=$IMAGE --region=$REGION
```

`gcloud run deploy`는 이전에 넣은 DB 연결·비밀값·환경변수 설정을 그대로 유지한다.

## 9. 로그 보기

```powershell
gcloud run services logs read teamplus-api --region=$REGION --limit=50
```

비밀번호 찾기 메일은 `MAIL_BACKEND=console`이면 보내지 않고 이 로그에 인증 코드가 찍힌다. 실제 메일을 보내려면 `SMTP_*` 값을 넣고 `MAIL_BACKEND=smtp`로 바꾼다. 이때 메일은 응답 뒤에 보내므로 `--no-cpu-throttling`을 같이 주는 게 안전하다(대신 서버가 켜져 있는 시간만큼 과금).

## 10. 시연 뒤 비용 정리

```powershell
# DB만 멈춤 (데이터는 남고 저장공간 비용만 남음). 다시 켤 때는 ALWAYS
gcloud sql instances patch teamplus-db --activation-policy=NEVER

# 완전히 지움 (되돌릴 수 없음)
gcloud run services delete teamplus-api --region=$REGION
gcloud sql instances delete teamplus-db
```

## 문제 해결

| 증상 | 확인할 것 |
| --- | --- |
| 서버 로그에 `Cloud Run에서 SQLite를 쓰고 있어요` | `DATABASE_URL` 비밀값이 연결되지 않음. 6단계 `--set-secrets` 확인 |
| `connection ... /cloudsql/... failed` | `--add-cloudsql-instances` 값, 4단계 `roles/cloudsql.client` 권한, DB 주소의 비밀번호 |
| `Permission denied on secret` | 4단계 `roles/secretmanager.secretAccessor` 권한 |
| Cloud Build가 권한 오류로 실패 | 같은 서비스 계정(`$SA`)에 `roles/artifactregistry.writer`, `roles/logging.logWriter`를 추가하거나 5단계 Docker 방식 사용 |
| `--allow-unauthenticated`가 조직 정책 때문에 실패 | 학교 계정 프로젝트에서 생길 수 있음. 개인 Google 계정 프로젝트를 쓰거나, 배포 명령에 `--no-invoker-iam-check`를 붙인다 |
| 호실 현황·추천이 503 `집현전 예약 현황을 불러오지 못했어요` | 학교 서버가 Google Cloud에서 오는 요청을 막는지 로그 확인. 그동안은 `RESERVATION_PROVIDER=mock` |
| 첫 요청이 몇 초 느림 | 요청이 없으면 서버가 꺼졌다가 다시 켜지기 때문. 시연 당일만 `--min-instances=1` (켜져 있는 동안 과금) |
