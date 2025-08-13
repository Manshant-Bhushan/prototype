import sys
import logging
from pathlib import Path
from datetime import datetime
from src.modules.get_data_from_pdf import PDFDataExtractor
from src.modules.get_data_from_dxf import DXFDataExtractor
from src.modules.get_data_from_shp import ShapefileValidator
from src.modules.compliance_validator import ComplianceValidator
from typing import Tuple, List

import os
os.environ['PROJ_LIB'] = r'D:\Project\Manshant_Project\prototype\manshant_project\Library\share\proj'

def configure_logging():
    """Set up comprehensive logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                f'compliance_pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
                encoding='utf-8'
            ),
            logging.StreamHandler(sys.stdout)  # Explicitly use stdout
        ]
    )
    return logging.getLogger(__name__)

class CompliancePipeline:
    def __init__(self):
        self.logger = configure_logging()
        self.pdf_extractor = PDFDataExtractor()
        self.dxf_extractor = DXFDataExtractor()
        self.gis_validator = ShapefileValidator()
        self.validator = ComplianceValidator()

    def run_pipeline(self, pdf_path: Path, dxf_path: Path, shp_path: Path) -> Tuple[bool, List[str]]:
        """Execute full compliance checking pipeline with enhanced debugging"""
        self.logger.info("Starting compliance pipeline")
        
        try:
            # Phase 1: PDF Processing
            print("\n" + "="*40)
            print("PHASE 1: EXTRACTING BY-LAWS FROM PDF")
            print("="*40)
            by_laws = self.pdf_extractor.extract_by_laws(pdf_path)
            found_rules = self.pdf_extractor.get_found_rules()
            print("\nPDF EXTRACTION RESULTS:")
            print(f"Found rules: {by_laws}")
            print(f"Rules detected: {found_rules}")
            
            # Phase 2: DXF Processing
            print("\n" + "="*40)
            print("PHASE 2: EXTRACTING METRICS FROM DXF")
            print("="*40)
            dxf_metrics = self.dxf_extractor.parse_floor_plan(dxf_path)
            print("\nDXF PROCESSING RESULTS:")
            for k, v in dxf_metrics.items():
                unit = "m" if k.endswith("_m") else "m²" if k.endswith("_m2") else ""
                print(f"{k}: {v:.2f}{unit}")
            
            # Phase 3: GIS Validation
            print("\n" + "="*40)
            print("PHASE 3: VALIDATING AGAINST PLOT BOUNDARIES")
            print("="*40)
            gis_result = self.gis_validator.validate_plot(shp_path, dxf_metrics)
            self.gis_validator.print_validation_summary()
            
            # Phase 4: Compliance Checking
            print("\n" + "="*40)
            print("PHASE 4: CHECKING COMPLIANCE")
            print("="*40)
            approved, violations = self.validator.check_compliance(
                by_laws, dxf_metrics, gis_result, found_rules
            )
            self.validator.print_compliance_summary()
            
            return approved, violations
            
        except Exception as e:
            self.logger.critical(f"Pipeline failed: {str(e)}", exc_info=True)
            raise

def main():
    try:
        pipeline = CompliancePipeline()
        data_dir = Path(r"D:\Project\Manshant_Project\prototype\sample_files\1\all_data")
        
        paths = {
            "pdf": data_dir / "Bylaw_rule.pdf",
            "dxf": data_dir / "floor_plan_4M.dxf",
            "shp": data_dir / "boundary.shp"
        }
        
        # Validate all input files exist
        for name, path in paths.items():
            if not path.exists():
                raise FileNotFoundError(f"{name} file not found at {path}")
            print(f"Found {name} file: {path}")
        
        approved, violations = pipeline.run_pipeline(
            paths["pdf"], paths["dxf"], paths["shp"]
        )
        sys.exit(0 if approved else 1)
        
    except Exception as e:
        logging.getLogger(__name__).critical(f"Execution failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Add current directory to Python path
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    main()