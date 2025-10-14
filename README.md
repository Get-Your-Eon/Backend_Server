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


문제가 있거나 시작 스크립스를 수정하길 원하시면 어떤 Start Command를 사용 중인지(또는 Render 서비스 URL/설정) 알려주시면 맞춤형으로 조정해 드리겠습니다.
