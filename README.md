# Codyssey EV Charger Backend

## 참조 관계 (Configuration & 주요 모듈)

아래는 프로젝트 내 주요 파일들이 어떻게 서로를 참조하는지 간단히 정리한 다이어그램입니다.

```
				  .env (optional, 프로젝트 루트)
					 |
					 v
			      +-----------------------+
			      | app/core/config.py    |  <- 메인 설정(권장)
			      |  Settings -> settings |
			      +-----------------------+
				       ^       
				       |       
    +----------------+   +-------------+-------+-------------------+
    | app/main.py    |   | alembic/env.py                              |
    | app/api/...    |   | app/auth.py                                 |
    +----------------+   +---------------------------------------------+

    (레거시/스크립트)
    +----------------+
    | app/config.py  |  <- 보조/레거시 설정 (init_db.py에서 사용되던 파일)
    +----------------+
	    |
	    v
    app/db/init_db.py  (현재는 app.core.config로 통일됨)

기본 원칙: 런타임 애플리케이션과 Alembic 마이그레이션은 `app/core/config.py`의 `settings`를 사용합니다. 일부 개별 스크립이 `app/config.py`를 참조할 수 있으므로 일관성 있게 통일하는 것을 권장합니다.

## 주요 설정 항목

- PROJECT_NAME, API_VERSION
- DATABASE_URL (또는 DATABASE_USER/.. 조합)
- REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
- SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
- ENVIRONMENT, DOCKER_ENV

## 권장 작업

- `app/core/config.py`를 메인 설정으로 사용하도록 통일했습니다.
- 필요한 경우 루트에 `.env` 파일을 추가하여 개발 환경의 값을 관리하세요.

## Render 배포 가이드

아래 내용은 Render(https://render.com)에 이 프로젝트를 배포할 때 필요한 최소 설정과 시작 스크립트 예시입니다.

1) 필수 환경 변수 (Render 대시보드 > Service > Environment > Environment Variables에 추가)

- DATABASE_URL: postgresql+asyncpg://<user>:<pass>@<host>:<port>/<dbname>
- REDIS_HOST (선택): Redis 호스트
- REDIS_PORT (선택): Redis 포트
- REDIS_PASSWORD (선택): Redis 비밀번호
- SECRET_KEY: JWT 등에서 사용하는 비밀키
- ENVIRONMENT: production
- DOCKER_ENV: true/false (선택)
- ADMIN_MODE: true (docs를 보고 싶으면)
- ADMIN_CREDENTIALS: "admin:password" (콤마로 여러 계정 구분)

2) 빌드/시작 설정 예시

- Build Command:
	- `poetry install --no-dev --no-interaction`  # 또는 프로젝트 빌드 방식에 맞게 설정

- Start Command (Render에서 설정):
	- `bash start.sh`
	- 또는 직접: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
	- 프로덕션 환경에서 Gunicorn을 사용할 경우:
		- `gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT app.main:app`

### Render용 명령어 샘플 (복사/붙여넣기용)

아래는 Render 서비스 설정 화면에 그대로 붙여넣어 사용할 수 있는 예시들입니다.

- Build Command (권장: Poetry 사용 시)

```
poetry install --no-dev --no-interaction
```

- Start Command (권장: start.sh를 사용하는 방법)

```
bash start.sh
```

- Start Command (직접 uvicorn 실행 — 개발/간단 배포용)

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- Start Command (프로덕션 권장: Gunicorn + Uvicorn worker)

```
gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT app.main:app
```

팁:
- `PORT` 환경변수는 Render가 자동으로 주입합니다. Start Command에는 `$PORT` 변수를 사용하세요.
- `bash start.sh`를 사용하면 마이그레이션(alembic/poetry 스크립트)이 먼저 실행된 뒤 서버가 올라가므로 배포가 더 안전합니다.


3) `start.sh` (레포트 루트에 포함됨)

- 이 스크립트는 마이그레이션을 실행한 뒤 Uvicorn을 실행합니다. Render의 Start Command에 `bash start.sh`를 지정하면 됩니다.

4) 데이터베이스 마이그레이션

- 마이그레이션 적용 (Render의 배포 단계에서 실행할 수 있음):
	- `poetry run migrate`  # pyproject.toml에 scripts.migrate가 설정되어 있는 경우
	- 또는 `alembic upgrade head`

5) Docs 접근

- 현재 코드에서는 docs( `/docs`, `/redoc` )와 `openapi_url`이 `ADMIN_MODE`가 true일 때만 활성화됩니다. Render에서 docs를 확인하려면 `ADMIN_MODE=true`와 `ADMIN_CREDENTIALS`를 설정하세요.

6) 간단한 테스트

- 배포 후 `db-test` 엔드포인트 테스트 예시 (제조사/모델그룹 쿼리):
	- `https://<your-service>.onrender.com/db-test?manufacturer=Hyundai&model_group=IONIQ`

7) 권장 보안 주의

- `ADMIN_CREDENTIALS`를 평문으로 두지 말고 Render Secrets(환경변수 암호화 기능)을 사용하세요.
- `SECRET_KEY`는 반드시 안전하게 보관하세요.

## Uptime & cold start 방지

Render의 무료(혹은 일부 설정된) 인스턴스는 일정 시간 동안 트래픽이 없으면 인스턴스를 정지시키거나 cold start가 발생할 수 있습니다. 서비스 응답 지연/초기화 비용을 줄이기 위해 UptimeRobot 같은 외부 모니터링 서비스를로 주기적으로 ping을 보내 인스턴스를 깨워두는 패턴을 사용할 수 있습니다.

