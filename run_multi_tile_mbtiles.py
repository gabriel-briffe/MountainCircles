#!/usr/bin/env python
"""
Multi-tile MBTiles generation script.

This script generates a single MBTiles file covering multiple selected tiles,
with sparse coverage (only selected tiles contain data).

CACHING SYSTEM:
- HGT files: Cached in cache/hgt/ (handled by hgt_reader.py)
- OSM tiles: Cached in cache/osm/<zoom>/<x>/<y>.png (handled by fetch_osm_tile)
- Both systems check cache first and only download if needed

Usage:
    python run_multi_tile_mbtiles.py --name <name> --max-zoom <zoom> --tiles <tx,ty> [<tx,ty> ...]

Examples:
    python run_multi_tile_mbtiles.py --name alps_region --max-zoom 12 --tiles 66,45 66,46 67,45
    python run_multi_tile_mbtiles.py --name himalayas --max-zoom 10 --tiles 85,45 86,45 85,46 86,46

Outputs:
    - {name}.mbtiles (MBTiles file with sparse coverage)
"""

import argparse
import sys
import os
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
import requests
import io
import sqlite3
from pyproj import Transformer
import tempfile
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.simple_mercator import tile_bounds, get_hgt_tiles_for_web_mercator_tile
from utils.hillshade import resample_to_metric, compute_hillshade, compute_normalized_slope, combine_images
from hgt_reader import combine_hgt_tiles


def fetch_osm_tile(tx: int, ty: int, zoom: int = 7) -> Image.Image:
    """
    Fetch a single OSM tile and return as PIL Image.
    Uses the existing cache system to avoid re-downloading.
    
    Args:
        tx, ty: Tile coordinates
        zoom: Zoom level
        
    Returns:
        PIL Image of the OSM tile
    """
    from src.shortcuts import normJoin
    
    # Use the existing cache system
    cache_dir = normJoin("cache", "osm", str(zoom), str(tx))
    cache_path = normJoin(cache_dir, f"{ty}.png")
    
    if os.path.exists(cache_path):
        print(f"Using cached OSM tile: z{zoom}/x{tx}/y{ty}")
        try:
            with open(cache_path, "rb") as f:
                tile_data = f.read()
            osm_img = Image.open(io.BytesIO(tile_data)).convert('RGB')
            return osm_img
        except Exception as e:
            print(f"Error reading cached OSM tile: {e}, re-downloading...")
    
    # Download if not cached or cache read failed
    osm_url = f"https://a.tile.openstreetmap.org/{zoom}/{tx}/{ty}.png"
    
    try:
        print(f"Downloading OSM tile: z{zoom}/x{tx}/y{ty}")
        headers = {'User-Agent': 'MountainCircles/1.0 (https://github.com/user/mountaincircles)'}
        response = requests.get(osm_url, timeout=10, headers=headers)
        response.raise_for_status()
        
        # Cache the downloaded tile
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(response.content)
        
        osm_img = Image.open(io.BytesIO(response.content)).convert('RGB')
        print(f"Downloaded and cached OSM tile ({tx}, {ty}) at zoom {zoom}")
        return osm_img
    except Exception as e:
        print(f"Failed to download OSM tile ({tx}, {ty}): {e}")
        # Return blank tile
        return Image.new('RGB', (256, 256), (240, 240, 240))


