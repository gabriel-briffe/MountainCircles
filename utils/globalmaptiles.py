#!/usr/bin/env python
"""
globalmaptiles.py

Global Map Tiles as defined in Tile Map Service (TMS) Profiles
==============================================================

Functions necessary for generation of global tiles used on the web.
It contains classes implementing coordinate conversions for:

- GlobalMercator (based on EPSG:900913 = EPSG:3785)
  for Google Maps, Yahoo Maps, Microsoft Maps compatible tiles
- GlobalGeodetic (based on EPSG:4326)
  for OpenLayers Base Map and Google Earth compatible tiles

More info at:

http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification
http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation
http://msdn.microsoft.com/en-us/library/bb259689.aspx
http://code.google.com/apis/maps/documentation/overlays.html#Google_Maps_Coordinates

Created by Klokan Petr Pridal on 2008-07-03.
Google Summer of Code 2008, project GDAL2Tiles for OSGEO.

In case you use this class in your product, translate it to another language
or find it useful for your project please let me know.
My email: klokan at klokan dot cz.
I would like to know where it was used.

Class is available under the open-source GDAL license (www.gdal.org).
"""

import math


class GlobalMercator(object):
    r"""
    TMS Global Mercator Profile
    ---------------------------

    Functions necessary for generation of tiles in Spherical Mercator projection,
    EPSG:900913 (EPSG:gOOglE, Google Maps Global Mercator), EPSG:3785, OSGEO:41001.

    Such tiles are compatible with Google Maps, Microsoft Virtual Earth, Yahoo Maps,
    UK Ordnance Survey OpenSpace API, ...
    and you can overlay them on top of base maps of those web mapping applications.

    Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

    What coordinate conversions do we need for TMS Global Mercator tiles::

        LatLon <-> Meters <-> Pixels <-> Tile

        WGS84 coordinates   Spherical Mercator  Pixels in pyramid  Tiles in pyramid
        lat/lon             XY in metres        XY pixels Z zoom    XYZ from TMS
        EPSG:4326           EPSG:900913
        .-----.             ---------           --                  TMS
        /     \     <->     |       |   <->     /----/      <->     Google
        \     /             |       |           /--------/          QuadTree
        -----               ---------           /------------/

        KML, public         WebMapService       Web Clients         TileMapService
    """

    def __init__(self, tileSize=256):
        "Initialize the TMS Global Mercator pyramid"
        self.tileSize = tileSize
        self.initialResolution = 2 * math.pi * 6378137 / self.tileSize
        # 156543.03392804062 for tileSize 256 pixels
        self.originShift = 2 * math.pi * 6378137 / 2.0
        # 20037508.342789244

    def LatLonToMeters(self, lat, lon):
        "Converts given lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"

        mx = lon * self.originShift / 180.0
        my = math.log(math.tan((90 + lat) * math.pi / 360.0)) / (math.pi / 180.0)

        my = my * self.originShift / 180.0
        return mx, my

    def MetersToLatLon(self, mx, my):
        "Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"

        lon = (mx / self.originShift) * 180.0
        lat = (my / self.originShift) * 180.0

        lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
        return lat, lon

    def PixelsToMeters(self, px, py, zoom):
        "Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"

        res = self.Resolution(zoom)
        mx = px * res - self.originShift
        my = py * res - self.originShift
        return mx, my

    def MetersToPixels(self, mx, my, zoom):
        "Converts EPSG:900913 to pyramid pixel coordinates in given zoom level"

        res = self.Resolution(zoom)
        px = (mx + self.originShift) / res
        py = (my + self.originShift) / res
        return px, py

    def PixelsToTile(self, px, py):
        "Returns a tile covering region in given pixel coordinates"

        tx = int(math.ceil(px / float(self.tileSize)) - 1)
        ty = int(math.ceil(py / float(self.tileSize)) - 1)
        return tx, ty

    def PixelsToRaster(self, px, py, zoom):
        "Move the origin of pixel coordinates to top-left corner"

        mapSize = self.tileSize << zoom
        return px, mapSize - py

    def MetersToTile(self, mx, my, zoom):
        "Returns tile for given mercator coordinates"

        px, py = self.MetersToPixels(mx, my, zoom)
        return self.PixelsToTile(px, py)

    def TileBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in EPSG:900913 coordinates"

        minx, miny = self.PixelsToMeters(tx * self.tileSize, ty * self.tileSize, zoom)
        maxx, maxy = self.PixelsToMeters((tx + 1) * self.tileSize, (ty + 1) * self.tileSize, zoom)
        return (minx, miny, maxx, maxy)

    def TileLatLonBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in latitude/longitude using WGS84 datum"

        bounds = self.TileBounds(tx, ty, zoom)
        minLat, minLon = self.MetersToLatLon(bounds[0], bounds[1])
        maxLat, maxLon = self.MetersToLatLon(bounds[2], bounds[3])

        return (minLat, minLon, maxLat, maxLon)

    def Resolution(self, zoom):
        "Resolution (meters/pixel) for given zoom level (measured at Equator)"

        # return (2 * math.pi * 6378137) / (self.tileSize * 2**zoom)
        return self.initialResolution / (2**zoom)

    def ZoomForPixelSize(self, pixelSize):
        "Maximal scaledown zoom of the pyramid closest to the pixelSize."

        for i in range(30):
            if pixelSize > self.Resolution(i):
                return i - 1 if i != 0 else 0  # We don't want to scale up

    def GoogleTile(self, tx, ty, zoom):
        "Converts TMS tile coordinates to Google Tile coordinates"

        # coordinate origin is moved from bottom-left to top-left corner of the extent
        return tx, (2**zoom - 1) - ty

    def QuadTree(self, tx, ty, zoom):
        "Converts TMS tile coordinates to Microsoft QuadTree"

        quadKey = ""
        ty = (2**zoom - 1) - ty
        for i in range(zoom, 0, -1):
            digit = 0
            mask = 1 << (i - 1)
            if (tx & mask) != 0:
                digit += 1
            if (ty & mask) != 0:
                digit += 2
            quadKey += str(digit)

        return quadKey


