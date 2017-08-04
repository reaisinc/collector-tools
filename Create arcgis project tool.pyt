import subprocess
import arcpy
from arcpy import env
import sqlite3
import xml.etree.ElementTree
import os
import json
import zipfile
from arcpy import mapping
import os
from xml.dom.minidom import parse
from datetime import datetime
import time
import copy
import shutil
import types
import ConfigParser
import copy
import logging
import sys

Config = ConfigParser.ConfigParser()


#logging.basicConfig(filename="logfile.txt")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# create a file handler
handler = logging.FileHandler("logfile.txt")
handler.setLevel(logging.INFO)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)


arcpy.env.overwriteOutput = True
#notes:  urlKey in portals.self.json must be blank or it will try to authenticate at arcgis.com
#other gotchas
#For polygon styles, makes sure to use "style": "esriSFSSolid" and NOT "style": "esriSLSSolid" for the outline style
                   
#OBS! OBJECTID in layers/tables MUST be int32, not integer.  Otherwise lookups will not work, even after creating new records

#import time
#env.workspace = "CURRENT"
#env.addOutputsToMap = False
#env.overwriteOutput = True
arcpy.env.overwriteOutput = True

toolkitPath = os.path.abspath(os.path.dirname(__file__)).replace("\\","/")
gdal_path = ""
ogr2ogr_path = ""
ogrinfo_path = ""
gdal_data_path = ""
spatialite_path = ""

#toolkitPath+"/gdal/ogr2ogr.exe

class Toolbox(object):
    def __init__(self):
        self.label =  "Create ArcServices toolbox"
        self.alias  = "arcservices"
        self.canRunInBackground = False
        # List of tool classes associated with this toolbox
        self.tools = [CreateNewProject]

