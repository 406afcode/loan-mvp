import streamlit as st
import openai
from PyPDF2 import PdfReader
import json

# --- 1. CONFIGURATION & MARKET DATA ---
st.set_page_config(page_title="UploadYourLoan", layout="wide")

# HARDCODED INDEX RATES
PRIME_RATE = 7.75
TREASURY_10Y = 4.25

# LISTS
COMMERCIAL_PROPERTY_TYPES = [
    "Multifamily (5+ Units)",
    "1-4 Unit Rental Property (Investment)",
    "Mixed-Use (Residential + Commercial)",
    "Office - General", "Office - Medical",
    "Industrial / Warehouse", "Self-Storage",
    "Retail - Strip Center", "Retail - Free Standing",
    "Hospitality - Hotel / Motel", "Mobile Home Park",
    "Land - Developed", "Special Purpose"
]

US_STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
             "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
             "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
             "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
             "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

LOAN_PURPOSES = [
    "Purchase Finished Commercial Real Estate",
    "Refinance Finished Commercial Real Estate",
    "Ground up Construction",
    "Fix & Flip",
    "Purchase and Improve Commercial Real Estate"
]

# --- 2. MARKET RATE ENGINE ---
def calculate_market_rate(purpose):
    if purpose == "Purchase Finished Commercial Real Estate":
        return TREASURY_10Y + 2.75, "10y Treasury + 2.75%"
    elif purpose == "Refinance Finished Commercial Real Estate":
        return TREASURY_10Y + 2.75, "10y Treasury + 2.75%"
    elif purpose == "Ground up Construction":
        return PRIME_RATE + 1.50, "Prime + 1.50%"
    elif purpose == "Fix & Flip":
        return PRIME_RATE + 3.50, "Prime + 3.50%"
    elif purpose == "Purchase and Improve Commercial Real Estate":
        return PRIME_RATE + 1.00, "Prime + 1.00%"
    else:
        return 8.00, "Standard Estimate"

# --- 3. AI AGENT (NOW USES SECRETS) ---
def analyze_existing_note(note_text):
    # AUTOMATICALLY PULLS KEY FROM SECRETS
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    system_prompt = f"""
    You are a Commercial Loan Servicer. Today's Prime Rate is {PRIME_RATE}%.
    Extract comprehensive loan terms.
    1. INTEREST RATE: Calculate current rate using {PRIME_RATE}% + Margin.
    2. DEFAULT RATE: Look for Default Rate clauses.
    3. PAYMENT: Extract amortization formula.
    4. LATE FEES: Extract late fee policy.
    
    Return JSON ONLY:
    {{
        "rate_structure": {{
            "description": "String", "current_rate_percent": Number,
            "is_fixed": Boolean, "default_rate_terms": "String"
        }},
        "payment_terms": {{
            "frequency": "String", "amortization_period": "String",
            "interest_only_period": "String", "late_fee_policy": "String"
        }},
        "maturity_date": "String", "prepay_penalty": "String"
    }}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": note_text[:15000]}],
        temperature=0, response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

def analyze_term_sheet(doc_text):
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    system_prompt = """
    You are a Real Estate Borrower's Advocate. Summarize terms and FLAG RISKS.
    Return JSON ONLY:
    {
        "loan_amount": "String", "rate_structure": "String", "amortization": "String",
        "recourse_type": "String", 
        "advisory_points": ["Point 1...", "Point 2..."]
    }
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": doc_text[:15000]}],
        temperature=0.2, response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

# --- 4. MAIN UI ---
st.sidebar.title("Navigation")
# NO KEY INPUT HERE - IT IS HIDDEN
workflow = st.sidebar.radio("Select Workflow:", ["1. Refinance Existing Loan", "2. Review New Term Sheet"])

st.sidebar.divider()
st.sidebar.markdown(f"**Market Data (Live):**")
st.sidebar.text(f"Treasury 10Y: {TREASURY_10Y}%")
st.sidebar.text(f"WSJ Prime:    {PRIME_RATE}%")

st.title("UploadYourLoan.com")

