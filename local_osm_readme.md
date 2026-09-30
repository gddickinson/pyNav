# PyNav - Local OSM Data Setup Guide

## Overview

PyNav now supports using **local OpenStreetMap data** as the primary source for map tiles! This feature allows you to use your `planet-latest.osm.pbf` file (or regional extracts) without relying on online tile downloads.

### How It Works

**Tile Loading Priority:**
1. 🏠 **Local OSM tiles** (from your MBTiles database) - FIRST
2. 💾 **Cached tiles** (previously downloaded tiles)
3. 🌐 **Online download** (when local tiles unavailable and online mode enabled)

This means you can browse maps completely offline if you have the tiles in your local database!

---

## Quick Start

### For Austin, TX (Example)

```bash
# 1. Convert your PBF to MBTiles for Austin area
python convert_osm_to_mbtiles.py \
    /Volumes/GeorgeDrive/planet-latest.osm.pbf \
    austin_tiles.mbtiles \
    --bbox=-97.9,30.1,-97.6,30.4 \
    --zoom-max=16

# 2. Open PyNav and configure
# View → Local OSM Settings
# Browse to: austin_tiles.mbtiles
# Enable: ✓ Use Local OSM Tiles
```

---

## Detailed Setup Instructions

### Step 1: Prepare Your System

Install required conversion tools (choose one):

#### Option A: tilemaker (Recommended)
```bash
# macOS
brew install tilemaker

# Ubuntu/Debian
sudo apt-get install tilemaker

# Build from source
git clone https://github.com/systemed/tilemaker.git
cd tilemaker
make
sudo make install
```

#### Option B: planetiler (Java-based, very fast)
```bash
# Download latest release
wget https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar

# Or use Maven
mvn clean package
```

### Step 2: Extract Your Region (Optional but Recommended)

The planet file is huge (60+ GB compressed). Extract just your region first:

```bash
# Install osmium-tool
brew install osmium-tool  # macOS
sudo apt-get install osmium-tool  # Ubuntu/Debian

# Extract your region
osmium extract \
    --bbox=-97.9,30.1,-97.6,30.4 \
    --strategy=simple \
    --output=austin.osm.pbf \
    /Volumes/GeorgeDrive/planet-latest.osm.pbf
```

**Common Bounding Boxes:**
- Austin, TX: `-97.9,30.1,-97.6,30.4`
- Texas: `-106.65,25.84,-93.51,36.50`
- San Francisco: `-122.5,37.7,-122.3,37.85`
- New York: `-74.3,40.5,-73.7,40.95`

Find coordinates for your area: https://boundingbox.klokantech.com/

### Step 3: Convert to MBTiles

#### Using tilemaker:

```bash
python convert_osm_to_mbtiles.py \
    austin.osm.pbf \
    austin_tiles.mbtiles \
    --zoom-min=0 \
    --zoom-max=16 \
    --tool=tilemaker
```

#### Using planetiler:

```bash
python convert_osm_to_mbtiles.py \
    austin.osm.pbf \
    austin_tiles.mbtiles \
    --zoom-min=0 \
    --zoom-max=16 \
    --tool=planetiler
```

#### Manual conversion with tilemaker:

```bash
tilemaker \
    --input austin.osm.pbf \
    --output austin_tiles.mbtiles \
    --process /usr/local/share/tilemaker/process-openmaptiles.lua \
    --config /usr/local/share/tilemaker/config-openmaptiles.json
```

### Step 4: Configure PyNav

1. Open PyNav
2. Go to **View → Local OSM Settings**
3. Click **Browse** and select your `.mbtiles` file
4. Check **✓ Enable Local OSM Tiles**
5. Click **Apply**
6. Click **Test Configuration** to verify it's working

---

## Understanding Zoom Levels

| Zoom | Coverage | Typical Use | Tiles/Region | Size Estimate |
|------|----------|-------------|--------------|---------------|
| 0-7  | Continental | Country view | ~1,000 | ~20 MB |
| 8-12 | Regional | State/province | ~50,000 | ~500 MB |
| 13-14 | City | Metro area | ~500,000 | ~3 GB |
| 15-16 | Neighborhood | Street detail | ~5,000,000 | ~20 GB |
| 17-18 | Street | Building detail | ~50,000,000 | ~100+ GB |

