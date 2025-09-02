import io
import re
from collections import Counter

import streamlit as st
from PyPDF2 import PdfReader
from textstat import textstat
from spellchecker import SpellChecker

# --------- Utilities ---------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        texts = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            texts.append(txt)
        return "\n".join(texts).strip()
    except Exception as e:
        return ""

def split_sentences(text: str):
    # simple sentence splitter (no heavy downloads)
    # splits on . ! ? while keeping things light
    text = re.sub(r'\s+', ' ', text)
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

def words(text: str):
    return re.findall(r"[A-Za-z']+", text)

def avg_words_per_sentence(sentences):
    if not sentences:
        return 0.0
    return sum(len(words(s)) for s in sentences) / len(sentences)

def find_long_sentences(sentences, threshold=25):
    issues = []
    for i, s in enumerate(sentences, 1):
        wc = len(words(s))
        if wc > threshold:
            issues.append((i, wc, s))
    return issues

def find_passive_voice(sentences):
    # very light heuristic: be-verb + past participle (ed)
    pattern = re.compile(r'\b(is|are|was|were|be|been|being)\s+\b(\w+ed)\b', re.IGNORECASE)
    issues = []
    for i, s in enumerate(sentences, 1):
        if pattern.search(s):
            issues.append((i, s))
    return issues

def find_adverbs(sentences, suffix='ly', threshold=2):
    # flag sentences with many -ly words
    issues = []
    for i, s in enumerate(sentences, 1):
        count = len([w for w in words(s) if w.lower().endswith(suffix)])
        if count >= threshold:
            issues.append((i, count, s))
    return issues

def find_duplicate_words(text):
    dupes = []
    for m in re.finditer(r'\b(\w+)\s+\1\b', text, flags=re.IGNORECASE):
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + 40)
        context = text[start:end].replace('\n', ' ')
        dupes.append((m.group(1), context))
    return dupes

def find_all_caps_words(text, min_len=5):
    caps = [w for w in re.findall(r'\b[A-Z]{%d,}\b' % min_len, text) if len(w) >= min_len]
    # allow common short acronyms by filtering len < 5 already
    return Counter(caps).most_common(20)

def find_bullets_with_long_lines(text, max_words=20):
    issues = []
    for line in text.splitlines():
        if re.match(r'^\s*([-*•])\s+', line):
            wc = len(words(line))
            if wc > max_words:
                issues.append((wc, line.strip()))
    return issues

def spelling_suggestions(text, max_items=30):
    sp = SpellChecker()
    toks = [w.lower() for w in words(text) if len(w) > 3]
    # Light stopword set to avoid noise
    common = set("""the be to of and a in that have i it for not on with he as you do at this
                    but his by from they we say her she or an will my one all would there their""".split())
    toks = [t for t in toks if t not in common]
    miss = sp.unknown(toks)
    # show suggestion pairs
    pairs = []
    for w in sorted(list(miss))[:max_items]:
        pairs.append((w, sp.correction(w)))
    return pairs

def readability_summary(text):
    try:
        return {
            "Flesch Reading Ease (higher is easier)": round(textstat.flesch_reading_ease(text), 1),
            "Flesch–Kincaid Grade (US school grade)": round(textstat.flesch_kincaid_grade(text), 1),
            "SMOG Index": round(textstat.smog_index(text), 1),
            "Dale–Chall Score": round(textstat.dale_chall_readability_score(text), 2),
            "Words": textstat.lexicon_count(text, removepunct=True),
            "Sentences": textstat.sentence_count(text),
        }
    except Exception:
        return {}

# --------- Streamlit App ---------
st.set_page_config(page_title="PDF Text Suggestions (Free)", page_icon="📄", layout="wide")
st.title("📄 PDF Text Suggestions — Free, local")

st.write("Upload a PDF and get readability and style suggestions (no paid APIs).")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
adv = st.checkbox("Show detailed issues list")

