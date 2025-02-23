import os
from pyproj import CRS
import numpy as np
from pyproj import Transformer, CRS
from scipy.interpolate import griddata
from math import ceil
from src.shortcuts import normJoin
from src.logging import log_output 

def read_asc(filepath):
    """
    Reads an Arc/Info ASCII grid file.
    
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
        for _ in range(6):
            line = f.readline().strip()
            if not line:
                continue
            key, value = line.split()
            key_lower = key.lower()
            if key_lower in ["ncols", "nrows"]:
                header[key_lower] = int(value)
            elif key_lower in ["xllcorner", "yllcorner", "cellsize", "nodata_value"]:
                header[key_lower] = float(value)
        data = np.loadtxt(f)
    return header, data

def resample_from_tm_to_wgs84(header, data, crs, target_res=0.0009, subset_bounds=None, output_queue=None):
    """
    Resamples an input DEM from a custom TM CRS to WGS84, preserving zero areas without blending.

    Args:
        header (dict): Header info from .asc file (ncols, nrows, xllcorner, yllcorner, cellsize, nodata_value).
        data (np.ndarray): Input DEM in TM CRS.
        crs (CRS): Source TM CRS object.
        target_res (float): Target resolution in degrees (default 0.0009°).
        subset_bounds (tuple): Optional (min_lon, min_lat, max_lon, max_lat) in WGS84 to subset the grid.
        output_queue (Queue or None): For logging messages.

    Returns:
        new_dem (np.ndarray): Resampled DEM in WGS84 with nodata and zeros preserved distinctly.
        dem_transform (tuple): (lon_origin, lat_origin, target_res, ncols, nrows) for the new grid.
        bbox_wgs84 (tuple): (min_lon, min_lat, max_lon, max_lat) of the new grid.
    """
    ncols = header["ncols"]
    nrows = header["nrows"]
    xll = header["xllcorner"]
    yll = header["yllcorner"]
    cellsize_orig = header["cellsize"]
    nodata_value = header["nodata_value"]

    # Step 1: Create full TM coordinate grid (centers)
    top_origin = yll + nrows * cellsize_orig
    easting = np.arange(xll + 0.5 * cellsize_orig, xll + ncols * cellsize_orig, cellsize_orig)
    northing = np.arange(top_origin - 0.5 * cellsize_orig, top_origin - nrows * cellsize_orig, -cellsize_orig)
    Easting, Northing = np.meshgrid(easting, northing)

    # Step 2: Filter valid points for interpolation (exclude nodata and zeros)
    valid_mask = (data != nodata_value) & (data != 0)  # Only non-zero, non-nodata points
    easting_valid = Easting[valid_mask]
    northing_valid = Northing[valid_mask]
    values_valid = data[valid_mask]
    # if output_queue:
    #     log_output(f"Valid points (not nodata or 0): {len(values_valid)} out of {data.size}", output_queue)

    # Step 3: Transform valid TM points to WGS84
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon_valid, lat_valid = transformer.transform(easting_valid, northing_valid)
    # if output_queue:
    #     log_output(f"Valid WGS84 coords: lon range [{lon_valid.min():.4f}, {lon_valid.max():.4f}], lat range [{lat_valid.min():.4f}, {lat_valid.max():.4f}]", output_queue)

    # Step 4: Define target WGS84 grid
    min_lon = lon_valid.min()
    max_lon = lon_valid.max()
    min_lat = lat_valid.min()
    max_lat = lat_valid.max()

    if subset_bounds:
        new_lon_min = max(min_lon, subset_bounds[0])
        new_lon_max = min(max_lon, subset_bounds[2])
        new_lat_top = min(max_lat, subset_bounds[3])
        new_lat_bottom = max(min_lat, subset_bounds[1])
    else:
        new_lon_min = min_lon
        new_lon_max = max_lon
        new_lat_top = max_lat
        new_lat_bottom = min_lat

    new_ncols = int(ceil((new_lon_max - new_lon_min) / target_res))
    new_nrows = int(ceil((new_lat_top - new_lat_bottom) / target_res))
    lon_origin = new_lon_min
    lat_origin = new_lat_top

    # Build target WGS84 grid (pixel centers)
    Lon_new = lon_origin + (np.arange(new_ncols) + 0.5) * target_res
    Lat_new = lat_origin - (np.arange(new_nrows) + 0.5) * target_res
    Lon_grid, Lat_grid = np.meshgrid(Lon_new, Lat_new)
    # if output_queue:
    #     log_output(f"WGS84 target grid shape: {Lon_grid.shape}, lon range [{Lon_new[0]:.4f}, {Lon_new[-1]:.4f}], lat range [{Lat_new[0]:.4f}, {Lat_new[-1]:.4f}]", output_queue)

    # Step 5: Interpolate valid non-zero points with griddata
    new_dem = griddata(
        (lon_valid, lat_valid),  # Valid source WGS84 coords (non-zero, non-nodata)
        values_valid,            # Valid source values
        (Lon_grid, Lat_grid),    # Target WGS84 grid
        method='linear',         # Linear interpolation
        fill_value=np.nan        # NaN for areas outside valid points
    )

    # Step 6: Transform full TM grid to WGS84 for nodata and zero masking
    lon_full, lat_full = transformer.transform(Easting, Northing)

    # Step 7: Create zero mask in target grid
    zero_mask_full = (data == 0).astype(float)  # 1 where zero, 0 elsewhere
    zero_mask_target = griddata(
        (lon_full.ravel(), lat_full.ravel()),
        zero_mask_full.ravel(),
        (Lon_grid, Lat_grid),
        method='nearest',  # Nearest neighbor to preserve exact zero boundaries
        fill_value=0       # Default to non-zero outside source grid
    )

    # Step 8: Create nodata mask in target grid
    nodata_mask_full = (data == nodata_value).astype(float)  # 1 where nodata, 0 elsewhere
    nodata_mask_target = griddata(
        (lon_full.ravel(), lat_full.ravel()),
        nodata_mask_full.ravel(),
        (Lon_grid, Lat_grid),
        method='nearest',  # Nearest neighbor to preserve exact nodata boundaries
        fill_value=1       # Default to nodata outside source grid
    )

    # Step 9: Apply masks to preserve zeros and nodata distinctly
    threshold = 0.5  # If > 50% zero or nodata, apply that value
    new_dem = np.where(nodata_mask_target > threshold, nodata_value, new_dem)  # Set nodata first
    new_dem = np.where(zero_mask_target > threshold, 0, new_dem)               # Then set zeros

    return new_dem, (lon_origin, lat_origin, target_res, new_ncols, new_nrows), (new_lon_min, new_lat_bottom, new_lon_max, new_lat_top)

def main(airfield_folder, output_queue=None):
    """
    Main function to convert TM-projected rasters in an airfield folder to WGS84.
    """
    crs_path = normJoin(airfield_folder, "crs.txt")
    with open(crs_path, "r") as f:
        crs_string = f.read().strip()
    source_crs = CRS.from_proj4(crs_string)

    files_to_convert = [("local.asc", "local4326.asc"),
                        ("output_sub.asc", "output_sub4326.asc")]

    for input_filename, output_filename in files_to_convert:
        input_path = normJoin(airfield_folder, input_filename)
        output_path = normJoin(airfield_folder, output_filename)
        if not os.path.exists(input_path):
            log_output(f"File {input_path} does not exist. Skipping.", output_queue)
            continue
        # log_output(f"Processing {input_path} -> {output_path}", output_queue)

        header, data = read_asc(input_path)
        
        new_dem, dem_transform, bbox_wgs84 = resample_from_tm_to_wgs84(header, data, source_crs, output_queue=output_queue)
        
        # log_output(f"WGS84 warped array shape: {new_dem.shape}, min={np.nanmin(new_dem):.2f}, max={np.nanmax(new_dem):.2f}", output_queue)

        with open(output_path, "w") as f:
            f.write(f"ncols        {new_dem.shape[1]}\n")
            f.write(f"nrows        {new_dem.shape[0]}\n")
            f.write(f"xllcorner    {dem_transform[0]}\n")
            f.write(f"yllcorner    {bbox_wgs84[1]}\n")
            f.write(f"cellsize     {dem_transform[2]}\n")
            f.write(f"NODATA_value {header['nodata_value']}\n")
            np.savetxt(f, new_dem, fmt="%.6f", delimiter=" ")

        # log_output(f"Warped raster saved as {output_path}", output_queue)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python warp.py <airfield_folder>")
        sys.exit(1)
    airfield_folder = sys.argv[1]
    main(airfield_folder)