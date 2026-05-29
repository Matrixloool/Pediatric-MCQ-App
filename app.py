import streamlit as st
import os
import json
import logging
from typing import Dict, Any, List

# Import our custom processors
from pdf_processor import extract_text_from_multiple_pdfs, get_combined_outline_text
from gemini_client import GeminiStudyClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROGRESS_FILE = "progress.json"

# Set up page config
st.set_page_config(
    page_title="Pediatric Board MCQ Study Companion",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# 1. Slate-Dark Clinical CSS Styling
# ----------------------------------------------------
st.markdown("""
<style>
    /* Global Page Styling */
    .stApp {
        background-color: #0F172A;
    }
    
    /* Elegant Sidebar Theme */
    [data-testid="stSidebar"] {
        background-color: #1E293B !important;
        border-right: 1px solid #334155;
    }
    
    /* Premium Header */
    .app-title {
        background: linear-gradient(135deg, #0D9488 0%, #0284C7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.3rem;
        margin-bottom: 2px;
        padding-bottom: 5px;
    }
    .app-subtitle {
        color: #94A3B8;
        font-size: 1.05rem;
        margin-bottom: 25px;
        font-weight: 400;
    }
    
    /* Study Question Card */
    .question-container {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 26px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        margin-bottom: 20px;
    }
    .question-vignette {
        color: #F8FAFC;
        font-size: 1.15rem;
        font-weight: 600;
        line-height: 1.6;
        margin-bottom: 20px;
    }
    
    /* Option Styling Customizations */
    .stRadio [data-testid="stWidgetLabel"] {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }
    
    /* Glassmorphism Explanation Box */
    .explanation-container {
        background-color: rgba(15, 23, 42, 0.65);
        border: 1px solid #0D9488;
        border-left: 6px solid #0D9488;
        border-radius: 12px;
        padding: 20px;
        margin-top: 20px;
    }
    .explanation-title {
        color: #0D9488;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
    }
    .explanation-text {
        color: #E2E8F0;
        font-size: 0.98rem;
        line-height: 1.55;
    }
    
    /* Sidebar Navigation Timeline Stepper */
    .timeline-title {
        color: #94A3B8;
        font-weight: 700;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 25px;
        margin-bottom: 12px;
    }
    .timeline-container {
        border-left: 2px solid #334155;
        margin-left: 8px;
        padding-left: 15px;
    }
    .timeline-item {
        position: relative;
        padding-bottom: 20px;
    }
    .timeline-item::before {
        content: '';
        position: absolute;
        left: -22px;
        top: 4px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: #334155;
        border: 2px solid #1E293B;
    }
    .timeline-item.active::before {
        background-color: #0D9488;
        box-shadow: 0 0 8px #0D9488;
        border-color: #0F172A;
    }
    .timeline-item.completed::before {
        background-color: #10B981;
        border-color: #0F172A;
    }
    .timeline-item-title {
        font-size: 0.9rem;
        color: #94A3B8;
    }
    .timeline-item-title.active {
        color: #F8FAFC;
        font-weight: 700;
    }
    .timeline-item-title.completed {
        color: #10B981;
        text-decoration: line-through;
        opacity: 0.8;
    }
    
    /* Navigation row buttons */
    .nav-btn {
        margin-right: 10px;
    }
    
    /* Premium Stats Dashboard */
    .stats-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
    }
    .stats-val {
        font-size: 1.8rem;
        font-weight: 800;
        color: #0D9488;
    }
    .stats-lbl {
        color: #94A3B8;
        font-size: 0.8rem;
        text-transform: uppercase;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 2. Defensive Cloud Sync Credentials Check
# ----------------------------------------------------
is_gsheets_configured = False
try:
    # Safely check Streamlit secrets without crashing if empty/absent
    if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        if "spreadsheet" in st.secrets["connections"]["gsheets"]:
            is_gsheets_configured = True
except Exception:
    is_gsheets_configured = False

# ----------------------------------------------------
# 3. Persistent State Loader & Saver (Local + Cloud)
# ----------------------------------------------------
def save_progress():
    """
    Saves current study state to a local progress.json file AND Google Sheets (if configured).
    """
    state_to_save = {
        "filenames": st.session_state.get("filenames", []),
        "all_pdfs_data": st.session_state.get("all_pdfs_data", {}),
        "outline_text": st.session_state.get("outline_text", ""),
        "topics": st.session_state.get("topics", []),
        "current_topic_index": st.session_state.get("current_topic_index", 0),
        "mcqs": st.session_state.get("mcqs", {}),
        "user_answers": st.session_state.get("user_answers", {}),
        "num_mcqs_per_topic": st.session_state.get("num_mcqs_per_topic", 5),
        "api_key": st.session_state.get("api_key", "")
    }
    
    # 1. Save Locally
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(state_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save progress locally: {str(e)}")
        
    # 2. Sync to Google Sheets if configured
    if is_gsheets_configured:
        try:
            import pandas as pd
            from streamlit_gsheets import GSheetsConnection
            
            # Structure a clean data row to write to Sheets (preserving cell space constraints)
            sheet_data = {
                "user_id": ["pediatric_study"],
                "filenames": [json.dumps(st.session_state.get("filenames", []))],
                "topics": [json.dumps(st.session_state.get("topics", []))],
                "current_topic_index": [int(st.session_state.get("current_topic_index", 0))],
                "mcqs": [json.dumps(st.session_state.get("mcqs", {}))],
                "user_answers": [json.dumps(st.session_state.get("user_answers", {}))],
                "num_mcqs_per_topic": [int(st.session_state.get("num_mcqs_per_topic", 5))],
                "api_key": [st.session_state.get("api_key", "")],
                "last_updated": [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")]
            }
            df = pd.DataFrame(sheet_data)
            
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(worksheet="Sheet1", data=df)
            logger.info("Successfully updated study progress in Google Sheets!")
        except Exception as e:
            logger.error(f"Failed to save progress to Google Sheets: {str(e)}")

def load_progress() -> bool:
    """
    Loads persistent study state. Prioritizes Google Sheets cloud sync, otherwise falls back to progress.json.
    Returns True if successfully restored, otherwise False.
    """
    # 1. Prioritize Google Sheets
    if is_gsheets_configured:
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)
            # ttl="0s" ensures we bypass local caching and fetch the absolute latest version!
            df = conn.read(worksheet="Sheet1", ttl="0s")
            if df is not None and not df.empty:
                row = df.iloc[0]
                
                # Deserialization from Sheet
                st.session_state["filenames"] = json.loads(row.get("filenames", "[]"))
                st.session_state["topics"] = json.loads(row.get("topics", "[]"))
                st.session_state["current_topic_index"] = int(row.get("current_topic_index", 0))
                st.session_state["mcqs"] = json.loads(row.get("mcqs", "{}"))
                st.session_state["user_answers"] = json.loads(row.get("user_answers", "{}"))
                st.session_state["num_mcqs_per_topic"] = int(row.get("num_mcqs_per_topic", 5))
                
                # Restore API Key if empty in state
                sheet_api_key = row.get("api_key", "")
                if sheet_api_key and ("api_key" not in st.session_state or not st.session_state["api_key"]):
                    st.session_state["api_key"] = sheet_api_key
                    
                logger.info("Successfully restored progress from Google Sheets!")
                return True
        except Exception as e:
            logger.error(f"Failed to load progress from Google Sheets: {str(e)}")
            st.warning("⚠️ Google Sheets Cloud Sync failed. Attempting local resume...")
            
    # 2. Local Fallback
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state["filenames"] = data.get("filenames", [])
            st.session_state["all_pdfs_data"] = data.get("all_pdfs_data", {})
            st.session_state["outline_text"] = data.get("outline_text", "")
            st.session_state["topics"] = data.get("topics", [])
            st.session_state["current_topic_index"] = data.get("current_topic_index", 0)
            st.session_state["mcqs"] = data.get("mcqs", {})
            st.session_state["user_answers"] = data.get("user_answers", {})
            st.session_state["num_mcqs_per_topic"] = data.get("num_mcqs_per_topic", 5)
            if "api_key" not in st.session_state or not st.session_state["api_key"]:
                st.session_state["api_key"] = data.get("api_key", "")
            logger.info("Successfully loaded progress from local progress.json!")
            return True
        except Exception as e:
            logger.error(f"Failed to load local progress: {str(e)}")
            
    return False

def reset_all_progress():
    """
    Deletes the local progress file, resets Google Sheets (if configured), and clears the Session State.
    """
    if os.path.exists(PROGRESS_FILE):
        try:
            os.remove(PROGRESS_FILE)
        except Exception as e:
            logger.error(f"Failed to remove progress file: {str(e)}")
            
    if is_gsheets_configured:
        try:
            from streamlit_gsheets import GSheetsConnection
            import pandas as pd
            # Overwrite with empty dataframe matching the schema
            empty_df = pd.DataFrame(columns=[
                "user_id", "filenames", "topics", "current_topic_index",
                "mcqs", "user_answers", "num_mcqs_per_topic", "api_key", "last_updated"
            ])
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(worksheet="Sheet1", data=empty_df)
            logger.info("Successfully cleared study progress in Google Sheets!")
        except Exception as e:
            logger.error(f"Failed to reset Google Sheets progress: {str(e)}")
            
    # Clear session state keys
    keys_to_clear = [
        "filenames", "all_pdfs_data", "outline_text", 
        "topics", "current_topic_index", "mcqs", 
        "user_answers", "current_q_idx"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ----------------------------------------------------
# 4. Session State Initializations
# ----------------------------------------------------
if "filenames" not in st.session_state:
    # Attempt to load from sheets/local progress first
    if not load_progress():
        # Set standard defaults if no progress exists
        st.session_state["filenames"] = []
        st.session_state["all_pdfs_data"] = {}
        st.session_state["outline_text"] = ""
        st.session_state["topics"] = []
        st.session_state["current_topic_index"] = 0
        st.session_state["mcqs"] = {}
        st.session_state["user_answers"] = {}
        st.session_state["num_mcqs_per_topic"] = 5

if "current_q_idx" not in st.session_state:
    st.session_state["current_q_idx"] = 0

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

# ----------------------------------------------------
# 5. Sidebar Elements & Configuration
# ----------------------------------------------------
with st.sidebar:
    st.markdown('<div class="app-title">👶 PedMCQ Study</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Pediatric Board Review Companion</div>', unsafe_allow_html=True)
    
    st.subheader("1. API Key & Settings")
    api_key_input = st.text_input(
        "Gemini API Key", 
        value=st.session_state["api_key"], 
        type="password",
        help="Get an API key from Google AI Studio. It will be saved securely in your session and local progress.json."
    )
    if api_key_input != st.session_state["api_key"]:
        st.session_state["api_key"] = api_key_input
        save_progress()
        
    model_choice = st.selectbox(
        "Gemini Model",
        options=["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        index=0,
        help="gemini-2.5-flash is highly recommended for speed and structured output conformity."
    )
    
    num_qs_choice = st.slider(
        "Default MCQs per batch",
        min_value=3,
        max_value=15,
        value=st.session_state["num_mcqs_per_topic"],
        step=1,
        help="Select the default number of verbatim questions to extract for each sub-topic."
    )
    if num_qs_choice != st.session_state["num_mcqs_per_topic"]:
        st.session_state["num_mcqs_per_topic"] = num_qs_choice
        save_progress()
        
    st.markdown("---")
    
    st.subheader("2. Upload Chapter PDF(s)")
    uploaded_files = st.file_uploader(
        "Upload one or multiple textbook PDFs containing MCQ chapters",
        type=["pdf"],
        accept_multiple_files=True
    )
    
    # Process PDF action button
    if uploaded_files:
        current_uploaded_names = [f.name for f in uploaded_files]
        # Check if the uploaded files are different from the ones currently processed
        files_changed = set(current_uploaded_names) != set(st.session_state["filenames"])
        
        btn_label = "Re-process Chapter PDFs" if not files_changed and st.session_state["topics"] else "Process Chapter PDFs"
        
        if st.button(btn_label, type="primary", use_container_width=True):
            if not st.session_state["api_key"]:
                st.error("Please enter a valid Gemini API Key in the settings first!")
            else:
                with st.spinner("Analyzing and parsing PDF contents..."):
                    try:
                        # Extract text
                        all_pdfs_data = extract_text_from_multiple_pdfs(uploaded_files)
                        st.session_state["all_pdfs_data"] = all_pdfs_data
                        st.session_state["filenames"] = current_uploaded_names
                        
                        # Generate outline text for Gemini
                        outline_text = get_combined_outline_text(all_pdfs_data)
                        st.session_state["outline_text"] = outline_text
                        
                        # Call Gemini to extract study topics
                        st.info("Extracting logical study subtopics using Gemini...")
                        client = GeminiStudyClient(
                            api_key=st.session_state["api_key"], 
                            model_name=model_choice
                        )
                        topics = client.extract_subtopics(outline_text)
                        
                        st.session_state["topics"] = topics
                        st.session_state["current_topic_index"] = 0
                        st.session_state["mcqs"] = {}
                        st.session_state["user_answers"] = {}
                        st.session_state["current_q_idx"] = 0
                        
                        save_progress()
                        st.success("Successfully analyzed chapter and extracted study track!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error processing files: {str(e)}")
                        
    if st.session_state["topics"]:
        st.markdown("---")
        st.subheader("Study Session Progress")
        
        # ----------------------------------------------------
        # Visual Interactive Sidebar Stepper
        # ----------------------------------------------------
        st.markdown('<div class="timeline-title">Chapter Outline</div>', unsafe_allow_html=True)
        st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
        for idx, topic in enumerate(st.session_state["topics"]):
            is_active = (idx == st.session_state["current_topic_index"])
            is_completed = (idx < st.session_state["current_topic_index"])
            
            c_class = "active" if is_active else ("completed" if is_completed else "locked")
            t_class = "active" if is_active else ("completed" if is_completed else "")
            
            # Show interactive links for completed or active topics
            if is_completed or is_active:
                if st.button(
                    f"{'✅' if is_completed else '🟢'} {topic}",
                    key=f"stepper_btn_{idx}",
                    use_container_width=True,
                    help=f"Jump to {topic}"
                ):
                    st.session_state["current_topic_index"] = idx
                    st.session_state["current_q_idx"] = 0
                    save_progress()
                    st.rerun()
            else:
                st.markdown(f"""
                <div class="timeline-item {c_class}">
                    <div class="timeline-item-title {t_class}">🔒 {topic}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("Reset Chapter & Clear Progress", type="secondary", use_container_width=True):
            reset_all_progress()

    # ----------------------------------------------------
    # Google Sheets Connection Status Widget in Sidebar
    # ----------------------------------------------------
    st.markdown("---")
    st.subheader("☁️ Cloud Sync Status")
    
    if is_gsheets_configured:
        st.markdown("""
        <div style="background-color: rgba(16, 185, 129, 0.1); border: 1px solid #10B981; border-radius: 8px; padding: 12px; margin-bottom: 5px;">
            <div style="color: #10B981; font-weight: 700; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;">
                🟢 Sync: Google Sheets
            </div>
            <div style="color: #94A3B8; font-size: 0.8rem; margin-top: 4px;">
                Progress is safely mirrored to your Google Drive!
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: rgba(245, 158, 11, 0.1); border: 1px solid #F59E0B; border-radius: 8px; padding: 12px; margin-bottom: 5px;">
            <div style="color: #F59E0B; font-weight: 700; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;">
                🟡 Sync: Local Offline
            </div>
            <div style="color: #94A3B8; font-size: 0.8rem; margin-top: 4px;">
                Local storage only. Click below to configure Google Sheets sync.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🔑 How to Set up Cloud Sync"):
            st.markdown("""
            To sync progress securely to your personal Google Sheet:
            
            **1. Create Google Sheet**
            Create an empty sheet in Google Drive. Share it with your service account email as **Editor**.
            
            **2. Share credentials**
            Paste service account JSON credentials inside the Streamlit Cloud Dashboard secrets or in a local `.streamlit/secrets.toml` file:
            ```toml
            [connections.gsheets]
            spreadsheet = "YOUR_SPREADSHEET_URL"
            type = "service_account"
            project_id = "..."
            private_key_id = "..."
            private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
            client_email = "..."
            # ... paste rest of key details
            ```
            """)

# ----------------------------------------------------
# 6. Main Study Workspace Area
# ----------------------------------------------------
# A. ONBOARDING LANDING PAGE (Empty State)
if not st.session_state["topics"]:
    st.markdown("""
    <div style="background-color: #1E293B; padding: 40px; border-radius: 16px; border: 1px solid #334155; margin-top: 20px;">
        <h1 style="color: #F8FAFC; margin-bottom: 10px; font-weight: 800;">👨‍⚕️ Welcome to Pediatric MCQ Study Companion</h1>
        <p style="color: #94A3B8; font-size: 1.15rem; margin-bottom: 30px;">
            An expert, high-yield educational desktop study tool that extracts verbatim textbook MCQs page-by-page.
        </p>
        
        <h3 style="color: #F8FAFC; margin-bottom: 20px; font-weight: 700;">How to Get Started:</h3>
        <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px;">
            <div style="flex: 1; min-width: 250px; background-color: #0F172A; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                <div style="font-size: 1.8rem; margin-bottom: 8px;">🔑</div>
                <h4 style="color: #0D9488; margin-top: 0;">1. Enter API Key</h4>
                <p style="color: #E2E8F0; font-size: 0.9rem; margin-bottom: 0;">
                    Input your Google Gemini API Key in the sidebar settings. Your key is securely handled locally.
                </p>
            </div>
            <div style="flex: 1; min-width: 250px; background-color: #0F172A; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                <div style="font-size: 1.8rem; margin-bottom: 8px;">📁</div>
                <h4 style="color: #0D9488; margin-top: 0;">2. Upload Textbook PDFs</h4>
                <p style="color: #E2E8F0; font-size: 0.9rem; margin-bottom: 0;">
                    Upload textbook chapters containing MCQs. The app is set up to parse and read these questions word-for-word.
                </p>
            </div>
            <div style="flex: 1; min-width: 250px; background-color: #0F172A; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                <div style="font-size: 1.8rem; margin-bottom: 8px;">🔍</div>
                <h4 style="color: #0D9488; margin-top: 0;">3. Extract & Study Verbatim</h4>
                <p style="color: #E2E8F0; font-size: 0.9rem; margin-bottom: 0;">
                    Click "Process Chapter PDFs". Gemini will map out subtopics and let you extract exact verbatim questions with customized batches!
                </p>
            </div>
        </div>
        
        <div style="background-color: rgba(13, 148, 136, 0.1); border-left: 4px solid #0D9488; padding: 15px; border-radius: 4px;">
            <strong style="color: #0D9488;">💾 Cross-Device Cloud Sync Enabled</strong><br>
            <span style="color: #E2E8F0; font-size: 0.92rem;">
                When Google Sheets is configured, your progress syncs instantly! 
                <strong>This means you can extract questions on your desktop, shut down your computer, and resume studying on your mobile phone!</strong>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# B. ACTIVE STUDY SPACE
else:
    topics = st.session_state["topics"]
    current_topic_idx = st.session_state["current_topic_index"]
    
    # Check if the study track is completely finished
    if current_topic_idx >= len(topics):
        st.balloons()
        st.markdown("""
        <div style="background-color: #1E293B; padding: 40px; border-radius: 16px; border: 1px solid #334155; text-align: center; max-width: 800px; margin: 0 auto; margin-top: 30px;">
            <h1 style="color: #10B981; font-weight: 800; margin-bottom: 10px;">🏆 Congratulations!</h1>
            <h3 style="color: #F8FAFC; margin-bottom: 25px;">You have successfully completed the MCQ Chapter Study</h3>
            <p style="color: #94A3B8; font-size: 1.1rem; margin-bottom: 35px;">
                You've completed all topics in this session. Let's look at your Board Readiness Summary metrics below:
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Calculate summary scores
        total_questions = 0
        total_correct = 0
        
        for topic in topics:
            mcqs_list = st.session_state["mcqs"].get(topic, [])
            ans_dict = st.session_state["user_answers"].get(topic, {})
            total_questions += len(mcqs_list)
            for q_idx in range(len(mcqs_list)):
                ans_state = ans_dict.get(str(q_idx), {})
                if ans_state.get("checked", False):
                    selected = ans_state.get("selected", "")
                    correct = mcqs_list[q_idx]["correct_answer"]
                    if selected == correct:
                        total_correct += 1
                        
        score_pct = (total_correct / total_questions * 100) if total_questions > 0 else 0
        
        # Display scorecard
        st.write("")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-val">{total_questions}</div>
                <div class="stats-lbl">Total MCQs Evaluated</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-val" style="color: #10B981;">{total_correct}</div>
                <div class="stats-lbl">Questions Correct</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            color = "#10B981" if score_pct >= 75 else ("#F59E0B" if score_pct >= 60 else "#EF4444")
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-val" style="color: {color};">{score_pct:.1f}%</div>
                <div class="stats-lbl">Overall Chapter Score</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.write("")
        # Board Readiness Assessment
        if score_pct >= 80:
            st.success("🌟 **Pediatric Board Readiness: EXCELLENT** — You show masterful clinical knowledge in these chapter concepts!")
        elif score_pct >= 70:
            st.info("📈 **Pediatric Board Readiness: PROFICIENT** — Strong knowledge. Review the minor explanations for the distractors to push past 80%!")
        else:
            st.warning("⚠️ **Pediatric Board Readiness: DEVELOPING** — We suggest reviewing the PDF chapter notes once more and resetting progress to re-test your conceptual grasp.")
            
        st.write("")
        if st.button("Reset Chapter Progress and Study Again", type="primary"):
            st.session_state["current_topic_index"] = 0
            st.session_state["current_q_idx"] = 0
            st.session_state["user_answers"] = {}
            save_progress()
            st.rerun()
            
    else:
        # Active Topic Workspace
        active_topic = topics[current_topic_idx]
        
        # ----------------------------------------------------
        # Visual Progress Tracker Header
        # ----------------------------------------------------
        progress_pct = current_topic_idx / len(topics)
        
        col_hdr, col_prog = st.columns([2, 3])
        with col_hdr:
            st.markdown(f'<div class="app-title" style="font-size: 1.8rem;">📖 Study Track</div>', unsafe_allow_html=True)
        with col_prog:
            st.markdown(
                f"<div style='text-align: right; color: #94A3B8; font-size: 0.9rem; font-weight: 600; margin-bottom: 2px;'>"
                f"Chapter Study Progress: {current_topic_idx} / {len(topics)} Topics Completed ({progress_pct*100:.0f}%)"
                f"</div>",
                unsafe_allow_html=True
            )
            st.progress(progress_pct)
            
        st.markdown("---")
        
        # ----------------------------------------------------
        # Skip Topic Feature Integration
        # ----------------------------------------------------
        col_t_title, col_t_skip = st.columns([3, 1])
        with col_t_title:
            st.markdown(f"""
            <div style="background-color: #1E293B; padding: 15px 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 20px;">
                <span style="color: #0D9488; font-weight: 700; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.05em;">Active Sub-topic</span>
                <h3 style="color: #F8FAFC; margin: 0; font-weight: 700;">{active_topic}</h3>
            </div>
            """, unsafe_allow_html=True)
        with col_t_skip:
            st.write("")
            st.write("")
            if st.button("⏭️ Skip Topic", key="skip_topic_btn", type="secondary", use_container_width=True, help="Instantly mark this topic as completed and advance to the next one."):
                st.session_state["current_topic_index"] = current_topic_idx + 1
                st.session_state["current_q_idx"] = 0
                save_progress()
                st.success("Topic marked as completed/skipped.")
                st.rerun()

        # Check if MCQs are loaded for this sub-topic
        if active_topic not in st.session_state["mcqs"] or not st.session_state["mcqs"][active_topic]:
            st.markdown(f"""
            <div style="background-color: #1E293B; padding: 30px; border-radius: 12px; border: 1px solid #334155; text-align: center; margin-top: 15px;">
                <h3 style="color: #F8FAFC; margin-bottom: 12px;">🌟 Topic Selected: <span style="color: #0D9488;">{active_topic}</span></h3>
                <p style="color: #94A3B8; font-size: 1rem; margin-bottom: 20px; max-width: 600px; margin-left: auto; margin-right: auto;">
                    We will extract existing, verbatim (word-for-word) multiple-choice questions belonging to this sub-topic directly from your textbook PDF.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Dynamic count selector before extraction
            batch_count = st.slider(
                "Select how many verbatim MCQs to extract for this batch:",
                min_value=1,
                max_value=20,
                value=st.session_state["num_mcqs_per_topic"],
                step=1,
                key=f"batch_slider_{current_topic_idx}"
            )
            
            # Helper message if PDF text is missing (resuming on mobile)
            is_pdf_available = bool(st.session_state["outline_text"])
            if not is_pdf_available:
                st.warning("⚠️ **PDF Text Context Missing**: You are currently studying synced cloud questions. To extract *new* questions, please re-upload your chapter PDF in the sidebar first.")
                
            if st.button("Extract Verbatim MCQs 🔍", type="primary", use_container_width=True, disabled=not is_pdf_available):
                with st.spinner(f"Gemini is parsing and extracting {batch_count} verbatim MCQs for '{active_topic}'..."):
                    try:
                        client = GeminiStudyClient(
                            api_key=st.session_state["api_key"],
                            model_name=model_choice
                        )
                        chapter_context = st.session_state["outline_text"]
                        mcqs = client.extract_verbatim_mcqs(
                            subtopic=active_topic,
                            chapter_context=chapter_context,
                            num_questions=batch_count
                        )
                        if mcqs:
                            st.session_state["mcqs"][active_topic] = mcqs
                            st.session_state["current_q_idx"] = 0
                            save_progress()
                            st.success(f"Extracted {len(mcqs)} questions successfully!")
                            st.rerun()
                        else:
                            st.warning("No questions found matching this subtopic in textbook. Try another topic.")
                    except Exception as e:
                        st.error(f"Failed to extract questions: {str(e)}")
        
        else:
            # Questions are loaded
            mcqs_list = st.session_state["mcqs"][active_topic]
            q_idx = st.session_state["current_q_idx"]
            
            # Bounds safety
            if q_idx >= len(mcqs_list):
                q_idx = len(mcqs_list) - 1
                st.session_state["current_q_idx"] = q_idx
                save_progress()
                
            current_mcq = mcqs_list[q_idx]
            
            # Display Sub-topic workspace header
            st.markdown(f"""
            <div style="background-color: #1E293B; padding: 15px 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.05em;">Verbatim Study Workspace</span>
                    <h4 style="color: #F8FAFC; margin: 0; font-weight: 700;">{active_topic}</h4>
                </div>
                <div style="text-align: right;">
                    <span style="color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 0.8rem;">Batch Question</span>
                    <h3 style="color: #0D9488; margin: 0; font-weight: 800;">{q_idx + 1} / {len(mcqs_list)}</h3>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Progress bar for this specific topic questions
            st.progress((q_idx + 1) / len(mcqs_list))
            st.write("")
            
            # ----------------------------------------------------
            # Question Card UI
            # ----------------------------------------------------
            st.markdown('<div class="question-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="question-vignette">{q_idx + 1}. {current_mcq["question"]}</div>', unsafe_allow_html=True)
            
            # Fetch user answer state
            topic_answers = st.session_state["user_answers"].setdefault(active_topic, {})
            ans_state = topic_answers.setdefault(str(q_idx), {"selected": None, "checked": False})
            selected_option = ans_state["selected"]
            checked = ans_state["checked"]
            
            # Option presentation
            options_dict = current_mcq["options"]
            options_list = []
            
            # Filter out 'N/A' options dynamically
            valid_keys = ["A", "B", "C", "D", "E"]
            for k in valid_keys:
                opt_val = options_dict.get(k, "")
                if opt_val and opt_val.strip().upper() != "N/A":
                    options_list.append(f"{k}. {opt_val}")
            
            # We determine the index to select
            selected_radio_index = None
            if selected_option:
                # Find matching index
                for i, opt in enumerate(options_list):
                    if opt.startswith(selected_option):
                        selected_radio_index = i
                        break
                        
            # Render options using Streamlit Radio
            radio_key = f"radio_{active_topic.replace(' ', '_')}_{q_idx}"
            user_choice = st.radio(
                "Choose the single most appropriate management or diagnosis:",
                options=options_list,
                index=selected_radio_index,
                key=radio_key,
                disabled=checked
            )
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Interaction buttons
            col_actions_1, col_actions_2 = st.columns([1, 4])
            with col_actions_1:
                if not checked:
                    if st.button("Check Answer ✔️", type="primary", use_container_width=True):
                        if user_choice is None:
                            st.warning("Please select an option first!")
                        else:
                            # Extract selection letter
                            choice_letter = user_choice[0]
                            ans_state["selected"] = choice_letter
                            ans_state["checked"] = True
                            save_progress()
                            st.rerun()
                else:
                    st.button("Answer Checked 🔒", disabled=True, use_container_width=True)
                    
            with col_actions_2:
                # Reveal explanation box if answer is checked
                if checked:
                    correct_answer = current_mcq["correct_answer"]
                    is_correct = (selected_option == correct_answer)
                    
                    if is_correct:
                        st.success(f"🎉 **Correct Answer: Option {correct_answer}**")
                    else:
                        st.error(f"❌ **Incorrect. You selected Option {selected_option}. Correct Answer is Option {correct_answer}.**")
                        
                    # Explanation Card
                    st.markdown(f"""
                    <div class="explanation-container">
                        <div class="explanation-title">💡 Textbook Detail & Explanation:</div>
                        <div class="explanation-text">{current_mcq["explanation"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
            st.write("")
            st.markdown("---")
            
            # Navigation row
            col_prev, col_middle, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("⬅️ Previous Question", disabled=(q_idx == 0), use_container_width=True):
                    st.session_state["current_q_idx"] = q_idx - 1
                    save_progress()
                    st.rerun()
            with col_middle:
                # Show answers count
                answered_count = sum(1 for q in topic_answers.values() if q.get("checked", False))
                st.markdown(
                    f"<div style='text-align: center; color: #94A3B8; font-size: 0.95rem; margin-top: 8px; font-weight: 500;'>"
                    f"Answered: {answered_count} / {len(mcqs_list)} questions"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_next:
                if q_idx < len(mcqs_list) - 1:
                    if st.button("Next Question ➡️", use_container_width=True):
                        st.session_state["current_q_idx"] = q_idx + 1
                        save_progress()
                        st.rerun()
                else:
                    st.button("End of Batch reached 🏁", disabled=True, use_container_width=True)
            
            # ----------------------------------------------------
            # Dynamic "Load More" & "Next Topic" Choice Cards
            # ----------------------------------------------------
            if checked and q_idx == len(mcqs_list) - 1:
                st.write("")
                st.markdown("""
                <div style="background-color: rgba(13, 148, 136, 0.1); border: 1px solid #0D9488; border-radius: 12px; padding: 25px; margin-top: 30px; text-align: center;">
                    <h3 style="color: #0D9488; margin-top: 0; font-weight: 700;">🎉 Topic Batch Completed!</h3>
                    <p style="color: #E2E8F0; font-size: 0.95rem; margin-bottom: 20px;">
                        You have completed the current batch of MCQs for this sub-topic. What would you like to do next?
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                col_load, col_next_topic = st.columns(2)
                
                with col_load:
                    st.markdown("""
                    <div style="background-color: #1E293B; padding: 20px; border-radius: 10px; border: 1px solid #334155; margin-bottom: 10px;">
                        <h4 style="color: #0D9488; margin-top: 0; margin-bottom: 10px;">Option A: Load More MCQs</h4>
                        <p style="color: #94A3B8; font-size: 0.85rem; margin-bottom: 15px;">Pull an additional batch of verbatim questions from this topic without duplicates.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    load_more_count = st.slider(
                        "How many more verbatim questions to load?",
                        min_value=1,
                        max_value=15,
                        value=st.session_state["num_mcqs_per_topic"],
                        step=1,
                        key=f"load_more_slider_{current_topic_idx}_{len(mcqs_list)}"
                    )
                    
                    is_pdf_available = bool(st.session_state["outline_text"])
                    if not is_pdf_available:
                        st.warning("⚠️ **PDF Text Context Missing**: To pull new questions, please upload your textbook PDF in the sidebar first.")
                        
                    if st.button("Load More MCQs 📥", type="primary", use_container_width=True, disabled=not is_pdf_available):
                        existing_qs = [q["question"] for q in mcqs_list]
                        with st.spinner("Extracting additional verbatim questions from text..."):
                            try:
                                client = GeminiStudyClient(
                                    api_key=st.session_state["api_key"],
                                    model_name=model_choice
                                )
                                new_mcqs = client.extract_verbatim_mcqs(
                                    subtopic=active_topic,
                                    chapter_context=st.session_state["outline_text"],
                                    num_questions=load_more_count,
                                    existing_questions=existing_qs
                                )
                                if new_mcqs:
                                    st.session_state["mcqs"][active_topic].extend(new_mcqs)
                                    st.session_state["current_q_idx"] = len(mcqs_list) # Point to the first newly added question
                                    save_progress()
                                    st.success(f"Successfully loaded {len(new_mcqs)} additional MCQs!")
                                    st.rerun()
                                else:
                                    st.warning("No additional MCQs found in the textbook text for this sub-topic.")
                            except Exception as e:
                                st.error(f"Failed to load more MCQs: {str(e)}")
                                
                with col_next_topic:
                    st.markdown("""
                    <div style="background-color: #1E293B; padding: 20px; border-radius: 10px; border: 1px solid #334155; margin-bottom: 10px;">
                        <h4 style="color: #0D9488; margin-top: 0; margin-bottom: 10px;">Option B: Go to Next Topic</h4>
                        <p style="color: #94A3B8; font-size: 0.85rem; margin-bottom: 15px;">Mark this topic as completely finished and advance directly to the next study division.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.write("")
                    st.write("")
                    
                    if current_topic_idx < len(topics) - 1:
                        next_topic_btn_text = f"Advance to: {topics[current_topic_idx + 1]} ➡️"
                        if st.button(next_topic_btn_text, type="secondary", use_container_width=True):
                            st.session_state["current_topic_index"] = current_topic_idx + 1
                            st.session_state["current_q_idx"] = 0
                            save_progress()
                            st.rerun()
                    else:
                        if st.button("🏆 Finish Chapter & View Summary", type="secondary", use_container_width=True):
                            st.session_state["current_topic_index"] = len(topics)
                            st.session_state["current_q_idx"] = 0
                            save_progress()
                            st.rerun()
