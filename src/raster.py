import os
import numpy as np
from src.shortcuts import normJoin
from src.postprocess import postProcess, postProcess2
from src.logging import log_output


def read_asc(file_path):
    """Reads an .asc file into a numpy array with metadata."""
    with open(file_path, 'r') as file:
        ncols = int(next(file).split()[1])
        nrows = int(next(file).split()[1])
        xllcorner = float(next(file).split()[1])
        yllcorner = float(next(file).split()[1])
        cellsize = float(next(file).split()[1])
        nodata_value = float(next(file).split()[1])
        
        data = np.genfromtxt(file, dtype=float)
        
        return data, ncols, nrows, xllcorner, yllcorner, cellsize, nodata_value



def write_asc(data, filename, ncols, nrows, xllcorner, yllcorner, cellsize, nodata_value):
    """Writes a numpy array to an .asc file."""
    with open(filename, 'w') as file:
        file.write(f'ncols {ncols}\n')
        file.write(f'nrows {nrows}\n')
        file.write(f'xllcorner {xllcorner}\n')
        file.write(f'yllcorner {yllcorner}\n')
        file.write(f'cellsize {cellsize}\n')
        file.write(f'NODATA_value {nodata_value}\n')
        for row in data:
            row_str = ' '.join(str(val if not np.isnan(val) else nodata_value) for val in row)
            file.write(row_str + '\n')



def align_rasters(rasters, cellsize):
    """Aligns rasters into a common grid by updating only where data exists,
    using pixel centers.
    
    Each raster header is assumed to be:
      (data, ncols, nrows, xllcorner, yllcorner, cellsize, nodata_value)
    
    For each raster, the pixel centers are:
      x_center = xllcorner + (col + 0.5) * cellsize
      y_center = yllcorner + (row + 0.5) * cellsize
      
    We build the global grid in pixel–center space and then compute the merged 
    grid's lower left pixel edge as new_xllcorner = (min_x_center – cellsize/2)
    and similarly for y.
    """
    # Determine the global pixel center extents for all rasters
    min_x_center = min(raster[3] + cellsize / 2 for raster in rasters)
    max_x_center = max(raster[3] + (raster[1] - 0.5) * cellsize for raster in rasters)
    min_y_center = min(raster[4] + cellsize / 2 for raster in rasters)
    max_y_center = max(raster[4] + (raster[2] - 0.5) * cellsize for raster in rasters)
    
    # Compute total columns and rows; note the addition of 1 to include the end pixel
    ncols = int(round((max_x_center - min_x_center) / cellsize)) + 1
    nrows = int(round((max_y_center - min_y_center) / cellsize)) + 1
    
    # Compute new lower–left corner (i.e. edge) from pixel center information
    new_xllcorner = min_x_center - cellsize / 2
    new_yllcorner = min_y_center - cellsize / 2
    
    nodata_value = rasters[0][6]
    aligned = np.full((nrows, ncols), nodata_value)
    
    # Place each sub–raster into the global grid using pixel–center coordinates.
    for data, ncols_sub, nrows_sub, xllcorner, yllcorner, _, _ in rasters:
        sub_min_x_center = xllcorner + cellsize / 2
        sub_max_x_center = xllcorner + (ncols_sub - 0.5) * cellsize
        sub_min_y_center = yllcorner + cellsize / 2
        sub_max_y_center = yllcorner + (nrows_sub - 0.5) * cellsize
        
        start_col = int(round((sub_min_x_center - min_x_center) / cellsize))
        # For rows, row 0 corresponds to max_y_center so we subtract.
        start_row = int(round((max_y_center - sub_max_y_center) / cellsize))
        
        end_row = start_row + nrows_sub
        end_col = start_col + ncols_sub
        
        aligned_slice = aligned[start_row:end_row, start_col:end_col]
        aligned[start_row:end_row, start_col:end_col] = np.minimum(data, aligned_slice)
    
    return aligned, new_xllcorner, new_yllcorner, nrows, ncols


