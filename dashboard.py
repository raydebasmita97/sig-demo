import streamlit as st
import requests
import json
import pandas as pd
import time

st.set_page_config(
    page_title="SIG Partners Live CRM",
    page_icon="📊",
    layout="wide",
)

# ── Navy blue accent via CSS ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    h1 { color: #1F4E79; }
    h3 { color: #1F4E79; }
    .stMetric label { color: #1F4E79; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Fetch leads from Monday.com ───────────────────────────────────────────────
def fetch_leads():
    api_key  = st.secrets["MONDAY_API_KEY"]
    board_id = st.secrets["MONDAY_BOARD_ID"]

    query = f"""
    query {{
      boards(ids: {board_id}) {{
        items_page(limit: 20) {{
          items {{
            name
            created_at
            column_values {{
              id
              text
            }}
          }}
        }}
      }}
    }}
    """

    response = requests.post(
        "https://api.monday.com/v2",
        headers={
            "Authorization": api_key,
            "Content-Type":  "application/json",
            "API-Version":   "2024-01",
        },
        json={"query": query},
    )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        raise ValueError(f"Monday.com API errors: {data['errors']}")

    items = data["data"]["boards"][0]["items_page"]["items"]

    rows = []
    for item in items:
        col = {cv["id"]: cv["text"] for cv in item["column_values"]}

        # Internal sort key — raw datetime, not displayed
        created_raw = item.get("created_at", "")
        try:
            sort_dt = pd.to_datetime(created_raw, utc=True)
        except Exception:
            sort_dt = pd.NaT

        def to_int(col_id):
            raw = col.get(col_id, "")
            try:
                return int(float(raw)) if raw else 0
            except Exception:
                return 0

        rows.append({
            "_sort_dt":            sort_dt,
            "Name":                item.get("name", ""),
            "Industry":            col.get("text_mm3rv0cy", ""),
            "Company":             col.get("lead_company", ""),
            "Title":               col.get("text", ""),
            "Email":               col.get("lead_email", ""),
            "Phone":               col.get("lead_phone", ""),
            "Last Interaction":    col.get("date__1", ""),
            "Recommended Action":  col.get("text_mm3rewdc", ""),
            "Key Concerns":        col.get("text_mm3rm6xw", ""),
            "Key Strengths":       col.get("text_mm3raqv0", ""),
            "Score Reasoning":     col.get("text_mm3re8td", ""),
            "Qualification Score":  to_int("numeric_mm3rwcwe"),
            "How They Found SIG":  col.get("text_mm3re92b", ""),
            "Location":            col.get("text_mm3rxw12", ""),
            "Has Management Team": col.get("text_mm3ryh43", ""),
            "Primary Motivation":  col.get("text_mm3rhnhb", ""),
            "Exit Timeline":       col.get("text_mm3rb47p", ""),
            "Years in Business":   to_int("numeric_mm3rvagf"),
            "Employees":           to_int("numeric_mm3r9q47"),
            "Annual Revenue":      col.get("text_mm3rc119", ""),
        })

    df = pd.DataFrame(rows)

    # Sort newest first, then drop the internal sort column
    if not df.empty:
        df = df.sort_values("_sort_dt", ascending=False).reset_index(drop=True)
    df = df.drop(columns=["_sort_dt"])

    # Ensure number columns are clean integers
    int_cols = ["Qualification Score", "Years in Business", "Employees"]
    for c in int_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # Fill NaN in all text columns with empty string
    text_cols = [
        "Name", "Industry", "Company", "Title", "Email", "Phone",
        "Last Interaction", "Recommended Action", "Key Concerns",
        "Key Strengths", "Score Reasoning", "How They Found SIG",
        "Location", "Has Management Team", "Primary Motivation",
        "Exit Timeline", "Annual Revenue",
    ]
    df[text_cols] = df[text_cols].fillna("")

    return df


# ── Score cell colour ─────────────────────────────────────────────────────────
def color_score(val):
    try:
        score = int(val)
        if score >= 7:
            color = 'background-color: #90EE90'  # green
        elif score >= 5:
            color = 'background-color: #FFD700'  # amber
        else:
            color = 'background-color: #FFB6B6'  # red
    except:
        color = ''
    return color


# ── HEADER ────────────────────────────────────────────────────────────────────
title_col, btn_col = st.columns([6, 1])
with title_col:
    st.title("SIG Partners — Live Lead Dashboard")
    st.subheader("Real-time submissions from the deal intake form")
    st.caption("Auto-refreshes every 30 seconds")
with btn_col:
    st.write("")
    st.write("")
    manual_refresh = st.button("🔄  Refresh Now", use_container_width=True)

if manual_refresh:
    st.rerun()

# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading leads from Monday.com..."):
        df = fetch_leads()

    if df.empty:
        st.info("No leads found on the board yet. Submit the first inquiry via the intake form.")
    else:
        # ── Metrics row ───────────────────────────────────────────────────────
        valid_scores = df["Qualification Score"]
        total  = len(df)
        avg    = valid_scores.mean() if len(valid_scores) else 0
        strong = int((valid_scores >= 7).sum())
        review = int(((valid_scores >= 5) & (valid_scores <= 6)).sum())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Leads",        total)
        m2.metric("Average Score",      f"{avg:.1f} / 10")
        m3.metric("Strong Leads (7+)",  strong)
        m4.metric("Needs Review (5–6)", review)

        st.divider()

        # ── Styled dataframe ──────────────────────────────────────────────────
        styled_df = df.style.map(
            color_score,
            subset=['Qualification Score']
        )

        st.dataframe(styled_df, use_container_width=True)

except Exception as e:
    st.error(f"Failed to load leads from Monday.com: {e}")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Live demo built by Debasmita Ray for SIG Partners. "
    "Powered by Monday.com API."
)

# ── AUTO-REFRESH every 30 seconds ────────────────────────────────────────────
time.sleep(30)
st.rerun()