**Recommendations:**
- **General use:** Zoom 0-14 (good detail, reasonable size)
- **City navigation:** Zoom 0-16 (street-level detail)
- **Complete detail:** Zoom 0-18 (very large!)

---

## File Size Guidelines

### Austin, TX Example (approx.):
- Zoom 0-12: ~100 MB
- Zoom 0-14: ~800 MB
- Zoom 0-16: ~5 GB
- Zoom 0-18: ~30 GB

### Texas State (approx.):
- Zoom 0-12: ~2 GB
- Zoom 0-14: ~15 GB
- Zoom 0-16: ~100 GB

### Entire Planet:
- Zoom 0-14: ~100+ GB
- Zoom 0-16: ~500+ GB
- **Not recommended** to convert entire planet at high zoom!

---

## Using the Conversion Utility

### Basic Usage

```bash
python convert_osm_to_mbtiles.py INPUT.pbf OUTPUT.mbtiles [OPTIONS]
```

### Options

```
--bbox MIN_LON,MIN_LAT,MAX_LON,MAX_LAT   Region to extract
--zoom-min N                              Minimum zoom level (default: 0)
--zoom-max N                              Maximum zoom level (default: 14)
--extract-first                           Extract region before converting
--tool {tilemaker,planetiler,auto}        Conversion tool to use
--instructions                            Print manual instructions
```

### Examples

**Small city (Austin):**
```bash
python convert_osm_to_mbtiles.py \
    /Volumes/GeorgeDrive/planet-latest.osm.pbf \
    austin.mbtiles \
    --bbox=-97.9,30.1,-97.6,30.4 \
    --zoom-max=16 \
    --extract-first
```

**Large region (Texas):**
```bash
python convert_osm_to_mbtiles.py \
    /Volumes/GeorgeDrive/planet-latest.osm.pbf \
    texas.mbtiles \
    --bbox=-106.65,25.84,-93.51,36.50 \
    --zoom-max=14 \
    --extract-first
```

**Get instructions:**
```bash
python convert_osm_to_mbtiles.py --instructions
```

---

## Settings & Configuration

### Via GUI

1. **View → Local OSM Settings**
2. Configure:
   - ✓ Enable Local OSM Tiles
   - MBTiles Path: `/path/to/your/file.mbtiles`
3. Click **Test Configuration** to verify
4. Click **Apply** to activate

### Via Settings File

Edit `~/.pynav/settings.json`:

```json
{
  "local_osm": {
    "enabled": true,
    "mbtiles_path": "/path/to/your/tiles.mbtiles"
  }
}
```

---

## Performance Tips

### 1. **Use SSD Storage**
MBTiles databases perform much better on SSD than HDD. Consider storing your `.mbtiles` file on an internal SSD rather than an external drive.

### 2. **Optimize Zoom Levels**
Only include zoom levels you'll actually use:
- City navigation: 0-16
- Regional overview: 0-14
- Continental view: 0-12

### 3. **Multiple MBTiles Files**
Create separate databases for different regions:
```
austin_tiles.mbtiles      (zoom 0-18, small area, high detail)
texas_tiles.mbtiles       (zoom 0-14, large area, moderate detail)
usa_overview.mbtiles      (zoom 0-10, entire USA, low detail)
```

Switch between them as needed in the settings dialog.

### 4. **Periodic Updates**
OSM data changes frequently. Update your local tiles periodically:
```bash
# Download latest planet file
wget https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf

# Re-run conversion
python convert_osm_to_mbtiles.py ...
```

---

## Troubleshooting

### ❌ "MBTiles file not found"

**Solution:** Check the file path. Use absolute paths:
```
✗ Wrong: ~/austin.mbtiles
✓ Right: /Users/yourusername/austin.mbtiles
```

### ❌ "Failed to load MBTiles database"

**Possible causes:**
1. File is corrupted - re-convert
2. File is being used by another application - close it
3. Incorrect file format - verify it's a valid MBTiles file

**Test the file:**
```bash
sqlite3 austin.mbtiles "SELECT COUNT(*) FROM tiles;"
```

### ❌ "Conversion takes forever"

**Solutions:**
1. Extract your region first with `osmium extract`
2. Use planetiler (faster than tilemaker)
3. Reduce maximum zoom level
4. Use a smaller bounding box