def merge_output_rasters(config, output_filename, sectors_filename, output_queue=None):
    log_output("merging final raster", output_queue)
    nodata_value = float(config.max_altitude)
    
    """Merges all output_sub.asc files from airfield directories in chunks,
    using pixel centers.
    """
    # First, read all headers to get the extent of all rasters
    all_headers = []
    for root, _, files in os.walk(config.calculation_folder_path):
        for file in files:
            if file == 'output_sub.asc':
                path = normJoin(root, file)
                with open(path, 'r') as file_obj:
                    ncols = int(next(file_obj).split()[1])
                    nrows = int(next(file_obj).split()[1])
                    xllcorner = float(next(file_obj).split()[1])
                    yllcorner = float(next(file_obj).split()[1])
                    cellsize = float(next(file_obj).split()[1])
                    # We don't need nodata_value from the file since we're using the one provided
                    all_headers.append((path, ncols, nrows, xllcorner, yllcorner, cellsize))
    
    if not all_headers:
        log_output("No output_sub.asc files found to merge.", output_queue)
        return
    
    cellsize = all_headers[0][5]
    
    # Determine the global pixel center extent from all headers
    min_x_center = min(header[3] + cellsize / 2 for header in all_headers)
    max_x_center = max(header[3] + (header[1] - 0.5) * cellsize for header in all_headers)
    min_y_center = min(header[4] + cellsize / 2 for header in all_headers)
    max_y_center = max(header[4] + (header[2] - 0.5) * cellsize for header in all_headers)
    
    ncols_total = int(round((max_x_center - min_x_center) / cellsize)) + 1
    nrows_total = int(round((max_y_center - min_y_center) / cellsize)) + 1
    
    # Compute the new lower–left corner for the merged grid
    new_xllcorner = min_x_center - cellsize / 2
    new_yllcorner = min_y_center - cellsize / 2
    
    # Initialize the aligned arrays with nodata_value
    aligned = np.full((nrows_total, ncols_total), nodata_value)
    sectors = np.full((nrows_total, ncols_total), nodata_value)
    
    # Process each raster file one by one.
    sector = 0
    for path, ncols_sub, nrows_sub, xllcorner, yllcorner, cellsize in all_headers:
        log_output(f"aligning {path}", output_queue)
        
        sub_min_x_center = xllcorner + cellsize / 2
        sub_max_x_center = xllcorner + (ncols_sub - 0.5) * cellsize
        sub_min_y_center = yllcorner + cellsize / 2
        sub_max_y_center = yllcorner + (nrows_sub - 0.5) * cellsize
        
        start_col = int(round((sub_min_x_center - min_x_center) / cellsize))
        start_row = int(round((max_y_center - sub_max_y_center) / cellsize))
        
        end_row = start_row + nrows_sub
        end_col = start_col + ncols_sub
        
        # Add bounds checking
        if start_row < 0 or end_row > nrows_total or start_col < 0 or end_col > ncols_total:
            log_output(f"airfield local matrix going out of bound of reconstructed matrix, skipping: {path}", output_queue)
            continue  # Skip this file if out of bounds
        
        # Read the data in chunks to avoid memory issues
        with open(path, 'r') as file_obj:
            for _ in range(6):  # Skip header lines
                next(file_obj)
            
            for i, line in enumerate(file_obj):
                if i >= nrows_sub:
                    log_output("out of bounds", output_queue)
                    break  # Ensure we don't read beyond the specified number of rows
                
                row_data = np.fromstring(line, dtype=float, sep=' ')
                aligned_slice = aligned[start_row + i, start_col:end_col]
                sectors_slice = sectors[start_row + i, start_col:end_col]
                # Create a mask for where updates will occur
                update_mask = (row_data != nodata_value) & (row_data < aligned_slice)
                sectors_mask = (row_data != nodata_value) & (row_data < aligned_slice)
                sectors_reset = (row_data == 0)
                # Update aligned array and sectors accordingly
                aligned_slice[update_mask] = row_data[update_mask]
                sectors_slice[sectors_mask] = sector
                sectors_slice[sectors_reset] = nodata_value
        sector += 1
    
    # Set merged data to nodata_value where data equals zero
    log_output("removing ground from merged raster", output_queue)
    aligned[aligned == 0] = nodata_value
    
    # Write the merged raster using the computed lower-left pixel edge (new_xllcorner, new_yllcorner)
    output_path = config.merged_output_raster_path
    sectors_path = config.sectors_filepath
    log_output(f"writing final raster to {output_path}", output_queue)
    log_output(f"writing sector raster to {sectors_path}", output_queue)
    log_output("Done, writing final raster...", output_queue)
    write_asc(aligned, output_path, ncols_total, nrows_total, new_xllcorner, new_yllcorner, cellsize, nodata_value)
    log_output("Done, writing sector raster...", output_queue)
    write_asc(sectors, sectors_path, ncols_total, nrows_total, new_xllcorner, new_yllcorner, cellsize, nodata_value)
    log_output("Post processing final raster...", output_queue)
    
    postProcess(config.calculation_folder_path, config.calculation_folder_path, config, output_path, config.merged_output_name)