class CreateNewProject(object):
    def __init__(self):
        self.label       = "Convert map document to JSON"
        self.alias="arcservices"
        self.description = "Creates the JSON files for a standalone ArcGIS Online/Server node application.  Note:  you need to fill out the project information in the File->Map Document Properties before running."
    def getParameterInfo(self):

        Config.read(toolkitPath+"/settings.ini")
        servername = arcpy.Parameter(
            displayName="Enter server FQDN (example: www.esri.com)",
            name="servername",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=False)
        try:
           servername.value = Config.get("settings","server")
        except Exception as e:
           pass
        
        if not servername.value:
            servername.value = "my.host.com"

        username = arcpy.Parameter(
            displayName="Enter your username",
            name="username",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            multiValue=False)
        try:
           username.value= Config.get("settings","username")
        except Exception as e:
           pass

        if not username.value:
            username.value="user"

        #projecttitle = arcpy.Parameter(
        #    displayName="Enter your project title",
        #    name="projectname",
        #    datatype="GPString",
        #    parameterType="Required",
        #    direction="Input",
        #    multiValue=False)

        #projectname = arcpy.Parameter(
        #    displayName="Enter your project name (no spaces)",
        #    name="projectname",
        #    datatype="GPString",
        #    parameterType="Required",
        #    direction="Input",
        #    multiValue=False)

        #tags = arcpy.Parameter(
        #    displayName="Enter tags",
        #    name="tags",
        #    datatype="GPString",
        #    parameterType="Optional",
        #    direction="Input",
        #    multiValue=False)
        #
        #summary = arcpy.Parameter(
        #    displayName="Enter project summary",
        #    name="summary",
        #    datatype="GPString",
        #    parameterType="Optional",
        #    direction="Input",
        #    multiValue=False)
        #
        #description = arcpy.Parameter(
        #    displayName="Enter project description",
        #    name="description",
        #    datatype="GPString",
        #    parameterType="Optional",
        #    direction="Input",
        #    multiValue=False)

        datasrc = arcpy.Parameter(
            displayName="Enter default database",
            name="datasrc",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=False)
        datasrc.filter.type = "ValueList"
        datasrc.filter.list = ["File","Sqlite","Postgresql"]
        datasrc.value = "Sqlite"

        outputfolder = arcpy.Parameter(
            displayName="Enter output folder",
            name="outputfolder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        try:
            outputfolder.value= Config.get("settings","destination")
        except Exception as e:
           pass
        
        if not outputfolder.value:
            outputfolder.value=os.getcwd().replace("\\","/")

        #sqlitedb = arcpy.Parameter()
        #sqlitedb.name = u'Output_Report_File'
        #sqlitedb.displayName = u'Output Sqlite database'
        #sqlitedb.parameterType = 'Optional'
        #sqlitedb.direction = 'Output'
        #sqlitedb.datatype = u'File'
        #try:
        #    sqlitedb.value= Config.get("settings","sqlitedb")
        #except Exception as e:
        #   pass        

        pg = arcpy.Parameter()
        pg.name = u'Output_DB_String'
        pg.displayName = u'Postgresql database connection string  Ex: PG:"host=localhost user=postgres dbname=gis"'
        pg.parameterType = 'Optional'
        pg.direction = 'Output'
        pg.datatype = u'GPString'
        try:
            pg.value= Config.get("settings","pg")
        except Exception as e:
           pass        

        spatialite_path = arcpy.Parameter()
        spatialite_path.name = u'spatialite_executable'
        spatialite_path.displayName = u'Path to spatialite executable'
        spatialite_path.parameterType = 'Required'
        spatialite_path.direction = 'Input'
        #spatialite_path.datatype="DEFolder"
        spatialite_path.datatype = u'File'
        try:
            spatialite_path.value= Config.get("settings","spatialite_path")
        except Exception as e:
           pass        

        gdal_path = arcpy.Parameter()
        gdal_path.name = u'gdal_executable'
        gdal_path.displayName = u'Path to ogr2ogr and ogrinfo executables'
        gdal_path.parameterType = 'Required'
        gdal_path.direction = 'Input'
        gdal_path.datatype = "DEFolder"
        #gdal_path.datatype = u'File'
        try:
            gdal_path.value= Config.get("settings","gdal_path")
        except Exception as e:
           pass        

        cert = arcpy.Parameter()
        cert.name = u'cert_path'
        cert.displayName = u'cert file for Https server'
        cert.parameterType = 'Optional'
        cert.direction = 'Input'
        cert.datatype = u'File'
        try:
            cert.value= Config.get("settings","cert")
        except Exception as e:
           pass        

        pem = arcpy.Parameter()
        pem.name = u'pem_path'
        pem.displayName = u'pem file for Https server'
        pem.parameterType = 'Optional'
        pem.direction = 'Input'
        pem.datatype = u'File'
        try:
            pem.value= Config.get("settings","pem")
        except Exception as e:
           pass        


        #param0.filter.type = "ValueList"
        #param0.filter.list = ["Street","Aerial","Terrain","Topographic"]
        parameters = [servername,username,datasrc,outputfolder,pg,spatialite_path,gdal_path,cert,pem]
        #username,projecttitle,projectname,tags,summary,description,
        return parameters

    def isLicensed(self): #optional
        return True

    def updateParameters(self, parameters): #optional
       #if parameters[2].altered:
       #   try:
       #       os.makedirs(parameters[2].valueAsText)
       #   except Exception as e:
       #       return
       return

    def updateMessages(self, parameters): #optional
        return

    def execute(self, parameters, messages):
        global toolkitPath
        global ogr2ogr_path
        global ogrinfo_path
        global spatialite_path
        global gdal_data_path
        global gdal_path
        
        serverName = parameters[0].valueAsText
        username = parameters[1].valueAsText        
        datasrc = parameters[2].valueAsText
        baseDestinationPath = parameters[3].valueAsText
        #sqliteDb = parameters[3].valueAsText
        
        pg  = parameters[4].valueAsText
        spatialite_path=parameters[5].valueAsText
        gdal_path=parameters[6].valueAsText
        cert = parameters[7].valueAsText
        pem = parameters[8].valueAsText
        
        #toolkitPath+"/spatialite/spatialite.exe
        created_ts=int(time.time()*1000)
        sep = "/"

        printMessage("****************************************************************")
        printMessage("Parameters")

        # suppose you want to add it to the current MXD (open MXD)
        #mxd,host,user,datasrc,output,pg,spatialite_path,gdal_path,cert,pem,
        try:
           if type(messages)==types.ListType:
              vals = messages
              #vals = messages.split("|")
              if len(vals)>1:
                 serverName = vals[1]
              if len(vals)>2:
                 username= vals[2]
              if len(vals)>3:
                 datasrc=vals[3]

              if len(vals)>4:
                 baseDestinationPath=vals[4].replace("\\","/")
              #if len(vals)>4:
              #   sqliteDb=vals[4]
              if len(vals)>5:
                 pg=vals[5]
              if len(vals)>6:
                 spatialite_path=vals[6]
              if len(vals)>7:
                 gdal_path=vals[7]
              if len(vals)>8:
                 cert=vals[8]
              if len(vals)>9:
                 pem=vals[9]

              mxdName=vals[0].replace("\\","/")
              mxd = arcpy.mapping.MapDocument(mxdName)
           else:
              mxd = arcpy.mapping.MapDocument("CURRENT")
        except Exception as e:
           printMessage("Still Unable to open map document.  Make sure background processing is unchecked in the geoprocessing options")
           return

        if datasrc == "File":
            datasrc = "file"
        elif datasrc=="Sqlite":
            datasrc = "sqlite"
        elif datasrc=="Postgresql":
            datasrc = "pgsql"
        else:
            datasrc="sqlite"

        
        #if sqliteDb.find(".sqlite") == -1:
        #    sqliteDb = sqliteDb + ".sqlite"
        #put file in the catalogs folder
        sqliteDb = os.path.join(baseDestinationPath,"catalogs","collectorDb.sqlite") #.replace("\\","/")
        #if os.path.exists(sqliteDb):
        #    try:
        #       os.remove(sqliteDb)
        #    except Exception as e:
        #       printMessage("Unable to delete collectoDb.sqlite file.  Is it currently open in another application or is the collector-server running?")
        #       printMessage(e)
        #       return
        #       #os._exit(1)


        #locate spatialite, ogr2ogr, and ogrinfo executables
        #if sys.platform== 'win32':
        gdal_path=gdal_path.replace("/","\\")
        if not os.path.exists(spatialite_path ):
        #    spatialite_path = os.path.join(spatialite_path , "spatialite.exe") #.replace("/","\\")
        #elif os.path.exists(spatialite_path + os.sep + "spatialite"):
        #    spatialite_path = (spatialite_path + os.sep + "spatialite")
        #else:
           printMessage("Unable to locate spatialite executable")
           return

        if os.path.exists(gdal_path + "/bin/gdal/apps/ogr2ogr.exe"):
            ogr2ogr_path = os.path.join(gdal_path ,"bin","gdal","apps","ogr2ogr.exe") #.replace("/","\\")
        elif os.path.exists(gdal_path + os.sep + "ogr2ogr"):
            ogr2ogr_path = (gdal_path + os.sep + "ogr2ogr")
        else:
           printMessage("Unable to locate ogr2ogr executable")
           return

        if os.path.exists(gdal_path + os.sep + "/bin/gdal/apps/ogrinfo.exe"):
            ogrinfo_path = os.path.join(gdal_path ,"bin","gdal","apps","ogrinfo.exe") #.replace("/","\\")
        elif os.path.exists(gdal_path + os.sep + "ogrinfo"):
            ogrinfo_path = (gdal_path + os.sep + "ogrinfo")
        else:
           printMessage("Unable to locate ogrinfo executable")
           return

        if os.path.exists(gdal_path + os.sep + "/bin/gdal-data"):
            gdal_data_path = os.path.join(gdal_path ,"bin","gdal-data")
            #(gdal_path  + "/bin/gdal-data").replace("/","\\")
        elif os.path.exists(gdal_path + os.sep + "gdal-data"):
            gdal_data_path = (gdal_path + os.sep + "gdal-data")
        else:
           printMessage("Unable to locate gdal-data path")
           return

        if not pem:
            pem=""
        if not cert:
            cert=""

        #try:
        #   arcpy.gp.CreateSQLiteDatabase(sqliteDb, "SPATIALITE")
        #except Exception as e:
        #   arcpy.AddMessage("Database already exists")

        
        serviceName = mxd.activeDataFrame.name.replace(" ","").lower()
        if serviceName=='Layers':
           printMessage("Rename the dataframe from Layers to service name.  Must be valid service name (no spaces)")
           return

        #mxd.makeThumbnail ()
        #toolkitPath = os.path.abspath(os.path.dirname(__file__)).replace("\\","/")
        
        templatePath = toolkitPath + "/templates"
        if not os.path.exists(templatePath):
            printMessage("Template path not found: " + templatePath)
            return

        cfgfile = open(toolkitPath+"/settings.ini",'w')
        try:
            Config.add_section("settings")
        except Exception as e:
            pass

        printMessage("Server name: " +serverName)
        printMessage("User name: " + username)
        printMessage("MXD Path: " + mxd.filePath)
        printMessage("Default data source: " + datasrc)
        printMessage("Destination path: " + baseDestinationPath)
        printMessage("Sqlite path: " + sqliteDb)
        printMessage("Spatialite path: " + spatialite_path)
        printMessage("ogr2ogr path: " + ogr2ogr_path)
        printMessage("ogrinfo path: " + ogrinfo_path)
        printMessage("gdal-data path: " + gdal_data_path)
        printMessage("cert path: " + cert)
        printMessage("pem path: " + pem)
        

        if pg:
            printMessage("Postgresql connection: " + pg)


        Config.set("settings","server",serverName)
        Config.set("settings","username",username)
        Config.set("settings","mxd",mxd.filePath)
        Config.set("settings","destination",baseDestinationPath)
        Config.set("settings","sqlitedb",sqliteDb)
        Config.set("settings","spatialite_path",spatialite_path)
        Config.set("settings","gdal_path",gdal_path)
        Config.set("settings","cert",cert)
        Config.set("settings","pem",pem)
        Config.set("settings","datasrc",datasrc)

        if pg:
            Config.set("settings","pg",pg)
        else:
            Config.set("settings","pg","")

        Config.write(cfgfile)
        cfgfile.close()
        del cfgfile       
        
        printMessage("****************************************************************")
        printMessage("Settings")
        printMessage("Exporting dataframe: " + mxd.activeDataFrame.name)
        if baseDestinationPath:
              baseDestinationPath = unicode(baseDestinationPath).encode('unicode-escape')
              baseDestinationPath=baseDestinationPath.replace("\\","/")+ sep +"catalogs"
        else:
              baseDestinationPath = toolkitPath+ sep +"catalogs"

        #baseDestinationPath = baseDestinationPath + sep + serviceName
        serviceDestinationPath = baseDestinationPath + sep + serviceName

        #if the folder does not exist create it
        if not os.path.exists(baseDestinationPath):
            os.makedirs(serviceDestinationPath)
        else:
            #check to see if service already exists.  If so, remove it so it can be overwritten
            if os.path.exists(serviceDestinationPath):
               try:
                  printMessage("Removing "+serviceDestinationPath+" directory")
                  shutil.rmtree(serviceDestinationPath)
               except Exception as e:
                  printMessage("Unable to remove destination path")
                  return
            try:
               os.makedirs(serviceDestinationPath)
            except Exception as e:
               printMessage("Unable to create destination path")


        servicesDestinationPath = serviceDestinationPath + "/services"
        if not os.path.exists(servicesDestinationPath):
            try:
                os.makedirs(servicesDestinationPath)
            except Exception as e:
                pass
        printMessage("Services path: " +servicesDestinationPath)

        dataDestinationPath = serviceDestinationPath + "/shapefiles"
        if not os.path.exists(dataDestinationPath):
            try:
                os.makedirs(dataDestinationPath)
            except Exception as e:
                pass
        printMessage("Shapefile path: " +dataDestinationPath)

        replicaDestinationPath = serviceDestinationPath + "/replicas"
        if not os.path.exists(replicaDestinationPath):
            try:
                os.makedirs(replicaDestinationPath)
            except Exception as e:
                pass
        printMessage("Replica path: " +replicaDestinationPath)

        mapfileDestinationPath = serviceDestinationPath + "/mapfiles"
        if not os.path.exists(mapfileDestinationPath):
            os.makedirs(mapfileDestinationPath)
        printMessage("Mapfile path: " +mapfileDestinationPath)
        printMessage("****************************************************************")
        printMessage("Log output")

        symbols = getSymbology(mxd)

        dataFrames = arcpy.mapping.ListDataFrames(mxd, "*")
        #service = {}
        project = None
        config = None
        if os.path.exists(baseDestinationPath + "/config.json"):
            config=openJSON(baseDestinationPath + "/config.json")
            try:
                for proj in config["projects"]:
                  if proj == serviceName:
                      printMessage("Found existing project for " + proj["name"] + ":  updating")
                      project = proj
                      break
            except:
                pass

            if not project:
                project = {}
                config["projects"][serviceName]=project
                #project["name"]=serviceName
                #config["projects"].append(project)
                #service = {}
                #project["services"]={}
                #project[serviceName]=service
            else:
                try:
                    project = config["projects"][serviceName]
                except Exception as e:
                    project = {}
                    #project["services"]={}
                    config["projects"][serviceName] =project

            #try:
            #   config["project"]["services"][serviceName]=service
            #except:
            #   printMessage("Service already exists: " + serviceName)
            #config["services"][serviceName]["layers"]={}
            #config["services"][serviceName]["mxd"]=mxd.filePath 
            project["layers"]={}
            project["mxd"]=mxd.filePath
        else:
            config={}
            config["projects"]={}
            project = {}
            #project["services"]={}
            config["projects"][serviceName]=project
            #service["name"]=serviceName
            #config["services"]=[service]
            project["layers"]={}
            project["mxd"]=mxd.filePath

            #config["services"][serviceName]={"layers":{}}
            #config["services"][serviceName]["mxd"]=mxd.filePath

        config["hostname"]=serverName
        config["username"]=username
        config["pemPath"]=pem
        config["certPath"]=cert
        config["httpPort"]="80"
        config["httpsPort"]="443"
        config["arcMapVersion"]=  arcpy.GetInstallInfo()['Version']
        config["defaultDatabase"]=datasrc

        config["dataPath"]=baseDestinationPath
        config["dataSourceTypes"]=["file","sqlite","pgsql"]

        #config["services"][serviceName]["mxd"]=mxd.filePath
        #config["services"][serviceName]["sqliteDb"]=sqliteDb
        #config["services"][serviceName]["pg"]=pg
        #config["services"][serviceName]["dataSource"]="sqlite"
        #config["services"][serviceName]["rootPath"]=baseDestinationPath

        config["sqliteDb"]=sqliteDb
        config["pg"]=pg
        #project["dataSource"]="sqlite"
        
        #config["services"][serviceName]["layers"]={}

        fullname = mxd.author
        if fullname=="":
           printMessage("Author missing in File->Map Document Properties")
           return
        fullname_split = fullname.split(' ')
        first_name = fullname_split[0]
        last_name=""
        if len(fullname_split)>1:
            last_name = fullname_split[1]
        email_address = first_name + '.' + last_name + '@' + serverName
        if not username:
           username=fullname.lower().replace(" ","")

        title  = mxd.title
        if title=="":
           printMessage("Title missing in File->Map Document Properties")
           return

        tags  = mxd.tags
        if not tags:
           tags=""

        summary  = mxd.summary
        if not summary:
           summary=""

        description  = mxd.description
        if not description:
           description=""        

        initializeSqlite(sqliteDb)

        if not os.path.exists(baseDestinationPath + "/portals.self.json"):
           portals_self_json=openJSON(templatePath + "/portals.self.json")
           portals_self_json['portalHostname']=serverName
           portals_self_json['defaultExtent']['xmin']=mxd.activeDataFrame.extent.XMin
           portals_self_json['defaultExtent']['ymin']=mxd.activeDataFrame.extent.YMin
           portals_self_json['defaultExtent']['xmax']=mxd.activeDataFrame.extent.XMax
           portals_self_json['defaultExtent']['ymax']=mxd.activeDataFrame.extent.YMax
           portals_self_json['user']['fullName']=fullname
           portals_self_json['user']['firstName']=first_name
           portals_self_json['user']['lastName']=last_name
           portals_self_json['user']['email']=email_address
           portals_self_json['user']['username']=username
           file = saveJSON(baseDestinationPath + "/portals.self.json",portals_self_json)
           LoadCatalog(sqliteDb,"portals", "self",file)

        if not os.path.exists(baseDestinationPath + "/community.users.json"):
           community_users_json=openJSON(templatePath + "/community.users.json")
           community_users_json['fullName']=fullname
           community_users_json['firstName']=first_name
           community_users_json['lastName']=last_name
           community_users_json['email']=email_address
           community_users_json['username']=username
           community_users_json['created']=created_ts
           community_users_json['modified']=created_ts
           community_users_json['lastLogin']=created_ts
           #community_users_json['groups'][0]['userMembership']['username']=username
           file = saveJSON(baseDestinationPath + "/community.users.json",community_users_json)
           LoadCatalog(sqliteDb,"community", "users",file)

        #User info
        content_users_json=openJSON(templatePath + "/content.users.json")
        content_users_json['username']=username
        #content_users_json['items'][0]['created']=int(time.time()*1000)
        file = saveJSON(baseDestinationPath + "/content.users.json",content_users_json)
        LoadCatalog(sqliteDb,"content", "users",file)

        #Search results
        if not os.path.exists(baseDestinationPath + "/search.json"):
            search_json=openJSON(templatePath + "/search.json")
            #search_json['results'][0]=username
            baseResult = search_json['results'][0]
            search_json['results']=[]
        else:
            search_json=openJSON(baseDestinationPath + "/search.json")
            baseResult = search_json['results'][0]
            #see if result already exists and delete it
            for idx, val in enumerate(search_json['results']):
               if val["id"] == serviceName:
                  del search_json['results'][idx]

            #search_json['results']

        #add stuff for each dataframe below

        #community groups
        #community_groups_json=openJSON(templatePath + "/community.groups.json")
        #saveJSON(destinationPath + "/community.groups.json",community_groups_json)
        shutil.copy2(templatePath + "/community.groups.json", baseDestinationPath + "/community.groups.json")
        #os.system("copy "+ templatePath + "/community.groups.json " + servicesDestinationPath + "/community.groups.json")
        #result = 0

        if not os.path.exists(baseDestinationPath+"/FeatureServer.json"):
            feature_services={"currentVersion":arcpy.GetInstallInfo()['Version'],"folders":[],"services":[]}
        else:
            feature_services=openJSON(baseDestinationPath + "/FeatureServer.json")

        #if not os.path.exists(servicesDestinationPath+"/FeatureServer.json"):
        #     saveJSON(servicesDestinationPath + "/FeatureServer.json",response)
        #else:
        #     featureServer_json=openJSON(servicesDestinationPath + "/FeatureServer.json")
        #     if not serviceName in featureServer_json['folders']:
        #         featureServer_json['folders'].append(serviceName);
        #         saveJSON(servicesDestinationPath + "/FeatureServer.json",featureServer_json)
        #     #create base FeatureServer.json file with folders for each service
        #     #,"folders":["Canvas","Demographics","Elevation","Ocean","Polar","Reference","Specialty","Utilities"]

        #for dataFrame in dataFrames:
        if mxd.activeDataFrame:
           dataFrame = mxd.activeDataFrame
           serviceName = dataFrame.name.replace(" ","").lower()
           #mxd.activeDataFrame.name
           if serviceName=='Layers':
              printMessage("Rename the dataframe from Layers to service name.  Must be valid service name (no spaces)")
              return

           #replace the service name if it exists
           for idx, val in enumerate(feature_services["folders"]):
               if val == serviceName:
                  del feature_services["folders"][idx]
            
           #flush the services table for this service
           ClearService(sqliteDb,serviceName)
           #must set dataframe projection to web mercator
           #outCS = arcpy.SpatialReference(3785) #the code for WGS84 Web Mercator
           outCS = arcpy.SpatialReference(3857) #the code for WGS84 Web Mercator

           #dataFrame.spatialReference = outCS

           #else:
           #   dataFrame = dataFrame #mxd.activeDataFrame
           operationalLayers = []
           operationalTables = []
           operationalTablesObj = []
           allData=[]
           layerIds={}
           id=0

           #for df in arcpy.mapping.ListDataFrames(mxd):
           for lyr in arcpy.mapping.ListLayers(mxd, "", dataFrame):
              # Exit if the current layer is not a service layer.
              if lyr.isServiceLayer or lyr.supports("SERVICEPROPERTIES"):  # or not lyr.visible
                continue
              #make sure layer is web mercator
              cur_projection = arcpy.Describe(lyr).spatialReference
              if cur_projection.name != outCS.name:
                  printMessage(lyr.name + " is NOT in Web Mercator projection.  Skipping...")
                  printMessage(cur_projection.name)
                  printMessage(outCS.name)


                  continue
              #lyr.visible=True
              #opLayer = {
              #    "id": lyr.name,
              #    "title": lyr.name,
              #    "url": lyr.serviceProperties["Resturl"]+ "/" + lyr.longName + "/" + lyr.serviceProperties["ServiceType"],
              #    "opacity": (100 - lyr.transparency) / 100,
              #    "visibility": lyr.visible
              #}
              printMessage("Exporting layer: " + lyr.name)
              
              operationalLayers.append(lyr)
              allData.append(lyr)
              layerIds[lyr.name]=id
              id = id+1
              #arcpy.mapping.RemoveLayer(df, lyr)

           if len(operationalLayers)==0:
              printMessage("No Feature layers found in data frame!")
              return

           id=len(operationalLayers)
           for tbl in arcpy.mapping.ListTableViews(mxd, "", dataFrame):
              operationalTables.append(tbl)
              allData.append(tbl)
              operationalTablesObj.append({"name":tbl.name,"id":id})
              layerIds[tbl.name]=id
              id=id+1


           #now add any attachment tables
           for lyr in allData:
               desc = arcpy.Describe(lyr)
               if hasattr(desc, "layer"):
                   featureName=os.path.basename(desc.layer.catalogPath)
                   rootFGDB=desc.layer.catalogPath.replace("\\","/")
               else:
                   featureName=os.path.basename(desc.catalogPath)
                   rootFGDB=os.path.dirname(desc.catalogPath).replace("\\","/")
               
               #layerIds[tbl.name]=id
               layerIds[featureName]=layerIds[lyr.name]

               if arcpy.Exists(rootFGDB+"/"+featureName+"__ATTACH"):
                   layerIds[featureName+"__ATTACH"]=id
                   id=id+1


           #lyrpath=os.getcwd().replace("\\","/")
           #lyrpath = os.path.abspath(os.path.dirname(__file__)).replace("\\","/")

           ext = operationalLayers[0].getExtent()
           dataFrame.extent = ext

           desc = arcpy.Describe(operationalLayers[0])
           if hasattr(desc, "layer"):
                 ws=desc.layer.catalogPath.replace("\\","/")
           else:
                 ws=os.path.dirname(desc.catalogPath).replace("\\","/")

           #for j,rel in enumerate(allData):
           #   printMessage(str(j) + ": " + rel.name)

           relationships = [c.name for c in arcpy.Describe(ws).children if c.datatype == "RelationshipClass"]

           relArr=[]
           desc = arcpy.Describe(lyr)
           #if not desc.relationshipClassNames:
           #    continue
           #   return rel
           if hasattr(desc, "layer"):
                 featureName=os.path.basename(desc.layer.catalogPath)
                 rootFGDB=desc.layer.catalogPath.replace("\\","/")
           else:
                 featureName=os.path.basename(desc.catalogPath)
                 rootFGDB=os.path.dirname(desc.catalogPath).replace("\\","/")

           project["fgdb"]=rootFGDB
           project["replica"]=replicaDestinationPath+"/"+serviceName+".geodatabase"

           #config["services"][serviceName]["fgdb"]=rootFGDB
           #config["services"][serviceName]["replica"]=replicaDestinationPath+"/"+serviceName+".geodatabase"
           relationshipList = {}
           relationshipObj = {}
           relations={}

           id=0
           destIds={}
           printMessage("Finding relationships")
           for rc in relationships:
             relDesc = arcpy.Describe(rootFGDB+"/"+rc)
             if relDesc.isAttachmentRelationship:
                  continue
             try:
                originId=layerIds[relDesc.originClassNames[0]]
             except:
                printMessage("Skipping unused relationship: " + relDesc.originClassNames[0])
                continue

             try:
                destId=layerIds[relDesc.destinationClassNames[0]]
             except:
                printMessage("Skipping unused relationship: " + relDesc.destinationClassNames[0])
                continue

             #if not layerIds.has_key(originId):
             #    printMessage("Skipping relation: " + relDesc.destinationClassNames[0])
             #    continue

             #printMessage("Relationship Name: " + rc)
             #printMessage("Origin Class Names")
             #printMessage(relDesc.originClassNames)

             #printMessage("Origin Class Keys")
             #printMessage(relDesc.originClassKeys)

             #printMessage("Destination Class Names")
             #printMessage(relDesc.destinationClassNames)

             #printMessage("Destination Class Keys")
             #printMessage(relDesc.destinationClassKeys)

             #printMessage("Key type:  "+relDesc.keyType)
             #printMessage(relDesc.notification)
             #printMessage("backwardPathLabel:  "+relDesc.backwardPathLabel)
             #printMessage("forwardPathLabel:  "+relDesc.forwardPathLabel)

             #originId=getDataIndex(allData,relDesc.originClassNames[0])
             #destId=getDataIndex(allData,relDesc.destinationClassNames[0])

             relatedTableId=0
             role=""
             key=""
             relations[str(id)]={"oTable":relDesc.originClassNames[0],"dTable":relDesc.destinationClassNames[0],"oJoinKey":relDesc.originClassKeys[0][0],"dJoinKey":relDesc.originClassKeys[1][0],"oId":originId,"dId":destId}
             
             relationshipList[originId]={"origin":originId,"dest":destId,"id":id,"name":relDesc.backwardPathLabel,"keyField":relDesc.originClassKeys[1][0]}

             relObj = {"id":id,"name":relDesc.forwardPathLabel,"relatedTableId":destId,"cardinality":"esriRelCardinality"+relDesc.cardinality,"role":"esriRelRoleOrigin","keyField":relDesc.originClassKeys[0][0],"composite":relDesc.isComposite}
             destIds[str(originId)]=id
             id=id+1

             try:
                len(relationshipObj[relDesc.originClassNames[0]])
             except:
                relationshipObj[relDesc.originClassNames[0]]=[]

             relationshipObj[relDesc.originClassNames[0]].append(relObj)

             try:
                len(relationshipObj[relDesc.destinationClassNames[0]])
             except:
                relationshipObj[relDesc.destinationClassNames[0]]=[]

             #if relationship already exists, use its id instead
             destId = id
             #if destIds[originId]:
             try:
                 destId = destIds[str(originId)]
             except:
                 pass

             
             relObj = {"id":destId,"name":relDesc.backwardPathLabel,"relatedTableId":originId,"cardinality":"esriRelCardinality"+relDesc.cardinality,"role":"esriRelRoleDestination","keyField":relDesc.originClassKeys[1][0],"composite":relDesc.isComposite}
             relationshipObj[relDesc.destinationClassNames[0]].append(relObj)

           #printMessage(json.dumps(relationshipObj, indent=4, sort_keys=True))
           #print(destIds)
           #config["services"][serviceName]["relationships"]=relations
           project["relationships"]=relations
           #return



           #printMessage(relationships)
           #for rc in relationships:
           #   rc_path = ws + "\\" + rc
           #   des_rc = arcpy.Describe(rc_path)
           #   printMessage(des_rc.originClassNames)

           #rc_list = [c.name for c in arcpy.Describe(workspace).children if c.datatype == "RelationshipClass"]
           #for rc in rc_list:
           #rc_path = workspace + "\\" + rc
           #des_rc = arcpy.Describe(rc_path)
           #origin = des_rc.originClassNames
           #destination = des_rc.destinationClassNames

           #mxd.activeDataFrame=dataFrame
           mxd.activeView = dataFrame.name
           arcpy.RefreshActiveView()

           #out_file_name = r"c:\thumbnails\{basename}.png".format(basename=os.path.basename(featureclass))
           # Export "thumbnail" of data frame

           #if the folder does not exist create it
           if not os.path.exists(servicesDestinationPath+"/thumbnails/"):
              os.makedirs(servicesDestinationPath+"/thumbnails/")

           out_file_name = servicesDestinationPath + "/thumbnails/" + serviceName + ".png"
           arcpy.mapping.ExportToPNG(mxd, out_file_name, dataFrame, 200, 133)

           #dataFrame = arcpy.mapping.ListDataFrames(mxd, "*")[0]
           #if dataFrame != mxd.activeDataFrame:
           #   printMessage("Active data frame is not the first data frame")

           feature_services['folders'].append(serviceName)

           #now set path to serviceName folder
           #destinationPath = servicesDestinationPath + "/data" #+ serviceName
           #print destinationPath
           #printMessage("Spatial JSON destination path: " + servicesDestinationPath)
           #if the folder does not exist create it
           #if not os.path.exists(destinationPath):
           #    os.makedirs(destinationPath)

           rootService_json={"folders": [], "services":[{"name":serviceName,"type":"FeatureServer","url":"http://"+serverName+"/rest/services/"+serviceName+"/FeatureServer"},{"name":serviceName,"type":"MapServer"}], "currentVersion": arcpy.GetInstallInfo()['Version']}
           file = saveJSON(servicesDestinationPath + "/"+serviceName+".json",rootService_json)
           LoadService(sqliteDb,serviceName,serviceName, "",-1,"",file)

           #analysis = arcpy.mapping.AnalyzeForMSD(mxd)
           #
           #for key in ('messages', 'warnings', 'errors'):
           #  printMessage( "----" + key.upper() + "---")
           #  vars = analysis[key]
           #  for ((message, code), layerlist) in vars.iteritems():
           #    printMessage( "    " + message + " (CODE %i)" % code)
           #    printMessage( "       applies to:")
           #    for layer in layerlist:
           #        printMessage( layer.name)
           #    printMessage("")

#           sddraft = templatePath + serviceName + '.sddraft'
#           sd = templatePath + serviceName + '.sd'
#           summary = 'Sample output'
#           tags = 'county, counties, population, density, census'
#
#           # create service definition draft
#           analysis = arcpy.mapping.CreateMapSDDraft(mxd, sddraft, serviceName, 'ARCGIS_SERVER')
#
#           for key in ('messages', 'warnings', 'errors'):
#             printMessage("----" + key.upper() + "---")
#             vars = analysis[key]
#             for ((message, code), layerlist) in vars.iteritems():
#               printMessage("    " +  message + " (CODE %i)" % code)
#               printMessage("       applies to:")
#               for layer in layerlist:
#                   printMessage(layer.name)
#               printMessage("")
#
#           printMessage("")
#           printMessage("")
#           #arcpy.StageService_server(sddraft, sd)
#
#           # stage and upload the service if the sddraft analysis did not contain errors
#           if analysis['errors'] == {}:
#               # Execute StageService
#               arcpy.StageService_server(sddraft, sd)
#               # Execute UploadServiceDefinition
#               #arcpy.UploadServiceDefinition_server(sd, con)
#           else:
#               # if the sddraft analysis contained errors, display them
#               #arcpy.StageService_server(sddraft, sd)
#               printMessage(analysis['errors'])
#               #print analysis['errors']

           #arcpy.mapping.ConvertToMSD(mxd,toolkitPath+"/output.msd",dataFrame, "NORMAL", "NORMAL")
           #mxde = MxdExtras(mxd)
           #for lyr in mxde.itervalues():
           #   printMessage("Layer Name: " + lyr.name )
           #   printMessage("Layer Symbology Field Name: " + lyr.symbologyFieldName)

           oldspatialref = dataFrame.spatialReference
           coordinateSystem = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.017453292519943295]]'
           #set to wgs84
           dataFrame.spatialReference = coordinateSystem
           #get coors of extent center in new coordinate system
           x = (dataFrame.extent.XMin + dataFrame.extent.XMax)/2
           y = (dataFrame.extent.YMin + dataFrame.extent.YMax)/2
           #printMessage(str(dataFrame.extent.XMin) + "," + str(dataFrame.extent.YMin) + "," + str(dataFrame.extent.XMax)  + "," + str(dataFrame.extent.YMax))
           xmin_geo=dataFrame.extent.XMin
           xmax_geo=dataFrame.extent.XMax
           ymin_geo=dataFrame.extent.YMin
           ymax_geo=dataFrame.extent.YMax
           # set dataframe spatial ref back
           dataFrame.spatialReference = oldspatialref

           output = {
             "extent": {
               "xmin": dataFrame.extent.XMin,
               "ymin": dataFrame.extent.YMin,
               "xmax": dataFrame.extent.XMax,
               "ymax": dataFrame.extent.YMax
             },
             "scale": dataFrame.scale,
             "rotation": dataFrame.rotation,
             "spatialReference": {"wkid": dataFrame.spatialReference.PCSCode}
           }

           result=copy.deepcopy(baseResult) # deep  copy
           result['snippet']=summary
           result['title']=dataFrame.description
           result['id']=serviceName
           #result['extent']=[0,0]
           result['extent'][0]=[0,0]
           result['extent'][1]=[0,0]
           result['extent'][0][0]=xmin_geo
           result['extent'][0][1]=ymin_geo
           result['extent'][1][0]=xmax_geo
           result['extent'][1][1]=ymax_geo
           result['owner']=username
           result['created']=created_ts
           result['modified']=created_ts
           if tags!="":
               result['tags']=tags.split(",")
           search_json['results'].append(result)
           #result = result + 1

           #only need to update the operationalLayers
           content_items_json=openJSON(templatePath + "/content.items.data.json")
           opLayers = getOperationalLayers(operationalLayers,serverName,serviceName,symbols)
           opTables = getTables(operationalTables,serverName,serviceName,len(opLayers))
           #need to update id (unique id=serviceName + layer name) and itemId (should be the serviceName)
           content_items_json['operationalLayers']=copy.deepcopy(opLayers) # deep  copy
           content_items_json['tables']=copy.deepcopy(opTables)
           for lyr in content_items_json['operationalLayers']:
               lyr["itemId"]=serviceName
               lyr["id"]=serviceName+"_"+lyr["title"].replace(" ","_")

           for lyr in content_items_json['tables']:
               lyr["itemId"]=serviceName
               lyr["id"]=serviceName+"_"+lyr["title"].replace(" ","_")

           file = saveJSON(servicesDestinationPath + "/content.data.json",content_items_json)
           LoadService(sqliteDb,serviceName,"content","", -1,"data",file)

           content_items_json=openJSON(templatePath + "/content.items.json")
           #content_items_json["id"]=title
           content_items_json["id"]=serviceName
           content_items_json["name"]=None
           content_items_json["owner"]=username
           content_items_json["created"]=created_ts
           content_items_json["modified"]=created_ts
           content_items_json["title"]=title
           content_items_json["snippet"]=summary
           content_items_json["description"]=description
           content_items_json['extent'][0][0]=xmin_geo
           content_items_json['extent'][0][1]=ymin_geo
           content_items_json['extent'][1][0]=xmax_geo
           content_items_json['extent'][1][1]=ymax_geo
           content_items_json["url"]=None

           #content_items_json["type"]="Feature Service"
           #content_items_json["url"]="http://"+serverName+"/rest/services/"+serviceName+"/FeatureServer"

           file=saveJSON(servicesDestinationPath + "/content.items.json",content_items_json)
           LoadService(sqliteDb,serviceName,"content","", -1,"items",file)

           #create JSON description of all services.  Each dataframe is a service for this application.
           featureserver_json={
              "currentVersion":arcpy.GetInstallInfo()['Version'],
              "services": [{
                 "name":serviceName,
                 "type":"FeatureServer",
                 "url": "http://"+serverName + "/arcgis/rest/services/"+serviceName+"/FeatureServer"
              }]
           }
           #file=saveJSON(servicesDestinationPath + "/FeatureServer.json",featureserver_json)
           #LoadService(sqliteDb,serviceName,"FeatureServer", -1,"",file)

           #create JSON description of all layers in the service.
           featureserver_json=openJSON(templatePath + "/name.FeatureServer.json")
           featureserver_json['initialExtent']['xmin']=dataFrame.extent.XMin
           featureserver_json['initialExtent']['ymin']=dataFrame.extent.YMin
           featureserver_json['initialExtent']['xmax']=dataFrame.extent.XMax
           featureserver_json['initialExtent']['ymax']=dataFrame.extent.YMax
           featureserver_json['fullExtent']['xmin']=dataFrame.extent.XMin
           featureserver_json['fullExtent']['ymin']=dataFrame.extent.YMin
           featureserver_json['fullExtent']['xmax']=dataFrame.extent.XMax
           featureserver_json['fullExtent']['ymax']=dataFrame.extent.YMax
           featureserver_json['layers'] = getLayers(operationalLayers)
           featureserver_json['tables']=operationalTablesObj
           
           file=saveJSON(servicesDestinationPath + "/FeatureServer.json",featureserver_json)
           LoadService(sqliteDb,serviceName,"FeatureServer", "",-1,"",file)

           maps_json=openJSON(templatePath + "/name.MapServer.json")
           maps_json['initialExtent']['xmin']=dataFrame.extent.XMin
           maps_json['initialExtent']['ymin']=dataFrame.extent.YMin
           maps_json['initialExtent']['xmax']=dataFrame.extent.XMax
           maps_json['initialExtent']['ymax']=dataFrame.extent.YMax
           maps_json['fullExtent']['xmin']=dataFrame.extent.XMin
           maps_json['fullExtent']['ymin']=dataFrame.extent.YMin
           maps_json['fullExtent']['xmax']=dataFrame.extent.XMax
           maps_json['fullExtent']['ymax']=dataFrame.extent.YMax
           maps_json['layers'] = featureserver_json['layers']
           maps_json['server']=serverName
           maps_json['name']=serviceName
           maps_json['mapName']=serviceName
           maps_json['tables']=operationalTablesObj
           file=saveJSON(servicesDestinationPath + "/MapServer.json",maps_json)
           LoadService(sqliteDb,serviceName,"MapServer","", -1,"",file)

           minx=str(dataFrame.extent.XMin)
           miny=str(dataFrame.extent.YMin)
           maxx=str(dataFrame.extent.XMax)
           maxy=str(dataFrame.extent.YMax)
           serviceitems_json=openJSON(templatePath + "/GDB_ServiceItems.json")
           serviceitems_json["name"]=title
           serviceitems_json["serviceDescription"]=summary
           serviceitems_json["description"]=description
           serviceitems_json['initialExtent']['xmin']=dataFrame.extent.XMin
           serviceitems_json['initialExtent']['ymin']=dataFrame.extent.YMin
           serviceitems_json['initialExtent']['xmax']=dataFrame.extent.XMax
           serviceitems_json['initialExtent']['ymax']=dataFrame.extent.YMax
           serviceitems_json['fullExtent']['xmin']=dataFrame.extent.XMin
           serviceitems_json['fullExtent']['ymin']=dataFrame.extent.YMin
           serviceitems_json['fullExtent']['xmax']=dataFrame.extent.XMax
           serviceitems_json['fullExtent']['ymax']=dataFrame.extent.YMax
 
           createReplica(mxd,dataFrame,allData,replicaDestinationPath,toolkitPath,username,serviceName,serverName,minx,miny,maxx,maxy,relationshipList,layerIds,serviceitems_json)

           #create a JSON service file for each feature layer -- broken ---
           serviceRep=[]

           id=0
           for lyr in operationalLayers:
               desc = arcpy.Describe(lyr)
               if hasattr(desc, "layer"):
                   featureName=os.path.basename(desc.layer.catalogPath)
               else:
                   featureName=os.path.basename(desc.catalogPath)
  
               printMessage("Loading layer: "+lyr.name+": " + featureName)
 
               feature_json=openJSON(templatePath + "/name.FeatureServer.id.json")
               feature_json['defaultVisibility']=lyr.visible
               feature_json['description'] = lyr.description
               feature_json['fields']=getFields(lyr)
               #type=esriFieldTypeOID

               #for i in feature_json:
               #     printMessage(i + ": " + str(feature_json[i]))
               #printMessage(feature_json['displayField'])
               #if lyr.showLabels:
               lbl=""
               if lyr.supports("LABELCLASSES"):
                   for lblclass in lyr.labelClasses:
                       lblclass.showClassLabels = True
                       #feature_json.displayField
                       lbl=lblclass.expression.replace("[","").replace("]","")
               #lblclass.expression = " [Label]"
               if lbl!="":
                  feature_json['displayField']=lbl
               else:
                  feature_json['displayField']=getDisplayField(feature_json['fields'])

               if desc.shapeType:
                   if desc.shapeType=='Polygon':
                      feature_json['geometryType']='esriGeometryPolygon'
                      feature_json['templates'][0]['drawingTool']="esriFeatureEditToolPolygon"
                   elif desc.shapeType=='Polyline':
                      feature_json['geometryType']='esriGeometryPolyline'
                      feature_json['templates'][0]['drawingTool']="esriFeatureEditToolPolyline"
                   elif desc.shapeType=='Point':
                      feature_json['geometryType']='esriGeometryPoint'

                   elif desc.shapeType=='MultiPoint':
                      feature_json['geometryType']='esriGeometryMultiPoint'
               feature_json['id']=layerIds[lyr.name] #id
               feature_json['name']=lyr.name
               if desc.hasOID:
                   feature_json['objectIdField']=desc.OIDFieldName
                   feature_json['objectIdFieldName']=desc.OIDFieldName
               if desc.hasGlobalID:
                   feature_json['globalIdField'] = desc.globalIDFieldName
                   feature_json['globalIdFieldName']=desc.globalIDFieldName
               else:
                   del feature_json['globalIdField']
                   #del feature_json['globalIdFieldName']

               feature_json['indexes']=getIndexes(lyr)
               feature_json['minScale']=lyr.minScale
               feature_json['maxScale']=lyr.maxScale
               #bad below, should be Feature Layer, not FeatureLayer
               #feature_json['type']=desc.dataType #'Feature Layer'
               feature_json['extent']['xmin']=desc.extent.XMin
               feature_json['extent']['ymin']=desc.extent.YMin
               feature_json['extent']['xmax']=desc.extent.XMax
               feature_json['extent']['ymax']=desc.extent.YMax
               #feature_json['indexes']=[]
               feature_json['templates'][0]['name']=serviceName
               attributes={}
               for field in feature_json['fields']:
                   #printMessage(field['name'])
                   if field['editable']:
                      attributes[ field['name'] ]=None
               feature_json['templates'][0]['prototype']['attributes']=attributes

               #feature_json['drawingInfo']['renderer']['symbol']=getSymbol(lyr)
               #feature_json['relationships']=getRelationships(lyr,id,len(operationalLayers),operationalTables,relationshipObj)
               try:
                  feature_json['relationships']=relationshipObj[featureName] #getRelationships(lyr,relationshipObj)
               except:
                  pass

               feature_json['drawingInfo']=getSymbol(lyr,symbols[featureName]["symbols"],lyr.name)
               #set editor tracking fields
               editorTracking={}
               if desc.editorTrackingEnabled:
                  editorTracking['creationDateField']=desc.createdAtFieldName
                  editorTracking['creatorField']=desc.creatorFieldName
                  editorTracking['editDateField']=desc.editedAtFieldName
                  editorTracking['editorField']=desc.editorFieldName
                  feature_json['editFieldsInfo']=editorTracking
                  
               else:
                  del feature_json['editFieldsInfo']

               feature_json['editingInfo']={"lastEditDate":created_ts}

               if arcpy.Exists(rootFGDB+"/"+featureName+"__ATTACH"):
                  feature_json['hasAttachments']=True
                  feature_json['advancedQueryCapabilities']['supportsQueryAttachments']=True
                  feature_json['attachmentProperties']=[{"name":"name","isEnabled":True},{"name":"size","isEnabled":True},{"name":"contentType","isEnabled":True},{"name":"keywords","isEnabled":True}]
               else:
                  feature_json['hasAttachments']=False
               
               #getSymbol(lyr,symbols[featureName],lyr.name)
               #opLayers = content_items_json['operationalLayers']=getOperationalLayers(operationalLayers,serverName,serviceName)
               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(layerIds[lyr.name])+".json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer",lyr.name, layerIds[lyr.name],"",file)

               #now create a MapServer json file
               mapserver_json=openJSON(templatePath + "/name.MapServer.id.json")
               mapserver_json['indexes']=feature_json['indexes']
               mapserver_json['extent']=feature_json['extent']
               mapserver_json['fields']=feature_json['fields']
               
               mapserver_json['templates']=feature_json['templates']
               mapserver_json['drawingInfo']=feature_json['drawingInfo']
               mapserver_json['geometryType']=feature_json['geometryType']

               file=saveJSON(servicesDestinationPath + "/MapServer."+str(layerIds[lyr.name])+".json",feature_json)
               LoadService(sqliteDb,serviceName,"MapServer", lyr.name,layerIds[lyr.name],"",file)

               #save replica file
               feature_json=openJSON(templatePath + "/name.FeatureServer.id.json")

               #steps: save layer to blank mxd, save it, run arcpy.CreateRuntimeContent on mxd
               createSingleReplica(templatePath,dataFrame,lyr,replicaDestinationPath,toolkitPath,feature_json,serverName,serviceName,username,id)
               #save mapserver .map file
               saveMapfile(mapfileDestinationPath + "/"+lyr.name+".map",lyr,desc,dataDestinationPath,mapserver_json)

               id = id+1

           #create a JSON geometry file for each feature layer
           id=0
           globalFields=[]
           valid_fields =[]# ["OBJECTID","GlobalID","GlobalGUID","has_permittee"]
           for lyr in operationalLayers:
               desc = arcpy.Describe(lyr)
               if hasattr(desc, "layer"):
                   featureName=os.path.basename(desc.layer.catalogPath)
                   inFeaturesGDB=desc.layer.path
               else:
                   featureName=os.path.basename(desc.catalogPath)
                   inFeaturesGDB=desc.path
               if sqliteDb:
                   saveToSqlite(lyr,sqliteDb)
                   if arcpy.Exists(inFeaturesGDB+"/"+featureName+"__ATTACH"):
                      saveToSqlite(inFeaturesGDB+"/"+featureName+"__ATTACH",sqliteDb)
               if pg:
                   saveToPg(lyr,pg)
                   if arcpy.Exists(inFeaturesGDB+"/"+featureName+"__ATTACH"):
                      saveAttachTableToPg(inFeaturesGDB,featureName,"__ATTACH",pg)

               fSet = arcpy.FeatureSet()
               fSet.load(desc.dataElement.catalogPath)
               fdesc = arcpy.Describe(fSet)
               #printMessage(fdesc.json)
               dataName = os.path.basename(desc.dataElement.catalogPath)
               layerObj={"name":lyr.name,"data":dataName}
               layerObj["id"]=layerIds[lyr.name]
               if desc.relationshipClassNames:
                  for j,rel in enumerate(desc.relationshipClassNames):
                    relDesc = arcpy.Describe(desc.path +"/"+rel)
                    for i in relDesc.originClassKeys:
                        #if i[1]=="OriginPrimary":
                        if i[1]=="OriginForeign":
                            layerObj["joinField"]=i[0]
                            #globalFields.append(layerObj["joinField"])
                            valid_fields.append(layerObj["joinField"])

               #fields = copy.deepcopy(feature_json['fields'])
               feature_json = json.loads(fdesc.json)
               feature_json['fields']=getFields(lyr)
               #feature_json=openJSON(templatePath + "/name.FeatureServer.id.query.json")
               #feature_json['features']=getFeatures(lyr)
               #feature_json['fields']=getFields(lyr)
               #if desc.shapeType:
               #    if desc.shapeType=='Polygon':
               #       feature_json['geometryType']='esriGeometryPolygon'
               #    elif desc.shapeType=='Polyline':
               #       feature_json['geometryType']='esriGeometryPolyline'
               #    elif desc.shapeType=='Point':
               #       feature_json['geometryType']='esriGeometryPoint'
               #    elif desc.shapeType=='MultiPoint':
               #       feature_json['geometryType']='esriGeometryMultiPoint'

               if desc.hasOID:
                   feature_json['objectIdField']=desc.OIDFieldName
                   layerObj["oidname"]=desc.OIDFieldName
                   feature_json['objectIdFieldName']=desc.OIDFieldName
                   valid_fields.append(desc.OIDFieldName)

               if desc.hasGlobalID:
                   feature_json['globalIdField'] = desc.globalIDFieldName
                   feature_json['globalIdFieldName']=desc.globalIDFieldName
                   layerObj["globaloidname"]=desc.globalIDFieldName
                   globalFields.append(desc.globalIDFieldName)
                   valid_fields.append(desc.globalIDFieldName)
               #else:
                   #del feature_json['globalIdField']
                   #del feature_json['globalIdFieldName']
               for field in desc.fields:
                   if field.type == 'Guid':
                      globalFields.append(field.name)

               try:
                  if symbols[featureName]["fields"]:
                      valid_fields.append(symbols[featureName]["fields"])
               except Exception as e:
                      pass
                      
               layerObj["type"]="layer"
               #remove the defaultValue is it is NEWID() WITH VALUES
               #for i in feature_json['fields']:
               #    try:
               #        if i.defaultValue=="NEWID() WITH VALUES":
               #           i.defaultValue=None
               #    except Exception as e:
               #        pass        

               #globalFields = ["GlobalID","GlobalGUID"]
               #OBS! must remove the curly brackets around the globalId and GlobalGUID attributes
               for i in feature_json['features']:
                  for j in i['attributes']:
                     if j in globalFields:
                        #printMessage(j)
                        #printMessage(i['attributes'][j])
                        i['attributes'][j]=i['attributes'][j].replace("{","").replace("}","")
               
               printMessage("Saving layer " + lyr.name + "(" + str(layerIds[lyr.name]) + ") to JSON")
               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(layerIds[lyr.name])+".query.json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer",lyr.name, layerIds[lyr.name],"query",file)

               #create file containing objectid,globalid and any field used for symbology
               fields = []
               for i in feature_json['fields']:
                  if i['name'] in valid_fields:
                      fields.append(i)
                     #try:
                     #   feature_json['fields'].remove(i)
                     #   del i
                     #except:
                     #   pass
                     #del i
                     #del feature_json['fields'][i]
               feature_json['fields'] = fields
               for i in feature_json['features']:
                  for j in i['attributes'].keys():
                     if j not in valid_fields:
                        del i['attributes'][j]
                        #del feature_json['features']['attributes'][j]
               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(id)+".outfields.json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer", "",id,"outfields",file)

               #create a JSON OBJECTID file used in ArcGIS for showing the attribute table
               #remove all fields except OBJECTID
               #feature_json['fields']=[{"alias":"OBJECTID","name":"OBJECTID","type":"esriFieldTypeInteger","alias":"OBJECTID","sqlType":"sqlTypeOther","defaultValue":None,"domain":None}]
               #OBJECTID,GlobalID,has_permittee

               feature_json['fields']=[
                   {"alias":"OBJECTID","name":"OBJECTID","type":"esriFieldTypeOID","sqlType":"sqlTypeOther","defaultValue":None,"domain":None,"nullable":False,"editable":False}
               ]
               features=[]
               #for i in feature_json['fields']:
               #   if i['name'] != 'OBJECTID':
               #      del i
               #      #del feature_json['fields'][i]
               for i in feature_json['features']:
                  if desc.OIDFieldName:
                    features.append({"attributes":{"OBJECTID":i['attributes'][desc.OIDFieldName]}})
               feature_json['features']=features
                  #for j in i['attributes']:
                  #    if j == 'OBJECTID':
                  #      attribute={"OBJECTID":j}
                  #      #del j
                  #for j in feature_json['features'][i]['attributes']:
                  #   if feature_json['features'][i]['attributes'][j]['name'] != 'OBJECTID':
                  #      del feature_json.features[i]['attributes'][j]

               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(layerIds[lyr.name])+".objectid.json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer",lyr.name, layerIds[lyr.name],"objectid",file)
               layerObj["itemId"]= lyr.name.replace(" ","_")+str(layerIds[lyr.name])
               if desc.editorTrackingEnabled:
                  #save to config too for easy access
                  try:
                    layerObj["editFieldsInfo"]=feature_json['editFieldsInfo']
                  except Exception as e:
                    pass

               #config["services"][serviceName]["layers"][str(layerIds[lyr.name])]=layerObj
               project["layers"][str(layerIds[lyr.name])]=layerObj
               id = id+1

           #now save any tables
           globalFields=[]
           valid_fields =[]
           for tbl in operationalTables:
               desc = arcpy.Describe(tbl)
               #featureName=os.path.basename(desc.catalogPath)

               if hasattr(desc, "layer"):
                   featureName=os.path.basename(desc.layer.catalogPath)
                   inFeaturesGDB=desc.layer.path
               else:
                   featureName=os.path.basename(desc.catalogPath)
                   inFeaturesGDB=desc.path
               if sqliteDb:
                   saveToSqlite(tbl,sqliteDb)
                   if arcpy.Exists(inFeaturesGDB+"/"+featureName+"__ATTACH"):
                      saveToSqlite(inFeaturesGDB+"/"+featureName+"__ATTACH",sqliteDb)   
               if pg:
                   saveToPg(tbl,pg)
                   if arcpy.Exists(inFeaturesGDB+"/"+featureName+"__ATTACH"):
                      saveAttachTableToPg(inFeaturesGDB,featureName,"__ATTACH",pg)

               feature_json=openJSON(templatePath + "/name.RecordSet.id.json")
               #feature_json['description'] = tbl.description
               tableObj={"name":tbl.name,"data":featureName}
               feature_json['fields']=getFields(tbl)
               feature_json['displayField']=getDisplayField(feature_json['fields'])

               #feature_json['relationships']=getRelationships(tbl,id,len(operationalLayers),operationalTables,relationshipObj)
               #feature_json['relationships']=getRelationships(lyr,relationshipObj)

               feature_json['id']=layerIds[tbl.name]
               feature_json['name']=tbl.name
               if desc.hasOID:
                   feature_json['objectIdField']=desc.OIDFieldName
                   feature_json['objectIdFieldName']=desc.OIDFieldName
                   tableObj["oidname"]=desc.OIDFieldName
                   valid_fields.append(desc.OIDFieldName)
               if desc.hasGlobalID:
                   feature_json['globalIdField'] = desc.globalIDFieldName
                   feature_json['globalIdFieldName']=desc.globalIDFieldName
                   tableObj["globaloidname"]=desc.globalIDFieldName
                   globalFields.append(desc.globalIDFieldName)
                   valid_fields.append(desc.globalIDFieldName)
               else:
                   del feature_json['globalIdField']
                   #del feature_json['globalIdFieldName']
                   
               for field in desc.fields:
                  if field.type == 'Guid':
                      globalFields.append(field.name)

               tableObj["type"]="table"
               tableObj["id"]=layerIds[tbl.name]
               if desc.relationshipClassNames:
                  for j,rel in enumerate(desc.relationshipClassNames):
                    relDesc = arcpy.Describe(desc.path +"/"+rel)
                    for i in relDesc.originClassKeys:
                        #if i[1]=="OriginPrimary":
                        if i[1]=="OriginForeign":
                            tableObj["joinField"]=i[0]
                            #globalFields.append(tableObj["joinField"])
                            valid_fields.append(tableObj["joinField"])
               
               feature_json['indexes']=getIndexes(tbl)
               feature_json['templates'][0]['name']=serviceName
               attributes={}
               for field in feature_json['fields']:
                   #printMessage(field['name'])
                   if field['editable']:
                      attributes[ field['name'] ]=None
               feature_json['templates'][0]['prototype']['attributes']=attributes

               #printMessage(tbl.name+": " + featureName)
               feature_json['relationships']=relationshipObj[featureName]

               #set editor tracking fields
               editorTracking={}
               if desc.editorTrackingEnabled:
                  editorTracking['creationDateField']=desc.createdAtFieldName
                  editorTracking['creatorField']=desc.creatorFieldName
                  editorTracking['editDateField']=desc.editedAtFieldName
                  editorTracking['editorField']=desc.editorFieldName
                  feature_json['editFieldsInfo']=editorTracking
                  #save to config too for easy access
                  tableObj["editFieldsInfo"]=editorTracking
               else:
                  del feature_json['editFieldsInfo']

               feature_json['editingInfo']={"lastEditDate":created_ts}

               if arcpy.Exists(rootFGDB+"/"+featureName+"__ATTACH"):
                  feature_json['hasAttachments']=True
                  feature_json['advancedQueryCapabilities']['supportsQueryAttachments']=True
                  feature_json['attachmentProperties']=[{"name":"name","isEnabled":True},{"name":"size","isEnabled":True},{"name":"contentType","isEnabled":True},{"name":"keywords","isEnabled":True}]
                  
               else:
                  feature_json['hasAttachments']=False

               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(layerIds[tbl.name])+".json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer", tbl.name,layerIds[tbl.name],"",file)
               tableObj["itemId"]= tbl.name.replace(" ","_")+str(layerIds[tbl.name])
               
               #config["services"][serviceName]["layers"][str(layerIds[tbl.name])]=tableObj
               project["layers"][str(layerIds[tbl.name])]=tableObj

               #fields = copy.deepcopy(feature_json['fields'])
               fSet = arcpy.RecordSet()
               fSet.load(desc.catalogPath)
               fdesc = arcpy.Describe(fSet)
               #printMessage(fdesc.json)
               feature_json = json.loads(fdesc.json)
               #replace fields with full fields
               feature_json['fields']=getFields(tbl)
               #remove the defaultValue is it is NEWID() WITH VALUES
               #for i in feature_json['fields']:
               #    try:
               #        if i.defaultValue=="NEWID() WITH VALUES":
               #           i.defaultValue=None
               #    except Exception as e:
               #        pass        
               #OBS! must remove the curly brackets around the globalId and GlobalGUID attributes
               for i in feature_json['features']:
                  for j in i['attributes']:
                     if j in globalFields:
                        i['attributes'][j]=i['attributes'][j].replace("{","").replace("}","")
               

               #dataName = os.path.basename(desc.dataElement.catalogPath)
               #layerObj={"name":lyr.name,"data":dataName}
               printMessage("Saving table " + tbl.name + "("+str(layerIds[tbl.name]) + ") to JSON")
               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(layerIds[tbl.name])+".query.json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer",tbl.name, layerIds[tbl.name],"query",file)

               #valid_fields = ["OBJECTID","GlobalID","GlobalGUID","has_permittee"]
               fields = []
               for i in feature_json['fields']:
                  if i['name'] in valid_fields:
                     fields.append(i)
                     #feature_json['fields'].remove(i)
                     #del i
               feature_json['fields'] = fields
               for i in feature_json['features']:
                  for j in i['attributes'].keys():
                     if j not in valid_fields:
                        del i['attributes'][j]
               file=saveJSON(servicesDestinationPath + "/FeatureServer."+str(layerIds[tbl.name])+".outfields.json",feature_json)
               LoadService(sqliteDb,serviceName,"FeatureServer",tbl.name, layerIds[tbl.name],"outfields",file)
               

               id = id+1

           #export all layers to shapefiles for rendering in mapserver
           for lyr in operationalLayers:
               desc = arcpy.Describe(lyr)
               if desc.dataType == "FeatureLayer":
                  printMessage("Exporting layer to shapefile: "+ lyr.name)
                  arcpy.FeatureClassToFeatureClass_conversion(desc.dataElement.catalogPath,
                     dataDestinationPath,
                     lyr.name+".shp")

           id = id+1

        #now save the search results
        search_json['total']=len(search_json['results'])
        file=saveJSON(baseDestinationPath + "/search.json",search_json)
        LoadCatalog(sqliteDb,"search", "",file)
        #save root FeatureServer.json file
        file=saveJSON(baseDestinationPath + "/FeatureServer.json",feature_services)
        LoadCatalog(sqliteDb,"FeatureServer", "",file)
        file=saveJSON(baseDestinationPath + "/MapServer.json",feature_services)
        LoadCatalog(sqliteDb,"MapServer", "",file)
        file=saveJSON(baseDestinationPath + "/config.json",config)
        LoadCatalog(sqliteDb,"config", "",file)
        if pg:
             saveSqliteToPG(["catalog","services"],sqliteDb,pg)
             saveSqliteServiceTablesToPG(replicaDestinationPath+"/"+serviceName+".geodatabase",pg)
 
        #conn.close()
        printMessage("Finished")

