# SDR Triangulation Application - API Documentation

## Overview

The SDR Triangulation Application is a comprehensive solution for signal detection, monitoring, and triangulation using Software Defined Radio (SDR) receivers. This document provides detailed information about the main components, classes, and functions of the application.

## Table of Contents

1. [Main Application](#main-application)
2. [SDR Client](#sdr-client)
3. [Signal Processing](#signal-processing)
   - [Triangulation](#triangulation)
   - [Signal Detection](#signal-detection)
   - [RSSI Computation](#rssi-computation)
4. [Data Export](#data-export)
5. [Frontend](#frontend)
6. [Utilities](#utilities)

## Main Application

### `src/main.py`

The entry point of the application, which initializes and coordinates all components.

#### Classes

##### `SDRTriangulationApp`

The main application class that coordinates all components and manages application resources.

```python
class SDRTriangulationApp:
    def __init__(self, config_path: Optional[str] = None)
    async def initialize(self) -> bool
    async def _add_receiver(self, receiver_config: Dict[str, Any]) -> bool
    async def connect_receivers(self) -> Dict[str, bool]
    async def _connect_receiver(self, name: str, kiwi: KiwiConnection) -> bool
    async def start_streams(self) -> Dict[str, Dict[str, bool]]
    async def start(self) -> bool
    async def _main_loop(self) -> None
    async def _check_connections(self) -> None
    async def _process_waterfall_data(self) -> None
    def _perform_triangulation(self, rssi_by_freq, timestamp) -> None
    async def stop(self) -> bool
    async def cleanup(self) -> None
    def get_status(self) -> Dict[str, Any]
    def get_performance_stats(self) -> Dict[str, Any]
```

**Example Usage:**

```python
# Initialize and start the application
import asyncio
from src.main import SDRTriangulationApp

async def main():
    # Create app instance with custom config
    app = SDRTriangulationApp(config_path='config/my_config.json')
    
    # Initialize app components
    if await app.initialize():
        # Start the application
        if await app.start():
            # Application is now running
            print("Application started successfully")
            
            # Wait for some time
            await asyncio.sleep(3600)  # Run for 1 hour
            
            # Stop the application
            await app.stop()
    
    # Show performance statistics
    stats = app.get_performance_stats()
    print(f"CPU usage: {stats['cpu_usage']}%")

# Run the application
asyncio.run(main())
```

#### Functions

##### `main()`

The entry point function that parses command-line arguments and starts the application.

**Example Usage:**

```python
# Running from command line
$ python -m src.main --config config/my_config.json --log-level DEBUG
```

## SDR Client

### `src/sdr_client/sdr_client.py`

Manages the connections to KiwiSDR receivers and coordinates the audio and waterfall streams.

#### Classes

##### `SDRClientPriority`

Enum defining priority levels for SDR connections.

```python
class SDRClientPriority(Enum):
    CRITICAL = 0  # Highest priority (e.g., emergency monitoring)
    HIGH = 1      # High priority (e.g., signal detection)
    NORMAL = 2    # Normal priority (e.g., regular listening)
    LOW = 3       # Low priority (e.g., background scanning)
    BACKGROUND = 4  # Lowest priority (e.g., mapping)
```

##### `SDRResource`

Represents an SDR resource with its priority.

```python
class SDRResource:
    def __init__(self, name: str, priority: SDRClientPriority = SDRClientPriority.NORMAL)
    def __lt__(self, other)
    def update_access_time(self)
```

##### `SDRClient`

The main client class for managing multiple SDR connections.

```python
class SDRClient:
    def __init__(self, max_connections: int = 5)
    async def add_receiver(self, url: str, name: str = None, 
                          location: Dict[str, float] = None,
                          priority: SDRClientPriority = SDRClientPriority.NORMAL) -> bool
    async def remove_receiver(self, name: str) -> bool
    async def connect_receiver(self, name: str, frequency: int = None, 
                              mode: KiwiSDRMode = None) -> bool
    async def disconnect_receiver(self, name: str) -> bool
    async def start_audio_stream(self, name: str, callback: Callable[[Any], None]) -> bool
    async def stop_audio_stream(self, name: str) -> bool
    async def start_waterfall_stream(self, name: str, callback: Callable[[Any], None]) -> bool
    async def stop_waterfall_stream(self, name: str) -> bool
    async def start(self)
    async def stop(self)
    def get_connection_status(self) -> Dict[str, Dict[str, Any]]
    def set_priority(self, name: str, priority: SDRClientPriority) -> bool
    async def _prioritize_connections(self)
    def _should_prioritize(self, name: str) -> Tuple[bool, Optional[str]]
    async def _connection_management_loop(self)
```

**Example Usage:**

```python
# Using SDRClient to connect to and manage receivers
import asyncio
from src.sdr_client.sdr_client import SDRClient, SDRClientPriority
from src.sdr_client.kiwi_connection import KiwiSDRMode

async def process_audio_data(data):
    # Process received audio data
    print(f"Received {len(data)} audio samples")

async def process_waterfall_data(data):
    # Process received waterfall data
    print(f"Received waterfall data with shape {data.shape}")

async def main():
    # Create client with maximum 3 simultaneous connections
    client = SDRClient(max_connections=3)
    
    # Add receivers
    await client.add_receiver(
        url="wss://kiwisdr.example.com/kiwi",
        name="Europe SDR",
        location={"latitude": 48.8566, "longitude": 2.3522},
        priority=SDRClientPriority.HIGH
    )
    
    await client.add_receiver(
        url="wss://kiwisdr2.example.com/kiwi",
        name="America SDR",
        location={"latitude": 40.7128, "longitude": -74.0060},
        priority=SDRClientPriority.NORMAL
    )
    
    # Start the client
    await client.start()
    
    # Connect to a receiver
    await client.connect_receiver(
        name="Europe SDR", 
        frequency=7100000,  # 7.1 MHz
        mode=KiwiSDRMode.AM
    )
    
    # Start audio and waterfall streams
    await client.start_audio_stream("Europe SDR", process_audio_data)
    await client.start_waterfall_stream("Europe SDR", process_waterfall_data)
    
    # Wait for some time
    await asyncio.sleep(60)
    
    # Stop streams
    await client.stop_audio_stream("Europe SDR")
    await client.stop_waterfall_stream("Europe SDR")
    
    # Disconnect and stop client
    await client.disconnect_receiver("Europe SDR")
    await client.stop()

# Run the client
asyncio.run(main())
```

### `src/sdr_client/kiwi_connection.py`

Manages the WebSocket connection to a KiwiSDR receiver.

#### Classes

##### `KiwiSDRMode`

Enum defining available modulation modes.

##### `KiwiConnectionState`

Enum defining the possible states of a connection.

##### `KiwiConnection`

Manages the connection to a single KiwiSDR receiver.

```python
class KiwiConnection:
    def __init__(self, url: str, name: str, location: Dict[str, float] = None)
    async def connect(self) -> bool
    async def disconnect(self) -> bool
    async def authenticate(self) -> bool
    async def set_frequency(self, frequency: int) -> bool
    async def set_mode(self, mode: KiwiSDRMode) -> bool
    async def set_bandwidth(self, bandwidth: int) -> bool
    def is_healthy(self) -> bool
    async def reconnect(self) -> bool
    def get_status(self) -> Dict[str, Any]
```

**Example Usage:**

```python
# Using KiwiConnection directly
import asyncio
from src.sdr_client.kiwi_connection import KiwiConnection, KiwiSDRMode

async def main():
    # Create connection
    kiwi = KiwiConnection(
        url="wss://kiwisdr.example.com/kiwi",
        name="Test Receiver",
        location={"latitude": 48.8566, "longitude": 2.3522}
    )
    
    # Connect and authenticate
    if await kiwi.connect():
        if await kiwi.authenticate():
            print("Successfully connected and authenticated")
            
            # Configure the receiver
            await kiwi.set_frequency(7100000)  # 7.1 MHz
            await kiwi.set_mode(KiwiSDRMode.USB)
            await kiwi.set_bandwidth(2400)     # 2.4 kHz
            
            # Check if connection is healthy
            if kiwi.is_healthy():
                print("Connection is healthy")
                
                # Show status
                status = kiwi.get_status()
                print(f"Frequency: {status['frequency']} Hz")
                print(f"Mode: {status['mode']}")
                
            # Disconnect when done
            await kiwi.disconnect()
            
# Run the example
asyncio.run(main())
```

### `src/sdr_client/audio_stream.py`

Manages the audio streams from the KiwiSDR receivers.

#### Classes

##### `AudioStream`

Handles an audio stream from a KiwiSDR receiver.

```python
class AudioStream:
    def __init__(self, kiwi_connection: KiwiConnection)
    async def start(self) -> bool
    async def stop(self) -> bool
    def get_recent_audio(self, seconds: float = 5.0) -> Optional[np.ndarray]
    def get_status(self) -> Dict[str, Any]
```

##### `AudioStreamManager`

Manages multiple audio streams.

```python
class AudioStreamManager:
    def __init__(self)
    async def add_stream(self, kiwi_connection: KiwiConnection) -> bool
    async def remove_stream(self, name: str) -> bool
    def get_stream(self, name: str) -> Optional[AudioStream]
    def get_all_streams(self) -> Dict[str, AudioStream]
```

### `src/sdr_client/waterfall_stream.py`

Manages the waterfall streams from the KiwiSDR receivers.

#### Classes

##### `WaterfallStream`

Handles a waterfall stream from a KiwiSDR receiver.

```python
class WaterfallStream:
    def __init__(self, kiwi_connection: KiwiConnection)
    async def start(self) -> bool
    async def stop(self) -> bool
    def get_latest_spectrum(self) -> Optional[np.ndarray]
    def get_frequency_range(self) -> Optional[np.ndarray]
    def get_status(self) -> Dict[str, Any]
```

##### `WaterfallStreamManager`

Manages multiple waterfall streams.

```python
class WaterfallStreamManager:
    def __init__(self)
    async def add_stream(self, kiwi_connection: KiwiConnection) -> bool
    async def remove_stream(self, name: str) -> bool
    def get_stream(self, name: str) -> Optional[WaterfallStream]
    def get_all_streams(self) -> Dict[str, WaterfallStream]
```

## Signal Processing

### `src/signal_processing/triangulation.py`

Implements the triangulation of signal sources based on RSSI measurements.

#### Classes

##### `Location`

Named tuple representing a geographic location.

```python
class Location(NamedTuple):
    latitude: float
    longitude: float
    altitude: float = 0.0
    def __str__(self) -> str
```

##### `ReliabilityLevel`

Enum defining reliability levels for triangulation results.

```python
class ReliabilityLevel(Enum):
    HIGH = "high"         # High reliability
    MEDIUM = "medium"     # Medium reliability
    LOW = "low"           # Low reliability
    VERY_LOW = "very_low" # Very low reliability
```

##### `TriangulationResult`

Data class containing the result of a triangulation.

```python
@dataclass
class TriangulationResult:
    estimated_location: Location
    error_radius: float
    reliability: ReliabilityLevel
    receiver_locations: Dict[str, Location]
    rssi_values: Dict[str, float]
    frequency: float
    timestamp: float
    def __str__(self) -> str
```

##### `GeoUtils`

Utility class for geographic calculations.

```python
class GeoUtils:
    EARTH_RADIUS = 6371.0  # Earth's radius in kilometers
    @staticmethod
    def haversine_distance(loc1: Location, loc2: Location) -> float
    @staticmethod
    def destination_point(start: Location, bearing: float, distance: float) -> Location
    @staticmethod
    def midpoint(locations: List[Location]) -> Location
```

**Example Usage:**

```python
# Using GeoUtils for geographic calculations
from src.signal_processing.triangulation import Location, GeoUtils

# Define two locations
paris = Location(latitude=48.8566, longitude=2.3522)
london = Location(latitude=51.5074, longitude=-0.1278)

# Calculate distance between two points
distance_km = GeoUtils.haversine_distance(paris, london)
print(f"Distance between Paris and London: {distance_km:.2f} km")

# Calculate destination point from Paris, heading east for 100 km
bearing = 90.0  # East
distance = 100.0  # km
destination = GeoUtils.destination_point(paris, bearing, distance)
print(f"Destination: {destination}")

# Calculate midpoint between multiple locations
new_york = Location(latitude=40.7128, longitude=-74.0060)
tokyo = Location(latitude=35.6762, longitude=139.6503)
locations = [paris, london, new_york, tokyo]
midpoint = GeoUtils.midpoint(locations)
print(f"Midpoint of all locations: {midpoint}")
```

##### `Triangulator`

Main class for triangulating signal sources.

```python
class Triangulator:
    def __init__(self, propagation_model: Optional[PropagationModel] = None)
    def add_receiver(self, name: str, location: Location) -> None
    def remove_receiver(self, name: str) -> bool
    def triangulate_signal(self, rssi_values: Dict[str, float],
                          frequency: float,
                          timestamp: Optional[float] = None) -> Optional[TriangulationResult]
    def _estimate_distances(self, rssi_values: Dict[str, float],
                          frequency: float) -> Dict[str, float]
    def _triangulate_by_estimated_circles(self, locations: Dict[str, Location],
                                        distances: Dict[str, float],
                                        frequency: float,
                                        timestamp: float) -> Optional[TriangulationResult]
    def _calculate_circle_intersections(self, center1: Location, 
                                      center2: Location, 
                                      radius1: float, 
                                      radius2: float) -> List[Location]
    def _calculate_bearing(self, start: Location, end: Location) -> float
    def _weighted_centroid_triangulation(self, locations: Dict[str, Location],
                                      rssi_values: Dict[str, float],
                                      frequency: float,
                                      timestamp: float) -> TriangulationResult
    def _determine_reliability(self, num_receivers: int, error_radius: float) -> ReliabilityLevel
```

**Example Usage:**

```python
# Using Triangulator to estimate signal source location
import time
from src.signal_processing.triangulation import Triangulator, Location
from src.signal_processing.rssi import PropagationModel

# Create a triangulator with default propagation model
triangulator = Triangulator()

# Add receiver locations
triangulator.add_receiver("SDR1", Location(48.8566, 2.3522))   # Paris
triangulator.add_receiver("SDR2", Location(51.5074, -0.1278))  # London
triangulator.add_receiver("SDR3", Location(52.5200, 13.4050))  # Berlin

# RSSI values from each receiver (in dBm)
rssi_values = {
    "SDR1": -65.0,
    "SDR2": -75.0,
    "SDR3": -70.0
}

# Triangulate the signal
frequency = 7100000  # 7.1 MHz
timestamp = time.time()
result = triangulator.triangulate_signal(rssi_values, frequency, timestamp)

if result:
    print(f"Estimated transmitter location: {result.estimated_location}")
    print(f"Error radius: {result.error_radius:.2f} km")
    print(f"Reliability: {result.reliability.name}")
else:
    print("Triangulation failed")
```

##### `TriangulationManager`

Manages triangulations and stores history.

```python
class TriangulationManager:
    def __init__(self, triangulator: Optional[Triangulator] = None)
    def triangulate(self, rssi_values: Dict[str, float],
                   frequency: float,
                   timestamp: Optional[float] = None) -> Optional[TriangulationResult]
    def get_latest_result(self, frequency: float) -> Optional[TriangulationResult]
    def get_history(self, frequency: float, 
                   max_age: Optional[float] = None) -> List[TriangulationResult]
    def get_average_location(self, frequency: float,
                           max_age: Optional[float] = None) -> Optional[Location]
    def clear_history(self, frequency: Optional[float] = None) -> None
    def get_all_frequencies(self) -> List[float]
    def add_receiver(self, name: str, location: Location) -> None
    def remove_receiver(self, name: str) -> bool
    def get_receivers(self) -> Dict[str, Location]
```

### `src/signal_processing/detection.py`

Implements signal detection from spectrum data.

#### Classes

##### `SignalType`

Enum defining types of signals.

##### `SignalDetection`

Data class containing information about a detected signal.

##### `SignalDetector`

Detects signals from spectrum data.

```python
class SignalDetector:
    def __init__(self, threshold_db: float = -80.0, 
                min_snr_db: float = 10.0,
                min_duration_sec: float = 2.0,
                max_inactive_sec: float = 5.0,
                frequency_tolerance_hz: float = 100.0)
    def detect_from_spectrum(self, spectrum: np.ndarray, 
                           frequencies: np.ndarray, 
                           timestamp: float) -> List[SignalDetection]
    def update_active_signals(self, spectrum: np.ndarray, 
                            frequencies: np.ndarray, 
                            timestamp: float) -> List[SignalDetection]
```

##### `AlertRule`

Defines a rule for triggering alerts.

##### `AlertManager`

Manages alert rules and checks signals against them.

```python
class AlertManager:
    def __init__(self)
    def add_rule(self, name: str, 
                min_frequency: Optional[float] = None, 
                max_frequency: Optional[float] = None,
                min_power: Optional[float] = None,
                signal_type: Optional[SignalType] = None,
                min_duration: Optional[float] = None) -> None
    def remove_rule(self, name: str) -> bool
    def check_signals(self, signals: List[SignalDetection]) -> List[Dict[str, Any]]
```

### `src/signal_processing/rssi.py`

Implements RSSI (Received Signal Strength Indicator) computation.

#### Classes

##### `RSSIMethod`

Enum defining methods for computing RSSI.

##### `PropagationModel`

Models signal propagation for different frequencies.

```python
class PropagationModel:
    def __init__(self)
    def estimate_signal_strength(self, frequency: float, 
                               distance: float, 
                               transmitter_power: float = 100.0) -> float
    def estimate_distance(self, frequency: float, 
                        rssi: float, 
                        transmitter_power: float = 100.0) -> float
```

##### `RSSIComputer`

Computes RSSI from spectrum data.

```python
class RSSIComputer:
    def __init__(self, method: RSSIMethod = RSSIMethod.MAX, 
                window_size: int = 10,
                reference_level: float = -100.0)
    def compute_rssi(self, spectrum: np.ndarray, 
                    frequencies: np.ndarray, 
                    center_frequency: float, 
                    bandwidth: Optional[float] = None) -> float
```

### `src/signal_processing/optimized_processing.py`

Implements optimized signal processing algorithms.

#### Classes

##### `OptimizedSignalProcessor`

Performs optimized signal processing using NumPy and SciPy.

```python
class OptimizedSignalProcessor:
    def __init__(self, sample_rate: int = 12000, fft_size: int = 1024)
    def process_audio(self, audio_data: np.ndarray) -> np.ndarray
    def process_spectrum(self, spectrum_data: np.ndarray) -> np.ndarray
    def compute_fft(self, audio_data: np.ndarray) -> np.ndarray
    def compute_spectrogram(self, audio_data: np.ndarray) -> np.ndarray
```

## Data Export

### `src/data_export/data_export.py`

Exports data (audio, spectrum, triangulation) to files.

#### Classes

##### `DataExporter`

Exports various types of data to files.

```python
class DataExporter:
    def __init__(self)
    def configure(self, output_dir: str = "exports", 
                 audio_format: str = "wav",
                 enable_audio_export: bool = True, 
                 enable_spectrum_export: bool = True,
                 enable_triangulation_export: bool = True) -> None
    def export_audio(self, audio_data: np.ndarray, 
                    frequency: float, 
                    receiver_name: str,
                    sample_rate: int = 12000) -> str
    def export_spectrum(self, spectrum_data: np.ndarray, 
                       frequencies: np.ndarray, 
                       timestamp: float, 
                       receiver_name: str) -> str
    def export_triangulation(self, triangulation_result: TriangulationResult) -> str
    def export_signal_detection(self, signal: SignalDetection, 
                              receiver_name: str) -> str
```

## Frontend

### `src/frontend/app.py`

Implements the Flask web server for the frontend.

#### Functions

##### `index()`

Returns the main application page.

##### `status()`

Returns the current application status.

##### `config()`

Gets or updates the application configuration.

##### `signals()`

Returns detected signals.

##### `triangulations()`

Returns triangulation results.

##### Socket.IO Event Handlers

```python
@socketio.on('connect')
def handle_connect() -> None

@socketio.on('disconnect')
def handle_disconnect() -> None

@socketio.on('set_frequency')
def handle_set_frequency(data) -> Dict[str, Any]

@socketio.on('start_listening')
def handle_start_listening(data) -> Dict[str, Any]

@socketio.on('set_mode')
def handle_set_mode(data) -> Dict[str, Any]

@socketio.on('save_annotation')
def handle_save_annotation(data) -> Dict[str, Any]

@socketio.on('get_annotations')
def handle_get_annotations() -> Dict[str, Any]

@socketio.on('delete_annotation')
def handle_delete_annotation(data) -> Dict[str, Any]

@socketio.on('map_click')
def handle_map_click(data) -> Dict[str, Any]

@socketio.on('signal_select')
def handle_signal_select(data) -> Dict[str, Any]

@socketio.on('frequency_select')
def handle_frequency_select(data) -> Dict[str, Any]

@socketio.on('receiver_select')
def handle_receiver_select(data) -> Dict[str, Any]
```

## Utilities

### `src/utils/logger.py`

Configures and provides logging facilities.

#### Functions

##### `configure_logger(log_level: int = logging.INFO, log_file: Optional[str] = None) -> None`

Configures the global logger.

##### `get_logger(name: str) -> logging.Logger`

Gets a logger instance with the specified name.

**Example Usage:**

```python
# Setting up logging in your module
from src.utils.logger import configure_logger, get_logger
import logging

# Configure logging at application startup
configure_logger(
    log_level=logging.DEBUG,
    log_file="logs/app.log"
)

# Get a logger for your module
logger = get_logger(__name__)

# Use the logger
logger.debug("This is a debug message")
logger.info("Application started")
logger.warning("Configuration file not found, using defaults")
logger.error("Failed to connect to receiver")
logger.critical("Unrecoverable error, shutting down")
```

### `src/utils/config_loader.py`

Loads and validates configuration files.

#### Functions

##### `load_config(config_path: Optional[str] = None) -> Dict[str, Any]`

Loads a configuration file.

**Example Usage:**

```python
# Loading configuration
from src.utils.config_loader import load_config

# Load default configuration
config = load_config()

# Or load specific configuration file
config = load_config("config/production.json")

# Access configuration values
receivers = config.get("receivers", [])
for receiver in receivers:
    print(f"Receiver: {receiver['name']} at {receiver['url']}")

# Access nested configuration with defaults
threshold = config.get("detection", {}).get("threshold_db", -80.0)
print(f"Signal detection threshold: {threshold} dB")
```

### `src/utils/performance.py`

Provides performance monitoring and optimization facilities.

#### Decorators

##### `@timeit`

Decorator to measure execution time of functions.

**Example Usage:**

```python
# Using the timeit decorator to measure function performance
from src.utils.performance import timeit
import time

# Apply decorator to a function
@timeit
def process_data(data_size):
    """Process a large amount of data."""
    # Simulate processing
    time.sleep(0.1)
    result = [i * i for i in range(data_size)]
    return result

# The function execution time will be logged automatically
result = process_data(10000)
# Output: "process_data took 0.1234 seconds"
``` 