import os
import shutil
import json
import numpy as np
import skimage.measure
from shapely.geometry import LineString
import geopandas as gpd
from rasterio.transform import from_origin
import pyproj

def generate_contours_from_asc(inThisFolder, config, ASCfilePath, contourFileName):
    """
    Generates contour lines from an ASCII Grid (.asc) file using NumPy and scikit-image.
    Contours are generated from 0 to max elevation with the given interval.
    """
    try:
        # Read the ASC file
        with open(ASCfilePath, 'r') as f:
            header = [next(f).strip().split() for _ in range(6)]
            data = np.loadtxt(f)

        # Extract header information
        ncols = int(header[0][1])
        nrows = int(header[1][1])
        xllcorner = float(header[2][1])
        yllcorner = float(header[3][1])
        cellsize = float(header[4][1])
        nodata_value = float(header[5][1])

        # Create an affine transformation
        transform = from_origin(xllcorner, yllcorner + nrows * cellsize, cellsize, cellsize)

        # Replace NoData values with NaN for proper handling in contouring
        data[data == nodata_value] = np.nan

        # Print min and max values
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)

        # Generate contours for all elevations
        contour_levels = np.arange(0, min(data_max + config.contour_height, nodata_value), config.contour_height)
        all_contours = []

        for level in contour_levels:
            contours = skimage.measure.find_contours(data, level)
            all_contours.extend(contours)

        # Create a list to store the contour geometries and elevations
        contour_geometries = []
        contour_elevations = []

        # Iterate over all contours
        for contour, level in zip(all_contours, [level for level in contour_levels for _ in range(len(skimage.measure.find_contours(data, level)))]):
            lines = []
            for i in range(len(contour)):
                y, x = contour[i]
                lon, lat = transform * (x, y)
                lines.append((lon, lat))
            line = LineString(lines)
            contour_geometries.append(line)
            contour_elevations.append(level)

        # Create a GeoDataFrame from the contour geometries and elevations
        gdf = gpd.GeoDataFrame(
            {'ELEV': contour_elevations},
            geometry=contour_geometries,
            crs=config.CRS
        )

        gpkg_path = os.path.join(inThisFolder, f'{contourFileName}.gpkg')
        # Write the GeoDataFrame to a GeoPackage file
        gdf.to_file(gpkg_path, driver='GPKG', layer='contour')

        print(f"Contours created successfully in {inThisFolder}")

    except Exception as e:
        print(f"An error occurred: {e}")



def create4326geosonContours_no_gdal(inThisFolder, config, contourFileName):
    """
    Convert contours to GeoJSON in EPSG:4326 without GDAL (ogr/osr).
    """
    try:
        gpkg_path = os.path.join(inThisFolder, f'{contourFileName}.gpkg')
        geojson_path = os.path.join(inThisFolder, f'{contourFileName}_{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}_noAirfields.geojson')

        # Read GeoPackage using GeoPandas
        # Try without specifying layer name first
        gdf = gpd.read_file(gpkg_path)
        # Define coordinate transformations
        # source_crs = pyproj.CRS(config.CRS)
        target_crs = pyproj.CRS("EPSG:4326")
        # transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

        # Reproject the GeoDataFrame using GeoPandas' built-in method
        gdf = gdf.to_crs(target_crs)

        # Convert ELEV to string
        gdf['ELEV'] = gdf['ELEV'].astype(int).astype(str)

        # Write to GeoJSON using GeoPandas
        gdf.to_file(geojson_path, driver='GeoJSON')

        print(f"Contours converted to GeoJSON in EPSG:4326: {geojson_path}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")



def merge_geojson_files(inThisFolder, toThatFolder, config, contourFileName):
    """
    Merge the GeoJSON files for contours and airfields using JSON parsing.
    
    This function assumes that you want to merge all features from both GeoJSON files.
    """
    try:
        geojson_airfields_path = os.path.join(config.result_folder_path, "airfields", f"{config.name}.geojson")
        geojson_contour_path = os.path.join(inThisFolder, f'{contourFileName}_{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}_noAirfields.geojson')
        merged_geojson_path = os.path.join(toThatFolder, f'{contourFileName}_{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}.geojson')

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


def copyMapCss(toThatFolder, config, contourFileName,extension):
    try:
        #copy mapcss for gurumaps export
        mapcss_file = os.path.join(toThatFolder,f'{contourFileName}_{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}{extension}.mapcss')
        shutil.copy2(config.mapcssTemplate, mapcss_file)
        print(f"mapcss copied successfully to {mapcss_file}")

    except Exception as e:
        print(f"Failed to copy mapcss file: {e}")


def postProcess(inThisFolder, toThatFolder, config, ASCfilePath, contourFileName):
    generate_contours_from_asc(inThisFolder, config, ASCfilePath, contourFileName)
    if (config.gurumaps):
        create4326geosonContours_no_gdal(inThisFolder, config, contourFileName)
        # copyMapCss(inThisFolder, config, contourFileName,"_noAirfields")
        merge_geojson_files(inThisFolder, toThatFolder, config, contourFileName)
        copyMapCss(toThatFolder, config, contourFileName,"")