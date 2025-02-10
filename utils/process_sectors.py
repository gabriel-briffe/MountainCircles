import numpy as np
from skimage import measure
from shapely.geometry import mapping, Polygon
from shapely.ops import transform, unary_union
import sys
import json
import os
import pyproj

def read_asc(file_path):
    with open(file_path, 'r') as f:
        ncols = int(next(f).split()[1])
        nrows = int(next(f).split()[1])
        xllcorner = float(next(f).split()[1])
        yllcorner = float(next(f).split()[1])
        cellsize = float(next(f).split()[1])
        nodata_value = float(next(f).split()[1])
        grid = np.array([list(map(int, map(float, line.split()))) for line in f])
    
    all_values = np.unique(grid)
    return grid, (ncols, nrows), (xllcorner, yllcorner, cellsize), nodata_value, all_values

def pixel_to_map(contour, xllcorner, yllcorner, cellsize, nrows):
    """
    Convert a contour from pixel coordinates [row, col] to map coordinates.
    """
    map_coords = []
    for pt in contour:
        col = pt[1]
        row = pt[0]
        # Calculate the center of the pixel
        x = xllcorner + (col + 0.5) * cellsize
        y = yllcorner + (nrows - row - 0.5) * cellsize
        map_coords.append((x, y))
    return map_coords

def topological_coloring(polygons, number_of_colors, buffer_distance=4000, max_attempts=10000):
    n = len(polygons)
    # Build a graph based on the buffered polygons.
    buffered_polygons = [poly.buffer(buffer_distance) for poly in polygons]
    graph = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if buffered_polygons[i].intersects(buffered_polygons[j]):
                graph[i].add(j)
                graph[j].add(i)

    # Dictionary to store the color for each polygon.
    colors = {}
    # A mutable counter for attempts to avoid deep recursive search.
    attempts = [0]

    def is_safe(node, color):
        """Check if assigning this color to a node is safe."""
        for neighbor in graph[node]:
            if neighbor in colors and colors[neighbor] == color:
                return False
        return True

    def assign_colors(node_index):
        """Recursively assign colors via backtracking."""
        attempts[0] += 1
        print(f"attempting to color: try number {attempts[0]}", end='\r', flush=True)
        # Check if we've exceeded our maximum allowed attempts.
        if attempts[0] > max_attempts:
            return False
        if node_index == len(polygons):
            return True

        for color in range(number_of_colors):
            if is_safe(node_index, color):
                colors[node_index] = color
                if assign_colors(node_index + 1):
                    return True
                del colors[node_index]  # Backtrack
        return False

    # Try to assign colors using backtracking. If it fails within our allowed attempts, use fallback.
    if not assign_colors(0):
        print("Warning : Could not ensure two neighbouring sectors always have different colors; attempting fallback coloring.")
        print("Warning : Buffer is probably too high; try again with a smaller buffer if not happy with the result.")
        for node in range(len(polygons)):
            if node not in colors:
                # Determine colors already used among the node's neighbours.
                forbidden_colors = {colors[nbr] for nbr in graph[node] if nbr in colors}
                # Try to assign one of the original colors that is not forbidden.
                for candidate in range(number_of_colors):
                    if candidate not in forbidden_colors:
                        colors[node] = candidate
                        break
                else:
                    # No allowed color from the palette works; assign a new unique fallback color.
                    fallback_color = max(colors.values(), default=number_of_colors - 1) + 1
                    colors[node] = fallback_color
    return colors

def main(asc_file, source_crs_str, buffer_distance, number_of_colors, simplify_tolerance):

    grid, dimensions, coords, nodata_value, all_values = read_asc(asc_file)
    ncols, nrows = dimensions
    xllcorner, yllcorner, cellsize = coords

    # Set default simplify_tolerance if not provided.
    if simplify_tolerance is None:
        simplify_tolerance = cellsize * 3

    # Create the "results" folder if it doesn't exist.
    result_folder = "results"
    os.makedirs(result_folder, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(asc_file))[0]

    # Prepare the coordinate transformer: from the initial custom CRS to EPSG:4326.
    source_crs = pyproj.CRS(source_crs_str)
    target_crs = pyproj.CRS("EPSG:4326")
    transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
    project = transformer.transform

    # Lists to accumulate merged multipolygons (one per unique v) and their associated id (v)
    all_donuts = []
    all_ids = []
    nb_values = len(all_values)
    # Process each unique value (ignoring nodata_value)
    for v in all_values:
        print(f"Processing sector: {v}/{nb_values}", end='\r', flush=True)
        if v == nodata_value:
            continue

        mask_v = (grid == v).astype(int)
        contours = measure.find_contours(mask_v, 0.5)
        if not contours:
            continue

        polygons = []
        for contour in contours:
            # Convert contour points from pixel to map coordinates.
            map_contour = pixel_to_map(contour, xllcorner, yllcorner, cellsize, nrows)
            polygons.append(Polygon(map_contour))

        # Keep only the polygons whose area is greater than 500000.
        polygons = [p for p in polygons if p.area > 500000]
        # Simplify the polygons.
        polygons = [p.simplify(tolerance=simplify_tolerance) for p in polygons]

        def find_donuts(polygons):
            donuts = []
            while polygons:
                outer_polygon = polygons.pop(0)  # Assume the first (largest) is outer.
                holes = []
                remaining_polygons = []
                for poly in polygons:
                    if outer_polygon.contains(poly):
                        holes.append(poly)
                    else:
                        remaining_polygons.append(poly)
                donut = outer_polygon
                for hole in holes:
                    donut = donut.difference(hole)
                donuts.append(donut)
                polygons = remaining_polygons  # Continue processing the remaining polygons
            return donuts

        donuts = find_donuts(polygons)

        if donuts:
            merged_donut = unary_union(donuts)
            all_donuts.append(merged_donut)
            all_ids.append(int(v))
    print("all sectors vectorized, going to color them")

    # Use topological coloring on the merged geometries with custom neighbour selection.
    all_features = []
    if all_donuts:
        color_mapping = topological_coloring(all_donuts, number_of_colors)
        # Transform the geometries just before writing to file.
        for i, donut in enumerate(all_donuts):
            transformed_geom = transform(project, donut)
            feature = {
                "type": "Feature",
                "geometry": mapping(transformed_geom),
                "properties": {
                    "id": all_ids[i],
                    "COLOR": color_mapping[i] if i in color_mapping else number_of_colors
                }
            }
            all_features.append(feature)

    # Merge all features into a single GeoJSON FeatureCollection.
    geojson = {
        "type": "FeatureCollection",
        "features": all_features
    }
    out_file = os.path.join(result_folder, f"{base_name}.geojson")
    with open(out_file, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"Sectors saved to {out_file}")

if __name__ == "__main__":
    if len(sys.argv) not in [2, 3, 4, 5]:
        print("Usage: python vectorise.py <asc_file> [number_of_colors] <source_crs> [simplify_tolerance]")
        sys.exit(1)
    
    asc_file = sys.argv[1]
    source_crs_str = "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs"
    simplify_tolerance = None
    number_of_colors =7
    buffer_distance = 4000

    main(asc_file, source_crs_str, buffer_distance, number_of_colors, simplify_tolerance)