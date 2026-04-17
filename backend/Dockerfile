FROM python:3.10-slim

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend /app
RUN mkdir -p /app/storage \
    && addgroup --system appuser \
    && adduser --system --ingroup appuser --no-create-home appuser \
    && chown -R appuser:appuser /app /app/storage

ENV PYTHONUNBUFFERED=1

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
