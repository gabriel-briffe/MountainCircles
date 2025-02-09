import numpy as np
from shapely import geometry, simplify
from shapely.ops import unary_union, linemerge, polygonize
from shapely.validation import make_valid
from multiprocessing import Pool, cpu_count
import sys

# Read the ASCII grid file
def read_asc(file_path):
    with open(file_path, 'r') as f:
        ncols = int(next(f).split()[1])
        nrows = int(next(f).split()[1])
        xllcorner = float(next(f).split()[1])
        yllcorner = float(next(f).split()[1])
        cellsize = float(next(f).split()[1])
        nodata_value = float(next(f).split()[1])
        grid = np.array([list(map(float, line.split())) for line in f])
    return grid, (ncols, nrows), (xllcorner, yllcorner, cellsize), nodata_value

# Vectorize a single chunk of the grid
def vectorize_chunk(chunk, chunk_coords, coords, nodata_value):
    xllcorner, yllcorner, cellsize = coords
    x0, y0 = chunk_coords
    polygons = []
    visited = np.zeros_like(chunk, dtype=bool)
    
    def dfs(x, y, value):
        stack = [(x, y)]
        points = []
        while stack:
            cx, cy = stack.pop()
            if (0 <= cx < chunk.shape[1] and 0 <= cy < chunk.shape[0] and 
                not visited[cy][cx] and chunk[cy][cx] == value):
                visited[cy][cx] = True
                points.append((cx * cellsize + xllcorner + x0*cellsize, cy * cellsize + yllcorner + y0*cellsize))
                stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
        # Only create a polygon if we have at least 4 points
        return [geometry.Polygon(points)] if len(points) >= 4 else []
    
    for y in range(chunk.shape[0]):
        for x in range(chunk.shape[1]):
            if not visited[y][x] and chunk[y][x] != nodata_value:
                new_polygons = dfs(x, y, chunk[y][x])
                if new_polygons:  # Check if polygons were created
                    polygons.extend(new_polygons)

    return polygons

# Worker function for multiprocessing
def worker(args):
    chunk, chunk_coords, coords, nodata_value = args
    return vectorize_chunk(chunk, chunk_coords, coords, nodata_value)

def remove_repeated_points(polygon):
    lines = linemerge([polygon.exterior] + list(polygon.interiors))
    new_polygon = unary_union(polygonize([lines]))
    return new_polygon

# Main execution
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py ")
        sys.exit(1)

    asc_file = sys.argv[1]
    grid, dimensions, coords, nodata_value = read_asc(asc_file)
    ncols, nrows = dimensions
    chunk_size = 500  # Adjust based on your system's memory and CPU

    # Split grid into chunks
    chunks = []
    for i in range(0, nrows, chunk_size):
        for j in range(0, ncols, chunk_size):
            chunk = grid[i:i+chunk_size, j:j+chunk_size]
            chunks.append((chunk, (j, i), coords, nodata_value))

    # Use multiprocessing to vectorize chunks
    with Pool(processes=cpu_count()) as pool:
        results = pool.map(worker, chunks)

    # Process polygons to ensure they are valid
    all_polygons = []
    for chunk_polygons in results:
        for poly in chunk_polygons:
            if not poly.is_valid:
                print(f"Invalid polygon found: ")
                valid_poly = make_valid(poly)
                if valid_poly.is_valid:
                    all_polygons.append(valid_poly)
                else:
                    print(f"Could not make polygon valid: {poly}")
            else:
                all_polygons.append(poly)

    # Clean up polygons (remove repeated points and simplify)
    cleaned_polygons = [remove_repeated_points(simplify(poly, 0.001, preserve_topology=True)) for poly in all_polygons]

    # Apply a tiny buffer to resolve any remaining topological issues
    buffered_polygons = [poly.buffer(0) for poly in cleaned_polygons]

    final_polygons = unary_union(buffered_polygons)

    # Save or further process the polygons here
    print(f"Vectorized {len(final_polygons)} polygons.")