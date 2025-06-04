#!/usr/bin/env python
"""
HGT file reader for SRTM data.

This module handles downloading and reading HGT files from the XCSoar mapgen server.
HGT files are binary elevation data files covering 1° x 1° areas.
"""

import os
import re
import numpy as np
import requests
from typing import Tuple, Dict, Any, List
import tempfile
import math


def parse_coordinate_string(coord_str: str) -> Tuple[float, float]:
    """
    Parse HGT coordinate string to extract latitude and longitude.
    
    Args:
        coord_str: Coordinate string like "N45W010" or "S12E034"
        
    Returns:
        Tuple of (latitude, longitude) in decimal degrees
        
    Raises:
        ValueError: If coordinate string format is invalid
    """
    # Match pattern like N45W010, S12E034, etc.
    pattern = r'^([NS])(\d{2})([EW])(\d{3})$'
    match = re.match(pattern, coord_str.upper())
    
    if not match:
        raise ValueError(f"Invalid coordinate format: {coord_str}. Expected format like N45W010")
    
    lat_hem, lat_val, lon_hem, lon_val = match.groups()
    
    # Convert to decimal degrees
    lat = float(lat_val)
    if lat_hem == 'S':
        lat = -lat
        
    lon = float(lon_val)
    if lon_hem == 'W':
        lon = -lon
        
    return lat, lon


def generate_coordinate_string(lat: float, lon: float) -> str:
    """
    Generate HGT coordinate string from latitude and longitude.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        
    Returns:
        Coordinate string like "N45W010"
    """
    # Determine hemispheres
    lat_hem = 'N' if lat >= 0 else 'S'
    lon_hem = 'E' if lon >= 0 else 'W'
    
    # Use absolute values for formatting
    lat_abs = abs(int(lat))
    lon_abs = abs(int(lon))
    
    return f"{lat_hem}{lat_abs:02d}{lon_hem}{lon_abs:03d}"


