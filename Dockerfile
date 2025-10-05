FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry

RUN poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock /app/

RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

RUN pip install -r requirements.txt && pip install "uvicorn[standard]"

COPY . /app

EXPOSE 8000

CMD ["/usr/local/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]