def openJSON(name):
    printMessage("Loading JSON template: " +name)
    with open(name, "r+") as f:
       json_data = json.load(f)
       f.close()
       return json_data

def saveJSON(name,json_data): #optional
    data = json.dumps(json_data)
    with open(name,'w') as f:
       f.write(data)
    return data

def clearSelections(mxd):
    for df in arcpy.mapping.ListDataFrames(mxd):
       for lyr in arcpy.mapping.ListLayers(mxd, "", df):
          # Exit if the current layer is not a service layer.
          if  lyr.isServiceLayer or lyr.supports("SERVICEPROPERTIES"):  # or not lyr.visible
            continue
          if not lyr.isFeatureLayer:
            continue
          #printMessage(lyr.name +": " + arcpy.Describe(lyr).catalogPath)
          arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
          #arcpy.Describe(lyr).catalogPath

def getSymbology(mxd):
    msdPath = os.path.abspath(os.path.dirname(__file__)).replace("\\","/")+"/output.msd"
    #msdPath = self.mxdPath.replace(self.MXD_SUFFIX, self.MSD_SUFFIX)

    # Delete temporary msd if it exists
    if os.path.exists(msdPath):
        os.remove(msdPath)

    clearSelections(mxd)
    arcpy.mapping.ConvertToMSD(mxd,msdPath)
    msd_metadata={}
    msd_metadata["symbols"]={}

    zz = zipfile.ZipFile(msdPath)
    EXCLUDED_FILE_NAMES = ["DocumentInfo.xml", "GISProject.xml", "layers/layers.xml"]
    for fileName in (fileName for fileName in zz.namelist() if not fileName in EXCLUDED_FILE_NAMES):
        printMessage("Opening: " + fileName)
        dom = parse(zz.open(fileName))
        #get Name, DisplayName, DatasetType, MinScale, MaxScale
        #get FeatureTable->DisplayField
        #FeatureTable->DataConnection->Dataset
        #child = dom.getElementsByTagName("Name")
        #displayName = dom.getElementsByTagName("DisplayName")
        #datasetType = dom.getElementsByTagName("DatasetType")
        #datasetType = dom.getElementsByTagName("DatasetType")
        obj = dom.getElementsByTagName("Dataset")
        if len(obj) > 0:
            name=str(obj[0].childNodes[0].nodeValue)
        else:
            name=fileName.split(".")[0]+"_root"

        msd_metadata[name]={}
        #for j in dom.childNodes:
        #   if j.tagName == "Name":
        #       name = str(j.childNodes[0].nodeValue)
        #       msd_metadata["name"]={}
        for j in dom.childNodes[0].childNodes:   
           if j.tagName == "DisplayName":
               msd_metadata[name]["displayName"]=str(j.childNodes[0].nodeValue)
           elif j.tagName == "Name":
                msd_metadata[name]["name"]=str(j.childNodes[0].nodeValue) 
           elif j.tagName == "DatasetType":
               msd_metadata[name]["datasetType"]=str(j.childNodes[0].nodeValue)    
           elif j.tagName == "FeatureTable":
               obj = j.getElementsByTagName("DisplayField")
               msd_metadata[name]["displayField"]=str(obj[0].childNodes[0].nodeValue)
               #obj = j.getElementsByTagName("Dataset")
               #msd_metadata[name]["dataset"]=str(obj[0].childNodes[0].nodeValue)
             

             #get the next symbol
             #k = j.getElementsByTagName("Symbol")
             #for m in k:
                #type = geomtype[0].getAttribute("xsi:type")=="typens:CIMPolygonSymbol"
             #   if m.getAttribute("xsi:type")=="typens:CIMPointSymbol":
             #      obj['symbol'] = getPointSymbol(m)
             #   elif m.getAttribute("xsi:type")=="typens:CIMPolygonSymbol":
             #      obj['symbol']=getPolygonSymbol(m)


            #symb = dom.getElementsByTagName("Symbolizer")
           elif j.tagName=="Symbolizer":
                #if symb.length>0:
                    #name=fileName.split(".")[0]
                    #rootname = name.split("/")
                    #if len(rootname)>1:
                    #  name=rootname[1]
                    #printMessage("Symbology found for : " + name + " length: " + str(symb.length))
               msd_metadata[name]["symbols"]=j
               #now get field for symbols if exists
               f = j.getElementsByTagName("Fields")
               if len(f)>0:
                   for m in f:
                       n = m.getElementsByTagName("String")
                       if len(n)>0:
                           msd_metadata[name]["fields"]=n[0].childNodes[0].nodeValue
                           printMessage("Found symbol field: " + msd_metadata[name]["fields"])




            #printMessage("Found: " + str(symb.length))
            #name,lyr = self.loadMsdLayerDom(dom)
            #if name != "":
            #   self[name] = lyr
    del zz
    return msd_metadata

