"""
Functions to support the add_attr_patches() function:
* clip_patches()
* add_utm_dd()
* add_albers()
* add_coords()
* create_central_pts()
* add_attrs_points()
* add_land_mgmt_wild()
* add_watershed()
* add_veg_type()
* add_zonal_geometry()

Functions to add additional attributes:
* add_park_patch_name()
* add_overlap_prev()
* add_paratio()
"""
import os
import arcpy
import addAttrUtils


def clip_patches(patches_fc, study_area_fc, mmu):
    """
    Clips the patches to the study area. If the area of any patches are less than the minimum mapping unit (mmu),
    those patches are removed. The area and perim fields for the clipped patches are updated using Shape_Area and
    Shape_Length. Deletes the original patches_fc and renames the clipped feature class to that of patches_fc. Returns
    nothing.

    :param patches_fc: str, the file path to the patches feature class (single year).
    :param study_area_fc: str, the file path for the study area feature class.
    :param mmu: int, the minimum mapping unit.
    """
    # Create name for clipped feature class as a variable
    clipped_patches = "clipped_patches"

    # Clip patches to study area
    arcpy.analysis.Clip(patches_fc, study_area_fc, clipped_patches)

    # SELECT AND DELETE FEATURES WITH AREA LESS THAN MMU
    # Calculate the area of the minimum mapping unit (Landsat imagery has 30-meter resolution)
    mmu_area = 30 * 30 * mmu

    # Create a feature layer of the clipped patches
    in_lyr = "in_layer"
    arcpy.management.MakeFeatureLayer(clipped_patches, in_lyr)

    # Select patches that are less than the MMU
    arcpy.management.SelectLayerByAttribute(
        in_lyr,
        'NEW_SELECTION',
        f'Shape_Area < {mmu_area}',
        'NON_INVERT'
    )

    # Delete the features
    arcpy.management.DeleteFeatures(in_lyr)

    # RENAME clipped_patches TO ORIGINAL patches_fc NAME
    # Only patches_fc if it exists, which it should
    if arcpy.Exists(patches_fc):
        arcpy.Delete_management(patches_fc)

    # Get the patches_fc name without the folder path
    patches = os.path.basename(patches_fc)
    # Rename the clipped features with the patches_fc name
    arcpy.management.Rename(clipped_patches, patches, "FeatureClass")

    # Update area and perim fields for clipped patches
    addAttrUtils.update_area_perim(patches_fc)


def add_utm_dd(fc, coord_type):
    """
    Adds the UTM and lat/long coordinates to the patches using the specified coordinate type. Used by add_coords().
    Returns nothing.

    :param fc: str, the file path of the feature class to add the coordinates to.
    :param coord_type: str, the coordinate type to calculate, CENTROID or INSIDE (central point).
    """
    # Add UTM coordinates
    arcpy.management.CalculateGeometryAttributes(
        in_features=fc,
        geometry_property=f"UTMX {coord_type}_X;UTMY {coord_type}_Y",
        length_unit="",
        area_unit="",
        coordinate_system='PROJCS["NAD_1983_UTM_Zone_10N",GEOGCS["GCS_North_American_1983",'
                          'DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
                          'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
                          'PROJECTION["Transverse_Mercator"],'
                          'PARAMETER["False_Easting",500000.0],'
                          'PARAMETER["False_Northing",0.0],'
                          'PARAMETER["Central_Meridian",-123.0],'
                          'PARAMETER["Scale_Factor",0.9996],'
                          'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]',
        coordinate_format="SAME_AS_INPUT"
    )

    # Add lat/long coordinates
    arcpy.management.CalculateGeometryAttributes(
        in_features=fc,
        geometry_property=f"Longitude {coord_type}_X;Latitude {coord_type}_Y",
        length_unit="",
        area_unit="",
        coordinate_system='GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
                          'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
                          'PRIMEM["Greenwich",0.0],'
                          'UNIT["Degree",0.0174532925199433]]',
        coordinate_format="DD"
    )


