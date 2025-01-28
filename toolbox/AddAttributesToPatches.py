"""
The purpose of this tool is to process all the shapefiles (patches) from a LandTrendr run by adding attributes and
saving all the patches from all years into one feature class.

This is the code that is executed by ArcGIS Pro when the geoprocessing tool is ran. Includes the user inputs to the
tool, creating the necessary file paths needed for adding attributes, loops through each shapefile calls the primary
function that actually adds the attributes to the patches and creates one feature class for all the change years. After
all shapefiles have been processed, the Park and PatchName attributes are added to the feature class for all the change
years. Next, the Event fields are added (if applicable), and labels are added to patches that are in the elevation mask.
"""
import arcpy
import os
import addAttr
import addAttrFunctions
import addAttrUtils
import eventsFunctions


# === User inputs === #
# Shapefiles/feature classes folder
patches_folder = arcpy.GetParameterAsText(0)
# Checkbox for resuming previous run
resume_prev = arcpy.GetParameter(1)
# Optional shapefile year to start with
shp_yr = arcpy.GetParameterAsText(2)
# GDB with attribute features classes, rasters, and table
park_gdb = arcpy.GetParameterAsText(3)
# Checkbox for whether to clip patches to study area
clip_patches_sa = arcpy.GetParameter(4)

# Minimum mapping unit for PatchName
mmu = arcpy.GetParameterAsText(5)
mmu = int(mmu)


# ZONAL GEOMETRY PARAMETERS (FOR THICKNESS, MAJORAXIS, MINORAXIS, AND ORIENTATION)
# Field containing values that define each zone
zone_field = arcpy.GetParameterAsText(6)
# Processing cell size
pro_cell_size = arcpy.GetParameterAsText(7)
pro_cell_size = int(pro_cell_size)

# Output GDB for the feature class with all years
run_gdb = arcpy.GetParameterAsText(8)

# Checkbox for whether to add Event fields and mask labels
events_mask = arcpy.GetParameter(9)

# Get park name from park GDB
park = os.path.basename(park_gdb)[:4]
# Create path for the output feature class
changeDB_fc = os.path.join(run_gdb, f"{park}_changeDB")

# Create path with just park prefix
park_path = os.path.join(park_gdb, f"{park}_")

# === ADD ATTRIBUTES AND CREATE CHANGEDB.SHP === #
# GET A LIST OF ALL SHAPEFILES IN THE FOLDER
# Change current working directory to patch_folder
arcpy.env.workspace = patches_folder
# Get a list of all the shapefiles in the patches_folder
shps = arcpy.ListFiles("*.shp")
# Keep only shapefiles that end in a year (four-digit number)
shps = [shp for shp in shps if shp[-8:-4].isdigit()]

# Initally set year to start with to zero
yr_index = 0

# Variables to hold the feature classes to check for overlapping patches
# Need to be declared before if shp_yr and if resume_prev
prev_fc = None
base_fc = None

# Variable for patches_fc needs to be set before if resume_prev
patches_fc = None

# If resuming from previous run or a shp_yr was specified
# This code needs to run if either was selected by the user
if resume_prev or shp_yr:
    # Get the last year in changeDB_fc
    if arcpy.Exists(changeDB_fc):
        # Get last year for prev_fc
        yrs = [row[0] for row in arcpy.da.SearchCursor(changeDB_fc, ["yod"])]
        last_yr = max(yrs)

        try:
            # Get the index of that year to start at that index
            if resume_prev:
                # Resume with the year after the last one in changeDB
                resume_yr = last_yr + 1
                yr_index = shps.index(f"change_{resume_yr}.shp")
            if shp_yr:
                yr_index = shps.index(f"change_{shp_yr}.shp")
        except ValueError:
            arcpy.AddError("The shapefile for the year to resume with was not found.")
            raise arcpy.ExecuteError

        # Set workspace to default gdb
        default_gdb = addAttrUtils.set_default_gdb_workspace()
    else:
        arcpy.AddError(f"{changeDB_fc} does not exist. Cannot resume adding attributes.")
        raise arcpy.ExecuteError

# If resuming a previous run of the tool that was interrupted by non-persistent error/failure
if resume_prev:
    # Get a list of all the feature classes in the default GDB that start with change_*
    # There should be two
    fc_list = arcpy.ListFeatureClasses("change_*")

    # Set overlapping patches variables to the change fcs if there are two
    if len(fc_list) == 2:
        # Get the year of the first fc
        prev_yr = int(fc_list[0][-4:])

        # Only set patch variables if first fc matches the last year in changeDB_fc
        # PyCharm warns that last_yr and default_gdb can be undefined, but it can't because an error will be raised and
        # the tool will stop before it gets to this point if they cannot be defined
        if prev_yr == last_yr:
            # Although the layer is for the previous year's patches, in the loop, prev_fc gets set to base_fc
            base_fc = os.path.join(default_gdb, fc_list[0])
            patches_fc = os.path.join(default_gdb, fc_list[1])
    else:
        arcpy.AddError("Patches feature classes for resuming previous run could not be found in the default "
                       "geodatabase. Try using the 'Year to Resume With' parameter instead.")
        raise arcpy.ExecuteError

