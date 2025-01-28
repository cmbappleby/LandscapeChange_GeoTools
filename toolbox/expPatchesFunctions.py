"""
Functions to support exporting patches as CSV or for GEE.
* primary_validation()
* extract_data()
* clean_data()
* check_mismatch()
* check_change_types()
* check_confidence()
* check_duplicate_patch_names()
* check_fields_have_values()
* exp_shp_spec_fields()
* export_patches_csv()
* export_patches_shp()
"""
import os.path
import arcpy
import pandas as pd
from sqlalchemy import create_engine
import csv


def primary_validation(patches_fc, patches_fields, csv_exp):
    """
    This is the primary validation function for export tools. This function calls other functions to extract patches
    attribute table to a pandas data frame, clean the data (if applicable), and perform validation checks.

    :param patches_fc: str, the file path to the patches feature class.
    :param patches_fields: list,list of fields to be extracted from the feature class.
    :param csv_exp: Boolean, whether the export is to CSV, if it is, then the data are cleaned the data before
    performing checks; also passed to check_confidence because we only care if the Confidence value is valid.
    :return: Boolean and DataFrame, whether the validation checks passed and data is good for export and a pandas
    data frame with the patches_fc data.
    """
    # Extract the data
    csv_df = extract_data(patches_fc, patches_fields)

    # Clean the data if exporting to CSV
    if csv_exp:
        csv_df = clean_data(csv_df)
    else:  # Only want rows with Events when exporting for GEE
        csv_df = csv_df[csv_df["EventType"].notna() &
                        (csv_df["EventType"] != "Mask") &
                        (csv_df["EventType"] != "Model")]

    # Variable no_export... to keep track of issues, that way all the checks will be performed before stopping the tool
    # but before saving the CSV.
    # Check that the change types match the database change types
    no_export_change_type = check_change_types(csv_df)

    # Check that confidence values are valid
    no_export_conf = check_confidence(csv_df, csv_exp)

    # Check for duplicate patch names
    no_export_dup_patch_names = check_duplicate_patch_names(csv_df)

    # Only need one True to cancel the export
    no_export = no_export_conf or no_export_change_type or no_export_dup_patch_names

    return no_export, csv_df


def extract_data(patches_fc, patches_fields):
    """
    Compares the field names of the patches feature class with a list of fields, creates a list of fields that the
    feature class is missing, and reads only fields that match from the feature class attribute table into a pandas
    data frame. The fields that are missing are added to the data frame and populated with nulls/NAs.

    :param patches_fc: str, the file path to the patches feature class.
    :param patches_fields: list,list of fields to be extracted from the feature class.
    :return: data frame, the feature class attribute table with required fields/columns.
    """
    # Get a list of all the feature class fields
    fc_fields = [f.name for f in arcpy.ListFields(patches_fc)]

    # Compare feature class fields with data.Patches fields and make a list of only the ones that match
    fields_to_export = [f for f in patches_fields if f in fc_fields]

    # Get a list of fields not in feature class to display as a message
    missing_fields = [f for f in patches_fields if f not in fc_fields]

    if len(missing_fields) > 0:
        arcpy.AddWarning(f'The following data.Patches fields were not found in the feature class: {missing_fields}.')

    # Create an empty list to hold the data
    csv_data = []

    # Use SearchCursor to extract the data from the feature class
    with arcpy.da.SearchCursor(patches_fc, fields_to_export) as cursor:
        for row in cursor:
            csv_data.append(row)

    # Create a dataframe from the data
    csv_df = pd.DataFrame(csv_data, columns=fields_to_export)

    # Add the missing fields to the dataframe with null/NA values
    for missing_field in missing_fields:
        csv_df[missing_field] = pd.NA

    # Reorder the dataframe columns to match patches_fields list
    csv_df = csv_df[patches_fields]

    return csv_df