def add_albers(fc, a_id=None, annual_ids=None):
    """
    Add Albers coordinates to the patches. The default is "Central point" (INSIDE), but if that cannot be calculated,
    then "Centroid" is used. The annualIDs for any patches using "Centroid" are added to a list.

    :param fc: str, the file path of the feature class to add the coordinates to.
    :param annual_ids: list (optional), if this function is used recursively because a "centroid" needed to be
    calculated instead of a "central point", the list of annualID(s) is an input, so it can be added to, if necessary.
    :param a_id: int (optional), the annualID of the most recent patch where the "centroid" needed to be calculated
    instead of the "central point".
    :return: list, if any patches required "centroid" instead of "central point", a list containing the annualID(s) for
    the patch(es) is returned.
    """
    # Find the maximum annualID
    a_ids = [row[0] for row in arcpy.da.SearchCursor(fc, ["annualID"])]
    max_aid = max(a_ids)

    # If a_id was passed in, that means this function was called recursively, and we have to do things a little
    # differently.
    if a_id:
        # Create a list for annualIDs with centroids if not passed in
        if annual_ids is None:
            annual_ids = []  # Initialize if it does not exist

        # Add the annualID that was passed in to the list
        annual_ids.append(a_id)

        # If the a_id is the max annualID, we are finished adding Albers coordinates
        if a_id == max_aid:
            fc_name = os.path.basename(fc)
            arcpy.AddWarning(f"The central point(s) could not be calculated for patch(es) from {fc_name} with "
                             f"annualID(s) {annual_ids}. Centroid(s) calculated instead.")

            return annual_ids

        # Create a feature layer out of the feature class that was passed in
        in_lyr = "in_layer"
        arcpy.management.MakeFeatureLayer(fc, in_lyr)

        # Select the features with annualIDs greater than the annualID passed in
        arcpy.management.SelectLayerByAttribute(
            in_lyr,
            'NEW_SELECTION',
            f'annualID > {a_id}',
            'NON_INVERT'
        )

        # Attempt to calculate the central point
        try:
            arcpy.management.CalculateGeometryAttributes(
                in_features=in_lyr,
                geometry_property="X_Coord_m INSIDE_X;Y_Coord_m INSIDE_Y",
                length_unit="",
                area_unit="",
                coordinate_system=None,
                coordinate_format="SAME_AS_INPUT"
            )

            return annual_ids

        # If an error occurs, the centroid will be calculated for that patch.
        except arcpy.ExecuteError:
            # Variables for the two field names we care about
            field_id = "annualID"
            field_coord = "X_Coord_m"

            # Go through each patch to find the one whose X_Coord_m is null
            with arcpy.da.SearchCursor(fc, [field_id, field_coord]) as cursor:
                for row in cursor:
                    annual_id = row[0]
                    x_coord = row[1]

                    # The first feature where X_Coord_m is null is the one where the central point can't be calculated
                    if x_coord is None:
                        # Create a feature layer
                        in_lyr = "in_layer"
                        arcpy.management.MakeFeatureLayer(fc, in_lyr)

                        # Select the culprit patch
                        arcpy.management.SelectLayerByAttribute(
                            in_lyr,
                            'NEW_SELECTION',
                            f'annualID = {annual_id}',
                            'NON_INVERT'
                        )

                        # Calculate the culprit's centroid
                        arcpy.management.CalculateGeometryAttributes(
                            in_features=in_lyr,
                            geometry_property="X_Coord_m CENTROID_X;Y_Coord_m CENTROID_Y",
                            length_unit="",
                            area_unit="",
                            coordinate_system=None,
                            coordinate_format="SAME_AS_INPUT"
                        )

                        # If annual_ids already exists, then we want to pass it in when we call this function, which
                        # would be the case if this is not the first culprit patch.
                        if annual_ids:
                            annual_ids = add_albers(fc, annual_id, annual_ids)
                        else:
                            annual_ids = add_albers(fc, annual_id)
    else:
        # It is impossible to calculate the central point for some patches, which causes an error
        try:
            arcpy.management.CalculateGeometryAttributes(
                in_features=fc,
                geometry_property="X_Coord_m INSIDE_X;Y_Coord_m INSIDE_Y",
                length_unit="",
                area_unit="",
                coordinate_system=None,
                coordinate_format="SAME_AS_INPUT"
            )

            return annual_ids
        # If an error occurs, the centroid will be calculated for that patch (see comments for the same code above)
        except arcpy.ExecuteError:
            field_id = "annualID"
            field_coord = "X_Coord_m"

            # Go through each patch to find the one whose X_Coord_m is null
            with arcpy.da.SearchCursor(fc, [field_id, field_coord]) as cursor:
                for row in cursor:
                    annual_id = row[0]
                    x_coord = row[1]

                    if x_coord is None:
                        in_lyr = "in_layer"
                        arcpy.management.MakeFeatureLayer(fc, in_lyr)

                        arcpy.management.SelectLayerByAttribute(
                            in_lyr,
                            'NEW_SELECTION',
                            f'annualID = {annual_id}',
                            'NON_INVERT'
                        )

                        arcpy.management.CalculateGeometryAttributes(
                            in_features=in_lyr,
                            geometry_property="X_Coord_m CENTROID_X;Y_Coord_m CENTROID_Y",
                            length_unit="",
                            area_unit="",
                            coordinate_system=None,
                            coordinate_format="SAME_AS_INPUT"
                        )

                        if annual_ids:
                            annual_ids = add_albers(fc, annual_id, annual_ids)
                        else:
                            annual_ids = add_albers(fc, annual_id)

    return annual_ids


