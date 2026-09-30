#!/usr/bin/env python3
"""
Setup script for PyNav - Navigation Software
Handles installation, dependency checking, and initial configuration
"""

import sys
import subprocess
import platform
import os
from pathlib import Path

# Required Python version
MIN_PYTHON_VERSION = (3, 8)
RECOMMENDED_PYTHON_VERSION = (3, 11)

# Required packages with version constraints
REQUIRED_PACKAGES = {
    # GUI Framework
    'PyQt6': '>=6.4.0',
    'PyQt6-Qt6': '>=6.4.0',
    
    # HTTP requests and networking
    'requests': '>=2.28.0',
    'urllib3': '>=1.26.0',
    
    # GPS and location handling
    'pynmea2': '>=1.19.0',
    'pyserial': '>=3.5',
    
    # Database
    'sqlite3': None,  # Built into Python
    
    # Math and calculations
    'numpy': '>=1.21.0',
    'math': None,  # Built into Python
    'json': None,  # Built into Python
    
    # System utilities
    'psutil': '>=5.9.0',  # For memory monitoring
    'platform': None,  # Built into Python
    'glob': None,  # Built into Python
    'pathlib': None,  # Built into Python
}

# Optional packages for enhanced functionality
OPTIONAL_PACKAGES = {
    'geopy': '>=2.3.0',  # Enhanced distance calculations
    'shapely': '>=2.0.0',  # Geometric operations
    'folium': '>=0.14.0',  # Alternative map rendering
    'gpxpy': '>=1.5.0',  # GPX file support
    'pillow': '>=9.0.0',  # Image processing
    'matplotlib': '>=3.5.0',  # Plotting and visualization
    'scipy': '>=1.9.0',  # Scientific computing
    'networkx': '>=2.8',  # Network analysis for routing
}

# System-specific packages
SYSTEM_PACKAGES = {
    'Windows': {
        'pywin32': '>=305',  # Windows-specific functionality
    },
    'Darwin': {  # macOS
        'pyobjc': '>=8.0',  # macOS-specific functionality (optional)
    },
    'Linux': {
        'python3-dev': None,  # Development headers (system package)
    }
}

def check_python_version():
    """Check if Python version meets requirements."""
    current_version = sys.version_info[:2]
    
    print(f"Python version: {'.'.join(map(str, current_version))}")
    
    if current_version < MIN_PYTHON_VERSION:
        print(f"❌ Python {'.'.join(map(str, MIN_PYTHON_VERSION))} or higher is required!")
        print(f"   Current version: {'.'.join(map(str, current_version))}")
        return False
    
    if current_version < RECOMMENDED_PYTHON_VERSION:
        print(f"⚠️  Python {'.'.join(map(str, RECOMMENDED_PYTHON_VERSION))} is recommended for best performance")
    else:
        print("✅ Python version is compatible")
    
    return True

def install_package(package_name, version_spec=None, optional=False):
    """Install a package using pip."""
    try:
        if version_spec:
            package_spec = f"{package_name}{version_spec}"
        else:
            package_spec = package_name
        
        print(f"Installing {package_spec}...")
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', package_spec
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ {package_name} installed successfully")
            return True
        else:
            print(f"❌ Failed to install {package_name}")
            if not optional:
                print(f"   Error: {result.stderr.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏱️  Installation of {package_name} timed out")
        return False
    except Exception as e:
        print(f"❌ Error installing {package_name}: {e}")
        return False

def check_package_installed(package_name):
    """Check if a package is already installed."""
    try:
        __import__(package_name.replace('-', '_').lower())
        return True
    except ImportError:
        # Try alternative import names
        alt_names = {
            'PyQt6': 'PyQt6.QtCore',
            'pynmea2': 'pynmea2',
            'pyserial': 'serial',
            'pillow': 'PIL'
        }
        
        if package_name in alt_names:
            try:
                __import__(alt_names[package_name])
                return True
            except ImportError:
                pass
        
        return False

