# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies for OpenCV and runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
	libgl1 \
	libglib2.0-0 \
	libsm6 \
	libxext6 \
	libxrender1 \
	libgomp1 \
	libgthread-2.0-0 \
	libgtk-3-0 \
	python3-opencv \
	&& rm -rf /var/lib/apt/lists/* \
	&& apt-get clean

FROM base AS dependencies

# Copy requirements first for better Docker layer caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
	pip install -r requirements.txt

FROM dependencies AS development

# Copy source code
COPY . /app

# Install in development mode
RUN pip install -e .

# Set deployment environment stage
ENV ENVIRONMENT=deployment

# Default command shows help
ENTRYPOINT ["cen"]
CMD ["--help"]