def process_hgt_for_tile(tx: int, ty: int, zoom: int = 7, cellsize: int = 100) -> tuple:
    """
    Process HGT data for a specific MBTiles tile coordinate.
    
    Args:
        tx, ty: Tile coordinates  
        zoom: Zoom level
        cellsize: Target cellsize in meters
        
    Returns:
        Tuple of (hillshade_composite, dem_transform, tile_bounds_geo)
    """
    # Get tile bounds
    min_lat, min_lon, max_lat, max_lon = tile_bounds(tx, ty, zoom)
    print(f"Processing HGT for tile ({tx}, {ty}) at zoom {zoom}")
    print(f"Tile bounds: {min_lat:.6f}° to {max_lat:.6f}°N, {min_lon:.6f}° to {max_lon:.6f}°E")
    
    # Get required HGT tiles
    coord_strings = get_hgt_tiles_for_web_mercator_tile(tx, ty, zoom)
    print(f"Required HGT tiles: {coord_strings}")
    
    # Download and combine HGT tiles
    try:
        header, data = combine_hgt_tiles(coord_strings)
        print("Combined HGT data successfully")
    except Exception as e:
        print(f"Error combining HGT tiles: {e}")
        raise
    
    # Resample to metric CRS with tile bounds as subset
    subset_bounds = (min_lon, min_lat, max_lon, max_lat)
    new_dem, dem_transform, bbox_3857 = resample_to_metric(
        header, data, cellsize_new=cellsize, subset_bounds=subset_bounds
    )
    print(f"Resampled DEM: shape = {new_dem.shape}")
    
    # Compute hillshade
    standard_hillshade = compute_hillshade(new_dem, cellsize, azimuth=315, altitude=45, z_factor_shades=0.7)
    slope_map = compute_normalized_slope(new_dem, cellsize, z_factor_slopes=4.0)
    inverted_slope = 255 - slope_map
    composite = combine_images(standard_hillshade, inverted_slope)
    print("Computed composite hillshade")
    
    return composite, dem_transform, (min_lat, min_lon, max_lat, max_lon)


def generate_hillshade_tile_image(composite: np.ndarray, dem_transform: tuple, 
                                 tx: int, ty: int, zoom: int = 7) -> Image.Image:
    """
    Generate a 256x256 hillshade image for a specific tile.
    
    Args:
        composite: Hillshade composite array
        dem_transform: DEM transformation parameters
        tx, ty: Tile coordinates
        zoom: Zoom level
        
    Returns:
        PIL Image of the hillshade tile
    """
    from scipy.ndimage import map_coordinates
    
    tile_size = 256
    x_origin, y_origin, cellsize, ncols, nrows = dem_transform
    
    # Get tile bounds
    min_lat, min_lon, max_lat, max_lon = tile_bounds(tx, ty, zoom)
    
    # Convert to Web Mercator for pixel calculations
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    tile_west, tile_south = transformer.transform(min_lon, min_lat)
    tile_east, tile_north = transformer.transform(max_lon, max_lat)
    
    # Build pixel grid for the tile
    resolution_x = (tile_east - tile_west) / tile_size
    resolution_y = (tile_north - tile_south) / tile_size
    
    pixel_indices = np.arange(tile_size) + 0.5
    tile_xs = tile_west + pixel_indices * resolution_x
    tile_ys = tile_north - pixel_indices * resolution_y
    X_tile, Y_tile = np.meshgrid(tile_xs, tile_ys)
    
    # Sample the hillshade composite
    src_cols = (X_tile - x_origin) / cellsize - 0.5
    src_rows = (y_origin - Y_tile) / cellsize - 0.5
    
    tile_data = map_coordinates(composite, [src_rows, src_cols],
                              order=1, mode="constant", cval=128)
    tile_data = tile_data.astype(np.uint8)
    
    # Create hillshade image
    hillshade_img = Image.fromarray(tile_data, mode="L").convert("RGB")
    print(f"Generated hillshade tile image ({tx}, {ty})")
    
    return hillshade_img