def install_required_packages():
    """Install all required packages."""
    print("\n📦 Installing required packages...")
    
    failed_packages = []
    
    for package, version in REQUIRED_PACKAGES.items():
        if version is None:  # Built-in package
            print(f"✅ {package} (built-in)")
            continue
            
        if check_package_installed(package):
            print(f"✅ {package} (already installed)")
            continue
            
        if not install_package(package, version, optional=False):
            failed_packages.append(package)
    
    if failed_packages:
        print(f"\n❌ Failed to install required packages: {', '.join(failed_packages)}")
        print("Please install these manually before running the application.")
        return False
    
    print("\n✅ All required packages installed successfully!")
    return True

def install_optional_packages():
    """Install optional packages for enhanced functionality."""
    print("\n🔧 Installing optional packages...")
    
    installed_count = 0
    
    for package, version in OPTIONAL_PACKAGES.items():
        if check_package_installed(package):
            print(f"✅ {package} (already installed)")
            installed_count += 1
            continue
            
        if install_package(package, version, optional=True):
            installed_count += 1
    
    print(f"\n✅ Installed {installed_count}/{len(OPTIONAL_PACKAGES)} optional packages")

def install_system_specific_packages():
    """Install system-specific packages."""
    system = platform.system()
    
    if system not in SYSTEM_PACKAGES:
        return
    
    print(f"\n🖥️  Installing {system}-specific packages...")
    
    packages = SYSTEM_PACKAGES[system]
    for package, version in packages.items():
        if version is None:
            print(f"ℹ️  {package} (install via system package manager)")
            continue
            
        if check_package_installed(package):
            print(f"✅ {package} (already installed)")
            continue
            
        install_package(package, version, optional=True)