if uploaded is not None:
    pdf_bytes = uploaded.read()
    text = extract_text_from_pdf(pdf_bytes)

    if not text or len(text) < 200:
        st.warning("Couldn’t extract much text. If your PDF is a scanned image, run OCR first (e.g., free Tesseract) and try again.")
    else:
        sentences = split_sentences(text)
        wcount = len(words(text))
        avg_wps = round(avg_words_per_sentence(sentences), 2)

        st.subheader("Quick Summary")
        cols = st.columns(3)
        cols[0].metric("Words", wcount)
        cols[1].metric("Sentences", len(sentences))
        cols[2].metric("Avg words / sentence", avg_wps)

        stats = readability_summary(text)
        if stats:
            st.write("**Readability**")
            st.json(stats)

        # Heuristic checks
        long_sents = find_long_sentences(sentences, threshold=25)
        passive = find_passive_voice(sentences)
        adverbs = find_adverbs(sentences, threshold=3)
        dupes = find_duplicate_words(text)
        caps = find_all_caps_words(text)
        long_bullets = find_bullets_with_long_lines(text)
        spell = spelling_suggestions(text)

        st.subheader("Top Suggestions")
        suggestions = []

        if stats and stats.get("Flesch Reading Ease (higher is easier)", 100) < 60:
            suggestions.append("Improve readability: use shorter sentences and simpler words (Flesch score < 60).")
        if avg_wps > 20:
            suggestions.append("Shorten sentences: aim for ~14–20 words per sentence on average.")
        if len(long_sents) >= 3:
            suggestions.append(f"Break up long sentences: found {len(long_sents)} sentences over 25 words.")
        if len(passive) >= 3:
            suggestions.append(f"Reduce passive voice: found {len(passive)} likely cases.")
        if len(adverbs) >= 3:
            suggestions.append(f"Trim adverbs (-ly): {len(adverbs)} sentences have many adverbs.")
        if len(spell) >= 5:
            suggestions.append(f"Fix spelling: at least {len(spell)} possible misspellings.")
        if len(long_bullets) >= 1:
            suggestions.append(f"Tighten bullet points: {len(long_bullets)} bullets exceed {20} words.")

        if not suggestions:
            suggestions.append("Looks good! No major issues detected by the basic checks.")

        for s in suggestions:
            st.write("• " + s)

        if adv:
            st.divider()
            st.subheader("Detailed Issues")

            with st.expander("Long sentences (> 25 words)"):
                for i, wc, s in long_sents[:50]:
                    st.write(f"**#{i}** ({wc} words): {s}")

            with st.expander("Likely passive voice"):
                for i, s in passive[:50]:
                    st.write(f"**#{i}**: {s}")

            with st.expander("Adverb-heavy sentences (-ly)"):
                for i, count, s in adverbs[:50]:
                    st.write(f"**#{i}** ({count} adverbs): {s}")

            with st.expander("Consecutive duplicate words"):
                for w, ctx in dupes[:50]:
                    st.write(f"‘{w} {w}’ … **context:** {ctx}")

            with st.expander("All-CAPS words (possible shouting/jargon)"):
                if caps:
                    for w, c in caps:
                        st.write(f"{w} × {c}")
                else:
                    st.write("None found.")

            with st.expander("Long bullet points (> 20 words)"):
                for wc, line in long_bullets[:50]:
                    st.write(f"({wc} words) {line}")

            with st.expander("Possible misspellings (suggestions)"):
                if spell:
                    for wrong, corr in spell:
                        st.write(f"{wrong} → *{corr}*")
                else:
                    st.write("None found.")

        # Optional: quick markdown report for download
        report_lines = ["# PDF Suggestions Report"]
        for s in suggestions:
            report_lines.append(f"- {s}")
        report = "\n".join(report_lines)
        st.download_button("Download summary report (.md)", report, file_name="pdf_suggestions_report.md", mime="text/markdown")
