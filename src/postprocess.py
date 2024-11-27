import os
import shutil
import subprocess


def generate_contours(inThisFolder, config, ASCfilePath, contourFileName):
    """Generate contour lines from the input raster file using gdal_contour from the specified Conda environment."""
    try:
        # Define the path to the Conda executable
        conda_path = config.conda_path
        gdal_env = config.conda_gdal_env

        # Check if the Conda path exists
        if not os.path.isfile(conda_path):
            raise FileNotFoundError(f"Conda executable not found: {conda_path}")

        # Paths for input ASC file and output GPKG
        gpkg_path = os.path.join(inThisFolder, f'{contourFileName}.gpkg')

        # Construct the command to run gdal_contour in the specified conda environment
        command = [
            conda_path, "run", "-n", gdal_env,
            "gdal_contour", 
            '-b', '1', 
            '-a', 'ELEV', 
            '-i', str(config.contour_height), 
            '-f', 'GPKG', 
            ASCfilePath, 
            gpkg_path
        ]
        
        # Execute the command and capture output for debugging purposes
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        # Check if the command was successful
        if result.returncode == 0:
            print(f"Contours created in {inThisFolder}")
        else:
            print("Command failed to execute successfully.")
            print("Error output:", result.stderr)
            print("Standard output:", result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"An error occurred while creating contours: {e}")
        print("Error output:", e.stderr)
    except FileNotFoundError as e:
        print(f"Environment or executable not found: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def create4326geosonContours(inThisFolder, config, contourFileName):
    """Generate contour lines from the input raster file using gdal_contour from the specified Conda environment."""
    try:
        gpkg_path = os.path.join(inThisFolder, f'{contourFileName}.gpkg')
        geojson_path = os.path.join(inThisFolder, f'{contourFileName}-{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}.geojson')

        conda_path = config.conda_path  # Assuming this is where your conda is installed
        gdal_env = config.conda_gdal_env

        command = [
            conda_path, "run", "-n", gdal_env, "ogr2ogr",
            "-f", "GeoJSON",
            "-s_srs", f"{config.CRS}",
            "-t_srs", "EPSG:4326",
            "-sql", f"SELECT CAST(CAST(ELEV AS INTEGER) AS TEXT) AS ELEV, * FROM \"contour\"",  #here contour is the layer, name, do not modify!
            geojson_path,
            gpkg_path
        ]

        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Contours converted to GeoJSON in EPSG:4326: {geojson_path}.geojson")
        else:
            print("Command failed to execute successfully.")
            print("Error output:", result.stderr)
            print("Standard output:", result.stdout)      

        # Run the command without output
        # with open(os.devnull, 'w') as devnull:
        #     subprocess.run(command, stdout=devnull, stderr=devnull, check=True)
        # print(f"Contours converted to GeoJSON in EPSG:3857 at {geojson_path}")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while converting contours: {e}")
        print("Error output:", e.stderr)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while creating contours: {e}")
    except FileNotFoundError as e:
        print(f"Environment or executable not found: {e}")


def copyMapCss(inThisFolder, config, contourFileName):
    try:
        #copy mapcss for gurumaps export
        mapcss_file = os.path.join(inThisFolder,f'{contourFileName}-{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}.mapcss')
        shutil.copy2(config.mapcssTemplate, mapcss_file)
        print(f"mapcss copied successfully to {mapcss_file}")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred while creating contours: {e}")
    except FileNotFoundError as e:
        print(f"Environment or executable not found: {e}")




def postProcess(inThisFolder, config, ASCfilePath, contourFileName):
    generate_contours(inThisFolder, config, ASCfilePath, contourFileName)
    if (config.gurumaps):
        create4326geosonContours(inThisFolder, config, contourFileName)
        copyMapCss(inThisFolder, config, contourFileName)