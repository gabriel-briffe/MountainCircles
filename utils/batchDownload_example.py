#!/usr/bin/env python
"""
Example usage of the batchDownload.py utility.

This script shows examples of how to use the batchDownload.py utility to download
elevation data from OpenTopography API for different regions.
"""

import os
import sys
from utils.batchDownload import batch_download, merge_ascii_grids

def example_download_alps():
    """
    Example: Download elevation data for a region in the Alps.
    Uses SRTM_GL3 (90m) dataset.
    """
    print("Example 1: Downloading a region in the Alps (SRTM_GL3)")
    
    # Define the region (Swiss Alps)
    north = 47.0  # Northern boundary (latitude)
    south = 46.0  # Southern boundary (latitude)
    east = 9.0    # Eastern boundary (longitude)
    west = 8.0    # Western boundary (longitude)
    
    # Output directory
    output_dir = "data/elevation/alps"
    os.makedirs(output_dir, exist_ok=True)
    
    # Download data in chunks
    downloaded_files = batch_download(
        north=north,
        south=south,
        east=east,
        west=west,
        dataset="SRTM_GL3",
        output_dir=output_dir,
        chunk_size=0.5,    # Split into 0.5 degree chunks
        output_format="AAIGrid",
        max_workers=4      # Use 4 concurrent downloads
    )
    
    # Merge the downloaded chunks
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Merging them...")
        merge_ascii_grids(downloaded_files, os.path.join(output_dir, "alps_merged.asc"))

def example_download_higher_resolution():
    """
    Example: Download higher resolution data for a smaller region.
    Uses SRTM_GL1 (30m) dataset.
    """
    print("Example 2: Downloading higher resolution data (SRTM_GL1)")
    
    # Define a smaller region (around Mont Blanc)
    north = 46.0  # Northern boundary (latitude)
    south = 45.8  # Southern boundary (latitude)
    east = 7.0    # Eastern boundary (longitude)
    west = 6.8    # Western boundary (longitude)
    
    # Output directory
    output_dir = "data/elevation/mont_blanc"
    os.makedirs(output_dir, exist_ok=True)
    
    # Download data in chunks
    downloaded_files = batch_download(
        north=north,
        south=south,
        east=east,
        west=west,
        dataset="SRTM_GL1",     # Higher resolution dataset
        output_dir=output_dir,
        chunk_size=0.1,         # Smaller chunks for higher resolution
        output_format="AAIGrid"
    )
    
    # Merge the downloaded chunks
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Merging them...")
        merge_ascii_grids(downloaded_files, os.path.join(output_dir, "mont_blanc_merged.asc"))

def example_download_custom_region():
    """
    Example: Download data for a custom region specified by command line arguments.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Download elevation data for a custom region")
    parser.add_argument("--north", type=float, required=True, help="Northern boundary (latitude)")
    parser.add_argument("--south", type=float, required=True, help="Southern boundary (latitude)")
    parser.add_argument("--east", type=float, required=True, help="Eastern boundary (longitude)")
    parser.add_argument("--west", type=float, required=True, help="Western boundary (longitude)")
    parser.add_argument("--dataset", type=str, default="SRTM_GL3", 
                        help="Dataset identifier (default: SRTM_GL3)")
    parser.add_argument("--output_dir", type=str, default="data/elevation/custom", 
                        help="Directory to save the downloaded data")
    parser.add_argument("--chunk_size", type=float, default=0.5, 
                        help="Size of each chunk in degrees (default: 0.5)")
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Download data
    print(f"Downloading data for region: North: {args.north}, South: {args.south}, "
          f"East: {args.east}, West: {args.west}")
    
    downloaded_files = batch_download(
        north=args.north,
        south=args.south,
        east=args.east,
        west=args.west,
        dataset=args.dataset,
        output_dir=args.output_dir,
        chunk_size=args.chunk_size,
        output_format="AAIGrid"
    )
    
    # Merge the downloaded chunks
    if downloaded_files:
        output_file = os.path.join(args.output_dir, "merged.asc")
        print(f"Downloaded {len(downloaded_files)} files. Merging them into {output_file}...")
        merge_ascii_grids(downloaded_files, output_file)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--custom":
        # Remove the "--custom" argument for the parser
        sys.argv.pop(1)
        example_download_custom_region()
    elif len(sys.argv) > 1 and sys.argv[1] == "--alps":
        example_download_alps()
    elif len(sys.argv) > 1 and sys.argv[1] == "--mont-blanc":
        example_download_higher_resolution()
    else:
        print("Please specify which example to run:")
        print("  --alps        Download elevation data for the Swiss Alps")
        print("  --mont-blanc  Download high-resolution data for Mont Blanc")
        print("  --custom      Download data for a custom region (requires additional arguments)")
        print("")
        print("Example for custom region:")
        print("  python utils/batchDownload_example.py --custom --north 47.0 --south 46.0 --east 9.0 --west 8.0 --output_dir data/elevation/custom") 