import streamlit as st
import json
import os
import base64
import textwrap
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Guruhari Ashirwad Knowledge Base",
    page_icon="🙏",
    layout="wide",
    initial_sidebar_state="expanded"
)

INDEX_FILE = "baps_video_index.json"

# Helper to encode images as base64 for reliable HTML embedding
def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            ext = os.path.splitext(image_path)[1].replace('.', '')
            if ext == 'jpg': ext = 'jpeg'
            return f"data:image/{ext};base64,{base64.b64encode(img_file.read()).decode()}"
    return None

# Load image paths
img_mandir = get_base64_image("assets/swami_mandir.jpg")
img_portrait = get_base64_image("assets/swami_portrait_1.png")
img_prarthana = get_base64_image("assets/swami_prarthana.png")
img_meditation = get_base64_image("assets/swami_meditation.png")
img_reading = get_base64_image("assets/swami_reading.png")

# Dynamic / Cached translation function with dual Groq + Gemini fallback
@st.cache_data(show_spinner=False)
def translate_on_the_fly(summary_en):
    if not summary_en: return ""
    # 1. Try Groq
    try:
        from groq import Groq
        keys = [k.strip() for k in os.getenv('GROQ_API_KEYS', '').split(',') if k.strip()]
        if keys:
            for k in keys:
                try:
                    client = Groq(api_key=k)
                    resp = client.chat.completions.create(
                        model='openai/gpt-oss-20b',
                        messages=[{'role': 'user', 'content': f'Translate this spiritual discourse summary into fluent, natural Gujarati. Return ONLY the Gujarati translation text with no English preamble:\n\n{summary_en}'}],
                        temperature=0.1
                    )
                    return resp.choices[0].message.content.strip()
                except:
                    continue
    except Exception:
        pass

    # 2. Try Gemini Fallback
    try:
        from google import genai
        g_keys = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
        if g_keys:
            for gk in g_keys:
                try:
                    client = genai.Client(api_key=gk)
                    resp = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=f'Translate this spiritual discourse summary into fluent, natural Gujarati. Return ONLY the Gujarati translation text:\n\n{summary_en}'
                    )
                    return resp.text.strip()
                except:
                    continue
    except Exception:
        pass

    return summary_en

# Custom CSS for dark spiritual aesthetic, collage, and glassmorphism
st.markdown("""
<style>
/* App background with ambient temple gradient */
.stApp {
    background: radial-gradient(circle at 15% 15%, #1e1b4b 0%, #0b0f19 55%, #05070d 100%);
    color: #f8fafc;
}

/* Headings */
h1, h2, h3, h4 {
    color: #f8fafc !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}

/* Hero Collage Grid */
.hero-collage {
    display: grid;
    grid-template-columns: 1.4fr 1fr 1fr 1fr 1fr;
    gap: 14px;
    margin-bottom: 24px;
    border-radius: 20px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(245, 158, 11, 0.25);
    padding: 14px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
}

.collage-item {
    position: relative;
    border-radius: 14px;
    overflow: hidden;
    height: 220px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
    transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.collage-item:hover {
    transform: translateY(-4px) scale(1.02);
    border-color: #f59e0b;
    box-shadow: 0 12px 28px rgba(245, 158, 11, 0.25);
}

.collage-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: top center;
    transition: transform 0.4s ease;
}

.collage-item:hover img {
    transform: scale(1.05);
}

.collage-caption {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.85) 0%, rgba(0, 0, 0, 0) 100%);
    color: #fbbf24;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 16px 10px 8px 10px;
    text-align: center;
}

/* Video Card Design */
.video-card {
    background: rgba(30, 41, 59, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.video-card:hover {
    border-color: #f59e0b;
    box-shadow: 0 8px 24px rgba(245, 158, 11, 0.18);
    transform: translateY(-2px);
}

/* Category Badge */
.category-badge {
    display: inline-block;
    background: rgba(245, 158, 11, 0.16);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.38);
    border-radius: 9999px;
    padding: 3px 12px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-right: 6px;
    margin-bottom: 6px;
}

/* Summary Box */
.summary-box {
    background: rgba(15, 23, 42, 0.75);
    border-left: 3px solid #f59e0b;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
    font-size: 0.96rem;
    line-height: 1.65;
    color: #e2e8f0;
}

/* YouTube Button */
.watch-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    color: #ffffff !important;
    font-weight: 600;
    padding: 7px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 0.88rem;
    box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3);
    transition: all 0.2s ease;
}

.watch-btn:hover {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    box-shadow: 0 6px 18px rgba(220, 38, 38, 0.45);
    transform: translateY(-1px);
    text-decoration: none;
}
</style>
""", unsafe_allow_html=True)

