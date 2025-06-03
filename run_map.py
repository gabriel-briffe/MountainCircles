#!/usr/bin/env python
"""
Wrapper script for generate_map.py that uses the correct parameter names.
This script doesn't modify the original code.

Usage:
    python run_map.py input_topo.asc output.mbtiles [--bounds file.geojson]
           [--cellsize 100] [--min_zoom 1] [--max_zoom 12] [--z_factor 1.4]
           [--azimuth 315] [--altitude 45] [--output_resampled resampled.asc]
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import function from utils module
from utils.generate_map import run_generate_map

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

    # Call run_generate_map with the correct parameter names
    # Note: z_factor is passed as z_factor_slopes
    run_generate_map(
        args.input_topo,
        args.output_mbtiles,
        bounds=args.bounds,
        cellsize=args.cellsize,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        z_factor_slopes=args.z_factor,  # Correct parameter name
        azimuth=args.azimuth,
        altitude=args.altitude,
        output_resampled=args.output_resampled
    )

if __name__ == "__main__":
    main() 