class GlobalGeodetic(object):
    r"""
    TMS Global Geodetic Profile
    ---------------------------

    Functions necessary for generation of global tiles in Plate Carre projection,
    EPSG:4326, "unprojected profile".

    Such tiles are compatible with Google Earth (as any other EPSG:4326 rasters)
    and you can overlay the tiles on top of OpenLayers base map.

    Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

    What coordinate conversions do we need for TMS Global Geodetic tiles?

    Global Geodetic tiles are using geodetic coordinates (latitude,longitude)
    directly as planar coordinates XY (it is also called Unprojected or Plate
    Carre). We need only scaling to pixel pyramid and cutting to tiles.
    Pyramid has on top level two tiles, so it is not square but rectangle.
    Area [-180,-90,180,90] is scaled to 512x256 pixels.
    TMS has coordinate origin (for pixels and tiles) in bottom-left corner.
    Rasters are in EPSG:4326 and therefore are compatible with Google Earth.

        LatLon <-> Pixels <-> Tiles

        WGS84 coordinates   Pixels in pyramid  Tiles in pyramid
        lat/lon             XY pixels Z zoom   XYZ from TMS
        EPSG:4326
        .-----.             ----
        /     \     <->     /--------/      <->     TMS
        \     /             /--------------/
        -----               /--------------------/
        WMS, KML            Web Clients, Google Earth  TileMapService
    """

    def __init__(self, tileSize=256):
        self.tileSize = tileSize

    def LatLonToPixels(self, lat, lon, zoom):
        "Converts lat/lon to pixel coordinates in given zoom of the EPSG:4326 pyramid"

        res = 180 / 256.0 / 2**zoom
        px = (180 + lat) / res
        py = (90 + lon) / res
        return px, py

    def PixelsToTile(self, px, py):
        "Returns coordinates of the tile covering region in pixel coordinates"

        tx = int(math.ceil(px / float(self.tileSize)) - 1)
        ty = int(math.ceil(py / float(self.tileSize)) - 1)
        return tx, ty

    def Resolution(self, zoom):
        "Resolution (arc/pixel) for given zoom level (measured at Equator)"

        return 180 / 256.0 / 2**zoom
        # return 180 / float( 1 << (8+zoom) )

    def TileBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile"
        res = 180 / 256.0 / 2**zoom
        return (
            tx * 256 * res - 180,
            ty * 256 * res - 90,
            (tx + 1) * 256 * res - 180,
            (ty + 1) * 256 * res - 90
        )


def get_hgt_tiles_for_web_mercator_tile(tx, ty, zoom=7):
    """
    Get list of HGT coordinate strings needed to cover a web mercator tile.
    
    Args:
        tx, ty: Web mercator tile coordinates
        zoom: Zoom level (default 7)
        
    Returns:
        List of HGT coordinate strings needed to cover the tile
    """
    mercator = GlobalMercator()
    
    # Get geographic bounds of the tile
    min_lat, min_lon, max_lat, max_lon = mercator.TileLatLonBounds(tx, ty, zoom)
    
    # Import here to avoid circular imports
    from hgt_reader import get_hgt_tiles_for_area
    
    return get_hgt_tiles_for_area(min_lat, min_lon, max_lat, max_lon)


