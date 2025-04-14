# SDR Triangulation Application - User Guide

## Overview

The SDR Triangulation Application is a comprehensive tool for detecting, monitoring, and triangulating radio signals using Software Defined Radio (SDR) receivers. This guide will help you install, configure, and use the application effectively.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Getting Started](#getting-started)
4. [Using the Web Interface](#using-the-web-interface)
5. [Signal Detection](#signal-detection)
6. [Triangulation](#triangulation)
7. [Exporting Data](#exporting-data)
8. [Advanced Features](#advanced-features)
9. [Troubleshooting](#troubleshooting)

## Installation

### Requirements

- Python 3.9 or higher
- Network access to KiwiSDR receivers
- Modern web browser

### Installation Steps

1. Clone the repository:
   ```
   git clone https://github.com/your-organization/sdr-triangulation.git
   cd sdr-triangulation
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

### Config File

The application uses a JSON configuration file for its settings. The default location is `config/config.json`. You can specify a different configuration file using the `--config` command-line option.

### Sample Configuration

```json
{
  "receivers": [
    {
      "name": "SDR1",
      "url": "wss://kiwisdr.example.com/kiwi",
      "location": {
        "latitude": 48.8566,
        "longitude": 2.3522
      }
    },
    {
      "name": "SDR2",
      "url": "wss://kiwisdr2.example.com/kiwi",
      "location": {
        "latitude": 51.5074,
        "longitude": -0.1278
      }
    }
  ],
  "signal_processing": {
    "fft_size": 1024,
    "sample_rate": 12000,
    "initial_frequency": 7100000,
    "modulation_mode": "am"
  },
  "detection": {
    "threshold_db": -80.0,
    "min_snr_db": 10.0,
    "min_duration_sec": 2.0,
    "max_inactive_sec": 5.0,
    "frequency_tolerance_hz": 100.0
  },
  "triangulation": {
    "min_receivers": 3,
    "max_distance_km": 1000,
    "confidence_threshold": 0.6
  },
  "data_export": {
    "output_dir": "exports",
    "audio_format": "wav",
    "enable_audio_export": true,
    "enable_spectrum_export": true,
    "enable_triangulation_export": true
  }
}
```

### Adding Receivers

To add a KiwiSDR receiver, you need:
- URL of the receiver's WebSocket endpoint
- Geographic coordinates (latitude and longitude)
- A descriptive name

## Getting Started

### Starting the Application

Run the application with:

```
python -m src.main
```

Options:
- `--config <path>`: Specify a configuration file
- `--log-level <level>`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--log-file <path>`: Write logs to a file
- `--web-port <port>`: Set the web interface port (default: 5000)

### Accessing the Web Interface

Open your web browser and navigate to:

```
http://localhost:5000
```

## Using the Web Interface

### Main Interface

The web interface is divided into several sections:

1. **Header**: Application title and status indicator
2. **Sidebar**: Receivers list, frequency controls, and detected signals
3. **Map**: Shows the location of receivers and triangulation results
4. **Data View**: Tabs for spectrograms, audio, triangulation results, and annotations

### Receiver Management

- **Adding Receivers**: Click "Add Receiver" in the sidebar
- **Selecting Receivers**: Check the receivers you want to use
- **Receiver Status**: Icons indicate connection status and signal strength

### Frequency Control

- **Setting Frequency**: Enter a frequency in Hz (or use kHz/MHz selector)
- **Modulation Mode**: Select AM, FM, USB, LSB, or CW
- **Bandwidth**: Adjust the receiver bandwidth

### Starting/Stopping Reception

- Click "Start Listening" to begin receiving signals
- Click "Stop" to end reception

## Signal Detection

### Signal Detection Display

Detected signals appear in the "Signals" list in the sidebar. Each signal shows:
- Frequency
- Signal strength (RSSI)
- Signal type (if identified)
- Detection time

### Signal Details

Click on a signal to:
- View detailed information
- Listen to the audio
- View the spectrogram
- Triangulate the source (if multiple receivers detect it)

## Triangulation

### Performing Triangulation

1. Select a signal from the list
2. Ensure at least 3 receivers have detected the signal
3. Click "Triangulate" in the Triangulation tab

### Understanding Results

The triangulation result includes:
- Estimated location (latitude/longitude)
- Error radius (in kilometers)
- Reliability level (HIGH, MEDIUM, LOW, VERY_LOW)
- Visualization on the map

### Triangulation Reliability

Reliability depends on:
- Number of receivers detecting the signal
- Geographic distribution of receivers
- Signal strength
- Error radius

## Exporting Data

The application can export various types of data:

### Audio Export

- Click "Export WAV" in the Audio tab
- Audio files are saved in the configured output directory

### Spectrum Export

- Click "Save" in the Spectrogram tab
- Exports a spectrogram image

### Triangulation Export

In the Triangulation tab, click:
- "JSON" for JSON format
- "CSV" for CSV format
- "KML" for Google Earth KML format

## Advanced Features

### Annotations

The Annotations tab allows you to:
- Create notes about signals
- Mark locations on the map
- Tag signals with custom labels
- Search and filter annotations

### Alert Rules

You can configure alert rules in the configuration file:

```json
"alert_rules": [
  {
    "name": "Emergency Channel Alert",
    "min_frequency": 7080000,
    "max_frequency": 7090000,
    "min_power": -70,
    "signal_type": "voice",
    "min_duration": 5.0
  }
]
```

The application will alert you when signals matching these rules are detected.

## Troubleshooting

### Connection Issues

If you cannot connect to SDR receivers:
1. Check that the receiver URL is correct
2. Verify that the receiver is online and accessible
3. Check your network connection
4. Look for firewall restrictions

### Performance Problems

If the application is slow or unresponsive:
1. Reduce the number of active receivers
2. Increase the processing intervals
3. Close other CPU-intensive applications
4. Check the system requirements

### Common Errors

- **"Receiver not found"**: The specified receiver is not in the configuration
- **"Authentication failed"**: The KiwiSDR requires authentication
- **"Connection timeout"**: The receiver is not responding
- **"Insufficient receivers for triangulation"**: You need at least 3 receivers with signal detection

For more help, check the logs (`logs/app.log`) or submit an issue on GitHub. 