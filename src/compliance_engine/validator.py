from typing import Dict, List, Tuple
import math

def check_compliance(dxf_metrics: Dict[str, float], 
                    gis_result: Dict[str, float], 
                    by_laws: Dict[str, float]) -> Tuple[bool, List[str]]:
    """
    Validates building design against by-laws and plot constraints
    
    Args:
        dxf_metrics: {
            "height_m": float, 
            "setback_front_m": float,
            "setback_rear_m": float,
            "setback_left_m": float,
            "setback_right_m": float,
            "footprint_area_m2": float,
            "total_area_m2": float
        }
        gis_result: {
            "within_plot": bool,
            "plot_area_m2": float,
            "violation_distance_m": float
        }
        by_laws: {
            "max_height_m": float,
            "min_setback_front_m": float,
            "min_setback_rear_m": float,
            "min_setback_side_m": float,
            "max_far": float,
            "max_coverage": float
        }
    
    Returns:
        Tuple[approved: bool, violations: List[str]]
    """
    violations = []
    
    # 1. GIS Boundary Validation
    if not gis_result["within_plot"]:
        violations.append(
            f"Plot boundary violation: {gis_result['violation_distance_m']:.2f}m beyond plot"
        )
    
    # 2. Height Check
    if dxf_metrics["height_m"] > by_laws["max_height_m"]:
        excess = dxf_metrics["height_m"] - by_laws["max_height_m"]
        violations.append(
            f"Height exceeds limit: {dxf_metrics['height_m']:.2f}m > {by_laws['max_height_m']}m "
            f"(+{excess:.2f}m)"
        )
    
    # 3. Setback Checks
    def check_setback(name: str, actual: float, required: float):
        if actual < required:
            violations.append(
                f"Insufficient {name} setback: {actual:.2f}m < {required}m "
                f"(missing {required-actual:.2f}m)"
            )
    
    check_setback("front", dxf_metrics["setback_front_m"], by_laws["min_setback_front_m"])
    check_setback("rear", dxf_metrics["setback_rear_m"], by_laws["min_setback_rear_m"])
    check_setback("left side", dxf_metrics["setback_left_m"], by_laws["min_setback_side_m"])
    check_setback("right side", dxf_metrics["setback_right_m"], by_laws["min_setback_side_m"])
    
    # 4. Floor Area Ratio (FAR)
    far = dxf_metrics["total_area_m2"] / gis_result["plot_area_m2"]
    if far > by_laws["max_far"]:
        violations.append(
            f"FAR exceeded: {far:.2f} > {by_laws['max_far']} "
            f"(max {gis_result['plot_area_m2']*by_laws['max_far']:.2f}m² allowed)"
        )
    
    # 5. Ground Coverage
    coverage = dxf_metrics["footprint_area_m2"] / gis_result["plot_area_m2"]
    if coverage > by_laws["max_coverage"]:
        violations.append(
            f"Coverage exceeded: {coverage:.1%} > {by_laws['max_coverage']:.0%} "
            f"(max {gis_result['plot_area_m2']*by_laws['max_coverage']:.2f}m²)"
        )
    
    # 6. Special Cases
    if by_laws.get("min_parking_spaces", 0) > 0:
        required_parking = math.ceil(dxf_metrics["total_area_m2"] / by_laws["parking_area_per_unit"])
        if dxf_metrics.get("parking_spaces", 0) < required_parking:
            violations.append(
                f"Insufficient parking: {dxf_metrics.get('parking_spaces', 0)} < {required_parking} "
                f"(1 space per {by_laws['parking_area_per_unit']}m²)"
            )
    
    return (len(violations) == 0, violations)


# Example Test Case
if __name__ == "__main__":
    # Mock data
    test_dxf = {
        "height_m": 16.5,
        "setback_front_m": 4.8,
        "setback_rear_m": 3.2,
        "setback_left_m": 1.9,
        "setback_right_m": 2.1,
        "footprint_area_m2": 450,
        "total_area_m2": 2700,
        "parking_spaces": 8
    }
    
    test_gis = {
        "within_plot": True,
        "plot_area_m2": 1200,
        "violation_distance_m": 0.0
    }
    
    test_by_laws = {
        "max_height_m": 15,
        "min_setback_front_m": 5,
        "min_setback_rear_m": 3,
        "min_setback_side_m": 2,
        "max_far": 2.0,
        "max_coverage": 0.4,
        "parking_area_per_unit": 300,
        "min_parking_spaces": 1
    }
    
    approved, violations = check_compliance(test_dxf, test_gis, test_by_laws)
    
    print(f"\nApproved: {approved}")
    if not approved:
        print("Violations:")
        for i, violation in enumerate(violations, 1):
            print(f"{i}. {violation}")