def getLayers(opLayers):
  layers=[]
  id=0
  for lyr in opLayers:
     layer={
        "name":lyr.name,
        "id":id,
        "parentLayerId":-1,
        "defaultVisibility":lyr.visible,
        "subLayerIds":None,
        "minScale":lyr.minScale,
        "maxScale":lyr.maxScale
      }
     layers.append(layer)
     id=id+1
  return layers

def createReplica(mxd,dataFrame,allData,replicaDestinationPath,toolkitPath,username,serviceName,serverName,minx,miny,maxx,maxy,relationshipList,layerIds,serviceItems):
  global spatialite_path

  arcpy.CreateRuntimeContent_management(mxd.filePath,
              replicaDestinationPath + os.sep + serviceName,
              serviceName,"#","#",
              "FEATURE_AND_TABULAR_DATA","NON_OPTIMIZE_SIZE","ONLINE","PNG","1","#")
              #OPTIMIZE_SIZE, NON_OPTIMIZE_SIZE
  filenames = next(os.walk(replicaDestinationPath + "/"+serviceName+"/data/"))[2]
  printMessage("Renamed " + replicaDestinationPath + "/"+serviceName+"/data/"+filenames[0]+" to "+ replicaDestinationPath+"/"+serviceName+".geodatabase")
  #if offline geodatabase exists, must delete first
  newFullReplicaDB=replicaDestinationPath+"/"+serviceName+".geodatabase"
  try:
     if os.path.exists(newFullReplicaDB):
        os.rmdir(newFullReplicaDB)
  except:
     printMessage("Unable to remove old replica geodatabase")

  os.rename(replicaDestinationPath + "/"+serviceName+"/data/"+filenames[0], newFullReplicaDB)
  try:
     os.rmdir(replicaDestinationPath + "/"+serviceName+"/data/")
     os.rmdir(replicaDestinationPath + "/"+serviceName)
  except:
     printMessage("Unable to remove replica folders")

  #get the creation sql string for each layer including __ATTACH tables
  conn = sqlite3.connect(newFullReplicaDB)
  c = conn.cursor()
    #conn = sqlite3.connect("c:/massappraisal/colville/"+inFeaturesName+".sqlite")
  #c = conn.cursor()
  #c.execute("INSERT INTO catalog(name,type,json) VALUES(?,?,?)", (name,dtype,json))
  #c.close()
  #conn.commit()
  #map(tuple, array.tolist())
  

  creationDate = time.strftime("%Y-%m-%dT%H:%M:%S")
  sql1=('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
    " select MAX(ObjectID)+1, '{7B6EB064-7BF6-42C8-A116-2E89CD24A000}', '{5B966567-FB87-4DDE-938B-B4B37423539D}', 'MyReplica', 'MYREPLICA', 'MyReplica', '', 1, NULL, NULL, NULL, "
    "'http://"+serverName+"/arcgis/rest/services/"+serviceName+"/FeatureServer', '"+username+"',"
    "'<GPSyncReplica xsi:type=''typens:GPSyncReplica'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
    "<ReplicaName>MyReplica</ReplicaName><ID>1</ID><ReplicaID>{7b6eb064-7bf6-42c8-a116-2e89cd24a000}</ReplicaID>"
    "<ServiceName>http://"+serverName+"/arcgis/rest/services/"+serviceName+"/FeatureServer</ServiceName>"
    "<Owner>"+username+"</Owner>"
    "<Role>esriReplicaRoleChild</Role><SyncModel>esriSyncModelPerLayer</SyncModel><Direction>esriSyncDirectionBidirectional</Direction><CreationDate>"+creationDate+"</CreationDate><LastSyncDate>1970-01-01T00:00:01</LastSyncDate>"
    "<ReturnsAttachments>true</ReturnsAttachments><SpatialRelation>esriSpatialRelIntersects</SpatialRelation><QueryGeometry xsi:type=''typens:PolygonN''><HasID>false</HasID><HasZ>false</HasZ><HasM>false</HasM><Extent xsi:type=''typens:EnvelopeN''>"
    "<XMin>"+minx+"</XMin><YMin>"+miny+"</YMin><XMax>"+maxx+"</XMax><YMax>"+maxy+"</YMax></Extent><RingArray xsi:type=''typens:ArrayOfRing''><Ring xsi:type=''typens:Ring''>"
    "<PointArray xsi:type=''typens:ArrayOfPoint''>"
    "<Point xsi:type=''typens:PointN''><X>"+minx+"</X><Y>"+miny+"</Y></Point><Point xsi:type=''typens:PointN''><X>"+maxx+"</X><Y>"+miny+"</Y></Point>"
    "<Point xsi:type=''typens:PointN''><X>"+maxx+"</X><Y>"+maxy+"</Y></Point><Point xsi:type=''typens:PointN''><X>"+minx+"</X><Y>"+maxy+"</Y></Point>"
    "<Point xsi:type=''typens:PointN''><X>"+minx+"</X><Y>"+miny+"</Y></Point></PointArray></Ring></RingArray>"
    "<SpatialReference xsi:type=''typens:ProjectedCoordinateSystem''><WKT>PROJCS[&quot;WGS_1984_Web_Mercator_Auxiliary_Sphere&quot;,GEOGCS[&quot;GCS_WGS_1984&quot;,DATUM[&quot;D_WGS_1984&quot;,SPHEROID[&quot;WGS_1984&quot;,6378137.0,298.257223563]],PRIMEM[&quot;Greenwich&quot;,0.0],UNIT[&quot;Degree&quot;,0.0174532925199433]],PROJECTION[&quot;Mercator_Auxiliary_Sphere&quot;],PARAMETER[&quot;False_Easting&quot;,0.0],PARAMETER[&quot;False_Northing&quot;,0.0],PARAMETER[&quot;Central_Meridian&quot;,0.0],PARAMETER[&quot;Standard_Parallel_1&quot;,0.0],PARAMETER[&quot;Auxiliary_Sphere_Type&quot;,0.0],UNIT[&quot;Meter&quot;,1.0],AUTHORITY[&quot;EPSG&quot;,3857]]</WKT>"
    "<XOrigin>-20037700</XOrigin><YOrigin>-30241100</YOrigin><XYScale>10000</XYScale><ZOrigin>-100000</ZOrigin><ZScale>10000</ZScale><MOrigin>-100000</MOrigin><MScale>10000</MScale><XYTolerance>0.001</XYTolerance><ZTolerance>0.001</ZTolerance><MTolerance>0.001</MTolerance><HighPrecision>true</HighPrecision><WKID>102100</WKID><LatestWKID>3857</LatestWKID></SpatialReference></QueryGeometry><GPSyncDatasets xsi:type=''typens:ArrayOfGPSyncDataset''>")

  #lyrs=[]
  #for lyr in arcpy.mapping.ListLayers(mxd, "", dataFrame):
  #   # Exit if the current layer is not a service layer.
  #   if lyr.isServiceLayer or lyr.supports("SERVICEPROPERTIES"):  # or not lyr.visible
  #      continue
  #   lyrs.append(lyr)
  #for lyr in arcpy.mapping.ListTableViews(mxd, "", dataFrame):
  #   lyrs.append(lyr)
  #<RelationshipClassNames xsi:type="typens:Names"/>
  #<ChangeTracked>false</ChangeTracked>

  serviceItems["layers"]=[]

  #OBS!  must alter the OBJECTID field type from integer to int32

  tables=""
  id=0
  idx=1
  sql2=[]
  sql3=[]
  sql5=[]

  for lyr in allData:
     desc = arcpy.Describe(lyr)
     if hasattr(desc, "layer"):
         featureName=os.path.basename(desc.layer.catalogPath)
         inFeaturesGDB=desc.layer.catalogPath.replace("\\","/")
     else:
         featureName=os.path.basename(desc.catalogPath)
         inFeaturesGDB=os.path.dirname(desc.catalogPath).replace("\\","/")

     useGeometry="false"
     lyrtype = "esriDTTable"
     svcType = "Table"
     queryOption="esriRowsTypeNone"
     oidName = desc.OIDFieldName
     if tables=="":
        tables=tables+'"'+featureName+'"'
     else:
        tables=tables+',"'+featureName+'"'
     
     if hasattr(desc,"featureClass"):
         lyrtype = "esriDTFeatureClass"
         useGeometry="true"
         svcType = "Feature Layer"
         queryOption="esriRowsTypeFilter"

     layer={
         "name":lyr.name,
         "id":id+8,
         "layerId":layerIds[lyr.name],
         "tableName":featureName,
         "type":svcType,
         "xssTrustedFields":""

     }
     sql5.append(('UPDATE "GDB_ServiceItems" set "DatasetName"="' + featureName + '" where "ItemId"='+str(layerIds[lyr.name])))
     sqlCreation = "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?"
     c.execute(sqlCreation, (featureName,))
     sql = c.fetchone()[0]
     #printMessage(sql )
     sql5.append(("alter table " + featureName + " rename to " + featureName + "_org"))
     #remove trailing close paren
     sql = sql[:-1]
     #next line is important when doing lookups
     sql = sql.replace(oidName +"integer",oidName + " int32")
     sql = sql.replace("primary key ","")
     sql = sql.replace(" not null","")
     #gdb_transaction_time = 'gdb_transaction_time()'
     #gdb_transaction_time = "strftime('%s', 'now')"
     gdb_transaction_time = "julianday('now')"

     #sql = sql.replace("OBJECTID integer","OBJECTID int32 check(typeof(OBJECTID) = 'integer' and OBJECTID >= -2147483648 and OBJECTID <= 2147483647)")
     #sql = sql.replace("OBJECTID integer","OBJECTID int32 not null")
     #sql = sql.replace("GlobalID uuidtext check(typeof(GlobalID) = 'text' and length(GlobalID) = 38) not null","GlobalID uuidtext check(typeof(GlobalID) = 'text' and length(GlobalID) = 38)")
     sql = sql +", gdb_archive_oid integer primary key not null, gdb_from_date realdate check(typeof(gdb_from_date) = 'real' and gdb_from_date >= 0.0) default ("+gdb_transaction_time  +"), gdb_to_date realdate check(typeof(gdb_to_date) = 'real' and gdb_to_date >= 0.0) default (julianday ('9999-12-31 23:59:59'))) "

     #sql = sql +", gdb_archive_oid integer primary key not null, gdb_from_date realdate check(typeof(gdb_from_date) = 'real' and gdb_from_date >= 0.0), gdb_to_date realdate check(typeof(gdb_to_date) = 'real' and gdb_to_date >= 0.0))"
     #sql = sql +", gdb_archive_oid integer primary key not null, gdb_from_date realdate check(typeof(gdb_from_date) = 'real' and gdb_from_date >= 0.0) not null default (gdb_transaction_time ()), gdb_to_date realdate check(typeof(gdb_to_date) = 'real' and gdb_to_date >= 0.0) not null default (julianday ('9999-12-31 23:59:59')))"
     sql5.append(sql)

     uuid = "(select upper('{' || substr(u,1,8)||'-'||substr(u,9,4)||'-4'||substr(u,13,3)||'-'||v||substr(u,17,3)||'-'||substr(u,21,12)||'}') from (select lower(hex(randomblob(16))) as u, substr('89ab',abs(random()) % 4 + 1, 1) as v))"
     hasAttachments="false"
     hasAttachmentsStr=""
     if arcpy.Exists(inFeaturesGDB+"/"+featureName+"__ATTACH"):
         hasAttachments="true"
         hasAttachmentsStr = "<HasAttachments>"+hasAttachments+"</HasAttachments>"
         layer["attachmentsTableName"]=inFeaturesGDB+"/"+featureName+"__ATTACH"
         layer["attachmentsTableName"]=featureName+"__ATTACH"
         dscfc = arcpy.Describe(inFeaturesGDB+"/"+featureName+"__ATTACH")

         #if dscfc.hasOID == True:
         #    layer["attachmentsPrimaryKey"]=dscfc.OIDFieldName
         #else:
         layer["attachmentsPrimaryKey"]= "GlobalID"


     serviceItems["layers"].append(layer)
     dataSetId='\'||(SELECT ObjectId FROM "GDB_Items" Where Name=\'main.'+featureName+"\')||\'"
     sql1=sql1+ ("<GPSyncDataset xsi:type=''typens:GPSyncDataset''><DatasetID>"+dataSetId+"</DatasetID><DatasetName>"+featureName+"</DatasetName><DatasetType>"+lyrtype+"</DatasetType>"
        "<LayerID>"+str(layerIds[lyr.name])+"</LayerID><LayerName>"+lyr.name+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction><ReplicaServerGen xsi:type=''xs:long''>53052</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen>"
        "<ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen><ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen>"
        "<UseGeometry>"+useGeometry+"</UseGeometry><IncludeRelated>true</IncludeRelated>"
        "<QueryOption>"+queryOption+"</QueryOption>"+hasAttachmentsStr+"</GPSyncDataset>")

     sql2.append(('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
        " select MAX(ObjectID)+1, "+uuid+", '{D86502F9-9758-45C6-9D23-6DD1A0107B47}', '"+featureName+"', '"+featureName.upper()+"', 'MyReplica\\"+featureName+"', '', 1, NULL, NULL, NULL, NULL, NULL, "
        "'<GPSyncDataset xsi:type=''typens:GPSyncDataset'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
        "<DatasetID>"+dataSetId+"</DatasetID>"
        "<DatasetName>"+lyr.name+"</DatasetName>"
        "<DatasetType>"+lyrtype+"</DatasetType><LayerID>"+str(layerIds[lyr.name])+"</LayerID><LayerName>"+lyr.name+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction>"
        "<ReplicaServerGen xsi:type=''xs:long''>53052</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen><ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen>"
        "<ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen>"
        "<UseGeometry>"+useGeometry+"</UseGeometry><IncludeRelated>true</IncludeRelated>"
        "<QueryOption>"+queryOption+"</QueryOption>"+ hasAttachmentsStr+ "</GPSyncDataset>', NULL, NULL, NULL from GDB_Items"))

     sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
         " values('"+featureName + "','gdb_from_date',7,0,NULL,'Archiving from date.',536870912,NULL)"))
     sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
         " values('"+featureName + "','gdb_to_date',7,0,NULL,'Archiving to date.',536870912,NULL)"))
     sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
         " values('"+featureName + "','gdb_archive_oid',2,0,NULL,'Archiving record unique id.',536870912,NULL)"))
     
     #sql5.append(('ALTER TABLE ' + featureName + ' add gdb_archive_oid integer')) # not null'))
     #sql5.append(('ALTER TABLE ' + featureName + ' add gdb_from_date realdate check(typeof(gdb_from_date) = \'real\' and gdb_from_date >= 0.0)')) # not null default (julianday())'))
     #sql5.append(('ALTER TABLE ' + featureName + ' add gdb_to_date realdate check(typeof(gdb_to_date) = \'real\' and gdb_to_date >= 0.0)')) # not null default (julianday (\'9999-12-31 23:59:59\'))'))


     sql5.append(('INSERT INTO "GDB_ItemRelationships"("ObjectID", "UUID", "Type", "OriginID", "DestID", "Properties", "Attributes")'
         'VALUES(' 
         '(select max(OBJECTID) + 1 from "GDB_ItemRelationships"),'+ uuid+','
         '(select UUID from "GDB_ItemRelationshipTypes" where "Name"= \'DatasetOfSyncDataset\' limit 1),'
         '(select UUID from "GDB_Items" where Name="'+featureName+'" limit 1),'
         '(select UUID from "GDB_Items" where Name="main.'+featureName+'" limit 1),'
         '1,NULL)'))

     sql5.append(('INSERT INTO "GDB_ItemRelationships"("ObjectID", "UUID", "Type", "OriginID", "DestID", "Properties", "Attributes") VALUES('
         '(select max(OBJECTID) + 1 from "GDB_ItemRelationships"),'+ uuid+','
         '(select UUID from "GDB_ItemRelationshipTypes" where "Name"=\'DatasetOfSyncDataset\' limit 1),'
         '(select UUID from "GDB_Items" where Name="MyReplica" limit 1),'
         '(select UUID from "GDB_Items" where Name="'+featureName+'" limit 1),'
         '1,NULL)'))
     desc = arcpy.Describe(lyr)
     rels=""
     if desc.relationshipClassNames:
         for name in desc.relationshipClassNames:
            rels = rels + "<Name>main."+name+"</Name>" 
         sql5.append(('UPDATE "GDB_Items" set "Definition"=replace("Definition","<RelationshipClassNames xsi:type=\'typens:Names\'></RelationshipClassNames>",\'<RelationshipClassNames xsi:type="typens:Names">'+rels+'</RelationshipClassNames>\') where "Name"="main.' +featureName+'"'  ) )


     #next_row_id='Next_RowID (NULL,\''+featureName+'\')'
     #next_row_id='(select max(OBJECTID)+1 from \''+featureName+'\')'
     next_row_id='(coalesce (NEW.OBJECTID,(select max(OBJECTID)+1 from \''+featureName+'\'),1)'

     fields=[]
     pre=""
     newFields=""
     allfields=""
     excludes=[oidName,"Shape_Length","Shape_Area"]
     for field in desc.fields:
         if field.name not in excludes:
            newFields = newFields +pre+ "NEW."+field.name
            allfields = allfields +pre+ field.name
            pre=","
            fields.append(field.name)
            #if field.name==depVar + '_calculated':
     
     sql5.append(('CREATE VIEW '+featureName+'_evw AS SELECT '+oidName+','+allfields+' FROM '+featureName + " WHERE gdb_to_date BETWEEN (julianday ('9999-12-31 23:59:59') - 0.000000001) AND (julianday ('9999-12-31 23:59:59') + 0.000000001)"))
      #WHERE gdb_to_date BETWEEN (julianday ('9999-12-31 23:59:59') - 0.000000001) AND (julianday ('9999-12-31 23:59:59') + 0.000000001)
     
     sql5.append(('CREATE TRIGGER '+featureName+'_evw_delete INSTEAD OF DELETE ON '+featureName+'_evw BEGIN '
     'DELETE FROM '+featureName+' WHERE '+oidName+' = OLD.'+oidName+' AND gdb_from_date BETWEEN ('+gdb_transaction_time  +' - 0.000000001) AND ('+gdb_transaction_time  +' + 0.000000001); '
     'UPDATE OR REPLACE '+featureName+' SET gdb_to_date = '+gdb_transaction_time  +' '
     'WHERE '+oidName+' = OLD.'+oidName+' AND gdb_to_date BETWEEN (julianday (\'9999-12-31 23:59:59\') - 0.000000001) AND (julianday (\'9999-12-31 23:59:59\') + 0.000000001); END;'))

     sql5.append(('CREATE TRIGGER '+featureName+'_evw_insert INSTEAD OF INSERT ON '+featureName+'_evw BEGIN '
     'INSERT INTO '+featureName+' ('+oidName+','+allfields+',gdb_from_date,gdb_to_date) '
     'VALUES '+next_row_id+','+newFields+','+gdb_transaction_time  +',julianday (\'9999-12-31 23:59:59\')); END;'))
     
     sql5.append(('CREATE TRIGGER '+featureName+'_evw_update INSTEAD OF UPDATE ON '+featureName+'_evw BEGIN '
     'UPDATE OR IGNORE '+featureName+' SET gdb_to_date = '+gdb_transaction_time  +' '
     'WHERE '+oidName+' = OLD.'+oidName+' AND gdb_to_date BETWEEN (julianday (\'9999-12-31 23:59:59\') - 0.000000001) AND (julianday (\'9999-12-31 23:59:59\') + 0.000000001);'
     'REPLACE INTO '+featureName+' ('+oidName+','+allfields+',gdb_from_date,gdb_to_date) '
     'VALUES (NEW.'+oidName+','+newFields+',(SELECT MAX (gdb_to_date) FROM '+featureName+' '
     'WHERE '+oidName+' = OLD.'+oidName+' AND gdb_to_date < julianday (\'9999-12-31 23:59:59\')),julianday (\'9999-12-31 23:59:59\')); END;'))

     sql5.append(("insert into " + featureName + "("+oidName+","+allfields+") select "+oidName+","+allfields+" from "+featureName + "_org"))
     sql5.append(("drop table "+featureName + "_org"))
     
     sql5.append(("CREATE INDEX gdb_ct4_"+str(idx)+" ON "+featureName+" ("+oidName+",gdb_from_date) "))
     sql5.append(("CREATE INDEX gdb_ct1_"+str(idx)+" ON "+featureName+" (gdb_from_date,gdb_to_date) "))
     sql5.append(("CREATE INDEX r"+str(idx)+"_gdb_xpk ON "+featureName+" ("+oidName+",gdb_to_date) "))

     #if desc.hasOID:
     #              feature_json['objectIdField']=desc.OIDFieldName
     #              feature_json['objectIdFieldName']=desc.OIDFieldName
     #feature_json['globalIdField'] = desc.globalIDFieldName
     #feature_json['globalIdFieldName']=desc.globalIDFieldName
     if desc.hasGlobalID:
         sql5.append(("CREATE INDEX UUID"+str(idx)+" ON "+featureName+" ("+desc.globalIDFieldName+") "))
     joinField = ""
     if desc.relationshipClassNames:
                  for j,rel in enumerate(desc.relationshipClassNames):
                    relDesc = arcpy.Describe(desc.path +"/"+rel)
                    for i in relDesc.originClassKeys:
                        #if i[1]=="OriginPrimary":
                        if i[1]=="OriginForeign":
                            joinField=i[0]
      
     if joinField in fields:
         sql5.append(("CREATE INDEX GDB_"+str(idx)+"_" + joinField + " ON "+featureName+" ("+joinField+") "))

     #need to add triggers for editing spatial layers
     if svcType!="Table":
         sql5.append(('CREATE TRIGGER "st_delete_trigger_'+featureName+'_SHAPE" AFTER DELETE ON '+featureName+' FOR EACH ROW BEGIN '
         'DELETE FROM "st_spindex__'+featureName+'_SHAPE" WHERE pkid = OLD._ROWID_; END'))
         sql5.append(('CREATE TRIGGER "st_insert_trigger_'+featureName+'_SHAPE" AFTER INSERT ON '+featureName+' FOR EACH ROW BEGIN '
         'SELECT InsertIndexEntry ("st_spindex__'+featureName+'_SHAPE",NEW.SHAPE,NEW._ROWID_,2); END'))
         sql5.append(('CREATE TRIGGER "st_update1_trigger_'+featureName+'_SHAPE" AFTER UPDATE OF SHAPE ON '+featureName+' WHEN OLD._ROWID_ != NEW._ROWID_ BEGIN '
         'DELETE FROM "st_spindex__'+featureName+'_SHAPE" WHERE pkid = OLD._ROWID_; SELECT UpdateIndexEntry ("st_spindex__'+featureName+'_SHAPE",NEW.SHAPE,NEW._ROWID_,2); END'))
         sql5.append(('CREATE TRIGGER "st_update_trigger_'+featureName+'_SHAPE" AFTER UPDATE OF SHAPE ON '+featureName+' WHEN OLD._ROWID_ = NEW._ROWID_ BEGIN '
         'SELECT UpdateIndexEntry ("st_spindex__'+featureName+'_SHAPE",NEW.SHAPE,NEW._ROWID_,2); END'))
         sql5.append(('UPDATE "GDB_TableRegistry" set object_flags=278535 where table_name=\''+featureName+"'"))
     else:
         sql5.append(('UPDATE "GDB_TableRegistry" set object_flags=262147 where table_name=\''+featureName+"'"))

     #printMessage("Loading " + lyr.name)
     #now process any attachment tables
     #OBS! The order of fields in these tables is important!!!
     if arcpy.Exists(inFeaturesGDB+"/"+featureName+"__ATTACH"):
        pre=""
        newFields=""
        allfields=""
        newallfields=""
        globalField = featureName+"_GlobalID"
        correct_field_order=["ATTACHMENTID","GLOBALID","REL_GLOBALID","CONTENT_TYPE","ATT_NAME","DATA_SIZE","DATA","gdb_archive_oid","gdb_from_date","gdb_to_date"]

        # elif field.type == 'Guid':
        #   fieldInfos['type']='esriFieldTypeGUID'
        #elif field.type == 'GlobalID':

        desc = arcpy.Describe(inFeaturesGDB+"/"+featureName+"__ATTACH")
        oidName = desc.OIDFieldName
        excludes=[oidName,"Shape_Length","Shape_Area"]
        for field in desc.fields:
           if field.type == 'Guid':
               globalField = field.name
           if field.name not in excludes:
              newFields = newFields +pre+ "NEW."+field.name
              allfields = allfields +pre+ field.name
              newallfields = newallfields + pre + field.name
              pre=","
         
        
        idx=idx+1
        lyrtype="esriDTTable"
        queryOption="esriRowsTypeFilter"
        dataSetId='\'||(SELECT ObjectId FROM "GDB_Items" Where Name=\'main.'+featureName+"__ATTACH"+"\')||\'"
        printMessage("Found attachment table: " + featureName+"__ATTACH")
        sql1=sql1+ ("<GPSyncDataset xsi:type=''typens:GPSyncDataset''><DatasetID>"+dataSetId+"</DatasetID><DatasetName>"+featureName+"__ATTACH"+"</DatasetName><DatasetType>"+lyrtype+"</DatasetType>"
        "<LayerID>"+str(layerIds[featureName+"__ATTACH"])+"</LayerID><LayerName>"+lyr.name+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction><ReplicaServerGen xsi:type=''xs:long''>53052</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen>"
        "<ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen><ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen>"
        "<UseGeometry>false</UseGeometry><IncludeRelated>false</IncludeRelated>"
        "<QueryOption>"+queryOption+"</QueryOption><IsAttachment>true</IsAttachment></GPSyncDataset>")

        sql3.append(('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
        " select MAX(ObjectID)+1, "+uuid+", '{D86502F9-9758-45C6-9D23-6DD1A0107B47}', '"+featureName+"__ATTACH', '"+featureName.upper()+"__ATTACH', 'MyReplica\\"+featureName+"__ATTACH', '', 1, NULL, NULL, NULL, NULL, NULL, "
        "'<GPSyncDataset xsi:type=''typens:GPSyncDataset'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
        "<DatasetID>"+dataSetId+"</DatasetID>"
        "<DatasetName>"+featureName+"__ATTACH</DatasetName><DatasetType>"+lyrtype+"</DatasetType><LayerID>"+str(layerIds[featureName])+"</LayerID><LayerName>"+featureName+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction>"
        "<ReplicaServerGen xsi:type=''xs:long''>53052</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen><ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen>"
        "<ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen>"
        "<UseGeometry>false</UseGeometry><IncludeRelated>false</IncludeRelated><QueryOption>"+queryOption+"</QueryOption>"
        "<IsAttachment>true</IsAttachment></GPSyncDataset>',"
        " NULL, NULL, NULL from GDB_Items"))
        sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
            " values('"+featureName + "__ATTACH','gdb_from_date',7,0,NULL,'Archiving from date.',536870912,NULL)"))
        sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
            " values('"+featureName + "__ATTACH','gdb_to_date',7,0,NULL,'Archiving to date.',536870912,NULL)"))
        sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
            " values('"+featureName + "__ATTACH','gdb_archive_oid',2,0,NULL,'Archiving record unique id.',536870912,NULL)"))

        #sql5.append(('ALTER TABLE ' + featureName + '__ATTACH add gdb_archive_oid integer')) # not null'))
        #sql5.append(('ALTER TABLE ' + featureName + '__ATTACH add gdb_from_date realdate check(typeof(gdb_from_date) = \'real\' and gdb_from_date >= 0.0)')) #not null default (julianday())'))
        #sql5.append(('ALTER TABLE ' + featureName + '__ATTACH add gdb_to_date realdate check(typeof(gdb_to_date) = \'real\' and gdb_to_date >= 0.0)')) # not null default (julianday (\'9999-12-31 23:59:59\'))'))

        #sql5.append(('INSERT INTO GDB_ColumnRegistry("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
        #    " values('"+featureName + "__ATTACH','REL_GLOBALID',12,38,NULL,NULL,0,NULL)"))

        sql5.append(("UPDATE GDB_ColumnRegistry set column_name='REL_GLOBALID' where column_name='"+globalField+"' and table_name='"+featureName+"__ATTACH'"))
        sql5.append(("UPDATE GDB_ColumnRegistry set column_name='GLOBALID' where column_name='GlobalID' and table_name='"+featureName+"__ATTACH'"))
        sql5.append(("DELETE FROM GDB_ColumnRegistry where column_name='REL_OBJECTID' and table_name='"+featureName+"__ATTACH'"))
        
        #sql5.append(("UPDATE GDB_ColumnRegistry set column_name='GLOBALID' where column_name='GlobalID'"))
        #("table_name", "column_name", "sde_type", "column_size", "decimal_digits", "description", "object_flags", "object_id")'
        #   " values('"+featureName + "__ATTACH','REL_GLOBALID',12,38,NULL,NULL,0,NULL)"))

        sql5.append(('INSERT INTO "GDB_ItemRelationships"("ObjectID", "UUID", "Type", "OriginID", "DestID", "Properties", "Attributes")'
           'VALUES(' 
           '(select max(OBJECTID) + 1 from "GDB_ItemRelationships"),'+ uuid+','
           '(select UUID from "GDB_ItemRelationshipTypes" where "Name"= \'DatasetOfSyncDataset\' limit 1),'
           '(select UUID from "GDB_Items" where Name="'+featureName+'__ATTACH" limit 1),'
           '(select UUID from "GDB_Items" where Name="main.'+featureName+'__ATTACH" limit 1),'
           '1,NULL)'))
        sql5.append(('INSERT INTO "GDB_ItemRelationships"("ObjectID", "UUID", "Type", "OriginID", "DestID", "Properties", "Attributes") VALUES('
           '(select max(OBJECTID) + 1 from "GDB_ItemRelationships"),'+ uuid+','           
           '(select UUID from "GDB_ItemRelationshipTypes" where "Name"=\'DatasetOfSyncDataset\' limit 1),'
           '(select UUID from "GDB_Items" where Name="MyReplica" limit 1),'
           '(select UUID from "GDB_Items" where Name="'+featureName+'__ATTACH" limit 1),'
           '1,NULL)'))
        
        #set table flag
        sql5.append(('UPDATE "GDB_TableRegistry" set object_flags=262147 where table_name="'+featureName+'__ATTACH"'))
        #replace old GlobalId 
        #sql5.append(('UPDATE "GDB_Items" set "Definition"=replace("Definition",\'<ObjectKeyName>'+ featureName +'_GlobalID</ObjectKeyName>\',\'<ObjectKeyName>GlobalID</ObjectKeyName>\') where "Name"=\'main.'+featureName+'__ATTACHREL\''))
        sql5.append(('UPDATE "GDB_Items" set "Definition"=replace("Definition",\'<ObjectKeyName>'+ globalField +'</ObjectKeyName>\',\'<ObjectKeyName>REL_GLOBALID</ObjectKeyName>\') where "Name"=\'main.'+featureName+'__ATTACHREL\''))

        rels=""
        if desc.relationshipClassNames:
            for name in desc.relationshipClassNames:
              rels = rels + "<Name>main."+name+"</Name>" 
            sql5.append(('UPDATE "GDB_Items" set "Definition"=replace("Definition","<RelationshipClassNames xsi:type=\'typens:Names\'></RelationshipClassNames>",\'<RelationshipClassNames xsi:type="typens:Names">'+rels+'</RelationshipClassNames>\') where "Name"="main.' +featureName+'__ATTACH"'  ) )

        sql5.append(('UPDATE "GDB_Items" set "Definition"=replace("Definition","<Name>REL_OBJECTID</Name><ModelName>REL_OBJECTID</ModelName><FieldType>esriFieldTypeInteger</FieldType><IsNullable>true</IsNullable>","<Name>REL_GLOBALID</Name><ModelName>REL_GLOBALID</ModelName><FieldType>esriFieldTypeGUID</FieldType><IsNullable>false</IsNullable>") where "Name"="main.' +featureName+'__ATTACH"'  ))

        #allfields="ATTACHMENTID,GLOBALID,REL_GLOBALID,CONTENT_TYPE,ATT_NAME,DATA_SIZE,DATA"
        #newFields="NEW.ATTACHMENTID,NEW.GLOBALID,NEW.REL_GLOBALID,NEW.CONTENT_TYPE,NEW.ATT_NAME,NEW.DATA_SIZE,NEW.DATA"
        sql5.append(("alter table " + featureName +"__ATTACH rename to " + featureName + "__ATTACH_org"))
        newallfields = newallfields.replace(globalField, "REL_GLOBALID")
        newallfields = newallfields.replace("GlobalID", "GLOBALID")
        newallfields = newallfields.replace("REL_OBJECTID,", "")
   
        newFields = newFields.replace(globalField, "REL_GLOBALID")
        #newFields = newFields.replace("GlobalID","GLOBALID")
        newFields = newFields.replace("NEW.GlobalID", uuid)
        newFields = newFields.replace("NEW.REL_OBJECTID,", "")
        newFields = newFields.replace("NEW.ATTACHMENTID,", "")
        #just hardcode the fields
        newallfields = "ATTACHMENTID,GLOBALID,REL_GLOBALID,CONTENT_TYPE,ATT_NAME,DATA_SIZE,DATA"
        newFields = "NEW.GLOBALID,NEW.REL_GLOBALID,NEW.CONTENT_TYPE,NEW.ATT_NAME,NEW.DATA_SIZE,NEW.DATA"
        allfields = "ATTACHMENTID,GLOBALID,REL_GLOBALID,CONTENT_TYPE,ATT_NAME,DATA_SIZE,DATA"
        #,julianday('now'),julianday ('9999-12-31 23:59:59')
   
        allfields = allfields.replace("REL_OBJECTID,", "")

        if False:
           sqlCreation = "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?"
           c.execute(sqlCreation, (featureName + "__ATTACH",))
           sql = c.fetchone()[0]
           #printMessage(sql)
           #remove trailing close paren
           sql = sql[:-1]
           sql = sql.replace("primary key ", "")
           sql = sql.replace(" not null", "")
           #sql = sql.replace("REL_OBJECTID int32 check((typeof(REL_OBJECTID) = 'integer' or typeof(REL_OBJECTID) = 'null') and REL_OBJECTID >= -2147483648 and REL_OBJECTID <= 2147483647),","")
   
           sql = sql.replace(globalField, "REL_GLOBALID")
           sql = sql.replace("GlobalID", "GLOBALID")
           sql = sql.replace("ATTACHMENTID integer",
                             "ATTACHMENTID int32 constraint attachementidcheck  check(typeof(ATTACHMENTID) = 'integer' and ATTACHMENTID >= -2147483648 and ATTACHMENTID <= 2147483647) not null")
   
           #newallfields = newallfields.replace("REL_OBJECTID,","")
   
           gdb_transaction_time = 'gdb_transaction_time()'
           gdb_transaction_time = "strftime('%s', 'now')"
           gdb_transaction_time = "julianday('now')"
   
           #oidName = desc.OIDFieldName
           #sql = sql.replace("GlobalID uuidtext check(typeof(GlobalID) = 'text' and length(GlobalID) = 38) not null","GlobalID uuidtext check(typeof(GlobalID) = 'text' and length(GlobalID) = 38)")
           sql = sql + ", gdb_archive_oid integer primary key not null, gdb_from_date realdate constraint gdbfromdatecheck check(typeof(gdb_from_date) = 'real' and gdb_from_date >= 0.0) default (" + \
               gdb_transaction_time + \
               "),gdb_to_date realdate constraint gdbtodatecheck  check(typeof(gdb_to_date) = 'real' and gdb_to_date >= 0.0) default (julianday ('9999-12-31 23:59:59'))) "
   
           #sql = sql +", gdb_archive_oid integer primary key not null, gdb_from_date realdate check(typeof(gdb_from_date) = 'real' and gdb_from_date >= 0.0) not null default (gdb_transaction_time ()), gdb_to_date realdate check(typeof(gdb_to_date) = 'real' and gdb_to_date >= 0.0) not null default         (julianday ('9999-12-31 23:59:59')))"

        #just create the dang table
        sql5.append(("CREATE TABLE "+featureName+"__ATTACH ( ATTACHMENTID int32 constraint attachementidcheck check(typeof(ATTACHMENTID) = 'integer' and ATTACHMENTID >= -2147483648 and ATTACHMENTID <= 2147483647) not null,        GLOBALID uuidtext constraint globalidcheck check(typeof(GLOBALID) = 'text' and length(GLOBALID) = 38), REL_GLOBALID uuidtext constraint relglobalidcheck check((typeof(REL_GLOBALID) = 'text' or typeof(REL_GLOBALID) = 'null') and length(REL_GLOBALID) = 38),         CONTENT_TYPE text(150) constraint contexttypecheck  check(typeof(CONTENT_TYPE) = 'text' and not length(CONTENT_TYPE) > 150), ATT_NAME text(250) constraint attnamecheck  check(typeof(ATT_NAME) = 'text' and not length(ATT_NAME) > 250), DATA_SIZE int32 constraint datasizecheck check(typeof(DATA_SIZE) = 'integer' and DATA_SIZE >= -2147483648 and DATA_SIZE <= 2147483647), DATA blob constraint datablobcheck check(typeof(DATA) = 'blob' or typeof(DATA) = 'null'),  gdb_archive_oid integer primary key not null, gdb_from_date realdate constraint gdbfromdatecheck check(typeof(gdb_from_date) = 'real' and gdb_from_date >= 0.0) default (julianday('now')), gdb_to_date realdate constraint gdbtodatecheck check(typeof(gdb_to_date) = 'real' and gdb_to_date >= 0.0) default (julianday ('9999-12-31 23:59:59')))"))

        #sql5.append(("insert into " + featureName + "__ATTACH("+newallfields+") select "+allfields+" from "+featureName + "__ATTACH_org"))
        
        sql5.append(("drop table "+featureName + "__ATTACH_org")) 

        #sql5.append(('ALTER TABLE '+featureName+'__ATTACH ADD REL_GLOBALID uuidtext'))
        #next_row_id='Next_RowID (NULL,\''+featureName+'__ATTACH\')'
        #next_row_id='(select max(rowid)+1 from \''+featureName+'__ATTACH\')'
        next_row_id='(coalesce (NEW.ATTACHMENTID,(select max(ATTACHMENTID)+1 from \''+featureName+'__ATTACH\'),1))'

        sql5.append(("CREATE INDEX gdb_ct4_"+str(idx)+" ON "+featureName+"__ATTACH (ATTACHMENTID,gdb_from_date) "))
        sql5.append(("CREATE INDEX gdb_ct1_"+str(idx)+" ON "+featureName+"__ATTACH (gdb_from_date,gdb_to_date) "))
        sql5.append(("CREATE INDEX r"+str(idx)+"_gdb_xpk ON "+featureName+"__ATTACH (ATTACHMENTID,gdb_to_date) "))
        #sql5.append(("CREATE INDEX GDB_"+str(idx)+"_GlobalGUID ON "+featureName+"__ATTACH (GlobalGUID) "))
        sql5.append(("CREATE INDEX UUID"+str(idx)+" ON "+featureName+"__ATTACH (REL_GLOBALID) "))

        sql5.append(('CREATE VIEW '+featureName+'__ATTACH_evw AS SELECT '+newallfields+' FROM '+featureName+"__ATTACH WHERE gdb_to_date BETWEEN (julianday ('9999-12-31 23:59:59') - 0.000000001) AND (julianday ('9999-12-31 23:59:59') + 0.000000001)"))

        sql5.append(('CREATE TRIGGER '+featureName+'__ATTACH_evw_delete INSTEAD OF DELETE ON '+featureName+'__ATTACH_evw BEGIN '
        'DELETE FROM '+featureName+'__ATTACH '
        'WHERE ATTACHMENTID = OLD.ATTACHMENTID AND gdb_from_date BETWEEN ('+gdb_transaction_time  +' - 0.000000001) AND ('+gdb_transaction_time  +' + 0.000000001); '
        'UPDATE OR REPLACE '+featureName+'__ATTACH SET gdb_to_date = '+gdb_transaction_time  +' '
        'WHERE ATTACHMENTID = OLD.ATTACHMENTID AND gdb_to_date BETWEEN (julianday (\'9999-12-31 23:59:59\') - 0.000000001) AND (julianday (\'9999-12-31 23:59:59\') + 0.000000001); END;'))

        sql5.append(('CREATE TRIGGER '+featureName+'__ATTACH_evw_insert INSTEAD OF INSERT ON '+featureName+'__ATTACH_evw BEGIN '
        'INSERT INTO '+featureName+'__ATTACH ('+newallfields+',gdb_from_date,gdb_to_date) '
        #'INSERT INTO '+featureName+'__ATTACH ('+newallfields+',gdb_archive_oid,gdb_from_date,gdb_to_date) '
        'VALUES ('+next_row_id+','+newFields+','+gdb_transaction_time  +',julianday (\'9999-12-31 23:59:59\')); END;'))
        #do I need to include the gdb_archive_oid?
        #'VALUES ('+next_row_id+','+newFields+','+next_row_id+','+gdb_transaction_time  +',julianday (\'9999-12-31 23:59:59\')); END;'))

        sql5.append(('CREATE TRIGGER '+featureName+'__ATTACH_evw_update INSTEAD OF UPDATE ON '+featureName+'__ATTACH_evw BEGIN '
        'UPDATE OR IGNORE '+featureName+'__ATTACH SET gdb_to_date = '+gdb_transaction_time  +' '
        'WHERE ATTACHMENT = OLD.ATTACHMENTID AND gdb_to_date BETWEEN (julianday (\'9999-12-31 23:59:59\') - 0.000000001) AND (julianday (\'9999-12-31 23:59:59\') + 0.000000001);'
        'REPLACE INTO '+featureName+'__ATTACH ('+newallfields+',gdb_from_date,gdb_to_date) '
        'VALUES (NEW.ATTACHMENTID,'+newFields+',(SELECT MAX (gdb_to_date) FROM '+featureName+'__ATTACH '
        'WHERE ATTACHMENTID = OLD.ATTACHMENTID AND gdb_to_date < julianday (\'9999-12-31 23:59:59\')),julianday (\'9999-12-31 23:59:59\')); END;'))

     id = id + 1
     idx=idx+1

  conn.close()
  #sql3=('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
  #" select MAX(ObjectID)+1, '{55C5E7E4-834D-4D44-A12C-991E7F8B4645}', '{D86502F9-9758-45C6-9D23-6DD1A0107B47}', '"+layerName+"__ATTACH', '"+layerName.upper()+"__ATTACH', 'MyReplica_"+str(id)+"\\"+layerName+"__ATTACH', '', 1, NULL, NULL, NULL, NULL, NULL, "
  #"'<GPSyncDataset xsi:type=''typens:GPSyncDataset'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
  #"<DatasetID>6</DatasetID>"
  #"<DatasetName>"+layerName+"__ATTACH</DatasetName><DatasetType>esriDTTable</DatasetType><LayerID>0</LayerID><LayerName>"+layerName+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction>"
  #"<ReplicaServerGen xsi:type=''xs:long''>2590</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen><ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen>"
  #"<ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen><UseGeometry>true</UseGeometry><IncludeRelated>false</IncludeRelated><QueryOption>esriRowsTypeFilter</QueryOption>"
  #"<IsAttachment>true</IsAttachment></GPSyncDataset>',"
  #" NULL, NULL, NULL from GDB_Items")

  sql4='update "GDB_ServiceItems" set "ItemInfo"=replace("ItemInfo",|"capabilities":"Query"|,|"capabilities":"Create,Delete,Query,Update,Editing,Sync"|);'
  sql4=sql4.replace("|","'")

  serviceItemsStr = json.dumps(serviceItems)
  sql5.append(('insert into "GDB_ServiceItems"("OBJECTID", "DatasetName", "ItemType", "ItemId", "ItemInfo", "AdvancedDrawingInfo")'
     'values((select max(OBJECTID)+1 from "GDB_ServiceItems"),\''+serviceName+'\',0,-1,\''+serviceItemsStr+'\',NULL)'))

  sql5.append(('update "GDB_Items" set Definition=replace(Definition,\'<ChangeTracked>false</ChangeTracked>\',\'<ChangeTracked>true</ChangeTracked>\') where "Name" !=\'main.'+featureName+'__ATTACHREL\''))

  sql5.append(('update "GDB_ServiceItems" set "ItemInfo" = replace("ItemInfo",\'Create,Delete,Query,Update,Editing\',\'Create,Delete,Query,Update,Editing,Sync\') where "ItemInfo" like \'%Create,Delete,Query,Update,Editing"%\''))
  sql5.append(('update "GDB_ServiceItems" set "ItemInfo"=replace("ItemInfo",\'"hasAttachments":true\',\'"hasAttachments":true,"attachmentProperties":[{"name":"name","isEnabled":true},{"name":"size","isEnabled":true},{"name":"contentType","isEnabled":true},{"name":"keywords","isEnabled":true}]\')'))
  #sql5.append(('update "GDB_ServiceItems" set "ItemInfo"=replace("ItemInfo",\'"advancedQueryCapabilities":{\',\'"supportsCalculate":true,"supportsTruncate":false,"supportsAttachmentsByUploadId":true,"supportsValidateSql":true,"supportsCoordinatesQuantization":true,"supportsApplyEditsWithGlobalIds":true,"useStandardizedQueries":false,"allowGeometryUpdates":true,"advancedQueryCapabilities":{"supportsQueryRelatedPagination":true,"supportsQueryWithResultType":true,"supportsSqlExpression":true,"supportsAdvancedQueryRelated":true,"supportsQueryAttachments":true,"supportsReturningGeometryCentroid":false,\')'))
  #sql5.append(('UPDATE "GDB_ServiceItems" set "DatasetName"="' + featureName + '" where "ItemId"='+datasetId))
  
  #sql5='update "GDB_Items" set ObjectId=ROWID'
  sql5.append(('update "GDB_ColumnRegistry" set object_flags=4 where table_name=\'GDB_ServiceItems\' and column_name in(\'DatasetName\',\'ItemType\',\'ItemId\',\'ItemInfo\')'))

  sql1=sql1+("</GPSyncDatasets><AttachmentsSyncDirection>esriAttachmentsSyncDirectionBidirectional</AttachmentsSyncDirection></GPSyncReplica>'"
   ", NULL, NULL, NULL from GDB_Items;")

  sql5.append(('PRAGMA writable_schema=ON;'))
  sql5.append(('delete FROM sqlite_master where type=\'trigger\' and name like \'%_Shape\''))
  sql5.append(('PRAGMA writable_schema=OFF;'))

  #sql1=sql1+("#PRAGMA writable_schema=ON;update sqlite_master set sql=replace(sql,'OBJECTID integer','OBJECTID int32') where name in ("+tables+") and type='table';#PRAGMA writable_schema=OFF;")
  #serviceRep=[sql1,sql2,sql4]
  #NON_OPTIMIZE_SIZE"
  name=replicaDestinationPath + "/"+serviceName+".sql"
  with open(name,'w') as f:
       f.write("SELECT load_extension( 'stgeometry_sqlite.dll', 'SDE_SQL_funcs_init');\n")
       #not sure here - use wal or not?
       #f.write("PRAGMA journal_mode=WAL;\n")

       #f.write(";\n")

       f.write(sql1)
       f.write(";\n")

       for i in sql2:
          f.write(i)
          f.write(";\n")

       for i in sql3:
          f.write(i)
          f.write(";\n")

       f.write(";\n")
       for i in sql5:
          f.write(i)
          f.write(";\n")

       f.write(sql4)
       f.close()
  #printMessage("Running \"" + toolkitPath+"/spatialite/spatialite.exe\" \"" + newFullReplicaDB + "\"  < " + name)
  #printMessage("Running \"" + spatialite_path+ "\" \"" + newFullReplicaDB + "\"  < \"" + name + "\"")
  cmd = "\"" + spatialite_path+"\"  \"" + newFullReplicaDB + "\"  < \"" + name + "\" >>\"" + replicaDestinationPath + os.sep + serviceName + ".log\" 2>&1"
  try:
     #os.system("\"" + spatialite_path+"\"  \"" + newFullReplicaDB + "\"  < \"" + name + "\" >>" + replicaDestinationPath + os.sep + serviceName + ".log 2>&1")
     result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
  except Exception, e:
     printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)
  
