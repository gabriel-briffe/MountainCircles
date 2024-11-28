# MountainCircles

This project is the continuation of a project that ended up in early 2024 with this interactive map covering the full Alps (different information at different zoom levels):
https://live.glidernet.org/#c=45.26242,7.67261&z=7&m=4&s=1

![mountain circles map](images/ogn.jpg)

you can still download the "alpes 600dpi 2.mbtiles" at https://drive.google.com/drive/folders/1fr68iDfBMsFurlEx9bBe8ZorvOEG9Lc7?usp=sharing and share this file on your phone with Guru Maps, a free android and iphone app that allows custom map import in MBTiles format. 
That map has the following parameters:
- glide ratio : 20
- ground clearance: 200m
- circuit height: 250m

The objective has now shifted to providing a way to quickly compute a file to display, with everyone its own glide parameters, and eveyone its own list of airfields.






# Requirements to make this work so far:

- Compile compute.cpp (it works on mac with clang++, need feedback on other systems)  
- put it in the main folder besides launch.py

- install conda
- make an environnement where you install GDAL
- make and environnement with the latest python (3.12.7 here) from which to launch the code

- install the dependencies (conda install pyyaml numpy pyproj ...) 

- add https://drive.google.com/file/d/1-VK5xH8YsDiYMH_TTw0kfHIHoiT12Jh2/view?usp=sharing in the topography folder

- check the file pathes in the yaml configuration files (start with albertville.yaml, gurumaps set to false)


``` 
python launch.py albertville.yaml
 ```

# Usage

### A run with several airfields will provide:
- a "local" calculation for each individual airfield as "local.asc" (topology of the local) and "airfieldName.gpkg" (the contour lines).
- a recombined topology for all the airfields, and its contour lines, as .asc and .gpkg in the root folder of the calculation results.
- all in the Coordinate Reference System specified in the yaml config file

### With ```gurumaps: true``` in the yaml config file, it will provide as well:
- a geojson conversion of the contour lines for all output, in the right CRS for Guru Maps
- a .mapcss style file of the same name
- copy the two files (with the same names beyond the extension) on your smartphone, and share them with Guru Maps
- i also suggest adding "google maps terrain HD" background. --> https://ms.gurumaps.app/ -->share the downloaded file with guru maps

### .mapcss styles
- found in /templates
- modify it and it will be dispatched to all the calculation results


# to do next

- add airfields, peaks, and passes, to the geojson
- add mapcss styles for that
- see if polygon export is viable in the geojson to color the map for each airfield
- add the ability to choose different glide/ground clearance/circuit height for each airfield
- use this calcultation to extract all the passes that are key points to glide back to an airfield
- long term: make a self contained executable


# Disclaimer:

this is unchecked amateur work, altitudes could be wrong, find a way to check that you are happy with the results if you fly with it.
