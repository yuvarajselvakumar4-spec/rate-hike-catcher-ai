from datetime import datetime
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

# --- 0. Login Gate (Safe Secrets + Demo Fallback) ---
expected_user = "demo"
expected_pass = "1234"

try:
    if "auth" in st.secrets:
        auth_cfg = st.secrets["auth"]
        u_sec = str(auth_cfg.get("username", "")).strip().lower()
        p_sec = str(auth_cfg.get("password", "")).strip()
        if u_sec and p_sec:
            expected_user = u_sec
            expected_pass = p_sec
except Exception:
    pass

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "is_pro" not in st.session_state:
    st.session_state["is_pro"] = False

if "audit_history" not in st.session_state:
    st.session_state["audit_history"] = []

if not st.session_state["authenticated"]:
    st.title("🛡️ RateGuard AI — Login / உள்நுழைவு")
    st.caption(
        "Secure access for SME invoice & rate-hike audit / பர்ச்சேஸ் பில் ஆடிட் பாதுகாப்பான அணுகல்"
    )
    st.caption(f"Active login user: {expected_user} (default demo: demo / 1234)")

    with st.form("login_form"):
        u_in = st.text_input("Username / பயனர் பெயர்", value="")
        p_in = st.text_input("Password / கடவுச்சொல்", type="password", value="")
        submitted = st.form_submit_button("Login / உள்நுழை")

    if submitted:
        entered_user = u_in.strip().lower()
        entered_pass = p_in.strip()
        if (entered_user == expected_user) and (entered_pass == expected_pass):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password / தவறான பயனர் பெயர் அல்லது கடவுச்சொல்.")
    st.stop()

if st.sidebar.button("Logout / வெளியேறு"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- 1. Top Controls: Language & Currency ---
_, top_c2, top_c3 = st.columns([2, 1, 1])
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
st.title("🛡️ RateGuard AI — Autonomous Procurement & Rate-Hike Audit")
st.write(
    t(
        "AI-driven invoice audit to detect unauthorized supplier rate hikes, cost leakage, savings, fuzzy item mismatches, automated item decisions & negotiation drafts.",
        "சப்ளையர் பில்களில் ரேட் உயர்வு, கூடுதல் செலவு, சேமிப்பு, பெயர் வித்தியாசங்கள், ஆட்டோமேட்டிக் ஐட்டம் முடிவுகள் மற்றும் பேச்சுவார்த்தை டிராஃப்ட்களை உருவாக்கும் AI ஆடிட் டூல்.",
    )
)

st.info(
    t(
        "🔒 Security & Privacy: Session-protected access; uploaded CSVs are analyzed in memory during your session without permanent database storage.",
        "🔒 பாதுகாப்பு: லாகின் மூலம் பாதுகாக்கப்பட்ட அணுகல்; அப்லோட் செய்யப்படும் CSV கோப்புகள் டேட்டாபேஸில் நிரந்தரமாகச் சேமிக்கப்படாது.",
    )
)

# --- 3. Built-in Scenarios & CSV Templates Download ---
sample_old = pd.DataFrame({
    "item_code": ["M101", "M102", "M103", "M104", "M105"],
    "item_name": ["SS Bolt 10mm", "Hydraulic Valve", "Bearing 6205", "Copper Wire 2mm", "Gasket Set"],
    "old_unit_price": [12.00, 1450.00, 210.00, 580.00, 95.00],
})

sample_inv = pd.DataFrame({
    "supplier_name": ["Apex Fasteners", "Apex Fasteners", "Kaveri Bearings", "Sri Murugan Wires", "Apex Fasteners", "Apex Fasteners"],
    "item_code": ["M101", "M102", "M103", "M104", "M105", "M999"],
    "item_name": ["SS Bolt 10mm", "Hydraulic Valve", "Bearing 6205", "Copper Wire 2mm", "Gasket Set", "SS Bolt 10 mm"],
    "qty_billed": [500, 10, 40, 25, 100, 5],
    "new_unit_price": [13.50, 1450.00, 235.00, 575.00, 110.00, 15.00],
})

real_case_old = pd.DataFrame({
    "item_code": ["PN-11", "PN-12", "PN-14", "PN-18", "PN-19"],
    "item_name": ["MS Hex Bolt M12", "Bearing 6205-ZZ", "Cutting Oil 20L", "Emery Sheet 120 Grit", "Rubber Bush Set"],
    "old_unit_price": [8.50, 210.00, 2400.00, 28.00, 180.00],
})

real_case_inv = pd.DataFrame({
    "supplier_name": ["Kongu Hardware", "Kongu Hardware", "Kongu Hardware", "Kongu Hardware", "Kongu Hardware"],
    "item_code": ["PN-11", "PN-14", "PN-18", "PN-19", "PN-99"],
    "item_name": ["MS Hex Bolt M12", "Cutting Oil 20L", "Emery Sheet 120 Grit", "Rubber Bush Set", "Bearing 6205 ZZ"],
    "qty_billed": [600, 8, 50, 40, 15],
    "new_unit_price": [10.20, 2640.00, 28.00, 165.00, 245.00],
})

with st.expander(t("📄 Download Test CSV Files (Phone Ready)", "📄 டெஸ்ட் CSV கோப்புகளை டவுன்லோட் செய்யவும்")):
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            t("⬇️ Real Company: Old Rates CSV", "⬇️ நிஜ கம்பெனி: பழைய ரேட் CSV"),
            data=real_case_old.to_csv(index=False).encode("utf-8"),
            file_name="old_rates_test.csv",
            mime="text/csv",
        )
    with d2:
        st.download_button(
            t("⬇️ Real Company: New Invoice CSV", "⬇️ நிஜ கம்பெனி: புது பில் CSV"),
            data=real_case_inv.to_csv(index=False).encode("utf-8"),
            file_name="new_invoice_test.csv",
            mime="text/csv",
        )