def add_coords(fc):
    """
    Adds field CoordType to feature class, which specifies what coordinate type was used, "Central Point" (INSIDE) or
    "Centroid"; the default is "Central point". add_ablers() returns a list of annualIDs where "Centroid" was used.
    This list is used to set CoordType to "Centroid" and to select patches for add_utm_dd(). Returns nothing.

    :param fc: str, the file path of the feature class to add the coordinates to.
    """
    # Add the default coordinate type to the feature class
    arcpy.management.AddField(
        in_table=fc,
        field_name="CoordType",
        field_type="TEXT",
        field_length=13,
        field_is_nullable="NULLABLE"
    )

    arcpy.management.CalculateField(
        in_table=fc,
        field="CoordType",
        expression='"Central point"',
        expression_type="PYTHON3"
    )

    # Add Albers coordinates and get a list of annualIDs where Centroid was used instead of Central point, if applicable
    annual_ids = add_albers(fc)

    # There are patches where Centroid was used
    if annual_ids is not None:
        # Create a new layer
        in_lyr = "in_layer"
        arcpy.management.MakeFeatureLayer(fc, in_lyr)

        # Convert list to a single string to use to Select by Attribute
        annual_ids_str = ', '.join(map(str, annual_ids))
        # Select patches with centroids using annualIDs
        arcpy.management.SelectLayerByAttribute(
            in_lyr,
            'NEW_SELECTION',
            f'annualID IN ({annual_ids_str})',
            'NON_INVERT'
        )

        # Add centroid to coordinate type
        arcpy.management.CalculateField(
            in_table=in_lyr,
            field="CoordType",
            expression='"Centroid"',
            expression_type="PYTHON3",
            field_type="TEXT"
        )

        # Add UTM and lat/long to patches with centroids
        add_utm_dd(in_lyr, "CENTROID")

        # Invert previous selection to get patches with Central points
        arcpy.management.SelectLayerByAttribute(
            in_lyr,
            'NEW_SELECTION',
            f'annualID IN ({annual_ids_str})',
            'INVERT'
        )

        # Add UTM and lat/long to patches with central points
        add_utm_dd(in_lyr, "INSIDE")

        # Clear the selection
        arcpy.management.SelectLayerByAttribute(in_lyr, 'CLEAR_SELECTION')

    else:
        # If no patches needed centroids, add UTM and lat/long using central point
        add_utm_dd(fc, "INSIDE")

    # Add field for UTM datum and populate
    arcpy.management.AddField(
        in_table=fc,
        field_name="Datum",
        field_type="TEXT",
        field_length=5,
        field_is_nullable="NULLABLE"
    )

    arcpy.management.CalculateField(
        in_table=fc,
        field="Datum",
        expression='"NAD83"',
        expression_type="PYTHON3"
    )


