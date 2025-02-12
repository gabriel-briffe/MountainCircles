import folium
import numpy as np
import webview
import json
from shapely.geometry import shape, Point, MultiPoint, LineString
from math import radians, cos, sin, asin, sqrt
import branca.element as be

# Load your GeoJSON file
with open('albertville.geojson') as f:
    data = json.load(f)

# Define the base map tile server (Google Maps)
tiles_url = "http://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}"
tile_options = {'attribution': 'Map data © Google Maps'}

# Calculate the center of the GeoJSON data
def get_center(geojson):
    points = []
    for feature in geojson['features']:
        geom = shape(feature['geometry'])
        if geom.geom_type == 'Point':
            points.append(geom)
        elif geom.geom_type in ['LineString', 'MultiLineString']:
            if geom.geom_type == 'LineString':
                points.extend([Point(xy) for xy in geom.coords])
            else:
                for line in geom:
                    points.extend([Point(xy) for xy in line.coords])

    if not points:
        return None

    multi_point = MultiPoint(points)
    bbox = multi_point.bounds  # Returns (minx, miny, maxx, maxy)
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2
    return (center_y, center_x)  # Shapely uses (y, x) for coords

center = get_center(data)

# Create a map centered on the GeoJSON data
m = folium.Map(
    location=center if center else [48.8566, 2.3522],  # Fallback to Paris
    zoom_start=13,
    tiles=tiles_url,
    attr=tile_options['attribution'],
)

# Haversine formula for more accurate distance in meters
def haversine(lon1, lat1, lon2, lat2):
    R = 6371000  # Earth radius in meters
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# Function to determine if a line is long enough for labeling (in meters, then to pixels)
def line_length_in_pixels(coords, zoom):
    """Calculates line length in pixels using a more accurate conversion."""
    total_length_meters = 0
    for i in range(len(coords) - 1):
        total_length_meters += haversine(*coords[i], *coords[i + 1])

    # Get the latitude in radians
    lat_rad = radians(np.mean([coord[1] for coord in coords]))  # Average latitude

    # Calculate pixels per meter
    resolution = cos(lat_rad) * 2 * np.pi * 6378137 / (256 * 2**zoom)
    pixels_per_meter = 1 / resolution

    # Convert total length to pixels
    total_length_pixels = total_length_meters * pixels_per_meter

    return total_length_pixels


def angle_between(p1, p2):
    """Calculates the angle between two points in degrees using Haversine."""
    lon1, lat1 = p1
    lon2, lat2 = p2

    # Calculate distances in meters
    y = haversine(lon1, lat2, lon1, lat1)  # North-south distance
    x = haversine(lon2, lat1, lon1, lat1)  # East-west distance

    angle = np.arctan2(y, x)
    if (lon1>lon2 and lat1>lat2) or (lon1<lon2 and lat1<lat2): angle=-angle
    return np.degrees(angle)

