import sys
from pathlib import Path
from src.utils.logger import setup_logger
from src.pdf_parser import extract_by_laws
from src.autocad_parser import parse_floor_plan
from src.gis_processor import validate_plot
from src.compliance_engine import check_compliance

logger = setup_logger()

def main():
    try:
        logger.info("Starting building compliance check")
        
        # 1. Load by-laws
        logger.info("Extracting by-laws from PDF")
        by_laws = extract_by_laws("data/by_laws.pdf")
        
        # 2. Parse AutoCAD file
        logger.info("Processing floor plan")
        dxf_metrics = parse_floor_plan("data/floor_plan.dwg")
        
        # 3. Validate against plot
        logger.info("Validating plot boundaries")
        gis_result = validate_plot(
            "data/plot_utm.shp",
            dxf_metrics,
            target_crs="EPSG:32644"  # UTM Zone 44N
        )
        
        # 4. Check compliance
        logger.info("Running compliance checks")
        approved, violations = check_compliance(dxf_metrics, gis_result, by_laws)
        
        # 5. Generate report
        print("\n=== COMPLIANCE REPORT ===")
        print(f"Result: {'APPROVED' if approved else 'REJECTED'}")
        print(f"Plot Area: {gis_result['plot_area_m2']:.2f} m²")
        print(f"Footprint Area: {dxf_metrics['footprint_area_m2']:.2f} m²")
        print(f"Total Built Area: {dxf_metrics['total_area_m2']:.2f} m²")
        
        if not approved:
            print("\nVIOLATIONS DETECTED:")
            for i, violation in enumerate(violations, 1):
                print(f"{i}. {violation}")
        else:
            print("\nAll checks passed successfully!")
            
        return 0 if approved else 1
        
    except FileNotFoundError as e:
        logger.error(f"Missing file: {e.filename}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())