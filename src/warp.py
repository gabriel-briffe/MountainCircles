import os
from pyproj import CRS
import numpy as np
from pyproj import Transformer
from scipy.interpolate import griddata
from math import ceil
from src.shortcuts import normJoin
from src.logging import log_output 

def read_asc(filepath):
    # [Unchanged, kept for context]
    header = {}
    with open(filepath, "r") as f:
        for _ in range(6):
            line = f.readline().strip()
            if not line:
                continue
            key, value = line.split()
            key_lower = key.lower()
            if key_lower in ["ncols", "nrows", "nodata_value"]:
                header[key_lower] = int(value)
            elif key_lower in ["xllcorner", "yllcorner", "cellsize"]:
                header[key_lower] = np.float32(value)
        data = np.loadtxt(f, dtype=np.float32)
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

    # Define a 32-bit half constant
    half = np.float32(0.5)

    # Step 1: Precompute full TM coordinate grid (centers) once and reuse
    top_origin = np.float32(yll + nrows * cellsize_orig)
    easting = np.arange(xll + half * cellsize_orig,
                        xll + ncols * cellsize_orig,
                        cellsize_orig,
                        dtype=np.float32)
    northing = np.arange(top_origin - half * cellsize_orig,
                         top_origin - nrows * cellsize_orig,
                         -cellsize_orig,
                         dtype=np.float32)
    Easting, Northing = np.meshgrid(easting, northing)
    del easting, northing

    # Step 2: Separate valid, zero, and nodata points upfront with vectorized operations
    valid_mask = (data != nodata_value) & (data != 0)
    zero_mask = (data == 0)
    nodata_mask = (data == nodata_value)

    # Extract coordinates and values for valid points
    easting_valid = Easting[valid_mask]
    northing_valid = Northing[valid_mask]
    values_valid = data[valid_mask]
    del data, valid_mask
    # if output_queue:
    #     log_output(f"Valid points (not nodata or 0): {len(values_valid)} out of {data.size}", output_queue)

    # Step 3: Transform coordinates to WGS84 with vectorized operations
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    
    # Transform valid points
    lon_valid, lat_valid = transformer.transform(easting_valid, northing_valid)
    del easting_valid, northing_valid
    lon_valid = np.array(lon_valid, dtype=np.float32)
    lat_valid = np.array(lat_valid, dtype=np.float32)
    
    # Transform full grid once and pre-flatten for reuse
    lon_full, lat_full = transformer.transform(Easting, Northing)
    del Easting, Northing
    lon_full = np.array(lon_full, dtype=np.float32)
    lat_full = np.array(lat_full, dtype=np.float32)
    lon_full_flat = lon_full.ravel()
    lat_full_flat = lat_full.ravel()
    del lon_full, lat_full

    # if output_queue:
    #     log_output(f"Valid WGS84 coords: lon range [{lon_valid.min():.4f}, {lon_valid.max():.4f}], lat range [{lat_valid.min():.4f}, {lat_valid.max():.4f}]", output_queue)

    # Step 4: Define and precompute target WGS84 grid once
    min_lon = lon_valid.min()
    max_lon = lon_valid.max()
    min_lat = lat_valid.min()
    max_lat = lat_valid.max()

    if subset_bounds:
        new_lon_min = np.float32(max(min_lon, subset_bounds[0]))
        new_lon_max = np.float32(min(max_lon, subset_bounds[2]))
        new_lat_top = np.float32(min(max_lat, subset_bounds[3]))
        new_lat_bottom = np.float32(max(min_lat, subset_bounds[1]))
    else:
        new_lon_min = np.float32(min_lon)
        new_lon_max = np.float32(max_lon)
        new_lat_top = np.float32(max_lat)
        new_lat_bottom = np.float32(min_lat)

    new_ncols = int(ceil((new_lon_max - new_lon_min) / target_res))
    new_nrows = int(ceil((new_lat_top - new_lat_bottom) / target_res))
    lon_origin = np.float32(new_lon_min)
    lat_origin = np.float32(new_lat_top)

    # Build target WGS84 grid (pixel centers) once and reuse
    Lon_new = lon_origin + (np.arange(new_ncols, dtype=np.float32) + half) * target_res
    Lat_new = lat_origin - (np.arange(new_nrows, dtype=np.float32) + half) * target_res
    Lon_grid, Lat_grid = np.meshgrid(Lon_new, Lat_new)
    del Lon_new, Lat_new

    # Step 5: Fast interpolation of valid points
    new_dem = griddata(
        (lon_valid, lat_valid),
        values_valid,
        (Lon_grid, Lat_grid),
        method='linear',
        fill_value=np.nan
    )
    del values_valid,lon_valid,lat_valid
    new_dem = np.array(new_dem, dtype=np.float32)

    # Step 6: Nearest-neighbor overlay for zeros and nodata using precomputed grids
    zero_mask_target = griddata(
        (lon_full_flat, lat_full_flat),
        zero_mask.ravel().astype(np.float32),
        (Lon_grid, Lat_grid),
        method='nearest',
        fill_value=0
    )
    del zero_mask
    nodata_mask_target = griddata(
        (lon_full_flat, lat_full_flat),
        nodata_mask.ravel().astype(np.float32),
        (Lon_grid, Lat_grid),
        method='nearest',
        fill_value=1
    )
    del nodata_mask,Lon_grid,Lat_grid, lon_full_flat, lat_full_flat
    # Step 7: Apply masks in-place instead of np.where (Point 1)
    threshold = 0.5
    new_dem[nodata_mask_target > threshold] = nodata_value  # In-place nodata overlay
    new_dem[zero_mask_target > threshold] = 0               # In-place zero overlay

    # Step 8: Release intermediate data early (Point 2)

    return new_dem, (lon_origin, lat_origin, target_res, new_ncols, new_nrows), (new_lon_min, new_lat_bottom, new_lon_max, new_lat_top)

def main(airfield_folder, output_queue=None):
    # [Unchanged, kept for context]
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

        header, data = read_asc(input_path)
        new_dem, dem_transform, bbox_wgs84 = resample_from_tm_to_wgs84(header, data, source_crs, output_queue=output_queue)

        with open(output_path, "w") as f:
            f.write(f"ncols        {new_dem.shape[1]}\n")
            f.write(f"nrows        {new_dem.shape[0]}\n")
            f.write(f"xllcorner    {dem_transform[0]}\n")
            f.write(f"yllcorner    {bbox_wgs84[1]}\n")
            f.write(f"cellsize     {dem_transform[2]}\n")
            f.write(f"NODATA_value {header['nodata_value']}\n")
            np.savetxt(f, new_dem, fmt="%.6f", delimiter=" ")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python warp.py <airfield_folder>")
        sys.exit(1)
    airfield_folder = sys.argv[1]
    main(airfield_folder)