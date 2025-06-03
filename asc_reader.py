#!/usr/bin/env python
"""
Standalone script to read an ASC file with proper header handling.
This fixes the issue in the original read_asc function.
"""

import numpy as np
import sys
import os

def read_asc_fixed(filepath):
    """
    Reads an Arc/Info ASCII grid file with proper header handling.
    
    Expects a header of 6 lines (ncols, nrows, xllcorner, yllcorner, cellsize,
    NODATA_value) followed by the data rows.
    
    Returns:
        header (dict): Keys include 'ncols', 'nrows', 'xllcorner', 'yllcorner',
                       'cellsize', and 'nodata_value'.
        data (np.ndarray): A 2D numpy array (shape = (nrows, ncols)).
                         Note: the first row in the file corresponds to the NORTH.
    """
    header = {}
    with open(filepath, "r") as f:
        # Read the header (properly read all 6 lines)
        for _ in range(6):  # Ensure we read all 6 lines
            line = f.readline().strip()
            if not line:
                continue
            parts = line.split(None, 1)  # Split on first whitespace
            if len(parts) != 2:
                continue
                
            key, value = parts
            key_lower = key.lower()
            # ncols and nrows are integers
            if key_lower in ["ncols", "nrows"]:
                header[key_lower] = int(value)
            elif key_lower in ["xllcorner", "yllcorner", "cellsize"]:
                header[key_lower] = float(value)
            elif key_lower.startswith("nodata"):
                header["nodata_value"] = float(value)
        
        # Read the data as a numpy array
        data = np.loadtxt(f)
    
    return header, data

def process_asc(input_path, output_path=None):
    """
    Process an ASC file, read it with the fixed function, and optionally save a cleaned version.
    
    Args:
        input_path (str): Path to the input ASC file
        output_path (str, optional): Path to save a cleaned ASC file
        
    Returns:
        tuple: (header, data)
    """
    print(f"Reading ASC file: {input_path}")
    header, data = read_asc_fixed(input_path)
    print("ASC header:")
    for key, value in header.items():
        print(f"  {key}: {value}")
    print(f"Data shape: {data.shape}")
    
    if output_path:
        print(f"Writing cleaned ASC file to: {output_path}")
        with open(output_path, 'w') as f:
            f.write(f"ncols {header['ncols']}\n")
            f.write(f"nrows {header['nrows']}\n")
            f.write(f"xllcorner {header['xllcorner']}\n")
            f.write(f"yllcorner {header['yllcorner']}\n")
            f.write(f"cellsize {header['cellsize']}\n")
            f.write(f"NODATA_value {int(header['nodata_value'])}\n")
            
            # Write the data row by row
            for row in data:
                row_str = ' '.join(f"{val:.2f}" if val != header['nodata_value'] else f"{int(header['nodata_value'])}" for val in row)
                f.write(row_str + '\n')
    
    return header, data

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python asc_reader.py input.asc [output.asc]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_asc(input_path, output_path) 