권장 설정 예시 (UptimeRobot):

- 모니터 타입: HTTP(s)
- 체크 URL: `https://<your-service>.onrender.com/` 또는 `/health` (권장)
- 주기: 5분
- 요청 방식: HEAD (가볍게 요청하기 위해)

우리 서비스에 적용된 변경 사항

- `/` 경로에 대한 `HEAD` 요청을 명시적으로 200 응답으로 처리하도록 서버에서 핸들러를 추가했습니다. 따라서 UptimeRobot의 HEAD ping이 405를 반환하지 않고 200을 받게 되어 안정적으로 인스턴스를 깨울 수 있습니다.
- 보다 명확한 상태 확인이 필요하면 별도의 `/health` GET 엔드포인트를 만들어 사용하세요(예: DB, Redis 연결 상태를 JSON으로 반환).

주의사항

- 너무 짧은 주기로 빈번히 ping을 보내면 비용 혹은 rate-limit 이슈가 발생할 수 있으니 5분 정도의 간격을 권장합니다.
- 보안상 `/health`를 공개할 경우 민감 정보를 노출하지 않도록 주의하세요(간단한 OK/status만 반환).

## 프론트엔드 연동: API 키 및 CORS 설정

이 프로젝트는 프론트엔드(React 앱)와의 연동을 위해 간단한 API 키 기반 인증과 CORS 제한을 지원합니다. 아래는 프론트엔드 팀에게 전달할 내용과 예시입니다.

1) 백엔드에서 설정해야 할 환경변수

- `FRONTEND_API_KEYS` — 프론트엔드에서 사용할 API 키들을 쉼표로 구분하여 설정합니다.
	- 예: `FRONTEND_API_KEYS=frontend-key-abc123,frontend-key-xyz987`
	- Render 대시보드: Service > Environment > Add Environment Variable

- `ALLOWED_ORIGINS` — CORS 허용 origin 목록(쉼표 구분)
	- 예: `ALLOWED_ORIGINS=https://app.example.com,https://staging.example.com`
	- 설정하면 서버는 해당 origin에서 오는 브라우저 요청만 허용합니다.

2) API 키 생성 권장 방법

- 간단 생성(예시): `openssl rand -hex 32` 또는 `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- 키는 비밀로 취급하세요. (레포지토리에 커밋금지)

3) 프론트엔드 팀에 전달할 키(예시)

- 전달 예시: `frontend-key-abc123` (실제 배포 전에 위에서 생성한 무작위 키로 대체하세요)

4) 프론트엔드에서 API를 호출하는 방법 (예시)

- Fetch API 예시:

```js
const API_KEY = 'frontend-key-abc123';
fetch(`https://backend-server-4na0.onrender.com/subsidy?manufacturer=${encodeURIComponent(manufacturer)}&model_group=${encodeURIComponent(modelGroup)}`, {
	method: 'GET',
	headers: {
		'X-API-KEY': API_KEY,
		'Accept': 'application/json'
	}
})
.then(res => res.json())
.then(data => console.log(data))
.catch(err => console.error(err));
```

- Axios 예시:

```js
import axios from 'axios';

const API_KEY = process.env.REACT_APP_API_KEY; // or embed securely
axios.get('https://backend-server-4na0.onrender.com/subsidy', {
	params: { manufacturer: '현대자동차', model_group: 'GV60' },
	headers: { 'X-API-KEY': API_KEY }
}).then(res => console.log(res.data));
```

5) curl 테스트 예시

```
curl -H "X-API-KEY: frontend-key-abc123" "https://backend-server-4na0.onrender.com/subsidy?manufacturer=현대자동차&model_group=GV60"
```

6) 보안 주의 및 권장사항

- 브라우저 환경에서 API 키를 클라이언트 코드에 직접 포함하는 것은 노출 위험이 있습니다. 최선의 방법은 백엔드에서 토큰 발급(세션/short-lived token) 또는 프론트엔드가 소유한 인증서버를 두는 것입니다. 다만, 팀 내부 프로젝트로서 제한된 도메인(ALLOWED_ORIGINS)과 제한된 키를 사용하는 경우 운영 상 허용하는 정책으로 사용할 수 있습니다.
- DB 사용자 권한을 읽기 전용(SELECT)으로 설정하세요. 서버 단에서도 `ensure_read_only_sql` 방어 로직을 적용했습니다.
- 주기적으로 키를 회전(rotate)하고, 더 이상 사용하지 않는 키는 `FRONTEND_API_KEYS`에서 제거하세요.

7) 어떤 엔드포인트가 API 키를 요구하나

- 현재 API 키가 필요한 엔드포인트: `/subsidy`, `/db-test` (읽기 전용 API)
- 공개 엔드포인트: `/health` (모니터링용), `/` (루트 헬스)

8) 환경변수 변경 시 배포

- Render에서 환경변수 업데이트한 후에는 Redeploy 또는 Manual Deploy가 필요합니다.

프론트엔드 팀에 이 문구와 함께 생성한 `frontend-key-...` 값을 공유해 주세요.


문제가 있거나 시작 스크립스를 수정하길 원하시면 어떤 Start Command를 사용 중인지(또는 Render 서비스 URL/설정) 알려주시면 맞춤형으로 조정해 드리겠습니다.
