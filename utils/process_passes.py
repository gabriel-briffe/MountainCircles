import pandas as pd
import os
from shapely.geometry import Point
import json
import pyproj
from geojson import Feature, FeatureCollection, Point
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from src.shortcuts import normJoin


def collect_and_merge_csv_files(root_folder):
    """
    Collect and merge all CSV files containing mountain pass data.

    Args:
    root_folder (str): Path to the root folder containing the CSV files
    Returns:
    pd.DataFrame: Merged dataframe containing all pass data
    """
    # List to store all dataframes
    dfs = []

    # Walk through all subdirectories and get all file path that ends with .csv
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            # Convert file extension to lower case for a case-insensitive match.
            if file.lower().endswith('.csv'):
                file_path = normJoin(root, file)
                print(f"DEBUG: Found CSV file: {file_path}")  # Debug statement
                try:
                    df = pd.read_csv(file_path)
                    dfs.append(df)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    if not dfs:
        raise ValueError("No valid mountain passes files found")

    # Merge all dataframes
    merged_df = pd.concat(dfs, ignore_index=True)

    # Remove duplicates based on coordinates
    merged_df = merged_df.drop_duplicates(subset=['x', 'y'])

    return merged_df


def convert_to_4326_geojson(df, input_crs, output_path):
    """
    Convert DataFrame with x,y coordinates to GeoJSON in EPSG:4326

    Args:
    df (pd.DataFrame): Input DataFrame with 'x' and 'y' columns
    input_crs (str): The CRS of the input coordinates (e.g., 'EPSG:32632')
    output_path (str): Path where to save the GeoJSON file
    """
    try:
        # Define coordinate transformations
        source_crs = pyproj.CRS(input_crs)
        target_crs = pyproj.CRS("EPSG:4326")
        transformer = pyproj.Transformer.from_crs(
            source_crs, target_crs, always_xy=True)

        # Transform coordinates and create features
        features = []
        for _, row in df.iterrows():
            # Transform point
            point = ShapelyPoint(row['x'], row['y'])
            transformed_point = transformer.transform(point.x, point.y)

            # Create GeoJSON Feature
            feature = Feature(geometry=Point(transformed_point),
                              properties=dict(row.drop(['x', 'y'])))
            features.append(feature)

        # Create FeatureCollection
        fc = FeatureCollection(features)

        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save to GeoJSON
        with open(output_path, 'w') as f:
            json.dump(fc, f)

        print(f"Converted data saved to {output_path}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def find_closest_pass(mountain_passes_path, custom_points_path, output_path):
    """
    Find the closest existing mountain pass for each calculated pass point using GeoJSON files.

    Args:
    mountain_passes_path (str): Path to the existing mountain passes GeoJSON file (EPSG:4326)
    custom_points_path (str): Path to the calculated passes GeoJSON file (EPSG:4326)
    output_path (str): Path where to save the output GeoJSON file
    """
    try:
        # Load the mountain passes GeoJSON
        with open(mountain_passes_path, 'r') as f:
            passes_data = json.load(f)

        print(
            f"Debug: Total features in mountain passes file: {len(passes_data['features'])}")

        passes = []
        passes_properties = []
        for feature in passes_data['features']:
            try:
                geom = shape(feature['geometry'])
                # Changed to direct type comparison due to unusual behavior
                if type(geom).__name__ == 'Point':  # Ensure we're only dealing with Point objects
                    passes.append(geom)
                    
                    # Ensure that the 'ele' field is stored as an integer.
                    ele_raw = feature['properties'].get('ele', 0)
                    if ele_raw is None:
                        ele_value = 0
                    elif isinstance(ele_raw, (int, float)):
                        ele_value = int(ele_raw)
                    else:
                        # Treat ele_raw as a string and remove extraneous characters
                        ele_str = str(ele_raw).strip()
                        import re
                        # This regex captures numbers with optional decimals and optional signs.
                        numbers = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", ele_str)
                        if numbers:
                            if len(numbers)>1:
                                ele_value = max(numbers)
                                print(f"Debug: Found {len(numbers)} elevations for {feature['properties'].get('name', '')}: {ele_raw}, choosed {ele_value}")
                            try:
                                ele_value = int(float(numbers[0]))
                            except (ValueError, TypeError) as conv_err:
                                print(f"Debug: Could not convert ele value {ele_raw} to int after regex: {conv_err}")
                                ele_value = 0
                        else:
                            ele_value = 0
                    
                    passes_properties.append({
                        'id': feature['properties'].get('id', 'No_ID'),
                        'name': feature['properties'].get('name', ''),
                        'ele': ele_value
                    })
                else:
                    print(f"Debug: Skipped non-Point geometry: {type(geom)}")
            except Exception as e:
                print(f"Debug: Error processing pass feature: {e}")

        print(
            f"Debug: Number of valid point geometries in passes: {len(passes)}")

        # Load the custom points GeoJSON
        with open(custom_points_path, 'r') as f:
            points_data = json.load(f)

        print(
            f"Debug: Total features in custom points file: {len(points_data['features'])}")

        points = []
        for feature in points_data['features']:
            try:
                point = shape(feature['geometry'])
                # Changed to direct type comparison due to unusual behavior
                # Ensure we're only dealing with Point objects
                if type(point).__name__ == 'Point':
                    points.append(point)
                else:
                    print(
                        f"Debug: Skipped non-Point geometry in custom points: {type(point)}")
            except Exception as e:
                print(f"Debug: Error processing custom point feature: {e}")

        print(
            f"Debug: Number of valid point geometries in custom points: {len(points)}")

        # Create a spatial index for faster queries
        if not passes:
            raise ValueError(
                "No valid pass geometries found in the mountain passes file.")
        passes_tree = STRtree(passes)

        # Define the buffer distance (1km)
        buffer_distance = 1000  # in meters

        def find_nearest_pass(point):
            buf = point.buffer(buffer_distance)
            possible_matches = passes_tree.query(buf)
            closest_pass = None
            min_distance = float('inf')
            for idx in possible_matches:
                pass_geom = passes[idx]
                distance = point.distance(pass_geom)
                if distance < min_distance:
                    min_distance = distance
                    closest_pass = idx
            if closest_pass is not None:
                return {
                    'geometry': passes[closest_pass],
                    'pass_id': passes_properties[closest_pass]['id'],
                    'name': passes_properties[closest_pass]['name'],
                    'ele': passes_properties[closest_pass]['ele'],
                    'distance': min_distance
                }
            return None

        # Find closest pass for each point
        results = [find_nearest_pass(point) for point in points if type(
            point).__name__ == 'Point']
        output_data = [res for res in results if res is not None]

        # Eliminate duplicates based on 'pass_id'
        unique_results = []
        seen_ids = set()
        for result in output_data:
            pass_id = result['pass_id']
            if pass_id not in seen_ids:
                unique_results.append(result)
                seen_ids.add(pass_id)

        # Prepare GeoJSON output
        if unique_results:
            features = [
                Feature(
                    geometry=result['geometry'],
                    properties={
                        # 'pass_id': result['pass_id'],
                        # 'name': result['name'],
                        # 'ele': result['ele'],
                        # 'distance': result['distance'],
                        'namele': f"{result['name']} {result['ele']}"
                    }
                )
                for result in unique_results
            ]
            feature_collection = FeatureCollection(features)

            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save to GeoJSON
            with open(output_path, 'w') as f:
                json.dump(feature_collection, f)
            print(f"Output written to {output_path}")
        else:
            print("No matches found within 1km or all results were duplicates")

    except Exception as e:
        print(f"An error occurred: {e}")


def process_passes(root_folder, input_crs, intermediate_geojson_path, mountain_passes_path, output_path):
    """
    Main function to process passes from CSV to final filtered shapefile

    Args:
    root_folder (str): Folder containing CSV files
    input_crs (str): CRS of the input coordinates (e.g., 'EPSG:32632')
    intermediate_geojson_path (str): Path for intermediate shapefile
    mountain_passes_path (str): Path to existing mountain passes shapefile
    output_path (str): Path for final output shapefile
    """
    # Collect and merge CSV files
    merged_df = collect_and_merge_csv_files(root_folder)

    # Convert to 4326 shapefile
    convert_to_4326_geojson(merged_df, input_crs, intermediate_geojson_path)

    # Find closest passes and filter
    find_closest_pass(mountain_passes_path,
                      intermediate_geojson_path, output_path)

    # Optionally clean up intermediate file
    if os.path.exists(intermediate_geojson_path):
        os.remove(intermediate_geojson_path)



if __name__ == "__main__":
    # Example usage
    root_folder = "./results/three"
    input_crs = "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs"
    intermediate_geojson_path = normJoin(
        "results", "three", "intermediate_passes.geojson")
    mountain_passes_path = normJoin(
        "data", "passes", "passesosmalps.geojson")
    output_path = normJoin("results", "passes", "passes4326alps.geojson")

    process_passes(root_folder, input_crs, intermediate_geojson_path,
                   mountain_passes_path, output_path)
