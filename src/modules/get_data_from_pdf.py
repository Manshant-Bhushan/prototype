import logging
from pathlib import Path
import pdfplumber
import re
from typing import Dict, Set

logger = logging.getLogger(__name__)

class PDFDataExtractor:
    def __init__(self):
        self.found_rules = set()
        self.rule_mappings = {
            "front setback": "min_setback_front_m",
            "rear setback": "min_setback_rear_m",
            "side setback": "min_setback_side_m",
            "height": "max_height_m",
            "far": "max_far",
            "coverage": "max_coverage"
        }

    def extract_by_laws(self, pdf_path: Path) -> Dict:
        """Extract regulations from PDF table"""
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
                for page in pdf.pages:
                    # Extract tables from each page
                    tables = page.extract_tables()
                    for table in tables:
                        if len(table) > 0 and "Rule Name" in table[0][0].lower():
                            # This is the header row, process subsequent rows
                            for row in table[1:]:
                                if len(row) >= 4:  # Ensure we have enough columns
                                    self._process_table_row(row, rules)
                    
                    # If no rules found in tables, try text extraction
                    if not any(rules.values()):
                        text = page.extract_text()
                        if text:
                            self._parse_text(text, rules)

            logger.info(f"Extracted rules: { {k:v for k,v in rules.items() if v is not None} }")
            return rules

        except Exception as e:
            logger.error(f"PDF parsing failed: {str(e)}", exc_info=True)
            raise

    def _process_table_row(self, row: list, rules: Dict):
        """Process a single table row from the PDF"""
        try:
            rule_name = row[0].strip().lower()
            value_str = row[2].strip()  # Value is in third column
            units = row[3].strip().lower() if len(row) > 3 else ""
            
            # Map rule names to our standard keys
            for keyword, rule_key in self.rule_mappings.items():
                if keyword in rule_name:
                    value = self._extract_numeric_value(value_str)
                    if value is not None:
                        # Handle percentage values
                        if "%" in units and rule_key == "max_coverage":
                            value = value / 100
                        rules[rule_key] = value
                        self.found_rules.add(rule_key)
                    break
        except Exception as e:
            logger.debug(f"Error processing table row: {str(e)}")

    def _parse_text(self, text: str, rules: Dict):
        """Fallback text parsing if table extraction fails"""
        patterns = {
            "min_setback_front_m": r"front\s*setback.*?(\d+\.?\d*)\s*m",
            "min_setback_rear_m": r"rear\s*setback.*?(\d+\.?\d*)\s*m",
            "min_setback_side_m": r"side\s*setback.*?(\d+\.?\d*)\s*m",
            "max_height_m": r"height.*?(\d+\.?\d*)\s*m",
            "max_far": r"far.*?(\d+\.?\d*)",
            "max_coverage": r"coverage.*?(\d+\.?\d*)%"
        }
        
        for rule_key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    if rule_key == "max_coverage":
                        value = value / 100
                    rules[rule_key] = value
                    self.found_rules.add(rule_key)
                except (ValueError, IndexError):
                    continue

    def _extract_numeric_value(self, text: str) -> float:
        """Extract numeric value from text"""
        try:
            # Remove any non-numeric characters except decimal point
            cleaned = re.sub(r"[^\d.]", "", text)
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def get_found_rules(self) -> Set[str]:
        """Return set of found rule names"""
        return self.found_rules