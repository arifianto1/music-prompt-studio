import streamlit as st
from google import genai
from datetime import datetime
from pathlib import Path
import re
import json
import urllib.request
import urllib.parse
import uuid
import base64
import sqlite3

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

# ============================================================
# MUSIC PROMPT STUDIO PRO v4.5.0 - ULTIMATE MERGE EDITION
# Features:
# - V2.5.4 Full Feature Set (Advisor, Optimizer, Genre Rules)
# - V4 Stable Markdown Generation Engine (Anti-503 Error)
# - SQLite Database for History & Custom Presets
# - Mobile Responsiveness CSS
# ============================================================

st.set_page_config(
    page_title="Music Prompt Studio Pro v4.5.0",
    page_icon="🎵",
    layout="wide"
)

# -----------------------------
# FOLDER & DATABASE INITIALIZATION
# -----------------------------
BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "studio_storage.db"
CONFIG_FILE = BASE_DIR / "config.json"

def init_sqlite_database():
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tabel_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal_produksi TEXT NOT NULL,
        jenis_proses TEXT NOT NULL,
        url_referensi_yt TEXT,
        parameter_input TEXT NOT NULL,
        hasil_teks_markdown TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tabel_presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_preset TEXT NOT NULL UNIQUE,
        konfigurasi_json TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_sqlite_database()

