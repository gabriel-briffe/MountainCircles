import os
import shutil
import subprocess
import json


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
            "-nln", "OGRGeoJSON",
            geojson_path,
            gpkg_path
        ]

        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Contours converted to GeoJSON in EPSG:4326: {geojson_path}")
        else:
            print("Command failed to execute successfully.")
            print("Error output:", result.stderr)
            print("Standard output:", result.stdout)      

    except subprocess.CalledProcessError as e:
        print(f"An error occurred while converting contours: {e}")
        print("Error output:", e.stderr)
    except FileNotFoundError as e:
        print(f"Environment or executable not found: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def merge_geojson_files(inThisFolder, config, contourFileName):
    """
    Merge the GeoJSON files for contours and airfields using JSON parsing.
    
    This function assumes that you want to merge all features from both GeoJSON files.
    """
    try:
        geojson_airfields_path = os.path.join(config.result_folder_path, "airfields", f"{config.name}.geojson")
        geojson_contour_path = os.path.join(inThisFolder, f'{contourFileName}-{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}.geojson')
        merged_geojson_path = os.path.join(inThisFolder, f'{contourFileName}-{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}_airfields.geojson')

        # Read GeoJSON files
        with open(geojson_airfields_path, 'r') as f:
            data_airfields = json.load(f)

        with open(geojson_contour_path, 'r') as f:
            data_contour = json.load(f)

        # Ensure both files are FeatureCollections
        if data_airfields.get("type") != "FeatureCollection" or data_contour.get("type") != "FeatureCollection":
            raise ValueError("Input files must be of type FeatureCollection")

        # Merge the features
        merged_features = data_airfields.get("features", []) + data_contour.get("features", [])

        # Create the merged GeoJSON
        merged_geojson = {
            "type": "FeatureCollection",
            "name": "OGRGeoJSON",
            "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
            "features": merged_features
        }

        with open(merged_geojson_path, 'w') as f:
            json.dump(merged_geojson, f, separators=(',', ':'))

        print(f"GeoJSON files merged successfully. Output file: {merged_geojson_path}")

    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def copyMapCss(inThisFolder, config, contourFileName,extension):
    try:
        #copy mapcss for gurumaps export
        mapcss_file = os.path.join(inThisFolder,f'{contourFileName}-{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}{extension}.mapcss')
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
        copyMapCss(inThisFolder, config, contourFileName,"")
        merge_geojson_files(inThisFolder, config, contourFileName)
        copyMapCss(inThisFolder, config, contourFileName,"_airfields")