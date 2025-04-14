# SDR Triangulation Application

A powerful software solution for signal detection, monitoring, and triangulation using Software Defined Radio (SDR) receivers.

## Overview

The SDR Triangulation Application allows you to connect to multiple KiwiSDR receivers, process signals in real-time, detect and classify signals of interest, and triangulate the position of transmitters. It provides a modern web interface for interactive signal analysis and visualization.

## Key Features

- **Multi-SDR Support**: Connect to multiple KiwiSDR receivers simultaneously
- **Real-time Signal Processing**: FFT-based signal analysis and visualization
- **Automatic Signal Detection**: Identify signals above noise threshold
- **Signal Classification**: Categorize signals based on modulation type
- **Transmitter Triangulation**: Locate signal sources using RSSI measurements
- **Interactive Map**: Visualize receivers and triangulation results
- **Data Export**: Save audio, spectrum data, and triangulation results
- **Alert System**: Get notified when signals of interest are detected
- **Annotation System**: Create and manage notes about signals and locations

## Project Completion Status

The SDR Triangulation Tool project has been successfully completed with all the main objectives met:

1. ✅ Development of tool for connecting to public KiwiSDR receivers
2. ✅ Implementation of real-time signal processing and visualization
3. ✅ Creation of signal detection and triangulation system
4. ✅ Building an interactive web interface for monitoring and analysis
5. ✅ Comprehensive documentation and deployment options

The project follows a clean, modular architecture:

``` txt
sdr-triangulation/
├── config/           # Configuration files
├── docs/             # Documentation
├── examples/         # Example scripts
├── exports/          # Export directory
├── logs/             # Log files
├── src/              # Source code
│   ├── data_export/  # Data export module
│   ├── frontend/     # Web interface
│   ├── sdr_client/   # SDR connection handling
│   ├── signal_processing/ # Signal processing algorithms
│   └── utils/        # Utility functions
└── tests/            # Unit and integration tests
```

## Hardware Setup Guide

### SDR Antenna Setup

To connect a physical SDR antenna to this project:

1. **Hardware Requirements**:
   - An RTL-SDR receiver (RTL2832U chipset) or KiwiSDR hardware
   - Appropriate antenna for your frequency range of interest
   - USB connection cable (for RTL-SDR)
   - Internet connection (for KiwiSDR access)

2. **Setting up RTL-SDR**:
   - Connect your antenna to the SMA or F-type connector on the RTL-SDR dongle
   - For frequencies below 30 MHz (HF band), use a long wire antenna (10-20m) with an upconverter
   - For VHF/UHF reception (30 MHz - 1 GHz), use a dipole or discone antenna
   - Connect the RTL-SDR to a USB port on your computer
   - Install required drivers (on Windows, use Zadig to install the WinUSB driver)

3. **Setting up KiwiSDR**:
   - If using a KiwiSDR device directly:
     - Connect a long wire antenna (minimum 10m) to the antenna input
     - Connect the KiwiSDR to your network via Ethernet
     - Configure the KiwiSDR with an IP address through the web interface
   - If using public KiwiSDR stations:
     - Add public KiwiSDR URLs to your configuration file
     - Example: `http://kiwisdr.example.com:8073`

4. **Configuration**:
   - Update the `config/config.json` file with your SDR details:

   ```json
   {
     "receivers": [
       {
         "name": "Local RTL-SDR",
         "type": "rtlsdr",
         "device_index": 0,
         "sample_rate": 2048000,
         "gain": 20,
         "frequency": 7100000,
         "location": {
           "latitude": 48.8566,
           "longitude": 2.3522
         }
       },
       {
         "name": "Remote KiwiSDR",
         "type": "kiwisdr",
         "url": "http://kiwisdr.example.com:8073",
         "frequency": 7100000,
         "mode": "AM",
         "location": {
           "latitude": 45.7640,
           "longitude": 4.8357
         }
       }
     ],
     "processing": {
       "detection_threshold": -80,
       "min_snr": 10,
       "fft_size": 1024
     }
   }
   ```

5. **Antenna Placement Tips**:
   - Place antennas away from electronic devices to minimize noise
   - For long wire antennas, mount as high as possible and away from buildings
   - Orient dipole antennas appropriately for the frequencies of interest
   - Consider using a bias tee for powered antennas (if supported by your SDR)

6. **Testing Reception**:
   - Start with a known strong signal (like a local AM/FM station)
   - Use the application's spectrum display to verify signal reception
   - Adjust antenna positioning and gain settings as needed

## Documentation

Comprehensive documentation is available in the `docs` directory:

- [User Guide](docs/user_guide.md): Installation, configuration, and usage instructions
- [API Documentation](docs/api_documentation.md): Detailed information about the codebase
- [Development Guide](docs/development_guide.md): Architecture overview and contribution guidelines

## Quick Start

### Requirements

- Python 3.9 or higher
- Network access to KiwiSDR receivers
- Modern web browser

### Installation

1. Clone the repository:

   ``` bash
   git clone https://github.com/Rovis91/sdr-triangulation.git
   cd sdr-triangulation
   ```

2. Create and activate a virtual environment:

   ``` bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:

   ``` bash
   pip install -r requirements.txt
   ```

4. Configure your receivers in `config/config.json`

5. Run the application:

   ``` bash
   python -m src.main
   ```

6. Open your browser and navigate to `http://localhost:5000`

### Docker Deployment

You can also run the application using Docker:

1. Build and start with Docker Compose:

   ``` bash
   docker-compose up -d
   ```

2. Open your browser and navigate to `http://localhost:5000`

For detailed Docker deployment instructions, see [Docker Deployment Guide](docs/docker_deployment.md).

## Troubleshooting Common Issues

### Website Inactive or Tabs Not Clickable

- Ensure the backend service is running correctly by checking the logs
- Verify that all required WebSocket connections are established
- Try clearing your browser cache or using an incognito/private window
- Check if your firewall is blocking WebSocket connections on port 5000

### Connection Issues

- Verify your configuration file has correct KiwiSDR URLs
- Ensure you have internet access if using remote KiwiSDR stations
- Check if the selected KiwiSDR stations are online and not at capacity
- If using RTL-SDR, verify device drivers are properly installed

### No Signal Detected

- Verify your antenna connection is secure
- Increase the gain setting in your configuration
- Try a different frequency where strong signals are known to exist
- Check your antenna placement and orientation

## Next Steps and Future Enhancements

While the project is complete according to the initial requirements, several potential enhancements could be considered:

1. **Additional Signal Types**: Support for more digital modes and modulation types
2. **Machine Learning Integration**: Automated signal classification
3. **Advanced Triangulation**: More sophisticated algorithms for increased accuracy
4. **Remote API**: REST API for integration with other systems
5. **Mobile Compatibility**: Optimized mobile interface for field use

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- The KiwiSDR project for making SDR accessible over the web
- All contributors who have helped improve this software
- The open-source community for the excellent libraries used in this project
