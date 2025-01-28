"""
Functions to support adding attributes to patches and other processes.
* set_default_gdb_workspace()
* rename_field()
* select_calculate()
* zonal_stats_rename_field()
* del_existing_fields()
* del_select_patches()
* update_area_perim()
"""
import arcpy


def set_default_gdb_workspace():
    """
    Get the default geodatabase and sets as the workspace.

    :return: str, the default project geodatabase.
    """
    # GET DEFAULT GDB TO USE FOR TEMPORARY FILES
    # Specify the path to the current ArcGIS Pro project (.aprx)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    # Get the default geodatabase from the project
    default_gdb = aprx.defaultGeodatabase

    # Set default geodatabase as workspace
    arcpy.env.workspace = default_gdb

    return default_gdb


def rename_field(fc, old_fields, new_fields, field_types=None, field_lengths=None):
    """
    Renames fields in a feature class by creating a new field, copying values from old field, and deleting old field.
    Returns nothing.

    :param fc: str, the file path of the feature class with fields to rename.
    :param old_fields: list, existing field names to be renamed.
    :param new_fields: list, new field names to rename existing field with.
    :param field_lengths:
    :param field_types:
    """
    # If inputs are not a list, turn them into a list
    if not isinstance(old_fields, list):
        old_fields = [old_fields]
        new_fields = [new_fields]
        field_types = [field_types]
        field_lengths = [field_lengths]

    # Iterate through each field
    for i in range(len(old_fields)):
        # Add a new field with the appropriate field type and length, if applicable
        arcpy.management.AddField(
            in_table=fc,
            field_name=new_fields[i],
            field_type=field_types[i],
            field_length=field_lengths[i],
            field_is_nullable="NULLABLE"
        )

        # Populate with old_field values to basically change the field name
        arcpy.management.CalculateField(
            in_table=fc,
            field=new_fields[i],
            expression=f"!{old_fields[i]}!",
            expression_type="PYTHON3",
        )

    # Delete old field(s)
    arcpy.management.DeleteField(
        in_table=fc,
        drop_field=old_fields
    )


def select_calculate(in_fc, select_fc, relationship, field):
    """
    Selects input point features that intersects the selecting polygon features and populates the desired field with
    1 (True), inverts the selection, and populates the field with 0 (False). Returns nothing.

    :param in_fc: str, the file path to the input point feature class to add the field to and populate using the
    selecting polygon feature class.
    :param select_fc: str, the file path to the selecting polygon feature class used to select features in the input
    point feature class.
    features
    :param relationship: str, the type of selection relationship between input and selecting features.
    :param field: str, the name of the field to create and populate.
    """
    # Create a layer so features can be selected
    in_lyr = "in_layer"
    arcpy.management.MakeFeatureLayer(in_fc, in_lyr)
    select_lyr = "select_layer"
    arcpy.management.MakeFeatureLayer(select_fc, select_lyr)

    # Select point features that intersect polygon features and add 1/True to field
    arcpy.management.SelectLayerByLocation(
        in_layer=in_lyr,
        overlap_type=f"{relationship}",
        select_features=select_lyr,
        search_distance=None,
        selection_type="NEW_SELECTION",
        invert_spatial_relationship="NOT_INVERT"
    )

    arcpy.management.CalculateField(
        in_table=in_lyr,
        field=field,
        expression='1',
        expression_type="PYTHON3",
        field_type="SHORT"
    )

    # Invert selection and add 0/False to field
    arcpy.management.SelectLayerByLocation(
        in_layer=in_lyr,
        overlap_type=f"{relationship}",
        select_features=select_lyr,
        search_distance=None,
        selection_type="NEW_SELECTION",
        invert_spatial_relationship="INVERT"
    )

    arcpy.management.CalculateField(
        in_table=in_lyr,
        field=field,
        expression='0',
        expression_type="PYTHON3",
        field_type="SHORT"
    )


