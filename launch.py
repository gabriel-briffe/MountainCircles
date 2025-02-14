import os
import sys
import multiprocessing
import shutil
import subprocess
from src.shortcuts import normJoin
# from src.config import Config
from src.airfields import Airfields4326
from src.postprocess import postProcess
from src.raster import merge_output_rasters
from pathlib import Path
from src.logging import log_output
import time
from src.use_case_settings import Use_case

from utils import process_sectors


def make_individuals(airfield, config, output_queue=None):
    print("DEBUG: In make_individuals. Airfield object:", airfield)
    print("DEBUG: Airfield type:", type(airfield))
    try:
        airfield_name = getattr(airfield, 'name', None)
        print("DEBUG: Retrieved airfield.name:", airfield_name)
    except Exception as e:
        print("DEBUG: Exception when accessing airfield.name:", e)

    print("DEBUG: Airfield coordinates: x =", getattr(airfield, 'x', 'N/A'),
          "y =", getattr(airfield, 'y', 'N/A'))

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
        if not os.path.isfile(config.calculation_script_path):
            raise FileNotFoundError(
                f"The calculation script/binary does not exist at {config.calculation_script_path}")

        # Call the C++ function
        command = [
            config.calculation_script_path,
            str(airfield.x), str(airfield.y),
            str(config.glide_ratio), str(
                config.ground_clearance), str(config.circuit_height),
            str(config.max_altitude), str(
                airfield_folder), config.topography_file_path, str(config.exportPasses).lower()
        ]
        print("DEBUG: Running command:", command)
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
        return  # Exit if there was an error with calculation_script_path

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
    print(f"cleaning {calc_folder_path}")
    # List all items (files only, as subfolders are not expected)
    folders = [item for item in os.listdir(calc_folder_path) if os.path.isdir(normJoin(calc_folder_path, item))]


    def move_mountain_passes(folder_name, file_path, destination_path):
        #move the folder_path to the destination_path and create the path if it doesn't exist
        os.makedirs(destination_path, exist_ok=True)
        shutil.move(file_path, normJoin(destination_path, f"{folder_name}.csv"))

    # Iterate over files in the calculation folder
    passes_folder = normJoin(calc_folder_path, "individual passes")
    for folder in folders:
        #skip item "individual passes"
        if folder == "individual passes":
            continue
        folder_path = normJoin(calc_folder_path, folder)
        for file in os.listdir(folder_path):
            file_path = normJoin(calc_folder_path, folder, file)
            if os.path.isfile(file_path):
                if file_path.endswith("mountain_passes.csv"):
                    print(f"moving {file_path} to {passes_folder}")
                    move_mountain_passes(folder, file_path, passes_folder)

    #remove all folders in the calculation folder except for the passes folder
    for folder in folders:
        if folder != "individual passes" and folder!= "sector_raster":
            print(f"removing {normJoin(calc_folder_path, folder)}")
            shutil.rmtree(normJoin(calc_folder_path, folder))

    # Remove files in the calculation folder matching specified criteria
    for file in os.listdir(config.calculation_folder_path):
        if (file.endswith('.asc') and not file.endswith('_sectors.asc')) or file.endswith('_customCRS.geojson') or file.endswith('_noAirfields.geojson'):
            os.remove(normJoin(config.calculation_folder_path, file))


def main(use_case_file, output_queue=None):
    print("DEBUG: Entering launch.main with use_case_file:", use_case_file)
    start_time = time.time()

    # Load the new use case settings from the YAML file.
    use_case = Use_case(use_case_file=use_case_file)
    print("DEBUG: Use_case loaded:")
    print(f"  calculation_script: {use_case.calculation_script}")
    print(f"  calculation_folder_path: {use_case.calculation_folder_path}")
    print(f"  airfield_file: {use_case.airfield_file_path}")
    print(f"  topography_file: {use_case.topography_file_path}")
    print(f"  merged_prefix: {use_case.merged_prefix}")
    print(f"  exportPasses: {use_case.exportPasses}")

    # Load the airfields file using the new use_case settings
    converted_airfields = Airfields4326(use_case).convertedAirfields
    print("DEBUG: Number of airfields loaded:", len(converted_airfields))

    # Use multiprocessing to make individual files for each airfield
    with multiprocessing.Pool() as pool:
        pool.starmap(make_individuals, [
            (airfield, use_case, output_queue) for airfield in converted_airfields
        ])

    # Build the filenames using the new use_case properties.
    sectors_file = f'{use_case.merged_prefix}_{use_case.calculation_name}_sectors.asc'
    merged_file = f'{use_case.merged_prefix}_{use_case.calculation_name}.asc'
    
    # Merge the output rasters.
    merge_output_rasters(use_case, merged_file, sectors_file, output_queue)
    
    # Process sectors (make sure process_sectors is updated if it depends on config)
    process_sectors.main(use_case, 4000, 7, None)
    print("finished processing sectors")

    # Clean temporary files if requested
    if use_case.clean_temporary_raster_files:
        print("cleaning temporary files")
        clean(use_case)
        print("cleaned temporary files")

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Finished! did it in: {elapsed_time:.2f} seconds")
    time.sleep(0.2)


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
