#!/usr/bin/env python
"""
Simple Web Mercator utilities using standard formulas.

This module provides simple, correct implementations of web mercator
coordinate conversions using the standard formulas used by Google Maps,
OpenStreetMap, and other web mapping services.
"""

import math


def lat_lon_to_tile(lat, lon, zoom):
    """
    Convert latitude/longitude to tile coordinates using standard web mercator formula.
    
    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees  
        zoom: Zoom level
        
    Returns:
        Tuple of (tile_x, tile_y)
    """
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lat_lon(x, y, zoom):
    """
    Convert tile coordinates to latitude/longitude using standard web mercator formula.
    
    Args:
        x: Tile X coordinate
        y: Tile Y coordinate
        zoom: Zoom level
        
    Returns:
        Tuple of (lat, lon) in degrees
    """
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


def tile_bounds(x, y, zoom):
    """
    Get the geographic bounds of a tile.
    
    Args:
        x: Tile X coordinate
        y: Tile Y coordinate
        zoom: Zoom level
        
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon)
    """
    # Get bounds from tile corners
    min_lat, min_lon = tile_to_lat_lon(x, y + 1, zoom)  # Bottom-left
    max_lat, max_lon = tile_to_lat_lon(x + 1, y, zoom)  # Top-right
    
    return min_lat, min_lon, max_lat, max_lon


def get_hgt_tiles_for_web_mercator_tile(tx, ty, zoom=7):
    """
    Get list of HGT coordinate strings needed to cover a web mercator tile.
    
    Args:
        tx, ty: Web mercator tile coordinates
        zoom: Zoom level (default 7)
        
    Returns:
        List of HGT coordinate strings needed to cover the tile
    """
    # Get geographic bounds of the tile
    min_lat, min_lon, max_lat, max_lon = tile_bounds(tx, ty, zoom)
    
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
    # Get geographic bounds of the tile
    min_lat, min_lon, max_lat, max_lon = tile_bounds(tx, ty, zoom)
    
    # For HGT area generation, we need min_lat, min_lon, lat_size, lon_size
    lat_size = max_lat - min_lat
    lon_size = max_lon - min_lon
    
    return min_lat, min_lon, lat_size, lon_size 