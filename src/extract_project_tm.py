import os
import numpy as np
from pyproj import Transformer, CRS
from scipy.ndimage import map_coordinates
from math import ceil
from src.shortcuts import normJoin  # Ensure you have this helper

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
                header[key_lower] = float(value)
        # Read the remaining data.
        data = np.loadtxt(f)
    return header, data

def main(use_case, airfields, radius_km=120, cellsize_new=100):
    """
    Extracts a subset from a WGS84 .asc matrix for each airfield in the provided list,
    and projects it into a Transverse Mercator (TM) CRS centered on the airfield.
    
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
    # limit size of matrix
    radius_km = use_case.glide_ratio * use_case.max_altitude/1000 +1

    
    # Read the input WGS84 .asc file from use_case.topography_file_path
    input_file = use_case.topography_file_path
    # print(f"Reading input file: {input_file}")
    header, wgs84_raster = read_asc(input_file)
    # print(f"header: {header}")

    # Since header is already a dict, use it directly:
    ncols = header["ncols"]
    nrows = header["nrows"]
    xll = header["xllcorner"]
    yll = header["yllcorner"]
    cellsize_orig = header["cellsize"]

    # Compute top origin (northern edge)
    top_origin = yll + nrows * cellsize_orig

    # Define the original WGS84 grid (cell centers)
    lon = xll + (np.arange(ncols) + 0.5) * cellsize_orig  # longitude centers
    lat = top_origin - (np.arange(nrows) + 0.5) * cellsize_orig  # latitude centers (top-down)
    Lon, Lat = np.meshgrid(lon, lat)
    # print(f"WGS84 raster shape: {wgs84_raster.shape}, min={np.nanmin(wgs84_raster):.2f}, max={np.nanmax(wgs84_raster):.2f}")


    # Loop over each airfield and process the projection
    for airfield in airfields:
        print(f"Projecting to local Transverse Mercator: {airfield.name}")
        # If airfield.x/y are in WGS84 where x is longitude and y is latitude,
        # then use airfield.y as the center latitude and airfield.x as the center longitude.
        center_lat = airfield.y
        center_lon = airfield.x

        # Define TM CRS centered on the airfield position.
        tm_proj = f"+proj=tmerc +lat_0={center_lat} +lon_0={center_lon} +k=1 " \
                  f"+x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
        tm_crs = CRS.from_proj4(tm_proj)
        wgs84_crs = CRS.from_epsg(4326)
        transformer = Transformer.from_crs(wgs84_crs, tm_crs, always_xy=True)

        # Define target TM grid (using provided cellsize and ±radius)
        radius_m = radius_km * 1000  # convert km to meters
        new_ncols = int(ceil(2 * radius_m / cellsize_new))
        new_nrows = int(ceil(2 * radius_m / cellsize_new))
        x_origin = -radius_m  # left edge (relative to center)
        y_origin = radius_m   # top edge (relative to center)

        new_cols_indices = np.arange(new_ncols)
        new_rows_indices = np.arange(new_nrows)
        X_new = x_origin + (new_cols_indices + 0.5) * cellsize_new  # easting centers
        Y_new = y_origin - (new_rows_indices + 0.5) * cellsize_new   # northing centers, top-down
        X_grid, Y_grid = np.meshgrid(X_new, Y_new)
        # print(f"TM target grid for {airfield.name}: shape={X_grid.shape}, " 
        #       f"x range=[{X_new[0]:.2f},{X_new[-1]:.2f}], y range=[{Y_new[0]:.2f},{Y_new[-1]:.2f}]")

        # Transform the target TM grid back to WGS84 coordinates for sampling
        transformer_inv = Transformer.from_crs(tm_crs, wgs84_crs, always_xy=True)
        lon_new, lat_new = transformer_inv.transform(X_grid, Y_grid)

        # Compute fractional indices into the original grid
        src_cols = (lon_new - xll) / cellsize_orig - 0.5
        src_rows = (top_origin - lat_new) / cellsize_orig - 0.5

        # Interpolate the raster using bilinear interpolation
        new_dem = map_coordinates(wgs84_raster, [src_rows, src_cols], order=1, mode="constant")
        # print(f"TM warped array for {airfield.name}: shape={new_dem.shape}, "
        #       f"min={np.nanmin(new_dem):.2f}, max={np.nanmax(new_dem):.2f}")

        # Prepare the airfield-specific output folder.
        airfield_folder = normJoin(use_case.calculation_folder_path, airfield.name)
        os.makedirs(airfield_folder, exist_ok=True)
        output_file = normJoin(airfield_folder, "projected.asc")

        # Write the projected raster to the output file
        with open(output_file, "w") as f:
            f.write(f"ncols        {new_dem.shape[1]}\n")
            f.write(f"nrows        {new_dem.shape[0]}\n")
            f.write(f"xllcorner    {x_origin}\n")
            f.write(f"yllcorner    {-radius_m}\n")
            f.write(f"cellsize     {cellsize_new}\n")
            np.savetxt(f, new_dem, fmt="%.6f", delimiter=" ")
        # print(f"Projected raster saved for {airfield.name} at {output_file}")

        # Write the individual CRS string to crs.txt in the same folder
        crs_file = normJoin(airfield_folder, "crs.txt")
        with open(crs_file, "w") as f_crs:
            f_crs.write(tm_proj)
        # print(f"CRS information saved for {airfield.name} at {crs_file}")

if __name__ == "__main__":
    # Example usage:
    # You will need a use_case object (with at least topography_file_path and calculation_folder_path)
    # and a list of airfields (each having name, x, and y). Here we create simple dummy objects for testing.

    class DummyUseCase:
        def __init__(self):
            # Update with actual input file and folder paths
            self.topography_file_path = "input_WGS84.asc"  
            self.calculation_folder_path = "calculation_folder"

    class DummyAirfield:
        def __init__(self, name, x, y):
            self.name = name
            self.x = x  # Assume longitude
            self.y = y  # Assume latitude

    use_case = DummyUseCase()
    # For example, create one airfield – update the coordinates as needed.
    airfields = [DummyAirfield("Airfield1", 6.3288829, 45.6263899)]
    
    main(use_case, airfields)