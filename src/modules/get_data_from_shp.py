import logging
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon
from typing import Dict
from pyproj import Transformer

logger = logging.getLogger(__name__)

class ShapefileValidator:
    def __init__(self):
        self.plot_area_m2 = 0.0
        self.within_plot = False
        self.violation_distance_m = 0.0

    def validate_plot(self, shp_path: Path, dxf_metrics: Dict) -> Dict:
        """GIS validation with coordinate transformation and enhanced debugging"""
        logger.info(f"Validating against plot at {shp_path}")
        try:
            # Read shapefile
            gdf = gpd.read_file(str(shp_path))
            
            # Debug print CRS info
            if gdf.crs:
                logger.info(f"Shapefile CRS: {gdf.crs}")
                logger.info(f"CRS units: {gdf.crs.axis_info[0].unit_name if gdf.crs.axis_info else 'unknown'}")
            else:
                logger.warning("Shapefile has no CRS, assuming local coordinates in meters")

            # Create footprint polygon from DXF metrics (already in meters)
            footprint_local = Polygon([
                (dxf_metrics["setback_left_m"], dxf_metrics["setback_rear_m"]),
                (dxf_metrics["setback_right_m"], dxf_metrics["setback_rear_m"]),
                (dxf_metrics["setback_right_m"], dxf_metrics["setback_front_m"]),
                (dxf_metrics["setback_left_m"], dxf_metrics["setback_front_m"])
            ])

            # Transform coordinates if shapefile has CRS
            if gdf.crs and gdf.crs.is_projected:
                try:
                    # Create transformer from local meters to shapefile CRS
                    transformer = Transformer.from_crs(
                        "EPSG:4326",  # Using WGS84 as intermediate
                        gdf.crs,
                        always_xy=True
                    )
                    
                    # Transform each point
                    transformed_points = []
                    for x, y in footprint_local.exterior.coords:
                        lon, lat = x, y  # Assuming DXF coords are in meters relative to origin
                        transformed_x, transformed_y = transformer.transform(lon, lat)
                        transformed_points.append((transformed_x, transformed_y))
                    
                    footprint = Polygon(transformed_points)
                except Exception as e:
                    logger.warning(f"Coordinate transformation failed, using local coordinates: {str(e)}")
                    footprint = footprint_local
            else:
                footprint = footprint_local

            # Debug print geometries
            logger.info(f"Plot bounds: {gdf.geometry.iloc[0].bounds}")
            logger.info(f"Footprint bounds: {footprint.bounds}")
            
            # Perform spatial validation
            self.within_plot = footprint.within(gdf.geometry.iloc[0])
            self.violation_distance_m = 0.0 if self.within_plot else footprint.distance(gdf.geometry.iloc[0])
            self.plot_area_m2 = gdf.geometry.iloc[0].area

            # Check for potential unit issues
            if not self.within_plot and footprint.area > 0:
                size_ratio = self.plot_area_m2 / footprint.area
                if size_ratio > 1000:  # Reasonable threshold for meters vs mm
                    logger.warning(f"Large size ratio detected ({size_ratio:.1f}:1). Verify units are consistent.")

            result = {
                "within_plot": self.within_plot,
                "plot_area_m2": self.plot_area_m2,
                "violation_distance_m": self.violation_distance_m
            }
            
            logger.info("GIS Validation Results:")
            logger.info(f"- Within plot: {self.within_plot}")
            logger.info(f"- Violation distance: {self.violation_distance_m:.2f} units")
            logger.info(f"- Plot area: {self.plot_area_m2:.2f} square units")
            
            return result
            
        except Exception as e:
            logger.error(f"GIS validation failed: {str(e)}", exc_info=True)
            raise

    def print_validation_summary(self):
        """Print formatted validation results"""
        print("\nGIS VALIDATION SUMMARY")
        print("---------------------")
        print(f"Plot contains building: {'YES' if self.within_plot else 'NO'}")
        if not self.within_plot:
            print(f"Distance outside plot: {self.violation_distance_m:.2f} meters")
        print(f"Plot area: {self.plot_area_m2:.2f} square meters")
        print(f"CRS: {'None (local coordinates)' if not hasattr(self, 'crs') else self.crs}")