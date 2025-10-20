# Render 배포 가이드

이 문서는 이 리포지토리를 Render에 배포하는 최소 단계와 환경변수(Secrets)를 등록하는 방법을 설명합니다.

요약
- 이 프로젝트는 `app.main:app` (FastAPI) 애플리케이션을 실행합니다.
- Render에서는 Docker 배포를 사용하거나 Build/Start 명령어로 배포할 수 있습니다. repo에는 `Dockerfile`이 있어서 Docker 방식 배포를 권장합니다.

사전 준비 (Render 계정 및 리포지토리 연결)
1. Render 계정 생성/로그인
2. Render 대시보드에서 "New +" → Web Service 선택
3. Repository provider (GitHub 등) 연결 → 이 리포지토리 선택

(중요) 이 저장소는 Render에서 `render-origin` 원격(remote)과 `main` 브랜치를 사용하도록 구성되어 있습니다.
배포 프로세스는 로컬에서 변경을 커밋한 뒤 `git push render-origin main` 으로 트리거됩니다. 아래 환경변수는 Render Dashboard의 Service > Environment 섹션에 등록하세요.

환경변수(필수) — Render Dashboard에 등록
(민감값은 반드시 Render UI에서 "Add Environment Variable"로 등록)
- DATABASE_URL: postgresql://user:pass@host:5432/dbname
- REDIS_HOST
- REDIS_PORT
- REDIS_PASSWORD
- FRONTEND_API_KEYS: 프론트엔드에서 사용할 x-api-key 값(콤마로 다중 가능)
- EXTERNAL_STATION_API_BASE_URL: https://chargeinfo.ksga.org
- EXTERNAL_STATION_API_KEY: (민감) serviceKey
- EXTERNAL_STATION_API_AUTH_TYPE: header (or query)
- EXTERNAL_STATION_API_KEY_HEADER_NAME: Authorization (or X-API-KEY)
- EXTERNAL_STATION_API_TIMEOUT_SECONDS: 15
- SECRET_KEY
- ENVIRONMENT=production
- DOCKER_ENV=true

배포 방식
- Docker (권장)
  - Start Command: Dockerfile 내부 CMD 사용 (Render가 Dockerfile을 사용하여 빌드)
  - `render.yaml`을 레포에 추가해 자동화 가능

- Buildpacks / Native (옵션)
  - Start Command: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app`

검증(배포 후)
1. Render 서비스 로그 확인 (Start logs)
   - pydantic ValidationError: 필요한 환경변수가 누락된 경우 발생 → 환경변수 등록 확인
2. /health 또는 / 엔드포인트 호출
   - / -> 기본 메시지
   - /api/v1/stations 는 `x-api-key` 헤더와 함께 호출

테스트 예시 (배포 후)
- 충전소 검색(예시):
```bash
curl -s -G \
  -H "x-api-key: <FRONTEND_API_KEY>" \
  --data-urlencode "lat=37.5665" \
  --data-urlencode "lon=126.9780" \
  "https://<your-service>.onrender.com/api/v1/stations" | jq
```

문제 발생 시 체크리스트
- pydantic ValidationError: env 누락
- 502/500 에러: 외부 API 호출 실패(권한/키/endpoint 확인)
- 외부 API가 HTML(로그인 페이지)를 반환: API가 공개되지 않았거나 세션/쿠키 요구

지원
- 배포 실행 후 로그 또는 curl 출력 결과를 붙여주시면 제가 문제를 진단하고 수정안을 적용하겠습니다.

참고
- render.yaml 템플릿은 repo 루트에 `render.yaml`로 추가되어 있습니다.
- 민감값은 반드시 Render Dashboard에 직접 등록하세요.
