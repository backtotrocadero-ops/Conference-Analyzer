import streamlit as st
import io, re
import pandas as pd

try:
    import fitz  # PyMuPDF
except:
    fitz = None

# 언어 감지
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    def detect_lang(s):
        try:
            return detect(s)
        except:
            return "en"
except:
    def detect_lang(s):
        return "en"

# OpenAI 요약
try:
    import openai
    openai_available = True
except:
    openai_available = False

def simple_summary(text, max_words=25):
    words = re.split(r'\s+', text.strip())
    return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")

# PDF 텍스트 추출
def extract_text_from_pdf(uploaded_file):
    data = uploaded_file.read()
    text = ""
    if fitz:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                blocks = page.get_text("blocks")
                for b in blocks:
                    text += b[4].strip() + "\n"
        except:
            text = ""
    return text

# 세션 분석 (사용자 정의 규칙 적용 + 중복 제거 + 2칸 이상 공백 기준)
def parse_sessions_from_text(text):
    # 2칸 이상 공백 기준으로 블록 나누기
    blocks = re.split(r'\s{2,}', text)
    sessions = []
    seen_texts = set()  # 중복 제거용

    current_time = ""
    current_place = ""
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # 중복 제거
        if block in seen_texts:
            continue
        seen_texts.add(block)

        time = ""
        place = ""
        title = ""

        # 1) 숫자로 시작하면 시간
        if re.match(r'^\d{1,2}[:.]\d{2}', block):
            current_time = block
            continue  # 시간만 있으면 다음 블록에서 제목/장소 처리

        # 2) 장소 키워드
        if any(k.lower() in block.lower() for k in ['omega', 'lambda', 'hall']):
            current_place = block

        # 3) 대문자로 시작하면 제목
        if re.match(r'^[A-Z][A-Za-z\s,&\-:]*', block):
            title = block

        # 최소 한 개라도 있으면 세션 추가
        if title or current_time or current_place:
            sessions.append({
                "time": current_time,
                "place": current_place,
                "title": title,
                "text": title if title else block,
                "lang": detect_lang(title if title else block)
            })
            # 제목이 추가되었으면 다음 블록에서는 새로 제목/장소 찾기
            title = ""
    return sessions

def summarize_with_openai(text):
    if not openai_available or not st.secrets.get("OPENAI_API_KEY"):
        return simple_summary(text)
    try:
        openai.api_key = st.secrets["OPENAI_API_KEY"]
        prompt = f"You are a concise assistant. Summarize this in 1 line:\n{text}"
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=120,
            temperature=0.2,
        )
        return resp['choices'][0]['message']['content'].strip()
    except:
        return simple_summary(text)

# --- Streamlit UI ---
st.set_page_config(page_title="Conference PDF Analyzer", layout="wide")
st.title("🗂️ Conference PDF Analyzer")

st.markdown("**사용법**: PDF 업로드 → 관심 키워드 확인 → 분석 시작")

uploaded_file = st.file_uploader("PDF 파일 업로드", type=["pdf"])
keywords_input = st.text_input("관심 키워드 (쉼표로 구분)", value="ammunition, defense, NATO, 탄약, 국방")
use_openai = st.checkbox("OpenAI로 요약 사용 (선택, Streamlit Secrets에 API_KEY 필요)", value=False)

if uploaded_file:
    st.info("PDF 분석 중... 잠시만 기다려 주세요.")
    text = extract_text_from_pdf(uploaded_file)
    if not text.strip():
        st.error("PDF에서 텍스트를 추출하지 못했습니다.")
    else:
        sessions = parse_sessions_from_text(text)
        st.success(f"총 {len(sessions)}개 세션 감지됨")
        keywords = [k.strip().lower() for k in keywords_input.split(",") if k.strip()]
        rows = []
        for s in sessions:
            summary = summarize_with_openai(s['title'] + "\n" + s['text']) if (use_openai and openai_available) else simple_summary(s['title'])
            lang_label = "EN" if s['lang'].startswith("en") else "⚠ Not English"
            score = sum(1 for kw in keywords if kw in (s['title'] + " " + s['text']).lower())
            if score >= 2: priority = "⭐⭐⭐ (강력추천)"
            elif score == 1: priority = "⭐⭐ (추천)"
            else: priority = "⭐ (참고)"
            rows.append({
                "시간": s['time'],
                "장소": s['place'],
                "제목": s['title'],
                "핵심요약": summary,
                "언어": lang_label,
                "우선순위": priority
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        # Excel 다운로드
        towrite = io.BytesIO()
        df.to_excel(towrite, index=False, sheet_name="recommendations")
        towrite.seek(0)
        st.download_button("📥 Excel로 다운로드", data=towrite, file_name="conference_recommendations.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("----")
        st.subheader("상세 리스트")
        for i, r in df.iterrows():
            st.markdown(f"**{i+1}. [{r['우선순위']}] {r['제목']}**  —  {r['시간']} / {r['장소']}  ({r['언어']})")
            st.write(r['핵심요약'])
            st.write("---")
