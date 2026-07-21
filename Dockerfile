# BROKEN as of the vLLM migration: this base image ships Python 3.11, but
# vLLM's pre-built ROCm wheels (requirements.txt) are Python-3.12-only, so
# `pip install -r requirements.txt` will fail to resolve a working vLLM here.
# Needs a Python-3.12 ROCm base image (and system libopenmpi3t64 + miopen-hip,
# see README) before this Dockerfile is usable again — not yet validated.
FROM rocm/pytorch:rocm7.1_ubuntu22.04_py3.11_pytorch_2.4.0

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends python3-tk xclip && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Drop root: create a non-privileged user and hand over the workdir
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV DISPLAY=:0
ENV WHISPER_MODEL=small
ENV MODEL_PATH=/models
ENV NOTES_DIR=/notes

CMD ["python3", "src/app.py"]
