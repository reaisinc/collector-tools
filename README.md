# collector-tools
An Arcpy python tool for creating database files for use with https://github.com/traderboy/collector-server.

## Getting Started
Instead of loading a .mxd project to ArcGIS Online, this script extracts all the data and settings to a folder to be used with collector-server to mimic some of the functions of AGOL.  Create a normal project containing vector-only data layers.  Rasters won't work.  Add any relationships and enable attachments, if needed.

### Prerequisites
* Windows (not tested in Linux)
* ArcMap 10.3+
* Spatialite executable
* GDAL with Filegeodatabase compiled in
* (Optional) cert and pem files for use with collector-server https

### Installing
Clone to folder that can be accessed in ArcMap.

Create a .mxd project with all your data layers stored in a single file geodatabase or shapefiles (not tested much).
Use simple

Can be run from command line or as ArcMap Toolbox.
Type the following to see the command line parameters:
````
python "Create arcgis project tool" -h 
````

Example:
````
python "Create arcgis project tool.pyt" -user myusername -host myhostname -mxd <fullpath_to_my_project.mxd> -output <full_path_to_output_directory> -spatialite_path <full_path_to_spatialite_executable> -gdal_path <full_path_to_gdal_directory> -pem <full_path_to_pem> -cert <full_path_to_cert>
````

## Built With

* [Python](http://python.org) - Python
* [ESRI ArcMap](http://esri.com/) - ESRI
* [Microsoft Visual Studio Code](http://microsoft.com/) - IDE

## Authors
* **traderboy**

## License

This project is licensed under the MIT License - see the [LICENSE] file for details
