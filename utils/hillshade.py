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


def resample_to_metric(header, data, cellsize_new=100, subset_bounds=None):
    """
    Resamples an input DEM (data with header information) from EPSG:4326 to a new regular grid
    in EPSG:3857 (metric) with a target cellsize (default 100 m).

    If subset_bounds is provided, it should be a tuple of (min_lon, min_lat, max_lon, max_lat) in EPSG:4326.
    The resampling will be applied only to the intersection of the original DEM's center coordinates and subset_bounds.

    Returns:
       new_dem (np.ndarray): The resampled DEM (in metric CRS) for the specified subset.
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

    # Ensure data is finite and handle any NaN or infinite values
    if not np.isfinite(data).all():
        print("Warning: Found non-finite values in input data, replacing with interpolated values")
        # Replace NaN/inf with nearest valid values
        from scipy.ndimage import distance_transform_edt
        mask = ~np.isfinite(data)
        if mask.any():
            # Find nearest valid values
            indices = distance_transform_edt(mask, return_distances=False, return_indices=True)
            data = data[tuple(indices)]

    # In an ASCII grid the first data row is the top.
    # The top (northern) edge corresponds to:
    top_origin = yll + nrows * cellsize_orig

    # Compute centers (in 4326) for the four corners.
    # For column centers, use: x = xllcorner + (col + 0.5)*cellsize.
    # For row centers (with row 0 at top), the Y coordinate of row i is:
    #     y = top_origin - (i + 0.5)*cellsize.
    full_lon_min = xll + 0.5 * cellsize_orig
    full_lon_max = xll + (ncols - 0.5) * cellsize_orig
    full_lat_top = top_origin - 0.5 * cellsize_orig  # row 0 center
    full_lat_bottom = yll + 0.5 * cellsize_orig       # last row center

    if subset_bounds:
        # Expect subset_bounds = (min_lon, min_lat, max_lon, max_lat)
        new_lon_min = max(full_lon_min, subset_bounds[0])
        new_lon_max = min(full_lon_max, subset_bounds[2])
        # Note: for latitude, the "top" is the maximum value.
        new_lat_top = min(full_lat_top, subset_bounds[3])
        new_lat_bottom = max(full_lat_bottom, subset_bounds[1])
    else:
        new_lon_min = full_lon_min
        new_lon_max = full_lon_max
        new_lat_top = full_lat_top
        new_lat_bottom = full_lat_bottom

    corners = np.array([
        [new_lon_min, new_lat_top],    # top-left
        [new_lon_max, new_lat_top],    # top-right
        [new_lon_min, new_lat_bottom], # bottom-left
        [new_lon_max, new_lat_bottom]  # bottom-right
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
    
    # Ensure the result is finite
    if not np.isfinite(new_dem).all():
        print("Warning: Non-finite values in resampled DEM, replacing with nearest valid values")
        mask = ~np.isfinite(new_dem)
        if mask.any():
            # Replace with mean of valid values
            valid_mean = np.nanmean(new_dem[np.isfinite(new_dem)])
            new_dem[mask] = valid_mean

    return new_dem, (x_origin, y_origin, cellsize_new, new_ncols, new_nrows), (min_x, min_y, max_x, max_y)


def compute_hillshade(dem, cellsize, azimuth=315, altitude=45, z_factor_shades=2.0):
    """
    Computes a hillshade (illumination) raster from an input DEM.
    
    Parameters:
      dem      - 2D numpy array (assumed to have uniform spacing = cellsize)
      cellsize - spacing in meters (both x and y)
      azimuth  - Sun azimuth angle in degrees (default: 315)
      altitude - Sun altitude angle in degrees (default: 45)
      z_factor_shades - Scaling factor applied to elevation values for shades (default: 2)
    
    The hillshade is computed via:
        hillshade = 255 * (cos(alt_rad)*cos(slope) +
                           sin(alt_rad)*sin(slope)*cos(az_rad - aspect))
    where the slope is computed as:
        slope = arctan(z_factor_shades * sqrt((dz/dx)² + (dz/dy)²))
    and the gradients are obtained via np.gradient.
    
    Returns:
      A uint8 numpy array with values 0–255 representing the hillshade.
    """
    az_rad = np.radians(azimuth)
    alt_rad = np.radians(altitude)
    # Compute gradients.
    dy, dx = np.gradient(dem, cellsize, cellsize)
    # Apply z-factor when computing the slope.
    # slope = np.arctan(z_factor_shades * np.sqrt(dx ** 2 + dy ** 2))
    slope = np.arctan(z_factor_shades * np.sqrt(dx ** 2 + dy ** 2))
    # Compute aspect: 0 = north.
    aspect = np.arctan2(-dx, dy)
    aspect = np.where(aspect < 0, 2 * np.pi + aspect, aspect)
    hs = (np.cos(alt_rad) * np.cos(slope) +
          np.sin(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect))
    # Clip negative values and scale to 0–255.
    hs = np.clip(hs, 0, 1)
    hs = (hs * 255).astype(np.uint8)
    return hs


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
    from utils.simple_mercator import tile_bounds, lat_lon_to_tile
    
    x_origin, y_origin, cellsize, ncols, nrows = dem_transform
    # Determine the extent of the slope map in EPSG:3857.
    dem_west = x_origin
    dem_north = y_origin
    dem_east = x_origin + ncols * cellsize
    dem_south = y_origin - nrows * cellsize

    # Convert DEM bounds to geographic coordinates to find tile ranges
    transformer_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    west_lon, south_lat = transformer_inv.transform(dem_west, dem_south)
    east_lon, north_lat = transformer_inv.transform(dem_east, dem_north)

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

    tile_size = 256

    for z in range(min_zoom, max_zoom + 1):
        # Find tile range using simple mercator functions
        min_tile_x, max_tile_y = lat_lon_to_tile(south_lat, west_lon, z)
        max_tile_x, min_tile_y = lat_lon_to_tile(north_lat, east_lon, z)
        
        print(f"Zoom level {z}: tile_x from {min_tile_x} to {max_tile_x}, "
              f"tile_y from {min_tile_y} to {max_tile_y}")

        for tx in range(min_tile_x, max_tile_x + 1):
            for ty in range(min_tile_y, max_tile_y + 1):
                # Get tile bounds using simple mercator functions
                tile_min_lat, tile_min_lon, tile_max_lat, tile_max_lon = tile_bounds(tx, ty, z)
                
                # Convert to Web Mercator for pixel calculations
                transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
                tile_west, tile_south = transformer.transform(tile_min_lon, tile_min_lat)
                tile_east, tile_north = transformer.transform(tile_max_lon, tile_max_lat)

                # Build a grid of pixel centers for the tile (256×256).
                resolution_x = (tile_east - tile_west) / tile_size
                resolution_y = (tile_north - tile_south) / tile_size
                
                pixel_indices = np.arange(tile_size) + 0.5
                tile_xs = tile_west + pixel_indices * resolution_x
                tile_ys = tile_north - pixel_indices * resolution_y
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
    bounds = f"{west_lon},{south_lat},{east_lon},{north_lat}"
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


def compute_normalized_slope(dem, cellsize, z_factor_slopes=1.0):
    """
    Computes slope from a DEM and normalizes it between 0 and 255.
    The slope is calculated using the gradient of the DEM (in radians),
    i.e. slope = arctan(z_factor_slopes * sqrt((dz/dx)² + (dz/dy)²)).
    The resulting slope image is then normalized using a fixed range to ensure
    consistent appearance across different area sizes.
    
    Parameters:
      dem      - 2D numpy array representing elevation values.
      cellsize - The horizontal resolution (in meters) of the DEM.
      z_factor_slopes - Scaling factor applied to elevation values for slopes (default: 1.0).
    
    Returns:
      A 2D uint8 numpy array where each pixel holds the normalized slope value.
    """
    # Compute gradients (dy along rows, dx along columns).
    dy, dx = np.gradient(dem, cellsize, cellsize)
    # Calculate slope (radians) with z-factor adjustment.
    slope = np.arctan(z_factor_slopes * np.sqrt(dx**2 + dy**2))
    
    # Use fixed normalization range instead of min/max to ensure consistent appearance
    # Typical slope range for mountainous terrain is 0 to ~1.2 radians (0° to ~70°)
    max_slope_rad = 1.2  # ~70 degrees, covers most mountainous terrain
    norm_slope = np.clip(slope / max_slope_rad * 255, 0, 255)
    
    return norm_slope.astype(np.uint8)


def combine_images(standard_hillshade, inverted_slope_map):
    """
    Combines the standard hillshade and the inverted normalized slope map by summing them 
    and normalizing the result to 0–255 using a fixed range for consistent appearance.
    
    Parameters:
      standard_hillshade - 2D uint8 numpy array from compute_hillshade.
      inverted_slope_map - 2D uint8 numpy array (the inverted normalized slope map).
    
    Returns:
      combined_image - 2D uint8 numpy array representing the composite hillshade.
    """
    combined = standard_hillshade.astype(np.float32) + inverted_slope_map.astype(np.float32)
    
    # Use fixed normalization range instead of min/max to ensure consistent appearance
    # Combined values typically range from ~50 to ~450 (two uint8 values summed)
    # We'll normalize assuming a reasonable range and clip to avoid over/under exposure
    combined_norm = np.clip(combined / 2.0, 0, 255)  # Divide by 2 to get back to 0-255 range
    
    return combined_norm.astype(np.uint8)


def generate_zoom7_combined_image(composite, dem_transform, tile_x, tile_y, zoom, output_path):
    """
    Generate a combined OSM + hillshade image at zoom level 7 for a SINGLE tile.
    
    Args:
        composite: The hillshade composite image (numpy array)
        dem_transform: DEM transformation parameters
        tile_x, tile_y: Web mercator tile coordinates
        zoom: Zoom level
        output_path: Path to save the combined image
    """
    import requests
    import io
    from PIL import Image, ImageChops, ImageEnhance
    from math import floor
    from pyproj import Transformer
    from utils.simple_mercator import tile_bounds
    
    tile_size = 256
    x_origin, y_origin, cellsize, ncols, nrows = dem_transform
    
    print(f"Generating single tile image for tile ({tile_x}, {tile_y}) at zoom {zoom}")
    
    # Get tile bounds using simple mercator functions
    min_lat, min_lon, max_lat, max_lon = tile_bounds(tile_x, tile_y, zoom)
    print(f"Tile bounds in geographic: {min_lat:.6f}° to {max_lat:.6f}°N, {min_lon:.6f}° to {max_lon:.6f}°E")
    
    # Convert to Web Mercator for pixel calculations
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    tile_west, tile_south = transformer.transform(min_lon, min_lat)
    tile_east, tile_north = transformer.transform(max_lon, max_lat)
    print(f"Tile bounds in Web Mercator: {tile_west:.0f}, {tile_south:.0f} to {tile_east:.0f}, {tile_north:.0f}")
    
    # Download OSM tile
    osm_url = f"https://a.tile.openstreetmap.org/{zoom}/{tile_x}/{tile_y}.png"
    try:
        headers = {'User-Agent': 'MountainCircles/1.0 (https://github.com/user/mountaincircles)'}
        response = requests.get(osm_url, timeout=10, headers=headers)
        response.raise_for_status()
        osm_img = Image.open(io.BytesIO(response.content)).convert('RGB')
        print(f"Downloaded OSM tile {tile_x},{tile_y}")
    except Exception as e:
        print(f"Failed to download OSM tile {tile_x},{tile_y}: {e}")
        osm_img = Image.new('RGB', (tile_size, tile_size), (240, 240, 240))
    
    # Build pixel grid for the tile
    resolution_x = (tile_east - tile_west) / tile_size
    resolution_y = (tile_north - tile_south) / tile_size
    
    pixel_indices = np.arange(tile_size) + 0.5
    tile_xs = tile_west + pixel_indices * resolution_x
    tile_ys = tile_north - pixel_indices * resolution_y
    X_tile, Y_tile = np.meshgrid(tile_xs, tile_ys)
    
    # Sample the hillshade composite
    from scipy.ndimage import map_coordinates
    src_cols = (X_tile - x_origin) / cellsize - 0.5
    src_rows = (y_origin - Y_tile) / cellsize - 0.5
    
    # Check sampling bounds
    valid_cols = (src_cols >= 0) & (src_cols < ncols)
    valid_rows = (src_rows >= 0) & (src_rows < nrows)
    valid_pixels = valid_cols & valid_rows
    valid_percent = 100 * valid_pixels.sum() / valid_pixels.size
    print(f"Valid pixels: {valid_pixels.sum()}/{valid_pixels.size} ({valid_percent:.1f}%)")
    
    tile_data = map_coordinates(composite, [src_rows, src_cols],
                              order=1, mode="constant", cval=128)
    tile_data = tile_data.astype(np.uint8)
    
    print(f"Tile data range: {tile_data.min()}-{tile_data.max()}, mean: {tile_data.mean():.1f}")
    
    # Create hillshade image
    hillshade_img = Image.fromarray(tile_data, mode="L").convert("RGB")
    
    # Combine OSM and hillshade using multiply blend
    osm_enhanced = ImageEnhance.Contrast(osm_img).enhance(1.0)
    osm_enhanced = ImageEnhance.Color(osm_enhanced).enhance(1.0)
    combined_tile = ImageChops.multiply(osm_enhanced, hillshade_img)
    
    # Save the single tile image (256x256)
    combined_tile.save(output_path, 'PNG', optimize=True)
    print(f"Single tile image saved to {output_path}")
    print(f"Image size: {tile_size}x{tile_size} pixels")


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
    parser.add_argument("--z_factor_slopes", type=float, default=1.4,
                        help="Z-factor to scale elevation values for slopes (default: 1.4)")
    parser.add_argument("--z_factor_shades", type=float, default=2,
                        help="Z-factor to scale elevation values for shades (default: 2)")
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
                                             z_factor_shades=args.z_factor_shades)
    print("Computed standard hillshade from DEM.")

    # Compute the normalized slope map.
    slope_map = compute_normalized_slope(new_dem, args.cellsize, z_factor_slopes=args.z_factor_slopes)
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
