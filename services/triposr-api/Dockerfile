FROM python:3.10-slim

WORKDIR /app

COPY life-course-from-2d-to-3d/services/triposr-api/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY life-course-from-2d-to-3d/services/triposr-api/triposr_api /app/triposr_api
COPY TripoSR-main /opt/triposr

ENV PYTHONUNBUFFERED=1
ENV TRIPOSR_SOURCE_DIR=/opt/triposr

CMD ["uvicorn", "triposr_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
