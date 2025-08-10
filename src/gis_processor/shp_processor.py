import os
import warnings
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
from typing import Dict, Any

# Disable all warnings
warnings.filterwarnings("ignore")
os.environ["PROJ_DISABLE_CACHE"] = "YES"

def validate_shapefile_path(shp_base_path: str) -> Dict[str, Any]:
    """Verify shapefile exists with all required components"""
    base_path = Path(shp_base_path)
    required_exts = ['.shp', '.shx', '.dbf']
    missing_files = []
    
    for ext in required_exts:
        if not base_path.with_suffix(ext).exists():
            missing_files.append(ext[1:])  # Remove dot from extension
    
    available_files = [f.name for f in base_path.parent.glob(base_path.stem + ".*")]
    
    return {
        "exists": len(missing_files) == 0,
        "missing": missing_files,
        "available": available_files,
        "searched_path": str(base_path.with_suffix('.shp'))
    }

def process_gis_data(shp_base_path: str, dxf_metrics: Dict[str, float]) -> Dict[str, Any]:
    """
    Robust GIS validator with:
    - Complete path verification
    - Unit normalization
    - Detailed error reporting
    """
    # 1. Validate shapefile exists
    path_check = validate_shapefile_path(shp_base_path)
    if not path_check["exists"]:
        return {
            "error": "Missing shapefile components",
            "details": path_check
        }

    try:
        # 2. Load shapefile
        gdf = gpd.read_file(path_check["searched_path"])
        if len(gdf) == 0:
            return {"error": "Shapefile contains no features"}
        
        plot_polygon = gdf.geometry.iloc[0]
        
        # 3. Create footprint polygon (mm → m)
        footprint = Polygon([
            (dxf_metrics["setback_left"]/1000, dxf_metrics["setback_rear"]/1000),
            (dxf_metrics["setback_right"]/1000, dxf_metrics["setback_rear"]/1000),
            (dxf_metrics["setback_right"]/1000, dxf_metrics["setback_front"]/1000),
            (dxf_metrics["setback_left"]/1000, dxf_metrics["setback_front"]/1000)
        ])
        
        # 4. Validate containment
        is_valid = footprint.within(plot_polygon)
        
        return {
            "is_valid": is_valid,
            "violation_distance_m": 0.0 if is_valid 
                else round(footprint.distance(plot_polygon), 2),
            "plot_area_m2": round(plot_polygon.area, 2),
            "footprint_area_m2": round(footprint.area, 2),
            "coverage_ratio": round(footprint.area / plot_polygon.area, 2),
            "units": "meters"
        }

    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {str(e)}",
            "troubleshooting": [
                "1. Verify shapefile integrity in QGIS",
                "2. Check coordinate units match between DXF and SHP",
                f"3. Original path: {shp_base_path}"
            ]
        }

if __name__ == "__main__":
    # Test configuration
    TEST_PATH = r"D:\Project\Manshant_Project\prototype\sample_files\2\gim_file\boundary"
    # TEST_METRICS = {
    #     "setback_front": 261240.89,
    #     "setback_rear": 141817.91,
    #     "setback_left": 127997.56,
    #     "setback_right": 223015.96
    # }
    
    # 1. First verify path
    path_status = validate_shapefile_path(TEST_PATH)
    print("Path Verification:", path_status)
    
    # 2. Only run validation if files exist
    if path_status["exists"]:
        results = process_gis_data(TEST_PATH, TEST_METRICS)
        print("Validation Results:", results)
    else:
        print("Cannot proceed - missing shapefile components")