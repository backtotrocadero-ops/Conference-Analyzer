import streamlit as st
import pandas as pd
import io
import openai

st.set_page_config(page_title="Company Info Analyzer", layout="wide")
st.title("🏢 Company Info Analyzer")

st.markdown("Upload a CSV or TXT file containing a list of company names, one per line.")

# 파일 업로드
uploaded_file = st.file_uploader("Upload company list", type=["csv", "txt"])

# OpenAI 요약 옵션
use_openai = st.checkbox("Use OpenAI for info summary (API key required in Streamlit Secrets)", value=True)

# 함수: OpenAI로 회사 정보 조회
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
    Respond in JSON format:
    {{
        "Company": "{company_name}",
        "Founded": "...",
        "Employees": "...",
        "Revenue": "...",
        "Main Products": "...",
        "Key Clients": "..."
    }}
    Only use official/public sources.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=250,
            temperature=0.2
        )
        content = response['choices'][0]['message']['content']
        # JSON-like parsing
        import json, re
        content = re.sub(r"(\w+):", r'"\1":', content)  # 간단 치환
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

# 메인 처리
if uploaded_file:
    # 회사명 리스트 불러오기
    if uploaded_file.type == "text/plain":
        company_list = [line.strip() for line in uploaded_file.read().decode("utf-8").splitlines() if line.strip()]
    else:
        df_in = pd.read_csv(uploaded_file)
        # CSV가 한 컬럼만 있는 경우
        company_list = df_in.iloc[:,0].dropna().astype(str).tolist()
    
    st.info(f"{len(company_list)} companies loaded. Retrieving info... This may take some time.")
    
    results = []
    for i, company in enumerate(company_list):
        st.write(f"Processing {i+1}/{len(company_list)}: {company}")
        info = get_company_info(company)
        results.append(info)
    
    df_result = pd.DataFrame(results)
    st.success("✅ Company info retrieval completed!")
    
    st.dataframe(df_result, use_container_width=True)
    
    # Excel 다운로드
    towrite = io.BytesIO()
    df_result.to_excel(towrite, index=False, sheet_name="Company Info")
    towrite.seek(0)
    st.download_button("📥 Download Excel", data=towrite, file_name="company_info.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
