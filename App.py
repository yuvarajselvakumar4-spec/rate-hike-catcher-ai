from difflib import SequenceMatcher
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="RateGuard AI — Procurement & Rate-Hike Audit",
    page_icon="🛡️",
    layout="wide",
)

# --- 0. Login Gate (Safe Secrets + Case-Insensitive Demo Fallback) ---
expected_user = "demo"
expected_pass = "1234"

try:
    if hasattr(st, "secrets") and "auth" in st.secrets:
        auth_cfg = st.secrets["auth"]
        if "username" in auth_cfg and str(auth_cfg["username"]).strip():
            expected_user = str(auth_cfg["username"]).strip().lower()
        if "password" in auth_cfg and str(auth_cfg["password"]).strip():
            expected_pass = str(auth_cfg["password"]).strip()
except Exception:
    pass

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🛡️ RateGuard AI — Login / உள்நுழைவு")
    st.caption(
        "Secure access for SME invoice & rate-hike audit / பர்ச்சேஸ் பில் ஆடிட்"
        " பாதுகாப்பான அணுகல்"
    )

    with st.form("login_form"):
        u_in = st.text_input("Username / பயனர் பெயர்")
        p_in = st.text_input("Password / கடவுச்சொல்", type="password")
        submitted = st.form_submit_button("Login / உள்நுழை")

    if submitted:
        entered_user = u_in.strip().lower()
        entered_pass = p_in.strip()
        if (entered_user == expected_user) and (entered_pass == expected_pass):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error(
                "Invalid username or password / தவறான பயனர் பெயர் அல்லது கடவுச்சொல்."
            )
    st.stop()

if st.sidebar.button("Logout / வெளியேறு"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- 1. Top Controls: Language & Currency ---
top_c1, top_c2, top_c3 = st.columns([2, 1, 1])
with top_c2:
    lang = st.selectbox(
        "🌐 Language / மொழி",
        ["Bilingual (English + தமிழ்)", "English", "தமிழ் (Tamil)"],
    )
with top_c3:
    currency = st.selectbox("💱 Currency", ["₹ (INR)", "$ (USD)", "€ (EUR)"])

curr_sym = currency.split(" ")[0]


def t(en, ta):
    if lang == "English":
        return en
    if lang == "தமிழ் (Tamil)":
        return ta
    return f"{en} / {ta}"


# --- 2. Header & Privacy Note ---
st.title("🛡️ RateGuard AI — AI Procurement & Rate-Hike Audit")
st.write(
    t(
        "AI-driven invoice audit to detect unauthorized supplier rate hikes, cost leakage, savings, fuzzy item mismatches & negotiation actions.",
        "சப்ளையர் பில்களில் ரேட் உயர்வு, கூடுதல் செலவு, சேமிப்பு, பெயர் வித்தியாசங்கள் மற்றும் பேச்சுவார்த்தை வழிமுறைகளை நொடிகளில் கண்டறியும் AI ஆடிட் டூல்.",
    )
)

st.info(
    t(
        "🔒 Security & Privacy: Session-protected access; uploaded CSVs are analyzed in memory during your session without permanent database storage.",
        "🔒 பாதுகாப்பு: லாகின் மூலம் பாதுகாக்கப்பட்ட அணுகல்; அப்லோட் செய்யப்படும் CSV கோப்புகள் டேட்டாபேஸில் நிரந்தரமாகச் சேமிக்கப்படாது.",
    )
)

# --- 3. Sample CSV Templates Download ---
sample_old = pd.DataFrame({
    "item_code": ["M101", "M102", "M103", "M104", "M105"],
    "item_name": [
        "SS Bolt 10mm",
        "Hydraulic Valve",
        "Bearing 6205",
        "Copper Wire 2mm",
        "Gasket Set",
    ],
    "old_unit_price": [12.00, 1450.00, 210.00, 580.00, 95.00],
})

sample_inv = pd.DataFrame({
    "item_code": ["M101", "M102", "M103", "M104", "M105", "M999"],
    "item_name": [
        "SS Bolt 10mm",
        "Hydraulic Valve",
        "Bearing 6205",
        "Copper Wire 2mm",
        "Gasket Set",
        "SS Bolt 10 mm",
    ],
    "qty_billed": [500, 10, 40, 25, 100, 5],
    "new_unit_price": [13.50, 1450.00, 235.00, 575.00, 110.00, 15.00],
})

with st.expander(
    t("📄 Sample CSV Templates", "📄 சாம்பிள் CSV டெம்ப்ளேட்கள்")
):
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            t("⬇️ Sample Old Rates CSV", "⬇️ சாம்பிள் பழைய ரேட் CSV"),
            data=sample_old.to_csv(index=False).encode("utf-8"),
            file_name="sample_old_approved_rates.csv",
            mime="text/csv",
        )
    with d2:
        st.download_button(
            t("⬇️ Sample New Invoice CSV", "⬇️ சாம்பிள் புது பில் CSV"),
            data=sample_inv.to_csv(index=False).encode("utf-8"),
            file_name="sample_new_invoice.csv",
            mime="text/csv",
        )


