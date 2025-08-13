import logging
import ezdxf
from pathlib import Path
from typing import Dict
import re

logger = logging.getLogger(__name__)

class DXFDataExtractor:
    def __init__(self):
        self.mm_to_m = 0.001  # Conversion factor from mm to meters

    def _get_height(self, msp) -> float:
        """Robust height extraction handling all entity types with unit conversion"""
        logger.debug("Starting height extraction from DXF modelspace")
        
        # Method 1: Check 3DFACE entities (in mm)
        for entity in msp:
            if entity.dxftype() == '3DFACE':
                try:
                    height_mm = max(v[2] for v in entity.vertices)
                    height_m = height_mm * self.mm_to_m
                    logger.debug(f"Found 3DFACE entity with height: {height_m:.2f}m")
                    return height_m
                except (AttributeError, TypeError):
                    continue
        
        # Method 2: Check text annotations (already in meters)
        for entity in msp:
            if entity.dxftype() == 'TEXT' and 'height' in (entity.text or '').lower():
                try:
                    match = re.search(r'(\d+\.?\d*)\s*m', entity.text)
                    if match:
                        return float(match.group(1))
                except (AttributeError, ValueError):
                    continue
        
        logger.warning("Using default height 10.0m (could not detect actual height)")
        return 10.0

    def parse_floor_plan(self, dxf_path: Path) -> Dict:
        """Parse DXF file and extract metrics with proper unit conversion"""
        logger.info(f"Processing floor plan from {dxf_path}")
        try:
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
            
            # Find largest closed polyline (footprint)
            closed_polylines = [e for e in msp if e.dxftype() in ['LWPOLYLINE', 'POLYLINE'] and e.closed]
            if not closed_polylines:
                raise ValueError("No closed polylines found in DXF")
            
            footprint = max(closed_polylines, key=lambda e: abs(ezdxf.math.area(e.get_points('xy')) or 0))
            
            # Calculate bounding box (values in mm)
            bbox = ezdxf.math.BoundingBox()
            if hasattr(footprint, 'vertices'):
                bbox.extend(footprint.vertices())
            elif hasattr(footprint, 'get_points'):
                bbox.extend(footprint.get_points('xy'))
            
            # Calculate area (mm² to m² conversion)
            area_mm2 = abs(ezdxf.math.area(footprint.get_points('xy'))) if hasattr(footprint, 'get_points') else 0
            area_m2 = area_mm2 * (self.mm_to_m ** 2)
            
            metrics = {
                "height_m": self._get_height(msp),
                "setback_front_m": bbox.extmax.y * self.mm_to_m if bbox.has_data else 0,
                "setback_rear_m": abs(bbox.extmin.y) * self.mm_to_m if bbox.has_data else 0,
                "setback_left_m": abs(bbox.extmin.x) * self.mm_to_m if bbox.has_data else 0,
                "setback_right_m": bbox.extmax.x * self.mm_to_m if bbox.has_data else 0,
                "footprint_area_m2": area_mm2 * (self.mm_to_m ** 2),
                "total_area_m2": area_mm2 * (self.mm_to_m ** 2) * 3  # 3 floors
            }
            
            # Debug print all extracted metrics
            logger.info("DXF Metrics (converted to meters):")
            for k, v in metrics.items():
                unit = "m" if k.endswith("_m") else "m²" if k.endswith("_m2") else ""
                logger.info(f"- {k}: {v:.2f}{unit}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"DXF parsing failed: {str(e)}", exc_info=True)
            raise