def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

index_data = load_index()

# Extract unique categories
all_categories = set()
for vid in index_data.values():
    all_categories.update(vid.get('categories', []))
all_categories = sorted(list(all_categories))

# Sidebar Configuration
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/BAPS_Logo.svg/512px-BAPS_Logo.svg.png", width=65)
st.sidebar.title("Ashirwad Archive")
st.sidebar.caption("Continuous Intelligent Indexer & Spiritual Explorer")

st.sidebar.divider()
st.sidebar.header("📊 Archive Statistics")
st.sidebar.metric(label="Total Discourses Indexed", value=len(index_data))
st.sidebar.metric(label="Unique Spiritual Concepts", value=len(all_categories))

gujarati_count = sum(1 for v in index_data.values() if v.get('summary_gu'))
st.sidebar.metric(label="Gujarati Summaries", value=f"{gujarati_count} / {len(index_data)} (Auto-Translates Live!)")

if st.sidebar.button("🔄 Refresh Database", use_container_width=True):
    st.rerun()

st.sidebar.divider()
st.sidebar.header("⚙️ Display Preferences")

# Language Choice
lang_choice = st.sidebar.radio(
    "Summary Language / સારાંશ ભાષા:",
    options=["English", "ગુજરાતી (Gujarati)"],
    index=0
)

# View Mode
summary_display_mode = st.sidebar.radio(
    "Summary View Mode:",
    options=["Expanded (Always Visible)", "Compact (Click to Read)"],
    index=0
)

st.sidebar.divider()
st.sidebar.info(
    "🤖 **24/7 Cloud Engine**\n\n"
    "Continuously scanning playlist for new discourses. Any missed videos are automatically re-indexed."
)

# ----------------- Hero Collage Section -----------------
collage_html = f"""
<div class="hero-collage">
    <div class="collage-item" style="grid-column: span 1;">
        <img src="{img_mandir or ''}" alt="Mahant Swami Maharaj in Mandir" />
        <div class="collage-caption">મંદિર દર્શન • Sarangpur Mandir</div>
    </div>
    <div class="collage-item">
        <img src="{img_portrait or ''}" alt="Mahant Swami Maharaj Portrait" />
        <div class="collage-caption">સ્મિત દર્શન • Divyabhav</div>
    </div>
    <div class="collage-item">
        <img src="{img_prarthana or ''}" alt="Mahant Swami Maharaj Prarthana" />
        <div class="collage-caption">પ્રાર્થના • Deep Devotion</div>
    </div>
    <div class="collage-item">
        <img src="{img_meditation or ''}" alt="Mahant Swami Maharaj Meditation" />
        <div class="collage-caption">ધ્યાન • Spiritual Stillness</div>
    </div>
    <div class="collage-item">
        <img src="{img_reading or ''}" alt="Mahant Swami Maharaj Reading Letters" />
        <div class="collage-caption">સત્સંગ કાળજી • Devotee Care</div>
    </div>
</div>
"""
st.markdown(collage_html, unsafe_allow_html=True)

# Main Title & Description
st.title("🙏 પરમ પૂજ્ય મહંત સ્વામી મહારાજ આશીર્વાદ સંગ્રહ")
st.markdown(
    "An autonomous spiritual knowledge base indexing **1,500+ discourses** by **Guruhari Mahant Swami Maharaj**. "
    "Every discourse is deeply analyzed into core BAPS Akshar-Purushottam virtues."
)

