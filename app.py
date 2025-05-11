import streamlit as st
import glob
import os
import pandas as pd
import fitz  # PyMuPDF
import re
import datetime
import requests
from pytrends.request import TrendReq


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



@st.cache_data
def get_historical_exchange_rates():
    start_date = "2022-06-01"
    end_date = datetime.date.today().isoformat()
    url = f"https://api.frankfurter.app/{start_date}..{end_date}?from=NZD&to=USD,GBP,EUR"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        rates = data.get("rates", {})
        if not rates:
            st.error("No exchange rate data returned.")
            return pd.DataFrame()
        records = [{"Date": pd.to_datetime(date), **values} for date, values in rates.items()]
        df = pd.DataFrame(records).sort_values("Date")
        return df
    except Exception as e:
        st.error(f"Failed to fetch exchange rates: {e}")
        return pd.DataFrame()

@st.cache_data
def get_trend_data(term, region=""):
    pytrends = TrendReq()
    pytrends.build_payload([term], geo=region)
    df = pytrends.interest_over_time()
    return df[[term]] if not df.empty else pd.DataFrame()


st.title("🍇 Sauvignon Blanc Market Dashboard")

st.header("🚢 TODO...")
st.markdown("Add SB Productions stats from NZ winegrowers")

# Exchange Rates Section
st.header("💱 Historical Exchange Rates (Since June 2022)")
fx_df = get_historical_exchange_rates()
fx_df = fx_df[fx_df["Date"] >= "2022-06-01"]
st.line_chart(fx_df.set_index("Date"))


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
    df = df.sort_values(by=['Report Date', 'Vintage'])
    df = df[df["Report Date"] >= datetime.date(2022, 6, 1)]
    st.markdown("**Source:** Ciatti Global Market Reports (local PDFs in `Ciatti Reports` folder)")
    st.dataframe(df)

    pivot_df = df.pivot(index="Report Date", columns="Vintage", values="Mid Price")
    st.line_chart(pivot_df)
else:
    st.warning("No vintage price data found in available reports.")



# --- NZ Wine Export Volume Time Series ---
st.header("🚢 NZ Wine Exports (Monthly Volume)")

# Load local export CSV (pre-downloaded from Stats NZ)
export_file = "nz wine exports.csv"
if os.path.exists(export_file):
    export_df = pd.read_csv(export_file)

    # Normalize and parse date
    month_lookup = {m: i for i, m in enumerate(
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], start=1)}
    export_df["Month"] = export_df["Month"].astype(str).str.strip().str[:3]
    export_df["MonthNum"] = export_df["Month"].map(month_lookup)
    export_df["MonthNum"] = pd.to_numeric(export_df["MonthNum"], errors="coerce")
    export_df = export_df.dropna(subset=["Year", "MonthNum"])


    # Drop or warn about rows where month mapping failed
    invalid_months = export_df[export_df["MonthNum"].isna()]
    if not invalid_months.empty:
        st.warning(f"Some rows had invalid or missing month values and were excluded: {invalid_months[['Year', 'Month']]}")
        export_df = export_df.dropna(subset=["MonthNum"])



    # Identify rows missing required date fields
    missing_parts = export_df[["Year", "MonthNum"]].isna().any(axis=1)
    if missing_parts.any():
        st.warning("Some rows are missing date components (Year or MonthNum) and will be excluded.")
        st.dataframe(export_df.loc[missing_parts])
        # Optionally write them to a CSV
        export_df.loc[missing_parts].to_csv("invalid_export_rows.csv", index=False)

    export_df = export_df[~missing_parts]



    # Assign a constant day value (1) to create a complete date for each row
    export_df["Year"] = export_df["Year"].astype(int)
    export_df["MonthNum"] = export_df["MonthNum"].astype(int)
    export_df["Date"] = pd.to_datetime(
        export_df["Year"].astype(str) + "-" + export_df["MonthNum"].astype(str).str.zfill(2) + "-01",
        format="%Y-%m-%d",
        errors="coerce"
    )

    export_df = export_df.dropna(subset=["Date"])

    export_df = export_df.sort_values("Date")
    export_df = export_df[export_df["Date"] >= "2022-06-01"]
    export_df = export_df.rename(columns={"Exports (million L)": "Volume (M L)"})
    export_df = export_df[["Date", "Volume (M L)"]]
    st.markdown("**Source:** [Stats NZ](https://www.stats.govt.nz/) — Overseas Merchandise Trade Feb 2025")
    st.line_chart(export_df.set_index("Date"))
   
else:
    st.warning("Export file not found: nz wine exports.csv")


# Google Trends Section
st.header("📈 Google Trends: Interest Over Time")
trend_term = st.selectbox("Choose a search term", ["Sauvignon Blanc", "NZ Wine", "Marlborough wine"])
trend_data = get_trend_data(trend_term, region="NZ")
trend_data = trend_data[trend_data.index >= "2022-06-01"]
if not trend_data.empty:
    st.line_chart(trend_data)
else:
    st.warning("No trend data available for the selected term.")