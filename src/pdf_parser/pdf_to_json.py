import pdfplumber
import re
import json
import argparse
from typing import Dict, List

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a single PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages)

def extract_numerical_rules(text: str) -> List[Dict[str, str]]:
    """
    Extract all numerical rules (e.g., "5m", "2.5") with context.
    Returns: [{"value": "5m", "context": "Front setback must be at least 5m"}, ...]
    """
    # Match numbers with units (e.g., "5m", "2.5") and their sentences
    pattern = re.compile(r"(\d+\.?\d*\s*[mM%°]?)")
    sentences = text.split('\n')
    rules = []
    
    for sent in sentences:
        matches = pattern.findall(sent)
        if matches:
            for match in matches:
                rules.append({
                    "value": match.strip(),
                    "context": sent.strip()
                })
    return rules

def main():
    parser = argparse.ArgumentParser(description="Extract numerical rules from a by-law PDF.")
    parser.add_argument("pdf_path", help="Path to the by-law PDF file.")
    parser.add_argument("--save", help="Optional: Path to save JSON output.", default=None)
    args = parser.parse_args()

    text = extract_text_from_pdf(args.pdf_path)
    rules = extract_numerical_rules(text)
    
    if args.save:
        with open(args.save, "w") as f:
            json.dump(rules, f, indent=2)
        print(f"Rules saved to {args.save}")
    else:
        print("=== Extracted Numerical Rules ===")
        for rule in rules:
            print(f"{rule['value']} (Context: {rule['context']})")

if __name__ == "__main__":
    main()