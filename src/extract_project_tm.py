import os
import numpy as np
from pyproj import Transformer, CRS
from scipy.ndimage import map_coordinates
from math import ceil
from src.shortcuts import normJoin  # Ensure you have this helper
import time
def read_asc(filepath):
    """
    Reads an Arc/Info ASCII grid file.
    
    Expects a header of 6 lines (ncols, nrows, xllcorner, yllcorner, cellsize,
    NODATA_value) followed by the data rows.
    
    Returns:
        header (dict): Keys include 'ncols', 'nrows', 'xllcorner', 'yllcorner',
                        'cellsize', and optionally 'nodata_value'.
        data (np.ndarray): A 2D numpy array (shape = (nrows, ncols)).
                        Note: the first row in the file corresponds to the NORTH.
    """
    header = {}
    with open(filepath, "r") as f:
        # Read the header (first 6 lines)
        for _ in range(5):
            line = f.readline().strip()
            if not line:
                continue
            key, value = line.split()
            key_lower = key.lower()
            if key_lower in ["ncols", "nrows"]:
                header[key_lower] = int(value)
            elif key_lower in ["xllcorner", "yllcorner", "cellsize"]:
                header[key_lower] = np.float32(value)  # use np.float32 for float values
        # Read the remaining data as integers.
        data = np.loadtxt(f, dtype=int)
    return header, data

