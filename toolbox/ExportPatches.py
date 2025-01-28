"""
This is the code that is executed by ArcGIS Pro when the geoprocessing tool is ran. Includes the user inputs to the
tool, getting a list of feature classes to process, looping through them and either exporting them as a CSV or as a
shapefile for Google Earth Engine.
"""
import arcpy
import os
import expPatchesFunctions


# === USER INPUTS === #
# Run geodatabase containing all the changeDB feature classes for the parks
run_gdb = arcpy.GetParameterAsText(0)
# OPTIONAL, user can select individual feature classes instead of processing all feature classes in the run_gdb
out_fcs = arcpy.GetParameter(1)
# OPTIONAL, checkbox to export as CSV
export_csv = arcpy.GetParameter(2)
# Output folder to save the CSVs to
csv_out_folder = arcpy.GetParameterAsText(3)
# OPTIONAL, checkbox to export for GEE
export_gee = arcpy.GetParameter(4)
# Output folder to save the shapefiles to
gee_out_folder = arcpy.GetParameterAsText(5)

# === CHECK PATCHES AND EXPORT === #
# Set worksspace to the run GDB
arcpy.env.workspace = run_gdb

# If the user selected individual feature classes
if out_fcs:
    # If it's not a list, make it a list
    if not isinstance(out_fcs, list):
        patches_fcs = [out_fcs]
    else:
        patches_fcs = out_fcs
else:
    # Get a list of the patches feature classes
    patches_fcs = arcpy.ListFeatureClasses()

no_export_csv = False
no_export_gee = False

# Loop through each feature class
for fc in patches_fcs:
    # Prevent outputs from being added to the map
    arcpy.env.addOutputsToMap = False

    # Create patches feature class file path
    patches_fc = os.path.join(run_gdb, fc)

    # Export to CSV
    if export_csv:
        # See if the CSV output folder contains park folders
        # Get the list of folders
        csv_out_folder_list = [
            entry.name for entry in os.scandir(csv_out_folder)
            if entry.is_dir()
        ]

        # Get the park code from the feature class name
        park_code = fc[:4]

        # Check if the folder exists
        if park_code in csv_out_folder_list:
            # Change output folder to park folder
            csv_save_folder = os.path.join(csv_out_folder, park_code)
        else:
            # Change output folder to a folder called Patches
            csv_save_folder = os.path.join(csv_out_folder, "Patches_CSV")
            # Check if folder exists
            if not os.path.exists(csv_save_folder):
                os.mkdir(csv_save_folder)

        # Create output file path
        patches_name = os.path.basename(patches_fc)
        years = patches_name[-9:]
        out_file = f"{park_code}_patches_{years}.csv"
        out_fp = os.path.join(csv_save_folder, out_file)

        # Check if file already exists, if it does, add a suffix to it until it doesn't
        while os.path.exists(out_fp):
            out_file = f"{out_file[:-4]}_1.csv"
            out_fp = os.path.join(csv_out_folder, out_file)

        # Run function to export
        no_export_csv_fc = expPatchesFunctions.export_patches_csv(patches_fc, out_fp)
        no_export_csv = no_export_csv or no_export_csv_fc

    # Export for GEE
    if export_gee:
        no_export_gee_fc = expPatchesFunctions.export_patches_shp(patches_fc, gee_out_folder)
        no_export_gee = no_export_gee or no_export_gee_fc

if no_export_csv or no_export_gee:
    arcpy.AddError(f"One of more patches feature class was not exported. Check error messages.")
    raise arcpy.ExecuteError