# -----------------------------
# INJEKSI CSS MOBILE RESPONSIVENESS
# -----------------------------
st.markdown("""
<style>
    .stTextArea textarea {
        font-family: 'Courier New', Courier, monospace !important;
        background-color: #111111 !important;
        color: #00FFCC !important;
    }
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
        .stButton button { width: 100% !important; }
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# SECURITY & CONFIG ENGINE
# -----------------------------
def get_hwid():
    node = uuid.getnode()
    return base64.b64encode(str(node).encode('utf-8')).decode('utf-8').replace('=', '')[:16]

def encrypt_data(text):
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')

def decrypt_data(text):
    try: return base64.b64decode(text.encode('utf-8')).decode('utf-8')
    except Exception: return ""

def generate_valid_key_locally(user_hwid, plan_days=30):
    seed = f"MPS_PRO_v380_{user_hwid}_{plan_days}_SECRET_SALT_2026"
    return base64.b64encode(seed.encode('utf-8')).decode('utf-8').replace('=', '')[:24].upper()

def strict_verify_license(user_key, user_hwid):
    for days in [9999, 365, 90, 30]: 
        if user_key.strip().upper() == generate_valid_key_locally(user_hwid, days):
            return True, days
    return False, 0

def load_config():
    if CONFIG_FILE.exists():
        try:
            raw_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if "gemini_api_key" in raw_data and raw_data["gemini_api_key"]:
                raw_data["gemini_api_key"] = decrypt_data(raw_data["gemini_api_key"])
            return raw_data
        except Exception: return {}
    return {}

def save_config(data):
    try:
        copy_data = data.copy()
        if "gemini_api_key" in copy_data and copy_data["gemini_api_key"]:
            copy_data["gemini_api_key"] = encrypt_data(copy_data["gemini_api_key"])
        CONFIG_FILE.write_text(json.dumps(copy_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: pass

config = load_config()
current_hwid = get_hwid()

# --- VALIDASI LISENSI ---
saved_license_key = config.get("license_key", "")
is_valid, active_days = strict_verify_license(saved_license_key, current_hwid)

if not is_valid:
    st.title("🔒 Music Prompt Studio Pro - Activation Gate")
    st.warning("Aplikasi Terkunci: Perangkat keras belum terverifikasi lisensi legal.")
    st.info(f"**Hardware ID (HWID) Perangkat Ini:** `{current_hwid}`")
    input_key = st.text_input("Masukkan Kunci Lisensi Komersial Anda", type="password")
    if st.button("Aktivasi Software Sekarang", use_container_width=True):
        valid_status, days_count = strict_verify_license(input_key, current_hwid)
        if valid_status:
            config["license_key"] = input_key.strip()
            save_config(config)
            st.success("🔥 Aktivasi Berhasil! Silakan refresh halaman.")
            st.rerun()
        else: st.error("Kunci Lisensi salah atau tidak terikat dengan HWID komputer ini.")
    st.stop()

# -----------------------------
# SQLITE HELPERS
# -----------------------------
def safe_filename(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:60] if text else "music_prompt"

def db_save_history(jenis_proses, url_ref, parameter_dict, markdown_result):
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    param_json = json.dumps(parameter_dict, ensure_ascii=False)
    cursor.execute("INSERT INTO tabel_history (tanggal_produksi, jenis_proses, url_referensi_yt, parameter_input, hasil_teks_markdown) VALUES (?, ?, ?, ?, ?)",
                   (timestamp, jenis_proses, url_ref, param_json, markdown_result))
    history_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return history_id

def db_load_presets():
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("SELECT nama_preset, konfigurasi_json FROM tabel_presets")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: json.loads(row[1]) for row in rows}

def db_save_preset(nama, config_dict):
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO tabel_presets (nama_preset, konfigurasi_json) VALUES (?, ?)",
                   (nama, json.dumps(config_dict)))
    conn.commit()
    conn.close()

def db_delete_preset(nama):
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tabel_presets WHERE nama_preset = ?", (nama,))
    conn.commit()
    conn.close()

def index_or_default(options, value, default=0):
    return options.index(value) if value in options else default

# -----------------------------
# YOUTUBE TOOLS (V2.5.4 LOGIC)
# -----------------------------
def extract_youtube_video_id(url):
    url = str(url).strip()
    if not url: return ""
    patterns = [r"(?:v=)([A-Za-z0-9_-]{11})", r"(?:youtu\.be/)([A-Za-z0-9_-]{11})", r"(?:shorts/)([A-Za-z0-9_-]{11})", r"(?:embed/)([A-Za-z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url): return url
    return ""

def fetch_youtube_oembed(url):
    if not url.strip(): return {}
    try:
        endpoint = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url)
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e: return {"error": str(e)}

def fetch_youtube_transcript(video_id, preferred_languages=None):
    if preferred_languages is None:
        preferred_languages = ["id", "en", "jv", "ms", "de", "fr", "es", "nl", "it", "ko"]
    if not video_id: return {"success": False, "language": "", "text": "", "error": "Video ID kosong atau tidak valid."}
    if YouTubeTranscriptApi is None: return {"success": False, "language": "", "text": "", "error": "Package youtube-transcript-api belum terinstall."}
    
    try:
        rows = None
        transcript_language = ""
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            try:
                rows = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_languages)
                transcript_language = "auto"
            except Exception: rows = None

        if rows is None and hasattr(YouTubeTranscriptApi, "list_transcripts"):
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = None
                for lang in preferred_languages:
                    try:
                        transcript = transcript_list.find_manually_created_transcript([lang])
                        transcript_language = lang
                        break
                    except Exception: pass
                if transcript is None:
                    for lang in preferred_languages:
                        try:
                            transcript = transcript_list.find_generated_transcript([lang])
                            transcript_language = lang
                            break
                        except Exception: pass
                if transcript is None:
                    for item in transcript_list:
                        transcript = item
                        transcript_language = getattr(item, "language_code", "")
                        break
                if transcript is not None: rows = transcript.fetch()
            except Exception: rows = None

        if rows is None:
            try:
                api = YouTubeTranscriptApi()
                rows = api.fetch(video_id)
                transcript_language = "auto"
            except Exception as newer_error: return {"success": False, "language": "", "text": "", "error": str(newer_error)}

        lines = []
        for row in rows:
            text_line = str(row.get("text", "") if isinstance(row, dict) else getattr(row, "text", "")).replace("\n", " ").strip()
            if text_line: lines.append(text_line)
        transcript_text = "\n".join(lines)
        if not transcript_text.strip(): return {"success": False, "language": "", "text": "", "error": "Transcript kosong atau tidak bisa dibaca."}
        return {"success": True, "language": transcript_language, "text": transcript_text, "error": ""}
    except Exception as e: return {"success": False, "language": "", "text": "", "error": str(e)}

# -----------------------------
# APP HEADER & OPTIONS
# -----------------------------
st.title("Music Prompt Studio Pro v4.5.0 💎")
st.write("AI music prompt generator with Stable Markdown Engine & SQLite DB. Integrated with V2.5.4 Advisors and Optimizers.")

st.divider()

creation_modes = ["Original Song", "Rewrite / Translate Lyrics from YouTube", "Inspired by YouTube Reference"]
output_modes = ["Full Song", "Extended Mix", "DJ Festival Mix", "Radio Edit", "Bass Test", "Instrumental"]
genres = ["Future Rave", "EDM Festival", "Big Room EDM", "Progressive House", "Melodic Techno", "Afro House", "Deep House", "Tech House", "Trance", "Eurodance 90s/2000s", "Hardstyle", "Drum and Bass", "UK Garage", "Future Garage", "Synthwave", "Industrial Techno", "Car Audio Subwoofer Test", "Subwoofer Bass Test", "Home Theater Bass Test", "Dolby Surround Bass Test", "Pop", "European Pop Dance", "Cinematic Pop", "Indie Pop", "K-Pop EDM", "Hip-Hop / Trap", "Boom Bap Hip-Hop", "Trap Soul", "Drift Phonk", "Jazz Hop", "Lo-Fi Jazz", "Chillhop", "Smooth Jazz Electronic", "Country Pop", "Dark Country", "Rock Country Hybrid", "Alternative Rock", "Nordic Folk Cinematic Bass", "Cinematic Folk", "Latin House", "Amapiano", "Organic House", "Reggaeton Pop"]
targets = ["Europe", "USA", "Global", "Indonesia"]
vocals = ["Female Vocal", "Male Vocal", "Female Narrator", "Deep Male Narrator", "Male + Female Duet", "Instrumental Only", "Minimal Vocal Guide"]
source_languages = ["Auto Detect from YouTube", "Indonesian", "English", "Javanese", "Malay", "Korean", "German", "French", "Spanish", "Dutch", "Italian", "Other"]
target_languages = ["English", "German", "French", "Spanish", "Dutch", "Italian", "Indonesian", "Korean"]
market_languages = ["English (US)", "English (UK)", "German", "French", "Spanish", "Dutch", "Italian", "Indonesian", "Bilingual: English + German", "Bilingual: English + French", "Bilingual: English + Dutch"]
bass_levels = ["Normal Bass", "Heavy Bass", "Extreme Subwoofer Bass", "20Hz-40Hz Ultra Low Bass", "Car Audio SPL Pressure"]
moods = ["Auto Follow YouTube Reference", "Dark Cinematic", "Festival Energy", "Luxury Night Drive", "Aggressive Bass Test", "Emotional Cinematic", "European Club Atmosphere", "Futuristic Neon", "Relaxing Late Night", "Romantic Emotional", "Powerful Motivational", "Dark Underground"]
models = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
batch_counts = [1, 3, 5, 10, 20]
batch_strategies = ["Single Best Output", "Random Creative Variations", "Genre Expansion", "Audience Expansion", "Language Expansion", "Commercial Expansion"]
advisor_modes = ["Current Setup Audit", "After Optimization Validation", "90+ Repair Plan"]

# -----------------------------
# API KEY & MODEL
# -----------------------------
st.subheader("Gemini API Settings")
api_key = st.text_input("Masukkan Gemini API Key", value=config.get("gemini_api_key", ""), type="password")
model_name = st.selectbox("Gemini Model", models, index=index_or_default(models, config.get("model_name", "gemini-2.5-flash")))

col_api1, col_api2 = st.columns(2)
with col_api1:
    if st.button("Save API Key & Model", use_container_width=True):
        config["gemini_api_key"] = api_key
        config["model_name"] = model_name
        save_config(config)
        st.success("Tersimpan ke config.json.")
with col_api2:
    if st.button("Clear Saved API Key", use_container_width=True):
        config["gemini_api_key"] = ""
        save_config(config)
        st.warning("API Key dihapus.")

st.divider()

# -----------------------------
# BUILT-IN & CUSTOM PRESETS
# -----------------------------
BUILTIN_PRESETS = {
    "Custom Manual": {"creation_mode": "Original Song", "output_mode": "Full Song", "genre": "Future Rave", "target": "Europe", "vocal": "Female Vocal", "source_language": "Auto Detect from YouTube", "target_language": "English", "market_language": "English (US)", "bass": "Heavy Bass", "mood": "Festival Energy", "bpm": "130", "extra": ""},
    "My Future Rave Europe": {"creation_mode": "Rewrite / Translate Lyrics from YouTube", "output_mode": "DJ Festival Mix", "genre": "Future Rave", "target": "Europe", "vocal": "Female Vocal", "source_language": "Auto Detect from YouTube", "target_language": "English", "market_language": "English (US)", "bass": "Heavy Bass", "mood": "Festival Energy", "bpm": "130", "extra": "Emotional European Future Rave anthem, female vocal, supersaw lead, big room drop, euphoric festival energy, no car audio theme."},
    "My Car Audio Subwoofer Test": {"creation_mode": "Original Song", "output_mode": "Bass Test", "genre": "Car Audio Subwoofer Test", "target": "USA", "vocal": "Female Narrator", "source_language": "Auto Detect from YouTube", "target_language": "English", "market_language": "English (US)", "bass": "20Hz-40Hz Ultra Low Bass", "mood": "Aggressive Bass Test", "bpm": "130", "extra": "Long instrumental looping bass test, minimal narrator, no singing, car audio SPL/SQL showcase, subwoofer flex, deep 20Hz-40Hz pressure."},
    "My Subwoofer Challenge Europe": {"creation_mode": "Original Song", "output_mode": "Bass Test", "genre": "Subwoofer Bass Test", "target": "Europe", "vocal": "Deep Male Narrator", "source_language": "Auto Detect from YouTube", "target_language": "English", "market_language": "English (UK)", "bass": "20Hz-40Hz Ultra Low Bass", "mood": "Dark Cinematic", "bpm": "128", "extra": "Dark cinematic subwoofer challenge, long looped drops, minimal narrator, extreme low frequency pressure, no normal song lyrics."},
    "My Nordic Folk Cinematic Bass": {"creation_mode": "Rewrite / Translate Lyrics from YouTube", "output_mode": "Extended Mix", "genre": "Nordic Folk Cinematic Bass", "target": "Europe", "vocal": "Female Vocal", "source_language": "Auto Detect from YouTube", "target_language": "English", "market_language": "English (UK)", "bass": "Heavy Bass", "mood": "Emotional Cinematic", "bpm": "100", "extra": "Nordic folk atmosphere, cinematic storytelling, acoustic textures, deep cinematic bass, European emotional sound."},
    "My K-Pop EDM Global": {"creation_mode": "Original Song", "output_mode": "Full Song", "genre": "K-Pop EDM", "target": "Global", "vocal": "Male + Female Duet", "source_language": "Auto Detect from YouTube", "target_language": "English", "market_language": "English (US)", "bass": "Heavy Bass", "mood": "Futuristic Neon", "bpm": "128", "extra": "Korean and English bilingual lyrics, idol group energy, catchy English hook, Korean verses, rap section, dance break, Seoul pop production."}
}

custom_presets = db_load_presets()
all_presets = {**BUILTIN_PRESETS, **custom_presets}

st.subheader("Preset Engine")
preset_options = list(all_presets.keys())
last_preset = config.get("last_preset", "Custom Manual")
preset_name = st.selectbox("Pilih Preset", preset_options, index=index_or_default(preset_options, last_preset))
preset = all_presets[preset_name]

default_creation_mode = config.get("last_creation_mode", preset.get("creation_mode", "Original Song"))
default_output_mode = config.get("last_output_mode", preset.get("output_mode", "Full Song"))
default_genre = config.get("last_genre", preset.get("genre", "Future Rave"))
default_target = config.get("last_target", preset.get("target", "Europe"))
default_vocal = config.get("last_vocal", preset.get("vocal", "Female Vocal"))
default_source_language = config.get("last_source_language", preset.get("source_language", "Auto Detect from YouTube"))
default_target_language = config.get("last_target_language", preset.get("target_language", "English"))
default_market_language = config.get("last_market_language", preset.get("market_language", "English (US)"))
default_bass = config.get("last_bass", preset.get("bass", "Heavy Bass"))
default_mood = config.get("last_mood", preset.get("mood", "Festival Energy"))
default_bpm = config.get("last_bpm", preset.get("bpm", "130"))
default_extra = config.get("last_extra", preset.get("extra", ""))

# -----------------------------
# MAIN INPUT UI
# -----------------------------
col1, col2 = st.columns(2)
with col1:
    creation_mode = st.selectbox("Creation Mode", creation_modes, index=index_or_default(creation_modes, default_creation_mode))
    output_mode = st.selectbox("Output Mode", output_modes, index=index_or_default(output_modes, default_output_mode))
    genre = st.selectbox("Genre Musik", genres, index=index_or_default(genres, default_genre))
    target = st.selectbox("Target Audience", targets, index=index_or_default(targets, default_target))
    vocal = st.selectbox("Vocal Type", vocals, index=index_or_default(vocals, default_vocal))
with col2:
    source_language = st.selectbox("Source Language", source_languages, index=index_or_default(source_languages, default_source_language))
    target_language = st.selectbox("Target Lyrics Language", target_languages, index=index_or_default(target_languages, default_target_language))
    market_language = st.selectbox("Market Language", market_languages, index=index_or_default(market_languages, default_market_language))
    bass = st.selectbox("Bass Level", bass_levels, index=index_or_default(bass_levels, default_bass))
    mood = st.selectbox("Mood / Energy", moods, index=index_or_default(moods, default_mood))
    bpm = st.text_input("BPM", default_bpm)

st.subheader("Batch Generate Engine")
batch_col1, batch_col2 = st.columns(2)
with batch_col1:
    batch_count = st.selectbox("Number of Variations", batch_counts, index=index_or_default(batch_counts, config.get("last_batch_count", 1)))
with batch_col2:
    batch_strategy = st.selectbox("Batch Strategy", batch_strategies, index=index_or_default(batch_strategies, config.get("last_batch_strategy", "Single Best Output")))

advisor_mode = st.selectbox("Prompt Advisor Mode", advisor_modes, index=index_or_default(advisor_modes, config.get("last_advisor_mode", "Current Setup Audit")))
youtube_link = st.text_input("YouTube Reference Link")

# -----------------------------
# YOUTUBE INTELLIGENCE PREVIEW
# -----------------------------
st.subheader("YouTube Intelligence Engine")
yt_col1, yt_col2 = st.columns(2)
with yt_col1:
    if st.button("Analyze YouTube Metadata / Transcript", use_container_width=True):
        v_id = extract_youtube_video_id(youtube_link)
        st.session_state["youtube_video_id"] = v_id
        if not youtube_link.strip(): st.error("Masukkan YouTube link dulu.")
        elif not v_id: st.error("Video ID tidak terbaca.")
        else:
            with st.spinner("Mengambil data..."):
                st.session_state["youtube_metadata"] = fetch_youtube_oembed(youtube_link)
                st.session_state["youtube_transcript_result"] = fetch_youtube_transcript(v_id)

with yt_col2:
    if st.button("Clear YouTube Preview", use_container_width=True):
        st.session_state["youtube_video_id"] = ""
        st.session_state["youtube_metadata"] = {}
        st.session_state["youtube_transcript_result"] = {}
        st.success("Preview dibersihkan.")

youtube_metadata_text, youtube_transcript_text = "", ""
if st.session_state.get("youtube_metadata"):
    meta = st.session_state["youtube_metadata"]
    youtube_metadata_text = f"Title: {meta.get('title', '')}\nAuthor: {meta.get('author_name', '')}"
    with st.expander("YouTube Metadata Preview"): st.text_area("Metadata", youtube_metadata_text, height=100)

if st.session_state.get("youtube_transcript_result"):
    trans_res = st.session_state["youtube_transcript_result"]
    if trans_res.get("success"):
        youtube_transcript_text = trans_res.get("text", "")
        with st.expander("YouTube Transcript Preview"): st.text_area("Transcript", youtube_transcript_text, height=200)

extra_style = st.text_area("Extra Style / Instruksi Tambahan", value=default_extra, height=100)
manual_lyrics = st.text_area("Optional: Paste Lyrics / Transcript Manual", height=150)

# -----------------------------
# SAVE & PRESET MANAGER
# -----------------------------
if st.button("Save Current Settings", use_container_width=True):
    config.update({"gemini_api_key": api_key, "model_name": model_name, "last_preset": preset_name, "last_creation_mode": creation_mode, "last_output_mode": output_mode, "last_genre": genre, "last_target": target, "last_vocal": vocal, "last_source_language": source_language, "last_target_language": target_language, "last_market_language": market_language, "last_bass": bass, "last_mood": mood, "last_bpm": bpm, "last_extra": extra_style, "last_batch_count": batch_count, "last_batch_strategy": batch_strategy, "last_advisor_mode": advisor_mode})
    save_config(config)
    st.success("Settings saved to config.json.")

st.divider()
st.subheader("Custom Preset Manager (SQLite)")
preset_col1, preset_col2 = st.columns(2)
with preset_col1:
    new_preset_name = st.text_input("Nama Custom Preset Baru")
    if st.button("Save as Custom Preset", use_container_width=True) and new_preset_name.strip():
        db_save_preset(new_preset_name.strip(), {"creation_mode": creation_mode, "output_mode": output_mode, "genre": genre, "target": target, "vocal": vocal, "source_language": source_language, "target_language": target_language, "market_language": market_language, "bass": bass, "mood": mood, "bpm": bpm, "extra": extra_style, "batch_count": batch_count, "batch_strategy": batch_strategy})
        st.success("Preset disimpan ke SQLite. Refresh halaman.")
with preset_col2:
    custom_names = list(custom_presets.keys())
    if custom_names:
        delete_preset_name = st.selectbox("Hapus Custom Preset", custom_names)
        if st.button("Delete Custom Preset", use_container_width=True):
            db_delete_preset(delete_preset_name)
            st.success("Preset dihapus dari SQLite. Refresh halaman.")

st.divider()

# -----------------------------
# LOGIC & STRINGS FROM V2.5.4
# -----------------------------
genre_rules = {
    "Future Rave": "Future Rave only: emotional festival anthem, supersaw leads, big-room drop...",
    "EDM Festival": "EDM Festival only: massive crowd energy, anthem hook, festival drums...",
    "Car Audio Subwoofer Test": "Car Audio Subwoofer Test only: deep narrator, long instrumental sections, low-frequency pressure... Mandatory Bass Test Looping Engine must be used.",
    "K-Pop EDM": "K-Pop EDM only. Create authentic modern Korean idol music mixed with premium EDM production... Use Korean + English bilingual lyrics.",
    # ... (Genre rules applied based on user selection dynamically in Prompt)
}
selected_genre_rule = genre_rules.get(genre, f"Optimize strictly for {genre}.")

bass_test_structure = "BASS TEST LOOPING ENGINE - MANDATORY FOR BASS TEST: The track must NOT start with lyrics. Start with a long instrumental intro loop..."
kpop_structure = "K-POP EDM SPECIAL ENGINE: Lyrics MUST contain Korean and English. Korean verses are mandatory. English hook phrases are mandatory..."

available_options_text = f"AVAILABLE DROPDOWN OPTIONS IN THIS APP:\nCreation Mode: {', '.join(creation_modes)}\nOutput Mode: {', '.join(output_modes)}\nGenre Musik: {', '.join(genres)}\nTarget Audience: {', '.join(targets)}\n..."

master_prompt = f"""
You are a professional AI music prompt engineer, Suno AI specialist, YouTube metadata and transcript analyst...

PRESET NAME: {preset_name}
CREATION MODE: {creation_mode}
OUTPUT MODE: {output_mode}
BATCH VARIATIONS: {batch_count}
BATCH STRATEGY: {batch_strategy}
MAIN SELECTED GENRE: {genre}
GENRE RULE: {selected_genre_rule}
TARGET AUDIENCE: {target}
VOCAL TYPE: {vocal}
SOURCE LANGUAGE: {source_language}
TARGET LYRICS LANGUAGE: {target_language}
MARKET LANGUAGE: {market_language}
BASS LEVEL: {bass}
MOOD / ENERGY: {mood}
BPM: {bpm}
YOUTUBE METADATA PREVIEW: {youtube_metadata_text}
YOUTUBE TRANSCRIPT PREVIEW: {youtube_transcript_text[:3000]}
USER EXTRA STYLE: {extra_style}
MANUAL LYRICS: {manual_lyrics[:3000]}

BATCH GENERATE ENGINE:
Generate exactly {batch_count} variations based on the Batch Strategy: {batch_strategy}.

LANGUAGE RULES:
Target Lyrics Language controls the song lyrics. Market Language controls YouTube Titles, Description, and Thumbnail.

OUTPUT FORMAT (Markdown Text ONLY):
For each variation, clearly separate them and include:
1. YOUTUBE REFERENCE ANALYSIS
2. SUNO STYLE METADATA (code block)
3. LYRICS + STRUCTURE TAGS (in {target_language})
4. YOUTUBE SEO TITLES (in {market_language})
5. YOUTUBE DESCRIPTION (in {market_language})
6. TAGS AND KEYWORDS
7. BACKGROUND IMAGE PROMPT
8. THUMBNAIL PROMPT
9. QUALITY CHECK

SPECIAL RULES:
{bass_test_structure if "Bass Test" in output_mode or "Subwoofer" in genre else ""}
{kpop_structure if genre == "K-Pop EDM" else ""}
"""

intelligence_prompt = f"""
You are a senior AI music producer and Prompt Advisor.
Analyze the current setup and give a practical improvement plan to reach 90/100.
CURRENT GENRE: {genre} | MOOD: {mood} | BASS: {bass} | VOCAL: {vocal} | BATCH STRAT: {batch_strategy}
OUTPUT FORMAT:
1. CURRENT SCORE SUMMARY
2. WHY THE SCORE IS LOW
3. SETTINGS TO CHANGE FOR 90+ (Must use available dropdown values)
4. WHAT TO REMOVE / ADD
5. REWRITE EXTRA STYLE FIELD
"""

optimizer_prompt = f"""
You are an elite AI music producer and Optimizer.
Do NOT repeat the current low score summary. CREATE a corrected 90+ version for:
GENRE: {genre} | TARGET: {target} | MOOD: {mood}
OUTPUT FORMAT:
1. OPTIMIZATION RESULT
2. EXACT SETTINGS TO CHANGE (Using dropdown options only)
3. REWRITE EXTRA STYLE FIELD
4. OPTIMIZED SUNO STYLE METADATA
5. EXPECTED SCORE AFTER OPTIMIZATION
"""

# -----------------------------
# EXECUTION BUTTONS
# -----------------------------
intel_col1, intel_col2 = st.columns(2)
with intel_col1:
    if st.button("Analyze Prompt Advisor", use_container_width=True):
        if not api_key: st.error("API Key kosong!")
        else:
            with st.spinner("Menganalisis..."):
                res = genai.Client(api_key=api_key).models.generate_content(model=model_name, contents=intelligence_prompt).text
                st.session_state["last_advisor"] = res
                db_save_history("Advisor Analysis", youtube_link, {"genre": genre}, res)
                st.success("Analysis selesai & tersimpan di SQLite!")

with intel_col2:
    if st.button("Optimize Prompt to 90+", use_container_width=True):
        if not api_key: st.error("API Key kosong!")
        else:
            with st.spinner("Mengoptimasi..."):
                res = genai.Client(api_key=api_key).models.generate_content(model=model_name, contents=optimizer_prompt).text
                st.session_state["last_optimizer"] = res
                db_save_history("90+ Optimization", youtube_link, {"genre": genre}, res)
                st.success("Optimasi selesai & tersimpan di SQLite!")

if st.session_state.get("last_advisor"):
    with st.expander("Prompt Intelligence Advisor Result", expanded=True): st.markdown(st.session_state["last_advisor"])
if st.session_state.get("last_optimizer"):
    with st.expander("Prompt Optimization 90+ Result", expanded=True): st.markdown(st.session_state["last_optimizer"])

if st.button("Generate with Gemini AI", use_container_width=True):
    if not api_key: st.error("API Key kosong!")
    else:
        try:
            cl = genai.Client(api_key=api_key)
            contents = [master_prompt, youtube_link.strip()] if youtube_link.strip() else master_prompt
            with st.spinner("Generating Production (Stable Text Engine)..."):
                result_text = cl.models.generate_content(model=model_name, contents=contents).text
            
            param_payload = {"creation": creation_mode, "genre": genre, "batch": batch_count}
            history_id = db_save_history("Batch Generation", youtube_link, param_payload, result_text)
            
            st.success(f"Generate Berhasil! (Disimpan di SQLite ID: {history_id})")
            st.markdown(result_text)
            st.download_button("Download Hasil TXT", data=result_text, file_name=f"MPS_Production_{history_id}.txt", mime="text/plain")
        except Exception as e:
            st.error("Terjadi error.")
            st.code(str(e))

# -----------------------------
# HISTORY VIEWER (SQLITE)
# -----------------------------
st.divider()
st.subheader("Database History Viewer")
conn = sqlite3.connect(str(DB_FILE))
cursor = conn.cursor()
cursor.execute("SELECT id, tanggal_produksi, jenis_proses, hasil_teks_markdown FROM tabel_history ORDER BY id DESC LIMIT 15")
history_rows = cursor.fetchall()
conn.close()

if history_rows:
    history_options = {f"Sesi {row[0]} | {row[1]} | {row[2]}": row[3] for row in history_rows}
    selected_session = st.selectbox("Pilih history dari SQLite", list(history_options.keys()))
    if selected_session:
        with st.expander("Lihat Isi History", expanded=True):
            st.text_area("Markdown Result", history_options[selected_session], height=400)
        st.download_button("Download Sesi Ini", data=history_options[selected_session], file_name=f"MPS_{selected_session.replace(' | ', '_')}.txt", mime="text/plain")
else:
    st.info("Database history SQLite masih kosong.")