def clean_data(csv_df):
    """
    Shapefiles cannot hold null values. As a result, numeric fields that should be null are 0, and text fields that
    should be null contain a single space. In case the patches were imported as a feature class from a shapefile, the
    data is cleaned by converting the zeros and empty spaces to null/NA.

    :param csv_df: data frame, the feature class attribute table with required fields/columns.
    :return: data frame, the cleaned feature class attribute table with required fields/columns.
    """
    # Replace any zeros with null/NA
    csv_df[["Confidence", "DistYear"]] = csv_df[["Confidence", "DistYear"]].replace(0, pd.NA)

    # Replace single spaces with null/NA
    csv_df[["EventType", "ChangeType", "AltType", "ChangeDesc", "DistName"]] = (
        csv_df[["EventType", "ChangeType", "AltType", "ChangeDesc", "DistName"]].replace(" ", pd.NA))

    # Remove anything that might mess with the SQL Server import
    csv_df = csv_df.replace(r'[\r\n]', ' ', regex=True)

    return csv_df


def check_mismatch(df_row, valid_values, column_to_check, column_to_return):
    """
    Checks mismatch between data frame column value and a list of values. If there is a mismatch, the values from
    the columns are returned, otherwise, None is returned.

    :param df_row: series, row of a pandas data frame.
    :param valid_values: list, valid values to check row value against.
    :param column_to_check: str, name of column containing values to check values against valid values.
    :param column_to_return: str, name of the column to return the value of along with the checked value.
    :return: checked value and return column value if the checked value is not valid, other returns None and None.
    """
    if df_row[column_to_check] not in valid_values:
        return df_row[column_to_check], df_row[column_to_return]
    return None, None


def check_change_types(csv_df):
    """
    Checks the change types in the ChangeType and AltType columns of the data frame against the ChangeTypes in the
    database lookup table. If there is a mismatch, an error message is displayed with the PatchName(s) and
    ChangeType(s).

    :param csv_df: data frame, the feature class attribute table with required fields/columns.
    :return: Boolean, True if a mismatch is found, otherwise, False.
    """
    # First check if there are change types to validate
    if csv_df['ChangeType'].isna().all():
        return False

    # Check to see if all the change types match the change types in the database lookup table
    # Save server and database names as variables
    server = 'inpolymnrm4'
    db = 'LPa01_Landscape_Change'
    # Create the connection string
    connection_string = f'mssql+pyodbc://{server}/{db}?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes'
    # Pass connection string and connect to the db
    engine = create_engine(connection_string)

    # Get the change types from the lookup table
    qry = 'SELECT ChangeType FROM lookup.ChangeType'
    # Read ChangeType into a pandas dataframe
    change_types = pd.read_sql(qry, engine)
    # Close the database connection
    engine.dispose()
    # Convert the dataframe to a list
    change_list = change_types['ChangeType'].tolist()
    # Since there is an empty space for blank values, add that to the list
    change_list.append(" ")

    # Check for mismatches
    changetype = csv_df.apply(lambda df_row: check_mismatch(df_row,
                                                            change_list,
                                                            'ChangeType',
                                                            'PatchName'),
                              axis=1)
    alttype = csv_df.apply(lambda df_row: check_mismatch(df_row,
                                                         change_list,
                                                         'AltType',
                                                         'PatchName'),
                           axis=1)

    # Filter out the mismatches
    mismatch_ct = [(ct[0], ct[1]) for ct in changetype if ct[0] is not None]
    mismatch_at = [(at[0], at[1]) for at in alttype if at[0] is not None]
    # Get a complete list of all mismatches
    mismatches = mismatch_ct + mismatch_at

    # If there are mismatches, throw an error, and display the mismatches
    if len(mismatches) > 0:
        # Change the variable because we don't want to save the CSV
        no_export = True
        arcpy.AddError("Change types in feature class do not match change types in lookup.ChangeType.")
        for mismatch in mismatches:
            arcpy.AddMessage(f"PatchName: {mismatch[1]}, change type: {mismatch[0]}")
    else:
        no_export = False
        arcpy.AddMessage("No change type mismatches found.")

    return no_export


