#!/usr/bin/env python
"""
Utility to merge multiple ASCII grid files into a single file.

This script handles the merging of ASC files downloaded from the OpenTopography API.
It includes special handling for potential size mismatches between files.

Usage:
    python utils/merge_grids.py --input_dir data/elevation/alos3d_test --output_file data/elevation/alos3d_merged/merged_region.asc
"""

import os
import argparse
import numpy as np
import glob
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ASC Grid Merger")

def read_asc_header(filepath):
    """
    Read the header of an ASC file.
    
    Args:
        filepath (str): Path to the ASC file
        
    Returns:
        dict: Header information
    """
    header = {}
    with open(filepath, 'r') as f:
        for _ in range(6):
            line = f.readline().strip()
            if not line:
                continue
            key, value = line.split(None, 1)
            key_lower = key.lower()
            if key_lower in ["ncols", "nrows"]:
                header[key_lower] = int(value)
            elif key_lower in ["xllcorner", "yllcorner", "cellsize"]:
                header[key_lower] = float(value)
            elif key_lower.startswith("nodata"):
                header["nodata_value"] = float(value)
    
    return header

def read_asc_data(filepath, header=None):
    """
    Read the data from an ASC file.
    
    Args:
        filepath (str): Path to the ASC file
        header (dict, optional): Header information if already read
        
    Returns:
        tuple: (header, data)
    """
    if header is None:
        header = read_asc_header(filepath)
    
    # Skip the header and read the data
    data = np.loadtxt(filepath, skiprows=6)
    
    return header, data

def extract_coords_from_filename(filename):
    """
    Extract coordinates from the filename.
    
    Args:
        filename (str): Filename with format "dataset_south_north_west_east.asc"
        
    Returns:
        tuple: (south, north, west, east)
    """
    parts = filename.split('_')
    south = float(parts[1])
    north = float(parts[2])
    west = float(parts[3])
    east = float(parts[4].split('.')[0])
    
    return south, north, west, east

def merge_asc_files(input_dir, output_file):
    """
    Merge multiple ASC files into a single file.
    
    Args:
        input_dir (str): Directory containing ASC files
        output_file (str): Path to the output merged ASC file
        
    Returns:
        bool: True if merge was successful, False otherwise
    """
    try:
        # Find all ASC files in the input directory
        asc_files = glob.glob(os.path.join(input_dir, "*.asc"))
        if not asc_files:
            logger.error(f"No ASC files found in {input_dir}")
            return False
        
        logger.info(f"Found {len(asc_files)} ASC files to merge")
        
        # Extract metadata from filenames and read headers
        grids_info = []
        for file_path in asc_files:
            filename = os.path.basename(file_path)
            south, north, west, east = extract_coords_from_filename(filename)
            
            # Read header information
            header = read_asc_header(file_path)
            
            grids_info.append({
                'file': file_path,
                'south': south,
                'north': north,
                'west': west,
                'east': east,
                'header': header
            })
        
        # Determine the extent of the merged grid
        overall_south = min(grid['south'] for grid in grids_info)
        overall_north = max(grid['north'] for grid in grids_info)
        overall_west = min(grid['west'] for grid in grids_info)
        overall_east = max(grid['east'] for grid in grids_info)
        
        logger.info(f"Overall extent: N:{overall_north}, S:{overall_south}, E:{overall_east}, W:{overall_west}")
        
        # Get cellsize (assuming all chunks have the same cellsize)
        cellsize = grids_info[0]['header']['cellsize']
        
        # Calculate dimensions of the merged grid
        # For latitude, 1 degree ≈ 111 km
        # For longitude, 1 degree at the equator ≈ 111 km, but varies with latitude
        # We'll use the cellsize from the ASC file which is in degrees
        
        # Calculate the number of cells in each direction
        lat_cells = int(round((overall_north - overall_south) / cellsize))
        lon_cells = int(round((overall_east - overall_west) / cellsize))
        
        # Create a merged grid with the calculated dimensions
        nodata_value = grids_info[0]['header'].get('nodata_value', -9999)
        merged_data = np.full((lat_cells, lon_cells), nodata_value, dtype=np.float32)
        
        logger.info(f"Created merged grid with dimensions: {lat_cells} rows x {lon_cells} columns")
        
        # Process each grid file
        for grid_info in tqdm(grids_info, desc="Merging grids"):
            file_path = grid_info['file']
            
            try:
                # Calculate the position of this grid in the merged grid
                row_offset = int(round((overall_north - grid_info['north']) / cellsize))
                col_offset = int(round((grid_info['west'] - overall_west) / cellsize))
                
                # Read data
                _, grid_data = read_asc_data(file_path, grid_info['header'])
                
                grid_rows, grid_cols = grid_data.shape
                
                # Calculate the end positions
                row_end = row_offset + grid_rows
                col_end = col_offset + grid_cols
                
                # Ensure we don't exceed the dimensions of the merged grid
                if row_end > lat_cells:
                    logger.warning(f"Grid {file_path} exceeds merged grid dimensions (rows)")
                    grid_data = grid_data[:lat_cells-row_offset, :]
                    row_end = lat_cells
                
                if col_end > lon_cells:
                    logger.warning(f"Grid {file_path} exceeds merged grid dimensions (columns)")
                    grid_data = grid_data[:, :lon_cells-col_offset]
                    col_end = lon_cells
                
                # Create a specific mask for this grid to handle potential size mismatches
                mask = merged_data[row_offset:row_end, col_offset:col_end] == nodata_value
                
                # Only update cells that currently contain NoData values
                merged_slice = merged_data[row_offset:row_end, col_offset:col_end]
                grid_data_slice = grid_data[:merged_slice.shape[0], :merged_slice.shape[1]]
                merged_slice[mask] = grid_data_slice[mask]
                
                logger.debug(f"Added grid {file_path} at position ({row_offset}, {col_offset})")
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                continue
        
        # Write the merged grid to output file
        logger.info(f"Writing merged grid to {output_file}")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(f"ncols {lon_cells}\n")
            f.write(f"nrows {lat_cells}\n")
            f.write(f"xllcorner {overall_west}\n")
            f.write(f"yllcorner {overall_south}\n")
            f.write(f"cellsize {cellsize}\n")
            f.write(f"NODATA_value {int(nodata_value)}\n")
            
            # Write the data row by row to avoid memory issues
            for row in merged_data:
                row_str = ' '.join(f"{val:.6f}" if val != nodata_value else f"{int(nodata_value)}" for val in row)
                f.write(row_str + '\n')
        
        logger.info("Merge completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error merging ASCII grids: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    parser = argparse.ArgumentParser(description="Merge multiple ASC grid files into a single file")
    
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing ASC files to merge")
    parser.add_argument("--output_file", type=str, required=True, help="Path to save the merged ASC file")
    
    args = parser.parse_args()
    
    merge_asc_files(args.input_dir, args.output_file)

if __name__ == "__main__":
    main() 