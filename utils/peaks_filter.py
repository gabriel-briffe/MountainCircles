import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import re

def convert_lat(lat_str):
    """Convert a latitude string of format DDMM.mmmN/S to decimal degrees."""
    try:
        # Remove the direction (last character) and convert the rest into a float.
        value = float(lat_str[:-1])
    except ValueError:
        return None
    # Extract degrees as the integer part of the quotient when divided by 100.
    degrees = int(value / 100)
    # The remainder (value - degrees*100) represents minutes with decimals.
    minutes = value - degrees * 100
    latitude = degrees + minutes / 60.0
    if lat_str[-1] == 'S':
        latitude = -latitude
    return latitude

def convert_lon(lon_str):
    """Convert a longitude string of format DDDMM.mmmE/W to decimal degrees."""
    try:
        value = float(lon_str[:-1])
    except ValueError:
        return None
    degrees = int(value / 100)
    minutes = value - degrees * 100
    longitude = degrees + minutes / 60.0
    if lon_str[-1] == 'W':
        longitude = -longitude
    return longitude

def filter_highest_peaks_spatial(input_csv, output_geojson):
    # Read the CSV file (header is present)
    df = pd.read_csv(input_csv, sep=';')
    
    # Debug: Print total points and count of invalid coordinates
    total_points = df.shape[0]
    invalid_lat = df['lat'].apply(convert_lat).isnull()
    invalid_lon = df['lon'].apply(convert_lon).isnull()
    num_invalid = (invalid_lat | invalid_lon).sum()
    
    print(f"Total points: {total_points}")
    print(f"Invalid points: {num_invalid}")

    # Create a GeoDataFrame using converted coordinates
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(
        df['lon'].apply(convert_lon), 
        df['lat'].apply(convert_lat)
    ))
    
    # Set the CRS to WGS84 (EPSG:4326)
    gdf.set_crs(epsg=4326, inplace=True)
    
    # Transform to a projected CRS (EPSG:3857 is in meters) for spatial operations
    gdf_metric = gdf.to_crs(epsg=3857)
    
    # Build the spatial index from the metric GeoDataFrame
    sindex = gdf_metric.sindex
    
    highest_peaks_rows = []
    # Iterate over each peak (now in metric coordinates)
    for idx, row in gdf_metric.iterrows():
        # Create a buffer of 5000 meters (5 km) around the point
        buffered_geom = row.geometry.buffer(5000)
        # Use the spatial index to quickly get candidate points whose bounding boxes intersect the buffer
        possible_matches_index = list(sindex.intersection(buffered_geom.bounds))
        possible_matches = gdf_metric.iloc[possible_matches_index]
        # Further filter candidates to those whose geometries actually intersect the buffer
        nearby_peaks = possible_matches[possible_matches.intersects(buffered_geom)]
        
        # Check if the current point is the highest in its vicinity
        if row['elev'] == nearby_peaks['elev'].max():
            highest_peaks_rows.append(row)
    
    # Create a new GeoDataFrame from the highest peaks rows
    highest_peaks_gdf = gpd.GeoDataFrame(highest_peaks_rows, columns=gdf_metric.columns)
    # Set the CRS for the new GeoDataFrame using the metric CRS
    highest_peaks_gdf.set_crs(gdf_metric.crs, inplace=True)
    # Convert back to EPSG:4326
    highest_peaks_gdf = highest_peaks_gdf.to_crs(epsg=4326)
    highest_peaks_gdf.to_file(output_geojson, driver='GeoJSON')

# Example usage
filter_highest_peaks_spatial('data/passes/mountain_peaks_FR_CH_IT.csv', 'tests/highest_peaks.geojson')
