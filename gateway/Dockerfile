FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

COPY gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway /app/gateway

EXPOSE 8124
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python - <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen('http://localhost:8124/health', timeout=5) as resp:
        data = json.loads(resp.read().decode())
    sys.exit(0 if data.get('status') == 'ok' else 1)
except Exception:
    sys.exit(1)
PY

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8124"]
