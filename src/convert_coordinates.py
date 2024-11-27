from pyproj import Transformer

def transform_airfield_coordinates(input_file_path, output_file_path,CRS):
    # Define the custom projection
    custom_crs = "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs"

    # Initialize the transformer from WGS84 to custom CRS
    transformer = Transformer.from_crs("EPSG:4326", custom_crs)
    
    try:
        # Open input file for reading
        with open(input_file_path, 'r') as infile:
            # Open output file for writing
            with open(output_file_path, 'w') as outfile:
                for line in infile:
                    # Strip whitespace and split by space
                    parts = line.strip().split(',', 1)
                    if len(parts) != 2:
                        continue  # Skip lines not in the expected format
                    
                    airfield_name, coords = parts
                    # Split coordinates by comma
                    lat, lon = map(float, coords.split(','))

                    # Transform coordinates
                    x, y = transformer.transform(lon, lat)  # Note: order is reversed here for geographic coordinates
                    # Write to output file with space-separated coordinates
                    outfile.write(f"{airfield_name},{x:.4f},{y:.4f}\n")
        
        print(f"Transformation completed. Results written to {output_file_path}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Example usage
# input_file_path = 'terrains4326.txt'
# output_file_path = 'terrainscustom.txt'
# transform_airfield_coordinates(input_file, output_file_path)