def create_central_points(fc):
    """
    Creates a point feature class using the Albers coordinates added by add_coords().

    :param fc: str, the file path of the feature class containing XY coordinates to turn into points.
    :return: str, name of point feature class.
    """
    # Create a point feature class using X_Coord_m and Y_Coord_m
    central_pts = "central_points"
    arcpy.management.XYTableToPoint(
        in_table=fc,
        out_feature_class=central_pts,
        x_field="X_Coord_m",
        y_field="Y_Coord_m",
        z_field=None,
        coordinate_system='PROJCS["Albers",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID['
                          '"GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",'
                          '0.0174532925199433]],PROJECTION["Albers"],PARAMETER["false_easting",0.0],PARAMETER['
                          '"false_northing",0.0],PARAMETER["central_meridian",-96.0],PARAMETER['
                          '"standard_parallel_1",'
                          '29.5],PARAMETER["standard_parallel_2",45.5],PARAMETER["latitude_of_origin",23.0],'
                          'UNIT["Meter",1.0]];-16901100 -6972200 266467840.990852;-100000 10000;-100000 '
                          '10000;0.001;0.001;0.001;IsHighPrecision'
    )

    return central_pts


def add_attrs_points(
        patches_fc,
        central_pts_sa,
        land_wild_fc,
        watershed_fc,
        park_fc,
        buff_fc,
        protected_fc,
        east_west_fc,
        zone_field):
    """
    Adds attributes (LandMgmt, Wilderness, InPark, InBuffer, Protected, Watershed, EastWest, if applicable) to
    the central points feature class using functions from addAttrFunctions and addAttrUtils, then joins those fields to
    the patches feature class. Returns nothing.

    :param patches_fc: str, the file path to the patches feature class (single year).
    :param central_pts_sa: str, the file path of the patches central point/centroid feature class.
    :param land_wild_fc: str, the file path to the feature class containing the land management and wilderness
    names.
    :param park_fc: str, the file path to the park boundary feature class.
    :param buff_fc: str, the file path to the buffer feature class.
    :param protected_fc: str, the file path to the protected areas feature class.
    :param east_west_fc: st, the file path to the east-west feature class.
    :param watershed_fc: str, the file path to the HUC12 watershed feature class.
    :param zone_field: str, the field containing the unique identifier.
    """
    # Add attributes
    add_land_mgmt_wild(land_wild_fc, central_pts_sa)
    add_watershed(watershed_fc, central_pts_sa)
    addAttrUtils.select_calculate(central_pts_sa, park_fc, "INTERSECT", "InPark")
    addAttrUtils.select_calculate(central_pts_sa, buff_fc, "INTERSECT", "InBuffer")

    # Join the desired fields
    arcpy.management.JoinField(
        in_data=patches_fc,
        in_field=zone_field,
        join_table=central_pts_sa,
        join_field=zone_field,
        fields=["WildName", "LandMgmt", "Watershed", "InPark", "InBuffer"],
        fm_option="NOT_USE_FM",
        field_mapping=None,
        index_join_fields="NO_INDEXES"
    )

    # Get a list of existing fields
    existing_fields = [field.name for field in arcpy.ListFields(central_pts_sa)]

    # LEWI does not have protected areas or crest (east west)
    # Create fields and leave null
    if protected_fc is None or east_west_fc is None:
        # If fields do not already exist, add them
        if "Protected" not in existing_fields:
            arcpy.management.AddField(
                in_table=central_pts_sa,
                field_name="Protected",
                field_type="SHORT",
                field_is_nullable="NULLABLE"
            )

        if "EastWest" not in existing_fields:
            arcpy.management.AddField(
                in_table=central_pts_sa,
                field_name="EastWest",
                field_type="TEXT",
                field_length=4,
                field_is_nullable="NULLABLE"
            )
    else:
        # Add attributes to the rest of the parks
        addAttrUtils.select_calculate(central_pts_sa, protected_fc, "INTERSECT", "Protected")

        if "EastWest" in existing_fields:
            # Delete original field, so it can be added with the spatial join and join field
            arcpy.management.DeleteField(
                in_table=central_pts_sa,
                drop_field="EastWest"
            )

            arcpy.management.DeleteField(
                in_table=patches_fc,
                drop_field="EastWest"
            )

        # Add EastWest
        arcpy.management.AddSpatialJoin(
            target_features=central_pts_sa,
            join_features=east_west_fc,
            join_operation="JOIN_ONE_TO_ONE",
            join_type="KEEP_ALL",
            field_mapping=f'EastWest "EastWest" true true false 4 Text 0 0,First,#,{east_west_fc},EastWest,0,3',
            match_option="INTERSECT",
            search_radius=None,
            distance_field_name="",
            permanent_join="PERMANENT_FIELDS",
            match_fields=None
        )

    # Determine which fields to join by comparing existing fields in patches_fc
    # Only want to join fields that do not already exist
    join_fields = [field for field in ["Protected", "EastWest"] if field not in existing_fields]

    # Only join fields if there are fields to join
    if join_fields:
        arcpy.management.JoinField(
            in_data=patches_fc,
            in_field=zone_field,
            join_table=central_pts_sa,
            join_field=zone_field,
            fields=join_fields,
            fm_option="NOT_USE_FM",
            field_mapping=None,
            index_join_fields="NO_INDEXES"
        )

    # Clean up GDB
    arcpy.management.Delete(central_pts_sa)


