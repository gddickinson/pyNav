#!/usr/bin/env python3
"""
OSM PBF to MBTiles Conversion Utility for PyNav
================================================

This script provides instructions and wrapper for converting OpenStreetMap
PBF files to MBTiles format for use with PyNav's local tile feature.

RECOMMENDED TOOLS:
1. tilemaker - https://github.com/systemed/tilemaker
2. planetiler - https://github.com/onthegomap/planetiler
3. tippecanoe - https://github.com/felt/tippecanoe

This script helps automate the process and provides guidance.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def print_banner():
    """Print banner and information."""
    print("=" * 70)
    print("  PyNav - OSM PBF to MBTiles Converter")
    print("=" * 70)
    print()


def check_tool_available(tool_name: str) -> bool:
    """Check if a conversion tool is available."""
    try:
        result = subprocess.run(
            [tool_name, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def find_available_tools():
    """Find which conversion tools are available."""
    tools = {
        'tilemaker': check_tool_available('tilemaker'),
        'planetiler': check_tool_available('java') and Path('planetiler.jar').exists(),
        'tippecanoe': check_tool_available('tippecanoe')
    }

    return {name: available for name, available in tools.items() if available}


def convert_with_tilemaker(pbf_path: str, output_path: str, bbox: str = None,
                           zoom_min: int = 0, zoom_max: int = 14):
    """
    Convert PBF to MBTiles using tilemaker.

    Args:
        pbf_path: Path to input PBF file
        output_path: Path to output MBTiles file
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        zoom_min: Minimum zoom level
        zoom_max: Maximum zoom level
    """
    print(f"Converting {pbf_path} to {output_path} using tilemaker...")
    print(f"Zoom range: {zoom_min}-{zoom_max}")

    cmd = [
        'tilemaker',
        '--input', pbf_path,
        '--output', output_path,
        '--process', 'resources/process-openmapti les.lua',  # Default tilemaker config
        '--config', 'resources/config-openmaptiles.json',
        '--store', '/tmp/tilemaker_store',  # Temporary storage
    ]

    if bbox:
        cmd.extend(['--bbox', bbox])

    print(f"Running: {' '.join(cmd)}")
    print("This may take a while for large areas...")
    print()

    try:
        result = subprocess.run(cmd, check=True)
        if result.returncode == 0:
            print(f"\n✓ Successfully created {output_path}")
            print_file_size(output_path)
            return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error during conversion: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ tilemaker not found. Please install it first.")
        print("   See: https://github.com/systemed/tilemaker")
        return False


def convert_with_planetiler(pbf_path: str, output_path: str, bbox: str = None,
                            zoom_min: int = 0, zoom_max: int = 14):
    """
    Convert PBF to MBTiles using planetiler.

    Args:
        pbf_path: Path to input PBF file
        output_path: Path to output MBTiles file
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        zoom_min: Minimum zoom level
        zoom_max: Maximum zoom level
    """
    print(f"Converting {pbf_path} to {output_path} using planetiler...")
    print(f"Zoom range: {zoom_min}-{zoom_max}")

    cmd = [
        'java', '-Xmx4g',  # Allocate 4GB RAM
        '-jar', 'planetiler.jar',
        '--osm-path=' + pbf_path,
        '--mbtiles=' + output_path,
        '--download',
        '--force'
    ]

    if bbox:
        # Planetiler uses --bounds format
        cmd.append(f'--bounds={bbox}')

    print(f"Running: {' '.join(cmd)}")
    print("This may take a while for large areas...")
    print()

    try:
        result = subprocess.run(cmd, check=True)
        if result.returncode == 0:
            print(f"\n✓ Successfully created {output_path}")
            print_file_size(output_path)
            return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error during conversion: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ planetiler.jar not found. Please download it first.")
        print("   See: https://github.com/onthegomap/planetiler")
        return False


def print_file_size(file_path: str):
    """Print file size in human-readable format."""
    try:
        size_bytes = os.path.getsize(file_path)

        if size_bytes < 1024:
            print(f"   Size: {size_bytes} bytes")
        elif size_bytes < 1024 * 1024:
            print(f"   Size: {size_bytes / 1024:.2f} KB")
        elif size_bytes < 1024 * 1024 * 1024:
            print(f"   Size: {size_bytes / (1024 * 1024):.2f} MB")
        else:
            print(f"   Size: {size_bytes / (1024 * 1024 * 1024):.2f} GB")
    except Exception as e:
        print(f"   Could not determine file size: {e}")


def extract_region(pbf_path: str, bbox: str, output_pbf: str):
    """
    Extract a region from a large PBF file using osmium.

    Args:
        pbf_path: Path to input PBF file
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        output_pbf: Path to output PBF file
    """
    print(f"Extracting region from {pbf_path}...")
    print(f"Bounding box: {bbox}")

    cmd = [
        'osmium', 'extract',
        '--bbox', bbox,
        '--strategy', 'simple',
        '--output', output_pbf,
        pbf_path
    ]

    print(f"Running: {' '.join(cmd)}")
    print("This may take a while...")
    print()

    try:
        result = subprocess.run(cmd, check=True)
        if result.returncode == 0:
            print(f"\n✓ Successfully extracted region to {output_pbf}")
            print_file_size(output_pbf)
            return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error during extraction: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ osmium not found. Please install osmium-tool first.")
        print("   Ubuntu/Debian: apt-get install osmium-tool")
        print("   macOS: brew install osmium-tool")
        return False


def print_instructions():
    """Print manual conversion instructions."""
    print("\n" + "=" * 70)
    print("  MANUAL CONVERSION INSTRUCTIONS")
    print("=" * 70)
    print()
    print("If automatic conversion doesn't work, follow these steps:")
    print()

    print("OPTION 1: Using tilemaker (Recommended)")
    print("-" * 40)
    print("1. Install tilemaker:")
    print("   https://github.com/systemed/tilemaker")
    print()
    print("2. For a specific region (e.g., Texas):")
    print("   tilemaker --input planet-latest.osm.pbf \\")
    print("            --output texas.mbtiles \\")
    print("            --bbox=-106.65,25.84,-93.51,36.50 \\")
    print("            --process resources/process-openmaptiles.lua \\")
    print("            --config resources/config-openmaptiles.json")
    print()

    print("OPTION 2: Using planetiler (Java-based, very fast)")
    print("-" * 40)
    print("1. Download planetiler.jar:")
    print("   https://github.com/onthegomap/planetiler/releases")
    print()
    print("2. Run conversion:")
    print("   java -Xmx4g -jar planetiler.jar \\")
    print("        --osm-path=planet-latest.osm.pbf \\")
    print("        --mbtiles=output.mbtiles \\")
    print("        --bounds=-106.65,25.84,-93.51,36.50")
    print()

    print("OPTION 3: Extract region first, then convert")
    print("-" * 40)
    print("1. Install osmium-tool:")
    print("   Ubuntu/Debian: apt-get install osmium-tool")
    print("   macOS: brew install osmium-tool")
    print()
    print("2. Extract your region:")
    print("   osmium extract \\")
    print("          --bbox=-106.65,25.84,-93.51,36.50 \\")
    print("          --strategy=simple \\")
    print("          --output=texas.osm.pbf \\")
    print("          planet-latest.osm.pbf")
    print()
    print("3. Then convert the smaller file to MBTiles using tilemaker or planetiler")
    print()

    print("TIPS:")
    print("-" * 40)
    print("• For the entire planet, you'll need 100+ GB of storage")
    print("• Extract only the region you need to save space")
    print("• Use zoom levels 0-14 for good detail without huge file size")
    print("• Austin area bbox: -97.9,30.1,-97.6,30.4")
    print("• Texas bbox: -106.65,25.84,-93.51,36.50")
    print("• To find coordinates: https://boundingbox.klokantech.com/")
    print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Convert OSM PBF to MBTiles for PyNav',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('pbf_file', help='Path to input PBF file')
    parser.add_argument('output_file', help='Path to output MBTiles file')
    parser.add_argument('--bbox', help='Bounding box: min_lon,min_lat,max_lon,max_lat')
    parser.add_argument('--zoom-min', type=int, default=0, help='Minimum zoom level (default: 0)')
    parser.add_argument('--zoom-max', type=int, default=14, help='Maximum zoom level (default: 14)')
    parser.add_argument('--extract-first', action='store_true',
                       help='Extract region to smaller PBF first (requires osmium)')
    parser.add_argument('--tool', choices=['tilemaker', 'planetiler', 'auto'],
                       default='auto', help='Conversion tool to use')
    parser.add_argument('--instructions', action='store_true',
                       help='Print manual instructions and exit')

    args = parser.parse_args()

    print_banner()

    if args.instructions:
        print_instructions()
        return 0

    # Check if input file exists
    if not os.path.exists(args.pbf_file):
        print(f"✗ Error: Input file not found: {args.pbf_file}")
        return 1

    print(f"Input file: {args.pbf_file}")
    print_file_size(args.pbf_file)
    print()

    # Find available tools
    available_tools = find_available_tools()

    if not available_tools:
        print("✗ No conversion tools found!")
        print()
        print_instructions()
        return 1

    print("Available conversion tools:")
    for tool, available in available_tools.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")
    print()

    # Extract region first if requested
    working_pbf = args.pbf_file
    if args.extract_first and args.bbox:
        print("Extracting region first...")
        extracted_pbf = args.output_file.replace('.mbtiles', '_extracted.osm.pbf')
        if extract_region(args.pbf_file, args.bbox, extracted_pbf):
            working_pbf = extracted_pbf
        else:
            print("Warning: Extraction failed, using original file")
        print()

    # Choose conversion tool
    if args.tool == 'auto':
        if 'planetiler' in available_tools:
            tool = 'planetiler'
        elif 'tilemaker' in available_tools:
            tool = 'tilemaker'
        else:
            tool = list(available_tools.keys())[0]
    else:
        tool = args.tool
        if tool not in available_tools:
            print(f"✗ Error: {tool} is not available")
            return 1

    print(f"Using tool: {tool}")
    print()

    # Convert
    if tool == 'tilemaker':
        success = convert_with_tilemaker(
            working_pbf, args.output_file, args.bbox,
            args.zoom_min, args.zoom_max
        )
    elif tool == 'planetiler':
        success = convert_with_planetiler(
            working_pbf, args.output_file, args.bbox,
            args.zoom_min, args.zoom_max
        )
    else:
        print(f"✗ Unsupported tool: {tool}")
        success = False

    if success:
        print()
        print("=" * 70)
        print("  ✓ CONVERSION SUCCESSFUL!")
        print("=" * 70)
        print()
        print(f"Output file: {args.output_file}")
        print()
        print("To use in PyNav:")
        print("1. Open PyNav")
        print("2. Go to View → Local OSM Settings")
        print(f"3. Set MBTiles path to: {os.path.abspath(args.output_file)}")
        print("4. Enable 'Use Local OSM Tiles'")
        print()
        return 0
    else:
        print()
        print("=" * 70)
        print("  ✗ CONVERSION FAILED")
        print("=" * 70)
        print()
        print("Try running with --instructions for manual conversion steps")
        return 1


if __name__ == '__main__':
    sys.exit(main())