### ❌ "Tiles appear but are low quality"

**Check zoom level range:**
- Increase `--zoom-max` for more detail
- Recommended: 16 for street-level navigation

### ❌ "Local tiles not being used"

**Verify:**
1. Local OSM tiles are **enabled** in settings
2. Path is correct in settings
3. Server type is OSM-compatible (OpenStreetMap, OpenTopoMap, CyclOSM)
4. Check Statistics → Local Tile Hits should increase

---

## Advanced: MBTiles Format

MBTiles is a SQLite database with this schema:

```sql
-- Metadata
CREATE TABLE metadata (name text, value text);

-- Tiles
CREATE TABLE tiles (
    zoom_level integer,
    tile_column integer,
    tile_row integer,
    tile_data blob
);
```

### Inspecting Your MBTiles

```bash
# Open in SQLite
sqlite3 your_tiles.mbtiles

# Check metadata
SELECT * FROM metadata;

# Count tiles
SELECT COUNT(*) FROM tiles;

# Check zoom levels
SELECT zoom_level, COUNT(*) FROM tiles GROUP BY zoom_level;

# Check bounds
SELECT value FROM metadata WHERE name='bounds';
```

---

## Integration with Existing Features

### Works With:
- ✅ Offline Maps dialog (download additional areas)
- ✅ Cache statistics
- ✅ Offline mode toggle
- ✅ Multiple tile servers

### Priority Chain:
```
User requests tile at zoom 15, coordinates 1234,5678

1. Check local MBTiles database
   ├─ Found? → Return tile ✓
   └─ Not found? → Continue...

2. Check memory cache
   ├─ Found? → Return tile ✓
   └─ Not found? → Continue...

3. Check disk cache (database)
   ├─ Found? → Return tile ✓
   └─ Not found? → Continue...

4. Offline mode enabled?
   ├─ Yes → Return "offline" placeholder
   └─ No → Download from online source
```

---

## Useful Resources

### Tools
- **tilemaker:** https://github.com/systemed/tilemaker
- **planetiler:** https://github.com/onthegomap/planetiler
- **osmium-tool:** https://osmcode.org/osmium-tool/
- **tippecanoe:** https://github.com/felt/tippecanoe

### Data Sources
- **Planet OSM:** https://planet.openstreetmap.org/
- **GeoFabrik Extracts:** https://download.geofabrik.de/
- **BBBike Extracts:** https://extract.bbbike.org/

### Documentation
- **MBTiles Spec:** https://github.com/mapbox/mbtiles-spec
- **OSM Wiki:** https://wiki.openstreetmap.org/
- **Tile Rendering:** https://switch2osm.org/serving-tiles/

---

## FAQ

**Q: Can I use the planet file directly without converting?**  
A: No. The PBF format stores raw OSM data (nodes, ways, relations), not rendered map tiles. You must convert it to MBTiles first.

**Q: How long does conversion take?**  
A: Depends on area and zoom level:
- Austin (zoom 0-16): ~30 minutes
- Texas (zoom 0-14): ~3-4 hours
- Planet (zoom 0-14): ~24+ hours

**Q: Can I update my tiles without re-converting everything?**  
A: Unfortunately no. MBTiles doesn't support incremental updates. You'll need to re-convert when you want fresh data.

**Q: Will this work on my external drive?**  
A: Yes, but performance will be better on internal SSD. External drives (especially /Volumes/GeorgeDrive) will work but may be slower.

**Q: Can I share my MBTiles file with others?**  
A: Yes! The MBTiles file is portable. Just copy it and others can use it with PyNav or other MBTiles-compatible applications.

**Q: What's the difference between this and the Offline Maps feature?**  
A: 
- **Local OSM**: Uses your own OSM data converted to MBTiles (complete offline capability)
- **Offline Maps**: Downloads tiles from online sources for later offline use (internet required initially)

---

## Support

If you encounter issues:

1. **Check logs:** `~/.pynav/logs/navigation.log`
2. **Test configuration:** Use "Test Configuration" button in settings dialog
3. **Verify file:** Use `sqlite3` to inspect your MBTiles file
4. **Check statistics:** View → Local OSM Settings → Usage Statistics

Happy mapping! 🗺️
