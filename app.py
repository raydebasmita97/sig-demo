import streamlit as st
import anthropic
import requests
import json
import re

st.set_page_config(page_title="SIG Partners Deal Intake", page_icon="🏢")


def extract_and_score(data):
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    prompt = f"""Analyze this business acquisition inquiry and return a JSON object with exactly these fields:
- company_name: string
- contact_name: string
- contact_title: string
- industry: string
- estimated_revenue: string
- reason_for_selling: string
- contact_email: string
- contact_phone: string
- employees: string
- years_in_business: string
- exit_timeline: string
- primary_motivation: string
- management_team: string
- location: string
- lead_source: string
- qualification_score: integer from 1 to 10
- score_reasoning: string explaining the score
- recommended_action: string, either "Route to BD Team" or "Add to Review Queue"
- key_strengths: array of strings
- key_concerns: array of strings

Scoring criteria (apply each that fits, sum the points, then normalize to a 1-10 score where 13 raw points = 10):
- Revenue $4M or more: 3 points
- Target industries (home healthcare, HVAC, plumbing, roofing, electrical, distribution, professional services, manufacturing): 2 points
- Legacy or motivated seller, not just price-driven: 2 points
- Clear exit timeline under 12 months: 1 point
- Has management team (fully or partially): 1 point
- Complete contact info including phone: 1 point
- Strong existing team mentioned in notes: 1 point
- Years in business over 5: 1 point
- Number of employees over 10: 1 point

Business inquiry:
Business Name: {data['business_name']}
Contact Name: {data['contact_name']}
Contact Title: {data['contact_title']}
Industry: {data['industry']}
Annual Revenue: {data['annual_revenue']}
Phone: {data['phone']}
Employees: {data['employees']}
Years in Business: {data['years_in_business']}
Exit Timeline: {data['exit_timeline']}
Primary Motivation: {data['primary_motivation']}
Management Team: {data['management_team']}
Location: {data['location']}
How They Found SIG: {data['lead_source']}
Reason for Selling: {data['reason_for_selling']}
Contact Email: {data['contact_email']}
Additional Notes: {data.get('additional_notes') or 'None provided'}"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are an acquisition analyst at SIG Partners. Always respond with only valid JSON and nothing else. No preamble, no markdown, no backticks.",
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    response_text = re.sub(r"```(?:json)?\s*", "", response_text).strip("`").strip()

    return json.loads(response_text)


def create_monday_record(lead_data):
    try:
        api_key = st.secrets["MONDAY_API_KEY"]
        board_id = st.secrets["MONDAY_BOARD_ID"]

        item_name = lead_data.get("contact_name", lead_data.get("company_name", "Unknown"))

        strengths = lead_data.get("key_strengths", [])
        concerns = lead_data.get("key_concerns", [])
        if isinstance(strengths, list):
            strengths = "; ".join(strengths)
        if isinstance(concerns, list):
            concerns = "; ".join(concerns)

        column_values = {
            "lead_status":      {"label": "New Lead"},
            "lead_company":     lead_data.get("company_name", ""),
            "text":             lead_data.get("contact_title", ""),
            "text_mm3rv0cy":    lead_data.get("industry", ""),
            "text_mm3rc119":    lead_data.get("estimated_revenue", ""),
            "numeric_mm3rwcwe": str(lead_data.get("qualification_score", "")),
            "text_mm3rewdc":    lead_data.get("recommended_action", ""),
            "text_mm3raqv0":    strengths,
            "text_mm3rm6xw":    concerns,
            "text_mm3re8td":    lead_data.get("score_reasoning", ""),
            "lead_email": {
                "email": lead_data.get("contact_email", ""),
                "text":  lead_data.get("contact_email", ""),
            },
            "lead_phone": {
                "phone":            lead_data.get("contact_phone", ""),
                "countryShortName": "US",
            },
            "text_mm3rb47p":    lead_data.get("exit_timeline", ""),
            "text_mm3rhnhb":    lead_data.get("primary_motivation", ""),
            "numeric_mm3r9q47": str(lead_data.get("employees", "")),
            "numeric_mm3rvagf": str(lead_data.get("years_in_business", "")),
            "text_mm3ryh43":    lead_data.get("management_team", ""),
            "text_mm3rxw12":    lead_data.get("location", ""),
            "text_mm3re92b":    lead_data.get("lead_source", ""),
        }

        mutation = """
        mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
            create_item(
                board_id: $boardId
                item_name: $itemName
                column_values: $columnValues
            ) {
                id
            }
        }
        """

        response = requests.post(
            "https://api.monday.com/v2",
            headers={
                "Authorization":  api_key,
                "Content-Type":   "application/json",
                "API-Version":    "2024-01",
            },
            json={
                "query": mutation,
                "variables": {
                    "boardId":       board_id,
                    "itemName":      item_name,
                    "columnValues":  json.dumps(column_values),
                },
            },
        )

        if response.status_code != 200:
            print(f"Monday.com API error: {response.status_code} — {response.text}")
        else:
            result = response.json()
            if "errors" in result:
                print(f"Monday.com GraphQL errors: {result['errors']}")
    except Exception as e:
        print(f"Monday.com integration error: {e}")


# ── Session state init ────────────────────────────────────────────────────────
if "stage" not in st.session_state:
    st.session_state.stage = "form"
if "form_data" not in st.session_state:
    st.session_state.form_data = {}
if "result" not in st.session_state:
    st.session_state.result = None


# ── SCREEN 1: FORM ────────────────────────────────────────────────────────────
if st.session_state.stage == "form":
    st.title("SIG Partners")
    st.subheader("Business Acquisition Inquiry")
    st.caption(
        "Tell us about your business. We review every inquiry personally "
        "and respond within one business day."
    )

    with st.form("intake_form"):
        business_name = st.text_input("Business Name *")
        contact_name = st.text_input("Contact Person Full Name *")

        contact_title = st.selectbox(
            "Your Title *",
            [
                "Select your title",
                "Owner",
                "CEO",
                "President",
                "Partner",
                "Co-Founder",
                "Other",
            ],
        )

        industry = st.selectbox(
            "Industry *",
            [
                "Select an industry",
                "Home Healthcare",
                "HVAC and Heating and Air",
                "Plumbing",
                "Roofing and Siding",
                "Electrical",
                "Distribution and Supply",
                "Pharmacy",
                "Professional Services",
                "Manufacturing",
                "Other",
            ],
        )

        annual_revenue = st.selectbox(
            "Annual Revenue *",
            [
                "Select revenue range",
                "Under $2M",
                "$2M to $4M",
                "$4M to $7M",
                "$7M to $15M",
                "$15M to $30M",
                "Over $30M",
            ],
        )

        col_a, col_b = st.columns(2)
        with col_a:
            employees = st.number_input(
                "Number of Employees *", min_value=0, step=1, value=0
            )
        with col_b:
            years_in_business = st.number_input(
                "Years in Business *", min_value=0, step=1, value=0
            )

        exit_timeline = st.selectbox(
            "Exit Timeline *",
            [
                "Select timeline",
                "Within 6 months",
                "6 to 12 months",
                "1 to 2 years",
                "Just exploring",
            ],
        )

        primary_motivation = st.selectbox(
            "Primary Motivation *",
            [
                "Select motivation",
                "Legacy and employees",
                "Best price",
                "Retirement",
                "Other",
            ],
        )

        management_team = st.selectbox(
            "Does a management team exist that can run without you? *",
            [
                "Select option",
                "Yes fully",
                "Partially",
                "No just me",
            ],
        )

        location = st.text_input("Location — City and State *")

        col_c, col_d = st.columns(2)
        with col_c:
            contact_email = st.text_input("Contact Email *")
        with col_d:
            phone = st.text_input("Phone Number *")

        lead_source = st.selectbox(
            "How did you hear about SIG? *",
            [
                "Select option",
                "Google search",
                "Broker referral",
                "Friend or colleague",
                "Social media",
                "Other",
            ],
        )

        reason_for_selling = st.text_area("Reason for Selling *")
        additional_notes = st.text_area("Additional Notes (optional)")

        submitted = st.form_submit_button("Submit Inquiry")

    if submitted:
        errors = []
        if not business_name.strip():
            errors.append("Business name is required.")
        if not contact_name.strip():
            errors.append("Contact person name is required.")
        if contact_title == "Select your title":
            errors.append("Please select your title.")
        if industry == "Select an industry":
            errors.append("Please select an industry.")
        if annual_revenue == "Select revenue range":
            errors.append("Please select a revenue range.")
        if employees == 0:
            errors.append("Number of employees is required.")
        if years_in_business == 0:
            errors.append("Years in business is required.")
        if exit_timeline == "Select timeline":
            errors.append("Please select an exit timeline.")
        if primary_motivation == "Select motivation":
            errors.append("Please select a primary motivation.")
        if management_team == "Select option":
            errors.append("Please select a management team option.")
        if not location.strip():
            errors.append("Location is required.")
        if not contact_email.strip():
            errors.append("Contact email is required.")
        if not phone.strip():
            errors.append("Phone number is required.")
        if lead_source == "Select option":
            errors.append("Please select how you heard about SIG.")
        if not reason_for_selling.strip():
            errors.append("Reason for selling is required.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            st.session_state.form_data = {
                "business_name":      business_name.strip(),
                "contact_name":       contact_name.strip(),
                "contact_title":      contact_title,
                "industry":           industry,
                "annual_revenue":     annual_revenue,
                "employees":          str(int(employees)),
                "years_in_business":  str(int(years_in_business)),
                "exit_timeline":      exit_timeline,
                "primary_motivation": primary_motivation,
                "management_team":    management_team,
                "location":           location.strip(),
                "contact_email":      contact_email.strip(),
                "phone":              phone.strip(),
                "lead_source":        lead_source,
                "reason_for_selling": reason_for_selling.strip(),
                "additional_notes":   additional_notes.strip(),
            }
            st.session_state.stage = "processing"
            st.rerun()


# ── SCREEN 2: PROCESSING ──────────────────────────────────────────────────────
elif st.session_state.stage == "processing":
    st.title("SIG Partners")

    try:
        with st.spinner("Analyzing your inquiry against SIG acquisition criteria..."):
            result = extract_and_score(st.session_state.form_data)
            create_monday_record(result)
        st.session_state.result = result
        st.session_state.stage = "result"
        st.rerun()
    except Exception as e:
        st.error(f"An error occurred while processing your inquiry: {e}")
        if st.button("Try Again"):
            st.session_state.stage = "form"
            st.rerun()


# ── SCREEN 3: RESULT ──────────────────────────────────────────────────────────
elif st.session_state.stage == "result":
    result = st.session_state.result
    score = int(result.get("qualification_score", 0))

    st.title("SIG Partners")

    if score >= 7:
        st.success(
            "Your inquiry has been routed to our Business Development team. "
            "Someone will be in touch within one business day."
        )
    elif score >= 5:
        st.warning(
            "Your inquiry has been added to our review queue. "
            "We will be in touch within two to three business days."
        )
    else:
        st.info(
            "Thank you for reaching out. Our team will review your inquiry "
            "and follow up if there is a fit."
        )

    st.divider()

    st.subheader("Who We Heard From")
    col_w1, col_w2 = st.columns(2)
    col_w1.metric("Contact", result.get("contact_name", "N/A"))
    col_w2.metric("Title", result.get("contact_title", "N/A"))

    st.divider()

    st.subheader("What We Captured")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Business Name", result.get("company_name", "N/A"))
        st.metric("Revenue", result.get("estimated_revenue", "N/A"))
    with col2:
        st.metric("Industry", result.get("industry", "N/A"))
        st.metric("Score", f"{score} / 10")

    st.divider()

    st.subheader("Qualification Analysis")
    st.write(result.get("score_reasoning", ""))

    key_strengths = result.get("key_strengths", [])
    if key_strengths:
        items = (
            "<br>".join(f"&bull; {s}" for s in key_strengths)
            if isinstance(key_strengths, list)
            else str(key_strengths)
        )
        st.markdown(
            f'<p style="color:#2E7D32;"><strong>Strengths:</strong><br>{items}</p>',
            unsafe_allow_html=True,
        )

    key_concerns = result.get("key_concerns", [])
    if key_concerns:
        items = (
            "<br>".join(f"&bull; {c}" for c in key_concerns)
            if isinstance(key_concerns, list)
            else str(key_concerns)
        )
        st.markdown(
            f'<p style="color:#B45309;"><strong>Considerations:</strong><br>{items}</p>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.caption(
        "Live demo built by Debasmita Ray for SIG Partners. "
        "CRM record created in real time."
    )

    if st.button("Submit Another Inquiry"):
        st.session_state.stage = "form"
        st.session_state.form_data = {}
        st.session_state.result = None
        st.rerun()
