import geopandas as gpd
import os
from shapely.geometry import Point
from shapely.ops import nearest_points

def find_closest_pass(mountain_passes_path, custom_points_path, output_path):
    # Load the mountain passes shapefile
    passes = gpd.read_file(mountain_passes_path)
    
    # Load the custom points shapefile
    points = gpd.read_file(custom_points_path)

    # Create a spatial index for faster queries
    passes_sindex = passes.sindex

    # Define the buffer distance (2km)
    buffer_distance = 1000  # in meters, assuming the CRS is in meters

    # Function to find the nearest pass within 2km
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

# Add this to prevent automatic execution when imported
if __name__ == "__main__":
    # Code that should only run when the script is executed directly
    mountain_passes_path = "data/passes/passesosmpyr.shp"
    custom_points_path = "data/passes/passesfromcalc4326pyr.shp"
    output_path = "results/passes/passes4326pyr.shp"
    find_closest_pass(mountain_passes_path, custom_points_path, output_path)