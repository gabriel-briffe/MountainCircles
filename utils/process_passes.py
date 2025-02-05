import pandas as pd
import geopandas as gpd
import os
from shapely.geometry import Point
from shapely.ops import nearest_points

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
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith('.csv') and 'passes' in file.lower():
                file_path = os.path.join(root, file)
                try:
                    df = pd.read_csv(file_path)
                    dfs.append(df)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    if not dfs:
        raise ValueError("No valid CSV files found")
    
    # Merge all dataframes
    merged_df = pd.concat(dfs, ignore_index=True)
    
    # Remove duplicates based on coordinates
    merged_df = merged_df.drop_duplicates(subset=['x', 'y'])
    
    return merged_df

def convert_to_4326_shapefile(df, input_crs, output_path):
    """
    Convert DataFrame with x,y coordinates to a GeoDataFrame in EPSG:4326
    
    Args:
    df (pd.DataFrame): Input DataFrame with 'x' and 'y' columns
    input_crs (str): The CRS of the input coordinates (e.g., 'EPSG:32632')
    output_path (str): Path where to save the shapefile
    """
    # Create geometry column
    geometry = [Point(xy) for xy in zip(df['x'], df['y'])]
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=input_crs)
    
    # Convert to EPSG:4326
    gdf = gdf.to_crs('EPSG:4326')
    
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save to shapefile
    gdf.to_file(output_path, driver='ESRI Shapefile')
    print(f"Converted data saved to {output_path}")
    
    return gdf

def find_closest_pass(mountain_passes_path, custom_points_path, output_path):
    """
    Find the closest existing mountain pass for each calculated pass point.
    
    Args:
    mountain_passes_path (str): Path to the existing mountain passes shapefile (EPSG:4326)
    custom_points_path (str): Path to the calculated passes shapefile (EPSG:4326)
    output_path (str): Path where to save the output shapefile
    """
    # Load the mountain passes shapefile
    passes = gpd.read_file(mountain_passes_path)
    
    # Load the custom points shapefile
    points = gpd.read_file(custom_points_path)

    # Create a spatial index for faster queries
    passes_sindex = passes.sindex

    # Define the buffer distance (2km)
    buffer_distance = 1000  # in meters

    # Function to find the nearest pass within buffer distance
    def find_nearest_pass(point):
        buf = point.buffer(buffer_distance)
        possible_matches_index = list(passes_sindex.intersection(buf.bounds))
        possible_matches = passes.iloc[possible_matches_index]
        closest_pass = None
        min_distance = float('inf')
        for _, match in possible_matches.iterrows():
            distance = point.distance(match.geometry)
            if distance < min_distance:
                min_distance = distance
                closest_pass = match
        if closest_pass is not None:
            return {
                'geometry': closest_pass.geometry, 
                'pass_id': closest_pass.get('id', 'No_ID'), 
                'name': closest_pass.get('name', ''), 
                'ele': closest_pass.get('ele', ''), 
                'distance': min_distance
            }
        return None

    # Apply the function to each point
    results = points['geometry'].apply(find_nearest_pass)

    # Prepare the output dataframe, eliminating duplicates
    output_data = [res for res in results if res is not None]
    output_gdf = gpd.GeoDataFrame(output_data)
    
    # Drop duplicates based on 'pass_id'
    output_gdf = output_gdf.drop_duplicates(subset='pass_id')

    if not output_gdf.empty:
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Save to Shapefile
        output_gdf.to_file(output_path, driver='ESRI Shapefile')
        print(f"Output written to {output_path}")
    else:
        print("No matches found within 2km or all results were duplicates")

def process_passes(root_folder, input_crs, intermediate_shp_path, mountain_passes_path, output_path):
    """
    Main function to process passes from CSV to final filtered shapefile
    
    Args:
    root_folder (str): Folder containing CSV files
    input_crs (str): CRS of the input coordinates (e.g., 'EPSG:32632')
    intermediate_shp_path (str): Path for intermediate shapefile
    mountain_passes_path (str): Path to existing mountain passes shapefile
    output_path (str): Path for final output shapefile
    """
    # Collect and merge CSV files
    merged_df = collect_and_merge_csv_files(root_folder)
    
    # Convert to 4326 shapefile
    convert_to_4326_shapefile(merged_df, input_crs, intermediate_shp_path)
    
    # Find closest passes and filter
    find_closest_pass(mountain_passes_path, intermediate_shp_path, output_path)
    
    # Optionally clean up intermediate file
    if os.path.exists(intermediate_shp_path):
        os.remove(intermediate_shp_path)
        # Also remove associated files (.dbf, .shx, .prj)
        for ext in ['.dbf', '.shx', '.prj', '.cpg']:
            aux_file = intermediate_shp_path.replace('.shp', ext)
            if os.path.exists(aux_file):
                os.remove(aux_file)

if __name__ == "__main__":
    # Example usage
    root_folder = "./results"
    input_crs = "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs"
    intermediate_shp_path = os.path.join("data", "passes", "intermediate_passes.shp")
    mountain_passes_path = os.path.join("data", "passes", "passesosmpyr.shp")
    output_path = os.path.join("results", "passes", "passes4326pyr.shp")
    
    process_passes(root_folder, input_crs, intermediate_shp_path, mountain_passes_path, output_path) 