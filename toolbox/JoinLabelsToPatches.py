"""
This is the code that is executed by ArcGIS Pro when the geoprocessing tool is ran. Includes the user inputs to the
tool, code to join the events fields to the patches if they do not already exist, or updates the existing events fields
if they do exist.
"""
import arcpy
import os
from datetime import datetime
import eventsFunctions


# === USER INPUTS === #
# Patches feature class to join labels to
patches_fc = arcpy.GetParameterAsText(0)
# Checkbox for creating a backup
create_backup = arcpy.GetParameter(1)
# Backup geodatabase folder
backup_path = arcpy.GetParameterAsText(2)
# Table with the labels to join
events_tbl = arcpy.GetParameterAsText(3)

# === CREATE COPY OF RUN GDB (if applicable) === #
if create_backup:
    # Extract the geodatabase path
    run_gdb_path = arcpy.Describe(patches_fc).path

    # Get the geodatabase name
    run_gdb_name = os.path.basename(run_gdb_path)
    run_gdb_name_no_ext = os.path.splitext(run_gdb_name)[0]

    # Get today's date in YYYYMMDD format
    today_date = datetime.today().strftime('%Y%m%d')

    # Create backup gdb path
    backup_gdb_name = f"{run_gdb_name_no_ext}_backup_{today_date}.gdb"
    backup_gdb_path = os.path.join(backup_path, backup_gdb_name)

    # Make the backup
    arcpy.management.Copy(run_gdb_path, backup_gdb_path)

# === JOIN/UPDATE LABELS === #
# Get a list of fields in patches feature class before joining the event fields
patches_fields = [f.name for f in arcpy.ListFields(patches_fc)]
# Check if field EventType exists, if it does assume the rest of the event fields exist as well
event_fields_exist = "EventType" in patches_fields

# Join event fields to patches
arcpy.management.JoinField(
    in_data=patches_fc,
    in_field="PatchName",
    join_table=events_tbl,
    join_field="PatchName",
    fields="EventType;ChangeType;Confidence;AltType;ChangeDesc;DistYear;DistName",
    fm_option="NOT_USE_FM",
    field_mapping=None,
    index_join_fields="NO_INDEXES"
)

# Update event fields if they already exist, otherwise, we don't have to do anything.
if event_fields_exist:
    eventsFunctions.update_event_fields(patches_fc)
