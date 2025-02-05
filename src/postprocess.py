import os
import shutil
import json
from osgeo import gdal, ogr, osr


def generate_contours(inThisFolder, config, ASCfilePath, contourFileName):
    """Generate contour lines from the input raster file using GDAL Python bindings."""
    try:
        # Paths for input ASC file and output GPKG
        gpkg_path = os.path.join(inThisFolder, f'{contourFileName}.gpkg')
        
        # Open the raster dataset
        ds = gdal.Open(ASCfilePath)
        if ds is None:
            raise Exception("Could not open raster dataset")
            
        # Get the first band
        band = ds.GetRasterBand(1)
        
        # Get nodata value from the band
        nodata = band.GetNoDataValue()
        if nodata is None:
            nodata = -9999  # Default nodata value if none is set
        
        # Create the output vector dataset
        driver = ogr.GetDriverByName('GPKG')
        if os.path.exists(gpkg_path):
            driver.DeleteDataSource(gpkg_path)
        
        # Create new GeoPackage
        contour_ds = driver.CreateDataSource(gpkg_path)
        
        # Create spatial reference from input
        srs = osr.SpatialReference()
        srs.ImportFromWkt(ds.GetProjection())
        
        # Create the layer
        contour_layer = contour_ds.CreateLayer('contour', srs=srs, geom_type=ogr.wkbLineString)
        
        # Add elevation field
        field_defn = ogr.FieldDefn('ELEV', ogr.OFTReal)
        contour_layer.CreateField(field_defn)
        
        # Generate the contours
        gdal.ContourGenerate(band, 
                           config.contour_height,  # Contour interval
                           0,                      # Base contour
                           [],                     # Fixed levels
                           1,                      # Use nodata flag
                           nodata,                 # No data value
                           contour_layer,          # Output layer
                           0,                      # ID field
                           0)                      # Elevation field
        
        # Clean up
        contour_ds = None
        ds = None
        
        print(f"Contours created in {inThisFolder}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def create4326geosonContours(inThisFolder, config, contourFileName):
    """Generate contour lines in GeoJSON format using GDAL/OGR Python bindings."""
    try:
        gpkg_path = os.path.join(inThisFolder, f'{contourFileName}.gpkg')
        geojson_path = os.path.join(inThisFolder, f'{contourFileName}_{config.glide_ratio}-{config.ground_clearance}-{config.circuit_height}_noAirfields.geojson')

        # Open input GPKG
        in_driver = ogr.GetDriverByName('GPKG')
        in_ds = in_driver.Open(gpkg_path, 0)  # 0 means read-only
        if in_ds is None:
            raise Exception("Could not open input GPKG")

        # Get input layer
        in_layer = in_ds.GetLayer('contour')
        if in_layer is None:
            raise Exception("Could not get contour layer from GPKG")

        # Create output GeoJSON
        out_driver = ogr.GetDriverByName('GeoJSON')
        if os.path.exists(geojson_path):
            out_driver.DeleteDataSource(geojson_path)
        out_ds = out_driver.CreateDataSource(geojson_path)

        # Create spatial reference objects
        source_srs = osr.SpatialReference()
        source_srs.ImportFromProj4(config.CRS)
        source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        target_srs = osr.SpatialReference()
        target_srs.ImportFromEPSG(4326)
        target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        
        # Create coordinate transformation
        transform = osr.CoordinateTransformation(source_srs, target_srs)

        # Create output layer
        out_layer = out_ds.CreateLayer('OGRGeoJSON', target_srs, in_layer.GetGeomType())

        # Add fields to output layer - make ELEV a String field
        in_layer_defn = in_layer.GetLayerDefn()
        for i in range(in_layer_defn.GetFieldCount()):
            field_defn = in_layer_defn.GetFieldDefn(i)
            if field_defn.GetName() == 'ELEV':
                new_field_defn = ogr.FieldDefn('ELEV', ogr.OFTString)
                out_layer.CreateField(new_field_defn)
            else:
                out_layer.CreateField(field_defn)

        # Get output layer definition
        out_layer_defn = out_layer.GetLayerDefn()

        # Process each feature
        in_feature = in_layer.GetNextFeature()
        while in_feature:
            # Get geometry and transform it
            geom = in_feature.GetGeometryRef().Clone()  # Clone to avoid modifying original
            geom.Transform(transform)

            # Create output feature
            out_feature = ogr.Feature(out_layer_defn)
            out_feature.SetGeometry(geom)

            # Copy attributes
            for i in range(in_layer_defn.GetFieldCount()):
                field_name = in_layer_defn.GetFieldDefn(i).GetName()
                if field_name == 'ELEV':
                    # Convert ELEV to string of integer (no decimals)
                    elev_value = str(int(float(in_feature.GetField(i))))
                    out_feature.SetField(i, elev_value)
                else:
                    out_feature.SetField(i, in_feature.GetField(i))

            # Add feature to output layer
            out_layer.CreateFeature(out_feature)

            # Clean up
            out_feature = None
            geom = None
            in_feature = in_layer.GetNextFeature()

        # Clean up
        in_ds = None
        out_ds = None

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
    generate_contours(inThisFolder, config, ASCfilePath, contourFileName)
    if (config.gurumaps):
        create4326geosonContours(inThisFolder, config, contourFileName)
        # copyMapCss(inThisFolder, config, contourFileName,"_noAirfields")
        merge_geojson_files(inThisFolder, toThatFolder, config, contourFileName)
        copyMapCss(toThatFolder, config, contourFileName,"")