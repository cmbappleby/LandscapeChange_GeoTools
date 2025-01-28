"""
Functions to support processing related to Event fields (EventType, ChangeType, Confidence, AltType, ChangeDesc,
EventDate, LabeledBy, PriorRun, PostDist, DistName, DistYear, and Split).
* add_event_fields()
* label_elev_mask()
* label_water_mask()
* add_annual_var()
* update_event_fields()
"""
import arcpy
from datetime import date


def add_event_fields(patches_fc):
    """
    Adds Event fields to the patches and populates the Split field. Returns nothing.

    :param patches_fc: str, the file path of the feature class to add the fields to.
    """
    # Create lists of field names, types, and lengths to loop through and add fields
    field_names = ["EventType", "ChangeType", "Confidence", "AltType", "ChangeDesc", "EventDate", "LabeledBy",
                   "PriorRun", "PostDist", "DistName", "DistYear", "Split", "MapPatch"]
    field_types = ["TEXT", "TEXT", "SHORT", "TEXT", "TEXT", "TEXT", "TEXT", "SHORT", "SHORT", "TEXT", "SHORT", "SHORT",
                   "TEXT"]
    field_lengths = [10, 25, None, 25, 500, 10, 50, None, None, 100, None, None, 50]

    # Loop through and add fields
    for i in range(len(field_names)):
        arcpy.management.AddField(
            in_table=patches_fc,
            field_name=field_names[i],
            field_type=field_types[i],
            field_length=field_lengths[i],
            field_is_nullable="NULLABLE"
        )

    # Set Split field to 0/False
    arcpy.management.CalculateField(
        in_table=patches_fc,
        field="Split",
        expression=0,
        expression_type="PYTHON3"
    )


def label_elev_mask(patches_fc):
    """
    Selects patches in the elevation mask and calls add_annual_var() to add Annual Variability label. Returns nothing.

    :param patches_fc: str, the file path of the feature class to add the labels to.
    """
    # Create a layer with features in mask
    in_lyr = "in_layer"
    arcpy.management.MakeFeatureLayer(patches_fc, in_lyr, where_clause="InMask = 1")

    # Calculate necessary fields
    add_annual_var(in_lyr)


def label_water_mask(patches_fc, water_fc):
    """
    Selects pathes that are fully inside the water mask and calls add_annual_var() to add Annual Variability label.
    Returns nothing.

    :param patches_fc: str, the file path of the feature class to add the labels to.
    :param water_fc: str, the file path to the water mask feature class.
    """
    # Create a layer
    in_lyr = "in_layer"
    arcpy.management.MakeFeatureLayer(patches_fc, in_lyr)

    # Select patches fully within water mask
    arcpy.management.SelectLayerByLocation(
        in_layer=in_lyr,
        overlap_type="COMPLETELY_WITHIN",
        select_features=water_fc,
        search_distance=None,
        selection_type="NEW_SELECTION",
        invert_spatial_relationship="NOT_INVERT"
    )

    # Calculate necessary fields
    add_annual_var(in_lyr)


def add_annual_var(fc):
    """
    Populates the applicable Event fields for the selected patches with Annual Variability label. Fields populated:
    EventType - Mask, ChnageType - Annual Variability, Confidence - 2, EventDate - today's date, LabeledBy -
    Geoprocessing, PriorRun - 0, and PostDist - 0. Returns nothing.

    :param fc: str, the feature layer with the selected patches to add the Annual Variability label to.
    """
    # Lists of fields and values for the fields to loop through
    fields = ["EventType", "ChangeType", "Confidence", "EventDate", "LabeledBy", "PriorRun", "PostDist"]
    values = ["Mask", "Annual Variability", 2, str(date.today()), "Geoprocessing", 0, 0]

    # Loop through the lists and populate the fields with the corresponding values
    for i in range(len(fields)):
        arcpy.management.CalculateField(
            in_table=fc,
            field=fields[i],
            expression=f'"{values[i]}"',
            expression_type="PYTHON3"
        )


def update_event_fields(patches_fc):
    """
    Updates existing Events fields with values from joined Events fields, then deletes the joined Events fields.
    Retunrs nothing.

    :param patches_fc: str, the file path of the feature class with Event fields to update.
    """
    # List of field to update
    patches_fields = [
        "EventType",
        "ChangeType",
        "Confidence",
        "AltType",
        "ChangeType",
        "DistYear",
        "DistName"
    ]
    # List of fields that contain the values
    value_fields = [
        "EventType_1",
        "ChangeType_1",
        "Confidence_1",
        "AltType_1",
        "ChangeType_1",
        "DistYear_1",
        "DistName_1"
    ]

    # Loop through the lists and update the fields
    for i in range(len(patches_fields)):
        arcpy.management.CalculateField(
            in_table=patches_fc,
            field=patches_fields[i],
            expression=f'!{value_fields[i]}!',
            expression_type="PYTHON3"
        )

    # Delete fields that were joined
    arcpy.management.DeleteField(patches_fc, value_fields)
