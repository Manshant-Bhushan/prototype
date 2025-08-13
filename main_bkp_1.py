import sys
import logging
import os
from pathlib import Path
import geopandas as gpd
import ezdxf
import pdfplumber
from shapely.geometry import Polygon
from typing import Dict, List, Tuple, Optional
import re
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            f'compliance_pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BuildingComplianceChecker:
    def __init__(self):
        self.dxf_metrics = {}
        self.gis_result = {}
        self.by_laws = {}
        self.found_rules = set()
        logger.debug("BuildingComplianceChecker initialized")

    def _get_height(self, msp) -> float:
        """Robust height extraction handling all entity types"""
        logger.debug("Starting height extraction from DXF modelspace")
        
        # Method 1: Check 3DFACE entities
        for entity in msp:
            if entity.dxftype() == '3DFACE':
                try:
                    height = max(v[2] for v in entity.vertices) / 1000
                    logger.debug(f"Found 3DFACE entity with height: {height}m")
                    return height
                except (AttributeError, TypeError):
                    continue
        
        # Method 2: Check text annotations
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

    def extract_by_laws(self, pdf_path: Path) -> Dict:
        """Extract only the regulations present in the PDF"""
        logger.info(f"Extracting by-laws from {pdf_path}")
        rules = {
            "max_height_m": None,
            "min_setback_front_m": None,
            "min_setback_rear_m": None,
            "min_setback_side_m": None,
            "max_far": None,
            "max_coverage": None
        }
        
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                # Extract all text first
                full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                logger.debug(f"Extracted text: {full_text[:200]}...")
                
                # Check for each rule only if its keyword exists in text
                rule_patterns = {
                    "max_height_m": (r"(?:max(?:imum)?\s*height|height\s*limit)[:.]?\s*(\d+\.?\d*)\s*m", "maximum height"),
                    "min_setback_front_m": (r"(?:front\s*setback|setback\s*from\s*front)[:.]?\s*(\d+\.?\d*)\s*m", "front setback"),
                    "min_setback_rear_m": (r"(?:rear\s*setback|setback\s*from\s*rear)[:.]?\s*(\d+\.?\d*)\s*m", "rear setback"),
                    "min_setback_side_m": (r"(?:side\s*setback|setback\s*from\s*sides?)[:.]?\s*(\d+\.?\d*)\s*m", "side setback"),
                    "max_far": (r"(?:far|floor\s*area\s*ratio)[:.]?\s*(\d+\.?\d*)", "FAR"),
                    "max_coverage": (r"(?:max(?:imum)?\s*coverage|site\s*coverage)[:.]?\s*(\d+\.?\d*)%?", "coverage")
                }
                
                for rule_name, (pattern, description) in rule_patterns.items():
                    if description.split()[0].lower() in full_text.lower():
                        match = re.search(pattern, full_text, re.IGNORECASE)
                        if match:
                            rules[rule_name] = float(match.group(1))
                            if rule_name == "max_coverage":
                                rules[rule_name] /= 100  # Convert percentage to decimal
                            self.found_rules.add(rule_name)
                            logger.info(f"Found {description}: {rules[rule_name]}")
                
                logger.info(f"Extracted rules: { {k:v for k,v in rules.items() if v is not None} }")
                return rules
                
        except Exception as e:
            logger.error(f"PDF parsing failed: {str(e)}", exc_info=True)
            raise

    def parse_floor_plan(self, dxf_path: Path) -> Dict:
        """Parse DXF file and extract metrics"""
        logger.info(f"Processing floor plan from {dxf_path}")
        try:
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
            
            # Find largest closed polyline (footprint)
            closed_polylines = [e for e in msp if e.dxftype() in ['LWPOLYLINE', 'POLYLINE'] and e.closed]
            if not closed_polylines:
                raise ValueError("No closed polylines found in DXF")
            
            footprint = max(closed_polylines, key=lambda e: abs(ezdxf.math.area(e.get_points('xy')) or 0))
            
            # Calculate bounding box
            bbox = ezdxf.math.BoundingBox()
            if hasattr(footprint, 'vertices'):
                bbox.extend(footprint.vertices())
            elif hasattr(footprint, 'get_points'):
                bbox.extend(footprint.get_points('xy'))
            
            # Calculate area
            area = abs(ezdxf.math.area(footprint.get_points('xy'))) if hasattr(footprint, 'get_points') else 0
            
            metrics = {
                "height_m": self._get_height(msp),
                "setback_front_m": bbox.extmax.y / 1000 if bbox.has_data else 0,
                "setback_rear_m": abs(bbox.extmin.y) / 1000 if bbox.has_data else 0,
                "setback_left_m": abs(bbox.extmin.x) / 1000 if bbox.has_data else 0,
                "setback_right_m": bbox.extmax.x / 1000 if bbox.has_data else 0,
                "footprint_area_m2": area / 1e6,
                "total_area_m2": (area / 1e6) * 3  # Assuming 3 floors
            }
            
            logger.info(f"Extracted DXF metrics: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"DXF parsing failed: {str(e)}", exc_info=True)
            raise

    def validate_plot(self, shp_path: Path, dxf_metrics: Dict) -> Dict:
        """GIS validation without CRS assumptions"""
        logger.info(f"Validating against plot at {shp_path}")
        try:
            # Read shapefile without CRS manipulation
            gdf = gpd.read_file(str(shp_path))
            
            if gdf.crs is None:
                logger.warning("Shapefile has no CRS, proceeding with raw coordinates")
            
            # Create footprint polygon
            footprint = Polygon([
                (dxf_metrics["setback_left_m"], dxf_metrics["setback_rear_m"]),
                (dxf_metrics["setback_right_m"], dxf_metrics["setback_rear_m"]),
                (dxf_metrics["setback_right_m"], dxf_metrics["setback_front_m"]),
                (dxf_metrics["setback_left_m"], dxf_metrics["setback_front_m"])
            ])
            
            # Compare geometries directly without CRS transformation
            within_plot = footprint.within(gdf.geometry.iloc[0])
            violation_distance = 0.0 if within_plot else footprint.distance(gdf.geometry.iloc[0])
            
            result = {
                "within_plot": within_plot,
                "plot_area_m2": gdf.geometry.iloc[0].area,
                "violation_distance_m": violation_distance
            }
            
            logger.info(f"GIS validation result: {'Valid' if within_plot else f'Invalid (distance: {violation_distance:.2f}m)'}")
            return result
            
        except Exception as e:
            logger.error(f"GIS validation failed: {str(e)}", exc_info=True)
            raise

    def check_compliance(self) -> Tuple[bool, List[str]]:
        """Check only for rules that were found in the PDF"""
        violations = []
        
        # Only check rules that were actually found in the PDF
        if "max_height_m" in self.found_rules:
            if self.dxf_metrics["height_m"] > self.by_laws["max_height_m"]:
                violations.append(f"Height exceeds limit by {self.dxf_metrics['height_m'] - self.by_laws['max_height_m']:.2f}m")
        
        if "min_setback_front_m" in self.found_rules:
            if self.dxf_metrics["setback_front_m"] < self.by_laws["min_setback_front_m"]:
                violations.append(f"Insufficient front setback: {self.dxf_metrics['setback_front_m']:.2f}m < {self.by_laws['min_setback_front_m']}m")
        
        if "min_setback_rear_m" in self.found_rules:
            if self.dxf_metrics["setback_rear_m"] < self.by_laws["min_setback_rear_m"]:
                violations.append(f"Insufficient rear setback: {self.dxf_metrics['setback_rear_m']:.2f}m < {self.by_laws['min_setback_rear_m']}m")
        
        if "min_setback_side_m" in self.found_rules:
            if self.dxf_metrics["setback_left_m"] < self.by_laws["min_setback_side_m"]:
                violations.append(f"Insufficient left side setback: {self.dxf_metrics['setback_left_m']:.2f}m < {self.by_laws['min_setback_side_m']}m")
            if self.dxf_metrics["setback_right_m"] < self.by_laws["min_setback_side_m"]:
                violations.append(f"Insufficient right side setback: {self.dxf_metrics['setback_right_m']:.2f}m < {self.by_laws['min_setback_side_m']}m")
        
        if "max_far" in self.found_rules and self.gis_result["plot_area_m2"] > 0:
            far = self.dxf_metrics["total_area_m2"] / self.gis_result["plot_area_m2"]
            if far > self.by_laws["max_far"]:
                violations.append(f"FAR exceeded: {far:.2f} > {self.by_laws['max_far']:.2f}")
        
        if "max_coverage" in self.found_rules and self.gis_result["plot_area_m2"] > 0:
            coverage = self.dxf_metrics["footprint_area_m2"] / self.gis_result["plot_area_m2"]
            if coverage > self.by_laws["max_coverage"]:
                violations.append(f"Coverage exceeded: {coverage:.1%} > {self.by_laws['max_coverage']:.1%}")
        
        compliant = len(violations) == 0
        logger.info(f"Compliance check complete: {'APPROVED' if compliant else 'REJECTED'}")
        return compliant, violations

    def generate_report(self, approved: bool, violations: List[str]):
        """Generate terminal report"""
        try:
            from colorama import Fore, Style, init
            init()
            
            report = [
                f"\n{Fore.CYAN}=== BUILDING COMPLIANCE REPORT ==={Style.RESET_ALL}",
                f"{Fore.GREEN if approved else Fore.RED}{'✅ APPROVED' if approved else '❌ REJECTED'}{Style.RESET_ALL}",
                f"\n{Fore.YELLOW}Project Metrics:{Style.RESET_ALL}",
                f"- Plot Area: {self.gis_result['plot_area_m2']:.2f} m²",
                f"- Footprint: {self.dxf_metrics['footprint_area_m2']:.2f} m²",
                f"- Total Built Area: {self.dxf_metrics['total_area_m2']:.2f} m²",
                f"- Height: {self.dxf_metrics['height_m']:.2f} m"
            ]
            
            if violations:
                report.extend([
                    f"\n{Fore.RED}Violations:{Style.RESET_ALL}",
                    *[f"{i}. {v}" for i, v in enumerate(violations, 1)]
                ])
            
            print("\n".join(report))
        except ImportError:
            # Fallback without colorama
            report = [
                "\n=== BUILDING COMPLIANCE REPORT ===",
                "APPROVED" if approved else "REJECTED",
                "\nProject Metrics:",
                f"- Plot Area: {self.gis_result['plot_area_m2']:.2f} m²",
                f"- Footprint: {self.dxf_metrics['footprint_area_m2']:.2f} m²",
                f"- Total Built Area: {self.dxf_metrics['total_area_m2']:.2f} m²",
                f"- Height: {self.dxf_metrics['height_m']:.2f} m"
            ]
            if violations:
                report.extend([
                    "\nViolations:",
                    *[f"{i}. {v}" for i, v in enumerate(violations, 1)]
                ])
            print("\n".join(report))

    def run_pipeline(self, pdf_path: Path, dxf_path: Path, shp_path: Path) -> Tuple[bool, List[str]]:
        """Run full compliance pipeline"""
        try:
            # Validate inputs
            for path, name in [(pdf_path, "PDF"), (dxf_path, "DXF"), (shp_path, "Shapefile")]:
                if not path.exists():
                    raise FileNotFoundError(f"{name} file not found")
                if path.stat().st_size == 0:
                    raise ValueError(f"{name} file is empty")
            
            logger.info("Starting compliance pipeline")
            
            # Pipeline phases
            self.by_laws = self.extract_by_laws(pdf_path)
            self.dxf_metrics = self.parse_floor_plan(dxf_path)
            self.gis_result = self.validate_plot(shp_path, self.dxf_metrics)
            approved, violations = self.check_compliance()
            
            self.generate_report(approved, violations)
            return approved, violations
            
        except Exception as e:
            logger.critical(f"Pipeline failed: {str(e)}", exc_info=True)
            raise

def main():
    try:
        checker = BuildingComplianceChecker()
        data_dir = Path(r"D:\Project\Manshant_Project\prototype\sample_files\2\all_data")
        
        paths = {
            "pdf": data_dir / "Bylaw_rule.pdf",
            "dxf": data_dir / "floor_plan_2M.dxf",
            "shp": data_dir / "boundary.shp"
        }
        
        approved, violations = checker.run_pipeline(paths["pdf"], paths["dxf"], paths["shp"])
        sys.exit(0 if approved else 1)
        
    except Exception as e:
        logger.critical(f"Execution failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()