#create a replica sqlite database for a single layer/table
def createSingleReplica(templatePath,df,lyr,replicaDestinationPath,toolkitPath,feature_json,serverName,serviceName,username,id):
  global spatialite_path
    
  blankmxd = arcpy.mapping.MapDocument(templatePath + "/blank.mxd")
  df = arcpy.mapping.ListDataFrames(blankmxd)[0]
  arcpy.mapping.AddLayer(df, lyr)

  tmpMxd=templatePath+"/temp.mxd"
  if os.path.exists(tmpMxd):
     os.remove(tmpMxd)

  blankmxd.saveACopy(tmpMxd)
  #mxd.save()
  desc=arcpy.Describe(lyr)

  saveReplica(tmpMxd,replicaDestinationPath + "/"+lyr.name,lyr,desc)
  #move to root folder and delete the "data" folder
  filenames = next(os.walk(replicaDestinationPath + "/"+lyr.name+"/data/"))[2]
  printMessage("Renamed " + replicaDestinationPath + "/"+lyr.name+"/data/"+filenames[0]+" to "+ replicaDestinationPath+"/"+lyr.name+".geodatabase")
  #if offline geodatabase exists, must delete first
  newReplicaDB=replicaDestinationPath+"/"+lyr.name+".geodatabase"
  try:
     if os.path.exists(newReplicaDB):
        os.rmdir(newReplicaDB)
  except:
     printMessage("Unable to remove old replica geodatabase")

  os.rename(replicaDestinationPath + "/"+lyr.name+"/data/"+filenames[0], newReplicaDB)
  try:
     os.rmdir(replicaDestinationPath + "/"+lyr.name+"/data/")
     os.rmdir(replicaDestinationPath + "/"+lyr.name)
  except:
     printMessage("Unable to remove replica folders")
  #if os.path.exists(tmpMxd):
  #   os.remove(tmpMxd)
  #sqliteDb=replicaDestinationPath + "/"+lyr.name+"/data/"+serviceName+".geodatabase"
  #sqliteDb=replicaDestinationPath + "/"+lyr.name+".geodatabase"

  serviceRep=[]
  if os.path.exists(newReplicaDB):
     #dom = parse(templatePath+"/replica.xml")
     #xml = createXML(dom,serverName,serviceName,lyr.name):
     ret=updateReplicaPaths(newReplicaDB,lyr.name,feature_json,"http://"+serverName + "/arcgis/rest/services/"+serviceName+"/FeatureServer",serverName,serviceName,username,id)
     ret1 = updateReplicaPaths(newReplicaDB,lyr.name,feature_json,"http://"+serverName + "/arcgis/rest/services/"+serviceName+"/FeatureServer",serverName,serviceName,username,id)

     for i in ret1:
        serviceRep.append(i)

     name=replicaDestinationPath + os.sep + lyr.name+".sql"
     with open(name,'w') as f:
          f.write("SELECT load_extension( 'stgeometry_sqlite.dll', 'SDE_SQL_funcs_init');\n")
          for i in ret:
             f.write(i)
             f.write(";\n")

          f.close()
     #printMessage("Running \"" + spatialite_path + "\" \""+ newReplicaDB + "\"  < \"" + name + "\"")
     cmd="\"" + spatialite_path + "\" \"" + newReplicaDB + "\"  < \"" + name + "\" >> \"" + replicaDestinationPath + os.sep + lyr.name + ".log\" 2>&1"
     try:
        #os.system("\"" + spatialite_path + "\" \"" + newReplicaDB + "\"  < \"" + name + "\" >> \"" + replicaDestinationPath + os.sep + lyr.name + ".log\" 2>&1")
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
     except Exception, e:
        printMessage("Unable to run sql commands:  "+e)


