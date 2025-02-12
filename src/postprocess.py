import os
import shutil
import json
import numpy as np
import skimage.measure
from shapely.geometry import LineString, shape, mapping
import pyproj
from geojson import Feature, FeatureCollection, LineString as GeoJSONLineString
from src.shortcuts import normJoin
from src.logging import log_output


def generate_contours_from_asc(inThisFolder, config, ASCfilePath, contourFileName, output_queue=None):
    """
    Generates contour lines from an ASCII Grid (.asc) file using NumPy and scikit-image.
    Contours are generated from 0 to max elevation with the given interval.
    CRS is the original custom CRS of the topography file.
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

        # Replace NoData values with NaN for proper handling in contouring
        data[data == nodata_value] = np.nan

        # Print min and max values
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)

        # Generate contours for all elevations
        contour_levels = np.arange(
            0, min(data_max + config.contour_height, nodata_value), config.contour_height)
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
                # Convert pixel coordinates to metric coordinates
                metric_x = xllcorner + (x * cellsize)
                # y-axis inversion for metric coordinates
                metric_y = yllcorner + ((nrows - y - 1) * cellsize)
                lines.append((metric_x, metric_y))
            line = LineString(lines)
            contour_geometries.append(line)
            contour_elevations.append(level)
        features = []

        for geometry, elevation in zip(contour_geometries, contour_elevations):
            feature = Feature(geometry=GeoJSONLineString(
                geometry.coords), properties={"ELEV": str(int(elevation))})
            features.append(feature)

        # Create FeatureCollection
        feature_collection = FeatureCollection(features)

        geojson_path = normJoin(
            inThisFolder, f'{contourFileName}_customCRS.geojson')

        # Write to GeoJSON file
        with open(geojson_path, 'w') as f:
            json.dump(feature_collection, f)

        log_output(
            f"Contours created successfully for {contourFileName}", output_queue)

    except Exception as e:
        log_output(f"An error occurred: {e}", output_queue)


def create4326geosonContours(inThisFolder, config, contourFileName, output_queue=None):
    """
    Convert contours from custom CRS to GeoJSON in EPSG:4326 without GeoPandas.
    """
    try:
        # Input GeoJSON path (from your custom CRS GeoJSON)
        input_geojson_path = normJoin(inThisFolder, f'{contourFileName}_customCRS.geojson')
        output_geojson_path = normJoin(inThisFolder, f'{contourFileName}_noAirfields.geojson')

        # Read the input GeoJSON
        with open(input_geojson_path, 'r') as f:
            data = json.load(f)

        # Define coordinate transformations
        # Assuming config.CRS is the source CRS string
        source_crs = pyproj.CRS(config.CRS)
        target_crs = pyproj.CRS("EPSG:4326")
        transformer = pyproj.Transformer.from_crs(
            source_crs, target_crs, always_xy=True)

        # Transform each feature's geometry to EPSG:4326
        features = []
        for feature in data['features']:
            geom = shape(feature['geometry'])
            if isinstance(geom, LineString):
                coords = geom.coords
                transformed_coords = [
                    transformer.transform(x, y) for x, y in coords]
                transformed_geom = GeoJSONLineString(transformed_coords)
            else:
                raise ValueError(f"Unexpected geometry type: {type(geom)}")

            # Create new feature with transformed geometry but keep original properties
            transformed_feature = Feature(
                geometry=transformed_geom, properties=feature['properties'])
            features.append(transformed_feature)

        # Create FeatureCollection
        fc = FeatureCollection(features)

        # Write transformed GeoJSON
        with open(output_geojson_path, 'w') as f:
            json.dump(fc, f)

        log_output(
            f"{contourFileName} : Contours converted to GeoJSON in EPSG:4326", output_queue)

    except Exception as e:
        log_output(f"An unexpected error occurred: {e}", output_queue)


def merge_geojson_files(inThisFolder, toThatFolder, config, contourFileName, output_queue=None):
    """
    Merge the GeoJSON files for contours and airfields using JSON parsing.

    This function assumes that you want to merge all features from both GeoJSON files.
    """
    try:
        geojson_airfields_path = normJoin(config.result_folder_path, "airfields", f"{config.name}.geojson")
        geojson_contour_path = normJoin(inThisFolder, f'{contourFileName}_noAirfields.geojson')
        merged_geojson_path = normJoin(toThatFolder, f'{contourFileName}.geojson')

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
        
        # Add 'filepath' property to each point feature based on its "name" property
        for feature in merged_features:
            if feature.get("geometry", {}).get("type") == "Point":
                name = feature.get("properties", {}).get("name", "unknown")
                feature["properties"]["filepath"] = normJoin(config.calculation_folder_path,f"{name}.geojson")

        # Create the merged GeoJSON
        merged_geojson = {
            "type": "FeatureCollection",
            "name": "OGRGeoJSON",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": merged_features
        }

        with open(merged_geojson_path, 'w') as f:
            json.dump(merged_geojson, f, separators=(',', ':'))

        log_output(
            f"{contourFileName} : Airfields added to contours.", output_queue)

    except FileNotFoundError as e:
        log_output(f"File not found: {e}", output_queue)
    except json.JSONDecodeError as e:
        log_output(f"JSON decoding error: {e}", output_queue)
    except Exception as e:
        log_output(f"An unexpected error occurred: {e}", output_queue)


def copyMapCss(toThatFolder, config, contourFileName, extension, output_queue=None):
    try:
        # copy mapcss for gurumaps export
        mapcss_file = normJoin(toThatFolder, f'{contourFileName}{extension}.mapcss')
        shutil.copy2(config.mapcssTemplate, mapcss_file)
        log_output(
            f"{contourFileName}: Guru Map style copied successfully", output_queue)

    except Exception as e:
        log_output(f"Failed to copy mapcss file: {e}", output_queue)


def postProcess(inThisFolder, toThatFolder, config, ASCfilePath, contourFileName, output_queue=None):
    generate_contours_from_asc(
        inThisFolder, config, ASCfilePath, contourFileName, output_queue)
    if (config.gurumaps):
        create4326geosonContours(inThisFolder, config, contourFileName, output_queue)
        merge_geojson_files(inThisFolder, toThatFolder, config, contourFileName, output_queue)
        copyMapCss(toThatFolder, config, contourFileName, "", output_queue)
