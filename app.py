# app.py
import streamlit as st
import io, re, pandas as pd

# --- OCR 및 PDF 처리 ---
try:
    import fitz  # PyMuPDF
except:
    fitz = None

try:
    from pdf2image import convert_from_bytes
    import pytesseract
except:
    convert_from_bytes = None
    pytesseract = None

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

# --- PDF 텍스트 추출 ---
def extract_text_from_pdf(uploaded_file):
    data = uploaded_file.read()
    text = ""

    # 1. PyMuPDF 시도
    if fitz:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                text += page.get_text("text") + "\n\n"
        except:
            text = ""

    # 2. 텍스트 부족시 ASCII 필터링
    if len(text.strip()) < 20:
        text = ''.join(chr(c) if 32 <= c <= 126 else ' ' for c in data)

    # 3. pytesseract OCR 시도 (이미지 PDF)
    if len(text.strip()) < 50 and convert_from_bytes and pytesseract:
        try:
            images = convert_from_bytes(data)
            for img in images:
                text += pytesseract.image_to_string(img, lang='eng+kor') + "\n\n"
        except:
            pass

    return text

# --- 세션 분석 ---
def find_time_in_block(block):
    m = re.search(r'(\b\d{1,2}[:.]\d{2}\b\s*[-–—~]\s*\b\d{1,2}[:.]\d{2}\b)', block)
    if m: return m.group(1)
    m2 = re.search(r'(\b\d{1,2}[:.]\d{2}\b)', block)
    return m2.group(1) if m2 else ""

def parse_sessions_from_text(text):
    blocks = re.split(r'\n{2,}', text)
    sessions = []
    for b in blocks:
        b = b.strip()
        if len(b) < 10: continue
        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        title = lines[0] if lines else b[:60]+"..."
        time = find_time_in_block(b)
        lang = detect_lang(b[:300]) if b else "en"
        snippet = b.replace("\n"," ")[:600]
        sessions.append({
            "time": time,
            "title": title,
            "text": snippet,
            "lang": lang
        })
    return sessions

def summarize_with_openai(text):
    if not openai_available:
        return simple_summary(text)
    if not st.secrets.get("OPENAI_API_KEY"):
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
        st.error("PDF에서 텍스트를 추출하지 못했습니다. (이미지 PDF일 경우 OCR 실패)")
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
            st.markdown(f"**{i+1}. [{r['우선순위']}] {r['제목']}**  —  {r['시간']}  ({r['언어']})")
            st.write(r['핵심요약'])
            st.write("---")