def create_directories():
    """Create necessary application directories."""
    print("\n📁 Creating application directories...")
    
    try:
        app_dir = Path.home() / ".pynav"
        
        directories = [
            app_dir,
            app_dir / "cache",
            app_dir / "logs",
            app_dir / "maps",
            app_dir / "routes",
            app_dir / "pois"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created: {directory}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating directories: {e}")
        return False

def create_desktop_shortcut():
    """Create desktop shortcut (platform-specific)."""
    try:
        system = platform.system()
        app_dir = Path(__file__).parent
        
        if system == "Windows":
            # Create Windows shortcut
            desktop = Path.home() / "Desktop"
            shortcut_path = desktop / "PyNav.lnk"
            
            # This would require pywin32 for full implementation
            print("ℹ️  Desktop shortcut creation requires manual setup on Windows")
            
        elif system == "Darwin":  # macOS
            # Create macOS alias/shortcut
            desktop = Path.home() / "Desktop"
            print("ℹ️  Desktop shortcut creation requires manual setup on macOS")
            
        elif system == "Linux":
            # Create .desktop file
            desktop_dir = Path.home() / ".local" / "share" / "applications"
            desktop_dir.mkdir(parents=True, exist_ok=True)
            
            desktop_file = desktop_dir / "pynav.desktop"
            with open(desktop_file, 'w') as f:
                f.write(f"""[Desktop Entry]
Name=PyNav Navigation
Comment=GPS Navigation Software
Exec={sys.executable} {app_dir / "main.py"}
Icon={app_dir / "icons" / "app.png"}
Terminal=false
Type=Application
Categories=Utility;Travel;
""")
            
            # Make executable
            os.chmod(desktop_file, 0o755)
            print(f"✅ Created desktop entry: {desktop_file}")
    
    except Exception as e:
        print(f"ℹ️  Could not create desktop shortcut: {e}")

def check_system_requirements():
    """Check system requirements and dependencies."""
    print("\n🔍 Checking system requirements...")
    
    # Check available memory
    try:
        import psutil
        memory_gb = psutil.virtual_memory().total / (1024**3)
        print(f"Available memory: {memory_gb:.1f} GB")
        
        if memory_gb < 2:
            print("⚠️  Less than 2GB RAM available. Performance may be limited.")
        else:
            print("✅ Sufficient memory available")
            
    except ImportError:
        print("ℹ️  Could not check memory (psutil not installed)")
    
    # Check disk space
    try:
        import shutil
        free_space_gb = shutil.disk_usage(Path.home()).free / (1024**3)
        print(f"Available disk space: {free_space_gb:.1f} GB")
        
        if free_space_gb < 1:
            print("⚠️  Less than 1GB free space. Map caching may be limited.")
        else:
            print("✅ Sufficient disk space available")
            
    except Exception as e:
        print(f"ℹ️  Could not check disk space: {e}")

def create_config_file():
    """Create initial configuration file."""
    try:
        config_dir = Path.home() / ".pynav"
        config_file = config_dir / "config.json"
        
        if config_file.exists():
            print("✅ Configuration file already exists")
            return True
        
        initial_config = {
            "version": "1.0.0",
            "first_run": True,
            "installation_date": str(datetime.now().isoformat()),
            "installation_platform": platform.system(),
            "python_version": ".".join(map(str, sys.version_info[:3]))
        }
        
        with open(config_file, 'w') as f:
            import json
            json.dump(initial_config, f, indent=2)
        
        print(f"✅ Created configuration file: {config_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating config file: {e}")
        return False

def main():
    """Main setup function."""
    print("🧭 PyNav Navigation Software Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check system requirements
    check_system_requirements()
    
    # Install packages
    if not install_required_packages():
        sys.exit(1)
    
    install_optional_packages()
    install_system_specific_packages()
    
    # Create directories
    if not create_directories():
        print("⚠️  Warning: Could not create all directories")
    
    # Create config
    if not create_config_file():
        print("⚠️  Warning: Could not create configuration file")
    
    # Create shortcut
    create_desktop_shortcut()
    
    print("\n🎉 Setup completed successfully!")
    print("\nTo run PyNav:")
    print(f"  python {Path(__file__).parent / 'main.py'}")
    print("\nFor help and documentation:")
    print("  python main.py --help")
    
    # Optional: Run the application
    response = input("\nWould you like to start PyNav now? (y/n): ")
    if response.lower().startswith('y'):
        try:
            import subprocess
            subprocess.run([sys.executable, str(Path(__file__).parent / "main.py")])
        except Exception as e:
            print(f"Could not start application: {e}")
            print("Please run it manually using the command above.")

if __name__ == "__main__":
    # Import required modules
    from datetime import datetime
    
    main()


# ===== REQUIREMENTS.TXT =====
"""
# PyNav Navigation Software - Requirements
# Core GUI framework
PyQt6>=6.4.0
PyQt6-Qt6>=6.4.0

# HTTP requests and networking
requests>=2.28.0
urllib3>=1.26.0

# GPS and location handling
pynmea2>=1.19.0
pyserial>=3.5

# System utilities
psutil>=5.9.0

# Optional packages for enhanced functionality
geopy>=2.3.0
shapely>=2.0.0
folium>=0.14.0
gpxpy>=1.5.0
Pillow>=9.0.0
matplotlib>=3.5.0
scipy>=1.9.0
networkx>=2.8

# Development and testing (optional)
pytest>=7.0.0
black>=22.0.0
flake8>=5.0.0
"""

# ===== INSTALL.BAT (Windows) =====
"""
@echo off
echo Installing PyNav Navigation Software...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Run setup script
python setup.py

pause
"""

# ===== INSTALL.SH (Linux/macOS) =====
"""
#!/bin/bash

echo "Installing PyNav Navigation Software..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed!"
    echo "Please install Python 3.8+ using your system package manager"
    exit 1
fi

# Check Python version
python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"
if [ $? -ne 0 ]; then
    echo "Python 3.8+ is required!"
    exit 1
fi

# Run setup script
python3 setup.py

echo "Setup completed!"
"""