def add_land_mgmt_wild(lmw_fc, pts):
    """
    Adds LandMgmt and WildName attributes to the patches central points. Returns nothing.

    :param lmw_fc: str, the file path to the feature class containing the land management and wilderness
    names.
    :param pts: str, the file path of the point feature class to add attributes to.
    """
    # Join MANAGER, and WildName from lmw_fc to the points
    # Field mapping for join
    fm = (f'MANAGER "MANAGER" true true false 100 Text 0 0,First,#,{lmw_fc},MANAGER,0,99;'
          f'WildName "WildName" true true false 100 Text 0 0,First,#,{lmw_fc},WildName,0,99')

    arcpy.management.AddSpatialJoin(
        target_features=pts,
        join_features=lmw_fc,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        field_mapping=fm,
        match_option="COMPLETELY_WITHIN",
        search_radius=None,
        distance_field_name="",
        permanent_join="PERMANENT_FIELDS",
        match_fields=None
    )

    addAttrUtils.rename_field(pts, "MANAGER", "LandMgmt", "TEXT", 50)


def add_watershed(watershed_fc, pts):
    """
    Add Watershed attribute to the patches central points. Returns nothing.

    :param watershed_fc: str, the file path to the HUC12 watershed feature class.
    :param pts: str, the file path of the point feature class to add attributes to.
    """
    # Join NAME to central points
    # Field mapping for join
    fm = f'NAME "NAME" true true false 120 Text 0 0,First,#,{watershed_fc},NAME,0,119'

    arcpy.management.AddSpatialJoin(
        target_features=pts,
        join_features=watershed_fc,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        field_mapping=fm,
        match_option="INTERSECT",
        search_radius=None,
        distance_field_name="",
        permanent_join="PERMANENT_FIELDS",
        match_fields=None
    )

    addAttrUtils.rename_field(pts, "NAME", "Watershed", "TEXT", 50)


