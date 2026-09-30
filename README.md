# PyNav - Comprehensive GPS Navigation Software

A modular, feature-rich navigation software built with Python and PyQt6 that provides GPS tracking, route planning, mapping, and points of interest management.

![PyNav Screenshot](https://via.placeholder.com/800x500/4CAF50/FFFFFF?text=PyNav+Navigation+Software)

## Features

### 🗺️ Interactive Mapping
- **Multiple Map Sources**: OpenStreetMap, Satellite imagery, Hybrid maps, Terrain maps, OpenTopoMap, CyclOSM
- **Real-time Rendering**: Smooth tile loading with intelligent caching
- **Layer Support**: Toggle satellite, traffic, and POI overlays
- **Multi-zoom Support**: Zoom levels 1-19 with dynamic tile loading
- **Offline Capabilities**: Map tile caching for offline use

### 🛰️ Location Services
- **Multi-Source GPS**: Serial GPS devices with NMEA protocol support
- **IP Geolocation**: Automatic fallback using multiple IP location services
- **Manual Input**: Coordinate entry for precise positioning
- **Real-time Tracking**: Live location updates with accuracy indicators
- **GPS Quality Monitoring**: Satellite count, fix quality, HDOP, and accuracy tracking

### 🧭 Navigation & Routing
- **Turn-by-Turn Navigation**: Complete routing with voice guidance ready
- **Multiple Routing Engines**: OSRM (free), GraphHopper, offline routing
- **Route Optimization**: Avoid tolls, highways, or specific road types
- **Vehicle Types**: Car, motorcycle, bicycle, walking routes
- **Live Route Display**: Blue route lines with turn indicators
- **Navigation Instructions**: Detailed step-by-step directions

### 🔍 Address Search & Geocoding
- **Address Lookup**: Search addresses, landmarks, and coordinates
- **Multiple Results**: Up to 5 search results with confidence scoring
- **Reverse Geocoding**: Get addresses from map coordinates
- **POI Search**: Find nearby restaurants, gas stations, hotels, etc.
- **Search History**: Remember recent searches
- **Map Integration**: Automatic marker placement and map centering

### 📍 Points of Interest (POI)
- **Custom POI Management**: Create, edit, and organize custom locations
- **Category Organization**: Organize by restaurants, hotels, services, etc.
- **Favorites System**: Mark frequently used locations
- **Distance Calculation**: Show distance from current location
- **Import/Export**: GPX and JSON format support
- **Search & Filter**: Find POIs by name, category, or proximity

### 📊 GPS Data Monitoring
- **Live GPS Dashboard**: Real-time satellite data, fix quality, and precision
- **NMEA Data Display**: Raw GPS sentence monitoring
- **Track Recording**: Log GPS tracks to CSV and GPX formats
- **Connection Status**: Monitor GPS device connectivity and data rates
- **Multiple Device Support**: Automatic detection of GPS receivers

### 💾 Data Management
- **SQLite Database**: Persistent storage for routes, POIs, and settings
- **Tile Caching**: Intelligent map tile storage and management
- **Settings Persistence**: User preferences and configuration storage
- **Data Export**: Routes and tracks in standard formats
- **Import Capabilities**: Load existing GPS and mapping data

## Installation

### Prerequisites
- **Python 3.8+** (Python 3.11+ recommended)
- **2GB+ RAM** (4GB+ recommended for large maps)
- **1GB+ Disk Space** for map tile caching
- **Internet Connection** for map tiles and routing services

### Quick Start

#### Option 1: Automatic Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/pynav.git
cd pynav

# Run automatic setup (Linux/macOS)
chmod +x install.sh
./install.sh

# Or on Windows
install.bat
```

#### Option 2: Manual Installation
```bash
# Clone repository
git clone https://github.com/yourusername/pynav.git
cd pynav

# Create virtual environment (recommended)
python -m venv pynav-env
source pynav-env/bin/activate  # Linux/macOS
# pynav-env\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Dependencies
```
PyQt6>=6.4.0           # GUI framework
requests>=2.28.0       # HTTP requests for APIs
sqlite3                # Database (included with Python)
pynmea2>=1.18.0        # GPS NMEA parsing (optional)
pyserial>=3.5          # Serial communication for GPS (optional)
```

## Usage

### First Run Setup

1. **Launch Application**:
   ```bash
   python main.py
   ```

2. **Initial Configuration**:
   - The app will create a `.pynav` directory in your home folder
   - Default settings will be loaded automatically
   - GPS devices will be auto-detected if connected

3. **Set Location Source**:
   - Choose from GPS devices, IP location, or manual input
   - GPS provides highest accuracy when available
   - IP location works without additional hardware

### Basic Navigation

#### 1. Search for a Destination
```
1. Enter address in search box: "1600 Pennsylvania Avenue, Washington DC"
2. Press Enter or click "Search"
3. Select from search results
4. Location appears on map with marker
```

#### 2. Get Directions
```
1. After searching, click "Navigate" button
2. Route calculates from current location
3. Blue route line appears on map
4. Turn-by-turn directions show in right panel
```

#### 3. GPS Monitoring
```
1. Click "Open GPS Tracker" button
2. Monitor real-time GPS data
3. View satellite count, accuracy, and signal quality
4. Record tracks for later analysis
```

### Advanced Features

#### Route Planning
- Access via "Route Planning" tab in right panel
- Set custom start/end points and waypoints
- Save frequently used routes
- Export routes to GPX format

#### POI Management
- Add custom points of interest
- Organize by categories (restaurants, gas stations, etc.)
- Mark favorites for quick access
- Import/export POI databases

#### GPS Track Recording
- Record movement tracks to CSV/GPX files
- Monitor real-time statistics (distance, speed, duration)
- Export for analysis in other GPS software

### Configuration

#### Settings File Location
- **Linux/macOS**: `~/.pynav/settings.json`
- **Windows**: `%USERPROFILE%\.pynav\settings.json`

#### Key Settings
```json
{
  "map": {
    "default_zoom": 15,
    "tile_server": "OpenStreetMap",
    "cache_size_mb": 500
  },
  "navigation": {
    "routing_service": "OSRM",
    "vehicle_type": "car",
    "avoid_tolls": false
  },
  "location": {
    "preferred_source": "GPS",
    "high_accuracy_mode": false
  }
}
```

#### API Keys (Optional)
For enhanced features, add API keys:
```json
{
  "api": {
    "here_api_key": "your_here_api_key",
    "mapbox_api_key": "your_mapbox_api_key",
    "graphhopper_api_key": "your_graphhopper_key"
  }
}
```

## Architecture

### Core Components

#### Location Management (`navigation/core/location_manager.py`)
- Multi-source location provider system
- GPS device detection and NMEA parsing
- IP geolocation with multiple service fallbacks
- Location history and accuracy tracking

#### Map Management (`navigation/core/map_manager.py`)
- Tile downloading and caching system
- Multiple map server support
- Layer management (base maps, overlays)
- Offline tile storage and retrieval

#### Routing Engine (`navigation/core/routing_engine.py`)
- Multiple routing service integration (OSRM, GraphHopper)
- Route calculation and optimization
- Turn-by-turn instruction generation
- Navigation progress tracking

#### Geocoding Service (`navigation/core/geocoding_service.py`)
- Address-to-coordinate conversion
- Reverse geocoding capabilities
- POI search functionality
- Multiple provider support (Nominatim, HERE)

### GUI Components

#### Navigation Map Widget (`navigation/gui/map_widget.py`)
- Interactive map display with PyQt6
- Route visualization and user location tracking
- POI markers and search result display
- Real-time rendering with tile management

#### Route Planning Panel (`navigation/gui/route_panel.py`)
- Route planning interface
- Waypoint management
- Saved routes functionality
- Route options configuration

#### POI Manager (`navigation/gui/poi_manager.py`)
- POI creation and editing interface
- Category organization system
- Search and filtering capabilities
- Import/export functionality

### Data Layer

#### Navigation Database (`navigation/data/database.py`)
- SQLite database management
- Map tile caching
- Route and POI storage
- Settings persistence
- Search history tracking

## Development

### Project Structure
```
pynav/
├── main.py                          # Application entry point
├── gps_tracker_dialog.py           # GPS monitoring interface
├── requirements.txt                 # Python dependencies
├── install.sh / install.bat        # Installation scripts
├── navigation/
│   ├── __init__.py
│   ├── core/                       # Core functionality
│   │   ├── location_manager.py     # Location handling
│   │   ├── map_manager.py          # Map tiles and rendering
│   │   ├── routing_engine.py       # Route calculation
│   │   └── geocoding_service.py    # Address resolution
│   ├── gui/                        # User interface
│   │   ├── map_widget.py           # Main map display
│   │   ├── route_panel.py          # Route planning
│   │   └── poi_manager.py          # POI management
│   ├── data/                       # Data persistence
│   │   └── database.py             # Database operations
│   └── utils/                      # Utilities
│       ├── settings.py             # Configuration
│       └── logger.py               # Logging system
└── README.md                       # This file
```

### Development Setup
```bash
# Clone repository
git clone https://github.com/yourusername/pynav.git
cd pynav

# Create development environment
python -m venv dev-env
source dev-env/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8  # Development tools

# Run in development mode
python main.py --debug
```

### Testing GPS Functionality
```bash
# Test GPS device detection
python -c "from navigation.core.location_manager import LocationManager; lm = LocationManager(); print(lm.get_available_sources())"

# Test map tile download
python -c "from navigation.core.map_manager import MapManager; from navigation.data.database import NavigationDatabase; mm = MapManager(NavigationDatabase())"

# Test geocoding
python -c "from navigation.core.geocoding_service import GeocodingService; gs = GeocodingService(); gs.geocode_address('Times Square')"
```

### Adding New Features

#### New Map Source
1. Add server configuration to `TileServer.SERVERS` in `map_manager.py`
2. Update map type selector in UI
3. Handle any special authentication or tile URL formats

#### New Routing Service
1. Inherit from `RoutingService` in `routing_engine.py`
2. Implement `calculate_route()` method
3. Add service to `RoutingEngine.services`

#### New Location Provider
1. Inherit from `LocationProvider` in `location_manager.py`
2. Implement `get_location()` method
3. Add provider to `LocationManager.providers`

## Troubleshooting

### Common Issues

#### GPS Not Working
**Symptoms**: No GPS data, "GPS: Offline" status

**Solutions**:
- Check GPS device connection and power
- Verify correct COM port (Windows) or device path (Linux/macOS)
- Try different baud rates: 4800, 9600, 38400, 115200
- Ensure NMEA output is enabled on GPS device
- Check device permissions (may need sudo on Linux)

#### Map Tiles Not Loading
**Symptoms**: Gray squares instead of map tiles

**Solutions**:
- Verify internet connection
- Check firewall settings (allow Python/PyNav)
- Clear tile cache: Delete `~/.pynav/cache/` directory
- Try different map source from dropdown
- Check antivirus software blocking network access

#### Search Not Working
**Symptoms**: "Search failed" or no results

**Solutions**:
- Verify internet connection for geocoding services
- Try simpler search terms (avoid special characters)
- Check if Nominatim service is accessible
- Consider adding HERE or other API keys for backup

#### Application Crashes
**Symptoms**: Python errors, application closes unexpectedly

**Solutions**:
- Check log files in `~/.pynav/logs/`
- Verify all dependencies are installed correctly
- Try running with: `python main.py --debug`
- Check crash logs in `~/.pynav/logs/crash_*.log`

#### Performance Issues
**Symptoms**: Slow map rendering, high memory usage

**Solutions**:
- Reduce tile cache size in settings
- Disable unnecessary layers (satellite, traffic)
- Lower map refresh rate
- Close other applications to free memory
- Consider upgrading hardware for large datasets

### Log Files
Debug information is stored in:
- **Main log**: `~/.pynav/logs/navigation.log`
- **Crash reports**: `~/.pynav/logs/crash_*.log`
- **GPS data**: Available in GPS Tracker dialog

### Getting Help
1. Check this README and inline code documentation
2. Review log files for error details
3. Search existing issues on GitHub
4. Create new issue with:
   - Operating system and Python version
   - Complete error message
   - Steps to reproduce
   - Relevant log file excerpts

## Contributing

### Development Guidelines
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Add docstrings to all public methods
- Include unit tests for new features
- Update documentation for any API changes

### Code Formatting
```bash
# Format code with Black
black navigation/ main.py gps_tracker_dialog.py

# Check style with flake8
flake8 navigation/ --max-line-length=100

# Run tests
pytest tests/ -v
```

### Submitting Changes
1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes with tests and documentation
4. Ensure all tests pass and code is formatted
5. Submit pull request with detailed description

### Feature Requests
When requesting features, please include:
- Use case description
- Expected behavior
- Screenshots or mockups if applicable
- Willingness to contribute to implementation

## License

This project is licensed under the MIT License. See LICENSE file for details.

### Third-Party Acknowledgments
- **OpenStreetMap** - Map data and tiles
- **OSRM Project** - Free routing services
- **Nominatim** - Free geocoding services
- **PyQt6** - GUI framework
- **Python Community** - Core language and libraries

### Data Sources
- Map tiles: © OpenStreetMap contributors
- Satellite imagery: © Esri, DigitalGlobe, GeoEye
- Routing: © OSRM contributors
- Geocoding: © OpenStreetMap Nominatim

## Roadmap

### Version 1.1 (Planned)
- Voice-guided navigation with text-to-speech
- Weather layer integration
- Real-time traffic data
- Mobile companion app

### Version 1.2 (Future)
- 3D terrain visualization
- Advanced route optimization algorithms
- Fleet management features
- Plugin architecture for extensions

### Version 2.0 (Long-term)
- Machine learning route suggestions
- Augmented reality navigation overlay
- Multi-language interface
- Cloud synchronization and backup

## Support

- **Documentation**: This README and inline code comments
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: GitHub Discussions for questions and ideas
- **Email**: Contact maintainers for security issues

## Status

**Current Version**: 1.0.0
**Status**: Active Development
**Platform Support**: Windows, macOS, Linux
**Python Support**: 3.8, 3.9, 3.10, 3.11+

---

**PyNav Navigation Software** - Professional GPS navigation for everyone.

Built with ❤️ using Python and PyQt6.


---
*Built with AI assistance from [Claude (Anthropic)](https://claude.com/).*
