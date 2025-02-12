import os
import sys
import multiprocessing
import shutil
import subprocess
from src.shortcuts import normJoin
from src.config import Config
from src.airfields import Airfields4326
from src.postprocess import postProcess
from src.raster import merge_output_rasters
from pathlib import Path
from src.logging import log_output
import time

from utils import process_sectors


def make_individuals(airfield, config, output_queue=None):

    if not config.isInside(airfield.x, airfield.y):
        log_output(
            f'{airfield.name} is outside the map, discarding...', output_queue)
        return
    else:
        log_output(f"launching {airfield.name}", output_queue)

    try:
        # Create folder for this airfield
        airfield_folder = normJoin(config.calculation_folder_path, airfield.name)
        os.makedirs(airfield_folder, exist_ok=True)

        # Check if the output file already exists, if so, skip processing
        ASCfile = normJoin(airfield_folder, 'local.asc')
        log_output(f"ascII file : {ASCfile}", output_queue)
        if os.path.exists(ASCfile):
            log_output(
                f"Output file already exists for {airfield.name}, skipping this airfield.", output_queue)
            log_output(f"Checking ASCfile path: {ASCfile}", output_queue)
            return

        # Ensure the computation executable exists
        if not os.path.isfile(config.compute):
            raise FileNotFoundError(
                f"The calculation script/binary does not exist at {config.compute}")

        # Call the C++ function
        command = [
            config.compute,
            str(airfield.x), str(airfield.y),
            str(config.glide_ratio), str(
                config.ground_clearance), str(config.circuit_height),
            str(config.max_altitude), str(
                airfield_folder), config.topography_file_path, str(config.exportPasses).lower()
        ]

        result = subprocess.run(command, check=True,
                                text=True, capture_output=True)

        # Check for errors or warnings in the output
        if result.stdout:
            log_output(
                f"Output for {airfield.name}: {result.stdout}", output_queue)
        if result.stderr:
            log_output(
                f"Warnings/Errors for {airfield.name}: {result.stderr}", output_queue)

    except subprocess.CalledProcessError as e:
        log_output(
            f"An error occurred while executing external process for {airfield.name}: {e}", output_queue)
        log_output(f"Process output: {e.output}", output_queue)
        log_output(f"Process errors: {e.stderr}", output_queue)
        return  # Exit if there was an error with compute

    except FileNotFoundError as e:
        log_output(
            f"File not found error during processing for {airfield.name}: {e}", output_queue)
        return  # Exit if an expected file was not found

    except IOError as e:
        log_output(
            f"I/O error occurred for {airfield.name}: {e}", output_queue)
        return  # Handle general I/O errors

    except Exception as e:
        log_output(
            f"An unexpected error occurred while processing {airfield.name}: {e}", output_queue)
        return  # Catch-all for any other exceptions

    # Post-process if all went well
    try:
        postProcess(str(airfield_folder), Path(config.calculation_folder_path),
                    config, str(ASCfile), airfield.name, output_queue)
    except Exception as e:
        log_output(
            f"Error during post-processing for {airfield.name}: {e}", output_queue)


def clean(config):
    calc_folder_path = config.calculation_folder_path
    # List all items (files only, as subfolders are not expected)
    items = [item for item in os.listdir(calc_folder_path) if os.path.isdir(normJoin(calc_folder_path, item))]

    mountain_passes_folders = []

    # Iterate over files in the calculation folder
    for item in items:
        item_path = normJoin(calc_folder_path, item)
        for file in os.listdir(item_path):
            file_path = normJoin(calc_folder_path, item, file)
            if os.path.isfile(file_path):
                if file_path.endswith("mountain_passes.csv"):
                    # Mark this file for moving
                    mountain_passes_folders.append(item_path)
                else:
                    os.remove(file_path)

    # If any mountain_passes.csv files exist, move their folders into an "individual passes" folder
    if mountain_passes_folders:
        # print("got mountain passes")
        individual_passes_folder = normJoin(calc_folder_path, "individual passes")
        if not os.path.exists(individual_passes_folder):
            os.makedirs(individual_passes_folder)

        for folder_path in mountain_passes_folders:
            target_path = normJoin(individual_passes_folder, os.path.basename(folder_path))
            # print("target path: ", target_path)
            if os.path.exists(target_path):
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                else:
                    os.remove(target_path)
            shutil.move(folder_path, individual_passes_folder)

    # Remove files in the calculation folder matching specified criteria
    for file in os.listdir(config.calculation_folder_path):
        if (file.endswith('.asc') and not file.endswith('_sectors.asc')) or file.endswith('_customCRS.geojson') or file.endswith('_noAirfields.geojson'):
            os.remove(normJoin(config.calculation_folder_path, file))


def main(config_file, output_queue=None):
    start_time = time.time()

    config = Config(config_file)

    # Example: Print out the paths for verification
    config.print()

    # Read the airfields file
    converted_airfields = Airfields4326(config).convertedAirfields

    # Use multiprocessing to make individual files for each airfield
    with multiprocessing.Pool() as pool:
        pool.starmap(make_individuals, [
                     (airfield, config, output_queue) for airfield in converted_airfields])

    sectors_file = f'{config.merged_output_name}_sectors.asc'
    merged_file = f'{config.merged_output_name}.asc'
    # Merge all output_sub.asc files
    merge_output_rasters(config, merged_file,
                         sectors_file, output_queue)
    
    # Process sectors
    process_sectors.main(config, 4000, 7, None, output_queue)

    # Only clean if clean_temporary_files is True
    if config.clean_temporary_files:
        clean(config)
        log_output("cleaned temporary files", output_queue)

    end_time = time.time()
    elapsed_time = end_time - start_time
    log_output(
        f"Finished!         did it in: {elapsed_time:.2f} seconds", output_queue)
    time.sleep(0.2)  # time to catch the last logs which are polled every 100ms


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