def saveReplica(tmpMxd,replicaPath,lyr,desc):
   arcpy.CreateRuntimeContent_management(tmpMxd,
      replicaPath,
      lyr.name,"#","#",
      "FEATURE_AND_TABULAR_DATA","NON_OPTIMIZE_SIZE","ONLINE","PNG","1","#")
   printMessage("Saved replica: "+ replicaPath)

def updateReplicaPaths(replicaPath,layerName,feature_json,servicePath,serverName,serviceName,username,id):
   minx=str(feature_json['extent']['xmin'])
   miny=str(feature_json['extent']['ymin'])
   maxx=str(feature_json['extent']['xmax'])
   maxy=str(feature_json['extent']['ymax'])

   sql1=('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
    " select MAX(ObjectID)+1, '{7B6EB064-7BF6-42C8-A116-2E89CD24A000}', '{5B966567-FB87-4DDE-938B-B4B37423539D}', 'MyReplica', 'MYREPLICA', 'MyReplica', '', 1, NULL, NULL, NULL, "
    "'http://"+serverName+"/arcgis/rest/services/"+serviceName+"/FeatureServer', '"+username+"',"
    "'<GPSyncReplica xsi:type=''typens:GPSyncReplica'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
    "<ReplicaName>MyReplica</ReplicaName><ID>"+str(id)+"</ID><ReplicaID>{7b6eb064-7bf6-42c8-a116-2e89cd24a000}</ReplicaID>"
    "<ServiceName>http://"+serverName+"/arcgis/rest/services/"+serviceName+"/FeatureServer</ServiceName>"
    "<Owner>"+username+"</Owner>"
    "<Role>esriReplicaRoleChild</Role><SyncModel>esriSyncModelPerLayer</SyncModel><Direction>esriSyncDirectionBidirectional</Direction><CreationDate>2015-09-02T13:48:33</CreationDate><LastSyncDate>1970-01-01T00:00:01</LastSyncDate>"
    "<ReturnsAttachments>true</ReturnsAttachments><SpatialRelation>esriSpatialRelIntersects</SpatialRelation><QueryGeometry xsi:type=''typens:PolygonN''><HasID>false</HasID><HasZ>false</HasZ><HasM>false</HasM><Extent xsi:type=''typens:EnvelopeN''>"
    "<XMin>"+minx+"</XMin><YMin>"+miny+"</YMin><XMax>"+maxx+"</XMax><YMax>"+maxy+"</YMax></Extent><RingArray xsi:type=''typens:ArrayOfRing''><Ring xsi:type=''typens:Ring''>"
    "<PointArray xsi:type=''typens:ArrayOfPoint''>"
    "<Point xsi:type=''typens:PointN''><X>"+minx+"</X><Y>"+miny+"</Y></Point><Point xsi:type=''typens:PointN''><X>"+maxx+"</X><Y>"+miny+"</Y></Point>"
    "<Point xsi:type=''typens:PointN''><X>"+maxx+"</X><Y>"+maxy+"</Y></Point><Point xsi:type=''typens:PointN''><X>"+minx+"</X><Y>"+maxy+"</Y></Point>"
    "<Point xsi:type=''typens:PointN''><X>"+minx+"</X><Y>"+miny+"</Y></Point></PointArray></Ring></RingArray>"
    "<SpatialReference xsi:type=''typens:ProjectedCoordinateSystem''><WKT>PROJCS[&quot;WGS_1984_Web_Mercator_Auxiliary_Sphere&quot;,GEOGCS[&quot;GCS_WGS_1984&quot;,DATUM[&quot;D_WGS_1984&quot;,SPHEROID[&quot;WGS_1984&quot;,6378137.0,298.257223563]],PRIMEM[&quot;Greenwich&quot;,0.0],UNIT[&quot;Degree&quot;,0.0174532925199433]],PROJECTION[&quot;Mercator_Auxiliary_Sphere&quot;],PARAMETER[&quot;False_Easting&quot;,0.0],PARAMETER[&quot;False_Northing&quot;,0.0],PARAMETER[&quot;Central_Meridian&quot;,0.0],PARAMETER[&quot;Standard_Parallel_1&quot;,0.0],PARAMETER[&quot;Auxiliary_Sphere_Type&quot;,0.0],UNIT[&quot;Meter&quot;,1.0],AUTHORITY[&quot;EPSG&quot;,3857]]</WKT><XOrigin>-20037700</XOrigin><YOrigin>-30241100</YOrigin><XYScale>10000</XYScale><ZOrigin>-100000</ZOrigin><ZScale>10000</ZScale><MOrigin>-100000</MOrigin><MScale>10000</MScale><XYTolerance>0.001</XYTolerance><ZTolerance>0.001</ZTolerance><MTolerance>0.001</MTolerance><HighPrecision>true</HighPrecision><WKID>102100</WKID><LatestWKID>3857</LatestWKID></SpatialReference></QueryGeometry>"

    "<GPSyncDatasets xsi:type=''typens:ArrayOfGPSyncDataset''>"
    "<GPSyncDataset xsi:type=''typens:GPSyncDataset''><DatasetID>5</DatasetID><DatasetName>"+layerName+"</DatasetName><DatasetType>esriDTFeatureClass</DatasetType>"
    "<LayerID>"+str(id)+"</LayerID><LayerName>"+layerName+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction><ReplicaServerGen xsi:type=''xs:long''>2590</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen>"
    "<ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen><ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen><UseGeometry>true</UseGeometry><IncludeRelated>true</IncludeRelated>"
    "<QueryOption>esriRowsTypeFilter</QueryOption><HasAttachments>true</HasAttachments></GPSyncDataset>"
    "<GPSyncDataset xsi:type=''typens:GPSyncDataset''><DatasetID>6</DatasetID><DatasetName>"+layerName+"__ATTACH</DatasetName><DatasetType>esriDTTable</DatasetType>"
    "<LayerID>0</LayerID>"
    "<LayerName>"+layerName+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction>"
    "<ReplicaServerGen xsi:type=''xs:long''>2590</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen><ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen>"
    "<ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen><UseGeometry>true</UseGeometry><IncludeRelated>false</IncludeRelated><QueryOption>esriRowsTypeFilter</QueryOption><IsAttachment>true</IsAttachment></GPSyncDataset>"
    "</GPSyncDatasets></GPSyncReplica>'"
    ", NULL, NULL, NULL from GDB_Items")

   sql2=('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
    " select MAX(ObjectID)+1, '{AE8D3C7E-9890-4BF4-B946-5BE50A1CC279}', '{D86502F9-9758-45C6-9D23-6DD1A0107B47}', '"+layerName+"', '"+layerName.upper()+"', 'MyReplica"+str(id)+"\\"+layerName+"', '', 1, NULL, NULL, NULL, NULL, NULL, "
    "'<GPSyncDataset xsi:type=''typens:GPSyncDataset'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
    "<DatasetID>5</DatasetID>"
    "<DatasetName>"+layerName+"</DatasetName>"
    "<DatasetType>esriDTFeatureClass</DatasetType><LayerID>0</LayerID><LayerName>"+layerName+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction>"
    "<ReplicaServerGen xsi:type=''xs:long''>2590</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen><ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen>"
    "<ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen><UseGeometry>true</UseGeometry><IncludeRelated>true</IncludeRelated><QueryOption>esriRowsTypeFilter</QueryOption>"
    "<HasAttachments>true</HasAttachments></GPSyncDataset>', NULL, NULL, NULL from GDB_Items")

   sql3=('INSERT INTO GDB_Items("ObjectID", "UUID", "Type", "Name", "PhysicalName", "Path", "Url", "Properties", "Defaults", "DatasetSubtype1", "DatasetSubtype2", "DatasetInfo1", "DatasetInfo2", "Definition", "Documentation", "ItemInfo", "Shape")'
   " select MAX(ObjectID)+1, '{55C5E7E4-834D-4D44-A12C-991E7F8B4645}', '{D86502F9-9758-45C6-9D23-6DD1A0107B47}', '"+layerName+"__ATTACH', '"+layerName.upper()+"__ATTACH', 'MyReplica_"+str(id)+"\\"+layerName+"__ATTACH', '', 1, NULL, NULL, NULL, NULL, NULL, "
   "'<GPSyncDataset xsi:type=''typens:GPSyncDataset'' xmlns:xsi=''http://www.w3.org/2001/XMLSchema-instance'' xmlns:xs=''http://www.w3.org/2001/XMLSchema'' xmlns:typens=''http://www.esri.com/schemas/ArcGIS/10.3''>"
   "<DatasetID>6</DatasetID>"
   "<DatasetName>"+layerName+"__ATTACH</DatasetName><DatasetType>esriDTTable</DatasetType><LayerID>0</LayerID><LayerName>"+layerName+"</LayerName><Direction>esriSyncDirectionBidirectional</Direction>"
   "<ReplicaServerGen xsi:type=''xs:long''>2590</ReplicaServerGen><ReplicaClientDownloadGen xsi:type=''xs:long''>1000</ReplicaClientDownloadGen><ReplicaClientUploadGen xsi:type=''xs:long''>1000</ReplicaClientUploadGen>"
   "<ReplicaClientAcknowledgeUploadGen xsi:type=''xs:long''>1000</ReplicaClientAcknowledgeUploadGen><UseGeometry>true</UseGeometry><IncludeRelated>false</IncludeRelated><QueryOption>esriRowsTypeFilter</QueryOption>"
   "<IsAttachment>true</IsAttachment></GPSyncDataset>',"
   " NULL, NULL, NULL from GDB_Items")

   #sql4='update "GDB_ServiceItems" set "ItemInfo"=replace("ItemInfo",|"capabilities":"Query"|,|"capabilities":"Create,Delete,Query,Update,Editing,Sync"|)'
   #sql4=sql4.replace("|","'")
   #sql5='update "GDB_Items" set ObjectId=ROWID'

   return [sql1,sql2,sql3]

   #sqliteReplicaPaths(sql1,sql2,sql3)

def sqliteReplicaPaths(sql1,sql2,sql3):
   conn = sqlite3.connect(replicaPath)
   conn.enable_load_extension(True)
   c = conn.cursor()
   sql4='update "GDB_ServiceItems" set "ItemInfo"=replace("ItemInfo",|"capabilities":"Query"|,|"capabilities":"Create,Delete,Query,Update,Editing,Sync"|)'
   sql4=sql4.replace("|","'")

   # A) Inserts an ID with a specific value in a second column
   #http://services5.arcgis.com/KOH6W4WICH5gzytg/ArcGIS/rest/services/rangeland_units/FeatureServer
   try:
      #c.execute("update GDB_Items set DatasetInfo1='"+servicePath + "',DatasetInfo2='"+username+"',Definition='+xml.toxml()+' where Name='"+name+"'")
      printMessage("SELECT load_extension( 'c:\Program Files (x86)\ArcGIS\Desktop10.3\DatabaseSupport\SQLite\Windows32\stgeometry_sqlite.dll', 'SDE_SQL_funcs_init')")
      c.execute("SELECT load_extension( 'c:/Program Files (x86)/ArcGIS/Desktop10.3/DatabaseSupport/SQLite/Windows32/stgeometry_sqlite.dll', 'SDE_SQL_funcs_init')")
      #c.execute("SELECT load_extension( 'c:/Program Files (x86)/ArcGIS/Desktop10.3/DatabaseSupport/SQLite/Windows64/stgeometry_sqlite.dll', 'SDE_SQL_funcs_init')")
   except sqlite3.IntegrityError:
      printMessage("Error in sql integrity")
   else:
      printMessage("Error in sql")

   try:
      #c.execute("update GDB_Items set DatasetInfo1='"+servicePath + "',DatasetInfo2='"+username+"',Definition='+xml.toxml()+' where Name='"+name+"'")
      printMessage(sql1)
      c.execute(sql1)
   except sqlite3.IntegrityError:
      printMessage("Error in sql integrity")
   else:
      printMessage("Error in sql")

   try:
      printMessage(sql2)
      c.execute(sql2)
   except sqlite3.IntegrityError:
      printMessage("Error in sql integrity")
   else:
      printMessage("Error in sql")

   try:
      printMessage(sql3)
      c.execute(sql3)
   except sqlite3.IntegrityError:
      printMessage("Error in sql integrity")
   else:
      printMessage("Error in sql")

   try:
      printMessage(sql4)
      c.execute(sql4)
   except sqlite3.IntegrityError:
      printMessage("Error in sql integrity")
   else:
      printMessage("Error in sql")

   conn.commit()
   conn.close()

def __createXML(xmlFile,serverName,serviceName,layerName):
  dom = parse(zz.open(xmlFile))
  symb = dom.getElementsByTagName("Symbolizer")
  dom.getElementsByTagName("ServiceName")
  dom.getElementsByTagName("ReplicaName")
  dom.getElementsByTagName("ID")
  dom.getElementsByTagName("ReplicaID")
  dom.getElementsByTagName("Owner")
  key.firstChild.data = "new text"

#DatasetID
#DatasetName
#DatasetType>esriDTFeatureClass</DatasetType>
#LayerID
#LayerName

  # Open original file
  #et = xml.etree.ElementTree.parse(xmlFile)

  # Append new tag: <a x='1' y='abc'>body text</a>
  #new_tag = xml.etree.ElementTree.SubElement(et.getroot(), 'a')
  #new_tag.text = 'body text'
  #new_tag.attrib['x'] = '1' # must be str; cannot be an int
  #new_tag.attrib['y'] = 'abc'

  # Write back to file
  #et.write('file.xml')
  #et.write('file_new.xml')


def __updateReplica(layer):
  import sqlite3

  sqlite_file = 'my_first_db.sqlite'
  table_name = 'my_table_2'
  id_column = 'my_1st_column'
  column_name = 'my_2nd_column'

  # Connecting to the database file
  conn = sqlite3.connect(sqlite_file)
  c = conn.cursor()

  # A) Inserts an ID with a specific value in a second column
  try:
      c.execute("INSERT INTO {tn} ({idf}, {cn}) VALUES (123456, 'test')".\
          format(tn=table_name, idf=id_column, cn=column_name))
  except sqlite3.IntegrityError:
      printMessage('ERROR: ID already exists in PRIMARY KEY column {}'.format(id_column))

  # B) Tries to insert an ID (if it does not exist yet)
  # with a specific value in a second column
  c.execute("INSERT OR IGNORE INTO {tn} ({idf}, {cn}) VALUES (123456, 'test')".\
          format(tn=table_name, idf=id_column, cn=column_name))

  # C) Updates the newly inserted or pre-existing entry
  c.execute("UPDATE {tn} SET {cn}=('Hi World') WHERE {idf}=(123456)".\
          format(tn=table_name, cn=column_name, idf=id_column))

  conn.commit()
  conn.close()


def copyGeodatabase():
  # Execute CopyRuntimeGdbToFileGdb
  arcpy.CopyRuntimeGdbToFileGdb_conversion("D:\runtimedata\replica.geodatabase", 'replica_Copy.gdb')

def createSqliteDb():
   # Set local variables
   sqlite_database_path = "C:\data\example.gpkg"

   # Execute CreateSQLiteDatabase
   arcpy.gp.CreateSQLiteDatabase(sqlite_database_path, "GEOPACKAGE")
   # Set environment settings
   arcpy.env.workspace = "C:/data"

   # Set local variables
   outWorkspace = "c:/output/output.gdb"

   # Use ListFeatureClasses to generate a list of shapefiles in the
   #  workspace shown above.
   fcList = arcpy.ListFeatureClasses()

   # Execute CopyFeatures for each input shapefile
   for shapefile in fcList:
       # Determine the new output feature class path and name
       outFeatureClass = os.path.join(outWorkspace, shapefile.strip(".shp"))
       arcpy.CopyFeatures_management(shapefile, outFeatureClass)

   mxd = arcpy.mapping.MapDocument(r"D:\xTemp\sample.mxd")
   df = arcpy.mapping.ListDataFrames(mxd, "*")[0]
   mxd.saveACopy(r"d:\xTemp\name.mxd")
   mxd.save()

   arcpy.CreateRuntimeContent("D:/Geoprocessing/OfflineMapping/sandiego_locators_basemap.mxd",
   "D:/Geoprocessing/Results/RRuntimeContent_sandiego",
   "MyBasemapLayer","#","#",
   "FEATURE_AND_TABULAR_DATA","NON_OPTIMIZE_SIZE","ONLINE","PNG","1","#")

