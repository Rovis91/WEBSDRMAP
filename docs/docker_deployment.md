# Docker Deployment Guide

This guide explains how to deploy the SDR Triangulation application using Docker, making it easy to run in different environments without complex setup.

## Prerequisites

- Docker installed on your system ([Docker Installation Guide](https://docs.docker.com/get-docker/))
- Docker Compose installed (included with Docker Desktop for Windows and Mac, separate install for Linux)
- Basic familiarity with Docker concepts

## Quick Start

The simplest way to deploy the application is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/your-organization/sdr-triangulation.git
cd sdr-triangulation

# Start the application
docker-compose up -d
```

The application will be available at http://localhost:5000

## Configuration

### Using Configuration Files

Configuration files are mounted from your local `config/` directory into the container. You can modify these files without rebuilding the Docker image:

1. Edit the configuration files in `./config/`
2. Restart the container: `docker-compose restart`

### Using Environment Variables

You can also configure the application using environment variables in the `docker-compose.yml` file:

```yaml
environment:
  - DEBUG=0
  - LOG_LEVEL=INFO
  - KIWISDR_URL=wss://kiwisdr.example.com:8073/
```

## Data Persistence

The Docker Compose setup includes volume mounts for:

- `./config`: Configuration files
- `./exports`: Exported data (audio recordings, spectrograms, etc.)
- `./logs`: Application logs

These directories will persist data between container restarts.

## Building the Docker Image

If you want to build the Docker image manually:

```bash
# Build the image
docker build -t sdr-triangulation .

# Run the container
docker run -p 5000:5000 -v $(pwd)/config:/app/config sdr-triangulation
```

## Advanced Configuration

### Custom Ports

To use a different port, modify the `docker-compose.yml` file:

```yaml
ports:
  - "8080:5000"  # Map port 8080 on host to port 5000 in container
```

### Resource Limits

You can set resource limits in the `docker-compose.yml` file:

```yaml
services:
  sdr-triangulation:
    # Other configuration...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## Troubleshooting

### Container Fails to Start

Check the logs:

```bash
docker-compose logs
```

### Performance Issues

1. Increase the allocated resources in Docker Desktop settings
2. Modify the resource limits in `docker-compose.yml`

### Network Connectivity

Ensure the host system has network access to the KiwiSDR receivers you're trying to connect to. 