import requests
import sqlite3
import math
import os
from PIL import Image, ImageEnhance, ImageChops
import io
import numpy as np
# from scipy.ndimage import gaussian_filter
import geojson
from src.shortcuts import normJoin

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def download_tile(z, x, y, tile_server):
    url = tile_server.format(z=z, x=x, y=y)
    response = requests.get(url, headers={'User-Agent': 'MapTileDownloader/1.0'})
    if response.status_code == 200:
        return response.content
    return None

def get_tile(z, x, y, tile_server, tile_type):
    """
    Check if the tile is cached on disk. If it is, load and return it.
    Otherwise, download the tile, cache it, and return it.
    
    The cache folder structure will be: cache/<tile_type>/<zoom>/<x>/<y>.png
    """
    cache_dir = normJoin("cache", tile_type, str(z), str(x))
    cache_path = normJoin(cache_dir, f"{y}.png")
    
    if os.path.exists(cache_path):
        print(f"Loaded cached {tile_type} tile: z{z}/x{x}/y{y}")
        with open(cache_path, "rb") as f:
            return f.read()
    else:
        print(f"Downloading {tile_type} tile: z{z}/x{x}/y{y}")
        tile_data = download_tile(z, x, y, tile_server)
        if tile_data is not None:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(tile_data)
        return tile_data

def decode_terrain_tile(tile_data):
    # Decode Mapzen terrain PNG (RGB encoded elevation)
    img = Image.open(io.BytesIO(tile_data)).convert("RGB")
    img_array = np.array(img).astype(np.int32)  # Convert to int32 to avoid overflow
    # Decode elevation: height = (red * 256 * 256 + green * 256 + blue) - 32768
    elevation = (img_array[:,:,0] * 256 * 256 + 
                 img_array[:,:,1] * 256 + 
                 img_array[:,:,2]) - 32768
    return elevation

def generate_hillshade(elevation, azimuth=315, altitude=45):
    # Calculate hillshade
    dx, dy = np.gradient(elevation)
    slope = np.pi/2. - np.arctan(np.sqrt(dx*dx + dy*dy))
    aspect = np.arctan2(-dx, dy)
    
    azimuth_rad = azimuth * np.pi / 180
    altitude_rad = altitude * np.pi / 180
    
    shaded = np.sin(altitude_rad) * np.sin(slope) + \
             np.cos(altitude_rad) * np.cos(slope) * \
             np.cos((azimuth_rad - np.pi/2.) - aspect)
    
    # Normalize and scale to 0-255
    shaded = (shaded - shaded.min()) / (shaded.max() - shaded.min())
    # shaded = gaussian_filter(shaded, sigma=5)  # Smooth the hillshade
    return (shaded * 255).astype(np.uint8)

