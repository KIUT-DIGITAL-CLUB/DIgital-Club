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
    && mkdir -p app/static/uploads/blogs

# Expose port 5051
EXPOSE 5051

# Set environment variables
ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1
#CMD ["python", "main.py"]
# Run the application with Gunicorn
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main:app"]

