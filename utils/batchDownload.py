#!/usr/bin/env python
"""
Batch Download utility for OpenTopography Global DEM API.

This script allows downloading elevation data from OpenTopography API for large regions
by splitting the area into smaller chunks and downloading them in Arc ASCII format.
The chunks can be later assembled into a single file.

API Documentation: https://portal.opentopography.org/apidocs/#/Public/getGlobalDem

Usage:
    python utils/batchDownload.py --north 47.5 --south 46.5 --east 12.5 --west 11.5 
                                  --dataset SRTM_GL3 --output_dir data/elevation 
                                  --chunk_size 0.5 --format AAIGrid

Available datasets:
    - SRTM_GL3: SRTM GL3 (90m)
    - SRTM_GL1: SRTM GL1 (30m)
    - SRTM_GL1_E: SRTM GL1 Ellipsoidal (30m)
    - AW3D30: ALOS World 3D 30m
    - AW3D30_E: ALOS World 3D Ellipsoidal 30m
    - SRTM15Plus: SRTM15+ (450m)
    - NASADEM: NASADEM (30m)
    - COP30: Copernicus DEM 30m
    - COP90: Copernicus DEM 90m
"""

import os
import argparse
import requests
import time
import numpy as np
import concurrent.futures
from urllib.parse import urlencode
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OpenTopo Batch Downloader")

# API URL
OPENTOPO_API_URL = "https://portal.opentopography.org/API/globaldem"

def download_chunk(north, south, east, west, dataset, output_file, output_format="AAIGrid", api_key=None):
    """
    Download a single chunk of elevation data from OpenTopography API.
    
    Args:
        north (float): Northern boundary (latitude)
        south (float): Southern boundary (latitude)
        east (float): Eastern boundary (longitude)
        west (float): Western boundary (longitude)
        dataset (str): Dataset identifier (e.g., SRTM_GL3)
        output_file (str): Path to save the downloaded data
        output_format (str): Output format (default: AAIGrid)
        api_key (str, optional): API key for OpenTopography
        
    Returns:
        bool: True if download was successful or file already exists, False otherwise
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Check if file already exists and has content
    if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
        logger.info(f"Skipping download, file already exists: {output_file}")
        return True
    
    # Build request parameters
    params = {
        "demtype": dataset,
        "south": south,
        "north": north,
        "west": west,
        "east": east,
        "outputFormat": output_format
    }
    
    # Add API key if provided
    if api_key:
        params["API_Key"] = api_key
    
    try:
        # Make API request
        response = requests.get(OPENTOPO_API_URL, params=params, stream=True)
        
        # Check if request was successful
        if response.status_code == 200:
            # Write the data to file
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Check if file is not empty and contains actual data
            if os.path.getsize(output_file) > 100:  # Basic check to ensure file has content
                logger.info(f"Successfully downloaded chunk: {output_file}")
                return True
            else:
                logger.error(f"Downloaded file is empty or too small: {output_file}")
                os.remove(output_file)  # Remove empty file
                return False
        else:
            logger.error(f"API request failed with status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error downloading chunk {output_file}: {str(e)}")
        return False

def batch_download(north, south, east, west, dataset, output_dir, chunk_size=0.5, 
                  output_format="AAIGrid", api_key=None, max_workers=4, retry_attempts=3):
    """
    Download elevation data for a large region by splitting it into smaller chunks.
    
    Args:
        north (float): Northern boundary (latitude)
        south (float): Southern boundary (latitude)
        east (float): Eastern boundary (longitude)
        west (float): Western boundary (longitude)
        dataset (str): Dataset identifier (e.g., SRTM_GL3)
        output_dir (str): Directory to save the downloaded data
        chunk_size (float): Size of each chunk in degrees (default: 0.5)
        output_format (str): Output format (default: AAIGrid)
        api_key (str, optional): API key for OpenTopography
        max_workers (int): Maximum number of concurrent downloads
        retry_attempts (int): Number of retry attempts for failed downloads
        
    Returns:
        list: List of paths to the downloaded files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate chunks
    lat_chunks = np.arange(south, north + chunk_size, chunk_size)
    lon_chunks = np.arange(west, east + chunk_size, chunk_size)
    
    # Ensure we don't exceed the original bounds
    lat_chunks = lat_chunks[lat_chunks <= north]
    lon_chunks = lon_chunks[lon_chunks <= east]
    
    # Create download tasks
    download_tasks = []
    
    for i in range(len(lat_chunks) - 1):
        for j in range(len(lon_chunks) - 1):
            chunk_south = lat_chunks[i]
            chunk_north = lat_chunks[i + 1]
            chunk_west = lon_chunks[j]
            chunk_east = lon_chunks[j + 1]
            
            # Generate filename (include coordinates for easy reassembly)
            filename = f"{dataset}_{chunk_south:.4f}_{chunk_north:.4f}_{chunk_west:.4f}_{chunk_east:.4f}.asc"
            output_file = os.path.join(output_dir, filename)
            
            # Add task
            download_tasks.append({
                "north": chunk_north,
                "south": chunk_south,
                "east": chunk_east,
                "west": chunk_west,
                "dataset": dataset,
                "output_file": output_file,
                "output_format": output_format,
                "api_key": api_key
            })
    
    # Execute downloads with retry logic
    successful_downloads = []
    failed_downloads = []
    
    logger.info(f"Starting batch download of {len(download_tasks)} chunks...")
    
    # Execute in parallel with a progress bar
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_chunk, **task): task for task in download_tasks}
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), 
                          desc="Downloading chunks"):
            task = futures[future]
            try:
                success = future.result()
                if success:
                    successful_downloads.append(task["output_file"])
                else:
                    failed_downloads.append(task)
            except Exception as e:
                logger.error(f"Error processing task {task['output_file']}: {str(e)}")
                failed_downloads.append(task)
    
    # Retry failed downloads
    if failed_downloads and retry_attempts > 0:
        logger.info(f"Retrying {len(failed_downloads)} failed downloads...")
        retry_results = batch_download(
            north, south, east, west, dataset, output_dir, chunk_size,
            output_format, api_key, max_workers, retry_attempts - 1
        )
        successful_downloads.extend(retry_results)
    
    logger.info(f"Download completed: {len(successful_downloads)} successful, {len(failed_downloads)} failed")
    
    return successful_downloads

