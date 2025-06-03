#!/usr/bin/env python
"""
Patched wrapper script for generate_map.py that:
1. Uses a fixed ASC reader function
2. Uses the correct parameter names

This avoids modifying any of the original code files.

Usage:
    python run_map_patched.py input_topo.asc output.mbtiles [--bounds file.geojson]
           [--cellsize 100] [--min_zoom 1] [--max_zoom 12] [--z_factor 1.4]
           [--azimuth 315] [--altitude 45] [--output_resampled resampled.asc]
"""

import argparse
import sys
import os
import numpy as np
from pyproj import Transformer
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required modules
from utils.hillshade import resample_to_metric, compute_hillshade, compute_normalized_slope, combine_images, generate_mbtiles
from utils.mbtile import download_and_combine_region, calculate_bbox_from_geojson

# Import our fixed read_asc function
from asc_reader import read_asc_fixed

def patched_run_generate_map(input_topo, output_mbtiles, bounds=None, cellsize=100,
                    min_zoom=1, max_zoom=12,
                    z_factor_slopes=1.4, z_factor_shades=2, azimuth=315, altitude=45,
                    output_resampled=None):
    """
    Run the map generation process with the given parameters and a fixed ASC reader.
    
    This is a patched version of the original run_generate_map function that uses
    our fixed read_asc_fixed function.
    """
    print("Reading topo file:", input_topo)
    header, data = read_asc_fixed(input_topo)
    print("Topo header:", header)

    # If a GeoJSON file is provided, use it to subset the DEM and to obtain the
    # geographic bounding box for tile downloads.
    if bounds:
        print("GeoJSON for bounds provided. Performing subset processing from the .asc file.")
        # Use calculate_bbox_from_geojson from the mbtile module.
        geojson_bbox = calculate_bbox_from_geojson(bounds)
        # The helper returns [min_lat, min_lon, max_lat, max_lon].
        # For clipping, we need to reorder it as (min_lon, min_lat, max_lon, max_lat):
        subset_bounds = (geojson_bbox[1], geojson_bbox[0], geojson_bbox[3], geojson_bbox[2])
        print("Using subset bounds for DEM processing:", subset_bounds)
        new_dem, dem_transform, _ = resample_to_metric(header, data, cellsize_new=cellsize, subset_bounds=subset_bounds)
        # Use the original GeoJSON bbox (which is in geographic coordinates) for tile downloads.
        tile_bbox = (geojson_bbox[0], geojson_bbox[1], geojson_bbox[2], geojson_bbox[3])
    else:
        print("No GeoJSON bounds provided; processing full DEM.")
        new_dem, dem_transform, bbox_3857 = resample_to_metric(header, data, cellsize_new=cellsize)
        # Convert metric bbox (EPSG:3857) to geographic (EPSG:4326)
        transformer_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        min_x, min_y, max_x, max_y = bbox_3857
        lon_min, lat_min = transformer_inv.transform(min_x, min_y)
        lon_max, lat_max = transformer_inv.transform(max_x, max_y)
        # Ensure that min values are less than max values.
        tile_bbox = (min(lat_min, lat_max), min(lon_min, lon_max),
                     max(lat_min, lat_max), max(lon_min, lon_max))
        print("Derived tile bounds from DEM:", tile_bbox)

    print(f"Resampled DEM: shape = {new_dem.shape}, transform = {dem_transform}")

    if output_resampled:
        x_origin, y_origin, cellsize_val, ncols, nrows = dem_transform
        xllcorner = x_origin
        yllcorner = y_origin - nrows * cellsize_val
        with open(output_resampled, 'w') as f:
            f.write(f"ncols {ncols}\n")
            f.write(f"nrows {nrows}\n")
            f.write(f"xllcorner {xllcorner}\n")
            f.write(f"yllcorner {yllcorner}\n")
            f.write(f"cellsize {cellsize_val}\n")
            f.write("NODATA_value -9999\n")
            np.savetxt(f, new_dem, fmt="%.2f")
        print(f"Resampled DEM written to {output_resampled}")

    print("Computing hillshade...")
    standard_hillshade = compute_hillshade(new_dem, cellsize, azimuth=azimuth, altitude=altitude, z_factor_shades=z_factor_shades)
    slope_map = compute_normalized_slope(new_dem, cellsize, z_factor_slopes=z_factor_slopes)
    inverted_slope = 255 - slope_map
    composite = combine_images(standard_hillshade, inverted_slope)
    print("Composite hillshade computed.")

    print("Generating intermediate hillshade MBTiles...")
    temp_hillshade_mbtiles = tempfile.NamedTemporaryFile(suffix=".mbtiles", delete=False)
    hillshade_mbtiles_path = temp_hillshade_mbtiles.name
    temp_hillshade_mbtiles.close()
    generate_mbtiles(composite, dem_transform, min_zoom, max_zoom, hillshade_mbtiles_path)
    print("Intermediate hillshade MBTiles generated at", hillshade_mbtiles_path)

    print("Downloading OSM tiles and combining with hillshade...")
    # Pass the geographic tile_bbox so that deg2num works correctly.
    download_and_combine_region(tile_bbox, min_zoom, max_zoom, output_mbtiles, hillshade_mbtiles_path)
    print("Final combined MBTiles saved to", output_mbtiles)

    os.remove(hillshade_mbtiles_path)
    print("Temporary hillshade MBTiles removed.")

def main():
    parser = argparse.ArgumentParser(
        description="Generate a combined OSM and hillshade MBTiles map from an input topo .asc file."
    )
    parser.add_argument("input_topo", help="Input DEM file (ASCII .asc in EPSG:4326)")
    parser.add_argument("output_mbtiles", help="Output combined MBTiles file")
    parser.add_argument("--bounds", help="GeoJSON file defining bounds (optional)")
    parser.add_argument("--cellsize", type=float, default=100,
                        help="Target cellsize in meters for resampling (default: 100)")
    parser.add_argument("--min_zoom", type=int, default=1,
                        help="Minimum zoom level (default: 1)")
    parser.add_argument("--max_zoom", type=int, default=12,
                        help="Maximum zoom level (default: 12)")
    parser.add_argument("--z_factor", type=float, default=1.4,
                        help="Z-factor to scale elevation values for hillshade (default: 1.4)")
    parser.add_argument("--azimuth", type=float, default=315,
                        help="Sun azimuth angle in degrees for hillshade (default: 315)")
    parser.add_argument("--altitude", type=float, default=45,
                        help="Sun altitude angle in degrees for hillshade (default: 45)")
    parser.add_argument("--output_resampled", help="Optional output path for the resampled DEM as ASCII")
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output_mbtiles), exist_ok=True)

    # Call our patched version with the correct parameter names
    patched_run_generate_map(
        args.input_topo,
        args.output_mbtiles,
        bounds=args.bounds,
        cellsize=args.cellsize,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        z_factor_slopes=args.z_factor,  # Correct parameter name
        z_factor_shades=args.z_factor * 1.43,  # Default ratio from original code
        azimuth=args.azimuth,
        altitude=args.altitude,
        output_resampled=args.output_resampled
    )

if __name__ == "__main__":
    main() 