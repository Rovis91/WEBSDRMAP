FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt .
COPY requirements-dev.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs exports

# Expose the port the app runs on
EXPOSE 5000

# Create a non-root user
RUN useradd -m sdrtuser
RUN chown -R sdrtuser:sdrtuser /app
USER sdrtuser

# Command to run the application
CMD ["python", "-m", "src.main", "--host", "0.0.0.0", "--port", "5000"] 