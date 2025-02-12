import os
import shutil
import yaml

from src.shortcuts import normJoin


def load_config(filename):
    with open(filename, 'r') as file:
        return yaml.safe_load(file)
    
def clean(path):
    try:
        # Check if the directory exists before attempting to remove it
        if os.path.exists(path):
            # Remove the directory and all its contents
            shutil.rmtree(path)
            print(f"deleted {path}")
    except Exception as e:
        print(f"An error occurred while trying to delete the directory {path}: {e}")


class Config:
    def __init__(self, config_file):
        config = load_config(config_file)

        self.name = config['name']

        self.airfield_file_path = config['input_files']['airfield_file']
        self.topography_file_path = config['input_files']['topography_file']
        self.result_folder_path = config['input_files']['result_folder']
        self.compute = config['input_files']['compute']
        self.mapcssTemplate = config['input_files']['mapcssTemplate']
        
        self.CRS = config['CRS']['definition']
        self.CRS_name = config['CRS']['name']

        self.glide_ratio = config['glide_parameters']['glide_ratio']
        self.ground_clearance = config['glide_parameters']['ground_clearance']
        self.circuit_height = config['glide_parameters']['circuit_height']

        self.max_altitude = config['calculation_parameters']['max_altitude']

        self.contour_height = config['rendering']['contour_height']

        self.gurumaps = config["gurumaps"]
        self.exportPasses = config["exportPasses"]
        self.delete_previous_calculation = config["reset_results"]
        self.clean_temporary_files = config.get("clean_temporary_files", False)  # Default to False if not specified

        self.merged_output_name = config["merged_output_name"] #aa
        
        combined_name = f"{self.merged_output_name}_{self.name}" #aa_alps
        self.calculation_name = f"{self.glide_ratio}-{self.ground_clearance}-{self.circuit_height}-{self.max_altitude}" #20-100-250_4200
        self.calculation_folder_path = self.create_calculation_folder() #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200
        if self.delete_previous_calculation: clean(self.calculation_folder_path)
        self.calculation_name_short = f"{self.glide_ratio}-{self.ground_clearance}-{self.circuit_height}" #20-100-250   
        self.merged_output_name = f"{combined_name}_{self.calculation_name_short}" #aa_alps_20-100-250
        self.merged_output_raster_path = normJoin(self.calculation_folder_path,f'{self.merged_output_name}.asc') #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250.asc
        self.merged_output_filename = f"{self.merged_output_name}.geojson" #aa_alps_20-100-250.geojson  
        self.merged_output_filepath = normJoin(self.calculation_folder_path,self.calculation_name, self.merged_output_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250.geojson    
        self.sectors_name = f"{combined_name}_{self.calculation_name_short}_sectors" #aa_alps_20-100-250_sectors  
        self.sectors1_name = f"{combined_name}_{self.calculation_name_short}_sectors1" #aa_alps_20-100-250_sectors1
        self.sectors2_name = f"{combined_name}_{self.calculation_name_short}_sectors2" #aa_alps_20-100-250_sectors2
        self.sectors_filename = f"{self.sectors_name}.asc" #aa_alps_20-100-250_sectors.asc
        self.sectors1_filename = f"{self.sectors1_name}.geojson" #aa_alps_20-100-250_sectors1.geojson   
        self.sectors2_filename = f"{self.sectors2_name}.geojson" #aa_alps_20-100-250_sectors2.geojson   
        self.sectors1_style_filename = f"{self.sectors1_name}.mapcss" #aa_alps_20-100-250_sectors1.mapcss   
        self.sectors2_style_filename = f"{self.sectors2_name}.mapcss" #aa_alps_20-100-250_sectors2.mapcss  
        self.sectors_filepath = normJoin(self.calculation_folder_path, self.sectors_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors.asc
        self.sectors1_filepath = normJoin(self.calculation_folder_path, self.sectors1_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors1.geojson 
        self.sectors2_filepath = normJoin(self.calculation_folder_path, self.sectors2_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors2.geojson 
        self.sectors1_style_filepath = normJoin(self.calculation_folder_path, self.sectors1_style_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors1.mapcss  
        self.sectors2_style_filepath = normJoin(self.calculation_folder_path, self.sectors2_style_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors2.mapcss      
        style_folder=os.path.dirname(self.mapcssTemplate)
        self.sector1_style_path=normJoin(style_folder, f"sectors1.mapcss")
        self.sector2_style_path=normJoin(style_folder, f"sectors2.mapcss")
        self.sectors1_style_filepath = normJoin(self.calculation_folder_path, self.sectors1_style_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors1.mapcss  
        self.calculate_boundaries()



    def calculate_boundaries(self):
        header = {}
        line_count = 0

        with open(self.topography_file_path, 'r') as file:
            for line in file:
                if line_count >= 5:
                    break  # Stop reading after the 5th line
                key, value = line.strip().split()
                header[key.strip()] = float(value.strip())
                line_count += 1

            # Extract necessary data
            ncols = header['ncols']
            nrows = header['nrows']
            xllcorner = header['xllcorner']
            yllcorner = header['yllcorner']
            cellsize = header['cellsize']

            # Calculate corners in the projected coordinate system
            xurcorner = xllcorner + (ncols - 1) * cellsize
            yurcorner = yllcorner + (nrows - 1) * cellsize

            self.minx = xllcorner
            self.maxy = yurcorner
            self.maxx = xurcorner
            self.miny = yllcorner

        
    def isInside(self,x,y):
        return (self.minx<= x <= self.maxx) and (self.miny<= y <= self.maxy)

    def create_calculation_folder(self):
        dir_path = normJoin(self.result_folder_path,self.calculation_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return dir_path

    
    def print(self):
        print(f"airfields: {self.airfield_file_path}")
        print(f"topography: {self.topography_file_path} - {self.CRS_name}")
        print(f"results folder: {self.result_folder_path}")
        print(f"calculating {self.name} with glide {self.glide_ratio}, ground clearance {self.ground_clearance}, circuit height {self.circuit_height}, up to {self.max_altitude}m")