def zonal_stats_rename_field(fc, rst, zone_field, stat_type, field_name, field_type):
    """
    Runs Zonal Statistics as Table for the statistics type specified, then joins that field to the feature class. The
    field is renamed to the desired field name. Zonal Statistics table is deleted. Returns nothing.

    :param fc: str, the file path of the feature class to add zonal stats field to.
    :param rst: str, the file path of the raster that will provide the stats.
    :param zone_field: str, the field name of the feature class unique identifier.
    :param stat_type: str, the zonal statistic to calculate.
    :param field_name: str, the desired name of the zonal stats field.
    :param field_type:
    """
    # Check the spatial reference and project the raster if necessary
    if arcpy.Describe(fc).spatialReference.name != arcpy.Describe(rst).spatialReference.name:
        proj_raster = "proj_raster"

        arcpy.management.ProjectRaster(
            in_raster=rst,
            out_raster=proj_raster,
            out_coor_system=arcpy.Describe(fc).spatialReference,
            resampling_type="NEAREST"
        )

        rst = proj_raster

    # Define the table
    zonal_stats_tbl = "zonal_stats_tbl"

    # Run Zonal Statistics As Table
    arcpy.ia.ZonalStatisticsAsTable(
        in_zone_data=fc,
        zone_field=zone_field,
        in_value_raster=rst,
        out_table=zonal_stats_tbl,
        ignore_nodata="DATA",
        statistics_type=stat_type,
        process_as_multidimensional="CURRENT_SLICE",
        percentile_values=[90],
        percentile_interpolation_type="AUTO_DETECT",
        circular_calculation="ARITHMETIC",
        circular_wrap_value=360
    )

    # Keep field names as-is when joining zonal stats field to shapefile
    arcpy.env.qualifiedFieldNames = False
    # Join the desired zonal stats field to the shapefile
    arcpy.management.JoinField(
        in_data=fc,
        in_field=zone_field,
        join_table=zonal_stats_tbl,
        join_field=zone_field,
        fields=stat_type,
        fm_option="NOT_USE_FM",
        field_mapping=None,
        index_join_fields="NO_INDEXES"
    )

    rename_field(fc, stat_type, field_name, field_type)

    # Clean up GDB
    arcpy.management.Delete(zonal_stats_tbl)

    if ('proj_raster' in locals()) or ('proj_raster' in globals()):
        arcpy.management.Delete(proj_raster)


def del_existing_fields(fc):
    """
    Deletes attribute fields that already exist so they can be recalculated since the attribute functions are not
    written to update existing attribute fields, only add them. Returns nothing.

    :param fc: str, the file path of the feature class to add zonal stats field to.
    """
    # Get a list of fields
    fields = [f.name for f in arcpy.ListFields(fc)]

    # Attribute fields to check
    attr_fields = [
        'CoordType',
        'X_Coord_m',
        'Y_Coord_m',
        'UTMX',
        'UTMY',
        'Latitude',
        'Longitude',
        'WildName',
        'LandMgmt',
        'Watershed',
        'InPark',
        'InBuffer',
        'InMask',
        'Protected',
        'EastWest',
        'VegCode',
        'ElevMean',
        'SlopeMean',
        'Aspect',
        'paratio'
    ]

    # Compare feature class fields with attribute fields and make a list of only the ones that match
    fields_to_del = [f for f in attr_fields if f in fields]

    # Check if there are fields to delete
    if len(fields_to_del) > 0:
        # Join fields into a string to use in DeleteField if there is more than one field
        fields_string = ";".join(fields_to_del)

        arcpy.management.DeleteField(
            in_table=fc,
            drop_field=fields_string,
            method="DELETE_FIELDS"
        )


def del_select_patches(all_patches, patches_fc):
    """
    Used to delete selected patches when running Add Attributes to Select Patches & Export CSV geoprocessing tool. If
    no patches are selected, the select patches feature class is used to select identical patches. Returns nothing.

    :param all_patches: str, feature class or feature layer containing all patches along with the selected patches.
    :param patches_fc: str, feature class containing only the selected patches.
    """
    # Set layer variable to the input patches
    patches_lyr = all_patches

    # Get feature class info to check if the input patches are already a layer
    desc = arcpy.Describe(all_patches)
    # If it's not a feature layer
    if desc.dataType != "FeatureLayer":
        # Create a feature layer
        patches_lyr = "patches_layer"
        arcpy.management.MakeFeatureLayer(all_patches, patches_lyr)

    # Find out how many patches are selected
    select_count = arcpy.management.GetCount(patches_lyr)

    # Select the patches if none are selected, otherwise all features will be deleted
    if int(select_count[0]) == 0:
        # Create a layer for select patches
        select_lyr = "select_layer"
        arcpy.management.MakeFeatureLayer(patches_fc, select_lyr)

        # Select patches that are identical to the select patches
        arcpy.management.SelectLayerByLocation(
            in_layer=patches_lyr,
            overlap_type=f"ARE_IDENTICAL_TO",
            select_features=select_lyr,
            search_distance=None,
            selection_type="NEW_SELECTION",
            invert_spatial_relationship="NOT_INVERT"
        )

    arcpy.management.DeleteFeatures(patches_lyr)


def update_area_perim(patches_fc):
    """
    Updates the area and perim fields with Shape_Area and Shape_Length values since those fields are not updated when a
    patch is clipped, split, or merged. Returns nothing.

    :param patches_fc: str, the file path of the feature class that needs area and perim fields updated.
    """
    # Function to use in calculate field, only change area or perim if they are different from Shape_Area or
    # Shape_Length, and round area and perim to a whole number.
    code = """def update(orig, new):
                        if orig == new:
                            return orig
                        else:
                            return round(new) """

    # Update the area and perim fields, if applicable
    arcpy.management.CalculateField(
        in_table=patches_fc,
        field="area",
        expression="update(!area!, !Shape_Area!)",
        expression_type="PYTHON3",
        code_block=code,
        field_type="LONG"
    )

    arcpy.management.CalculateField(
        in_table=patches_fc,
        field="perim",
        expression="update(!perim!, !Shape_Length!)",
        expression_type="PYTHON3",
        code_block=code,
        field_type="LONG"
    )