def check_confidence(csv_df, only_values):
    """
    Checks the validity patch confidence values where the EventType is not null. Displays an error message with the
    number of patches with invalid confidence values. For patches being exported for GEE, if the Confidence values is
    1 or 2, the function checks if there is an AltType present.

    :param csv_df: data frame, the feature class attribute table with required fields/columns.
    :param only_values: Boolean, whether to only check Confidence values are valid or to also check if there is an
    AltType is Confidence value is 1 or 2.
    :return: Boolean, True if a confidence value is invalid, otherwise, False.
    """
    # Get all patches that have an event
    events = csv_df[(csv_df['EventType'] != " ") & (csv_df['EventType'].notna())]

    if len(events) == 0:
        return False

    # Find events that don't meet confidence validation rule
    con_ck = events[(events['Confidence'] < 1) | (events['Confidence'] > 3)][['PatchName', 'Confidence']]

    # If there are validation rule violations, throw an error, and display the violations
    if len(con_ck) > 0:
        # Change the variable because we don't want to save the CSV
        no_export = True
        arcpy.AddError("Confidence value does not pass validation rule of Confidence >= 1 and <=3.")
        arcpy.AddMessage(f"There are {len(con_ck)} patches with invalid confidence values.")
    else:
        no_export = False
        arcpy.AddMessage("Confidence values for Events pass the data table validation rule.")

    if not only_values:
        # Get all patches with Confidence of 1 or 2 that do not have an EventType of Mask
        conf_1_2 = events[(events['Confidence'] < 3) & (events['EventType'] != "Mask")]

        # AltType is present if Confidence is 1 or 2
        conf_alttype = conf_1_2[conf_1_2['AltType'].isna()]
        # Get only the Patch_names
        conf_alttype_patches = conf_alttype['PatchName'].tolist()
        # If there are validation rule violations, display the violations
        if len(conf_alttype_patches) > 0:
            no_export = no_export or True
            arcpy.AddError("There are Events with a Confidence of 1 or 2 with no AltType:")
            for patch in conf_alttype_patches:
                arcpy.AddMessage(f"PatchName: {patch}")
        else:
            no_export = no_export or False
            arcpy.AddMessage("Confidence values for Events with AltTypes passed validation.")

    return no_export


def check_duplicate_patch_names(csv_df):
    """
    Checks for duplicate PatchNames, and if there is, displays an error message with the PatchName(s).

    :param csv_df: data frame, the feature class attribute table with required fields/columns.
    :return: Boolean, True if there is a duplicate PatchName, otherwise, False.
    """
    # Find duplicate patch names
    duplicates = csv_df[csv_df.duplicated(subset=['PatchName'], keep=False)]
    # Get a list of patch names associated with the duplicates
    duplicate_patches = duplicates['PatchName'].tolist()

    # If there are duplicate patches, throw an error, and display the duplicate patch names
    if len(duplicate_patches) > 0:
        # Change the variable because we don't want to save the CSV
        no_export = True
        arcpy.AddError("There are duplicate patch names in the dataset.")
        for patch in duplicate_patches:
            arcpy.AddMessage(f"PatchName: {patch}")
    else:
        no_export = False
        arcpy.AddMessage("There are no duplicate patch names in the dataset.")

    return no_export


def check_fields_have_values(csv_df, value_fields):
    """
    Checks that the input fields all have values.

    :param csv_df: data frame, the feature class attribute table with required fields/columns.
    :param value_fields: list, the fields to check for values.
    :return: Boolean, True if all input fields have values, otherwise, False.
    """
    # List to hold fields with missing values
    missing_values = []

    # Loop through each field to check for missing values
    for field in value_fields:
        if csv_df[field].isna().any() or (csv_df[field] == " ").any():
            missing_values.append(field)

    # If there are missing values, display the fields with missing values
    if len(missing_values) > 0:
        no_export = True
        arcpy.AddError("There are fields with missing values.")
        for value in missing_values:
            arcpy.AddMessage(f"Field: {value}")
    else:
        no_export = False
        arcpy.AddMessage("No fields with missing values were found.")

    return no_export