def create_multi_tile_mbtiles(tile_data: List[Tuple[int, int, Image.Image, Image.Image]], 
                             name: str, output_path: str, base_zoom: int = 7,
                             min_zoom: int = 7, max_zoom: int = 12):
    """
    Create MBTiles file from multiple tiles with sparse coverage.
    Each zoom level is treated as native with proper OSM and hillshade generation.
    
    Args:
        tile_data: List of (tx, ty, composite_hillshade, dem_transform) tuples
        name: Name for the MBTiles file
        output_path: Output MBTiles file path
        base_zoom: Base zoom level
        min_zoom: Minimum zoom level for MBTiles
        max_zoom: Maximum zoom level for MBTiles
    """
    from scipy.ndimage import map_coordinates
    from pyproj import Transformer
    
    # Create MBTiles database
    if os.path.exists(output_path):
        os.remove(output_path)
        
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE metadata (
            name TEXT,
            value TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB,
            PRIMARY KEY (zoom_level, tile_column, tile_row)
        )
    """)
    
    # Calculate overall bounds
    all_bounds = []
    for tx, ty, _, _ in tile_data:
        min_lat, min_lon, max_lat, max_lon = tile_bounds(tx, ty, base_zoom)
        all_bounds.append((min_lat, min_lon, max_lat, max_lon))
    
    overall_min_lat = min(b[0] for b in all_bounds)
    overall_min_lon = min(b[1] for b in all_bounds)
    overall_max_lat = max(b[2] for b in all_bounds)
    overall_max_lon = max(b[3] for b in all_bounds)
    
    bounds = f"{overall_min_lon},{overall_min_lat},{overall_max_lon},{overall_max_lat}"
    
    # Insert metadata
    metadata = [
        ("name", f"{name} - Multi-tile Hillshaded Map"),
        ("type", "baselayer"),
        ("version", "1"),
        ("description", f"OSM with hillshading for {len(tile_data)} selected tiles"),
        ("format", "png"),
        ("bounds", bounds),
        ("minzoom", str(min_zoom)),
        ("maxzoom", str(max_zoom)),
    ]
    cursor.executemany("INSERT INTO metadata VALUES (?, ?)", metadata)
    
    # Process each zoom level natively
    for z in range(min_zoom, max_zoom + 1):
        print(f"Processing zoom level {z} natively...")
        
        # Calculate scale factor from base zoom
        scale_factor = 2 ** (z - base_zoom)
        
        # Process each base tile
        for tx, ty, composite_hillshade, dem_transform in tile_data:
            print(f"  Processing base tile ({tx}, {ty}) for zoom {z}")
            
            if z == base_zoom:
                # Base zoom level - process the exact tile
                tiles_to_process = [(tx, ty)]
            elif z > base_zoom:
                # Higher zoom levels - calculate child tiles
                tiles_to_process = []
                for dx in range(scale_factor):
                    for dy in range(scale_factor):
                        child_tx = tx * scale_factor + dx
                        child_ty = ty * scale_factor + dy
                        tiles_to_process.append((child_tx, child_ty))
            else:
                # Lower zoom levels - calculate parent tile
                parent_tx = tx // scale_factor
                parent_ty = ty // scale_factor
                tiles_to_process = [(parent_tx, parent_ty)]
            
            # Generate native tiles for this zoom level
            for tile_x, tile_y in tiles_to_process:
                # Download OSM tile at the current zoom level
                osm_img = fetch_osm_tile(tile_x, tile_y, z)
                
                # Generate hillshade at current zoom level resolution
                hillshade_img = generate_native_hillshade_tile(
                    composite_hillshade, dem_transform, tile_x, tile_y, z
                )
                
                # Adjust hillshade brightness and contrast before combining
                hillshade_img = ImageEnhance.Brightness(hillshade_img).enhance(1.6)  # Increase brightness (1.0 = no change, >1.0 = brighter)
                hillshade_img = ImageEnhance.Contrast(hillshade_img).enhance(1.2)    # Increase contrast (1.0 = no change, >1.0 = more contrast)
                
                # Combine OSM and hillshade
                combined_img = ImageChops.multiply(osm_img, hillshade_img)
                
                # Convert to TMS coordinates for storage
                tms_y = (2**z - 1) - tile_y
                
                # Save image as PNG
                buffer = io.BytesIO()
                combined_img.save(buffer, format="PNG")
                png_data = buffer.getvalue()
                
                cursor.execute(
                    "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                    (z, tile_x, tms_y, sqlite3.Binary(png_data))
                )
        
        conn.commit()
        print(f"Completed zoom level {z}")
    
    conn.close()
    print(f"Multi-tile MBTiles saved to {output_path}")


def generate_native_hillshade_tile(composite: np.ndarray, dem_transform: tuple, 
                                  tx: int, ty: int, zoom: int) -> Image.Image:
    """
    Generate a 256x256 hillshade image for a specific tile at native zoom resolution.
    
    Args:
        composite: Hillshade composite array from base processing
        dem_transform: DEM transformation parameters
        tx, ty: Tile coordinates at the target zoom level
        zoom: Target zoom level
        
    Returns:
        PIL Image of the hillshade tile at native resolution
    """
    from scipy.ndimage import map_coordinates
    
    tile_size = 256
    x_origin, y_origin, cellsize, ncols, nrows = dem_transform
    
    # Get tile bounds at the target zoom level
    min_lat, min_lon, max_lat, max_lon = tile_bounds(tx, ty, zoom)
    
    # Convert to Web Mercator for pixel calculations
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    tile_west, tile_south = transformer.transform(min_lon, min_lat)
    tile_east, tile_north = transformer.transform(max_lon, max_lat)
    
    # Build pixel grid for the tile at native resolution
    resolution_x = (tile_east - tile_west) / tile_size
    resolution_y = (tile_north - tile_south) / tile_size
    
    pixel_indices = np.arange(tile_size) + 0.5
    tile_xs = tile_west + pixel_indices * resolution_x
    tile_ys = tile_north - pixel_indices * resolution_y
    X_tile, Y_tile = np.meshgrid(tile_xs, tile_ys)
    
    # Sample the hillshade composite at native resolution
    src_cols = (X_tile - x_origin) / cellsize - 0.5
    src_rows = (y_origin - Y_tile) / cellsize - 0.5
    
    tile_data = map_coordinates(composite, [src_rows, src_cols],
                              order=1, mode="constant", cval=128)
    tile_data = tile_data.astype(np.uint8)
    
    # Create hillshade image
    hillshade_img = Image.fromarray(tile_data, mode="L").convert("RGB")
    
    return hillshade_img


def run_multi_tile_generation(tiles: List[Tuple[int, int]], name: str, 
                             max_zoom: int = 12, cellsize: int = 100):
    """
    Generate multi-tile MBTiles file with native zoom level processing.
    
    Args:
        tiles: List of (tx, ty) tile coordinates
        name: Name for the output file
        max_zoom: Maximum zoom level
        cellsize: HGT processing cellsize
    """
    print(f"Processing {len(tiles)} tiles for multi-tile MBTiles: {name}")
    print(f"Tiles: {tiles}")
    print(f"Max zoom: {max_zoom}")
    print("Using native zoom level processing for optimal quality")
    
    tile_data = []
    
    for i, (tx, ty) in enumerate(tiles, 1):
        print(f"\n=== Processing base tile {i}/{len(tiles)}: ({tx}, {ty}) ===")
        
        # Step 1: Process HGT data (this gives us the high-resolution composite)
        print("Processing HGT data...")
        composite, dem_transform, tile_bounds_geo = process_hgt_for_tile(tx, ty, 7, cellsize)
        
        # Store the composite and transform for native zoom processing
        tile_data.append((tx, ty, composite, dem_transform))
        print(f"Completed base processing for tile ({tx}, {ty})")
    
    # Step 2: Create multi-tile MBTiles with native zoom processing
    print(f"\n=== Creating multi-tile MBTiles with native zoom processing: {name}.mbtiles ===")
    output_path = f"{name}.mbtiles"
    create_multi_tile_mbtiles(tile_data, name, output_path, 7, 7, max_zoom)
    
    print(f"\n=== Success! ===")
    print(f"Generated multi-tile MBTiles: {output_path}")
    print(f"Coverage: {len(tiles)} tiles with sparse coverage")
    print(f"Zoom levels: 7-{max_zoom} (all native resolution)")
    print(f"OSM tiles downloaded at each zoom level for maximum detail")
    print(f"Hillshade generated at native resolution for each zoom level")


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-tile MBTiles with sparse coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_multi_tile_mbtiles.py --name alps_region --max-zoom 12 --tiles 66,45 66,46 67,45
  python run_multi_tile_mbtiles.py --name himalayas --max-zoom 10 --tiles 85,45 86,45 85,46 86,46
        """
    )
    
    parser.add_argument("--name", required=True, help="Name for the MBTiles file")
    parser.add_argument("--max-zoom", type=int, default=12, help="Maximum zoom level (default: 12)")
    parser.add_argument("--tiles", nargs="+", required=True, help="Tile coordinates as tx,ty pairs")
    parser.add_argument("--cellsize", type=int, default=100, help="HGT processing cellsize in meters (default: 100)")
    
    args = parser.parse_args()
    
    # Parse tile coordinates
    tiles = []
    for tile_str in args.tiles:
        try:
            tx, ty = map(int, tile_str.split(','))
            tiles.append((tx, ty))
        except ValueError:
            print(f"Error: Invalid tile format '{tile_str}'. Use format 'tx,ty'")
            sys.exit(1)
    
    if not tiles:
        print("Error: No valid tiles provided")
        sys.exit(1)
    
    try:
        run_multi_tile_generation(tiles, args.name, args.max_zoom, args.cellsize)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 