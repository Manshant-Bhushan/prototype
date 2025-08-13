import logging
from typing import Dict, List, Tuple, Set

logger = logging.getLogger(__name__)

class ComplianceValidator:
    def __init__(self):
        self.violations = []
        self.compliant = True

    def check_compliance(self, by_laws: Dict, dxf_metrics: Dict, 
                        gis_result: Dict, found_rules: Set[str]) -> Tuple[bool, List[str]]:
        """Check compliance with detailed rule validation and debugging"""
        logger.info("Starting compliance checks")
        self.violations = []
        
        # Print header for debug output
        logger.info("\nCOMPLIANCE CHECKS")
        logger.info("----------------")
        
        # Check each rule only if it exists in the PDF
        self._check_height(by_laws, dxf_metrics, found_rules)
        self._check_setbacks(by_laws, dxf_metrics, found_rules)
        self._check_far(by_laws, dxf_metrics, gis_result, found_rules)
        self._check_coverage(by_laws, dxf_metrics, gis_result, found_rules)
        
        self.compliant = len(self.violations) == 0
        status = "PASSED" if self.compliant else "FAILED"
        logger.info(f"\nOVERALL COMPLIANCE: {status}")
        logger.info(f"Violations found: {len(self.violations)}")
        
        return self.compliant, self.violations

    def _check_height(self, by_laws: Dict, dxf_metrics: Dict, found_rules: Set[str]):
        """Validate building height"""
        if "max_height_m" in found_rules:
            actual = dxf_metrics["height_m"]
            allowed = by_laws["max_height_m"]
            logger.info(f"Height Check: {actual:.2f}m vs {allowed:.2f}m limit")
            
            if actual > allowed:
                violation = f"Height exceeds limit by {actual - allowed:.2f}m"
                self.violations.append(violation)
                logger.warning(f"VIOLATION: {violation}")
            else:
                logger.info("✓ Height compliant")

    def _check_setbacks(self, by_laws: Dict, dxf_metrics: Dict, found_rules: Set[str]):
        """Validate all setback requirements"""
        setbacks = [
            ("front", "min_setback_front_m", "setback_front_m"),
            ("rear", "min_setback_rear_m", "setback_rear_m"),
            ("left side", "min_setback_side_m", "setback_left_m"), 
            ("right side", "min_setback_side_m", "setback_right_m")
        ]
        
        for name, rule_key, metric_key in setbacks:
            if rule_key in found_rules:
                actual = dxf_metrics[metric_key]
                required = by_laws[rule_key]
                logger.info(f"{name.title()} Setback: {actual:.2f}m vs {required:.2f}m required")
                
                if actual < required:
                    violation = f"Insufficient {name} setback: {actual:.2f}m < {required}m"
                    self.violations.append(violation)
                    logger.warning(f"VIOLATION: {violation}")
                else:
                    logger.info(f"✓ {name.title()} setback compliant")

    def _check_far(self, by_laws: Dict, dxf_metrics: Dict, 
                 gis_result: Dict, found_rules: Set[str]):
        """Validate Floor Area Ratio"""
        if "max_far" in found_rules and gis_result["plot_area_m2"] > 0:
            far = dxf_metrics["total_area_m2"] / gis_result["plot_area_m2"]
            allowed = by_laws["max_far"]
            logger.info(f"FAR Check: {far:.2f} vs {allowed:.2f} limit")
            
            if far > allowed:
                violation = f"FAR exceeded: {far:.2f} > {allowed:.2f}"
                self.violations.append(violation)
                logger.warning(f"VIOLATION: {violation}")
            else:
                logger.info("✓ FAR compliant")

    def _check_coverage(self, by_laws: Dict, dxf_metrics: Dict,
                      gis_result: Dict, found_rules: Set[str]):
        """Validate Site Coverage"""
        if "max_coverage" in found_rules and gis_result["plot_area_m2"] > 0:
            coverage = dxf_metrics["footprint_area_m2"] / gis_result["plot_area_m2"]
            allowed = by_laws["max_coverage"]
            logger.info(f"Coverage Check: {coverage:.1%} vs {allowed:.1%} limit")
            
            if coverage > allowed:
                violation = f"Coverage exceeded: {coverage:.1%} > {allowed:.1%}"
                self.violations.append(violation)
                logger.warning(f"VIOLATION: {violation}")
            else:
                logger.info("✓ Coverage compliant")

    def print_compliance_summary(self):
        """Print formatted compliance results"""
        print("\nCOMPLIANCE SUMMARY")
        print("-----------------")
        print(f"Overall Status: {'APPROVED' if self.compliant else 'REJECTED'}")
        
        if self.violations:
            print("\nVIOLATIONS FOUND:")
            for i, violation in enumerate(self.violations, 1):
                print(f"{i}. {violation}")
        else:
            print("\nNo violations found - Building plan is compliant!")