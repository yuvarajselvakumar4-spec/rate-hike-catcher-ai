import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(
    page_title="RateGuard AI — Procurement & Rate-Hike Audit",
    page_icon="🛡️",
    layout="wide"
)

# --- 0. Login Gate (Secrets-backed with Case-Insensitive Demo Fallback) ---
auth_cfg = st.secrets.get("auth", {}) if hasattr(st, "secrets") else {}
expected_user = str(auth_cfg.get("username", "demo")).strip().lower()
expected_pass = str(auth_cfg.get("password", "1234")).strip()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🛡️ RateGuard AI — Login / உள்நுழைவு")
    st.caption("Secure access for SME invoice & rate-hike audit / பர்ச்சேஸ் பில் ஆடிட் பாதுகாப்பான அணுகல்")

    with st.form("login_form"):
        u_in = st.text_input("Username / பயனர் பெயர்")
        p_in = st.text_input("Password / கடவுச்சொல்", type="password")
        submitted = st.form_submit_button("Login / உள்நுழை")

    if submitted:
        if u_in.strip().lower() == expected_user and p_in.strip() == expected_pass:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid username or password / தவறான பயனர் பெயர் அல்லது கடவுச்சொல்.")
    st.stop()

if st.sidebar.button("Logout / வெளியேறு"):
    st.session_state.authenticated = False
    st.rerun()

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
st.title("🛡️ RateGuard AI — Rate-Hike & Bill Audit")
st.write(t(
    "AI-assisted procurement audit to catch unauthorized supplier rate hikes, leakage, price drops & billing anomalies fast.",
    "சப்ளையர் பில்களில் அங்கீகரிக்கப்படாத ரேட் உயர்வு, கூடுதல் செலவு, ரேட் குறைவு மற்றும் வித்தியாசங்களை நொடிகளில் கண்டறியும் AI ஆடிட் டூல்."
))