# Function to add labels with dynamic placement
def add_labels(m, feature, zoom=13, min_length_px=50, label_width_px=50):
    """
    Adds labels to a LineString feature on a Folium map, with improved HTML styling.

    Args:
        m (folium.Map): The Folium map object.
        feature (dict): A GeoJSON feature representing a LineString with an 'ELEV' property.
        zoom (int): The current zoom level of the map.
        min_length_px (int): Minimum line length in pixels for labeling.
        label_width_px (int): The width of the label in pixels.
    """
    if feature['geometry']['type'] == 'LineString' and 'ELEV' in feature['properties']:
        coords = feature['geometry']['coordinates']
        elev = str(feature['properties']['ELEV'])

        # Calculate line length in pixels
        line_length_px = line_length_in_pixels(coords, zoom)


        if line_length_px > min_length_px:
            # Calculate midpoint
            line = LineString(coords)
            midpoint = line.interpolate(0.5, normalized=True)
            midpoint_coords = list(midpoint.coords)[0]

            # Find the segment containing the midpoint
            for i in range(len(coords) - 1):
                segment = LineString([coords[i], coords[i+1]])
                if segment.distance(midpoint) < 1e-6:  # Tolerance for floating-point comparisons
                    break  # Found the segment
            else:
                i = -1  # Midpoint is outside the line (shouldn't happen)

            # Calculate angle using the points before and after the midpoint
            if i > 0 and i < len(coords) - 2:
                angle = angle_between(coords[i], coords[i+1])
            elif i == 0 and len(coords) > 2:
                angle = angle_between(coords[0], coords[1])
            elif i == len(coords) - 2 and len(coords) > 2:
                angle = angle_between(coords[-2], coords[-1])
            else:
                angle = 0  # Default angle if not enough points


            # Create the label as a DivIcon with improved HTML
            label_html = f"""
                <div style="
                    font-size: 11pt;
                    color: black;
                    text-align: center;
                    white-space: nowrap;
                    transform: translate(0, 0) rotate({angle}deg);
                    transform-origin: center;
                    text-shadow:
                        -1px -1px 0 white,
                        1px -1px 0 white,
                        -1px 1px 0 white,
                        1px 1px 0 white;
                ">
                    {elev}
                </div>
            """

            icon = folium.DivIcon(
                icon_size=(label_width_px, 20),
                icon_anchor=(label_width_px / 2, 10),
                html=label_html,
            )

            folium.Marker(location=midpoint_coords[::-1], icon=icon).add_to(m)

# Global variable to store the zoom level
current_zoom = 13  # Initialize with a default zoom level

# Python function to receive the zoom level from JavaScript
def set_zoom(zoom):
    global current_zoom
    current_zoom = zoom
    print(f"Zoom level updated to: {current_zoom}")

# JavaScript code to get the zoom level and send it to Python
js_code = """
var map = map_7829279890a702fca7495cbbf86a571b; // Access the map instance
map.on('zoomend', function() {
    var zoom = map.getZoom();
    console.log("Current zoom level: " + zoom);
    // Create a custom event to send the zoom level to Python
    var event = new CustomEvent('zoom_level', {detail: zoom});
    document.dispatchEvent(event);
});

document.addEventListener('zoom_level', function (e) {
    var zoom = e.detail;
    // Send the zoom level to Python (replace with your actual communication method)
    console.log("Zoom level received in JavaScript: " + zoom);
    // You'll need a way to send this zoom level back to Python
    // For example, you could use a hidden input field and update its value
    // Or use a library like pywebview to communicate between Python and JavaScript
});
"""

# Add the JavaScript code to the map using folium.Element
m.add_child(folium.Element("<script>{}</script>".format(js_code)))

# --- DEBUGGING SECTION ---
print("--- HTML AFTER JAVASCRIPT INJECTION ---")
print(m.get_root().render())
print("--- END HTML AFTER JAVASCRIPT INJECTION ---")
# --- END DEBUGGING SECTION ---



# Iterate through GeoJSON data to add lines and labels
for feature in data['features']:
    if feature['geometry']['type'] == 'LineString':
        folium.PolyLine(
            locations=[coord[::-1] for coord in feature['geometry']['coordinates']],
            color='black',
            weight=3,
            popup=f"Elevation: {feature['properties'].get('ELEV', 'N/A')}"
            if 'ELEV' in feature['properties']
            else None,
        ).add_to(m)
        add_labels(m, feature)  # Call the add_labels function

    elif feature['geometry']['type'] == 'Point':
        folium.CircleMarker(
            location=feature['geometry']['coordinates'][::-1],  # Reverse coords
            radius=5,
            color='black',
            fill=True,
            fill_color='blue',
            fill_opacity=0.8,
            popup=f"Name: {feature['properties'].get('name', 'N/A')}",
        ).add_to(m)

# Add a layer control to toggle layers on/off
folium.LayerControl().add_to(m)

# Convert the Folium map to HTML string
html_content = m.get_root().render()

# Directly open the map in fullscreen mode
webview.create_window("Map Viewer", html=html_content, fullscreen=True)
webview.start()