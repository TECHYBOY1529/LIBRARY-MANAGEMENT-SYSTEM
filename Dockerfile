# Production Dockerfile for Campus Library Management System
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory and non-root user
WORKDIR /app
RUN useradd -m -u 1000 libraryuser

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure instance and logs directory permissions
RUN mkdir -p instance /tmp && chown -R libraryuser:libraryuser /app instance /tmp

USER libraryuser

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    APP_ENV=production

EXPOSE 5000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/healthz || exit 1

# Launch deployment automation bootstrapper
CMD ["python", "scripts/auto_deploy_start.py"]
