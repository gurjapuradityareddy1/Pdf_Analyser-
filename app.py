import streamlit as st
import PyPDF2
import textstat
import re

st.set_page_config(
    page_title="PDF Suggester 🎉",
    page_icon="📄",
    layout="centered"
)

# Add a fun banner
st.image("https://www.shutterstock.com/image-vector/man-talk-recruitment-team-interview-260nw-2218243563.jpg", use_container_width=True)

st.title("📄 PDF Suggester 🤖✨")
st.markdown("Upload a PDF and let our *friendly robot* suggest improvements 🐱‍👤")

uploaded_file = st.file_uploader("👉 Drop your PDF here", type="pdf")

if uploaded_file is not None:
    # Extract text
    reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    
    st.subheader("📚 Extracted Text")
    st.write(text[:500] + "...")  # Show first 500 chars
    
    # Readability
    score = textstat.flesch_reading_ease(text)
    st.subheader("📊 Readability Score")
    st.metric("Flesch Reading Ease", f"{score:.2f}")
    
    # Issues
    st.subheader("⚠️ Suggested Fixes")
    issues = []
    if score < 50:
        issues.append("Your text is *too complex*. Try using shorter sentences.")
    if re.search(r"\b(very|really|just|basically)\b", text):
        issues.append("Too many filler words like *very/really*. Keep it sharp!")
    if re.search(r"\b(is|was|were|be|been|being)\b\s+\w+ed", text):
        issues.append("Detected **passive voice**. Use active voice instead.")
    
    if issues:
        for i, issue in enumerate(issues, 1):
            st.write(f"🐱‍🏍 **Tip {i}:** {issue}")
    else:
        st.success("🎉 Looks great! No major issues found.")
    
    st.image("https://media.giphy.com/media/3oEjI6SIIHBdRxXI40/giphy.gif")
