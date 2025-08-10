import warnings
from pathlib import Path
from src.pdf_parser.pdf_to_json import extract_by_laws
from src.autocad_parser.dwg_parser import parse_floor_plan
from src.gis_processor.shp_processor import validate_plot
from src.compliance_engine.validator import check_compliance

# Disable warnings
warnings.filterwarnings("ignore")

def main():
    try:
        # 1. Extract by-laws
        by_laws = extract_by_laws("D:\Project\Manshant_Project\prototype\sample_files\1\by-laws\Bylaw_rule.pdf")
        
        # 2. Parse AutoCAD
        dxf_metrics = parse_floor_plan(r"D:\Project\Manshant_Project\prototype\sample_files\1\floor_plan\09-08-2025_PHYTON PROTOTYPE_4M.dxf")
        
        # 3. Validate against plot boundaries
        gis_result = validate_plot(
            "data/plot_utm.shp", 
            dxf_metrics,
            target_crs="EPSG:32644"  # UTM Zone 44N (India)
        )
        
        # 4. Final compliance check
        approval, report = check_compliance(
            dxf_metrics=dxf_metrics,
            gis_result=gis_result,
            by_laws=by_laws
        )
        
        print("\n=== Final Result ===")
        print(f"Approved: {approval}")
        print("Violations:" if not approval else "Compliant with:")
        for item in report:
            print(f"- {item}")

    except Exception as e:
        print(f"Pipeline failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()