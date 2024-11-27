from typing import List
from pyproj import Transformer


def read_airfields(filename: str) -> List[List]:
    airfields = []
    with open(filename, 'r') as file:
        print("reading airfields")
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



class Airfield:
    def __init__(self, parts):
        self.name = parts[0]
        self.x = parts[1]
        self.y = parts[2]



class Airfields4326:
    def __init__(self, config):
        self.filePath = config.airfield_file_path  
        self.destinationCRS = config.CRS  
        self.convertedAirfields = convert_airfields(read_airfields(self.filePath),self.destinationCRS)  

