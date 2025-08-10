import ezdxf
from typing import Dict, Optional
from pathlib import Path

def parse_floor_plan(dxf_path: str) -> Dict[str, Optional[float]]:
    """
    Extract metrics from DXF file using ezdxf.
    Returns: {
        "area_m2": float,
        "setback_front": float,
        "setback_rear": float,
        "setback_left": float,
        "setback_right": float,
        "height_m": Optional[float]
    }
    """
    try:
        # Load DXF document
        doc = ezdxf.readfile(dxf_path)
        print("Entity types:", {e.dxftype() for e in doc.modelspace()})
        msp = doc.modelspace()

        # Find largest closed polyline (assumed to be footprint)
        max_area = 0
        footprint = None
        for entity in msp:
            if entity.dxftype() == 'LWPOLYLINE' and entity.closed:
                # Calculate area manually for LWPolyline
                area = abs(ezdxf.math.area(entity.get_points('xy')))
                if area > max_area:
                    max_area = area
                    footprint = entity

        if not footprint:
            raise ValueError("No closed polylines found in DXF.")

        # Get bounding box for setbacks
        bbox = ezdxf.math.BoundingBox(footprint.vertices())
        metrics = {
            "area_m2": max_area,
            "setback_front": bbox.extmax.y,  # Y-max
            "setback_rear": abs(bbox.extmin.y),  # Y-min
            "setback_left": abs(bbox.extmin.x),  # X-min
            "setback_right": bbox.extmax.x,  # X-max
            "height_m": _get_height(msp)  # Optional 3D check
        }

        return metrics

    except Exception as e:
        print(f"Error parsing DXF: {e}")
        return {key: None for key in [
            "area_m2", "setback_front", "setback_rear",
            "setback_left", "setback_right", "height_m"
        ]}

def _get_height(msp) -> Optional[float]:
    """Extract height from 3D objects if available."""
    for entity in msp:
        if entity.dxftype() == '3DFACE':
            return max(v[2] for v in entity.vertices)  # Max Z-coordinate
    return None

if __name__ == "__main__":
    # Example usage
    dxf_path = Path(r"D:\Project\Manshant_Project\prototype\sample_files\1\floor_plan\09-08-2025_PHYTON PROTOTYPE_4M.dxf")
    metrics = parse_floor_plan(dxf_path)
    print("Extracted metrics:", metrics)