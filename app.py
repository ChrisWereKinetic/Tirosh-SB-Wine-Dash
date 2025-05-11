import streamlit as st
import glob
import os
import pandas as pd
import fitz  # PyMuPDF
import re
import datetime

def extract_nz_bulk_price_from_pdf(pdf_path):
    results = []
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    lines = full_text.splitlines()
    for i, line in enumerate(lines):
        if "NZ Marlborough SB" in line:
            # Extract vintage from previous line
            vintage = None
            if i > 0 and re.match(r"\d{4}", lines[i-1].strip()):
                vintage = lines[i-1].strip()
            # Extract price from next line
            if i + 1 < len(lines):
                price_line = lines[i+1]
                match = re.search(r"NZD\s*(\d+\.\d+)\s*[-–to]+\s*(\d+\.\d+)", price_line, re.IGNORECASE)
                if match:
                    results.append({
                        "vintage": vintage,
                        "low_price": float(match.group(1)),
                        "high_price": float(match.group(2))
                    })
    return results

st.header("📊 NZ Marlborough SB Bulk Price History")

report_folder = "Ciatti Reports"
pdf_files = sorted(glob.glob(os.path.join(report_folder, "*.pdf")))

# Extract data from all PDFs
price_history = []
for pdf_path in pdf_files:
    results = extract_nz_bulk_price_from_pdf(pdf_path)
    if results:
        for entry in results:
            fname = os.path.basename(pdf_path)
            m = re.search(r"-(January|February|March|April|May|June|July|August|September|October|November|December)-(\d{4})", fname)
            if m:
                report_date = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%B %Y").date()
            else:
                report_date = None
            price_history.append({
                "Report Date": report_date,
                "Vintage": entry["vintage"],
                "Low Price": entry["low_price"],
                "High Price": entry["high_price"],
                "Mid Price": (entry["low_price"] + entry["high_price"]) / 2
            })

# Show table and chart
if price_history:
    df = pd.DataFrame(price_history)
    df = df.dropna(subset=['Report Date'])
    df = df.sort_values(by=['Vintage', 'Report Date'])
    st.dataframe(df)

    pivot_df = df.pivot(index="Report Date", columns="Vintage", values="Mid Price")
    st.line_chart(pivot_df)
else:
    st.warning("No vintage price data found in available reports.")