import os
import addAttrFunctions
import addAttrUtils


def add_attr_patches(patches_fc,
                     zone_field,
                     pro_cell_size,
                     park,
                     park_path,
                     clip_patches_sa,
                     mmu=None):
    """
    This is the primary function of the geoprocessing tool. The function creates the paths for the items in the park
    GDB that are needed to add the attributes, and it adds attributes to the patches using functions
    from addAttrFunctions and addAttrUtils. A new feature class is created for the patches and saved to the
    user-specified geodatabase. The original shapefile is not modified. Returns nothing.

    :param patches_fc: str, the file path to the patches feature class (single year).
    :param zone_field: str, the field containing the unique identifier.
    :param pro_cell_size: int, the processing cell size for Zonal Geometry as Table.
    :param park: str, the four-letter park code extracted from the park GDB name.
    :param park_path: str, path to park GDB with park prefix for items in the GDB (path/to/park/gdb/PARK_)
    :param clip_patches_sa: Boolean, whether to clip patches to study area.
    :param mmu: int (optional), the minimum mapping unit for the patches; not needed when adding attributes to select
    patches because PatchName is already populated and patches have already been clipped, if necessary.
    """
    # Get and set the default gdb as the workspace
    gdb = addAttrUtils.set_default_gdb_workspace()

    # CHECK WHICH FIELDS ALREADY EXIST AND DELETE
    addAttrUtils.del_existing_fields(patches_fc)

    # CREATE PATHS FOR ITEMS IN PARK GDB
    # Study area to remove patches with centroids outside of study area
    study_area_fc = f"{park_path}study_area_fc"
    # DEM for Elev_mean
    dem_rst = f"{park_path}dem_rst"
    # Slope raster for Slope_mean
    slope_rst = f"{park_path}slope_rst"
    # Aspect raster (categorical) for Aspect
    aspect_rst = f"{park_path}aspect_rst"
    # Vegetation raster for VegValue
    veg_rst = f"{park_path}veg_rst"

    # Initially set to None because LEWI does not have these
    veg_type_tbl = None
    mask_fc = None
    protected_fc = None
    east_west_fc = None

    # If the park is not LEWI, create paths
    if park != "LEWI":
        # Table with vegetation types for Veg_code
        veg_type_tbl = f"{park_path}veg_type_tbl"
        # Elevation mask feature class for InMask and for labeling patches with Annual Variability
        mask_fc = f"{park_path}mask_fc"
        # Protected areas feacture class for Protected
        protected_fc = f"{park_path}protected_fc"
        # East and west of crest polygons
        east_west_fc = f"{park_path}east_west_fc"

    # Land management and wilderness feature class for LandMgmt and WildName
    land_mgmt_wild_fc = f"{park_path}land_mgmt_wild_fc"
    # Park boundary feature class for InPark
    park_bndry_fc = f"{park_path}park_bndry_fc"
    # Buffer feature class for InBuffer
    buff_fc = f"{park_path}buff_fc"
    # Watershed feature class for Watershed
    watershed_fc = f"{park_path}watershed_fc"

    # ADD ATTRIBUTES
    if clip_patches_sa:
        # Clip patches to study area and remove patches that are less than MMU, update area and perim
        addAttrFunctions.clip_patches(patches_fc, study_area_fc, mmu)

    # Add centroids in Albers, UTM, and lat/long to fc
    addAttrFunctions.add_coords(patches_fc)

    # Create a point feature class using X_Coord_m and Y_Coord_m and create file path
    central_pts_sa = addAttrFunctions.create_central_points(patches_fc)
    central_pts_sa = os.path.join(gdb, central_pts_sa)

    # Add LandMgmt, WildName, Watershed, InPark, InBuffer, Protected, and EastWest
    addAttrFunctions.add_attrs_points(patches_fc,
                                      central_pts_sa,
                                      land_mgmt_wild_fc,
                                      watershed_fc,
                                      park_bndry_fc,
                                      buff_fc,
                                      protected_fc,
                                      east_west_fc,
                                      zone_field)

    # Add InMask to parks that are not LEWI (patches must be completely within mask to be Yes)
    if mask_fc is not None:
        addAttrUtils.select_calculate(patches_fc, mask_fc, "COMPLETELY_WITHIN", "InMask")

    # Add Veg_type and Veg_code
    addAttrFunctions.add_veg_type(patches_fc, veg_rst, zone_field, veg_type_tbl)

    # Add Elev_mean, Slope_mean, and Aspect
    addAttrUtils.zonal_stats_rename_field(patches_fc, dem_rst, zone_field, "MEAN", "ElevMean", "FLOAT")
    addAttrUtils.zonal_stats_rename_field(patches_fc, slope_rst, zone_field, "MEAN", "SlopeMean", "FLOAT")
    addAttrUtils.zonal_stats_rename_field(patches_fc, aspect_rst, zone_field, "MAJORITY", "Aspect", "SHORT")

    # Add zonal geometry to the shapefile
    addAttrFunctions.add_zonal_geometry(patches_fc, zone_field, pro_cell_size)