st.info(t(
    "🔒 Security & Privacy: Session-protected access; uploaded CSVs are analyzed in memory during your session without permanent database storage.",
    "🔒 பாதுகாப்பு: லாகின் மூலம் பாதுகாக்கப்பட்ட அணுகல்; அப்லோட் செய்யப்படும் CSV கோப்புகள் டேட்டாபேஸில் நிரந்தரமாகச் சேமிக்கப்படாது."
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

with st.expander(t("📄 Sample CSV Templates", "📄 சாம்பிள் CSV டெம்ப்ளேட்கள்")):
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

# --- 5. Data Source ---
use_sample = st.checkbox(
    t("Use built-in demo data", "டெமோ டேட்டாவைப் பயன்படுத்தவும்"),
    value=True
)

if use_sample:
    old_df = sample_old.copy()
    inv_df = sample_inv.copy()
else:
    u1, u2 = st.columns(2)
    with u1:
        old_file = st.file_uploader(t("1. Old Approved Rates CSV", "1. பழைய Approved Rates CSV"), type=["csv"])
    with u2:
        inv_file = st.file_uploader(t("2. New Supplier Invoice CSV", "2. புது Supplier Invoice CSV"), type=["csv"])

    if not (old_file and inv_file):
        st.warning(t(
            "Upload both CSV files or check 'Use built-in demo data'.",
            "இரண்டு CSV கோப்புகளையும் அப்லோட் செய்யவும் அல்லது டெமோ டேட்டாவைத் தேர்வு செய்யவும்."
        ))
        st.stop()

    try:
        old_raw = pd.read_csv(old_file)
        inv_raw = pd.read_csv(inv_file)
    except Exception as e:
        st.error(t(f"Error reading CSV: {e}", f"CSV கோப்பைப் படிப்பதில் சிக்கல்: {e}"))
        st.stop()

    with st.expander(t("🧩 Column Mapping", "🧩 காலம் மேப்பிங்"), expanded=False):
        m1, m2, m3 = st.columns(3)
        with m1:
            old_code_col = st.selectbox(t("Old: Item Code", "பழையது: Item Code"), old_raw.columns, index=list(old_raw.columns).index(find_col(old_raw.columns, ["item_code", "code", "sku", "item_id", "id"])))
        with m2:
            old_name_col = st.selectbox(t("Old: Item Name", "பழையது: Item Name"), old_raw.columns, index=list(old_raw.columns).index(find_col(old_raw.columns, ["item_name", "name", "description", "item", "material"])))
        with m3:
            old_price_col = st.selectbox(t("Old: Approved Price", "பழையது: Approved Price"), old_raw.columns, index=list(old_raw.columns).index(find_col(old_raw.columns, ["old_unit_price", "old_price", "approved_price", "rate", "price"])))

        n1, n2, n3 = st.columns(3)
        with n1:
            inv_code_col = st.selectbox(t("Invoice: Item Code", "பில்: Item Code"), inv_raw.columns, index=list(inv_raw.columns).index(find_col(inv_raw.columns, ["item_code", "code", "sku", "item_id", "id"])))
        with n2:
            inv_qty_col = st.selectbox(t("Invoice: Quantity", "பில்: Quantity"), inv_raw.columns, index=list(inv_raw.columns).index(find_col(inv_raw.columns, ["qty_billed", "qty", "quantity", "billed_qty"])))
        with n3:
            inv_price_col = st.selectbox(t("Invoice: New Price", "பில்: New Price"), inv_raw.columns, index=list(inv_raw.columns).index(find_col(inv_raw.columns, ["new_unit_price", "new_price", "billed_price", "rate", "price"])))

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
    t("Alert Threshold (% hike above approved rate)", "அலர்ட் வரம்பு (% ரேட் உயர்வு)"),
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
    matched["net_impact"] = (matched["price_diff"] * matched["qty_billed"]).round(2)

    hikes = matched[matched["hike_pct"] > threshold].copy()
    hikes["extra_cost_loss"] = hikes["net_impact"]
    hikes = hikes.sort_values(by="extra_cost_loss", ascending=False)

    drops = matched[matched["price_diff"] < 0].copy()
    drops["savings_amt"] = (drops["price_diff"].abs() * drops["qty_billed"]).round(2)
    drops = drops.sort_values(by="savings_amt", ascending=False)
else:
    hikes = pd.DataFrame(columns=["item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "hike_pct", "extra_cost_loss"])
    drops = pd.DataFrame(columns=["item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "savings_amt"])

total_loss = hikes["extra_cost_loss"].sum() if not hikes.empty else 0.0
total_savings = drops["savings_amt"].sum() if not drops.empty else 0.0
max_hike_pct = hikes["hike_pct"].max() if not hikes.empty else 0.0

if total_loss >= 2000 or max_hike_pct >= 15.0 or len(unmatched) >= 2:
    risk_label = t("HIGH RISK", "அதிக அபாயம் (HIGH)")
elif total_loss > 0 or len(unmatched) > 0:
    risk_label = t("MEDIUM RISK", "நடுத்தர அபாயம் (MEDIUM)")
else:
    risk_label = t("LOW RISK", "குறைந்த அபாயம் (LOW)")

# --- 7. KPIs & Smart AI Audit Summary ---
st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric(t("Rate-Hiked Items", "ரேட் ஏறிய ஐட்டங்கள்"), f"{len(hikes)}")
k2.metric(t("Total Extra Cost Leakage", "மொத்த கூடுதல் செலவு"), f"{curr_sym}{total_loss:,.2f}")
k3.metric(t("Price Drop Savings", "ரேட் குறைவால் சேமிப்பு"), f"{curr_sym}{total_savings:,.2f}")
k4.metric(t("Audit Risk Level", "ஆடிட் ரிஸ்க் நிலை"), risk_label)

if not hikes.empty:
    top_loss_row = hikes.iloc[0]
    spike_row = hikes.sort_values(by="hike_pct", ascending=False).iloc[0]
    st.warning(t(
        f"🤖 AI Anomaly Summary: Highest financial leakage is '{top_loss_row['item_name']}' ({curr_sym}{top_loss_row['extra_cost_loss']:,.2f}), while steepest percentage spike is '{spike_row['item_name']}' (+{spike_row['hike_pct']}%). Found {len(unmatched)} unmatched item(s).",
        f"🤖 AI அனாமலி சுருக்கம்: அதிக செலவு உயர்வு '{top_loss_row['item_name']}' ({curr_sym}{top_loss_row['extra_cost_loss']:,.2f}), அதிக சதவீத உயர்வு '{spike_row['item_name']}' (+{spike_row['hike_pct']}%). மேலும் {len(unmatched)} புதிய/மேட்ச் ஆகாத ஐட்டம் உள்ளது."
    ))
elif not unmatched.empty:
    st.info(t(
        f"🤖 AI Anomaly Summary: No rate hikes above threshold, but {len(unmatched)} unmatched item(s) need rate approval check.",
        f"🤖 AI அனாமலி சுருக்கம்: வரம்புக்கு மேல் ரேட் உயர்வு இல்லை; ஆனால் {len(unmatched)} புதிய ஐட்டங்களுக்கு ரேட் உறுதி செய்ய வேண்டும்."
    ))
else:
    st.success(t(
        "🤖 AI Anomaly Summary: Invoice aligns cleanly with approved rates above your selected threshold.",
        "🤖 AI அனாமலி சுருக்கம்: நிர்ணயிக்கப்பட்ட வரம்பிற்குள் பில் சரியாக உள்ளது."
    ))

# --- 8. Detected Hikes, Report & Supplier Email ---
st.subheader(t("🚨 Detected Rate-Hike Items", "🚨 ரேட் உயர்வு கண்டறியப்பட்ட ஐட்டங்கள்"))
if not hikes.empty:
    display_cols = ["item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "hike_pct", "extra_cost_loss"]
    st.dataframe(hikes[display_cols], use_container_width=True)

    csv_data = hikes[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        t("📥 Download Audit Report CSV", "📥 ஆடிட் ரிப்போர்ட் CSV டவுன்லோட்"),
        data=csv_data,
        file_name="rateguard_audit_report.csv",
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
    st.text_area(t("Copy & Send:", "காப்பி செய்து அனுப்பவும்:"), email_text, height=200)

    # --- 8B. Direct Email Alert Dispatch ---
    with st.expander(t("📣 Send Audit Alert via Email", "📣 ஈமெயில் மூலம் ஆடிட் அலர்ட் அனுப்பவும்")):
        recipient_email = st.text_input(t("Recipient Email (Owner / Purchase Head)", "பெறுநர் ஈமெயில் (உரிமையாளர் / பர்ச்சேஸ் ஹெட்)"))
        alert_body = (
            f"RateGuard AI Alert Summary\n"
            f"Risk Level: {risk_label}\n"
            f"Rate-Hiked Items: {len(hikes)}\n"
            f"Total Extra Cost Leakage: {curr_sym}{total_loss:,.2f}\n"
            f"Unmatched Items: {len(unmatched)}"
        )
        if st.button(t("Send Email Alert", "ஈமெயில் அலர்ட் அனுப்பு")):
            email_cfg = st.secrets.get("email", {}) if hasattr(st, "secrets") else {}
            smtp_server = email_cfg.get("smtp_server")
            smtp_port = int(email_cfg.get("smtp_port", 587))
            sender_email = email_cfg.get("sender_email")
            app_password = email_cfg.get("app_password")

            if not recipient_email:
                st.error(t("Please enter a recipient email.", "பெறுநர் ஈமெயில் முகவரியை உள்ளிடவும்."))
            elif not (smtp_server and sender_email and app_password):
                st.info(t(
                    "SMTP secrets not configured yet. Here is the alert payload ready to send once configured in Streamlit Secrets:",
                    "Streamlit Secrets-ல் SMTP விவரங்கள் இன்னும் சேர்க்கப்படவில்லை. சேர்த்ததும் அனுப்ப வேண்டிய அலர்ட் விவரம் கீழே உள்ளது:"
                ))
                st.code(alert_body)
            else:
                try:
                    msg = MIMEMultipart()
                    msg["From"] = sender_email
                    msg["To"] = recipient_email
                    msg["Subject"] = f"RateGuard AI Alert: {curr_sym}{total_loss:,.2f} Rate Variance Detected"
                    msg.attach(MIMEText(alert_body, "plain"))

                    with smtplib.SMTP(smtp_server, smtp_port) as server:
                        server.starttls()
                        server.login(sender_email, app_password)
                        server.send_message(msg)
                    st.success(t("Email alert sent successfully!", "ஈமெயில் அலர்ட் வெற்றிகரமாக அனுப்பப்பட்டது!"))
                except Exception as e:
                    st.error(t(f"Failed to send email: {e}", f"ஈமெயில் அனுப்புவதில் பிழை: {e}"))
else:
    st.success(t(
        "No unauthorized rate hikes found above your threshold.",
        "நீங்கள் நிர்ணயித்த வரம்பிற்கு மேல் எந்த ரேட் உயர்வும் இல்லை."
    ))

# --- 9. Price Drops & Unmatched Items ---
if not drops.empty:
    st.subheader(t("💚 Price Drops / Potential Savings", "💚 ரேட் குறைவு / சாத்தியமான சேமிப்பு"))
    st.dataframe(drops[["item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "savings_amt"]], use_container_width=True)

if not unmatched.empty:
    st.warning(t(
        "⚠️ Unmatched / New Items (Not in Approved Rate List):",
        "⚠️ பழைய அப்ரூவ்ட் ரேட் பட்டியலில் இல்லாத புது ஐட்டங்கள்:"
    ))
    st.dataframe(unmatched[["item_code", "qty_billed", "new_unit_price"]], use_container_width=True)

# --- 10. Subscription & Upgrade Plan (Monetization Starter) ---
st.divider()
st.subheader(t("💳 Plans & Subscription (Starter vs Pro)", "💳 திட்டங்கள் & சப்ஸ்கிரிப்ஷன் (Starter vs Pro)"))
p1, p2 = st.columns(2)
with p1:
    st.markdown(f"""
    **{t("Free Starter", "இலவச திட்டம் (Free)")}**
    * {t("Manual CSV rate-hike & savings check", "CSV ரேட் உயர்வு & சேமிப்பு பரிசோதனை")}
    * {t("Bilingual UI & CSV report export", "இருமொழி வசதி & CSV ரிப்போர்ட்")}
    """)
with p2:
    st.markdown(f"""
    **{t("Pro Business Plan", "ப்ரோ பிசினஸ் திட்டம் (Pro)")}**
    * {t("Automated Email / SMS / WhatsApp alerts", "தானியங்கி ஈமெயில் / SMS / WhatsApp அலர்ட்கள்")}
    * {t("Priority support & multi-bill workflows", "முன்னுரிமை உதவி & பல பில் ஆடிட் வசதி")}
    """)

with st.expander(t("🚀 Upgrade / UPI & Razorpay Subscription Inquiry", "🚀 அப்கிரேட் / UPI & Razorpay சப்ஸ்கிரிப்ஷன் விவரம்")):
    st.write(t(
        "Connect Razorpay (UPI / Cards / Netbanking) or bank transfer details in Streamlit Secrets to enable live checkout links.",
        "நேரடி கட்டண லிங்க்குகளை இயக்க Streamlit Secrets-ல் Razorpay / UPI / வங்கி விவரங்களை இணைக்கலாம்."
    ))
    biz_name = st.text_input(t("Company / Business Name", "நிறுவனத்தின் பெயர்"))
    plan_choice = st.selectbox(t("Select Plan", "திட்டத்தைத் தேர்ந்தெடுக்கவும்"), ["Pro Monthly", "Pro Yearly"])
    if st.button(t("Request Pro Activation", "Pro திட்டத்தைக் கோரவும்")):
        if biz_name.strip():
            st.success(t(
                f"Pro request noted for '{biz_name}' ({plan_choice}). Configure Razorpay/UPI checkout in Secrets to accept live payments.",
                f"'{biz_name}' நிறுவனத்திற்கான ({plan_choice}) கோரிக்கை பதிவு செய்யப்பட்டது. நேரடி கட்டணத்திற்கு Secrets-ல் Razorpay/UPI விவரங்களை இணைக்கவும்."
            ))
        else:
            st.warning(t("Please enter your company name.", "நிறுவனத்தின் பெயரை உள்ளிடவும்."))