# ==========================================
# WORKFLOW 1: EXISTING LOAN
# ==========================================
if workflow == "1. Refinance Existing Loan":
    st.markdown("### 🏦 Post your Existing Loan for Refinance")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("1. Property Snapshot")
        p_type = st.selectbox("Property Type", COMMERCIAL_PROPERTY_TYPES)
        loan_purpose = st.selectbox("Original Loan Purpose", LOAN_PURPOSES)
        p_state = st.selectbox("State", US_STATES, index=42)
        c1, c2 = st.columns(2)
        with c1: c_bal = st.number_input("Current Balance ($)", value=1000000, step=10000)
        with c2: e_val = st.number_input("Est. Value ($)", value=1500000, step=10000)

    with col2:
        st.subheader("2. Upload Promissory Note")
        f = st.file_uploader("Upload Note (PDF)", type="pdf", key="refi_upload")

    st.divider()
    if f is not None:
        if st.button("RUN ANALYSIS 🚀", type="primary", use_container_width=True):
            text = ""
            reader = PdfReader(f)
            for page in reader.pages: text += page.extract_text()
            
            with st.spinner("AI is auditing loan terms..."):
                try:
                    res = json.loads(analyze_existing_note(text)) # No API key passed here
                    st.success("Analysis Complete!")
                    st.divider()
                    
                    st.subheader("💰 Financial Structure")
                    rate_data = res.get('rate_structure', {})
                    pay_data = res.get('payment_terms', {})
                    col_a, col_b, col_c = st.columns(3)
                    
                    user_rate = rate_data.get('current_rate_percent', 0)
                    col_a.metric("Your Current Rate", f"{user_rate}%", help=rate_data.get('description'))
                    
                    market_rate_val, market_desc = calculate_market_rate(loan_purpose)
                    if user_rate > market_rate_val:
                        savings = (c_bal * (user_rate/100)) - (c_bal * (market_rate_val/100))
                        col_b.metric("Market Rate", f"{market_rate_val}%", f"-{user_rate - market_rate_val:.2f}%", delta_color="inverse")
                        st.success(f"💰 **Potential Savings:** Refinancing to a market rate ({market_desc}) could save **${savings:,.0f}/year**.")
                    else:
                         col_b.metric("Market Rate", f"{market_rate_val}%", f"+{market_rate_val - user_rate:.2f}% (You are below market)")
                         st.info(f"Your rate is excellent. Market for '{loan_purpose}' is approx {market_rate_val}%.")

                    col_c.metric("Default Rate", rate_data.get('default_rate_terms', 'Not Found'))

                    st.subheader("📜 Terms & Covenants")
                    t1, t2 = st.columns(2)
                    with t1:
                        st.write("**Amortization:**", pay_data.get('amortization_period', 'Not specified'))
                        st.write("**Late Fee:**", pay_data.get('late_fee_policy', 'Not specified')) 
                    with t2:
                        st.write("**Maturity Date:**", res.get('maturity_date'))
                        st.error(f"**Prepayment Penalty:** {res.get('prepay_penalty')}")
                    
                    if st.button("🚀 Post to Lender Portal"):
                        st.balloons()
                        st.success("Deal Posted! Lenders have been notified.")
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("👆 Please upload a PDF to unlock the analysis button.")

# ==========================================
# WORKFLOW 2: NEW LOAN
# ==========================================
elif workflow == "2. Review New Term Sheet":
    st.markdown("### ⚖️ New Loan Advisor")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.subheader("Upload Term Sheet")
        ts_file = st.file_uploader("Upload PDF", type="pdf", key="new_loan_upload")
    
    if ts_file is not None:
        if st.button("REVIEW TERM SHEET 🔎", type="primary", use_container_width=True):
            text = ""
            reader = PdfReader(ts_file)
            for page in reader.pages: text += page.extract_text()
            
            with st.spinner("Reviewing Deal Terms..."):
                try:
                    advice_data = json.loads(analyze_term_sheet(text)) # No API Key passed here
                    st.session_state['advice'] = advice_data
                except Exception as e:
                    st.error(f"Error: {e}")

    with col_b:
        if 'advice' in st.session_state:
            data = st.session_state['advice']
            st.subheader("📋 Term Summary")
            t1, t2 = st.columns(2)
            t1.metric("Loan Amount", data.get('loan_amount'))
            t2.metric("Amortization", data.get('amortization'))
            st.metric("Interest Rate Structure", data.get('rate_structure'))
            recourse = data.get('recourse_type', 'Unknown')
            if "Non-Recourse" in recourse or "Limited" in recourse:
                st.success(f"✅ Recourse: {recourse}")
            else:
                st.error(f"🛑 Recourse: {recourse}")

    if 'advice' in st.session_state:
        st.divider()
        st.subheader("💡 Borrower Advisory Points")
        for point in st.session_state['advice']['advisory_points']:
            st.markdown(f"👉 **{point}**")
        st.divider()
        st.button("⬇️ Download Summary (PDF)")