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

def topological_coloring(polygons, number_of_colors, buffer_distance=5000):
    """
    Performs topological coloring on a list of geometries using a custom graph.
    Graph building steps:
      1. For each polygon, compute its center as the midpoint of its bounding box.
         (center = ((minx+maxx)/2, (miny+maxy)/2))
      2. Compute a buffered version of each polygon using the provided buffer_distance.
      3. For each polygon, compare it to all others:
         - If the buffered polygons intersect, add them to an intersecting candidate list along with their distance.
         - Otherwise, add them to a non-intersecting candidate list.
      4. From the intersecting candidates, keep only the number_of_colors closest.
         If the count is still less than number_of_colors, fill the remainder with the closest non-intersecting polygons.
      5. With the resulting neighbour graph, assign a color recursively.
         
    Returns:
        A mapping {index: color} for each polygon.
    """
    graph = {}
    centers = []
    buffered_polygons = []
    for i, poly in enumerate(polygons):
        minx, miny, maxx, maxy = poly.bounds
        center = ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
        centers.append(center)
        # Create a buffered version of the polygon
        buffered_polygons.append(poly.buffer(buffer_distance))
        graph[i] = []
    
    for i, poly in enumerate(polygons):
        intersecting_candidates = []
        nonintersecting_candidates = []
        for j, other in enumerate(polygons):
            if i == j:
                continue
            dx = centers[i][0] - centers[j][0]
            dy = centers[i][1] - centers[j][1]
            dist = (dx**2 + dy**2)**0.5
            # Use the buffered polygon for the intersection test.
            if buffered_polygons[i].intersects(buffered_polygons[j]):
                intersecting_candidates.append((j, dist))
            else:
                nonintersecting_candidates.append((j, dist))
        # Sort the candidate neighbours based on distance.
        intersecting_candidates.sort(key=lambda x: x[1])
        nonintersecting_candidates.sort(key=lambda x: x[1])
        print(f'got {len(intersecting_candidates)} intersecting candidates')
        print(f'closest non-intersecting candidate: {nonintersecting_candidates[1]}')
        
        # Start with the closest intersecting neighbours.
        neighbors = [j for j, _ in intersecting_candidates][:number_of_colors]

        # If there aren't enough, add the closest non-intersecting ones.
        if len(neighbors) < number_of_colors:
            for candidate in nonintersecting_candidates:
                if candidate[0] not in neighbors:
                    neighbors.append(candidate[0])
                    if len(neighbors) == number_of_colors:
                        break
        graph[i] = neighbors

    colors = {}
    used_colors = {i: set() for i in range(len(polygons))}
    
    def color_node(node, color):
        if node not in colors:
            if color not in used_colors[node]:
                colors[node] = color
                for neighbor in graph[node]:
                    used_colors[neighbor].add(color)
                    next_color = (color + 1) % number_of_colors
                    color_node(neighbor, next_color)
                return True
        return False

    for node in range(len(polygons)):
        if node not in colors:
            for color in range(number_of_colors):
                if color_node(node, color):
                    break

    return colors

def main(asc_file, number_of_colors, source_crs_str, simplify_tolerance):

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

    # Process each unique value (ignoring nodata_value)
    for v in all_values:
        if v == nodata_value:
            continue
        
        # print(f"Processing value: {v}")

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
                    "COLOR": color_mapping[i]
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
    print(f"polygons saved to {out_file}")

if __name__ == "__main__":
    if len(sys.argv) not in [2, 3, 4, 5]:
        print("Usage: python vectorise.py <asc_file> [number_of_colors] <source_crs> [simplify_tolerance]")
        sys.exit(1)
    
    asc_file = sys.argv[1]
    source_crs_str = "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs"
    simplify_tolerance = None
    number_of_colors = 7

    main(asc_file, number_of_colors, source_crs_str, simplify_tolerance)