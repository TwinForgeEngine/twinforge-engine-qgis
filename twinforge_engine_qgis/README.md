# TwinForge Engine for QGIS

Publish QGIS layers to TwinForge Engine and add TwinForge Engine layers to QGIS.

Guide and download: https://twinforgeengine.online/qgis-plugin/

## What it does
- Connects with a `tft_` access token from your TwinForge Engine account (Account, API keys).
  `gis:read` lists and adds layers; `gis:publish` also lets you publish.
- On the first connection with `gis:publish`, creates your own project (My layers).
- Publishes vector layers as GeoJSON (EPSG:4326) with classes, colours, legend, labels and pop-up fields,
  and rasters as Cloud Optimized GeoTIFF (converted on your computer).
- Published layers can be added in TwinForge Map, in TwinForge Engine scenes and in TwinForge Canvas.
- Adds layers that are already in TwinForge Engine back into QGIS through signed links (about 1 hour).
- Interface in English, Thai and Japanese (follows the QGIS language).

## Privacy
The token is kept in the QGIS authentication database (protected by the QGIS master password).
It is never written to project files or plain settings. Requests go through the QGIS network manager.

## Requirements
QGIS 3.34 or newer, including QGIS 4 (Qt6). No extra Python packages; GDAL from QGIS is used for COG conversion.

## License
GPL-2.0-or-later. See LICENSE.