def merge_output_rasters2(config, output_filename, sectors_filename, output_queue=None):
    log_output("merging final raster", output_queue)
    nodata_value = float(config.max_altitude)
    
    """Merges all output_sub4326.asc files from airfield directories in chunks,
    using pixel centers.
    """
    # First, read all headers to get the extent of all rasters
    all_headers = []
    for root, _, files in os.walk(config.calculation_folder_path):
        for file in files:
            if file == 'output_sub4326.asc':
                path = normJoin(root, file)

                # Proceed with reading the header safely
                try:
                    with open(path, 'r', encoding='utf-8-sig') as file_obj:
                        ncols = int(next(file_obj).split()[1])
                        nrows = int(next(file_obj).split()[1])
                        xllcorner = float(next(file_obj).split()[1])
                        yllcorner = float(next(file_obj).split()[1])
                        cellsize = float(next(file_obj).split()[1])
                        all_headers.append((path, ncols, nrows, xllcorner, yllcorner, cellsize))
                except Exception as e:
                    log_output(f"Error reading header from {path}: {e}", output_queue)
    
    if not all_headers:
        log_output("No output_sub4326.asc files found to merge.", output_queue)
        return
    
    
    cellsize = all_headers[0][5]
    log_output(f"number of files to merge: {len(all_headers)}", output_queue)
    
    # Determine the global pixel center extent from all headers
    min_x_center = min(header[3] + cellsize / 2 for header in all_headers)
    max_x_center = max(header[3] + (header[1] - 0.5) * cellsize for header in all_headers)
    min_y_center = min(header[4] + cellsize / 2 for header in all_headers)
    max_y_center = max(header[4] + (header[2] - 0.5) * cellsize for header in all_headers)
    
    ncols_total = int(round((max_x_center - min_x_center) / cellsize)) + 1
    nrows_total = int(round((max_y_center - min_y_center) / cellsize)) + 1
    
    new_xllcorner = min_x_center - cellsize / 2
    new_yllcorner = min_y_center - cellsize / 2
    
    aligned = np.full((nrows_total, ncols_total), nodata_value)
    sectors = np.full((nrows_total, ncols_total), nodata_value)
    
    sector = 0
    for path, ncols_sub, nrows_sub, xllcorner, yllcorner, cellsize in all_headers:
        # log output with last folder of path
        log_output(f"aligning {path}", output_queue)
        
        sub_min_x_center = xllcorner + cellsize / 2
        sub_max_x_center = xllcorner + (ncols_sub - 0.5) * cellsize
        sub_min_y_center = yllcorner + cellsize / 2
        sub_max_y_center = yllcorner + (nrows_sub - 0.5) * cellsize
        
        start_col = int(round((sub_min_x_center - min_x_center) / cellsize))
        start_row = int(round((max_y_center - sub_max_y_center) / cellsize))
        
        end_row = start_row + nrows_sub
        end_col = start_col + ncols_sub
        
        if start_row < 0 or end_row > nrows_total or start_col < 0 or end_col > ncols_total:
            log_output(f"airfield local matrix going out of bound of reconstructed matrix, skipping: {path}", output_queue)
            continue
        
        with open(path, 'r') as file_obj:
            for _ in range(6):
                next(file_obj)
            
            for i, line in enumerate(file_obj):
                if i >= nrows_sub:
                    log_output("out of bounds", output_queue)
                    break
                
                row_data = np.fromstring(line, dtype=float, sep=' ')
                aligned_slice = aligned[start_row + i, start_col:end_col]
                sectors_slice = sectors[start_row + i, start_col:end_col]
                update_mask = (row_data != nodata_value) & (row_data < aligned_slice)
                sectors_mask = (row_data != nodata_value) & (row_data < aligned_slice)
                sectors_reset = (row_data == 0)
                aligned_slice[update_mask] = row_data[update_mask]
                sectors_slice[sectors_mask] = sector
                sectors_slice[sectors_reset] = nodata_value
        sector += 1
    
    log_output("removing ground from merged raster", output_queue)
    aligned[aligned == 0] = nodata_value
    
    output_path = config.merged_output_raster_path
    sectors_path = config.sectors_filepath
    log_output(f"writing final raster to {output_path}", output_queue)
    log_output(f"writing sector raster to {sectors_path}", output_queue)
    log_output("Done, writing final raster...", output_queue)
    write_asc(aligned, output_path, ncols_total, nrows_total, new_xllcorner, new_yllcorner, cellsize, nodata_value)
    log_output("Done, writing sector raster...", output_queue)
    write_asc(sectors, sectors_path, ncols_total, nrows_total, new_xllcorner, new_yllcorner, cellsize, nodata_value)
    log_output("Post processing final raster...", output_queue)
    
    postProcess2(config.calculation_folder_path, config.calculation_folder_path, config, output_path, config.merged_output_name)

