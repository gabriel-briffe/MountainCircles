#!/usr/bin/env python
"""
Generate hillshade from a DEM in ASCII (.asc) format (in EPSG:4326), resample 
it into a metric CRS with a 100 m cellsize, compute a hillshade and export 
the resulting image as MBTiles (tile pyramid).

Usage:
    python tests/hillshade.py input.asc output.mbtiles [--cellsize 100]
         [--azimuth 315] [--altitude 45] [--min_zoom 10] [--max_zoom 14]
"""

import argparse
import numpy as np
import sqlite3
from math import ceil, floor
from io import BytesIO
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import map_coordinates


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
            # ncols and nrows are integers
            if key_lower in ["ncols", "nrows"]:
                header[key_lower] = int(value)
            elif key_lower in ["xllcorner", "yllcorner", "cellsize"]:
                header[key_lower] = float(value)
            # elif key_lower == "nodata_value":
            #     header["nodata_value"] = float(value)
        # Read the remaining data.
        data = np.loadtxt(f)
    return header, data


def resample_to_metric(header, data, cellsize_new=100):
    """
    Resamples an input DEM (data with header information) from EPSG:4326 to a new regular grid
    in EPSG:3857 (metric) with a target cellsize (default 100 m).
    
    The method:
      - Computes the 4326 coordinates of the grid's corners (taking the pixel centers),
      - Transforms to EPSG:3857 and builds a new bounding box,
      - Constructs a new grid (with TOP row first) with a specified cellsize,
      - For each new grid cell (its center) the coordinates are back-projected to 4326 and
        the original DEM is sampled using bilinear interpolation.
      
    Returns:
       new_dem (np.ndarray): The resampled DEM (in metric CRS).
       dem_transform (tuple): (x_origin, y_origin, cellsize, ncols, nrows) where x_origin is the left
                              and y_origin is the top of the new grid.
       bbox_3857 (tuple): (min_x, min_y, max_x, max_y) of the new metric grid.
    """
    ncols = header["ncols"]
    nrows = header["nrows"]
    xll = header["xllcorner"]
    yll = header["yllcorner"]
    cellsize_orig = header["cellsize"]
    # nodata may be used if needed
    # nodata = header.get("nodata_value", -9999)

    # In an ASCII grid the first data row is the top.
    # The top (northern) edge corresponds to:
    top_origin = yll + nrows * cellsize_orig

    # Compute centers (in 4326) for the four corners.
    # For column centers, use: x = xllcorner + (col + 0.5)*cellsize.
    # For row centers (with row 0 at top), the Y coordinate of row i is:
    #     y = top_origin - (i + 0.5)*cellsize.
    lon_min = xll + 0.5 * cellsize_orig
    lon_max = xll + (ncols - 0.5) * cellsize_orig
    lat_top = top_origin - 0.5 * cellsize_orig  # row 0 center
    lat_bottom = yll + 0.5 * cellsize_orig       # last row center

    corners = np.array([
        [lon_min, lat_top],    # top-left
        [lon_max, lat_top],    # top-right
        [lon_min, lat_bottom], # bottom-left
        [lon_max, lat_bottom]  # bottom-right
    ])

    # Transform corners from EPSG:4326 to EPSG:3857.
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    xs, ys = transformer.transform(corners[:, 0], corners[:, 1])
    xs = np.array(xs)
    ys = np.array(ys)

    # New bounding box in 3857.
    min_x = xs.min()
    max_x = xs.max()
    min_y = ys.min()
    max_y = ys.max()

    # Determine new grid dimensions
    new_ncols = int(ceil((max_x - min_x) / cellsize_new))
    new_nrows = int(ceil((max_y - min_y) / cellsize_new))
    # For our new grid we set the top-left (x_origin, y_origin) as:
    x_origin = min_x
    y_origin = max_y

    # Build arrays for new grid pixel centers (in 3857).
    new_cols_indices = np.arange(new_ncols)
    new_rows_indices = np.arange(new_nrows)
    X_new = x_origin + (new_cols_indices + 0.5) * cellsize_new  # (ncols,)
    Y_new = y_origin - (new_rows_indices + 0.5) * cellsize_new   # (nrows,)
    X_grid, Y_grid = np.meshgrid(X_new, Y_new)  # shape: (new_nrows, new_ncols)

    # Now transform these metric centers back to 4326 (lon, lat) to sample the original data.
    transformer_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    lon_new, lat_new = transformer_inv.transform(X_grid, Y_grid)

    # Compute (fractional) indices into the original DEM.
    # For X: center of col j is: xll + (j+0.5)*cellsize_orig  -> j = (lon - xll)/cellsize_orig - 0.5
    src_cols = (lon_new - xll) / cellsize_orig - 0.5
    # For Y (with row 0 at top): top_origin is at row = 0 center, so:
    src_rows = (top_origin - lat_new) / cellsize_orig - 0.5

    # Sample the original data. (Using order=1 for bilinear interpolation.)
    new_dem = map_coordinates(data, [src_rows, src_cols], order=1, mode="nearest")

    return new_dem, (x_origin, y_origin, cellsize_new, new_ncols, new_nrows), (min_x, min_y, max_x, max_y)


