FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
# LightGBM requires libgomp on Debian Linux.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/requirements-serving.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY src/taxi_mlops/serving /app/taxi_mlops/serving
RUN touch /app/taxi_mlops/__init__.py \
    && groupadd --system app && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app
USER app
EXPOSE 8080
CMD ["uvicorn", "taxi_mlops.serving.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
