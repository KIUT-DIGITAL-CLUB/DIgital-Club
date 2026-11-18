# Use Python 3.13 as base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Pillow, CairoSVG, and fonts
RUN apt-get update && apt-get install -y \
    gcc \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fontconfig \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Install Python dependencies
RUN uv pip install --system -r pyproject.toml

# Install production WSGI server
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p instance \
    && mkdir -p app/static/uploads/profiles \
    && mkdir -p app/static/uploads/gallery \
    && mkdir -p app/static/uploads/digital_ids \
    && mkdir -p app/static/uploads/blogs \
    && mkdir -p app/static/uploads/competitions \
    && mkdir -p app/static/uploads/elections/passports \
    && mkdir -p app/static/uploads/quiz_resources

# Stash a copy of the bundled uploads. When a persistent volume is mounted at
# /app/app/static/uploads it shadows the image's copy, so the start script seeds
# the volume from here on first boot (see scripts/railway_start.sh).
RUN cp -r app/static/uploads /app/seed_uploads \
    && chmod +x scripts/railway_start.sh

# Expose port 5051
EXPOSE 5051

# Set environment variables
ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1

# Seed the uploads volume (if any), then run gunicorn.
# Workers override this with their own start command, e.g.:
#   python scripts/rq_worker.py
CMD ["sh", "scripts/railway_start.sh"]
# For development/debugging, override the command with: python main.py