def compute_hillshade(dem, cellsize, azimuth=315, altitude=45, z_factor=1.0):
    """
    Computes a hillshade (illumination) raster from an input DEM.
    
    Parameters:
      dem      - 2D numpy array (assumed to have uniform spacing = cellsize)
      cellsize - spacing in meters (both x and y)
      azimuth  - Sun azimuth angle in degrees (default: 315)
      altitude - Sun altitude angle in degrees (default: 45)
      z_factor - Scaling factor applied to elevation values (default: 1.0)
    
    The hillshade is computed via:
        hillshade = 255 * (cos(alt_rad)*cos(slope) +
                           sin(alt_rad)*sin(slope)*cos(az_rad - aspect))
    where the slope is computed as:
        slope = arctan(z_factor * sqrt((dz/dx)² + (dz/dy)²))
    and the gradients are obtained via np.gradient.
    
    Returns:
      A uint8 numpy array with values 0–255 representing the hillshade.
    """
    az_rad = np.radians(azimuth)
    alt_rad = np.radians(altitude)
    # Compute gradients.
    dy, dx = np.gradient(dem, cellsize, cellsize)
    # Apply z-factor when computing the slope.
    # slope = np.arctan(z_factor * np.sqrt(dx ** 2 + dy ** 2))
    slope = np.arctan(2 * np.sqrt(dx ** 2 + dy ** 2))
    # Compute aspect: 0 = north.
    aspect = np.arctan2(-dx, dy)
    aspect = np.where(aspect < 0, 2 * np.pi + aspect, aspect)
    hs = (np.cos(alt_rad) * np.cos(slope) +
          np.sin(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect))
    # Clip negative values and scale to 0–255.
    hs = np.clip(hs, 0, 1)
    hs = (hs * 255).astype(np.uint8)
    return hs


# def compute_hillshade_multidirectional_additive(dem, cellsize, altitude=45, z_factor=1.0):
#     """
#     Computes a multidirectional hillshade by summing the hillshade contributions from 
#     eight azimuth angles (0°, 45°, ..., 315°) and then linearly normalizing the result
#     so that the lowest pixel becomes 0 and the highest becomes 255.
    
#     Parameters:
#       dem      - 2D numpy array representing elevation values.
#       cellsize - Horizontal cell size in meters.
#       altitude - Sun altitude angle in degrees (default: 45).
#       z_factor - Scaling factor applied to elevation values (default: 1.0).
    
#     Returns:
#       A uint8 numpy array with values 0–255 representing the normalized multidirectional hillshade.
#     """
#     alt_rad = np.radians(altitude)
#     dy, dx = np.gradient(dem, cellsize, cellsize)
#     # Use z_factor when computing the slope.
#     slope = np.arctan(z_factor * np.sqrt(dx**2 + dy**2))
#     aspect = np.arctan2(-dx, dy)
#     aspect = np.where(aspect < 0, 2 * np.pi + aspect, aspect)
    
#     # Define eight azimuth angles: 0, 45, 90, ... 315 degrees.
#     azimuth_angles = np.radians(np.arange(0, 360, 45))
#     hs_sum = np.zeros_like(dem, dtype=float)
    
#     # Sum hillshade values for each azimuth angle.
#     for az in azimuth_angles:
#         hs = (np.cos(alt_rad) * np.cos(slope) +
#               np.sin(alt_rad) * np.sin(slope) * np.cos(az - aspect))
#         hs_sum += hs
    
#     hs_normalized = (hs_sum - hs_sum.min()) / (hs_sum.max() - hs_sum.min()) * 255
#     hs_normalized = hs_normalized.astype(np.uint8)
    
#     return hs_normalized


