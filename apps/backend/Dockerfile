FROM python:3.11-slim

WORKDIR /app

# curl needed for DynamoDB health check probe
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e . \
    && python -m spacy download en_core_web_sm

EXPOSE 8080

CMD ["uvicorn", "autoeval_sum.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