def create_mbtiles_file(filename):
    # Remove the existing file to avoid "table metadata already exists" error.
    if os.path.exists(filename):
        os.remove(filename)
        
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE metadata (
            name TEXT,
            value TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB,
            PRIMARY KEY (zoom_level, tile_column, tile_row)
        )
    """)
    
    metadata = [
        ("name", "Hillshaded Map"),
        ("type", "baselayer"),
        ("version", "1"),
        ("description", "OSM with hillshading"),
        ("format", "jpeg")
    ]
    cursor.executemany("INSERT INTO metadata VALUES (?, ?)", metadata)
    
    conn.commit()
    return conn

def calculate_bbox_from_geojson(geojson_path):
    """
    Calculate bounding box from GeoJSON file containing LineString features.
    Returns: [min_lat, min_lon, max_lat, max_lon]
    """
    with open(geojson_path, 'r') as f:
        data = geojson.load(f)
    
    min_lat = float('inf')
    min_lon = float('inf')
    max_lat = float('-inf')
    max_lon = float('-inf')
    
    for feature in data['features']:
        if feature['geometry']['type'] == 'LineString':
            coordinates = feature['geometry']['coordinates']
            for lon, lat in coordinates:
                min_lat = min(min_lat, lat)
                min_lon = min(min_lon, lon)
                max_lat = max(max_lat, lat)
                max_lon = max(max_lon, lon)
    
    return [min_lat, min_lon, max_lat, max_lon]

def download_and_combine_region(bbox, min_zoom, max_zoom, mbtiles_file, hillshade_mbtiles):
    """
    Downloads OSM tiles and overlays them with hillshade tiles sourced from a local MBTiles file.
    Instead of using a remote terrain endpoint, this function reads hillshade tiles from the
    specified local MBTiles (hillshade_mbtiles).
    """
    osm_server = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
    
    # Create output MBTiles file for the combined hillshaded map
    conn = create_mbtiles_file(mbtiles_file)
    cursor = conn.cursor()
    
    # Open connection to local hillshade MBTiles
    hillshade_conn = sqlite3.connect(hillshade_mbtiles)
    hillshade_cursor = hillshade_conn.cursor()
    
    min_lat, min_lon, max_lat, max_lon = bbox
    
    for zoom in range(min_zoom, max_zoom + 1):
        # Compute the tile range:
        min_x, min_y = deg2num(max_lat, min_lon, zoom)   # top-left corner
        max_x, max_y = deg2num(min_lat, max_lon, zoom)     # bottom-right corner
        
        total_tiles = (max_x - min_x + 1) * (max_y - min_y + 1)
        current_tile = 0
        
        print(f"Processing {total_tiles} tiles for zoom level {zoom}")
        
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                current_tile += 1
                # print(f"Processing tile {current_tile}/{total_tiles} (z{zoom}/x{x}/y{y})")
                
                # Using caching for OSM tiles
                osm_data = get_tile(zoom, x, y, osm_server, "osm")
                # Instead of downloading a terrain tile, fetch the hillshade tile from the local MBTiles.
                flipped_y = (2**zoom - 1) - y
                hillshade_cursor.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (zoom, x, flipped_y)
                )
                result = hillshade_cursor.fetchone()
                if result:
                    hillshade_data = result[0]
                else:
                    print(f"Hillshade tile not found for z{zoom}/x{x}/y{y}")
                    hillshade_data = None
                
                if osm_data and hillshade_data:
                    # Instead of working in RGBA, we work in RGB since multiply doesn't use alpha
                    # Load hillshade image as RGB:
                    hillshade_img = Image.open(io.BytesIO(hillshade_data)).convert('RGB')
                    
                    # Load the OSM tile in RGB mode and enhance it:
                    osm_img = Image.open(io.BytesIO(osm_data)).convert('RGB')
                    osm_img = ImageEnhance.Contrast(osm_img).enhance(1)
                    osm_img = ImageEnhance.Color(osm_img).enhance(1)
                    
                    # Multiply blend: each pixel is (osm_pixel * hillshade_pixel) / 255
                    final_img = ImageChops.multiply(osm_img, hillshade_img)
                    
                    # Save to bytes using JPEG compression with specified quality:
                    output = io.BytesIO()
                    final_img.save(output, format='JPEG', quality=85)
                    tile_data = output.getvalue()
                    
                    # MBTiles uses a flipped y coordinate for storage
                    cursor.execute(
                        "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                        (zoom, x, flipped_y, tile_data)
                    )
        
        conn.commit()
    
    conn.close()
    hillshade_conn.close()
    print("Download and processing complete!")

# Example usage
if __name__ == "__main__":
    # Hardcoded GeoJSON file path
    geojson_path = "./tests/aa_alps_25-100-250 copy.geojson"
    
    # Calculate bbox from GeoJSON
    bbox = calculate_bbox_from_geojson(geojson_path)
    
    # Set zoom levels
    min_zoom = 1
    max_zoom = 12
    
    # Output MBTiles file for the hillshaded map
    output_file = "./tests/hillshaded_alps.mbtiles"

    # Local hillshade MBTiles file which contains precomputed hillshade tiles
    hillshade_mbtiles_path = "./tests/hillshade.mbtiles"
    
    download_and_combine_region(bbox, min_zoom, max_zoom, output_file, hillshade_mbtiles_path)