def get_hgt_tiles_for_area(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> List[str]:
    """
    Get list of HGT coordinate strings needed to cover a geographic area.
    
    Args:
        min_lat, min_lon, max_lat, max_lon: Bounding box in decimal degrees
        
    Returns:
        List of HGT coordinate strings
    """
    tiles = []
    
    # Generate coordinates for each 1° tile needed
    # Use floor for start and ceil for end to ensure complete coverage
    lat_start = int(math.floor(min_lat))
    lat_end = int(math.ceil(max_lat))
    lon_start = int(math.floor(min_lon))
    lon_end = int(math.ceil(max_lon))
    
    print(f"HGT tiles needed for area {min_lat:.6f}° to {max_lat:.6f}°N, {min_lon:.6f}° to {max_lon:.6f}°E:")
    print(f"  Latitude range: {lat_start} to {lat_end} (inclusive)")
    print(f"  Longitude range: {lon_start} to {lon_end} (inclusive)")
    
    for lat in range(lat_start, lat_end + 1):
        for lon in range(lon_start, lon_end + 1):
            coord_str = generate_coordinate_string(lat, lon)
            tiles.append(coord_str)
            print(f"  Adding tile: {coord_str} (covers {lat}° to {lat+1}°N, {lon}° to {lon+1}°E)")
    
    return tiles


def download_hgt_file(coord_str: str, cache_dir: str = "cache/hgt") -> str:
    """
    Download HGT file from XCSoar mapgen server.
    
    Args:
        coord_str: Coordinate string like "N45W010"
        cache_dir: Local directory to cache downloaded files
        
    Returns:
        Path to the downloaded/cached HGT file
        
    Raises:
        requests.RequestException: If download fails
        ValueError: If coordinate format is invalid
    """
    # Validate coordinate format
    parse_coordinate_string(coord_str)
    
    filename = f"{coord_str.upper()}.hgt"
    local_path = os.path.join(cache_dir, filename)
    
    # Return cached file if it exists
    if os.path.exists(local_path):
        print(f"Using cached HGT file: {local_path}")
        return local_path
    
    # Create cache directory
    os.makedirs(cache_dir, exist_ok=True)
    
    # Try lowercase first, then uppercase
    filenames_to_try = [
        f"{coord_str.lower()}.hgt",  # Try lowercase first
        f"{coord_str.upper()}.hgt"   # Then uppercase
    ]
    
    for filename in filenames_to_try:
        url = f"https://mapgen-data.sigkill.ch/dem3/{filename}"
        print(f"Trying to download HGT file from: {url}")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Write to cache (always use uppercase filename locally for consistency)
            with open(local_path, 'wb') as f:
                f.write(response.content)
                
            print(f"Downloaded HGT file: {local_path} ({len(response.content)} bytes)")
            return local_path
            
        except requests.RequestException as e:
            print(f"Failed to download {url}: {e}")
            continue  # Try next filename format
    
    # If we get here, none of the filename formats worked
    raise requests.RequestException(f"Failed to download HGT file for {coord_str}. Tried: {filenames_to_try}")


def read_hgt_file(filepath: str) -> Tuple[Dict[str, Any], np.ndarray]:
    """
    Read HGT file and return header and elevation data.
    
    Args:
        filepath: Path to HGT file
        
    Returns:
        Tuple of (header_dict, elevation_data)
        Header dict contains ASC-compatible format information
        Elevation data is a 2D numpy array
        
    Raises:
        FileNotFoundError: If HGT file doesn't exist
        ValueError: If file format is invalid
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"HGT file not found: {filepath}")
    
    # Extract coordinates from filename
    filename = os.path.basename(filepath)
    coord_str = filename.replace('.hgt', '').replace('.HGT', '')
    lat, lon = parse_coordinate_string(coord_str)
    
    # Read binary data
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # SRTM3 files should be 1201x1201 16-bit integers = 2,884,802 bytes
    expected_size = 1201 * 1201 * 2
    if len(data) != expected_size:
        raise ValueError(f"Invalid HGT file size: {len(data)} bytes, expected {expected_size}")
    
    # Convert to numpy array (big-endian 16-bit signed integers)
    elevation_data = np.frombuffer(data, dtype='>i2').reshape(1201, 1201)
    
    # Convert to float and handle no-data values
    elevation_data = elevation_data.astype(np.float64)
    
    # SRTM uses -32768 as no-data value
    elevation_data[elevation_data == -32768] = np.nan
    
    # Create ASC-compatible header
    # HGT files cover from lat to lat+1 and lon to lon+1
    # Cell size is 1/1200 degrees (3 arc-seconds)
    header = {
        'ncols': 1201,
        'nrows': 1201,
        'xllcorner': lon,  # Lower-left corner longitude
        'yllcorner': lat,  # Lower-left corner latitude
        'cellsize': 1.0 / 1200.0,  # 3 arc-seconds in degrees
        'nodata_value': -9999
    }
    
    print(f"Read HGT file: {filepath}")
    print(f"Coordinates: {lat}°N to {lat+1}°N, {lon}°E to {lon+1}°E")
    print(f"Elevation range: {np.nanmin(elevation_data):.1f}m to {np.nanmax(elevation_data):.1f}m")
    
    return header, elevation_data


def combine_hgt_tiles(coord_strings: List[str], cache_dir: str = "cache/hgt") -> Tuple[Dict[str, Any], np.ndarray]:
    """
    Download and combine multiple HGT tiles into a single DEM.
    
    Args:
        coord_strings: List of HGT coordinate strings to combine
        cache_dir: Directory for caching downloaded files
        
    Returns:
        Tuple of (combined_header, combined_elevation_data)
        
    Raises:
        ValueError: If tiles don't form a regular grid
    """
    if not coord_strings:
        raise ValueError("No coordinate strings provided")
    
    print(f"Combining {len(coord_strings)} HGT tiles...")
    
    # Download all tiles and read their data
    tiles_data = {}
    for coord_str in coord_strings:
        try:
            hgt_file = download_hgt_file(coord_str, cache_dir)
            header, data = read_hgt_file(hgt_file)
            lat, lon = parse_coordinate_string(coord_str)
            tiles_data[(lat, lon)] = (header, data)
        except Exception as e:
            print(f"Warning: Could not process tile {coord_str}: {e}")
            continue
    
    if not tiles_data:
        raise ValueError("No valid tiles could be downloaded")
    
    # Determine the bounding box of available tiles
    lats = [lat for lat, lon in tiles_data.keys()]
    lons = [lon for lat, lon in tiles_data.keys()]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    print(f"Combining tiles covering {min_lat}° to {max_lat+1}°N, {min_lon}° to {max_lon+1}°E")
    
    # Calculate dimensions of combined DEM
    lat_range = int(max_lat - min_lat + 1)
    lon_range = int(max_lon - min_lon + 1)
    
    # Each tile is 1201x1201, but we need to avoid double-counting borders
    # Combined size: (lat_range * 1200 + 1) x (lon_range * 1200 + 1)
    combined_rows = lat_range * 1200 + 1
    combined_cols = lon_range * 1200 + 1
    
    # Initialize combined array with NaN
    combined_data = np.full((combined_rows, combined_cols), np.nan, dtype=np.float64)
    
    # Place each tile in the correct position
    for (tile_lat, tile_lon), (header, data) in tiles_data.items():
        # Calculate position in combined array
        # Note: HGT data has row 0 at the north (top)
        lat_offset = int(max_lat - tile_lat)  # Tiles are placed from north to south
        lon_offset = int(tile_lon - min_lon)  # Tiles are placed from west to east
        
        start_row = lat_offset * 1200
        end_row = start_row + 1201
        start_col = lon_offset * 1200
        end_col = start_col + 1201
        
        # Handle overlapping borders by taking the average
        existing_data = combined_data[start_row:end_row, start_col:end_col]
        mask = ~np.isnan(existing_data)
        
        if np.any(mask):
            # Average overlapping areas
            combined_data[start_row:end_row, start_col:end_col] = np.where(
                mask,
                (existing_data + data) / 2,
                data
            )
        else:
            # No existing data, just place the tile
            combined_data[start_row:end_row, start_col:end_col] = data
    
    # Create combined header
    combined_header = {
        'ncols': combined_cols,
        'nrows': combined_rows,
        'xllcorner': float(min_lon),  # Lower-left corner longitude
        'yllcorner': float(min_lat),  # Lower-left corner latitude
        'cellsize': 1.0 / 1200.0,  # 3 arc-seconds in degrees
        'nodata_value': -9999
    }
    
    print(f"Combined DEM: {combined_rows} x {combined_cols} pixels")
    print(f"Coverage: {min_lat}° to {max_lat+1}°N, {min_lon}° to {max_lon+1}°E")
    print(f"Elevation range: {np.nanmin(combined_data):.1f}m to {np.nanmax(combined_data):.1f}m")
    
    return combined_header, combined_data


def get_hgt_bounds(coord_str: str) -> Tuple[float, float, float, float]:
    """
    Get geographic bounds for HGT coordinate.
    
    Args:
        coord_str: Coordinate string like "N45W010"
        
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon)
    """
    lat, lon = parse_coordinate_string(coord_str)
    
    # HGT files cover exactly 1° x 1°
    return lat, lon, lat + 1.0, lon + 1.0


def get_area_bounds(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> Tuple[float, float, float, float]:
    """
    Get geographic bounds for a multi-degree area.
    
    Args:
        min_lat, min_lon, max_lat, max_lon: Area bounds in decimal degrees
        
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon)
    """
    return min_lat, min_lon, max_lat, max_lon


if __name__ == "__main__":
    # Test the module
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python hgt_reader.py N45W010")
        sys.exit(1)
    
    coord = sys.argv[1]
    
    try:
        # Test coordinate parsing
        lat, lon = parse_coordinate_string(coord)
        print(f"Parsed coordinates: {lat}°, {lon}°")
        
        # Test download
        hgt_file = download_hgt_file(coord)
        
        # Test reading
        header, data = read_hgt_file(hgt_file)
        print(f"Header: {header}")
        print(f"Data shape: {data.shape}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 