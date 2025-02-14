import os
import csv
import json
from typing import List
from pyproj import Transformer

from src.shortcuts import normJoin


class Airfield:
    def __init__(self, parts):
        self.name = parts[0]
        self.x = parts[1]
        self.y = parts[2]



class Airfields4326:
    def __init__(self, config):
        self.filePath = config.airfield_file_path  
        self.destinationCRS = config.CRS  
        # print(f"DEBUG: Destination CRS: {self.destinationCRS}")
        self.convertedAirfields = convert_airfields(read_airfields(self.filePath),self.destinationCRS)
        csv_to_geojson(config)



def read_airfields(filename: str) -> List[List]:
    airfields = []
    with open(filename, 'r') as file:
        print("reading airfields")
        next(file)        # Skip the header line
        for line in file:
            parts = line.split(",")
            if len(parts) == 3:
                airfields.append(Airfield(parts))
    return airfields



def convert_airfields(airfields4326,CRS):
    converted_airfields=[]
    transformer = Transformer.from_crs("EPSG:4326", CRS)

    for airfield in airfields4326:
        x, y = transformer.transform(airfield.y, airfield.x)  # Note: order is reversed here for geographic coordinates
        converted_airfields.append(Airfield([airfield.name,x,y]))
    return converted_airfields


def csv_to_geojson(config):
    # Extract base filename without extension
    base_filename = config.use_case_name
    output_dir = normJoin(config.result_folder, 'airfields')
    geojson_file_path = normJoin(output_dir, f"{base_filename}.geojson")

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Initialize GeoJSON structure with the specified format
    geojson = {
        "type": "FeatureCollection",
        "name": "AF_from_csv_no_conversion",  # You might want to change this to something more appropriate for airfields
        "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" }},
        "features": []
    }

    with open(config.airfield_file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Create a feature for each row in CSV
            feature = {"type": "Feature","properties": { "name": row['name']} , "geometry": { "type": "Point", "coordinates": [float(row['x']),float(row['y'])] }}
            geojson['features'].append(feature)

    # Write the GeoJSON to file
    with open(geojson_file_path, 'w') as geojson_file:
        json.dump(geojson, geojson_file, indent=2)

    print(f"GeoJSON file created at: {geojson_file_path}")