def add_lat_long_wgs84(patches_fc):
    """
    Converts the Longitude and Latitude to WGS 84. Returns nothing.

    :param patches_fc: str, the file path to the patches feature class.
    """
    # Convert to points because it's easier to calculate geometry attributes that way
    patches_pts = "patches_pts"
    arcpy.management.XYTableToPoint(
        in_table=patches_fc,
        out_feature_class=patches_pts,
        x_field="Longitude",
        y_field="Latitude",
        z_field=None,
        coordinate_system='GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",'
                          '6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]];-400 '
                          '-400 1000000000;-100000 10000;-100000 10000;8.98315284119521E-09;0.001;0.001;IsHighPrecision'
    )

    # Calculate geometry attributes for lat/long in WGS84
    arcpy.management.CalculateGeometryAttributes(
        in_features=patches_pts,
        geometry_property="Long_WGS84 POINT_X;Lat_WGS84 POINT_Y",
        length_unit="",
        area_unit="",
        coordinate_system='GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
                          'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
        coordinate_format="SAME_AS_INPUT"
    )

    # Transpose WGS84 lat/long into existing lat/long fields
    arcpy.management.CalculateField(
        in_table=patches_pts,
        field="Longitude",
        expression="!Long_WGS84!",
        expression_type="PYTHON3"
    )

    arcpy.management.CalculateField(
        in_table=patches_pts,
        field="Latitude",
        expression="!Lat_WGS84!",
        expression_type="PYTHON3"
    )

    # Delete lat/long fields from patches polygon fc
    arcpy.management.DeleteField(
        in_table=patches_fc,
        drop_field=["Longitude", "Latitude"]
    )

    # Join lat/long from points to patches fc
    arcpy.management.JoinField(
        in_data=patches_fc,
        in_field="PatchName",
        join_table=patches_pts,
        join_field="PatchName",
        fields="Longitude;Latitude",
        fm_option="NOT_USE_FM",
        field_mapping=None,
        index_join_fields="NO_INDEXES"
    )

    # Add lat/long datum field
    arcpy.management.AddField(
        in_table=patches_fc,
        field_name="LLDatum",
        field_type="TEXT",
        field_length=5,
        field_is_nullable="NULLABLE"
    )

    # Populate datum field
    arcpy.management.CalculateField(
        in_table=patches_fc,
        field="LLDatum",
        expression="'WGS84'",
        expression_type="PYTHON3"
    )

    # Clean up GDB
    arcpy.management.Delete(patches_pts)


def exp_shp_spec_fields(patches_fc, exp_fields, out_folder):
    """
    Exports a shapefile with only the fields needed for GEE and only records with an EventType that is not "Mask" or
    "Model".

    :param patches_fc: str, the file path to the patches feature class.
    :param exp_fields: list, the fields to export.
    :param out_folder: str, the folder path to export the shapefile to.
    :return: str, the folder path for the shapefile that was exported.
    """
    # Prevent outputs from being added to the map
    arcpy.env.addOutputsToMap = False

    # Create a temporary feature layer
    temp_lyr = "temp_lyr"
    arcpy.management.MakeFeatureLayer(
        patches_fc,
        temp_lyr,
        where_clause="EventType IS NOT NULL And EventType NOT IN ('Mask', 'Model')",
        field_info=";".join([f"{field} {field} VISIBLE NONE" for field in exp_fields])
    )

    # Create a name for the shapefile
    patches_fc_name = os.path.basename(patches_fc)
    temp_fc = f"{patches_fc_name}_GEE"

    # Create folder name for the shapefile
    shp_folder = os.path.join(out_folder, temp_fc)

    # Check if folder already exists, if it does, add a suffix to it until it doesn't
    while os.path.exists(shp_folder):
        temp_fc = f"{temp_fc}_1"
        shp_folder = os.path.join(out_folder, temp_fc)

    # Create the folder
    os.mkdir(shp_folder)

    # Copy temporary feature layer to a feature class to export as shapefile
    arcpy.management.CopyFeatures(temp_lyr, temp_fc)

    # Convert lat/long to WGS84 and add datum column
    add_lat_long_wgs84(temp_fc)

    # Export feature class as shapefile
    arcpy.conversion.FeatureClassToShapefile(temp_fc, shp_folder)

    # Clean up GDB
    arcpy.management.Delete(temp_fc)

    return shp_folder


