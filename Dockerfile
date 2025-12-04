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

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
