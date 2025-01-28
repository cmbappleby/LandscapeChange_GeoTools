"""
This is the code that is executed by ArcGIS Pro when the geoprocessing tool is ran. Includes the user inputs to the
tool, creating the necessary file paths needed for adding attributes, creates a feature class for the patches, and
calls the primary function that actually adds the attributes to the patches. Then the Park and PatchName attributes are
added to the feature class. Lastly, the patches are exported to a CSV for uploading into the database.
"""
import arcpy
import os
import addAttr
import addAttrFunctions
import addAttrUtils
import expPatchesFunctions

# Input feature class
all_patches = arcpy.GetParameterAsText(0)
# GDB with attribute features classes, rasters, and table
park_gdb = arcpy.GetParameterAsText(1)

# ZONAL GEOMETRY PARAMETERS (FOR THICKNESS, MAJORAXIS, MINORAXIS, AND ORIENTATION)
# Field containing values that define each zone
zone_field = arcpy.GetParameterAsText(2)
# Processing cell size
pro_cell_size = arcpy.GetParameterAsText(3)
pro_cell_size = int(pro_cell_size)

# Output folder for CSV and file name
out_folder = arcpy.GetParameterAsText(4)
out_name = arcpy.GetParameterAsText(5)

# Create path
if not out_name.endswith(".csv"):
    out_name = f"{out_name}.csv"
out_csv = os.path.join(out_folder, out_name)

# Get park name from park GDB
park = os.path.basename(park_gdb)[:4]

# Create path with just park prefix
park_path = os.path.join(park_gdb, f"{park}_")

# Prevent outputs from being added to the map
arcpy.env.addOutputsToMap = False

# Get/set default geodatabase
gdb = addAttrUtils.set_default_gdb_workspace()
# Create path for patches feature class
patches_fc = os.path.join(gdb, f"select_{all_patches}")
# Copy feature class to default_gdb
arcpy.management.CopyFeatures(
    in_features=all_patches,
    out_feature_class=patches_fc
)

# Add the attributes using the primary function
addAttr.add_attr_patches(
    patches_fc,
    zone_field,
    pro_cell_size,
    park,
    park_path,
    False,
    False
)

# Update the area and perim fields
addAttrUtils.update_area_perim(patches_fc)

# Add paratio, must happen after area and perim fields are updated
addAttrFunctions.add_paratio(patches_fc)

# Delete selected features from input feature class
addAttrUtils.del_select_patches(all_patches, patches_fc)

# Add the select patches to all_patches
arcpy.management.Append(patches_fc, all_patches, schema_type="TEST_AND_SKIP")

# Export patches to CSV
expPatchesFunctions.export_patches_csv(patches_fc, out_csv)

# Clean up the default geodatabase
arcpy.management.Delete(patches_fc)