def saveMapfile(mapfile,lyr,desc,dataDestinationPath,mapserver_json):
  mapsize="400 400"
  symbol=""
  type=""
  style=""

  try:
     size=str(mapserver_json['drawingInfo']['renderer']['symbol']['size'])
  except:  # AttributeError:
     size="1"

  try:
     width=str(mapserver_json['drawingInfo']['renderer']['symbol']['width'])
  except: # AttributeError:
     width="1"

  try:
     color=str(mapserver_json['drawingInfo']['renderer']['symbol']['color'][0]) +" "+ str(mapserver_json['drawingInfo']['renderer']['symbol']['color'][1])+" " + str(mapserver_json['drawingInfo']['renderer']['symbol']['color'][2])
  except:  # AttributeError:
     color="0 0 0"
  try:
     outlinecolor=str(mapserver_json['drawingInfo']['renderer']['symbol']['outline']['color'][0]) +" "+ str(mapserver_json['drawingInfo']['renderer']['symbol']['outline']['color'][1])+" " + str(mapserver_json['drawingInfo']['renderer']['symbol']['outline']['color'][2])
  except:  # AttributeError:
     outlinecolor="0 0 0"

  if mapserver_json['geometryType']=='esriGeometryPolygon':
     type="POLYGON"
     style=("COLOR "+color+" \n"
       "OUTLINECOLOR "+outlinecolor+" \n"
       "WIDTH "+width+" \n")
  elif mapserver_json['geometryType']=='esriGeometryPolyline':
     type="LINE"
     style=("COLOR "+color+" \n"
       "OUTLINECOLOR "+outlinecolor+" \n"
       "WIDTH "+width+" \n")
  elif mapserver_json['geometryType']=='esriGeometryPoint':
     symbol=("SYMBOL\n"
      "NAME 'circle'\n"
      "TYPE ellipse\n"
      "FILLED true\n"
      "POINTS\n"
      "1 1\n"
      "END\n"
      "END\n")

     type="POINT"
     style=("COLOR "+color+"\n"
      "SYMBOL 'circle'\n"
      "SIZE "+size+"\n")


  mapstr = ("MAP \n "
      "NAME '" +lyr.name + "' \n"
      "STATUS ON \n"
      "EXTENT " + str(mapserver_json['extent']['xmin']) + " " + str(mapserver_json['extent']['ymin']) + " " + str(mapserver_json['extent']['xmax']) + " " + str(mapserver_json['extent']['ymax']) + "\n"
      "SIZE " + mapsize + "\n"
      "IMAGECOLOR 255 255 255 \n"
      "TRANSPARENT on \n"
      +symbol+
      "LAYER\n"
      "NAME "+lyr.name+"\n"
      "STATUS ON \n"
      "DATA 'data/"+lyr.name+"'\n"
      "TYPE "+type+"\n"
      "CLASS\n"
      "NAME '"+lyr.name+"'\n"
      "STYLE\n"
      +style+
      "END\n"
      "END\n"
      "END\n"
      "END")

  try:
    file = open(mapfile,'w')   # Trying to create a new file or open one
    file.write(mapstr)
    file.close()
  except:
    printMessage("Unable to create mapfile: " + mapstr)


def getOperationalLayers(opLayers,serverName,serviceName,symbols):
   layers=[]
   id = 0
   for lyr in opLayers:
     desc = arcpy.Describe(lyr)
     if hasattr(desc, "layer"):
         featureName=os.path.basename(desc.layer.catalogPath)
     else:
         featureName=os.path.basename(desc.catalogPath)
       
     opLayer = {
         "id": str(id),
         "itemId": lyr.name.replace(" ","_")+str(id),
         "layerType":"ArcGISFeatureLayer",
         "title": lyr.name,
         "url": "http://"+serverName + "/arcgis/rest/services/"+serviceName+"/FeatureServer/"+str(id),
         "popupInfo": getPopupInfo(lyr),
         "layerDefinition":{"drawingInfo":getSymbol(lyr,symbols[featureName]["symbols"],lyr.name)},
         "opacity": (100.0 - float(lyr.transparency)) / 100.0,
         "capabilities": "Create,Delete,Query,Update,Editing,Sync",
         "visibility": lyr.visible
     }
     lbl=""
     if lyr.supports("LABELCLASSES"):
         for lblclass in lyr.labelClasses:
             lblclass.showClassLabels = True
             lbl=lblclass.expression.replace("[","").replace("]","")
     if lbl!="":
          opLayer['popupInfo']['title']=lyr.name + ":  {" + lbl + "}"
     #"opacity": (100 - lyr.transparency) / 100,
     #"url": lyr.serviceProperties["Resturl"]+ "/" + lyr.longName + "/" + lyr.serviceProperties["ServiceType"],

     id=id+1
     layers.append(opLayer)
   return layers

def getTables(opTables,serverName,serviceName,id=0):
   tbls=[]
   for tbl in opTables:
     opTable = {
         "id": str(id),
         "itemId": tbl.name.replace(" ","_")+str(id),
         #"layerType":"ArcGISFeatureLayer",
         "title": tbl.name,
         "url": "http://"+serverName + "/arcgis/rest/services/"+serviceName+"/FeatureServer/"+str(id),
         "popupInfo": getPopupInfo(tbl)
         #"visibility": lyr.visible,
         
     }
     #"capabilities": "Create,Delete,Query,Update,Editing,Sync"
     id=id+1
     tbls.append(opTable)
   return tbls

def getDisplayField(fields):
    displayField=""
    for field in fields:
      #printMessage(field['type'])
      if field['type']=="esriFieldTypeString":
          return field['name']
    #type=esriFieldTypeOID
    return displayField

def getDisplayFieldName(lyr):
    desc = arcpy.Describe(lyr)
    if desc.dataType == "FeatureLayer":
        # Create a fieldinfo object
        fields= arcpy.ListFields(desc.dataElement.catalogPath)
    else:
        fields= arcpy.ListFields(desc.catalogPath)

    displayField=""
    for field in fields:
      #printMessage(field.type)
      if field.type=="String":
          return field.name + " {"+field.name +"}"
    #type=esriFieldTypeOID
    return displayField


def getPopupInfo(lyr):

   popInfo = {'title': getDisplayFieldName(lyr),
              'description':None,
              'showAttachments': True,
              'mediaInfo': [],
              'fieldInfos': getFieldInfos(lyr)
              }

#              'relatedRecordsInfo':{
#                  'showRelatedRecords':True,
#                  'orderByFields':None
#              },

   desc = arcpy.Describe(lyr)
   if not hasAttachments(desc.catalogPath):
       popInfo["showAttachments"]=False
   return popInfo

#def getLayerDefinition(lyr,symbol):
#    return getSymbol(lyr,symbols[featureName],lyr.name)
#    layerDef={
#        "drawingInfo":{
#            "renderer":getRendere(lyr)
#        }
#    }

#get the fields for the popup
def getFieldInfos(layer):
   popInfo=[]
   #printMessage("Layer name: " + layer.name)
   #if layer.supports['FEATURECLASS']:
   #     printMessage("Layer has featureclass")
   desc = arcpy.Describe(layer)
   if desc.dataType == "FeatureLayer":
        # Create a fieldinfo object
        allfields= arcpy.ListFields(desc.dataElement.catalogPath)
   else:
        allfields= arcpy.ListFields(desc.catalogPath)
        #return popInfo

   #SmallInteger, Integer, Single, Double, String, Date, OID, Geometry, Blob
   # Iterate through the fields and set them to fieldinfo
   #"GlobalID",
   invisFields = ["Shape_Length","Shape_Area","has_permittee","permittee_globalid"]
   for field in allfields:
        fieldInfos = None
        #printMessage("Field: " + field.name + ":  " + field.type)
        visible = True
        if field.name in invisFields:
            visible=False
        if field.type=='Geometry':
           continue
        if field.type == 'OID':
            oidFldName = field.name
            fieldInfos = {
                'fieldName':field.name,
                'label':field.aliasName,
                'isEditable':field.editable,
                'isEditableOnLayer':field.editable,
                'tooltip':'',
                'visible':visible,
                'format':None,
                'stringFieldOption':'textbox'
            }

        elif field.type == 'Integer':
            fieldInfos = {
                'fieldName':field.name,
                'label':field.aliasName,
                'isEditable':field.editable,
                'isEditableOnLayer':field.editable,
                'tooltip':'',
                'visible':visible,
                'format':{
                    'places':0,
                    'digitSeparator':True
                },
                'stringFieldOption':'textbox'
            }
        elif field.type == 'Double':
            fieldInfos = {
                'fieldName':field.name,
                'label':field.aliasName,
                'isEditable':field.editable,
                'isEditableOnLayer':field.editable,
                'tooltip':'',
                'visible':visible,
                'format':{
                    'places':2,
                    'digitSeparator':True
                    },
                'stringFieldOption':'textbox'
            }
        elif field.type == 'String':
            fieldInfos = {
                'fieldName':field.name,
                'label':field.aliasName,
                'isEditable':field.editable,
                'isEditableOnLayer':field.editable,
                'tooltip':'',
                'visible':visible,
                'format':None,
                'stringFieldOption':'textbox'
            }
        elif field.type == 'Date':
            fieldInfos = {
                'fieldName':field.name,
                'label':field.aliasName,
                'isEditable':field.editable,
                'isEditableOnLayer':field.editable,
                'tooltip':'',
                'visible':visible,
                'format':{"dateFormat":"longMonthDayYear"},
                'stringFieldOption':'textbox'
            }
        
        else:
            fieldInfos = {
                'fieldName':field.name,
                'label':field.aliasName,
                'isEditable':field.editable,
                'isEditableOnLayer':field.editable,
                'tooltip':'',
                'visible':visible,
                'format':None,
                'stringFieldOption':'textbox'
            }
        if fieldInfos is not None:
            popInfo.append(fieldInfos)

   return popInfo

def getFields(layer):
   fields=[]
   desc = arcpy.Describe(layer)
   if hasattr(desc, "layer"):
      catPath = desc.dataElement.catalogPath
   else:
      catPath = desc.catalogPath
   #printMessage("Catalog path: "+catPath)
   #printMessage(desc.dataType)
   if desc.dataType == "FeatureLayer":
        allfields= arcpy.ListFields(catPath)
   elif desc.dataType == "TableView":
        allfields= arcpy.ListFields(catPath)
   else:
        return fields

   #SmallInteger, Integer, Single, Double, String, Date, OID, Geometry, Blob,Guid
   # Iterate through the fields and set them to fieldinfo
   for field in allfields:
        fieldInfos = None
        #printMessage("Field: " + field.name + ":  " + field.type)
        if field.type=='Geometry':
           continue
        fieldInfos = {
                'alias':field.aliasName,
                'defaultValue':None,
                'domain':None,
                'editable':field.editable,
                'name':field.name,
                'nullable':field.isNullable,
                'sqlType':'sqlTypeOther'
        }
        if field.length:
             fieldInfos['length']=field.length
        #"domain":{"type":"codedValue","name":"cover_type","codedValues":[{"name":"No trees","code":0},{"name":"Trees","code":1}]}

        if field.domain:  #domain contains the name of the domain.  You must look it up to get the full definition using ListDomains
           fieldInfos['domain']={"name":field.domain}
           domains = arcpy.da.ListDomains(getFeatureClassParentWorkspace(catPath))
           for domain in domains:
               if domain.name == field.domain:
                    #printMessage('Domain name: {0}'.format(domain.name))
                    #printMessage('Domain name: {0}'.format(domain.name) )
                    if domain.domainType == 'CodedValue':
                        fieldInfos['domain']['type']='codedValue'
                        codedValuesArray=[]
                        for val,desc in domain.codedValues.iteritems():
                            codedValuesArray.append({"code":val,"name":desc})
                            #[domain.codedValues]
                        fieldInfos['domain']['codedValues'] = codedValuesArray

                        #for val, desc in coded_values.iteritems():
                        #    printMessage('{0} : {1}'.format(val, desc))
                    elif domain.domainType == 'Range':
                        fieldInfos['domain']['type']='range'
                        fieldInfos['domain']['rangeValues']=domain.range
                        #printMessage('Min: {0}'.format(domain.range[0]))
                        #printMessage('Max: {0}'.format(domain.range[1]))

           #for iDomain in arcpy.da.ListDomains(getFeatureClassParentWorkspace(inFeatureClass)):
           #     if iDomain.name == searchDomainName:
           #         return iDomain

        if field.type == 'OID':
            oidFldName = field.name
            fieldInfos['type']='esriFieldTypeOID'
            del fieldInfos['length']
        #elif field.name == 'OBJECTID':
        #    oidFldName = field.name
        #    fieldInfos['type']='esriFieldTypeOID'
        elif field.type == 'Integer':
           fieldInfos['type']='esriFieldTypeInteger'
        elif field.type == 'Single':
           fieldInfos['type']='esriFieldTypeSingle'
           #del fieldInfos['length']
        elif field.type == 'SmallInteger':
           fieldInfos['type']='esriFieldTypeSmallInteger'
           #del fieldInfos['length']
        elif field.type == 'Double':
           fieldInfos['type']='esriFieldTypeDouble'
        elif field.type == 'String':
           fieldInfos['type']='esriFieldTypeString'
        elif field.type == 'Date':
           fieldInfos['type']='esriFieldTypeDate'
        elif field.type == 'Guid':
           fieldInfos['type']='esriFieldTypeGUID'
        elif field.type == 'GlobalID':
           fieldInfos['type']='esriFieldTypeGlobalID'
           #fieldInfos['defaultValue']='NEWID() WITH VALUES'
        else:
           printMessage("Unknown field type for " + field.name + ": " + field.type)
           fieldInfos['type']='esriFieldTypeOID'
        if fieldInfos is not None:
            fields.append(fieldInfos)

        #{
        #    "domain": null,
        #    "name": "OBJECTID",
        #    "nullable": false,
        #    "defaultValue": null,
        #    "editable": false,
        #    "alias": "OBJECTID",
        #    "sqlType": "sqlTypeOther",
        #    "type": "esriFieldTypeInteger"
        #},
        #    "domain": null,
        #    "name": "GlobalID",
        #    "nullable": false,
        #    "defaultValue":"NEWID() WITH VALUES",
        #    "editable": false,
        #    "alias": "GlobalID",
        #    "length": 38,
        #    "sqlType": "sqlTypeOther",
        #    "type": "esriFieldTypeGlobalID"

        #if field.name=='OBJECTID':
        #   fieldInfos['type']='esriFieldTypeInteger'

   return fields

#{
#    "id" : <relationshipId1>,
#    "name" : "<relationshipName1>",
#    "relatedTableId" : <relatedTableId1>,
#    "cardinality" : "<esriRelCardinalityOneToOne>|<esriRelCardinalityOneToMany>|<esriRelCardinalityManyToMany>";,//Added at 10.1
#    "role" : "<esriRelRoleOrigin>|<esriRelRoleDestination>";,//Added at 10.1
#    "keyField" : "<keyFieldName2>",//Added at 10.1
#    "composite" : <true>|<false>,//Added at 10.1
#    "relationshipTableId": <attributedRelationshipClassTableId>,  //Added in 10.1. Returned only for attributed relationships
#    "keyFieldInRelationshipTable": "<key field in AttributedRelationshipClass table that matches keyField>" //Added in 10.1. Returned only for attributed relationships
#},

#def getRelationships(lyr,lyrid,cnt,tables,relationshipObj):
def getJoinField(lyr):
   desc = arcpy.Describe(lyr)
   if not desc.relationshipClassNames:
      return ""
   for j,rel in enumerate(desc.relationshipClassNames):
     #printMessage("Relationship class name: " + rel)
     relDesc = arcpy.Describe(desc.path +"/"+rel)
     #originClassKeys=relDesc.originClassKeys
     for i in relDesc.originClassKeys:
         if i[1]=="OriginPrimary":
             return i[0]
    
def getRelationshipsUnused(lyr,relationshipObj):
   relArr=[]
   desc = arcpy.Describe(lyr)
   if not desc.relationshipClassNames:
      return relArr
   for j,rel in enumerate(desc.relationshipClassNames):
     printMessage("Relationship class name: " + rel)
     relArr.append(relationshipObj[rel])
   return relArr

def getRelationshipsNoGood(lyr,lyrid,cnt,tables,relationships):
   relArr=[]
   desc = arcpy.Describe(lyr)
   if not desc.relationshipClassNames:
      return rel
   if hasattr(desc, "layer"):
         featureName=os.path.basename(desc.layer.catalogPath)
         rootFGDB=desc.layer.catalogPath.replace("\\","/")
   else:
         featureName=os.path.basename(desc.catalogPath)
         rootFGDB=os.path.dirname(desc.catalogPath).replace("\\","/")

   relid=0
   #for index in xrange(0, field_info.count):
   for j,rel in enumerate(desc.relationshipClassNames):
     relDesc = arcpy.Describe(rootFGDB+"/"+rel)
     if relDesc.isAttachmentRelationship:
          continue
     #printMessage(relDesc)
     #for i in desc:
     #   printMessage(i)

     label = relDesc.backwardPathLabel
     cardinality = relDesc.cardinality
     #key=relDesc.classKey

     originClassKeys=relDesc.originClassKeys
     key=relDesc.destinationClassNames[0]

     printMessage("Origin Class Names")
     printMessage(relDesc.originClassNames)

     printMessage("Origin Class Keys")
     printMessage(relDesc.originClassKeys)

     printMessage("Destination Class Names")
     printMessage(relDesc.destinationClassNames)

     printMessage("Destination Class Keys")
     printMessage(relDesc.destinationClassKeys)

     printMessage("Key type:  "+relDesc.keyType)
     printMessage(relDesc.notification)
     printMessage("backwardPathLabel:  "+relDesc.backwardPathLabel)
     printMessage("forwardPathLabel:  "+relDesc.forwardPathLabel)
     role="esriRelRoleOrigin"
     role="esriRelRoleDestination"

     id=0
     relatedTableId=0
     for i in relDesc.destinationClassNames:
        for j in tables:
          #printMessage(i+":  " + j.datasetName)
          if i == j.datasetName:
            relatedTableId=id
            printMessage("Relationship name: "+i+": " + j.name + "(" + j.datasetName + ") with id: " +str(relatedTableId+cnt))
        id=id+1
     relatedTableId=relatedTableId+cnt

     relObj = {"id":relid,"name":label,"relatedTableId":relatedTableId,"cardinality":"esriRelCardinality"+cardinality,"role":role,"keyField":key,"composite":relDesc.isComposite}
     relArr.append(relObj)
     #relClasses.add(rel)
   return relArr

def getDataIndex(arr,name):
  for j,rel in enumerate(arr):
      #printMessage(str(j) + ": " + rel.name)
      if hasattr(rel, "datasetName"):
         #printMessage(i+":  " + str(j) + ": " + rel.datasetName)
         datasetName=rel.datasetName
      else:
         desc = arcpy.Describe(rel)

         if hasattr(desc, "layer"):
             datasetName=os.path.basename(desc.layer.catalogPath)
         else:
             datasetName=os.path.basename(desc.catalogPath)

      if name == datasetName:
        printMessage("Found relationship name: "+name+": " + rel.name + "(" + datasetName + ") with id: " +str(j))
        return j

  return -1


# getFeatureClassParentWorkspace: This script gets the geodatabase for a
# feature class. The trick here is that feature classes can be within a
# feature dataset so you need to account for two possible levels in the
# directory structure.
def getFeatureClassParentWorkspace(inFeatureClass):
    describeFC = arcpy.Describe(inFeatureClass)
    if (describeFC.dataType == 'FeatureClass') or (describeFC.dataType == 'Table'):
        workspace1 = describeFC.path
        describeWorkspace1 = arcpy.Describe(workspace1)
        if (describeWorkspace1.dataType == 'FeatureDataset'):
            return describeWorkspace1.path
        return workspace1

    return None



def getIndexes(lyr):
   indexes=[]
   desc = arcpy.Describe(lyr)
   if desc.dataType == "FeatureLayer":
       lyrindexes = arcpy.ListIndexes(desc.dataElement.catalogPath)
   elif desc.dataType == "TableView":
       lyrindexes = arcpy.ListIndexes(desc.catalogPath)

   for index in lyrindexes:
       fields=[]
       for field in index.fields:
          fields.append(field.name)

       indexes.append({"name":index.name,"fields":",".join(fields),"isAscending":index.isAscending,"isUnique":index.isUnique})
   return indexes

   #printMessage("Name        : {0}".format(index.name))
   #printMessage("IsAscending : {0}".format(index.isAscending))
   #printMessage("IsUnique    : {0}".format(index.isUnique))

def hasAttachments(tbl):
    return arcpy.Exists(tbl+"__ATTACH")

def hasEditorTracking(tbl):
    desc = arcpy.Describe(tbl)
    return desc.editorTrackingEnabled

def num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)

def getSymbolColor(sym):
    printMessage("here")

def getPointSymbol(sym):
    #"style" : "< esriSMSCircle | esriSMSCross | esriSMSDiamond | esriSMSSquare | esriSMSX | esriSMSTriangle >",
    obj = {}
    obj['type']="esriSMS"
    obj['style']="esriSMSCircle"
    obj['size']= 4
    obj['angle']= 0
    obj['xoffset']= 0
    obj['yoffset']=  0
    #obj['outline']={}
    #obj['outline']['width']= 1
    symb = sym.getElementsByTagName("CIMSymbolLayer")
    size = sym.getElementsByTagName("Size")
    if len(size) > 0:
       #printMessage("Size: " + size[0].childNodes[0].nodeValue)
       obj['size']= num(size[0].childNodes[0].nodeValue)

    #type = symb.getAttribute("xsi:type")
    #if type == "typens:CIMFilledStroke":
    #    x=1
    #elif type == "typens:CIMCharacterMarker":
    #    x=2

    for i in symb:

       if i.getAttribute("xsi:type")=="typens:CIMFill":
          #obj['color']['type']="esriSLS"
          #obj['outline']['style']="esriSLSSolid"
          #2drawingInfo['renderer']['symbol']['outline']['style']="esriSFSSolid"
          #obj['outline']['style']="esriSLSSolid"
          obj['color'] = getSymbolColor(i)  
       elif i.getAttribute("xsi:type")== "typens:CIMFilledStroke":
          obj['outline']={}
          obj['outline']['type']="esriSLS"
          obj['outline']['style']="esriSLSSolid"
          obj['outline']['color'] = getSymbolColor(i)  
          
          width = i.getElementsByTagName("Width")
          if len(width)>0:
             #printMessage("Width: " + width[0].childNodes[0].nodeValue)
             obj['outline']['width']=num(width[0].childNodes[0].nodeValue)  
          
       
    #obj = getSymbolColor(sym,obj)               
    return obj
    
def getPolygonSymbol(sym):
    #"style" : "< esriSFSBackwardDiagonal | esriSFSCross | esriSFSDiagonalCross | esriSFSForwardDiagonal | esriSFSHorizontal | esriSFSNull | esriSFSSolid | esriSFSVertical >",
    obj = {}
    obj['type']="esriSFS"
    obj['style']="esriSFSSolid"

    symb = sym.getElementsByTagName("CIMSymbolLayer")
    for i in symb:
        
       if i.getAttribute("xsi:type")=="typens:CIMFill":
          #obj['color']= {}
          #obj['color']['type']="esriSLS"
          #2drawingInfo['renderer']['symbol']['outline']['style']="esriSFSSolid"
          #obj['outline']['style']="esriSLSSolid"
          obj['color'] = getSymbolColor(i)  
       elif i.getAttribute("xsi:type")== "typens:CIMFilledStroke":
          obj['outline']={}
          obj['outline']['type']="esriSLS"
          obj['outline']['style']="esriSLSSolid"
          obj['outline']['color'] = getSymbolColor(i)  
          #size = i.getElementsByTagName("Size")
          width = i.getElementsByTagName("Width")
          
          #if len(size) > 0:
          #   printMessage("Size: " + size[0].childNodes[0].nodeValue)
          #   obj['outline']['size']= num(size[0].childNodes[0].nodeValue)
          if len(width)>0:
             #printMessage("Width: " + width[0].childNodes[0].nodeValue)
             obj['outline']['width']=num(width[0].childNodes[0].nodeValue)  
          
    return obj

