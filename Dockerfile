FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://www.ucw.cz/isolate/debian/signing-key.asc \
        -o /etc/apt/keyrings/isolate.asc \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc] http://www.ucw.cz/isolate/debian/ bookworm-isolate main" \
        > /etc/apt/sources.list.d/isolate.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends isolate \
    && rm -rf /var/lib/apt/lists/*

COPY . /appl

RUN pip install --no-cache-dir fastapi uvicorn redis sqlalchemy rq==1.15

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
