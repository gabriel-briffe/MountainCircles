import os
import shutil
import yaml
from src.shortcuts import normJoin


def load_(filename):
    with open(filename, "r") as file:
        return yaml.safe_load(file)


def clean(path):
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"deleted {path}")
    except Exception as e:
        print(
            f"An error occurred while trying to delete the directory {path}: {e}"
        )


class Use_case:
    def __init__(self, use_case_file=None, params=None):
        """
        Initializes the Use_case object.
        Either load config from an existing YAML file or use the provided params.
        """
        if use_case_file:
            config = load_(use_case_file)
        elif params:
            config = params
        else:
            raise ValueError(
                "Data Folder Path and either use_case_file or params must be provided."
            )

        # Required parameters (rename if needed)
        self.data_folder_path = config["data_folder_path"]
        self.region = config["region"]                    
        self.use_case_name = config["use_case_name"]        
        
        self.airfield_file_path = config["airfield_file"]   
        self.calculation_script = config["calculation_script"]

        self.glide_ratio = config["glide_ratio"]
        self.ground_clearance = config["ground_clearance"]
        self.circuit_height = config["circuit_height"]
        self.max_altitude = config["max_altitude"]
        self.contour_height = config["contour_height"]
        self.merged_prefix = config["merged_prefix"]

        self.gurumaps_styles = config["gurumaps_styles"]
        self.exportPasses = config["exportPasses"]
        self.delete_previous_calculation = config["delete_previous_calculation"]
        self.clean_temporary_raster_files = config["clean_temporary_raster_files"]

        self.topography_and_crs_folder = normJoin(self.data_folder_path, self.region, "topography and CRS")
        self.airfields_folder = normJoin(self.data_folder_path, self.region, "airfields")
        self.calc_script_folder = normJoin(self.data_folder_path, "common files", "calculation script")
        self.calculation_script_path = normJoin(self.calc_script_folder, self.calculation_script)
        self.result_folder = normJoin(self.data_folder_path, self.region, "RESULTS", self.use_case_name)

        # Compute a calculation name similar to the old Config logic.
        combined_name = f"{self.merged_prefix}_{self.use_case_name}"
        self.calculation_name_short = f"{self.glide_ratio}-{self.ground_clearance}-{self.circuit_height}"
        self.calculation_name = f"{self.glide_ratio}-{self.ground_clearance}-{self.circuit_height}-{self.max_altitude}"
        self.use_case_files_folder = normJoin(self.data_folder_path, self.region, "use case files")
        self.calculation_folder_path = self.create_calculation_folder()
        if self.delete_previous_calculation: clean(self.calculation_folder_path)
        self.merged_output_name = f"{combined_name}_{self.calculation_name_short}"
        self.merged_output_raster_path = normJoin(self.calculation_folder_path,f'{self.merged_output_name}.asc') #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250.asc
        self.merged_output_filename = f"{self.merged_output_name}.geojson" #aa_alps_20-100-250.geojson  
        self.merged_output_filepath = normJoin(self.calculation_folder_path, self.merged_output_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250.geojson    
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
        style_folder=normJoin(self.data_folder_path, "common files", "Guru Map styles")
        self.sector1_style_path=normJoin(style_folder, f"sectors1.mapcss")
        self.sector2_style_path=normJoin(style_folder, f"sectors2.mapcss")
        self.sectors1_style_filepath = normJoin(self.calculation_folder_path, self.sectors1_style_filename) #/Users/gabrielbriffe/Downloads/MountainCircles/Alps/---RESULTS---/three/20-100-250_4200/aa_alps_20-100-250_sectors1.mapcss  

        self.mapcssTemplate = normJoin(style_folder, "circlesAndAirfields.mapcss")

        self.crs_file_path = self.find_crs_file()
        self.CRS = self.read_crs_file()
        self.topography_file_path = self.find_topography_file()

        self.calculate_boundaries()

        #-----------------------FOLDER STRUCTURE---------------------------
        # The following dictionary documents how the folder structure is organized under
        # the data folder. 
        #
        # data_folder_path/
        # ├── Region_1/
        # │   ├── RESULTS/
        # │   │   ├── use_case_1/   
        # │   │   ├── use_case_2/
        # │   │   └── use_case_3/
        # │   │
        # │   ├── airfields/
        # │   ├── use case files/
        # │   ├── mountain passes public unfiltered/
        # │   ├── topography and CRS/
        # │   └── Guru Map background map/
        # │
        # └── common files/
        #     ├── Guru Map styles/
        #     ├── calculation script/
        #     └── help_files/

    def find_crs_file(self,):
        try:
            folder_path = self.topography_and_crs_folder
            #find the file that ends with .txt
            for file in os.listdir(folder_path):
                if file.endswith(".txt"):
                    return normJoin(folder_path, file)
        except Exception as e:
            print(f"[DEBUG] Error reading CRS file '{folder_path}': {e}")

    def read_crs_file(self,):
        with open(self.crs_file_path, 'r') as file:
            first_line = file.readline().strip()
        return first_line

    def find_topography_file(self,):
        try:
            folder_path = self.topography_and_crs_folder
            #find the file that ends with .asc
            for file in os.listdir(folder_path):
                if file.endswith(".asc"):
                    return normJoin(folder_path, file)
        except Exception as e:
            print(f"[DEBUG] Error reading topography file '{folder_path}': {e}")

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
        dir_path = normJoin(self.result_folder ,self.calculation_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return dir_path

    def save(self):
        """
        Save the current Use_case object into a YAML file.
        
        The file is saved in the "use case files" directory inside the region folder.
        If the directory does not exist, it is created.
        
        YAML template structure (each key on its own line):
            use_case_name:  three
            airfield_file:
            topography_file:
            CRS_file:
            use_case_result_folder:
            calculation_script:
            gurumaps_styles:
            glide_ratio: 
            ground_clearance: 
            circuit_height: 
            max_altitude: 
            contour_height: 
            delete_previous_calculation: 
            exportPasses: 
            clean_temporary_raster_files: 
            merged_prefix: aa
        """
        # Ensure that the use case files folder exists:
        use_case_dir = self.use_case_files_folder
        # print(f"[DEBUG] Use case directory: {use_case_dir}")
        if not os.path.exists(use_case_dir):
            # print(f"[DEBUG] Directory does not exist. Creating: {use_case_dir}")
            os.makedirs(use_case_dir, exist_ok=True)

        # Construct the filename using the use_case_name (add .yaml extension)
        file_name = f"{self.use_case_name}.yaml"
        file_path = normJoin(use_case_dir, file_name)
        # print(f"[DEBUG] Use case YAML file will be saved as: {file_path}")

        # Auto-deduce topography and CRS files from topography_and_crs_folder
        topo_crs_folder = self.topography_and_crs_folder
        # print(f"[DEBUG] Looking for topography and CRS files in: {topo_crs_folder}")
        self.topography_file = ""
        self.crs_file = ""
        if os.path.exists(topo_crs_folder):
            for fname in os.listdir(topo_crs_folder):
                fpath = normJoin(topo_crs_folder, fname)
                # print(f"[DEBUG] Checking file: {fpath}")
                if os.path.isfile(fpath):
                    lower_fname = fname.lower()
                    if lower_fname.endswith('.asc'):
                        self.topography_file = fpath
                        # print(f"[DEBUG] Found topography file: {fpath}")
                    elif lower_fname.endswith('.txt'):
                        self.crs_file = fpath
                        # print(f"[DEBUG] Found CRS file: {fpath}")
        else:
            print(f"[DEBUG] Folder does not exist: {topo_crs_folder}")

        # Raise an error if no topography file (.asc) is found.
        if not self.topography_file:
            raise ValueError(f"Topography file path is required. No .asc file found in folder: {topo_crs_folder}")

        # Determine the result folder location for this use case.
        result_folder = normJoin(self.data_folder_path, self.region, "RESULTS", self.use_case_name)
        # print(f"[DEBUG] Result folder is set to: {result_folder}")

        # Prepare the configuration dictionary.
        config_dict = {
            "data_folder_path": self.data_folder_path,
            "region": self.region,
            "use_case_name": self.use_case_name,
            "airfield_file": self.airfield_file_path,
            "topography_file": self.topography_file,
            "CRS_file": self.crs_file,
            "use_case_result_folder": self.result_folder,
            "calculation_script": self.calculation_script,
            "gurumaps_styles": self.gurumaps_styles,
            "glide_ratio": self.glide_ratio,
            "ground_clearance": self.ground_clearance,
            "circuit_height": self.circuit_height,
            "max_altitude": self.max_altitude,
            "contour_height": self.contour_height,
            "delete_previous_calculation": self.delete_previous_calculation,
            "exportPasses": self.exportPasses,
            "clean_temporary_raster_files": self.clean_temporary_raster_files,
            "merged_prefix": self.merged_prefix,
        }

        try:
            with open(file_path, "w") as file:
                yaml.safe_dump(config_dict, file, default_flow_style=False)
            # print(f"[DEBUG] Saved Use_case file: {file_path}")
        except Exception as e:
            print(f"[DEBUG] Error saving Use_case file: {e}")

   