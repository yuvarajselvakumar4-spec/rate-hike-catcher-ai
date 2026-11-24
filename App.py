import streamlit as st
import pandas as pd

st.set_page_config(page_title="Purchase Rate-Hike Catcher AI", layout="wide")

st.title("🔍 Purchase Rate-Hike & Bill Audit AI")
st.write("பழைய அப்ரூவ்ட் ரேட் பட்டியலையும், புது சப்ளையர் பில்லையும் அப்லோட் பண்ணுங்க — ரேட் உயர்வையும் கூடுதல் செலவையும் நொடிகளில் பிடிங்க!")

use_sample = st.checkbox("சாம்பிள் டேட்டா வச்சு உடனே டெஸ்ட் பண்ணிப் பார்க்க (Try with Sample Data)", value=True)

if use_sample:
    old_df = pd.DataFrame({
        "item_code": ["M101", "M102", "M103", "M104", "M105"],
        "item_name": ["SS Bolt 10mm", "Hydraulic Valve", "Bearing 6205", "Copper Wire 2mm", "Gasket Set"],
        "old_unit_price": [12.00, 1450.00, 210.00, 580.00, 95.00]
    })
    inv_df = pd.DataFrame({
        "item_code": ["M101", "M102", "M103", "M104", "M105", "M999"],
        "qty_billed": [500, 10, 40, 25, 100, 5],
        "new_unit_price": [13.50, 1450.00, 235.00, 575.00, 110.00, 300.00]
    })
else:
    col1, col2 = st.columns(2)
    with col1:
        old_file = st.file_uploader("1. Old Approved Rates CSV அப்லோட் பண்ணுங்க", type=["csv"])
    with col2:
        inv_file = st.file_uploader("2. New Supplier Invoice CSV அப்லோட் பண்ணுங்க", type=["csv"])

    if old_file and inv_file:
        old_df = pd.read_csv(old_file)
        inv_df = pd.read_csv(inv_file)
    else:
        st.info("மேலே இரண்டு CSV ஃபைல்களையும் அப்லோட் பண்ணுங்க அல்லது 'Sample Data' டிக் பண்ணுங்க.")
        st.stop()

threshold = st.slider("எத்தனை % மேல் ரேட் ஏறினால் அலர்ட் காட்டணும்? (Alert Threshold %)", 0.0, 20.0, 0.0, 0.5)

old_df["item_code"] = old_df["item_code"].astype(str).str.strip().str.upper()
inv_df["item_code"] = inv_df["item_code"].astype(str).str.strip().str.upper()

merged = pd.merge(inv_df, old_df, on="item_code", how="left")
unmatched = merged[merged["old_unit_price"].isna()]
matched = merged.dropna(subset=["old_unit_price"]).copy()

matched["price_diff"] = matched["new_unit_price"] - matched["old_unit_price"]
matched["hike_pct"] = ((matched["price_diff"] / matched["old_unit_price"]) * 100).round(2)
matched["extra_cost_loss"] = (matched["price_diff"] * matched["qty_billed"]).round(2)

hikes = matched[matched["hike_pct"] > threshold].sort_values(by="extra_cost_loss", ascending=False)

st.divider()
k1, k2, k3 = st.columns(3)
k1.metric("ரேட் ஏறிய ஐட்டங்கள்", f"{len(hikes)} Items")
k2.metric("மொத்த கூடுதல் செலவு (Extra Loss)", f"₹{hikes['extra_cost_loss'].sum():,.2f}")
k3.metric("புது / மேட்ச் ஆகாத ஐட்டங்கள்", f"{len(unmatched)} Items")

st.subheader("🚨 Rate-Hike கண்டுபிடிக்கப்பட்ட ஐட்டங்கள்")
if not hikes.empty:
    display_cols = ["item_name", "old_unit_price", "new_unit_price", "hike_pct", "extra_cost_loss"]
    st.dataframe(hikes[display_cols], width="stretch")

    csv_data = hikes.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Audit Report CSV டவுன்லோட் பண்ணுங்க", data=csv_data, file_name="rate_hike_report.csv", mime="text/csv")

    st.subheader("✉️ சப்ளையருக்கு அனுப்ப வேண்டிய Email Draft")
    email_rows = "\n".join([
        f"* {row['item_name']} ({row['item_code']}): Billed ₹{row['new_unit_price']} vs Approved ₹{row['old_unit_price']} (+{row['hike_pct']}%)"
        for _, row in hikes.iterrows()
    ])
    email_text = f"""Subject: Rate Variance Clarification – Recent Invoice Audit

Hi Supplier Team,

During our routine invoice audit, we noticed unit price increases on the following items compared to our previous approved rates:

{email_rows}

Total variance identified on this bill is ₹{hikes['extra_cost_loss'].sum():,.2f}. Please share the approved revision note before we process payment for the variance portion.

Best regards,
Procurement Team"""
    st.text_area("Copy & Send:", email_text, height=220)
else:
    st.success("இந்த பில்லில் எந்த அங்கீகரிக்கப்படாத ரேட் உயர்வும் இல்லை!")

if not unmatched.empty:
    st.warning("⚠️ பழைய ரேட் பட்டியலில் இல்லாத புது ஐட்டங்கள்:")
    st.dataframe(unmatched[["item_code", "qty_billed", "new_unit_price"]], width="stretch")