def generate_mbtiles(slope_map, dem_transform, min_zoom, max_zoom, output_path):
    """
    Generates an MBTiles file from the slope map raster.
    
    The slope map is assumed to be a 2D numpy array in EPSG:3857 with an affine transform:
      X = x_origin + (col+0.5)*cellsize
      Y = y_origin - (row+0.5)*cellsize
    where (x_origin, y_origin, cellsize, ncols, nrows) is provided in dem_transform.
    
    For each zoom level between min_zoom and max_zoom, tiles are generated by computing 
    (via bilinear interpolation with scipy.ndimage.map_coordinates) a 256×256 image that covers 
    that tile extent. The tiles are encoded as PNG and inserted into an MBTiles SQLite database.
    
    Parameters:
       slope_map   (np.ndarray): 2D uint8 array (the slope map).
       dem_transform (tuple): (x_origin, y_origin, cellsize, ncols, nrows).
       min_zoom, max_zoom: Integers for the zoom-level range.
       output_path: Path for the MBTiles output file.
    """
    x_origin, y_origin, cellsize, ncols, nrows = dem_transform
    # Determine the extent of the slope map in EPSG:3857.
    dem_west = x_origin
    dem_north = y_origin
    dem_east = x_origin + ncols * cellsize
    dem_south = y_origin - nrows * cellsize

    # Open SQLite connection and create MBTiles tables.
    conn = sqlite3.connect(output_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT, value TEXT);")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS tiles (
           zoom_level INTEGER,
           tile_column INTEGER,
           tile_row INTEGER,
           tile_data BLOB
           );"""
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS tile_index on tiles (zoom_level, tile_column, tile_row);"
    )
    conn.commit()

    # Web Mercator full extent (in meters)
    WEB_MERC_MAX = 20037508.342789244
    tile_size = 256

    for z in range(min_zoom, max_zoom + 1):
        resolution = (2 * WEB_MERC_MAX) / (tile_size * 2 ** z)
        tile_x_min = int(floor((dem_west + WEB_MERC_MAX) / (tile_size * resolution)))
        tile_x_max = int(floor((dem_east + WEB_MERC_MAX) / (tile_size * resolution)))
        tile_y_min = int(floor((WEB_MERC_MAX - dem_north) / (tile_size * resolution)))
        tile_y_max = int(floor((WEB_MERC_MAX - dem_south) / (tile_size * resolution)))

        print(f"Zoom level {z}: tile_x from {tile_x_min} to {tile_x_max}, "
              f"tile_y from {tile_y_min} to {tile_y_max}")

        for tx in range(tile_x_min, tile_x_max + 1):
            for ty in range(tile_y_min, tile_y_max + 1):
                # Compute tile bounds in EPSG:3857.
                tile_west = -WEB_MERC_MAX + tx * tile_size * resolution
                tile_north = WEB_MERC_MAX - ty * tile_size * resolution
                tile_east = tile_west + tile_size * resolution
                tile_south = tile_north - tile_size * resolution

                # Build a grid of pixel centers for the tile (256×256).
                pixel_indices = np.arange(tile_size) + 0.5
                tile_xs = tile_west + pixel_indices * resolution
                tile_ys = tile_north - pixel_indices * resolution
                X_tile, Y_tile = np.meshgrid(tile_xs, tile_ys)

                # Sample the slope map using bilinear interpolation.
                src_cols = (X_tile - x_origin) / cellsize - 0.5
                src_rows = (y_origin - Y_tile) / cellsize - 0.5
                tile_data = map_coordinates(slope_map, [src_rows, src_cols],
                                            order=1, mode="constant", cval=0)
                tile_data = tile_data.astype(np.uint8)

                # Create a grayscale image and convert it to RGB so that the tile has 3 channels.
                im = Image.fromarray(tile_data, mode="L").convert("RGB")
                buffer = BytesIO()
                im.save(buffer, format="PNG")
                png_data = buffer.getvalue()

                # MBTiles tile_row is in TMS scheme.
                tms_y = (2 ** z - 1) - ty
                cur.execute(
                    "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                    (z, tx, tms_y, sqlite3.Binary(png_data)),
                )
        conn.commit()

    # Insert metadata.
    transformer_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    lon1, lat1 = transformer_inv.transform(dem_west, dem_south)
    lon2, lat2 = transformer_inv.transform(dem_east, dem_north)
    bounds = f"{min(lon1, lon2)},{min(lat1, lat2)},{max(lon1, lon2)},{max(lat1, lat2)}"
    metadata = {
        "name": "Slope Map",
        "type": "overlay",
        "version": "1.0",
        "description": "Slope map generated from DEM",
        "format": "png",
        "bounds": bounds,
        "minzoom": str(min_zoom),
        "maxzoom": str(max_zoom),
    }
    for key, value in metadata.items():
        cur.execute("INSERT INTO metadata (name, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
    print(f"MBTiles file saved to {output_path}")


def compute_normalized_slope(dem, cellsize, z_factor=1.0):
    """
    Computes slope from a DEM and normalizes it between 0 and 255.
    The slope is calculated using the gradient of the DEM (in radians),
    i.e. slope = arctan(z_factor * sqrt((dz/dx)² + (dz/dy)²)).
    The resulting slope image is then normalized so that the minimum slope becomes 0
    and the maximum becomes 255.
    
    Parameters:
      dem      - 2D numpy array representing elevation values.
      cellsize - The horizontal resolution (in meters) of the DEM.
      z_factor - Scaling factor applied to elevation values (default: 1.0).
    
    Returns:
      A 2D uint8 numpy array where each pixel holds the normalized slope value.
    """
    # Compute gradients (dy along rows, dx along columns).
    dy, dx = np.gradient(dem, cellsize, cellsize)
    # Calculate slope (radians) with z-factor adjustment.
    slope = np.arctan(z_factor * np.sqrt(dx**2 + dy**2))
    # Normalize the slope values linearly so that min->0 and max->255.
    norm_slope = (slope - slope.min()) / (slope.max() - slope.min()) * 255
    return norm_slope.astype(np.uint8)


def combine_images(standard_hillshade, inverted_slope_map):
    """
    Combines the standard hillshade and the inverted normalized slope map by summing them 
    and linearly normalizing the result to 0–255.
    
    Parameters:
      standard_hillshade - 2D uint8 numpy array from compute_hillshade.
      inverted_slope_map - 2D uint8 numpy array (the inverted normalized slope map).
    
    Returns:
      combined_image - 2D uint8 numpy array representing the composite hillshade.
    """
    combined = standard_hillshade.astype(np.float32) + inverted_slope_map.astype(np.float32)
    # Linearly normalize so that the minimum becomes 0 and the maximum becomes 255.
    combined_norm = 255 * ((combined - combined.min()) / (combined.max() - combined.min()))
    return combined_norm.astype(np.uint8)


def main():
    parser = argparse.ArgumentParser(
        description="Generate composite hillshade from an .asc DEM (EPSG:4326), resample to metric (100 m), "
                    "compute a standard hillshade and a normalized slope map, combine them, "
                    "and export to MBTiles (no GDAL required)."
    )
    parser.add_argument("input_asc", help="Path to input .asc file in EPSG:4326")
    parser.add_argument("output_mbtiles", help="Path to output MBTiles file for composite hillshade")
    parser.add_argument("--cellsize", type=float, default=100,
                        help="Target cellsize in meters for resampling (default: 100)")
    parser.add_argument("--min_zoom", type=int, default=1,
                        help="Minimum zoom level for MBTiles (default: 1)")
    parser.add_argument("--max_zoom", type=int, default=12,
                        help="Maximum zoom level for MBTiles (default: 12)")
    parser.add_argument("--z_factor", type=float, default=1.4,
                        help="Z-factor to scale elevation values (default: 1.4)")
    parser.add_argument("--azimuth", type=float, default=315,
                        help="Sun azimuth angle in degrees for standard hillshade (default: 315)")
    parser.add_argument("--altitude", type=float, default=45,
                        help="Sun altitude angle in degrees for standard hillshade (default: 45)")
    # Optional output for the resampled DEM (for inspection).
    parser.add_argument("--output_resampled", help="Path to output resampled DEM as ASCII grid (optional)")
    args = parser.parse_args()

    header, data = read_asc(args.input_asc)
    print("Read ASC file. Header:", header)

    new_dem, dem_transform, bbox_3857 = resample_to_metric(header, data, cellsize_new=args.cellsize)
    print(f"Resampled DEM to metric CRS: shape = {new_dem.shape}, transform = {dem_transform}")

    if args.output_resampled:
        x_origin, y_origin, cellsize, ncols, nrows = dem_transform
        xllcorner = x_origin
        yllcorner = y_origin - nrows * cellsize
        with open(args.output_resampled, 'w') as f:
            f.write(f"ncols {ncols}\n")
            f.write(f"nrows {nrows}\n")
            f.write(f"xllcorner {xllcorner}\n")
            f.write(f"yllcorner {yllcorner}\n")
            f.write(f"cellsize {cellsize}\n")
            f.write("NODATA_value -9999\n")
            np.savetxt(f, new_dem, fmt="%.2f")
        print(f"Resampled DEM written to {args.output_resampled}")

    # Compute the standard hillshade.
    standard_hillshade = compute_hillshade(new_dem, args.cellsize,
                                             azimuth=args.azimuth,
                                             altitude=args.altitude,
                                             z_factor=args.z_factor)
    print("Computed standard hillshade from DEM.")

    # Compute the normalized slope map.
    slope_map = compute_normalized_slope(new_dem, args.cellsize, z_factor=args.z_factor)
    # Invert the slope map so that high slope areas become dark.
    inverted_slope_map = 255 - slope_map
    print("Computed normalized and inverted slope map from DEM.")

    # Combine the standard hillshade and the inverted slope map.
    composite = combine_images(standard_hillshade, inverted_slope_map)
    print("Combined standard hillshade and inverted slope map into composite hillshade.")

    generate_mbtiles(composite, dem_transform, args.min_zoom, args.max_zoom, args.output_mbtiles)
    print(f"Composite hillshade MBTiles file saved to {args.output_mbtiles}")


if __name__ == "__main__":
    main()
