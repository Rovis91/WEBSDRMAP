# SDR Triangulation Application - Development Guide

## Overview

This development guide provides technical information for developers who want to understand the architecture of the SDR Triangulation Application and contribute to its development.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Code Structure](#code-structure)
3. [Development Environment Setup](#development-environment-setup)
4. [Coding Standards](#coding-standards)
5. [Adding New Features](#adding-new-features)
6. [Testing](#testing)
7. [Documentation](#documentation)
8. [Contributing](#contributing)

## Architecture Overview

The SDR Triangulation Application is built with a modular architecture that separates concerns and promotes reusability. The main components are:

### Core Components

1. **SDR Client**: Manages connections to KiwiSDR receivers and handles audio and waterfall data streams.
2. **Signal Processing**: Processes audio and waterfall data, detects signals, and performs triangulation.
3. **Data Export**: Exports audio, spectrum, and triangulation data to various formats.
4. **Frontend**: Web interface built with Flask and Socket.IO for real-time updates.
5. **Main Application**: Coordinates all components and manages the application lifecycle.

### Data Flow

```
KiwiSDR Receivers → SDR Client → Signal Processing → Triangulation
                                 ↓
                            Data Export
                                 ↓
                             Frontend
```

## Code Structure

The application is organized into the following directory structure:

```
sdr-triangulation/
├── src/
│   ├── __init__.py
│   ├── main.py                # Main application entry point
│   ├── sdr_client/            # SDR client components
│   │   ├── __init__.py
│   │   ├── sdr_client.py      # Main client class
│   │   ├── kiwi_connection.py # KiwiSDR connection
│   │   ├── audio_stream.py    # Audio stream management
│   │   └── waterfall_stream.py # Waterfall stream management
│   ├── signal_processing/     # Signal processing components
│   │   ├── __init__.py
│   │   ├── detection.py       # Signal detection
│   │   ├── triangulation.py   # Triangulation algorithms
│   │   ├── rssi.py            # RSSI computation
│   │   └── optimized_processing.py # Optimized algorithms
│   ├── data_export/           # Data export functionality
│   │   ├── __init__.py
│   │   └── data_export.py     # Export class
│   ├── frontend/              # Web interface
│   │   ├── __init__.py
│   │   ├── app.py             # Flask application
│   │   ├── templates/         # HTML templates
│   │   └── static/            # Static assets (JS, CSS)
│   └── utils/                 # Utility functions
│       ├── __init__.py
│       ├── logger.py          # Logging
│       ├── config_loader.py   # Configuration
│       └── performance.py     # Performance monitoring
├── config/                    # Configuration files
│   └── config.json            # Default configuration
├── docs/                      # Documentation
├── tests/                     # Unit and integration tests
└── requirements.txt           # Dependencies
```

## Development Environment Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tool (venv, virtualenv, conda)
- IDE with Python support (VSCode, PyCharm, etc.)

### Setup Steps

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

3. Install development dependencies:
   ```
   pip install -r requirements-dev.txt
   ```

4. Install pre-commit hooks:
   ```
   pre-commit install
   ```

## Coding Standards

The project follows these coding standards:

### Python Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use type hints
- Document using docstrings in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- Maximum line length: 88 characters

### JavaScript Style

- Follow [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- Use ES6+ features where applicable
- Use descriptive variable and function names

### Code Quality Tools

The project uses the following tools to maintain code quality:

- **Black**: Python code formatter
- **isort**: Import sorter
- **flake8**: Linter
- **mypy**: Static type checker
- **pytest**: Testing framework
- **pre-commit**: Pre-commit hooks

## Adding New Features

When adding new features, follow these guidelines:

### Planning

1. Create a detailed plan
2. Identify the components that need to be modified
3. Consider the impact on existing functionality
4. Design API changes carefully

### Implementation

1. Create a feature branch from `main`:
   ```
   git checkout -b feature/your-feature-name
   ```

2. Implement the feature, following these steps:
   - Add necessary classes and functions
   - Update existing code as needed
   - Document your code with docstrings
   - Add unit tests

3. Run tests to ensure everything works:
   ```
   pytest
   ```

4. Submit a pull request

## Testing

The project uses pytest for testing. The tests are organized as follows:

### Test Structure

```
tests/
├── unit/
│   ├── test_sdr_client.py
│   ├── test_triangulation.py
│   └── ...
├── integration/
│   ├── test_signal_detection.py
│   ├── test_triangulation_flow.py
│   └── ...
└── conftest.py
```

### Running Tests

- Run all tests:
  ```
  pytest
  ```

- Run unit tests only:
  ```
  pytest tests/unit
  ```

- Run integration tests only:
  ```
  pytest tests/integration
  ```

- Run with coverage:
  ```
  pytest --cov=src
  ```

### Writing Tests

When writing tests:
- Focus on testing functionality, not implementation
- Use fixtures when appropriate
- Mock external dependencies
- Aim for high code coverage
- Test edge cases and error conditions

## Documentation

Documentation is an integral part of the project. Follow these guidelines:

### Code Documentation

- Document all public classes and functions with docstrings
- Explain parameters, return values, and exceptions
- Provide examples for complex functions

### Project Documentation

Update these documentation files when making changes:
- `README.md`: Project overview
- `docs/api_documentation.md`: API reference
- `docs/user_guide.md`: User guide
- `docs/development_guide.md`: This development guide

## Contributing

### Contribution Workflow

1. Find an issue to work on or create a new one
2. Create a feature branch from `main`
3. Implement your changes
4. Write tests
5. Update documentation
6. Submit a pull request

### Pull Request Guidelines

- Keep PRs focused and small (one feature/fix per PR)
- Write a clear description of the changes
- Reference related issues
- Ensure all tests pass
- Add necessary documentation

### Code Review Process

- All code is reviewed before merging
- Address review comments
- Ensure code quality standards are met
- Final approval from a core maintainer is required

## Advanced Topics

### Async Programming

The application uses asyncio for asynchronous operations. When working with async code:
- Use `async`/`await` consistently
- Avoid blocking calls in async functions
- Be mindful of event loop performance
- Handle exceptions properly in async context

### Websocket Communication

The frontend communicates with the backend via Socket.IO:
- Events should be well-defined and documented
- Handle connection errors gracefully
- Minimize message size for performance
- Use structured message formats

### Performance Optimization

When optimizing performance:
- Profile code to identify bottlenecks
- Use NumPy for numerical operations
- Consider parallelization with ProcessPool
- Optimize critical paths first
- Measure results before and after optimization 