def merge_ascii_grids(input_files, output_file):
    """
    Merge multiple ASCII grid files into a single file.
    
    Args:
        input_files (list): List of input ASC file paths
        output_file (str): Path to the output merged ASC file
        
    Returns:
        bool: True if merge was successful, False otherwise
    """
    if not input_files:
        logger.error("No input files provided for merging")
        return False
    
    try:
        # Extract metadata from filenames to determine grid arrangement
        grids_info = []
        for file_path in input_files:
            # Parse coordinates from filename
            filename = os.path.basename(file_path)
            parts = filename.split('_')
            south = float(parts[1])
            north = float(parts[2])
            west = float(parts[3])
            east = float(parts[4].split('.')[0])
            
            # Read header information from the file
            with open(file_path, 'r') as f:
                header = {}
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
        
        # Get cellsize (assuming all chunks have the same cellsize)
        cellsize = grids_info[0]['header']['cellsize']
        
        # Calculate number of rows and columns for the merged grid
        # Convert geographic coordinates to number of cells
        lat_diff = overall_north - overall_south
        lon_diff = overall_east - overall_west
        
        # Calculate rows and columns
        nrows = int(round(lat_diff / cellsize))
        ncols = int(round(lon_diff / cellsize))
        
        # Create an array for the merged grid (filled with NoData values)
        nodata_value = grids_info[0]['header'].get('nodata_value', -9999)
        merged_data = np.full((nrows, ncols), nodata_value, dtype=np.float32)
        
        logger.info(f"Creating merged grid with dimensions: {nrows} rows x {ncols} columns")
        
        # Read and place each grid in the merged grid
        for grid_info in tqdm(grids_info, desc="Merging grids"):
            file_path = grid_info['file']
            
            # Calculate the position of this grid in the merged grid
            row_offset = int(round((overall_north - grid_info['north']) / cellsize))
            col_offset = int(round((grid_info['west'] - overall_west) / cellsize))
            
            # Read the data
            header = grid_info['header']
            grid_nrows = header['nrows']
            grid_ncols = header['ncols']
            
            # Skip header and read data
            grid_data = np.loadtxt(file_path, skiprows=6)
            
            # Place this grid in the merged grid
            row_end = row_offset + grid_nrows
            col_end = col_offset + grid_ncols
            
            # Ensure we don't exceed the dimensions of the merged grid
            if row_end > nrows:
                logger.warning(f"Grid {file_path} exceeds merged grid dimensions (rows)")
                grid_data = grid_data[:nrows-row_offset, :]
                row_end = nrows
            
            if col_end > ncols:
                logger.warning(f"Grid {file_path} exceeds merged grid dimensions (columns)")
                grid_data = grid_data[:, :ncols-col_offset]
                col_end = ncols
            
            # Copy the data, but only where the target cells contain NoData
            # This handles overlapping areas (later grids don't overwrite data from earlier grids)
            mask = merged_data[row_offset:row_end, col_offset:col_end] == nodata_value
            merged_data[row_offset:row_end, col_offset:col_end][mask] = grid_data[mask]
        
        # Write the merged grid to file
        logger.info(f"Writing merged grid to {output_file}")
        with open(output_file, 'w') as f:
            f.write(f"ncols {ncols}\n")
            f.write(f"nrows {nrows}\n")
            f.write(f"xllcorner {overall_west}\n")
            f.write(f"yllcorner {overall_south}\n")
            f.write(f"cellsize {cellsize}\n")
            f.write(f"NODATA_value {nodata_value}\n")
            
            # Write the data (row by row to avoid loading everything into memory)
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
    parser = argparse.ArgumentParser(description="Batch download elevation data from OpenTopography API")
    
    # Region boundaries
    parser.add_argument("--north", type=float, required=True, help="Northern boundary (latitude)")
    parser.add_argument("--south", type=float, required=True, help="Southern boundary (latitude)")
    parser.add_argument("--east", type=float, required=True, help="Eastern boundary (longitude)")
    parser.add_argument("--west", type=float, required=True, help="Western boundary (longitude)")
    
    # Dataset and output options
    parser.add_argument("--dataset", type=str, default="SRTM_GL3", 
                        help="Dataset identifier (default: SRTM_GL3)")
    parser.add_argument("--output_dir", type=str, required=True, 
                        help="Directory to save the downloaded data")
    parser.add_argument("--chunk_size", type=float, default=0.5, 
                        help="Size of each chunk in degrees (default: 0.5)")
    parser.add_argument("--format", type=str, default="AAIGrid", 
                        help="Output format (default: AAIGrid)")
    
    # API and download options
    parser.add_argument("--api_key", type=str, help="API key for OpenTopography (optional)")
    parser.add_argument("--max_workers", type=int, default=4, 
                        help="Maximum number of concurrent downloads (default: 4)")
    parser.add_argument("--retry_attempts", type=int, default=3, 
                        help="Number of retry attempts for failed downloads (default: 3)")
    
    # Merge option
    parser.add_argument("--merge", action="store_true", 
                        help="Merge downloaded chunks into a single file")
    parser.add_argument("--output_file", type=str, 
                        help="Output file for merged data (required if --merge is specified)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.north <= args.south:
        logger.error("Northern boundary must be greater than southern boundary")
        return
    
    if args.east <= args.west:
        logger.error("Eastern boundary must be greater than western boundary")
        return
    
    if args.merge and not args.output_file:
        logger.error("--output_file is required when --merge is specified")
        return
    
    # Download data
    downloaded_files = batch_download(
        north=args.north,
        south=args.south,
        east=args.east,
        west=args.west,
        dataset=args.dataset,
        output_dir=args.output_dir,
        chunk_size=args.chunk_size,
        output_format=args.format,
        api_key=args.api_key,
        max_workers=args.max_workers,
        retry_attempts=args.retry_attempts
    )
    
    # Merge if requested
    if args.merge and downloaded_files:
        logger.info(f"Merging {len(downloaded_files)} files into {args.output_file}...")
        merge_success = merge_ascii_grids(downloaded_files, args.output_file)
        if merge_success:
            logger.info("Merge completed successfully")
        else:
            logger.error("Failed to merge files")
    
    logger.info("Batch download process completed")

if __name__ == "__main__":
    main() 