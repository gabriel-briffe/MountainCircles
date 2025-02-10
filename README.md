# MountainCircles
MountainCircles is an algorithm that generates contour lines of the glide cones around landable places in the mountains.
Inputs are:
- a list of landable places
- glide ratio
- circuit height
- ground clearance (over the passes)

### Origin
This project is the continuation of a project that ended up in early 2024 with this interactive map covering the full Alps (different information at different zoom levels):
https://live.glidernet.org/#c=45.26242,7.67261&z=7&m=4&s=1

you can still download the "alpes 600dpi 2.mbtiles" at https://drive.google.com/drive/folders/1fr68iDfBMsFurlEx9bBe8ZorvOEG9Lc7?usp=sharing and share this file on your phone with Guru Maps, a free android and iphone app that allows custom map import in MBTiles format. 
That map has the following parameters:
- glide ratio : 20
- ground clearance: 200m
- circuit height: 250m

The objective has now shifted to providing a way to quickly compute a file to display, with everyone its own glide parameters, and eveyone its own list of airfields.

# Today
for quicker export, we just have vector layers that we can switch on and off in Guru Maps:

![guru map](images/overview.png)
![guru map](images/zoomed.png)

# How to download already made files
## from your phone:
- [Video tutorial](https://youtu.be/Bm3o6srzsl8), files [here](https://drive.google.com/drive/folders/1nf3-rh1FVG5X43KMUsyvlxcQL0Tnapjj?usp=drive_link)
- install Guru Maps
- install a nice free map background :
- Option 1 (online only): adding "google maps terrain HD" background. --> https://ms.gurumaps.app/ -->share the downloaded file with guru maps
- Option 2 (offline): as in the video tutorial, [file here](https://drive.google.com/drive/folders/1ApDTSuf8jsdpCH97JeU6T_NIGHr8ZFPG?usp=sharing), download, share with guru maps

- find the [folder](https://drive.google.com/drive/folders/1nf3-rh1FVG5X43KMUsyvlxcQL0Tnapjj?usp=drive_link) corresponding to the parameters you want ("L/D 20-ground 100m-circuit 250m" for example)
- download everything either the zip file or the individual files in that folder.
- share the files with Guru Maps
- in Guru Maps, the files are transparent overlays, which means you can choose the background layer that you want.
- to unselect many layers, or reorganise them, access the layers **via the settings button**, otherwise you can only unselect one at a time.
- the layers startng by "aa_" are the recombined file of all the individual airfields.


## from your mac
- in the app store, on apple silicon, the app is available
- get the files the same way as from a phone
- copy/paste the pairs of geojson+mapcss files in /Users/yourname/Library/Containers/com.bodunov.galileo/Data/Documents
- to make the font size bigger, open a mapcss file with textEdit and adjust the size
- could be available on windows too, to be checked


## How to use
The following pictures are with glide parameters L/D 25, ground clearance 100m (100m margin over the passes), circuit height 250m
- the calculated path back to the landing is always going towards the center of the arcs of circles
- here at 2600m the way back to Albertville is not the same depending on which side of the valley we are
- the way north goes through a pass, we have 100m ground clearance.
![albertville.png](images/albertville.png)
- we might be interested in finding the point at which we switch from one airfield to the next one, and know the minimum altitude at that point
- here, **with 100m ground clearance over a flat pass to the south** it would be at Saint-laurent du pont at 1700m
![chartreuse.png](images/chartreuse.png)
- or we might want to know which are the escapes from the rhone valley to the rhine valley
- here we see that the jump from rhone to rhine necessitates at least 2700m, and the high rhine valley necessitates at least 3000m to be on reach of bad ragaz
![furka.png](images/furka.png)


# If you want to contribute, or run the code yourself to choose you own airfields and glide parameters:

### Requirements to make this work so far:
- python 3.12.7 or higher
- copy the repository (green button on the top right of this page -> download zip)
- unzip, open terminal or command prompt, navigate to the mountaincircles folder that you downloaded and extracted.
- Create python virtual environnement : ```python -m venv myenv```
- Activate myenv : mac : ```source myenv/bin/activate```  
- windows from command prompt : ```myenv\Script\activate.bat```
- install dependencies : ``` pip install -r requirements.txt```
- run : ``` python gui.py```

If the calculation script doesn't work, try to recompile the C++ code as is described below.


### Compiling C++ on mac with VSCode
- check or install xcode
- open vscode -> open folder ->C++ to build
- open compute.cpp, agree to install C++ extension..
- from the main folder in the integrated terminal, run ```g++ -std=c++11 -o compute_mac cpp/*.cpp cpp/data/*.cpp cpp/io/*.cpp```

### Compiling C++ on windows
- install the MinGW toolchain. follow this tutorial, skip the vscode installation, no need: https://code.visualstudio.com/docs/cpp/config-mingw
- When ```g++ --version``` is responding with a version number, navigate to the main folder of the mountaincircles folder that you downloaded and extracted.
- Run ```g++ -std=c++11 -o compute.exe cpp\main.cpp cpp\data\Cell.cpp cpp\data\Matrix.cpp cpp\io\Params.cpp```
- Open a new command prompt, check gcc version again
- Run the gui.py ```python gui.py```

### making it into an app
- from both mac and windows, if you could run a calculation, you might be able to build it into a standalone app:
- from the main folder, run ```pyinstaller gui.spec```
- you app should be in the dist folder

# Usage

### A run with several airfields will provide:
- individual and recombined glide cones (.asc files) in a well choosen metric Coordinate Reference System (CRS) to be as accurate as possible for 2D distance calculations
- CRS definition should be in a text file along the topology files
- a xxx_sectors.asc, ready to be transformed in QGIS for vectorisation, topological coloring, and projection from the custom CRS of the calculation into the right CRS for Guru Maps (EPSG:4326)

### With ```generate Guru Maps data files``` it will provide as well:
- .geojson vector files of the contour lines of the glide cones in the right CRS for Guru Maps (EPSG:4326)
- a .mapcss style file of the same name, ready for simultaneous export to Guru Maps

### .mapcss styles
- found in /templates, can be edited with any text editor according to you preferences
- they are copied alongside each geojson, named identically, after calculations, for quicker export
- Guru Maps docs: https://gurumaps.app/docs/mapcss

### Notes on the peaks and passes layers
- the peaks are a decluttered version of the OSM database, designed to keep only the highest one 5km around
- the passes were computed to be "all the key points to glide back to an airfield, with L/D 20, 25, 30"



# to do next

- get the missing eastern bit of the alp
- add the ability to choose individual glide/ground clearance/circuit height for each airfield
- add airspace. we could start with airspace connected to the ground (P areas, national/regional parks)

# clean zip from mac
```zip -r MountainCirclesData.zip . -x "*.DS_Store" -x "__MACOSX/*" -x ".AppleDouble/*" -x "._*"```

# Disclaimer:

this is unchecked amateur work, altitudes could be wrong, find a way to check that you are happy with the results if you fly with it.

# Credits
@Mullerf for the original idea, https://github.com/planeur-net/outlanding for the west alps cup file
