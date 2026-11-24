import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Purchase Rate-Hike Catcher AI",
    page_icon="🔍",
    layout="wide"
)

# --- 1. Top Controls: Language & Currency ---
top_c1, top_c2, top_c3 = st.columns([2, 1, 1])
with top_c2:
    lang = st.selectbox(
        "🌐 Language / மொழி",
        ["Bilingual (English + தமிழ்)", "English", "தமிழ் (Tamil)"]
    )
with top_c3:
    currency = st.selectbox("💱 Currency", ["₹ (INR)", "$ (USD)", "€ (EUR)"])

curr_sym = currency.split(" ")[0]

def t(en, ta):
    if lang == "English":
        return en
    elif lang == "தமிழ் (Tamil)":
        return ta
    return f"{en} / {ta}"

# --- 2. Header & Privacy Note ---
st.title("🔍 Purchase Rate-Hike & Bill Audit AI")
st.write(t(
    "Audit supplier invoices against approved rates in seconds — spot unauthorized price hikes, calculate extra spend, export reports & draft supplier emails.",
    "அப்ரூவ்ட் ரேட் பட்டியலோடு புது சப்ளையர் பில்லை நொடிகளில் ஒப்பிடுங்க — தேவையற்ற ரேட் உயர்வு, கூடுதல் செலவு, ரிப்போர்ட் & சப்ளையர் மெயில் டிராஃப்ட் அனைத்தும் ஒரே இடத்தில்!"
))

st.info(t(
    "🔒 Privacy Note: Uploaded CSV files are processed in memory for your session and are not permanently stored in a database. Do not upload sensitive passwords or keys.",
    "🔒 பாதுகாப்பு குறிப்பு: அப்லோட் செய்யப்படும் CSV கோப்புகள் இந்த செஷனில் மட்டுமே கணக்கிடப்படும்; டேட்டாபேஸில் நிரந்தரமாகச் சேமிக்கப்படாது. பாஸ்வேர்ட் அல்லது ரகசிய கீ-களை அப்லோட் செய்ய வேண்டாம்."
))

# --- 3. Sample CSV Templates Download ---
sample_old = pd.DataFrame({
    "item_code": ["M101", "M102", "M103", "M104", "M105"],
    "item_name": ["SS Bolt 10mm", "Hydraulic Valve", "Bearing 6205", "Copper Wire 2mm", "Gasket Set"],
    "old_unit_price": [12.00, 1450.00, 210.00, 580.00, 95.00]
})

sample_inv = pd.DataFrame({
    "item_code": ["M101", "M102", "M103", "M104", "M105", "M999"],
    "qty_billed": [500, 10, 40, 25, 100, 5],
    "new_unit_price": [13.50, 1450.00, 235.00, 575.00, 110.00, 300.00]
})

with st.expander(t("📄 Need Sample CSV Templates? Download here", "📄 சாம்பிள் CSV டெம்ப்ளேட் வேண்டுமா? இங்கே டவுன்லோட் செய்யவும்")):
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            t("⬇️ Sample Old Rates CSV", "⬇️ சாம்பிள் பழைய ரேட் CSV"),
            data=sample_old.to_csv(index=False).encode("utf-8"),
            file_name="sample_old_approved_rates.csv",
            mime="text/csv"
        )
    with d2:
        st.download_button(
            t("⬇️ Sample New Invoice CSV", "⬇️ சாம்பிள் புது பில் CSV"),
            data=sample_inv.to_csv(index=False).encode("utf-8"),
            file_name="sample_new_invoice.csv",
            mime="text/csv"
        )