def add_veg_type(fc, veg_raster, zone_field, veg_type_tbl):
    """
    Adds VegType attribute using Zonal Statistics to find the majority veg type within the patch. Uses the veg type
    lookup table with VegValue (converted to an integer) to add VegCode attribute. If the park is LEWI, no veg type
    looku table is needed; the VegCode is calculated using the VegValue. Returns nothing.

    :param fc: str, the file path of the feature class to add the attributes to.
    :param veg_raster: str, the file path to the vegetation raster containing the MCID/value for the vegetation types.
    :param zone_field: str, the field containing the unique identifier.
    :param veg_type_tbl: str, file path to the table containing the MCID and vegetations codes for the park.
    """
    # Find majority VegValue and add to patches
    addAttrUtils.zonal_stats_rename_field(fc, veg_raster, zone_field, "MAJORITY", "Veg_value_text", "TEXT")

    # Convert Veg_value to long for join
    arcpy.management.CalculateField(
        in_table=fc,
        field="VegValue",
        expression="int(!Veg_value_text!) if !Veg_value_text! else None",
        expression_type="PYTHON3",
        field_type="LONG"
    )

    arcpy.management.DeleteField(
        in_table=fc,
        drop_field="Veg_value_text"
    )

    # LEWI does not have a veg type lookup table, but the rest of the parks do
    if veg_type_tbl:
        # Join the CODE associated with the Veg_value (MCID)
        arcpy.management.JoinField(
            in_data=fc,
            in_field="VegValue",
            join_table=veg_type_tbl,
            join_field="MCID",
            fields="CODE",
            fm_option="NOT_USE_FM",
            field_mapping=None,
            index_join_fields="NO_INDEXES"
        )

        addAttrUtils.rename_field(fc, "CODE", "VegCode", "TEXT", 4)
    else:
        # Add VegCode field
        arcpy.management.AddField(
            in_table=fc,
            field_name="VegCode",
            field_type="TEXT",
            field_length=4,
            field_is_nullable="NULLABLE"
        )

        # Calculate LEWI VegCode
        arcpy.management.CalculateField(
            in_table=fc,
            field="VegCode",
            expression="create_code(!VegValue!)",
            expression_type="PYTHON3",
            code_block="""def create_code(id):
                if id < 10:
                    code = "L0" + str(id)
                else:
                    code = "L" + str(id)
                return code"""
        )


def add_zonal_geometry(fc, zone_field, pro_cell_size):
    """
    Adds Thickness, MajorAxis, MinorAxis, and Orientation zonal geometry attributes to the patches feature class using
    Zonal Geometry as Table and joining the applicable fields from the table to the feature classes. Returns nothing.

    :param fc: str, the file path of the feature class to add the attributes to.
    :param zone_field: str, the field containing the unique identifier.
    :param pro_cell_size: int, the processing cell size for Zonal Geometry as Table.
    """
    # Create table name
    zonal_geo_tbl = "zonal_geo_tbl"

    # Run Zonal Geometry as Table
    arcpy.sa.ZonalGeometryAsTable(
        in_zone_data=fc,
        zone_field=zone_field,
        out_table=zonal_geo_tbl,
        processing_cell_size=pro_cell_size
    )

    # Keep field names as-is when joining zonal geometry fields to patches
    arcpy.env.qualifiedFieldNames = False
    # Join the desired zonal geometry fields to the patches
    arcpy.management.JoinField(
        in_data=fc,
        in_field=zone_field,
        join_table=zonal_geo_tbl,
        join_field="VALUE",
        fields="THICKNESS;MAJORAXIS;MINORAXIS;ORIENTATION",
        fm_option="NOT_USE_FM",
        field_mapping=None,
        index_join_fields="NO_INDEXES"
    )

    # Clean up GDB
    arcpy.management.Delete(zonal_geo_tbl)


