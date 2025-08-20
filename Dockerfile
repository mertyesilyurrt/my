FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

# System deps (curl for downloading spaCy model if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && python -m spacy download en_core_web_sm

# Project files
COPY . .

# Default command: prepare data and execute StudyPipeline, writing outputs into the mounted /workspace
CMD ["/bin/sh", "-lc", "mkdir -p outputs data-clean/processed && python scripts/prepare_data.py --config gctg-clean.yaml && python -m jupyter nbconvert --to html --execute StudyPipeline.ipynb --output outputs/StudyPipeline.html --ExecutePreprocessor.kernel_name=python3 --ExecutePreprocessor.timeout=7200 && ls -lah outputs data-clean/processed && echo 'Open outputs/StudyPipeline.html' "]
