# Platform Testing Guide

This guide explains how to test the SDR Triangulation application on different platforms to ensure compatibility and proper deployment.

## Supported Platforms

The application has been tested on:

- **Linux**: Ubuntu 20.04+, Debian 11+
- **Windows**: Windows 10, Windows 11
- **macOS**: macOS Catalina (10.15)+

## Testing Methods

### Method 1: Native Python Installation

Testing with a native Python installation validates that the application can run directly on the platform with Python installed.

#### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- Git

#### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/your-organization/sdr-triangulation.git
   cd sdr-triangulation
   ```

2. Create and activate a virtual environment:
   - **Linux/macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows**:
     ```powershell
     python -m venv venv
     venv\Scripts\activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python -m src.main
   ```

5. Verify by accessing http://localhost:5000 in a web browser

### Method 2: Docker Deployment

Testing with Docker validates that the containerized application can run on different platforms.

#### Prerequisites
- Docker
- Docker Compose (optional but recommended)

#### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/your-organization/sdr-triangulation.git
   cd sdr-triangulation
   ```

2. Run the automated test script:
   - **Linux/macOS**:
     ```bash
     chmod +x test_deployment.sh
     ./test_deployment.sh
     ```
   - **Windows**:
     ```powershell
     .\test_deployment.ps1
     ```

3. Alternatively, manually test with Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Verify by accessing http://localhost:5000 in a web browser

## Test Scenarios

When testing on each platform, validate the following functionality:

1. **Basic Operation**:
   - Application starts without errors
   - Web interface loads correctly
   - All UI elements display properly

2. **SDR Connectivity**:
   - Application can connect to KiwiSDR receivers
   - Waterfall display updates in real-time

3. **Signal Processing**:
   - Signal detection works properly
   - Triangulation calculations perform as expected

4. **Data Export**:
   - Audio export works
   - Data export functionality works correctly

## Reporting Issues

If you encounter issues on a specific platform, please report them with:

1. Platform details (OS name and version)
2. Installation method used (native or Docker)
3. Error messages or logs
4. Steps to reproduce the issue

## Performance Considerations

- **Linux**: Generally offers the best performance for signal processing tasks
- **Windows**: May require additional CPU/memory resources for equivalent performance
- **macOS**: Performance is typically good but may vary based on hardware

## Compatibility Matrix

| Platform | Python 3.9 | Python 3.10 | Python 3.11 | Docker |
|----------|------------|-------------|-------------|--------|
| Ubuntu 20.04 | ✅ | ✅ | ✅ | ✅ |
| Ubuntu 22.04 | ✅ | ✅ | ✅ | ✅ |
| Debian 11 | ✅ | ✅ | ✅ | ✅ |
| Windows 10 | ✅ | ✅ | ✅ | ✅ |
| Windows 11 | ✅ | ✅ | ✅ | ✅ |
| macOS Catalina | ✅ | ✅ | ✅ | ✅ |
| macOS Monterey | ✅ | ✅ | ✅ | ✅ |
| macOS Ventura | ✅ | ✅ | ✅ | ✅ | 