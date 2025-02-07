import os
import sys
import multiprocessing
import shutil
import subprocess
from src.config import Config
from src.airfields import Airfields4326
from src.postprocess import postProcess
from src.raster import merge_output_rasters
from pathlib import Path
from src.logging import log_output
import time



def make_individuals(airfield, config, output_queue=None):

    if not config.isInside(airfield.x, airfield.y):
        log_output(f'{airfield.name} is outside the map, discarding...',output_queue)
        return
    else:
        log_output(f"launching {airfield.name}",output_queue)

    try:
        # Create folder for this airfield
        airfield_folder = os.path.join(config.calculation_folder, airfield.name)
        os.makedirs(airfield_folder, exist_ok=True)

        # Check if the output file already exists, if so, skip processing
        ASCfile = os.path.join(airfield_folder, 'local.asc')
        if os.path.exists(ASCfile):
            log_output(f"Output file already exists for {airfield.name}, skipping this airfield.",output_queue)
            return 

        # Ensure the computation executable exists
        if not os.path.isfile(config.compute):
            raise FileNotFoundError(f"The compute executable does not exist at {config.compute}")

        # Call the C++ function
        command = [
            config.compute,
            str(airfield.x), str(airfield.y),
            str(config.glide_ratio), str(config.ground_clearance), str(config.circuit_height),
            str(config.max_altitude), str(airfield_folder), config.topography_file_path, str(config.exportPasses).lower()
        ]

        result = subprocess.run(command, check=True, text=True, capture_output=True)
        
        # Check for errors or warnings in the output
        if result.stdout:
            log_output(f"Output for {airfield.name}: {result.stdout}",output_queue)
        if result.stderr:
            log_output(f"Warnings/Errors for {airfield.name}: {result.stderr}",output_queue)

    except subprocess.CalledProcessError as e:
        log_output(f"An error occurred while executing external process for {airfield.name}: {e}",output_queue)
        log_output(f"Process output: {e.output}",output_queue)
        log_output(f"Process errors: {e.stderr}",output_queue)
        return  # Exit if there was an error with compute

    except FileNotFoundError as e:
        log_output(f"File not found error during processing for {airfield.name}: {e}",output_queue)
        return  # Exit if an expected file was not found

    except IOError as e:
        log_output(f"I/O error occurred for {airfield.name}: {e}",output_queue)
        return  # Handle general I/O errors

    except Exception as e:
        log_output(f"An unexpected error occurred while processing {airfield.name}: {e}",output_queue)
        return  # Catch-all for any other exceptions

    # Post-process if all went well
    try:
        postProcess(str(airfield_folder), Path(config.calculation_folder), config, str(ASCfile), airfield.name, output_queue)
    except Exception as e:
        log_output(f"Error during post-processing for {airfield.name}: {e}",output_queue)


def clean(config):
    # Remove all output folders
    for folder in os.listdir(config.calculation_folder):
        folder = os.path.join(config.calculation_folder, folder)
        if os.path.isdir(folder):
            shutil.rmtree(folder)
    # Remove all .asc, .gpkg, *_noAirfields.geojson files
    for file in os.listdir(config.calculation_folder):
        if (file.endswith('.asc') and not file.endswith('_sectors.asc')) or file.endswith('_customCRS.geojson') or file.endswith('_noAirfields.geojson'):
            os.remove(os.path.join(config.calculation_folder, file))



def main(config_file, output_queue=None):
    start_time = time.time()

    config = Config(config_file)
    
    # Example: Print out the paths for verification
    config.print()

    # Read the airfields file
    converted_airfields = Airfields4326(config).convertedAirfields

    # Use multiprocessing to make individual files for each airfield
    with multiprocessing.Pool() as pool:
        pool.starmap(make_individuals, [(airfield, config, output_queue) for airfield in converted_airfields])

    # Merge all output_sub.asc files
    merge_output_rasters(config, f'{config.merged_output_name}.asc', f'{config.merged_output_name}_sectors.asc', output_queue)
    
    # Only clean if clean_temporary_files is True
    if config.clean_temporary_files:
        clean(config)
        log_output("cleaned temporary files", output_queue)

    end_time = time.time()
    elapsed_time = end_time - start_time
    log_output(f"Finished!         did it in: {elapsed_time:.2f} seconds", output_queue)
    time.sleep(0.2) #time to catch the last logs which are polled every 100ms



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