if not index_data:
    st.warning("⚠️ The database is currently empty. The background indexer is active. Click Refresh in a few moments!")
    st.stop()

st.divider()

# Search & Filter Controls
col1, col2 = st.columns([1, 2])
with col1:
    selected_cats = st.multiselect(
        "🏷️ Filter by Spiritual Concept",
        options=all_categories,
        placeholder="e.g. Samp, Ekta, Mahima, Satsang"
    )
with col2:
    search_query = st.text_input(
        "🔍 Search Discourses (English Keywords)",
        placeholder="e.g. youth, unity, London, Paris, forgiveness, seva, katha"
    )

# Filtering logic
results = []
for vid_id, data in index_data.items():
    match_cat = True
    match_text = True
    
    if selected_cats:
        match_cat = any(c in data.get('categories', []) for c in selected_cats)
        
    if search_query:
        q = search_query.lower()
        title_match = q in data.get('title', '').lower()
        summary_en_match = q in data.get('summary', '').lower()
        summary_gu_match = q in data.get('summary_gu', '').lower()
        match_text = title_match or summary_en_match or summary_gu_match
        
    if match_cat and match_text:
        # Keep track of video id
        data_copy = dict(data)
        data_copy['id'] = vid_id
        results.append(data_copy)

# Pagination for snappy browsing
RESULTS_PER_PAGE = 20
total_pages = max(1, (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)

p_col1, p_col2 = st.columns([2, 1])
with p_col1:
    st.write(f"Showing **{len(results)}** discourses matching your criteria")
with p_col2:
    current_page = st.number_input(f"Page (of {total_pages})", min_value=1, max_value=total_pages, value=1, step=1)

start_idx = (current_page - 1) * RESULTS_PER_PAGE
page_results = results[start_idx : start_idx + RESULTS_PER_PAGE]

# Render Results
for res in page_results:
    vid_id = res.get('id', '')
    categories_html = "".join([f'<span class="category-badge">{cat}</span>' for cat in res.get('categories', [])])
    if not categories_html:
        categories_html = '<span class="category-badge" style="color:#94a3b8; border-color:#64748b;">Uncategorized</span>'
        
    is_gujarati = (lang_choice == "ગુજરાતી (Gujarati)")
    
    # Handle Gujarati summary (cached live translation if not yet backfilled)
    if is_gujarati:
        if res.get('summary_gu'):
            summary_text = res['summary_gu']
        else:
            # Dynamically translate on the fly!
            summary_text = translate_on_the_fly(res.get('summary', ''))
            # Save translated version back to the loaded index so it doesn't need to re-fetch
            res['summary_gu'] = summary_text
        lang_badge = "🇮🇳 ગુજરાતી સારાંશ"
    else:
        summary_text = res.get('summary', 'No summary available.')
        lang_badge = "🇬🇧 English Summary"

    thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""

    # Card layout with thumbnail on left, discourse info on right
    card_cols = st.columns([1, 3])
    
    with card_cols[0]:
        if thumbnail_url:
            st.image(thumbnail_url, use_container_width=True)
            
    with card_cols[1]:
        st.markdown(f"""
        <h4 style="margin-top:0; margin-bottom:8px; color:#f8fafc;">
            {res.get('title', 'Untitled Discourse')}
        </h4>
        <div style="margin-bottom: 8px;">
            {categories_html}
        </div>
        """, unsafe_allow_html=True)
        
        if summary_display_mode.startswith("Expanded"):
            st.markdown(f"""
            <div class="summary-box">
                <strong style="color:#fbbf24;">{lang_badge}:</strong><br>
                {summary_text}
            </div>
            """, unsafe_allow_html=True)
        else:
            with st.expander(f"📖 Read {lang_badge} / સારાંશ વાંચો"):
                st.write(summary_text)
                
        st.markdown(f"""
        <div style="margin-top: 8px; margin-bottom: 12px;">
            <a href="{res.get('link', '#')}" target="_blank" class="watch-btn">▶ Watch on YouTube</a>
        </div>
        """, unsafe_allow_html=True)
        
    st.divider()
