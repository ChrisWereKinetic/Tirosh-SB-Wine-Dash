import fitz
import re

def extract_nz_bulk_price_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    results = []
    lines = full_text.splitlines()

    for i, line in enumerate(lines):
        if "NZ Marlborough SB" in line:
            vintage = None
            price_line = None

            # Try to find a vintage above
            if i > 0 and re.match(r"\d{4}", lines[i - 1].strip()):
                vintage = lines[i - 1].strip()

            # Try to find price below
            if i + 1 < len(lines):
                price_line = lines[i + 1]
                match = re.search(r"NZD\s*(\d+\.\d+)\s*[-–to]+\s*(\d+\.\d+)", price_line, re.IGNORECASE)
                if match:
                    results.append({
                        "vintage": vintage,
                        "low_price": float(match.group(1)),
                        "high_price": float(match.group(2))
                    })

    if results:
        for result in results:
            print(f"✅ {result['vintage']}: ${result['low_price']} – ${result['high_price']}")
    else:
        print("❌ No matches found.")
        print(f"Total characters in PDF text: {len(full_text)}")

    return results

if __name__ == "__main__":
    extract_nz_bulk_price_from_pdf("Ciatti Reports/Global-Market-Report-April-2025-1.pdf")