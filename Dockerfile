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

CMD ["python3", "src/app.py"]