def export_patches_csv(patches_fc, out_fp):
    """
    Exports patches to a CSV with only the required the fields if the validation checks pass.

    :param patches_fc: str, the file path to the patches feature class.
    :param out_fp: str, the output file path for the CSV.
    :return no_export: Boolean, True if the patches were exported, otherwise, False.
    """
    # List of data.Patches fields to include in CSV, if they exist
    # MapPatch and PatchNotes are not included in this list
    patches_fields = [
        'Park',
        'PatchName',
        'yod',
        'annualID',
        'X_Coord_m',
        'Y_Coord_m',
        'Latitude',
        'Longitude',
        'UTMX',
        'UTMY',
        'CoordType',
        'idxMagMn',
        'durMn',
        'durSd',
        'area',
        'perim',
        'paratio',
        'Watershed',
        'WildName',
        'LandMgmt',
        'EastWest',
        'ElevMean',
        'SlopeMean',
        'Aspect',
        'Protected',
        'InBuffer',
        'InPark',
        'InMask',
        'VegCode',
        'DistYear',
        'DistName',
        'OverlapPrv',
        'Split',
        'EventType',
        'ChangeType',
        'Confidence',
        'AltType',
        'ChangeDesc',
        'EventDate',
        'LabeledBy',
        'PriorRun',
        'PostDist'
    ]
    # Run primary validation function to clean and validate
    no_export, csv_df = primary_validation(patches_fc, patches_fields, True)

    if no_export:
        arcpy.AddError(f"Validation error(s). {patches_fc} NOT exported to CSV.")
    else:
        # Write dataframe to CSV
        csv_df.to_csv(out_fp, index=False, quoting=csv.QUOTE_NONNUMERIC, quotechar='"')

        arcpy.AddMessage(f"Patches saved to: {out_fp}.")

    return no_export


def export_patches_shp(patches_fc, out_folder):
    """
    Exports patches to a shapefile with only the required fields if validation checks pass.

    :param patches_fc: str, the file path to the patches feature class.
    :param out_folder: str, the folder path to export the shapefile to.
    :return no_export: Boolean, True if the patches were exported, otherwise, False.
    """
    # List of fields to export
    exp_fields = [
        'AltType',
        'ChangeDesc',
        'ChangeType',
        'Confidence',
        'DistYear',
        'DistName',
        'EventType',
        'InBuffer',
        'InMask',
        'InPark',
        'MAJORAXIS',
        'MINORAXIS',
        'ORIENTATION',
        'Aspect',
        'PatchName',
        'Protected',
        'THICKNESS',
        'X_Coord_m',
        'Y_Coord_m',
        'Latitude',
        'Longitude',
        'paratio',
        'Park',
        'annualID',
        'area',
        'perim',
        'shape_1',
        'index',
        'uniqID',
        'yod',
        'durMn',
        'durSd',
        'idxMagMn',
        'idxMagSd',
        'tcbMagMn',
        'tcbMagSd',
        'tcbPreMn',
        'tcbPreSd',
        'tcbPst01Mn',
        'tcbPst01Sd',
        'tcbPst03Mn',
        'tcbPst03Sd',
        'tcbPst07Mn',
        'tcbPst07Sd',
        'tcbPst15Mn',
        'tcbPst15Sd',
        'tcbPstMn',
        'tcbPstSd',
        'tcgMagMn',
        'tcgMagSd',
        'tcgPreMn',
        'tcgPreSd',
        'tcgPst01Mn',
        'tcgPst01Sd',
        'tcgPst03Mn',
        'tcgPst03Sd',
        'tcgPst07Mn',
        'tcgPst07Sd',
        'tcgPst15Mn',
        'tcgPst15Sd',
        'tcgPstMn',
        'tcgPstSd',
        'tcwMagMn',
        'tcwMagSd',
        'tcwPreMn',
        'tcwPreSd',
        'tcwPst01Mn',
        'tcwPst01Sd',
        'tcwPst03Mn',
        'tcwPst03Sd',
        'tcwPst07Mn',
        'tcwPst07Sd',
        'tcwPst15Mn',
        'tcwPst15Sd',
        'tcwPstMn',
        'tcwPstSd',
        'Shape_Area',
        'Shape_Length'
    ]

    # Run primary validation function to validate patches
    no_export, csv_df = primary_validation(patches_fc, exp_fields, False)

    # List of fields not to check
    no_check_fields = [
        'AltType',
        'ChangeDesc',
        'DistYear',
        'DistName'
    ]

    # Get a list of only fields to check
    value_fields = [field for field in exp_fields if field not in no_check_fields]

    # Check that those fields have values
    no_export_values = check_fields_have_values(csv_df, value_fields)

    # Combine no_exports, only need one True to not export
    no_export = no_export or no_export_values

    if no_export:
        arcpy.AddError(f"Validation error(s). {patches_fc} NOT exported to CSV.")
    else:
        # Export feature class to shapefile
        out_shp = exp_shp_spec_fields(patches_fc, exp_fields, out_folder)

        arcpy.AddMessage(f"Shapefile saved to: {out_shp}.")

        return no_export