def add_park_patch_name(changeDB_fc, park, mmu, start_yr, end_yr):
    """
    Adds park and patch name attributes to the patches feature class by calculating the fields. Returns nothing.

    :param changeDB_fc: str, the file path of the feature class containing patches for the entire run (all years).
    :param park: str, the park code.
    :param mmu: int, the minimum mapping unit.
    :param end_yr: int, the max year in changeDB_fc.
    :param start_yr: int, the min year in changeDB_fc.
    """
    # Add Park field
    arcpy.management.AddField(
        in_table=changeDB_fc,
        field_name="Park",
        field_type="TEXT",
        field_length=4,
        field_is_nullable="NULLABLE"
    )

    # Populate with Park code
    arcpy.management.CalculateField(
        in_table=changeDB_fc,
        field="Park",
        expression=f'"{park}"',
        expression_type="PYTHON3"
    )

    # Add PatchName field
    arcpy.management.AddField(
        in_table=changeDB_fc,
        field_name="PatchName",
        field_type="TEXT",
        field_length=50,
        field_is_nullable="NULLABLE"
    )

    # Calculate PatchName
    arcpy.management.CalculateField(
        in_table=changeDB_fc,
        field="PatchName",
        expression=f'"{park}_{mmu}_" + !index! + "_{start_yr}_{end_yr}_" + str(!yod!) + "_" + str(!annualID!)',
        expression_type="PYTHON3"
    )


def add_overlap_prev(base_fc, prev_fc, park, events_mask):
    """
    Adds OverlapPrv attribute to patches feature class. Initally, OverlapPrv is set to 0/False. Then the base_fc
    patches that overlap (intersect) with the prev_fc patches are selected, and OverlapPrv is set to 1/True. Returns
    nothing.

    :param base_fc: str, the file path of the patches for the current year.
    :param prev_fc: str, the file path of the patches for the previous year.
    :param park: str, the park code.
    :param events_mask: Boolean, indicates whether event fields are populated for patches inside water and/or elevation
    mask.
    """
    # Create layer names
    base_lyr = "base_lyr"
    prev_lyr = "prev_lyr"

    # Create the layers selecting only patches not in the mask (LEWI does not have an InMask field)
    if events_mask:
        arcpy.management.MakeFeatureLayer(base_fc, base_lyr, f"EventType IS NULL")
        arcpy.management.MakeFeatureLayer(prev_fc, prev_lyr, f"EventType IS NULL")
    else:
        if park != "LEWI":
            arcpy.management.MakeFeatureLayer(base_fc, base_lyr, f"InMask = 0")
            arcpy.management.MakeFeatureLayer(prev_fc, prev_lyr, f"InMask = 0")
        else:
            arcpy.management.MakeFeatureLayer(base_fc, base_lyr)
            arcpy.management.MakeFeatureLayer(prev_fc, prev_lyr)

    # Select patches in the base_lyr that intersect with the prev_lyr
    # -1 meter search distance is to ensure patches overlap and don't just share borders
    arcpy.management.SelectLayerByLocation(
        in_layer=base_lyr,
        overlap_type="INTERSECT",
        select_features=prev_lyr,
        search_distance="-1 Meters",
        selection_type="NEW_SELECTION",
        invert_spatial_relationship="NOT_INVERT"
    )

    # Set OverlapPrv to 1/True for selected patches
    arcpy.management.CalculateField(
        in_table=base_lyr,
        field="OverlapPrv",
        expression="1",
        expression_type="PYTHON3",
    )


def add_paratio(patches_fc):
    """
    Adds paratio to patches feature class by performing a calculation using area and perim. Returns nothing.

    :param patches_fc: str, the file path of the feature class to add the attributes to.
    """
    # Add field and calculate
    arcpy.management.AddField(
        in_table=patches_fc,
        field_name="paratio",
        field_type="DOUBLE",
        field_precision=16,
        field_scale=15,
        field_length=None,
        field_alias="",
        field_is_nullable="NULLABLE",
        field_is_required="NON_REQUIRED",
        field_domain=""
    )
    arcpy.management.CalculateField(
        in_table=patches_fc,
        field="paratio",
        expression=f'!area! /  ((0.282 * !perim!)**2)',
        expression_type="PYTHON3"
    )