# --- 4. Helper Functions (Column Auto-Match, Fuzzy Match & Risk Score) ---
def find_col(columns, candidates, optional=False):
    lower_map = {c.strip().lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for c in columns:
        cl = c.strip().lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    if optional:
        return None
    return columns[0] if len(columns) > 0 else None


def best_name_match(target_name, ref_df):
    if (not target_name) or ref_df.empty:
        return None, 0.0
    t_clean = " ".join(str(target_name).lower().replace("-", " ").split())
    best_row = None
    best_score = 0.0
    for _, r in ref_df.iterrows():
        r_clean = " ".join(str(r.get("item_name", "")).lower().replace("-", " ").split())
        if not r_clean:
            continue
        score = SequenceMatcher(None, t_clean, r_clean).ratio()
        if score > best_score:
            best_score = score
            best_row = r
    return best_row, round(best_score * 100, 1)


def compute_item_ai_score(hike_pct, extra_loss):
    pct_part = min(max(float(hike_pct), 0.0) * 2.5, 50.0)
    loss_part = min(max(float(extra_loss), 0.0) / 50.0, 50.0)
    score = round(min(pct_part + loss_part, 100.0), 1)
    if score >= 65.0:
        action = "HOLD PAYMENT"
    elif score >= 25.0:
        action = "REVIEW & VERIFY"
    else:
        action = "AUTO-APPROVE"
    return score, action


def dispatch_email_alert(smtp_server, smtp_port, sender_email, app_password, recipient, subject, body_text):
    clean_pwd = str(app_password).replace(" ", "").strip()
    clean_sender = str(sender_email).strip()
    clean_recipient = str(recipient).strip()
    clean_host = str(smtp_server).strip()
    port_num = int(smtp_port)

    msg = MIMEMultipart()
    msg["From"] = clean_sender
    msg["To"] = clean_recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    if port_num == 465:
        with smtplib.SMTP_SSL(clean_host, port_num, timeout=15) as server:
            server.login(clean_sender, clean_pwd)
            server.send_message(msg)
    else:
        try:
            with smtplib.SMTP(clean_host, port_num, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(clean_sender, clean_pwd)
                server.send_message(msg)
        except Exception:
            with smtplib.SMTP_SSL(clean_host, 465, timeout=15) as server:
                server.login(clean_sender, clean_pwd)
                server.send_message(msg)


# --- 5. Data Source Selector (1-Click Scenarios or Upload) ---
data_mode = st.radio(
    t("Select Audit Data Source", "ஆடிட் டேட்டா வகையைத் தேர்ந்தெடுக்கவும்"),
    [
        t("Real Company Case: Sri Kovai Precision Components", "நிஜ கம்பெனி கேஸ்: Sri Kovai Precision Components"),
        t("Quick Demo Data", "அடிப்படை டெமோ டேட்டா"),
        t("Upload My Own CSV Files", "எனது சொந்த CSV கோப்புகளை அப்லோட் செய்"),
    ],
    horizontal=True,
)

source_label = "Sri Kovai Precision"
if "Sri Kovai" in data_mode:
    old_df = real_case_old.copy()
    inv_df = real_case_inv.copy()
    source_label = "Sri Kovai Precision"
elif "Quick Demo" in data_mode:
    old_df = sample_old.copy()
    inv_df = sample_inv.copy()
    source_label = "Quick Demo"
else:
    source_label = "Uploaded CSV"
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
                "Upload both CSV files or pick one of the built-in test cases above.",
                "இரண்டு CSV கோப்புகளையும் அப்லோட் செய்யவும் அல்லது மேலே உள்ள டெஸ்ட் கேஸ்களில் ஒன்றைத் தேர்வு செய்யவும்.",
            )
        )
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
            old_code_col = st.selectbox(
                t("Old: Item Code", "பழையது: Item Code"),
                old_raw.columns,
                index=list(old_raw.columns).index(
                    find_col(old_raw.columns, ["item_code", "code", "sku", "item_id", "id"])
                ),
            )
        with m2:
            old_name_col = st.selectbox(
                t("Old: Item Name", "பழையது: Item Name"),
                old_raw.columns,
                index=list(old_raw.columns).index(
                    find_col(old_raw.columns, ["item_name", "name", "description", "item", "material"])
                ),
            )
        with m3:
            old_price_col = st.selectbox(
                t("Old: Approved Price", "பழையது: Approved Price"),
                old_raw.columns,
                index=list(old_raw.columns).index(
                    find_col(old_raw.columns, ["old_unit_price", "old_price", "approved_price", "rate", "price"])
                ),
            )

        n1, n2, n3, n4, n5 = st.columns(5)
        with n1:
            inv_code_col = st.selectbox(
                t("Invoice: Item Code", "பில்: Item Code"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(
                    find_col(inv_raw.columns, ["item_code", "code", "sku", "item_id", "id"])
                ),
            )
        with n2:
            inv_name_col = st.selectbox(
                t("Invoice: Item Name", "பில்: Item Name"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(
                    find_col(inv_raw.columns, ["item_name", "name", "description", "item", "material"])
                ),
            )
        with n3:
            inv_qty_col = st.selectbox(
                t("Invoice: Quantity", "பில்: Quantity"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(
                    find_col(inv_raw.columns, ["qty_billed", "qty", "quantity", "billed_qty"])
                ),
            )
        with n4:
            inv_price_col = st.selectbox(
                t("Invoice: New Price", "பில்: New Price"),
                inv_raw.columns,
                index=list(inv_raw.columns).index(
                    find_col(inv_raw.columns, ["new_unit_price", "new_price", "billed_price", "rate", "price"])
                ),
            )
        with n5:
            sup_opts = ["None"] + list(inv_raw.columns)
            auto_sup = find_col(inv_raw.columns, ["supplier_name", "supplier", "vendor", "vendor_name"], optional=True)
            sup_idx = sup_opts.index(auto_sup) if auto_sup in sup_opts else 0
            inv_sup_col = st.selectbox(
                t("Invoice: Supplier (Optional)", "பில்: சப்ளையர் (விருப்பம்)"),
                sup_opts,
                index=sup_idx,
            )

    old_df = pd.DataFrame({
        "item_code": old_raw[old_code_col],
        "item_name": old_raw[old_name_col],
        "old_unit_price": pd.to_numeric(old_raw[old_price_col], errors="coerce"),
    })
    inv_df = pd.DataFrame({
        "item_code": inv_raw[inv_code_col],
        "item_name": inv_raw[inv_name_col],
        "qty_billed": pd.to_numeric(inv_raw[inv_qty_col], errors="coerce"),
        "new_unit_price": pd.to_numeric(inv_raw[inv_price_col], errors="coerce"),
        "supplier_name": inv_raw[inv_sup_col] if inv_sup_col != "None" else "Default Supplier",
    })

if "supplier_name" not in inv_df.columns:
    inv_df["supplier_name"] = "Default Supplier"

# --- 6. Thresholds & AI Audit Calculation ---
th_c1, th_c2 = st.columns(2)
with th_c1:
    threshold = st.slider(
        t("Alert Threshold (% hike above approved rate)", "அலர்ட் வரம்பு (% ரேட் உயர்வு)"),
        0.0,
        30.0,
        0.0,
        0.5,
    )
with th_c2:
    min_loss_filter = st.number_input(
        t(f"Ignore Minor Extra Cost Below ({curr_sym})", f"சிறிய கூடுதல் செலவைத் தவிர்க்க ({curr_sym} கீழ்)"),
        min_value=0.0,
        max_value=10000.0,
        value=0.0,
        step=10.0,
    )

old_df["item_code"] = old_df["item_code"].astype(str).str.strip().str.upper()
inv_df["item_code"] = inv_df["item_code"].astype(str).str.strip().str.upper()
inv_df["supplier_name"] = inv_df["supplier_name"].fillna("Default Supplier").astype(str).str.strip()

old_clean = old_df.dropna(subset=["old_unit_price"]).drop_duplicates(subset=["item_code"])
inv_clean = inv_df.dropna(subset=["new_unit_price", "qty_billed"])

merged = pd.merge(
    inv_clean,
    old_clean,
    on="item_code",
    how="left",
    suffixes=("_inv", "_old"),
)
merged["item_name"] = merged["item_name_old"].fillna(merged["item_name_inv"])

unmatched = merged[merged["old_unit_price"].isna()].copy()
matched = merged.dropna(subset=["old_unit_price"]).copy()

fuzzy_suggestions = []
if not unmatched.empty:
    for _, urow in unmatched.iterrows():
        best_r, sim_pct = best_name_match(urow.get("item_name_inv", ""), old_clean)
        if (best_r is not None) and (sim_pct >= 65.0):
            est_diff = round(float(urow["new_unit_price"]) - float(best_r["old_unit_price"]), 2)
            est_loss = round(est_diff * float(urow["qty_billed"]), 2)
            fuzzy_suggestions.append({
                "supplier_name": urow.get("supplier_name", "Default Supplier"),
                "inv_code": urow["item_code"],
                "inv_name": urow["item_name_inv"],
                "matched_code": best_r["item_code"],
                "matched_name": best_r["item_name"],
                "similarity_%": sim_pct,
                "approved_rate": best_r["old_unit_price"],
                "billed_rate": urow["new_unit_price"],
                "est_variance": est_loss,
            })

if not matched.empty:
    matched["price_diff"] = (matched["new_unit_price"] - matched["old_unit_price"]).round(2)
    matched["hike_pct"] = (((matched["new_unit_price"] - matched["old_unit_price"]) / matched["old_unit_price"]) * 100).round(2)
    matched["net_impact"] = (matched["price_diff"] * matched["qty_billed"]).round(2)

    ai_scores = []
    ai_actions = []
    for _, mrow in matched.iterrows():
        sc, act = compute_item_ai_score(mrow["hike_pct"], max(mrow["net_impact"], 0.0))
        ai_scores.append(sc)
        ai_actions.append(act)
    matched["ai_risk_score"] = ai_scores
    matched["ai_action"] = ai_actions

    hikes = matched[(matched["hike_pct"] > threshold) & (matched["net_impact"] >= min_loss_filter)].copy()
    hikes["extra_cost_loss"] = hikes["net_impact"]
    hikes = hikes.sort_values(by=["ai_risk_score", "extra_cost_loss"], ascending=[False, False])

    drops = matched[matched["price_diff"] < 0].copy()
    drops["savings_amt"] = (drops["price_diff"].abs() * drops["qty_billed"]).round(2)
    drops = drops.sort_values(by="savings_amt", ascending=False)
else:
    hikes = pd.DataFrame(
        columns=["supplier_name", "item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "hike_pct", "extra_cost_loss", "ai_risk_score", "ai_action"]
    )
    drops = pd.DataFrame(
        columns=["supplier_name", "item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "savings_amt"]
    )

total_loss = float(hikes["extra_cost_loss"].sum()) if not hikes.empty else 0.0
total_savings = float(drops["savings_amt"].sum()) if not drops.empty else 0.0
max_hike_pct = float(hikes["hike_pct"].max()) if not hikes.empty else 0.0

if (total_loss >= 2000) or (max_hike_pct >= 15.0) or (len(unmatched) >= 2) or (len(fuzzy_suggestions) > 0):
    risk_label = t("HIGH RISK", "அதிக அபாயம் (HIGH)")
elif (total_loss > 0) or (len(unmatched) > 0):
    risk_label = t("MEDIUM RISK", "நடுத்தர அபாயம் (MEDIUM)")
else:
    risk_label = t("LOW RISK", "குறைந்த அபாயம் (LOW)")

audit_sig = f"{source_label}|{threshold}|{min_loss_filter}|{len(hikes)}|{round(total_loss,2)}|{round(total_savings,2)}"
if st.session_state.get("last_audit_sig") != audit_sig:
    st.session_state["last_audit_sig"] = audit_sig
    st.session_state["audit_history"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "source": source_label,
        "hiked_items": len(hikes),
        "extra_cost": f"{curr_sym}{total_loss:,.2f}",
        "savings": f"{curr_sym}{total_savings:,.2f}",
        "risk": risk_label,
    })

# --- 7. KPIs & AI Executive Summary ---
st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric(t("Rate-Hiked Items", "ரேட் ஏறிய ஐட்டங்கள்"), f"{len(hikes)}")
k2.metric(t("Total Extra Cost Leakage", "மொத்த கூடுதல் செலவு"), f"{curr_sym}{total_loss:,.2f}")
k3.metric(t("Price Drop Savings", "ரேட் குறைவால் சேமிப்பு"), f"{curr_sym}{total_savings:,.2f}")
k4.metric(t("Audit Risk Level", "ஆடிட் ரிஸ்க் நிலை"), risk_label)

if not hikes.empty:
    top_loss_row = hikes.iloc[0]
    spike_row = hikes.sort_values(by="hike_pct", ascending=False).iloc[0]
    st.warning(
        t(
            f"🤖 AI Executive Summary: Priority hold item is '{top_loss_row['item_name']}' (AI Score {top_loss_row['ai_risk_score']}/100, {curr_sym}{top_loss_row['extra_cost_loss']:,.2f}); highest % hike is '{spike_row['item_name']}' (+{spike_row['hike_pct']}%); fuzzy matches: {len(fuzzy_suggestions)}.",
            f"🤖 AI சுருக்கம்: முதலில் நிறுத்த வேண்டிய ஐட்டம் '{top_loss_row['item_name']}' (AI Score {top_loss_row['ai_risk_score']}/100, {curr_sym}{top_loss_row['extra_cost_loss']:,.2f}); அதிக % உயர்வு '{spike_row['item_name']}' (+{spike_row['hike_pct']}%); பெயர் ஒப்பீடு: {len(fuzzy_suggestions)}.",
        )
    )
elif fuzzy_suggestions:
    st.warning(
        t(
            f"🤖 AI Fuzzy Alert: Found {len(fuzzy_suggestions)} item(s) with new/different code but matching item name.",
            f"🤖 AI ஒப்பீடு எச்சரிக்கை: புது கோடில் வந்தாலும் பழைய ஐட்டம் பெயருடன் ஒத்துப்போகும் {len(fuzzy_suggestions)} ஐட்டம் உள்ளது.",
        )
    )
else:
    st.success(
        t(
            "🤖 AI Audit Insight: No major rate anomalies above your threshold.",
            "🤖 AI ஆடிட் குறிப்பு: உங்கள் வரம்புக்கு மேல் முக்கிய ரேட் உயர்வு இல்லை.",
        )
    )

# --- Visual Cost Impact Chart & Supplier Breakdown ---
if not hikes.empty:
    st.subheader(t("📊 Visual Rate-Hike Cost Impact", "📊 ரேட் உயர்வு செலவு வரைபடம்"))
    chart_df = hikes.set_index("item_name")[["extra_cost_loss"]]
    st.bar_chart(chart_df)

    sup_summary = (
        hikes.groupby("supplier_name", as_index=False)
        .agg(
            hiked_items=("item_code", "count"),
            total_extra_cost=("extra_cost_loss", "sum"),
            max_risk_score=("ai_risk_score", "max"),
        )
        .sort_values(by="total_extra_cost", ascending=False)
    )
    st.caption(t("Supplier-wise Rate-Hike Summary", "சப்ளையர் வாரியான ரேட் உயர்வு சுருக்கம்"))
    st.dataframe(sup_summary, use_container_width=True)

# --- 8. Detected Hikes, Pro AI Automation & Alerts ---
st.subheader(t("🚨 Detected Rate-Hike Items & AI Action", "🚨 ரேட் உயர்வு ஐட்டங்கள் & AI முடிவு"))
if not hikes.empty:
    display_cols = [
        "supplier_name",
        "item_code",
        "item_name",
        "old_unit_price",
        "new_unit_price",
        "qty_billed",
        "hike_pct",
        "extra_cost_loss",
        "ai_risk_score",
        "ai_action",
    ]
    st.dataframe(hikes[display_cols], use_container_width=True)

    ex1, ex2 = st.columns(2)
    with ex1:
        csv_data = hikes[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            t("📥 Download AI Audit Report CSV", "📥 AI ஆடிட் ரிப்போர்ட் CSV டவுன்லோட்"),
            data=csv_data,
            file_name="rateguard_ai_audit_report.csv",
            mime="text/csv",
        )
    with ex2:
        exec_summary_txt = (
            f"RateGuard AI — Executive Audit Summary\n"
            f"Risk Level: {risk_label}\n"
            f"Rate-Hiked Items: {len(hikes)}\n"
            f"Total Extra Cost Leakage: {curr_sym}{total_loss:,.2f}\n"
            f"Price Drop Savings: {curr_sym}{total_savings:,.2f}\n"
            f"Unmatched / Fuzzy Items: {len(unmatched)} / {len(fuzzy_suggestions)}\n"
        )
        st.download_button(
            t("📄 Download Executive Summary (.txt)", "📄 ஆடிட் சுருக்கம் டவுன்லோட் (.txt)"),
            data=exec_summary_txt.encode("utf-8"),
            file_name="rateguard_executive_summary.txt",
            mime="text/plain",
        )

    if not st.session_state["is_pro"]:
        st.info(
            t(
                "🔒 Pro Business Feature: Unlock Automated Negotiation Playbook, Custom Supplier Drafts, Verification Checklist & Email/SMS Alerts in the 'Pay Online & Activate Pro' section below.",
                "🔒 Pro திட்ட வசதி: தானியங்கி பேச்சுவார்த்தை டிராஃப்ட், சரிபார்ப்பு பட்டியல் மற்றும் ஈமெயில்/SMS அலர்ட்களை இயக்க கீழே உள்ள 'Pay Online & Activate Pro' பகுதியில் Pro-வை இயக்கவும்.",
            )
        )
    else:
        st.subheader(t("🧠 AI Negotiation Automation, Checklist & Drafts", "🧠 AI பேச்சுவார்த்தை ஆட்டோமேஷன், சரிபார்ப்பு & டிராஃப்ட்"))

        t_col1, t_col2 = st.columns(2)
        with t_col1:
            neg_tone = st.radio(
                t("Select Negotiation Tone", "பேச்சுவார்த்தை தொனியைத் தேர்ந்தெடுக்கவும்"),
                [
                    t("Firm (Hold Excess Payment)", "கறாரானது (கூடுதல் தொகை நிறுத்தம்)"),
                    t("Partnership (Rate Lock & Volume Deal)", "கூட்டுறவு (ரேட் லாக் & ஒப்பந்தம்)"),
                ],
                horizontal=True,
            )
        with t_col2:
            dispute_reason = st.selectbox(
                t("Primary Dispute Reason", "முக்கிய தகராறு காரணம்"),
                [
                    "Unauthorized Rate Hike",
                    "Wrong Unit / Pack Size",
                    "New Code Without Approval",
                ],
            )

        top_item = hikes.iloc[0]["item_name"]
        top_loss = float(hikes.iloc[0]["extra_cost_loss"])
        hold_items = hikes[hikes["ai_action"] == "HOLD PAYMENT"]["item_name"].tolist()
        hold_str = ", ".join(hold_items) if hold_items else top_item

        if "Firm" in neg_tone:
            playbook_msg = t(
                f"Hold {curr_sym}{total_loss:,.2f} variance payout immediately ({dispute_reason}). Priority hold items: {hold_str}. Require written approval before clearing balance.",
                f"{curr_sym}{total_loss:,.2f} வித்தியாசத் தொகையை உடனடியாக நிறுத்தி வைக்கவும் ({dispute_reason}). உடனடி நிறுத்த ஐட்டங்கள்: {hold_str}. எழுத்துப்பூர்வமான ஒப்புதல் வந்த பிறகே மீதித் தொகையை வழங்கவும்.",
            )
        else:
            playbook_msg = t(
                f"Request supplier to honor prior approved rate card on '{top_item}' ({curr_sym}{top_loss:,.2f}) regarding '{dispute_reason}' and lock quarterly pricing for repeat orders.",
                f"'{top_item}' ({curr_sym}{top_loss:,.2f}) ஐட்டத்திற்கு ('{dispute_reason}') பழைய approved rate தொடரவும், அடுத்த ஆர்டர்களுக்கு காலாண்டு rate lock செய்யவும் சப்ளையரிடம் பேசுங்கள்.",
            )

        st.info(f"🎯 {playbook_msg}")

        with st.expander(t("📋 Audit Brief & Buyer Verification Checklist", "📋 ஆடிட் சுருக்கம் & சரிபார்ப்பு பட்டியல்"), expanded=True):
            brief_txt = (
                f"RateGuard AI Audit Summary\n"
                f"- Risk Level: {risk_label}\n"
                f"- Dispute Reason: {dispute_reason}\n"
                f"- Rate-Hiked Items: {len(hikes)}\n"
                f"- Total Extra Cost Leakage: {curr_sym}{total_loss:,.2f}\n"
                f"- Price Drop Savings: {curr_sym}{total_savings:,.2f}\n"
                f"- Unmatched / Fuzzy Items: {len(unmatched)} / {len(fuzzy_suggestions)}\n"
                f"- Recommended Action: {playbook_msg}"
            )
            st.text_area(t("Copy-Ready Audit Summary:", "காப்பி செய்யத் தயாரான ஆடிட் சுருக்கம்:"), brief_txt, height=160)

            st.markdown(
                t(
                    """
                    **Buyer Verification Checklist before Payment:**
                    1. Verify written rate-revision approval or email confirmation from Procurement/Management.
                    2. Cross-check PO rate, billed unit/pack size (e.g., per piece vs box), and item code/name spelling.
                    3. Hold excess variance amount until rate discrepancy is resolved or credit note is issued.
                    """,
                    """
                    **பணம் வழங்குவதற்கு முன் சரிபார்க்க வேண்டியவை:**
                    1. ரேட் மாற்றத்திற்கான எழுத்துப்பூர்வமான ஒப்புதல் அல்லது ஈமெயில் ஆதாரம் இருக்கிறதா எனச் சரிபார்க்கவும்.
                    2. Purchase Order ரேட், யூனிட்/பேக் அளவு (piece/box), மற்றும் ஐட்டம் பெயர்/கோட் சரியாக இருக்கிறதா எனப் பார்க்கவும்.
                    3. வித்தியாசத் தொகை தெளிவாகும் வரை அல்லது Credit Note வரும் வரை கூடுதல் தொகையை நிறுத்தி வைக்கவும்.
                    """,
                )
            )

        email_rows = "\n".join([
            f"* [{row['supplier_name']}] {row['item_name']} ({row['item_code']}): Billed {curr_sym}{row['new_unit_price']} vs Approved {curr_sym}{row['old_unit_price']} (+{row['hike_pct']}%) | Action: {row['ai_action']}"
            for _, row in hikes.iterrows()
        ])
        email_text = (
            f"Subject: Rate Variance Review ({dispute_reason}) - Invoice Audit\n\n"
            f"Hi Supplier Team,\n\n"
            f"Our AI procurement audit flagged unit price variances ({dispute_reason}) on the following items:\n\n"
            f"{email_rows}\n\n"
            f"Total identified variance: {curr_sym}{total_loss:,.2f}.\n"
            f"Next step: {playbook_msg}\n\n"
            f"Best regards,\nProcurement Team"
        )
        st.text_area(t("Automated Email Draft:", "தானியங்கி ஈமெயில் டிராஃப்ட்:"), email_text, height=195)

        short_msg = (
            f"RateGuard AI ({dispute_reason}): Noted {curr_sym}{total_loss:,.2f} variance across {len(hikes)} item(s). Please share approved rate note."
        )
        st.text_input(
            t("Quick SMS / Call Talking Point:", "சப்ளையருக்கு குறுகிய SMS / பேச்சு குறிப்பு:"),
            value=short_msg,
        )

        with st.expander(t("📣 Send Rate-Hike Alert (Email / SMS)", "📣 ரேட் உயர்வு அலர்ட் அனுப்பவும் (ஈமெயில் / SMS)")):
            alert_summary = (
                f"RateGuard AI Alert | Risk: {risk_label} | Reason: {dispute_reason} | "
                f"Hiked Items: {len(hikes)} | Extra Cost: {curr_sym}{total_loss:,.2f} | "
                f"Unmatched: {len(unmatched)}"
            )

            tab_email, tab_sms = st.tabs([
                t("✉️ Email Alert", "✉️ ஈமெயில் அலர்ட்"),
                t("📱 SMS Alert", "📱 SMS அலர்ட்"),
            ])

            with tab_email:
                recipient_email = st.text_input(
                    t("Recipient Email (Owner / Purchase Head)", "பெறுநர் ஈமெயில் (உரிமையாளர் / பர்ச்சேஸ் ஹெட்)"),
                    key="alert_email_to",
                )
                if st.button(t("Send Email Alert", "ஈமெயில் அலர்ட் அனுப்பு"), key="btn_send_email"):
                    email_cfg = st.secrets.get("email", {}) if hasattr(st, "secrets") else {}
                    smtp_server = email_cfg.get("smtp_server", "smtp.gmail.com")
                    smtp_port = email_cfg.get("smtp_port", 465)
                    sender_email = email_cfg.get("sender_email")
                    app_password = email_cfg.get("app_password")

                    if not recipient_email.strip():
                        st.error(t("Please enter a recipient email.", "பெறுநர் ஈமெயில் முகவரியை உள்ளிடவும்."))
                    elif not (smtp_server and sender_email and app_password):
                        st.info(
                            t(
                                "Email secrets not set yet. Preview of alert ready to send:",
                                "ஈமெயில் Secrets இன்னும் அமைக்கப்படவில்லை. அனுப்பத் தயாராக உள்ள அலர்ட் விவரம்:",
                            )
                        )
                        st.code(alert_summary)
                    else:
                        try:
                            dispatch_email_alert(
                                smtp_server=smtp_server,
                                smtp_port=smtp_port,
                                sender_email=sender_email,
                                app_password=app_password,
                                recipient=recipient_email,
                                subject=f"RateGuard AI Alert: {curr_sym}{total_loss:,.2f} Extra Cost Detected",
                                body_text=alert_summary,
                            )
                            st.success(t("Email alert sent!", "ஈமெயில் அலர்ட் அனுப்பப்பட்டது!"))
                        except Exception as e:
                            st.error(t(f"Email error: {e}", f"ஈமெயில் பிழை: {e}"))

            with tab_sms:
                recipient_phone = st.text_input(
                    t("Recipient Phone (with country code, e.g. +91...)", "பெறுநர் மொபைல் எண் (நாடு குறியீட்டுடன், எ.கா. +91...)"),
                    key="alert_sms_to",
                )
                sms_preview = (
                    f"RateGuard AI: {len(hikes)} rate hikes ({curr_sym}{total_loss:,.2f} extra cost). Risk: {risk_label}."
                )
                st.caption(
                    t(
                        f"SMS Preview ({len(sms_preview)} chars): {sms_preview}",
                        f"SMS முன்னோட்டம் ({len(sms_preview)} எழுத்துக்கள்): {sms_preview}",
                    )
                )

                if st.button(t("Send SMS Alert", "SMS அலர்ட் அனுப்பு"), key="btn_send_sms"):
                    sms_cfg = st.secrets.get("sms", {}) if hasattr(st, "secrets") else {}
                    account_sid = sms_cfg.get("account_sid")
                    auth_token = sms_cfg.get("auth_token")
                    from_number = sms_cfg.get("from_number")

                    if not recipient_phone.strip():
                        st.error(t("Please enter a phone number.", "மொபைல் எண்ணை உள்ளிடவும்."))
                    elif not (account_sid and auth_token and from_number):
                        st.info(
                            t(
                                "SMS gateway secrets not configured yet. Connect Twilio/SMS provider in Streamlit Secrets to dispatch live SMS.",
                                "SMS கேட்வே Secrets இன்னும் சேர்க்கப்படவில்லை. நேரடி SMS அனுப்ப Streamlit Secrets-ல் விவரங்களைச் சேர்க்கவும்.",
                            )
                        )
                        st.code(f"To: {recipient_phone.strip()}\nMessage: {sms_preview}")
                    else:
                        try:
                            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                            resp = requests.post(
                                url,
                                data={
                                    "From": from_number,
                                    "To": recipient_phone.strip(),
                                    "Body": sms_preview,
                                },
                                auth=(account_sid, auth_token),
                                timeout=10,
                            )
                            if resp.status_code in (200, 201):
                                st.success(t("SMS alert sent!", "SMS அலர்ட் அனுப்பப்பட்டது!"))
                            else:
                                st.error(t(f"SMS failed ({resp.status_code}): {resp.text}", f"SMS அனுப்ப முடியவில்லை ({resp.status_code})"))
                        except Exception as e:
                            st.error(t(f"SMS error: {e}", f"SMS பிழை: {e}"))
else:
    st.success(
        t(
            "No unauthorized rate hikes found above your threshold.",
            "நீங்கள் நிர்ணயித்த வரம்பிற்கு மேல் எந்த ரேட் உயர்வும் இல்லை.",
        )
    )

# --- 9. Price Drops, AI Fuzzy Matches & Unmatched Items ---
if not drops.empty:
    st.subheader(t("💚 Price Drops / Potential Savings", "💚 ரேட் குறைவு / சாத்தியமான சேமிப்பு"))
    st.dataframe(
        drops[["supplier_name", "item_code", "item_name", "old_unit_price", "new_unit_price", "qty_billed", "savings_amt"]],
        use_container_width=True,
    )

if fuzzy_suggestions:
    st.subheader(
        t(
            "🔍 AI Fuzzy Name Matches (Check Code / Name Variations)",
            "🔍 AI பெயர் ஒப்பீடு (கோட் / பெயர் வித்தியாசங்களைச் சரிபார்க்கவும்)",
        )
    )
    st.dataframe(pd.DataFrame(fuzzy_suggestions), use_container_width=True)

if not unmatched.empty:
    st.warning(
        t(
            "⚠️ Unmatched / New Items (Not in Approved Rate List):",
            "⚠️ பழைய அப்ரூவ்ட் ரேட் பட்டியலில் இல்லாத புது ஐட்டங்கள்:",
        )
    )
    st.dataframe(
        unmatched[["supplier_name", "item_code", "item_name_inv", "qty_billed", "new_unit_price"]],
        use_container_width=True,
    )

# --- 10. Session Audit History ---
if st.session_state["audit_history"]:
    with st.expander(t("🕒 Session Audit History", "🕒 இந்த செஷன் ஆடிட் வரலாறு"), expanded=False):
        st.dataframe(pd.DataFrame(st.session_state["audit_history"]), use_container_width=True)
        if st.button(t("Clear History", "வரலாற்றை அழி"), key="btn_clear_hist"):
            st.session_state["audit_history"] = []
            st.session_state["last_audit_sig"] = ""
            st.rerun()

# --- 11. Subscription & Online Checkout Flow ---
st.divider()
st.subheader(t("💳 Online Plans & Pro Subscription", "💳 ஆன்லைன் திட்டங்கள் & Pro சப்ஸ்கிரிப்ஷன்"))

billing_cfg = st.secrets.get("billing", {}) if hasattr(st, "secrets") else {}
pro_monthly_url = str(billing_cfg.get("pro_monthly_url", "")).strip()
pro_yearly_url = str(billing_cfg.get("pro_yearly_url", "")).strip()
upi_id = str(billing_cfg.get("upi_id", "")).strip()
support_email = str(billing_cfg.get("support_email", "")).strip()
pro_unlock_code = str(billing_cfg.get("pro_code", "PRO2026")).strip()

p1, p2 = st.columns(2)
with p1:
    st.markdown(
        f"**{t('Free Starter', 'இலவச திட்டம் (Free)')}**\n"
        f"* {t('Manual CSV rate-hike & savings check', 'CSV ரேட் உயர்வு & சேமிப்பு பரிசோதனை')}\n"
        f"* {t('Bilingual UI & CSV report export', 'இருமொழி வசதி & CSV ரிப்போர்ட்')}"
    )
with p2:
    status_badge = (
        t("✅ Active Pro", "✅ Pro ஆக்டிவ்")
        if st.session_state["is_pro"]
        else t("🔒 Online Upgrade Available", "🔒 ஆன்லைன் அப்கிரேட் வசதி")
    )
    st.markdown(
        f"**{t('Pro Business Plan', 'ப்ரோ பிசினஸ் திட்டம் (Pro)')}** — {status_badge}\n"
        f"* {t('Automated Email & SMS alerts', 'தானியங்கி ஈமெயில் & SMS அலர்ட்கள்')}\n"
        f"* {t('Priority support & AI negotiation playbook', 'முன்னுரிமை உதவி & AI பேச்சுவார்த்தை வழிகாட்டி')}"
    )

with st.expander(t("🚀 Pay Online & Activate Pro", "🚀 ஆன்லைனில் கட்டணம் செலுத்தி Pro-வை இயக்கவும்"), expanded=False):
    c_plan, c_biz = st.columns(2)
    with c_plan:
        plan_choice = st.selectbox(
            t("Select Plan", "திட்டத்தைத் தேர்ந்தெடுக்கவும்"),
            ["Pro Monthly", "Pro Yearly"],
            key="sub_plan_choice",
        )
    with c_biz:
        biz_name = st.text_input(
            t("Company / Business Name", "நிறுவனத்தின் பெயர்"),
            key="sub_biz_name",
        )

    checkout_url = pro_monthly_url if plan_choice == "Pro Monthly" else pro_yearly_url

    if checkout_url:
        st.link_button(
            t(
                f"💳 Proceed to Online Payment ({plan_choice})",
                f"💳 ஆன்லைன் கட்டணத்திற்குச் செல்லவும் ({plan_choice})",
            ),
            checkout_url,
        )
    else:
        st.info(
            t(
                "Online payment link is not configured yet. Add `pro_monthly_url` and `pro_yearly_url` under `[billing]` in Streamlit Secrets to activate live online checkout.",
                "ஆன்லைன் கட்டண லிங்க் இன்னும் சேர்க்கப்படவில்லை. நேரடி ஆன்லைன் கட்டணத்திற்கு Streamlit Secrets-ல் `[billing]` கீழ் `pro_monthly_url` மற்றும் `pro_yearly_url` சேர்க்கவும்.",
            )
        )

    if upi_id:
        st.caption(t(f"UPI ID: {upi_id}", f"UPI ஐடி: {upi_id}"))
    if support_email:
        st.caption(t(f"Billing Support: {support_email}", f"பில்லிங் உதவி: {support_email}"))

    unlock_in = st.text_input(
        t("Pro Activation Code", "Pro ஆக்டிவேஷன் கோடு"),
        type="password",
        key="pro_code_input",
    )
    if st.button(t("Activate Pro Access", "Pro அணுகலை இயக்கு"), key="btn_activate_pro"):
        if unlock_in.strip() == pro_unlock_code:
            st.session_state["is_pro"] = True
            st.success(t("Pro Business Plan unlocked for this session!", "இந்த செஷனுக்கு Pro பிசினஸ் திட்டம் இயக்கப்பட்டது!"))
            st.rerun()
        else:
            st.error(t("Invalid activation code.", "தவறான ஆக்டிவேஷன் கோடு."))
