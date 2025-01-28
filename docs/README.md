# Landscape Change Geoprocessing Tools

The following geoprocessing tools in LandscapeChange.atbx support the Landscape Change protocol workflow:
* Add Attributes to Patches
* Export Patches
* Add Attributes to Select Patches & Export CSV
* Join Labels to Patches

The Python scripts for the tools are in the [toolbox](https://github.com/NPS-NCCN/Landscape_GeoTools/tree/main/toolbox) folder. To set up the tools in an ArcGIS Pro project, see [LandscapeChange_GeoTools_Documentation.docx](https://github.com/NPS-NCCN/Landscape_GeoTools/blob/main/docs/LandscapeChange_GeoTools_Documentation.docx).

## Add Attributes to Patches
Adds attributes/predictors to the LandTrendr output patches for each individual year and creates an output feature class containing all years. The original shapefiles are not modified. The rasters, feature classes, and vegetation type table needed to add the attributes must be in a park-specific geodatabase. The following attributes are added: coordinates for the patch centroid (Albers, UTM, DD), wilderness name, land management, watershed, whether the patch centroid is in the park, buffer, and protected area, whether the entire patch is within the elevation mask, vegetation value and code, mean slope and elevation, aspect category, zonal geometry (thickness, major and minor axis, orientation), and whether the patch overlaps a patch or patches from the previous year. The fields Park and PatchName are generated also generated. Additionally, patches that are completely within the elevation or water mask are labeled with a ChangeType of "Annual Variability", a Confidence of 2, and LabeledBy of "Geoprocessing". The field names for the attributes match those needed to use the Landscape Change geoprocessing tool Export Patches to CSV.

## Add Attributes to Select Patches & Export CSV
Updates attributes/predictors for selected patches that have split or merged by copying the patches, deleting the attributes, recalculating the attributes, deleting the selected patches from the feature class, and copying the updated patches to the feature class. The rasters, feature classes, and vegetation type table needed to add the attributes must be in a park-specific geodatabase. 

## Export Patches
Depending on the user selections, this tool either exports a CSV and/or shapefile. Exports only required fields from the patches feature class to a CSV to be used for importing patches and prior events data into the Landscape Change database. Exports only required fields from the patches feature class to a shapefile to be used in Google Earth Engine. Validation checks are performed, and the patches will only be exported if the validation checks pass.

## Join Labels to Patches
Joins Event labels (EventType, ChangeType, Confidence, AltType, ChangeDesc, DistYear, DistName) exported from the SQL Server database to the patches feature class if the Event fields do not exist. Otherwise, the existing Event fields are updated with labels. This tool is useful when the Event fields already exist in the feature class.

If you have any questions, please contact Christina Appleby at [cmbappleby@gmail.com](mailto:cmbappleby@gmail.com).

_Updated 20250128_
