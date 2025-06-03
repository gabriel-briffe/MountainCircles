import os
import sys
import multiprocessing
import shutil
import subprocess
from src.shortcuts import normJoin
from src.airfields import Airfields4326
from src.postprocess import postProcess2
from src.raster import merge_output_rasters2
from pathlib import Path
from src.logging import log_output
import time
from src.use_case_settings import Use_case
from src.warp import main as warp

from utils import process_sectors
import src.extract_project_tm


def make_individuals(airfield, config, output_queue=None):

    # if not config.isInside(airfield.x, airfield.y):
    #     log_output(
    #         f'{airfield.name} is outside the map, discarding...', output_queue)
    #     return
    # else:
    log_output(f"launching {airfield.name}", output_queue)
    # start_time = time.time()

    try:
        # Create folder for this airfield
        airfield_folder = normJoin(config.calculation_folder_path, airfield.name)
        # os.makedirs(airfield_folder, exist_ok=True)

        # Check if the output file already exists, if so, skip processing
        ASCfile = normJoin(airfield_folder, 'local.asc')
        # log_output(f"ascII file : {ASCfile}", output_queue)
        if os.path.exists(ASCfile):
            log_output(f"Output file already exists for {airfield.name}, skipping this airfield.", output_queue)
            # log_output(f"Checking ASCfile path: {ASCfile}", output_queue)
            return

        # Ensure the computation executable exists
        if not os.path.isfile(config.calculation_script_path):
            raise FileNotFoundError(
                f"The calculation script/binary does not exist at {config.calculation_script_path}")

        # Call the C++ function
        command = [
            config.calculation_script_path,
            str(0), str(0),
            str(config.glide_ratio), str(
                config.ground_clearance), str(config.circuit_height),
            str(config.max_altitude), str(
                airfield_folder), normJoin(airfield_folder, "projected.asc"), str(config.exportPasses).lower()
        ]
        # print("DEBUG: Running command:", command)
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

    # end_time = time.time()
    # log_output(f"Time taken for {airfield.name}: {end_time - start_time:.2f} seconds", output_queue)
    # start_time = time.time()
    
# make a war function for an individual airfield with output_queue
def warp_airfield(airfield,config,output_queue):
    start_time = time.time()
    airfield_folder = normJoin(config.calculation_folder_path, airfield.name)
    
    try:
        warp(airfield_folder, output_queue=output_queue)
        end_time = time.time()
        log_output(f"Time taken for warp for {airfield.name}: {end_time - start_time:.2f} seconds", output_queue)
        start_time = time.time()
    except Exception as e:
        log_output(
            f"Error during warp for {airfield.name}: {e}", output_queue)

# make a postprocess function for an individual airfield with output_queue
def postprocess_airfield(airfield,config,output_queue):
    # start_time = time.time()
    airfield_folder = normJoin(config.calculation_folder_path, airfield.name)
    
    try:
        ASCfile2 = normJoin(airfield_folder, 'local4326.asc')
        naming = f"{airfield.name}_{config.calculation_name_short}"
        postProcess2(str(airfield_folder), Path(config.calculation_folder_path),
                    config, str(ASCfile2), naming, output_queue)
    except Exception as e:
        log_output(
            f"Error during post-processing for {airfield.name}: {e}", output_queue)
    # end_time = time.time()
    # log_output(f"Time taken for post-processing for {airfield.name}: {end_time - start_time:.2f} seconds", output_queue)
    # start_time = time.time()
    #     start_time = time.time()
    #     ASCfile2 = normJoin(airfield_folder, 'local4326.asc')
    #     naming = f"{airfield.name}_{config.calculation_name_short}"
    #     postProcess2(str(airfield_folder), Path(config.calculation_folder_path),
    #                 config, str(ASCfile2), naming, output_queue)
    # except Exception as e:
    #     log_output(
    #         f"Error during post-processing for {airfield.name}: {e}", output_queue)


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
    # print("DEBUG: Entering launch.main with use_case_file:", use_case_file)
    start_time = time.time()

    # Load the new use case settings from the YAML file.
    use_case = Use_case(use_case_file=use_case_file)
    # print("DEBUG: Use_case loaded:")
    print(f"  calculation_script: {use_case.calculation_script}")
    print(f"  calculation_folder_path: {use_case.calculation_folder_path}")
    print(f"  airfield_file: {use_case.airfield_file_path}")
    print(f"  topography_file: {use_case.topography_file_path}")
    print(f"  merged_prefix: {use_case.merged_prefix}")
    print(f"  exportPasses: {use_case.exportPasses}")

    if use_case.delete_previous_calculation:
        use_case.clean()

    # Load the airfields file using the new use_case settings
    airfields = Airfields4326(use_case).list_of_airfields
    # print([(airfield.name, airfield.x, airfield.y) for airfield in airfields])
    print("Number of airfields loaded:", len(airfields))


    #discard airfields that are outside the map
    airfields = [airfield for airfield in airfields if use_case.isInside(airfield.x, airfield.y)]
    print("Number of airfields inside the map:", len(airfields))

    # create folders for each airfield
    for airfield in airfields:
        os.makedirs(normJoin(use_case.calculation_folder_path, airfield.name), exist_ok=True)

    src.extract_project_tm.main(use_case, airfields)

    # Use multiprocessing to make individual files for each airfield
    with multiprocessing.Pool() as pool:
        pool.starmap(make_individuals, [
            (airfield, use_case, output_queue) for airfield in airfields
        ])
    
    # Use multiprocessing to warp each airfield with half the number of cores
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()//2) as pool:
        pool.starmap(warp_airfield, [
            (airfield, use_case, output_queue) for airfield in airfields
        ]) 
    
    # Use multiprocessing to post-process each airfield
    with multiprocessing.Pool() as pool:
        pool.starmap(postprocess_airfield, [
            (airfield, use_case, output_queue) for airfield in airfields
        ])

    print("finished processing individual airfields")
    # Build the filenames using the new use_case properties.
    sectors_file = f'{use_case.merged_prefix}_{use_case.calculation_name}_sectors.asc'
    merged_file = f'{use_case.merged_prefix}_{use_case.calculation_name}.asc'
    print(sectors_file)
    print(merged_file)
    # # Merge the output rasters.
    merge_output_rasters2(use_case, merged_file, sectors_file, output_queue)
    
    # # Process sectors (make sure process_sectors is updated if it depends on config)
    process_sectors.main2(use_case, 4000, 7, None)
    print("finished processing sectors")

    # # Clean temporary files if requested
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
