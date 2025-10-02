import streamlit as st
import pandas as pd
import io
import openai
import json
import re

st.set_page_config(page_title="Company Info Auto-Fill", layout="wide")
st.title("🏢 Company Info Auto-Fill")

st.markdown(
    "Upload a CSV or TXT file containing a list of company names (one per line). "
    "ChatGPT will try to fill in the information automatically. Unknown data will be left blank."
)

# File upload
uploaded_file = st.file_uploader("Upload company list", type=["csv", "txt"])

# OpenAI checkbox
use_openai = st.checkbox(
    "Use OpenAI API to auto-fill info (API key required in Streamlit Secrets)", value=True
)

# Function to get company info via OpenAI
def get_company_info(company_name):
    if not use_openai or not st.secrets.get("OPENAI_API_KEY"):
        return {
            "Company": company_name,
            "Founded": "",
            "Employees": "",
            "Revenue": "",
            "Main Products": "",
            "Key Clients": ""
        }
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    prompt = f"""
    Provide the following information for the company "{company_name}" in English. 
    If any information is unknown, leave it blank.
    Respond strictly in JSON format:

    {{
        "Company": "{company_name}",
        "Founded": "...",
        "Employees": "...",
        "Revenue": "...",
        "Main Products": "...",
        "Key Clients": "..."
    }}
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=250,
            temperature=0.2
        )
        content = response['choices'][0]['message']['content']

        # 간단한 JSON 파싱
        content = re.sub(r"(\w+):", r'"\1":', content)
        content = content.replace("'", '"')
        return json.loads(content)
    except:
        return {
            "Company": company_name,
            "Founded": "",
            "Employees": "",
            "Revenue": "",
            "Main Products": "",
            "Key Clients": ""
        }

# Main processing
if uploaded_file:
    # Load company list
    if uploaded_file.type == "text/plain":
        company_list = [line.strip() for line in uploaded_file.read().decode("utf-8").splitlines() if line.strip()]
    else:
        df_in = pd.read_csv(uploaded_file)
        company_list = df_in.iloc[:,0].dropna().astype(str).tolist()
    
    st.info(f"{len(company_list)} companies loaded. Retrieving info (this may take a while)...")

    results = []
    for i, company in enumerate(company_list):
        st.write(f"Processing {i+1}/{len(company_list)}: {company}")
        info = get_company_info(company)
        results.append(info)
    
    df_result = pd.DataFrame(results)
    st.success("✅ Company info retrieval completed!")
    
    st.dataframe(df_result, use_container_width=True)

    # Excel download
    towrite = io.BytesIO()
    df_result.to_excel(towrite, index=False, sheet_name="Company Info")
    towrite.seek(0)
    st.download_button(
        "📥 Download Excel",
        data=towrite,
        file_name="company_info.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