# --- 4. Helper for Flexible Column Matching ---
def find_col(columns, candidates):
    lower_map = {c.strip().lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for c in columns:
        cl = c.strip().lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return columns[0] if len(columns) > 0 else None

# --- 5. Data Source: Demo or Company CSV Upload ---
use_sample = st.checkbox(
    t("Use built-in demo data right now", "இப்போதே உள்ளமைக்கப்பட்ட டெமோ டேட்டாவைப் பயன்படுத்தவும்"),
    value=True
)

if use_sample:
    old_df = sample_old.copy()
    inv_df = sample_inv.copy()
    old_code_col, old_name_col, old_price_col = "item_code", "item_name", "old_unit_price"
    inv_code_col, inv_qty_col, inv_price_col = "item_code", "qty_billed", "new_unit_price"
else:
    u1, u2 = st.columns(2)
    with u1:
        old_file = st.file_uploader(
            t("1. Old Approved Rates CSV", "1. பழைய Approved Rates CSV"),
            type=["csv"]
        )
    with u2:
        inv_file = st.file_uploader(
            t("2. New Supplier Invoice CSV", "2. புது Supplier Invoice CSV"),
            type=["csv"]
        )

    if not (old_file and inv_file):
        st.warning(t(
            "Please upload both CSV files above, or check 'Use built-in demo data right now' to test.",
            "இரண்டு CSV கோப்புகளையும் மேலே அப்லோட் செய்யவும், அல்லது டெமோ டேட்டாவைத் தேர்வு செய்யவும்."
        ))
        st.stop()

    try:
        old_raw = pd.read_csv(old_file)
        inv_raw = pd.read_csv(inv_file)
    except Exception as e:
        st.error(t(f"Could not read CSV files: {e}", f"CSV கோப்புகளைப் படிக்க முடியவில்லை: {e}"))
        st.stop()

    with st.expander(t("🧩 Column Mapping (Auto-detected — adjust if needed)", "🧩 காலம் மேப்பிங் (தானாகக் கண்டறியப்பட்டது — தேவைப்பட்டால் மாற்றவும்)"), expanded=False):
        m1, m2, m3 = st.columns(3)
        with m1:
            old_code_col = st.selectbox(
                t("Old Rate: Item Code Column", "பழைய ரேட்: Item Code காலம்"),
                old_raw.columns,
                index=list(old_raw.columns).index(find_col(old_raw.columns, ["item_code", "code", "sku", "item_id", "id"]))
            )
        with m2:
            old_name_col = st.selectbox(
                t("Old Rate: Item Name Column", "பழைய ரேட்: Item Name காலம்"),
                old_raw.columns,
                index=list(old_raw.columns).index(find_col(old_raw.columns, ["item_name", "name", "description", "item", "material"]))
            )
        with m3:
            old_price_col = st.selectbox(
                t("Old Rate: Approved Price Column", "பழைய ரேட்: Approved Price காலம்"),
                old_raw.columns,
                index=list(old_raw.columns).index(find_col(old_raw.columns, ["old_unit_price", "old_price", "approved_price", "rate", "price"]))
            )

        n1, n2, n3 = st.columns(3)
        with n1:
            inv_code_col = st.selectbox(
                t("Invoice: Item Code Column", "பில்: Item Code காலம்"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(find_col(inv_raw.columns, ["item_code", "code", "sku", "item_id", "id"]))
            )
        with n2:
            inv_qty_col = st.selectbox(
                t("Invoice: Quantity Column", "பில்: Quantity காலம்"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(find_col(inv_raw.columns, ["qty_billed", "qty", "quantity", "billed_qty"]))
            )
        with n3:
            inv_price_col = st.selectbox(
                t("Invoice: New Unit Price Column", "பில்: New Unit Price காலம்"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(find_col(inv_raw.columns, ["new_unit_price", "new_price", "billed_price", "rate", "price"]))
            )

    old_df = pd.DataFrame({
        "item_code": old_raw[old_code_col],
        "item_name": old_raw[old_name_col],
        "old_unit_price": pd.to_numeric(old_raw[old_price_col], errors="coerce")
    })
    inv_df = pd.DataFrame({
        "item_code": inv_raw[inv_code_col],
        "qty_billed": pd.to_numeric(inv_raw[inv_qty_col], errors="coerce"),
        "new_unit_price": pd.to_numeric(inv_raw[inv_price_col], errors="coerce")
    })

# --- 6. Threshold & Audit Calculation ---
threshold = st.slider(
    t("Alert Threshold (% hike above approved rate)", "அலர்ட் வரம்பு (அப்ரூவ்ட் ரேட்டை விட எத்தனை % கூடினால் காட்டணும்?)"),
    0.0, 30.0, 0.0, 0.5
)

old_df["item_code"] = old_df["item_code"].astype(str).str.strip().str.upper()
inv_df["item_code"] = inv_df["item_code"].astype(str).str.strip().str.upper()

old_clean = old_df.dropna(subset=["old_unit_price"]).drop_duplicates(subset=["item_code"])
inv_clean = inv_df.dropna(subset=["new_unit_price", "qty_billed"])

merged = pd.merge(inv_clean, old_clean, on="item_code", how="left")
unmatched = merged[merged["old_unit_price"].isna()].copy()
matched = merged.dropna(subset=["old_unit_price"]).copy()

if not matched.empty:
    matched["price_diff"] = (matched["new_unit_price"] - matched["old_unit_price"]).round(2)
    matched["hike_pct"] = (((matched["new_unit_price"] - matched["old_unit_price"]) / matched["old_unit_price"]) * 100).round(2)
    matched["extra_cost_loss"] = (matched["price_diff"] * matched["qty_billed"]).round(2)
    hikes = matched[matched["hike_pct"] > threshold].sort_values(by="extra_cost_loss", ascending=False)
else:
    hikes = pd.DataFrame(columns=["item_code", "item_name", "old_unit_price", "new_unit_price", "hike_pct", "extra_cost_loss"])

total_loss = hikes["extra_cost_loss"].sum() if not hikes.empty else 0.0

# --- 7. KPIs & Results ---
st.divider()
k1, k2, k3 = st.columns(3)
k1.metric(t("Rate-Hiked Items", "ரேட் ஏறிய ஐட்டங்கள்"), f"{len(hikes)}")
k2.metric(t("Total Extra Cost Leakage", "மொத்த கூடுதல் செலவு"), f"{curr_sym}{total_loss:,.2f}")
k3.metric(t("Unmatched / New Items", "புது / மேட்ச் ஆகாத ஐட்டங்கள்"), f"{len(unmatched)}")

st.subheader(t("🚨 Detected Rate-Hike Items", "🚨 ரேட் உயர்வு கண்டறியப்பட்ட ஐட்டங்கள்"))
if not hikes.empty:
    display_cols = ["item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "hike_pct", "extra_cost_loss"]
    st.dataframe(hikes[display_cols], use_container_width=True)

    csv_data = hikes[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        t("📥 Download Audit Report CSV", "📥 ஆடிட் ரிப்போர்ட் CSV டவுன்லோட்"),
        data=csv_data,
        file_name="rate_hike_audit_report.csv",
        mime="text/csv"
    )

    st.subheader(t("✉️ Supplier Clarification Email Draft", "✉️ சப்ளையருக்கு அனுப்ப வேண்டிய ஈமெயில் டிராஃப்ட்"))
    email_rows = "\n".join([
        f"* {row['item_name']} ({row['item_code']}): Billed {curr_sym}{row['new_unit_price']} vs Approved {curr_sym}{row['old_unit_price']} (+{row['hike_pct']}%)"
        for _, row in hikes.iterrows()
    ])
    email_text = f"""Subject: Rate Variance Clarification – Recent Invoice Audit

Hi Supplier Team,

During our routine invoice audit, we noticed unit price increases on the following items compared to our previous approved rates:

{email_rows}

Total variance identified on this bill is {curr_sym}{total_loss:,.2f}. Please share the approved revision note before we process payment for the variance portion.

Best regards,
Procurement Team"""
    st.text_area(t("Copy & Send:", "காப்பி செய்து அனுப்பவும்:"), email_text, height=220)
else:
    st.success(t(
        "No unauthorized rate hikes found above your threshold.",
        "நீங்கள் நிர்ணயித்த வரம்பிற்கு மேல் எந்த ரேட் உயர்வும் இல்லை."
    ))

if not unmatched.empty:
    st.warning(t(
        "⚠️ Unmatched / New Items (Not in Approved Rate List):",
        "⚠️ பழைய அப்ரூவ்ட் ரேட் பட்டியலில் இல்லாத புது ஐட்டங்கள்:"
    ))
    st.dataframe(unmatched[["item_code", "qty_billed", "new_unit_price"]], use_container_width=True)