def getPolylineSymbol(sym):
    #"style" : "< esriSLSDash | esriSLSDashDot | esriSLSDashDotDot | esriSLSDot | esriSLSNull | esriSLSSolid >",
    obj = {}
    obj['type']="esriSLS"
    obj['style']="esriSFSSolid"
    obj['outline']={}
    return obj
    
def hsv_to_rgb(h, s, v,a):
        if s == 0.0: v*=255; return [v, v, v,a]
        i = int(h*6.) # XXX assume int() truncates!
        f = (h*6.)-i; p,q,t = int(255*(v*(1.-s))), int(255*(v*(1.-s*f))), int(255*(v*(1.-s*(1.-f)))); v*=255; i%=6
        if i == 0: return [v, t, p,a]
        if i == 1: return [q, v, p,a]
        if i == 2: return [p, v, t,a]
        if i == 3: return [p, q, v,a]
        if i == 4: return [t, p, v,a]
        if i == 5: return [v, p, q,a]

def getColorObj(color):
    
    if len(color[0].getElementsByTagName("R")) > 0:
       colorStr = (str(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue) + "," + 
       str(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue) + "," + 
       str(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue) + "," + 
       str(color[0].getElementsByTagName("Alpha")[0].childNodes[0].nodeValue))
            
       colorObj = [ 
             int(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue), 
             int(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue), 
             int(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue),
             int(color[0].getElementsByTagName("Alpha")[0].childNodes[0].nodeValue) 
       ]
       #printMessage("Color (polygon): " + colorStr) 
       return colorObj
    
    elif len(color[0].getElementsByTagName("H")) > 0:
       colorStr = (str(color[0].getElementsByTagName("H")[0].childNodes[0].nodeValue) + "," + 
       str(color[0].getElementsByTagName("S")[0].childNodes[0].nodeValue) + "," + 
       str(color[0].getElementsByTagName("V")[0].childNodes[0].nodeValue) + "," + 
       str(color[0].getElementsByTagName("Alpha")[0].childNodes[0].nodeValue))
            
       colorObj = hsv_to_rgb(
             int(color[0].getElementsByTagName("H")[0].childNodes[0].nodeValue), 
             int(color[0].getElementsByTagName("S")[0].childNodes[0].nodeValue), 
             int(color[0].getElementsByTagName("V")[0].childNodes[0].nodeValue),
             int(color[0].getElementsByTagName("Alpha")[0].childNodes[0].nodeValue)
       ) 
       
       #printMessage("Color (polygon): " + colorStr) 
       return colorObj
    
         #if patt[0].getAttribute("xsi:type")=="typens:CIMFilledStroke":
         #   obj['color']=[ int(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue),255]
         #else:
         #   obj['color']=[ int(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue),255]
    
    return []

def getSymbolColor(sym):
    patt = sym.getElementsByTagName("Pattern")
    colorObj=[]
    #colorObj = {}
    if len(patt)>0:
         color = patt[0].getElementsByTagName("Color")
         if len(color)==0:
            return colorObj
         colorObj = getColorObj(color)

    return colorObj


def getSymbolColora(sym,obj):
    patt = sym.getElementsByTagName("Pattern")
    if len(patt)>0:
         color = patt[0].getElementsByTagName("Color")
         colorStr = str(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue) + "," + str(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue) + "," + str(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue)
         if patt[0].getAttribute("xsi:type")=="typens:CIMFilledStroke":
            obj['outline']['color']=[ int(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue),255]
         else:
            obj['color']=[ int(color[0].getElementsByTagName("R")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("G")[0].childNodes[0].nodeValue), int(color[0].getElementsByTagName("B")[0].childNodes[0].nodeValue),255]
         #printMessage("Color (polygon): " + colorStr)
    return obj

def getGroupSymbols(sym):
    #loop through sym and return Array
    #get geometry type
    group=[]
    for i in sym:
        obj = {}
        val = i.getElementsByTagName("FieldValues")
        if len(val)>0:
            #obj["value"]=val[0].childNodes[0].nodeValue
            s = val[0].getElementsByTagName("String")
            obj["value"]=s[0].childNodes[0].nodeValue
        label = i.getElementsByTagName("Label")
        if len(label)>0:
            obj["label"]=label[0].childNodes[0].nodeValue
        else:
            obj["label"]=obj["value"]
        

        for j in i.childNodes:
           if j.tagName == "Symbol":
             #get the next symbol
             k = j.getElementsByTagName("Symbol")
             for m in k:
                #type = geomtype[0].getAttribute("xsi:type")=="typens:CIMPolygonSymbol"
                if m.getAttribute("xsi:type")=="typens:CIMPointSymbol":
                   obj['symbol'] = getPointSymbol(m)
                elif m.getAttribute("xsi:type")=="typens:CIMPolygonSymbol":
                   obj['symbol']=getPolygonSymbol(m)
        group.append(obj)
    return group
        


#see http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r30000019t000000
# and http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000n5000000
#"symbol":{ "type": "esriSMS", "style": "esriSMSSquare", "color": [76,115,0,255], "size": 8, "angle": 0, "xoffset": 0, "yoffset": 0, "outline": { "color": [152,230,0,255], "width": 1 } }
def getSymbol(lyr,sym,name):
   drawingInfo= {
     "renderer": {
      "label": "",
      "description": ""
     },
     "transparency": lyr.transparency,
     "labelingInfo": None
   }

   if sym.getAttribute("xsi:type") == "typens:CIMUniqueValueSymbolizer":
         drawingInfo['renderer']['type']="uniqueValue"
         #drawingInfo['renderer']['uniqueValueInfos']=[]
   else:
         drawingInfo['renderer']['type']="simple"
         #drawingInfo['renderer']['symbol']={}
         #drawingInfo['renderer']['symbol']['outline']={}

   #renderer->uniqueValueInfos
   #printMessage("******Creating symbology for " + name + "*******")
   for i in sym.childNodes:
      #printMessage(i.tagName + ": " + i.getAttribute("xsi:type"))
      #printMessage(i)
      #printMessage(str(i.childNodes.length))
      if i.tagName=='Fields':
            c=1
            k = i.getElementsByTagName("String")
            for m in k:
              lbl = 'field'+str(c)
              drawingInfo['renderer'][lbl]=m.childNodes[0].nodeValue
              c=c+1
      elif i.tagName=='Groups':
             if i.getAttribute("xsi:type") == "typens:ArrayOfCIMUniqueValueGroup":
                 k = i.getElementsByTagName("CIMUniqueValueClass")
                 drawingInfo['renderer']['uniqueValueInfos'] = getGroupSymbols(k)
      elif i.tagName == "Symbol":
         for j in i.childNodes:
           #printMessage(" " + j.tagName + ": " + j.getAttribute("xsi:type"))
           #get first symbol
           if j.tagName=='Symbol':
                 if j.getAttribute("xsi:type")=="typens:CIMPointSymbol":
                      drawingInfo['renderer']['symbol'] = getPointSymbol(j)
                 elif j.getAttribute("xsi:type")=="typens:CIMPolygonSymbol":
                      drawingInfo['renderer']['symbol']=getPolygonSymbol(j)
              #for k in j.childNodes:
              #   printMessage("  " + k.tagName + ": " + k.getAttribute("xsi:type"))
                 #get second symbol
                 #if k.getAttribute("xsi:type")=="typens:CIMSymbolReference":
                 #if k.tagName=='Symbol':
                 
               #elif k.tagName=='SymbolLayers':
                    #drawingInfo['renderer']['symbol'] = getSymbolLayers(k)
               #     drawingInfo['renderer']['uniqueValueInfos']=getSymbolLayers(k)
   
   return drawingInfo

def saveSqliteToPG(tables,sqliteDb,pg):
    #-lco LAUNDER=NO keeps the case for column names
    #must run the following in the Database afterwards
    #alter table services alter column json type jsonb using json::jsonb;
    #alter table catalog alter column json type jsonb using json::jsonb;
    #--config OGR_SQLITE_CACHE 1024
    #need to add gdal/bin directory to path
    #os.environ['PATH'] += os.pathsep + (gdal_path + os.sep + "bin").replace("/","\\")
    os.putenv("PATH",(gdal_path + os.sep + "bin").replace("/","\\"))
    #printMessage(os.environ['PATH'])
    
    for table in tables:
       cmd = "\""+ogr2ogr_path+"\"  -lco FID=OBJECTID -preserve_fid  --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+gdal_data_path + "\" -f \"Postgresql\" PG:\"" + pg + "\"  \"" + sqliteDb + "\" " + table + " -nlt None -overwrite"
       #printMessage("Running " + cmd)
       try:
           #os.system(cmd)
           result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
       except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)
    
    cmd = "\""+ogrinfo_path+"\"  PG:\"" + pg + "\"  -sql \"alter table services alter column json type jsonb using json::jsonb\""
    #printMessage("Running " + cmd)
    try:
           #os.system(cmd)
           result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)
    cmd = "\""+ogrinfo_path+"\"  PG:\"" + pg + "\"  -sql \"alter table catalog alter column json type jsonb using json::jsonb\""
    #printMessage("Running " + cmd)
    try:
           #os.system(cmd)
           result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)

def saveSqliteServiceTablesToPG(serviceDb,pg):
    global ogr2ogr_path
    global gdal_data_path
    global gdal_path
    #need to add gdal/bin directory to path
    #os.environ['PATH'] += os.pathsep + (gdal_path + os.sep + "bin").replace("/","\\")
    os.putenv("PATH",(gdal_path + os.sep + "bin").replace("/","\\"))
    #printMessage(os.environ['PATH'])
    
    #SET PGCLIENTENCODING=LATIN1
    #-lco SCHEMA postgres
    tables=["GDB_ColumnRegistry","GDB_ItemRelationshipTypes","GDB_ItemRelationships","GDB_ItemTypes","GDB_Items","GDB_Layers","GDB_Locators","GDB_Metadata","GDB_ReplicaLog","GDB_RowidGenerators","GDB_ServiceItems","GDB_TableRegistry","GDB_TablesModified","GDB_Tables_Last_Modified","GDB_Version"]
    os.putenv("PGCLIENTENCODING","LATIN1")
    for table in tables:
        #-lco FID=OBJECTID -preserve_fid  
        cmd = "\"" + ogr2ogr_path+"\" -lco LAUNDER=NO -lco GEOMETRY_NAME=the_geom --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+gdal_data_path + "\" -f \"Postgresql\" PG:\"" + pg + "\"  \"" + serviceDb + "\" \""+table+"\" -overwrite"
        #printMessage("Running " + cmd)
        try:
              #os.system(cmd)
              result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)
    os.unsetenv("PGCLIENTENCODING")

def saveToPg(lyr,pg):
   global ogr2ogr_path
   global gdal_data_path
   global gdal_path
   #need to add gdal/bin directory to path
   #os.environ['PATH'] += os.pathsep + (gdal_path + os.sep + "bin").replace("/","\\")
   os.putenv("PATH",(gdal_path + os.sep + "bin").replace("/","\\"))
   #printMessage(os.environ['PATH'])
    
   desc = arcpy.Describe(lyr)
   #-lco FID=OBJECTID -preserve_fid 
   if hasattr(desc,"shapeType"):
       cmd = "\"" + ogr2ogr_path+"\" -lco LAUNDER=NO -forceNullable --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+ gdal_data_path + "\" -f \"Postgresql\" PG:\"" + pg + "\"  \"" + desc.path + "\" " + desc.name.replace(".shp","") + " -overwrite"
   else:
       cmd = "\"" + ogr2ogr_path+"\" -lco LAUNDER=NO -forceNullable --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+gdal_data_path + "\" -f \"Postgresql\" PG:\"" + pg + "\"  \"" + desc.path + "\" " + desc.name.replace(".shp","") + " -nlt None -overwrite"
   #printMessage("Running " + cmd)
   try:
        #os.system(cmd)
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
   except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)

def saveAttachTableToPg(fgdb,lyr,suffix,pg):
   global ogr2ogr_path
   global ogrinfo_path
   global gdal_data_path
   global gdal_path
   #need to add gdal/bin directory to path
   #os.environ['PATH'] += os.pathsep + (gdal_path + os.sep + "bin").replace("/","\\")
   os.putenv("PATH",(gdal_path + os.sep + "bin").replace("/","\\"))
   #printMessage(os.environ['PATH'])
    
   desc = arcpy.Describe(fgdb+"/"+lyr+suffix)
   #-lco FID=OBJECTID -preserve_fid 
   if hasattr(desc,"shapeType"):
       cmd = "\"" + ogr2ogr_path+"\" -lco LAUNDER=NO -forceNullable --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+gdal_data_path + "\" -f \"Postgresql\" PG:\"" + pg + "\"  \"" + desc.path + "\" " + desc.name.replace(".shp","") + " -overwrite"
   else:
       cmd = "\""+ogr2ogr_path+"\" -lco LAUNDER=NO -forceNullable --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+gdal_data_path + "\" -f \"Postgresql\" PG:\"" + pg + "\"  \"" + desc.path + "\" " + desc.name.replace(".shp","") + " -nlt None -overwrite"
   #printMessage("Running " + cmd)
   try:
        #os.system(cmd)
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
   except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)
   #find the globalid
   cmd = "\""+ogrinfo_path+"\"  PG:\"" + pg + "\"  -sql \"alter table \\\""+lyr+suffix+"\\\" rename \\\"GlobalID\\\" to \\\"GLOBALID\\\""
   #printMessage("Running " + cmd)
   try:
        #os.system(cmd)
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
   except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)

   #need to rename grazing_inspections_GlobalID fields to REL_GLOBALID
   cmd = "\""+ogrinfo_path+"\"  PG:\"" + pg + "\"  -sql \"alter table \\\""+lyr+suffix+"\\\" rename \\\""+lyr + "_GlobalID\\\" to \\\"REL_GLOBALID\\\""
   #printMessage("Running " + cmd)
   try:
        #os.system(cmd)
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
   except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)

def saveToSqlite(lyr,sqliteDb):
   global ogr2ogr_path
   global gdal_data_path
   global gdal_path
   #need to add gdal/bin directory to path
   #os.environ['PATH'] += os.pathsep + (gdal_path + os.sep + "bin").replace("/","\\")
   os.putenv("PATH",(gdal_path + os.sep + "bin").replace("/","\\"))
   #printMessage(os.environ['PATH'])
    
   #drop table if it exists
   
   desc = arcpy.Describe(lyr)
   if hasattr(desc,"shapeType"):
       cmd = "\""+ogr2ogr_path+"\" -lco LAUNDER=NO -lco FID=OBJECTID -preserve_fid -forceNullable --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+gdal_data_path + "\" -f \"SQLITE\" \"" + sqliteDb + "\"  \"" + desc.path + "\" " + desc.name.replace(".shp","") + " -overwrite"
   else:
       cmd = "\""+ogr2ogr_path+"\" -lco LAUNDER=NO -lco FID=OBJECTID -preserve_fid -forceNullable --config OGR_SQLITE_SYNCHRONOUS OFF -gt 65536 --config GDAL_DATA \""+ gdal_data_path + "\" -f \"SQLITE\" \"" + sqliteDb + "\"  \"" + desc.path + "\" " + desc.name.replace(".shp","") + " -nlt None -overwrite"
   #printMessage("Running " + cmd)
   try:
        #os.system(cmd)
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
   except Exception, e:
           printMessage("Unable to run sql commands:  "+cmd + "\n" + e.output)

def saveToSqliteUsingArcpy(lyr,sqliteDb):
   desc = arcpy.Describe(lyr)

   inFeaturesSqlName = desc.name.lower().replace(".shp","") .replace("-","_") #.replace("_","")
   if hasattr(desc,"shapeType"):
        try:
            arcpy.CreateFeatureclass_management(sqliteDb,inFeaturesSqlName, desc.shapeType.upper())
        except Exception as e:
            printMessage("Table already exists")
            printMessage(e)
        try:
            arcpy.CopyFeatures_management(desc.catalogPath, sqliteDb+"/"+inFeaturesSqlName)
        except Exception as e:
            printMessage("Unable to copy features")
            printMessage(e)

   else:
        arcpy.CopyRows_management(desc.catalogPath, sqliteDb+"/"+inFeaturesSqlName)
        printMessage("")

   arcpy.ClearWorkspaceCache_management(sqliteDb)
   desc = arcpy.Describe(sqliteDb)

def initializeSqlite(sqliteDb):
        conn = sqlite3.connect(sqliteDb)
        c = conn.cursor()

        #c.execute("PRAGMA journal_mode=WAL")
        
        c.execute("DROP TABLE IF EXISTS catalog")
        #c.execute("DROP TABLE IF EXISTS services")
        c.execute("CREATE TABLE IF NOT EXISTS catalog (id INTEGER PRIMARY KEY AUTOINCREMENT, name text, type text, json text)")
        c.execute("CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, service text,name text, layername text,layerid int, type text,json text)")

        #c.execute("Create table "+inFeaturesName+" (objectid integer,t_r text,sect text,shape_area double)")
        #c.executemany("Insert into "+inFeaturesName+"(objectid,t_r,sect,shape_area) values (?,?,?,?)", map(tuple, array.tolist()))
        conn.commit()
        conn.close()
        return conn

def LoadCatalog(sqliteDb,name, dtype,file):
    conn = sqlite3.connect(sqliteDb)
    c = conn.cursor()
    json = file.replace("'", "''")
    json = json.replace("\xa0", "")
    json = json.replace("\n", "")
    array = [name,dtype,json]
    #c.execute("DELETE FROM catalog where name=? and type=?", (name,dtype))
    c.execute("INSERT INTO catalog(name,type,json) VALUES(?,?,?)", (name,dtype,json))
    c.close()
    conn.commit()
    #map(tuple, array.tolist())
    conn.close()

def ClearService(sqliteDb,service):
    conn = sqlite3.connect(sqliteDb)
    c = conn.cursor()
    #c.execute("DELETE FROM catalog where name=?", (name,dtype))
    c.execute("DELETE FROM services where service=?", (service,))
    c.close()
    conn.commit()
    conn.close()


def LoadService(sqliteDb,service,name, layername, layerid,dtype,file):
    conn = sqlite3.connect(sqliteDb)
    c = conn.cursor() 

    json = file.replace("'", "''")
    json = json.replace("\xa0", "")
    json = json.replace("\n", "")
    
    array = [service,name,layerid,dtype,json]
    #c.execute("DELETE FROM services where service=? and name=? and layerid=? and type=?", (service,name,layerid,dtype))
    c.execute("INSERT INTO services(service,name,layername,layerid,type,json) VALUES(?,?,?,?,?,?)", (service,name,layername,layerid,dtype,json))
    c.close()
    conn.commit()
    conn.close()

def printUsage():
    print "Usage:\n"
    print "python \"Create arcgis project tool.pyt\" -user myusername -host myhostname -mxd <fullpath_to_my_project.mxd> -output <full_path_to_output_directory> -spatialite_path <full_path_to_spatialite_executable> -gdal_path <full_path_to_gdal_directory> -pem <full_path_to_pem> -cert <full_path_to_cert>"
    print "Note:  the output folder can contain only one type of database (file, Sqlite, or Postgresql)"
    
def printMessage(str):
  logger.info(str)
  if sys.executable.find("python.exe") != -1:
     print(str)
  else:
     try:
       arcpy.AddMessage(str)
     except Exception as e:
       print(str)

def main():
    tbx=Toolbox()
    tool=CreateNewProject()

    pg=None
    #"user=postgres dbname=gis host=192.168.99.100"
    #set dummy values
    user="user"
    host="my.host.com"
    #db="collectorDb.sqlite"
    mxd=None
    output="../collector"
    spatialite_path="../arcrestgo/spatialite/spatialite.exe"
    gdal_path="../arcrestgo/gdal/"
    cert=""
    pem=""
    datasrc=""

    #load settings
    Config.read(os.getcwd()+"/settings.ini")
    try:
        host = Config.get("settings","server")
    except Exception as e:
        pass

    try:
        user= Config.get("settings","username")
    except Exception as e:
        pass

    try:
        output= Config.get("settings","destination")
    except Exception as e:
        pass
        
    if not output:
        output=os.getcwd().replace("\\","/")

    try:
        mxd= Config.get("settings","mxd")
    except Exception as e:
        pass        

    #try:
    #    db= Config.get("settings","sqlitedb")
    #except Exception as e:
    #    pass        

    try:
        pg= Config.get("settings","pg")
    except Exception as e:
        pass        

    try:
        pem= Config.get("settings","pem")
    except Exception as e:
        pass        

    try:
        cert= Config.get("settings","cert")
    except Exception as e:
        pass        

    try:
        spatialite_path= Config.get("settings","spatialite_path")
    except Exception as e:
        pass        

    try:
        gdal_path= Config.get("settings","gdal_path")
    except Exception as e:
        pass      

    try:
        datasrc= Config.get("settings","datasrc")
    except Exception as e:
        pass      

    if len(sys.argv)==1 and not mxd and not host and not user and not output and not spatialite_path and not gdal_path:
        printUsage()
        return

    #print "This is the name of the script: ", sys.argv[0]
    #print "Number of arguments: ", len(sys.argv)
    #print "The arguments are: " , str(sys.argv)
    for i in xrange(0,len(sys.argv)):
        if sys.argv[i] == "-user":
            user=sys.argv[i+1]
        elif sys.argv[i]=="-host":
            host = sys.argv[i+1]
        #elif sys.argv[i]=="-db":
        #    db = sys.argv[i+1]
        elif sys.argv[i]=="-mxd":
            mxd = sys.argv[i+1]
        elif sys.argv[i]=="-root":
            root_path = sys.argv[i+1]
        elif sys.argv[i]=="-pg":
            pg = sys.argv[i+1]
        elif sys.argv[i]=="-spatialite_path":
            spatialite_path = sys.argv[i+1]
        elif sys.argv[i]=="-gdal_path":
            gdal_path = sys.argv[i+1]
        elif sys.argv[i]=="-cert":
            cert = sys.argv[i+1]
        elif sys.argv[i]=="-pem":
            pem = sys.argv[i+1]
        elif sys.argv[i]=="-src":
            datasrc = sys.argv[i+1]
        elif sys.argv[i]=="-h":
            printUsage()
            return

    tool.execute(tool.getParameterInfo(),[mxd,host,user,datasrc,output,pg,spatialite_path,gdal_path,cert,pem])
    
if __name__ == '__main__':
    if sys.executable.find("python.exe") != -1:
       main()