# If the user entered a Year to Start With,
if shp_yr:
    # Although the layer is for the previous year's patches, in the loop, prev_fc gets set to base_fc
    base_fc = os.path.join(default_gdb, f"change_{shp_yr}")

    # Select patches for the last year in the chnageDB
    arcpy.management.SelectLayerByAttribute(
        changeDB_fc,
        'NEW_SELECTION',
        f'yod = {last_yr}',
        'NON_INVERT'
    )

    # Create a feature class in the default geodatabase
    arcpy.management.CopyFeatures(changeDB_fc, base_fc)

# ADD ATTRIBUTES TO EACH SHAPEFILE
for i in range(yr_index, len(shps)):
    # Prevent outputs from being added to the map
    arcpy.env.addOutputsToMap = False
    # Get and set the default gdb as the workspace
    gdb = addAttrUtils.set_default_gdb_workspace()

    # If resuming a previous run and it's the first iteration, patches_fc is already set
    if resume_prev and (i == yr_index):
        # Need to delete existing attribute fields so they can be calculated again
        addAttrUtils.del_existing_fields(patches_fc)
    else:
        # GET SHAPEFILE, SHAPEFILE NAME, FILEPATH, AND SET ENVIRONMENT
        # Get the shapefile name
        shp = shps[i]
        # Get shapefile basename sans .shp
        shp_name = shp[:-4]
        # Create the filepath for the shapefile
        shp_fp = os.path.join(patches_folder, shp)

        # Convert shapefile to feature class
        arcpy.conversion.FeatureClassToGeodatabase(shp_fp, gdb)
        # Create path for feature class
        patches_fc = os.path.join(gdb, shp_name)

    # Add the attributes using the primary function
    addAttr.add_attr_patches(
        patches_fc,
        zone_field,
        pro_cell_size,
        park,
        park_path,
        clip_patches_sa,
        mmu
    )

    # Add paratio, must happen separate since Add Attributes to Select Patches also utilizes addAttr.add_attr_patches(),
    # and area and perim do not get updated until after addAttr.add_attr_patches().
    addAttrFunctions.add_paratio(patches_fc)

    # Add Event fields, elevation mask, and water/lakes mask
    if events_mask:
        eventsFunctions.add_event_fields(patches_fc)

        if park != "LEWI":
            eventsFunctions.label_elev_mask(patches_fc)

        # Water mask feature class for labeling patches with Annual Variability
        water_fc = f"{park_path}water_fc"
        eventsFunctions.label_water_mask(patches_fc, water_fc)

    # The base from the last loop becomes the previous, and current patches become base
    prev_fc = base_fc
    base_fc = patches_fc

    # Add the field just in case there are no overlapping pataches (and for the first year of patches)
    arcpy.management.AddField(
        in_table=patches_fc,
        field_name="OverlapPrv",
        field_type="SHORT",
        field_is_nullable="NULLABLE"
    )

    # prev_fc will be None for the first year in the patches folder
    if prev_fc:
        # Find and flag overlapping patches
        addAttrFunctions.add_overlap_prev(base_fc, prev_fc, park, events_mask)

        # Clean up the default geodatabase
        arcpy.management.Delete(prev_fc)

    # CREATE/ADD PATCHES TO FINAL FEATURE CLASS
    # Create a new feature class if it doesn't exist
    if not arcpy.Exists(changeDB_fc):
        arcpy.management.CopyFeatures(patches_fc, changeDB_fc)
    # Append if it does
    else:
        arcpy.management.Append(patches_fc, changeDB_fc, schema_type="TEST_AND_SKIP")

# Clean up the default geodatabase after
arcpy.management.Delete(base_fc)

# Get start year and end year for PatchName and to change the GDB name
yrs = [row[0] for row in arcpy.da.SearchCursor(changeDB_fc, ["yod"])]
start_yr = min(yrs)
end_yr = max(yrs)

# Add Park and PatchName
addAttrFunctions.add_park_patch_name(changeDB_fc, park, mmu, start_yr, end_yr)

# Rename changeDB
new_changeDB_fc = f"{park}_changeDB_{start_yr}_{end_yr}"
arcpy.env.workspace = run_gdb
arcpy.management.Rename(changeDB_fc, new_changeDB_fc, "FeatureClass")
