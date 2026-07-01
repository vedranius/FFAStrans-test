FROM python:3.12-slim

LABEL maintainer="FFAStrans Linux Mimo"
LABEL description="FFAStrans Linux Mimo - Workflow & Transcoding System"

ENV DEBIAN_FRONTEND=noninteractive
ENV FFASTRANS_API_HOST=0.0.0.0
ENV FFASTRANS_API_PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mediainfo \
    exiftool \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r ffastrans && useradd -r -g ffastrans -d /app -s /bin/bash ffastrans

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ffastrans/ ./ffastrans/
COPY drop_folders/ ./drop_folders/
COPY data/ ./data/

RUN mkdir -p /app/data/workflows /app/data/jobs /app/data/logs \
    && chown -R ffastrans:ffastrans /app

USER ffastrans

EXPOSE 8080

VOLUME ["/app/data", "/app/drop_folders"]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/about || exit 1

ENTRYPOINT ["python", "-m", "ffastrans.main"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
