FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy both packages so gateway.* and tools.* are importable from /app
COPY gateway/ ./gateway/
COPY tools/ ./tools/

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