# --- 4. Helper Functions (Column Auto-Match & AI Fuzzy Name Matcher) ---
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


def best_name_match(target_name, ref_df):
    if not target_name or ref_df.empty:
        return None, 0.0
    t_clean = " ".join(str(target_name).lower().replace("-", " ").split())
    best_row = None
    best_score = 0.0
    for _, r in ref_df.iterrows():
        r_clean = " ".join(
            str(r.get("item_name", "")).lower().replace("-", " ").split()
        )
        if not r_clean:
            continue
        score = SequenceMatcher(None, t_clean, r_clean).ratio()
        if score > best_score:
            best_score = score
            best_row = r
    return best_row, round(best_score * 100, 1)


# --- 5. Data Source ---
use_sample = st.checkbox(
    t("Use built-in demo data", "டெமோ டேட்டாவைப் பயன்படுத்தவும்"), value=True
)

if use_sample:
    old_df = sample_old.copy()
    inv_df = sample_inv.copy()
else:
    u1, u2 = st.columns(2)
    with u1:
        old_file = st.file_uploader(
            t("1. Old Approved Rates CSV", "1. பழைய Approved Rates CSV"),
            type=["csv"],
        )
    with u2:
        inv_file = st.file_uploader(
            t("2. New Supplier Invoice CSV", "2. புது Supplier Invoice CSV"),
            type=["csv"],
        )

    if not (old_file and inv_file):
        st.warning(
            t(
                "Upload both CSV files or check 'Use built-in demo data'.",
                "இரண்டு CSV கோப்புகளையும் அப்லோட் செய்யவும் அல்லது டெமோ டேட்டாவைத் தேர்வு செய்யவும்.",
            )
        )
        st.stop()

    try:
        old_raw = pd.read_csv(old_file)
        inv_raw = pd.read_csv(inv_file)
    except Exception as e:
        st.error(
            t(f"Error reading CSV: {e}", f"CSV கோப்பைப் படிப்பதில் சிக்கல்: {e}")
        )
        st.stop()

    with st.expander(
        t("🧩 Column Mapping", "🧩 காலம் மேப்பிங்"), expanded=False
    ):
        m1, m2, m3 = st.columns(3)
        with m1:
            old_code_col = st.selectbox(
                t("Old: Item Code", "பழையது: Item Code"),
                old_raw.columns,
                index=list(old_raw.columns).index(
                    find_col(
                        old_raw.columns,
                        ["item_code", "code", "sku", "item_id", "id"],
                    )
                ),
            )
        with m2:
            old_name_col = st.selectbox(
                t("Old: Item Name", "பழையது: Item Name"),
                old_raw.columns,
                index=list(old_raw.columns).index(
                    find_col(
                        old_raw.columns,
                        ["item_name", "name", "description", "item", "material"],
                    )
                ),
            )
        with m3:
            old_price_col = st.selectbox(
                t("Old: Approved Price", "பழையது: Approved Price"),
                old_raw.columns,
                index=list(old_raw.columns).index(
