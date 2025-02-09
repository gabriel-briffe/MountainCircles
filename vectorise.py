import numpy as np
from shapely import MultiPolygon
from skimage import measure
from shapely.geometry import mapping, LineString, Polygon
from shapely.ops import polygonize, unary_union
import sys
import json
import os

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

def main():
    if len(sys.argv) not in [2, 3]:
        print("Usage: python vectorise.py <asc_file> [simplify_tolerance]")
        sys.exit(1)
    
    asc_file = sys.argv[1]
    grid, dimensions, coords, nodata_value, all_values = read_asc(asc_file)
    ncols, nrows = dimensions
    xllcorner, yllcorner, cellsize = coords
    
    if len(sys.argv) == 3:
        simplify_tolerance = float(sys.argv[2])
    else:
        simplify_tolerance = cellsize * 5

    # Create the "results" folder if it doesn't exist.
    result_folder = "results"
    os.makedirs(result_folder, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(asc_file))[0]

    # List to store all GeoJSON features.
    all_features = []

    # Process each value (ignoring nodata_value)
    for v in all_values:
        if v == nodata_value:
            continue
        
        print(f"Processing value: {v}")

        mask_v = (grid == v).astype(int)
        contours = measure.find_contours(mask_v, 0.5)
        if not contours:
            continue

        polygons = []
        for contour in contours:
            # Convert contour points from pixel to map coordinates
            map_contour = pixel_to_map(contour, xllcorner, yllcorner, cellsize, nrows)
            polygons.append(Polygon(map_contour))

        # Keep the polygons whose area is greater than 1000000
        polygons = [p for p in polygons if p.area > 500000]
        #simplify the polygons
        polygons = [p.simplify(tolerance=simplify_tolerance) for p in polygons]

        # Function to find outer polygons and their holes ("donuts")
        def find_donuts(polygons):
            donuts = []
            while polygons:
                outer_polygon = polygons.pop(0)  # Assume the first (largest) is outer
                holes = []

                # Check for holes in this outer polygon
                remaining_polygons = []
                for poly in polygons:
                    if outer_polygon.contains(poly):
                        holes.append(poly)
                    else:
                        remaining_polygons.append(poly)
                
                # Create the donut by differencing the outer polygon with holes
                donut = outer_polygon
                for hole in holes:
                    donut = donut.difference(hole)
                
                donuts.append(donut)
                polygons = remaining_polygons  # Continue processing the remaining polygons

            return donuts

        # Generate donuts from polygons
        donuts = find_donuts(polygons)

        # Create features for the current value, adding an "id" field with the value 'v'
        for donut in donuts:
            all_features.append({
                "type": "Feature",
                "geometry": mapping(donut),
                "properties": {"id": int(v)}
            })

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
    main()