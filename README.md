# MountainCircles
Requirements to make this work so far:

Compile compute.cpp and put it in the main folder besides launch.py

install conda
make an environnement where you install GDAL
make and environnement with the latest python (3.12.7 here) from which to launch the code

install the dependencies (conda install pyyaml numpy pyproj ...)

add https://drive.google.com/file/d/1-VK5xH8YsDiYMH_TTw0kfHIHoiT12Jh2/view?usp=sharing in the topography folder

check the file pathes in the yaml configuration files (start with albertville.yaml, gurumaps set to false)


--> python launch.py albertville.yaml