def web_mercator_tile_to_hgt_area_bounds(tx, ty, zoom=7):
    """
    Convert web mercator tile coordinates to area bounds for HGT map generation.
    
    Args:
        tx, ty: Web mercator tile coordinates  
        zoom: Zoom level (default 7)
        
    Returns:
        Tuple of (min_lat, min_lon, lat_size, lon_size) for run_map_hgt_area.py
    """
    mercator = GlobalMercator()
    
    # Get geographic bounds of the tile
    min_lat, min_lon, max_lat, max_lon = mercator.TileLatLonBounds(tx, ty, zoom)
    
    # For HGT area generation, we need min_lat, min_lon, lat_size, lon_size
    lat_size = max_lat - min_lat
    lon_size = max_lon - min_lon
    
    return min_lat, min_lon, lat_size, lon_size


if __name__ == "__main__":
    import sys
    import os

    def Usage(s=""):
        print("Usage: globalmaptiles.py [-profile 'mercator'|'geodetic'] zoomlevel lat lon [latmax lonmax]")
        print()
        if s:
            print(s)
            print()
        print("This utility prints for given WGS84 lat/lon coordinates (or bounding box) the list of tiles")
        print("covering specified area. Tiles are in the given 'profile' (default is Google Maps 'mercator')")
        print("and in the given pyramid 'zoomlevel'.")
        print("For each tile several information is printed including bounding box in EPSG:900913 and WGS84.")
        sys.exit(1)

    profile = 'mercator'
    zoomlevel = None
    lat, lon, latmax, lonmax = None, None, None, None
    boundingbox = False

    argv = sys.argv
    i = 1
    while i < len(argv):
        arg = argv[i]

        if arg == '-profile':
            i = i + 1
            profile = argv[i]

        if zoomlevel is None:
            zoomlevel = int(argv[i])
        elif lat is None:
            lat = float(argv[i])
        elif lon is None:
            lon = float(argv[i])
        elif latmax is None:
            latmax = float(argv[i])
        elif lonmax is None:
            lonmax = float(argv[i])
        else:
            Usage("ERROR: Too many parameters")

        i = i + 1

    if profile != 'mercator':
        Usage("ERROR: Sorry, given profile is not implemented yet.")

    if zoomlevel == None or lat == None or lon == None:
        Usage("ERROR: Specify at least 'zoomlevel', 'lat' and 'lon'.")
    if latmax is not None and lonmax is None:
        Usage("ERROR: Both 'latmax' and 'lonmax' must be given.")

    if latmax != None and lonmax != None:
        if latmax < lat:
            Usage("ERROR: 'latmax' must be bigger then 'lat'")
        if lonmax < lon:
            Usage("ERROR: 'lonmax' must be bigger then 'lon'")
        boundingbox = (lon, lat, lonmax, latmax)

    tz = zoomlevel
    mercator = GlobalMercator()

    mx, my = mercator.LatLonToMeters(lat, lon)
    print("Spherical Mercator (ESPG:900913) coordinates for lat/lon: ")
    print((mx, my))
    tminx, tminy = mercator.MetersToTile(mx, my, tz)

    if boundingbox:
        mx, my = mercator.LatLonToMeters(latmax, lonmax)
        print("Spherical Mercator (ESPG:900913) coordinate for maxlat/maxlon: ")
        print((mx, my))
        tmaxx, tmaxy = mercator.MetersToTile(mx, my, tz)
    else:
        tmaxx, tmaxy = tminx, tminy

    for ty in range(tminy, tmaxy + 1):
        for tx in range(tminx, tmaxx + 1):
            tilefilename = "%s/%s/%s" % (tz, tx, ty)
            print(tilefilename, "( TileMapService: z / x / y )")

            gx, gy = mercator.GoogleTile(tx, ty, tz)
            print("\tGoogle:", gx, gy)
            quadkey = mercator.QuadTree(tx, ty, tz)
            print("\tQuadkey:", quadkey, '(', int(quadkey, 4), ')')
            bounds = mercator.TileBounds(tx, ty, tz)
            print()
            print("\tEPSG:900913 Extent: ", bounds)
            wgsbounds = mercator.TileLatLonBounds(tx, ty, tz)
            print("\tWGS84 Extent:", wgsbounds)
            print("\tgdalwarp -ts 256 256 -te %s %s %s %s %s %s_%s_%s.tif" % (
                bounds[0], bounds[1], bounds[2], bounds[3], "<your-raster-file-in-epsg900913.ext>", tz, tx, ty))
            print() 