def main(use_case, airfields, radius_km=120, cellsize_new=100):
    """
    Extracts a subset from a WGS84 .asc matrix for each airfield in the provided list,
    and projects it into a Transverse Mercator (TM) CRS centered on the airfield.
    
    All internal float values and arrays are maintained as np.float32.
    
    The input WGS84 raster is read from use_case.topography_file_path.
    For each airfield, the projected raster is saved as:
      use_case.calculation_folder_path/airfield.name/projected.asc
    and an individual crs.txt file is written in the same folder containing the CRS string.
    
    Args:
        use_case: A configuration object with attributes, at minimum:
                  - topography_file_path
                  - calculation_folder_path
        airfields (list): List of airfields (each having attributes: name, x, y).  
                          (Assumes airfield.x is longitude and airfield.y is latitude.)
        radius_km (float): Radius (in km) around the airfield where the target TM grid is defined.
                           Default is 120 km.
        cellsize_new (float): Target cellsize in meters of the TM grid.
                              Default is 100 m.
    
    Returns:
        None (one output file is written per airfield).
    """
    # Skip entire function if all output files already exist.
    total_files = 0
    for airfield in airfields:
        output_file = normJoin(use_case.calculation_folder_path, airfield.name, "projected.asc")
        if os.path.exists(output_file):
            total_files += 1
    if total_files == len(airfields):
        print("All files already exist, skipping the function")
        return

    # Use float32 for all float values.
    # Compute radius_km from use_case properties and cast everything to float32.
    # radius_km = (np.float32(use_case.glide_ratio) *
    #              np.float32(use_case.max_altitude) /
    #              np.float32(1000)) + np.float32(1)
    
    # Read the input WGS84 .asc file.
    input_file = use_case.topography_file_path
    # print(f"Reading input file: {input_file}")
    header, wgs84_raster = read_asc(input_file)
    # print(f"header: {header}")

    # Since header is already a dict, use it directly:
    ncols = header["ncols"]
    nrows = header["nrows"]
    xll = header["xllcorner"]       # np.float32
    yll = header["yllcorner"]       # np.float32
    cellsize_orig = header["cellsize"]  # np.float32

    # Compute top origin (northern edge) using float32 arithmetic.
    top_origin = yll + np.float32(nrows) * cellsize_orig

    # Define the original WGS84 grid (cell centers) as float32 vectors.
    lon = xll + (np.arange(ncols, dtype=np.float32) + np.float32(0.5)) * cellsize_orig
    lat = top_origin - (np.arange(nrows, dtype=np.float32) + np.float32(0.5)) * cellsize_orig
    Lon, Lat = np.meshgrid(lon, lat)
    # print(f"WGS84 raster shape: {wgs84_raster.shape}, min={np.nanmin(wgs84_raster):.2f}, max={np.nanmax(wgs84_raster):.2f}")

    # Process each airfield.
    for airfield in airfields:
        # add timing for each airfield
        # start_time = time.time()    
        # Convert airfield coordinates to float32.
        center_lat = np.float32(airfield.y)
        center_lon = np.float32(airfield.x)

        # compute top origin (northern edge) based on the header
        top_origin = yll + np.float32(nrows) * cellsize_orig

        # Convert airfield coordinates to indices.
        # For the latitude, compute the index from the top, since the first row corresponds to the north.
        center_lat_index = int((top_origin - center_lat) / cellsize_orig)
        center_lon_index = int((center_lon - xll) / cellsize_orig)

        # Retrieve the altitude from the matrix using the computed indices.
        value = wgs84_raster[center_lat_index, center_lon_index]
        # print(f"Altitude at {airfield.name}: {value}m")
        radius_m = (np.float32(use_case.glide_ratio) *
                 (np.float32(use_case.max_altitude)-value)) + np.float32(1)
        print(f"Projecting to local Transverse Mercator: {airfield.name}: {value}m, Radius: {int(radius_m/1000)}km")

        # Define TM CRS centered on the airfield position.
        tm_proj = f"+proj=tmerc +lat_0={center_lat} +lon_0={center_lon} +k=1 " \
                  f"+x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
        tm_crs = CRS.from_proj4(tm_proj)
        wgs84_crs = CRS.from_epsg(4326)
        transformer = Transformer.from_crs(wgs84_crs, tm_crs, always_xy=True)

        # Define target TM grid using float32.
        cellsize_new = np.float32(cellsize_new)
        new_ncols = int(ceil(float(np.float32(2) * radius_m / cellsize_new)))
        new_nrows = int(ceil(float(np.float32(2) * radius_m / cellsize_new)))
        x_origin = -radius_m  # left edge (relative to center) as float32
        y_origin = radius_m   # top edge (relative to center) as float32

        new_cols_indices = np.arange(new_ncols, dtype=np.float32)
        new_rows_indices = np.arange(new_nrows, dtype=np.float32)
        X_new = x_origin + (new_cols_indices + np.float32(0.5)) * cellsize_new  # easting centers
        Y_new = y_origin - (new_rows_indices + np.float32(0.5)) * cellsize_new   # northing centers, top-down
        X_grid, Y_grid = np.meshgrid(X_new, Y_new)
        # print(f"TM target grid for {airfield.name}: shape={X_grid.shape}, " 
        #       f"x range=[{X_new[0]:.2f},{X_new[-1]:.2f}], y range=[{Y_new[0]:.2f},{Y_new[-1]:.2f}]")

        # Transform the target TM grid back to WGS84 coordinates for sampling.
        # (Cast to float64 for the transformation, then convert back to float32.)
        transformer_inv = Transformer.from_crs(tm_crs, wgs84_crs, always_xy=True)
        lon_new, lat_new = transformer_inv.transform(X_grid.astype(np.float64), Y_grid.astype(np.float64))
        lon_new = np.array(lon_new, dtype=np.float32)
        lat_new = np.array(lat_new, dtype=np.float32)

        # Compute fractional indices into the original grid (all as float32).
        src_cols = (lon_new - xll) / cellsize_orig - np.float32(0.5)
        src_rows = (top_origin - lat_new) / cellsize_orig - np.float32(0.5)

        # Interpolate the raster using bilinear interpolation.
        new_dem = map_coordinates(wgs84_raster, [src_rows, src_cols], order=1, mode="constant")
        new_dem = np.array(new_dem, dtype=np.float32)

        # Prepare the airfield-specific output folder.
        airfield_folder = normJoin(use_case.calculation_folder_path, airfield.name)
        os.makedirs(airfield_folder, exist_ok=True)
        output_file = normJoin(airfield_folder, "projected.asc")

        # Skip if the file already exists.
        if os.path.exists(output_file):
            print(f"Skipping {airfield.name} because the file already exists")
            continue

        # Write the projected raster (as integers) to the output file.
        with open(output_file, "w") as f:
            f.write(f"ncols        {new_dem.shape[1]}\n")
            f.write(f"nrows        {new_dem.shape[0]}\n")
            f.write(f"xllcorner    {x_origin}\n")
            f.write(f"yllcorner    {-radius_m}\n")
            f.write(f"cellsize     {cellsize_new}\n")
            # Option: Round and convert to int.
            np.savetxt(f, np.rint(new_dem).astype(int), fmt="%d", delimiter=" ")
        # print(f"Projected raster saved for {airfield.name} at {output_file}")

        # Write the CRS string to crs.txt in the same folder.
        crs_file = normJoin(airfield_folder, "crs.txt")
        with open(crs_file, "w") as f_crs:
            f_crs.write(tm_proj)
        # print(f"CRS information saved for {airfield.name} at {crs_file}")
        # end_time = time.time()
        # print(f"Time taken for {airfield.name}: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    # Example usage:
    # You will need a use_case object (with at least topography_file_path and calculation_folder_path)
    # and a list of airfields (each having name, x, and y). Here we create simple dummy objects for testing.

    class DummyUseCase:
        def __init__(self):
            self.topography_file_path = "input_WGS84.asc"
            self.calculation_folder_path = "calculation_folder"
            self.glide_ratio = 1.0  # example value
            self.max_altitude = 1000  # example value

    class DummyAirfield:
        def __init__(self, name, x, y):
            self.name = name
            self.x = x  # Longitude
            self.y = y  # Latitude

    use_case = DummyUseCase()
    airfields = [DummyAirfield("Airfield1", 6.3288829, 45.6263899)]
    
    main(use_case, airfields)