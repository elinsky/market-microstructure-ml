FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd --create-home appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files and set ownership
COPY --chown=appuser:appuser pyproject.toml README.md ./
COPY --chown=appuser:appuser src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir . gunicorn

# Switch to non-root user
USER appuser

# Cloud Run sets PORT env var
ENV PORT=8050

# Expose port
EXPOSE $PORT

# Run with Gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 2 --timeout 0 src.run_live:server
