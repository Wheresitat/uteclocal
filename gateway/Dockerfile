FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

COPY gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway /app/gateway

EXPOSE 8000
VOLUME ["/data"]

ENV GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8000

CMD ["sh", "-c", "uvicorn gateway.app:app --host ${GATEWAY_HOST:-0.0.0.0} --port ${GATEWAY_PORT:-8000}"]
