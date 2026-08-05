FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY entity_lookup ./entity_lookup

RUN pip install --no-cache-dir -e ".[dev]"

ENV PYTHONPATH=/app/src
ENV ADAPTER_MODE=mock
ENV ENTITY_LOOKUP_PATH=/app/entity_lookup/databases.yaml

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
