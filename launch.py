import os
import sys
import multiprocessing
import subprocess
from src.config import Config
from src.airfields import Airfields4326
from src.postprocess import postProcess
from src.raster import merge_output_rasters



def make_individuals(airfield, config):

    # Create folder for this airfield
    airfield_folder = os.path.join(config.calculation_folder, airfield.name)
    os.makedirs(airfield_folder, exist_ok=True)

    # Check if the output file already exists, if so, skip processing
    ASCfile = os.path.join(airfield_folder, 'local.asc')
    if os.path.exists(ASCfile):
        print(f"Output file already exists for {airfield.name}, skipping this airfield.")
        return  # Exit the function if the file exists
    
    # Call the C++ function
    try:
        subprocess.run([config.compute, 
                        str(airfield.x), str(airfield.y), 
                        str(config.glide_ratio), str(config.ground_clearance), str(config.circuit_height), 
                        str(config.max_altitude), airfield_folder,config.topography_file_path], 
                       check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while creating contour for {airfield.name}: {e}")
        return  # Exit if there was an error with compute

    # postprocess
    postProcess(airfield_folder, config, ASCfile, airfield.name)



def main(config_file):

    config = Config(config_file)
    
    # Example: Print out the paths for verification
    config.print()

    # Read the airfields file
    converted_airfields = Airfields4326(config).convertedAirfields

    # Use multiprocessing to make individual files for each airfield
    with multiprocessing.Pool() as pool:
        pool.starmap(make_individuals, [(airfield, config) for airfield in converted_airfields])

    # # Merge all output_sub.asc files
    merge_output_rasters(config, f'{config.merged_output_name}.asc')




if __name__ == "__main__":
    # Allow for command line argument to choose config file
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        print("Please choose config file --> python launch.py [config].yaml")
    
    # Ensure the config file exists
    if not os.path.exists(config_file):
        print(f"Error: Configuration file {config_file} not found.")
        sys.exit(1)

    main(config_file)