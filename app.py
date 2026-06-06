import streamlit as st
from google import genai
from datetime import datetime
from pathlib import Path
import re
import json
import urllib.request
import urllib.parse

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

# ============================================================
# MUSIC PROMPT STUDIO PRO v2.5.4
# Features:
# - Gemini AI integration
# - Save / Load Gemini API Key
# - Remember last settings
# - YouTube Adaptation Engine
# - Multi-language lyrics
# - Market language for title, description, tags, thumbnail text
# - Built-in Preset Engine
# - Custom Preset Save / Load / Delete
# - Auto Save History
# - Bass Test Looping Engine
# - Expanded Europe & USA genre library
# ============================================================

st.set_page_config(
    page_title="Music Prompt Studio Pro v2.5.4",
    page_icon="M",
    layout="wide"
)

# -----------------------------
# BASIC FOLDER SETUP
# -----------------------------
BASE_DIR = Path(__file__).parent
HISTORY_DIR = BASE_DIR / "history"
EXPORT_DIR = BASE_DIR / "exports"
CUSTOM_PRESET_FILE = BASE_DIR / "custom_presets.json"
CONFIG_FILE = BASE_DIR / "config.json"

HISTORY_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def safe_filename(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:60] if text else "music_prompt"

def save_history(content, genre, preset_name):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    genre_slug = safe_filename(genre)
    preset_slug = safe_filename(preset_name)
    filename = f"{timestamp}_{preset_slug}_{genre_slug}.txt"
    path = HISTORY_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path

def read_recent_history(limit=10):
    files = sorted(HISTORY_DIR.glob("*.txt"), reverse=True)
    return files[:limit]

def load_custom_presets():
    if CUSTOM_PRESET_FILE.exists():
        try:
            return json.loads(CUSTOM_PRESET_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_custom_presets(data):
    CUSTOM_PRESET_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_config(data):
    CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def index_or_default(options, value, default=0):
    return options.index(value) if value in options else default

def extract_youtube_video_id(url):
    url = str(url).strip()
    if not url:
        return ""

    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url

    return ""

def fetch_youtube_oembed(url):
    if not url.strip():
        return {}

    try:
        endpoint = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url)
        req = urllib.request.Request(
            endpoint,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        return {"error": str(e)}

def fetch_youtube_transcript(video_id, preferred_languages=None):
    if preferred_languages is None:
        preferred_languages = ["id", "en", "jv", "ms", "de", "fr", "es", "nl", "it", "ko"]

    if not video_id:
        return {
            "success": False,
            "language": "",
            "text": "",
            "error": "Video ID kosong atau tidak valid."
        }

    if YouTubeTranscriptApi is None:
        return {
            "success": False,
            "language": "",
            "text": "",
            "error": "Package youtube-transcript-api belum terinstall. Jalankan: pip install youtube-transcript-api"
        }

    try:
        rows = None
        transcript_language = ""

        # Compatible with older versions: YouTubeTranscriptApi.get_transcript(...)
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            try:
                rows = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_languages)
                transcript_language = "auto"
            except Exception:
                rows = None

        # Compatible with older versions: YouTubeTranscriptApi.list_transcripts(...)
        if rows is None and hasattr(YouTubeTranscriptApi, "list_transcripts"):
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = None

                for lang in preferred_languages:
                    try:
                        transcript = transcript_list.find_manually_created_transcript([lang])
                        transcript_language = lang
                        break
                    except Exception:
                        pass

                if transcript is None:
                    for lang in preferred_languages:
                        try:
                            transcript = transcript_list.find_generated_transcript([lang])
                            transcript_language = lang
                            break
                        except Exception:
                            pass

                if transcript is None:
                    for item in transcript_list:
                        transcript = item
                        transcript_language = getattr(item, "language_code", "")
                        break

                if transcript is not None:
                    rows = transcript.fetch()
            except Exception:
                rows = None

        # Compatible with newer versions: instance.fetch(video_id)
        if rows is None:
            try:
                api = YouTubeTranscriptApi()
                rows = api.fetch(video_id)
                transcript_language = "auto"
            except Exception as newer_error:
                return {
                    "success": False,
                    "language": "",
                    "text": "",
                    "error": str(newer_error)
                }

        lines = []
        for row in rows:
            if isinstance(row, dict):
                text_line = row.get("text", "")
            else:
                text_line = getattr(row, "text", "")
            text_line = str(text_line).replace("\n", " ").strip()
            if text_line:
                lines.append(text_line)

        transcript_text = "\n".join(lines)

        if not transcript_text.strip():
            return {
                "success": False,
                "language": "",
                "text": "",
                "error": "Transcript kosong atau tidak bisa dibaca."
            }

        return {
            "success": True,
            "language": transcript_language,
            "text": transcript_text,
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "language": "",
            "text": "",
            "error": str(e)
        }
# -----------------------------
# LOAD CONFIG
# -----------------------------
config = load_config()

# -----------------------------
# APP HEADER
# -----------------------------
st.title("Music Prompt Studio Pro v2.5.4")
st.write("AI music prompt generator for Suno AI, YouTube lyric adaptation, SEO titles, descriptions, tags, background prompts, thumbnails, custom presets, history, saved settings, YouTube intelligence preview, and batch generation, prompt intelligence, and stable dropdown-aware prompt optimization.")

st.divider()

# -----------------------------
# OPTION LISTS
# -----------------------------
creation_modes = [
    "Original Song",
    "Rewrite / Translate Lyrics from YouTube",
    "Inspired by YouTube Reference"
]

output_modes = [
    "Full Song",
    "Extended Mix",
    "DJ Festival Mix",
    "Radio Edit",
    "Bass Test",
    "Instrumental"
]

genres = [
    "Future Rave",
    "EDM Festival",
    "Big Room EDM",
    "Progressive House",
    "Melodic Techno",
    "Afro House",
    "Deep House",
    "Tech House",
    "Trance",
    "Eurodance 90s/2000s",
    "Hardstyle",
    "Drum and Bass",
    "UK Garage",
    "Future Garage",
    "Synthwave",
    "Industrial Techno",
    "Car Audio Subwoofer Test",
    "Subwoofer Bass Test",
    "Home Theater Bass Test",
    "Dolby Surround Bass Test",
    "Pop",
    "European Pop Dance",
    "Cinematic Pop",
    "Indie Pop",
    "K-Pop EDM",
    "Hip-Hop / Trap",
    "Boom Bap Hip-Hop",
    "Trap Soul",
    "Drift Phonk",
    "Jazz Hop",
    "Lo-Fi Jazz",
    "Chillhop",
    "Smooth Jazz Electronic",
    "Country Pop",
    "Dark Country",
    "Rock Country Hybrid",
    "Alternative Rock",
    "Nordic Folk Cinematic Bass",
    "Cinematic Folk",
    "Latin House",
    "Amapiano",
    "Organic House",
    "Reggaeton Pop"
]

targets = [
    "Europe",
    "USA",
    "Global",
    "Indonesia"
]

vocals = [
    "Female Vocal",
    "Male Vocal",
    "Female Narrator",
    "Deep Male Narrator",
    "Male + Female Duet",
    "Instrumental Only",
    "Minimal Vocal Guide"
]

source_languages = [
    "Auto Detect from YouTube",
    "Indonesian",
    "English",
    "Javanese",
    "Malay",
    "Korean",
    "German",
    "French",
    "Spanish",
    "Dutch",
    "Italian",
    "Other"
]

target_languages = [
    "English",
    "German",
    "French",
    "Spanish",
    "Dutch",
    "Italian",
    "Indonesian",
    "Korean"
]

market_languages = [
    "English (US)",
    "English (UK)",
    "German",
    "French",
    "Spanish",
    "Dutch",
    "Italian",
    "Indonesian",
    "Bilingual: English + German",
    "Bilingual: English + French",
    "Bilingual: English + Dutch"
]

bass_levels = [
    "Normal Bass",
    "Heavy Bass",
    "Extreme Subwoofer Bass",
    "20Hz-40Hz Ultra Low Bass",
    "Car Audio SPL Pressure"
]

moods = [
    "Auto Follow YouTube Reference",
    "Dark Cinematic",
    "Festival Energy",
    "Luxury Night Drive",
    "Aggressive Bass Test",
    "Emotional Cinematic",
    "European Club Atmosphere",
    "Futuristic Neon",
    "Relaxing Late Night",
    "Romantic Emotional",
    "Powerful Motivational",
    "Dark Underground"
]

models = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash"
]

batch_counts = [1, 3, 5, 10, 20]

batch_strategies = [
    "Single Best Output",
    "Random Creative Variations",
    "Genre Expansion",
    "Audience Expansion",
    "Language Expansion",
    "Commercial Expansion"
]

advisor_modes = [
    "Current Setup Audit",
    "After Optimization Validation",
    "90+ Repair Plan"
]

# -----------------------------
# API KEY + MODEL CONFIG
# -----------------------------
st.subheader("Gemini API Settings")

api_key = st.text_input(
    "Masukkan Gemini API Key",
    value=config.get("gemini_api_key", ""),
    type="password"
)

model_name = st.selectbox(
    "Gemini Model",
    models,
    index=index_or_default(models, config.get("model_name", "gemini-3.5-flash"))
)

save_api_col1, save_api_col2 = st.columns(2)

with save_api_col1:
    if st.button("Save API Key & Model", use_container_width=True):
        config["gemini_api_key"] = api_key
        config["model_name"] = model_name
        save_config(config)
        st.success("API Key dan model berhasil disimpan ke config.json.")

with save_api_col2:
    if st.button("Clear Saved API Key", use_container_width=True):
        config["gemini_api_key"] = ""
        save_config(config)
        st.warning("API Key tersimpan sudah dihapus. Refresh aplikasi untuk melihat perubahan.")

st.caption("Catatan: API key disimpan lokal di file config.json di folder aplikasi. Jangan bagikan folder aplikasi jika API key masih tersimpan.")
st.caption("Untuk fitur transcript YouTube, install tambahan: pip install youtube-transcript-api")

st.divider()

# -----------------------------
# BUILT-IN PRESETS
# -----------------------------
BUILTIN_PRESETS = {
    "Custom Manual": {
        "creation_mode": "Original Song",
        "output_mode": "Full Song",
        "genre": "Future Rave",
        "target": "Europe",
        "vocal": "Female Vocal",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (US)",
        "bass": "Heavy Bass",
        "mood": "Festival Energy",
        "bpm": "130",
        "extra": ""
    },
    "My Future Rave Europe": {
        "creation_mode": "Rewrite / Translate Lyrics from YouTube",
        "output_mode": "DJ Festival Mix",
        "genre": "Future Rave",
        "target": "Europe",
        "vocal": "Female Vocal",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (US)",
        "bass": "Heavy Bass",
        "mood": "Festival Energy",
        "bpm": "130",
        "extra": "Emotional European Future Rave anthem, female vocal, supersaw lead, big room drop, euphoric festival energy, no car audio theme."
    },
    "My Car Audio Subwoofer Test": {
        "creation_mode": "Original Song",
        "output_mode": "Bass Test",
        "genre": "Car Audio Subwoofer Test",
        "target": "USA",
        "vocal": "Female Narrator",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (US)",
        "bass": "20Hz-40Hz Ultra Low Bass",
        "mood": "Aggressive Bass Test",
        "bpm": "130",
        "extra": "Long instrumental looping bass test, minimal narrator, no singing, car audio SPL/SQL showcase, subwoofer flex, deep 20Hz-40Hz pressure."
    },
    "My Subwoofer Challenge Europe": {
        "creation_mode": "Original Song",
        "output_mode": "Bass Test",
        "genre": "Subwoofer Bass Test",
        "target": "Europe",
        "vocal": "Deep Male Narrator",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (UK)",
        "bass": "20Hz-40Hz Ultra Low Bass",
        "mood": "Dark Cinematic",
        "bpm": "128",
        "extra": "Dark cinematic subwoofer challenge, long looped drops, minimal narrator, extreme low frequency pressure, no normal song lyrics."
    },
    "My Nordic Folk Cinematic Bass": {
        "creation_mode": "Rewrite / Translate Lyrics from YouTube",
        "output_mode": "Extended Mix",
        "genre": "Nordic Folk Cinematic Bass",
        "target": "Europe",
        "vocal": "Female Vocal",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (UK)",
        "bass": "Heavy Bass",
        "mood": "Emotional Cinematic",
        "bpm": "100",
        "extra": "Nordic folk atmosphere, cinematic storytelling, acoustic textures, deep cinematic bass, European emotional sound."
    },
    "My K-Pop EDM Global": {
        "creation_mode": "Original Song",
        "output_mode": "Full Song",
        "genre": "K-Pop EDM",
        "target": "Global",
        "vocal": "Male + Female Duet",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (US)",
        "bass": "Heavy Bass",
        "mood": "Futuristic Neon",
        "bpm": "128",
        "extra": "Korean and English bilingual lyrics, idol group energy, catchy English hook, Korean verses, rap section, dance break, Seoul pop production."
    },
    "My Melodic Techno Germany": {
        "creation_mode": "Rewrite / Translate Lyrics from YouTube",
        "output_mode": "Extended Mix",
        "genre": "Melodic Techno",
        "target": "Europe",
        "vocal": "Minimal Vocal Guide",
        "source_language": "Auto Detect from YouTube",
        "target_language": "German",
        "market_language": "German",
        "bass": "Heavy Bass",
        "mood": "European Club Atmosphere",
        "bpm": "124",
        "extra": "German market, melodic techno, hypnotic arpeggios, emotional club atmosphere, minimal vocal, deep European night sound."
    },
    "My Afro House Europe": {
        "creation_mode": "Original Song",
        "output_mode": "Extended Mix",
        "genre": "Afro House",
        "target": "Europe",
        "vocal": "Female Vocal",
        "source_language": "Auto Detect from YouTube",
        "target_language": "English",
        "market_language": "English (UK)",
        "bass": "Heavy Bass",
        "mood": "Luxury Night Drive",
        "bpm": "122",
        "extra": "Premium Afro House, organic percussion, warm groove, emotional vocal, luxury European club atmosphere."
    }
}

custom_presets = load_custom_presets()
all_presets = {}
all_presets.update(BUILTIN_PRESETS)
all_presets.update(custom_presets)

# -----------------------------
# PRESET UI
# -----------------------------
st.subheader("Preset Engine")

preset_options = list(all_presets.keys())
last_preset = config.get("last_preset", "Custom Manual")
preset_name = st.selectbox(
    "Pilih Preset",
    preset_options,
    index=index_or_default(preset_options, last_preset)
)
preset = all_presets[preset_name]

st.caption("Preset bawaan tidak bisa dihapus. Custom preset tersimpan di file custom_presets.json.")

# -----------------------------
# DEFAULT VALUES PRIORITY
# config last settings > selected preset > fallback
# -----------------------------
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
    creation_mode = st.selectbox(
        "Creation Mode",
        creation_modes,
        index=index_or_default(creation_modes, default_creation_mode)
    )

    output_mode = st.selectbox(
        "Output Mode",
        output_modes,
        index=index_or_default(output_modes, default_output_mode)
    )

    genre = st.selectbox(
        "Genre Musik",
        genres,
        index=index_or_default(genres, default_genre)
    )

    target = st.selectbox(
        "Target Audience",
        targets,
        index=index_or_default(targets, default_target)
    )

    vocal = st.selectbox(
        "Vocal Type",
        vocals,
        index=index_or_default(vocals, default_vocal)
    )

with col2:
    source_language = st.selectbox(
        "Source Language",
        source_languages,
        index=index_or_default(source_languages, default_source_language)
    )

    target_language = st.selectbox(
        "Target Lyrics Language",
        target_languages,
        index=index_or_default(target_languages, default_target_language)
    )

    market_language = st.selectbox(
        "Market Language for Title / Description / Thumbnail",
        market_languages,
        index=index_or_default(market_languages, default_market_language)
    )

    bass = st.selectbox(
        "Bass Level",
        bass_levels,
        index=index_or_default(bass_levels, default_bass)
    )

    mood = st.selectbox(
        "Mood / Energy",
        moods,
        index=index_or_default(moods, default_mood)
    )

    bpm = st.text_input("BPM", default_bpm if "default_bpm" in globals() else preset.get("bpm", "130"))

st.subheader("Batch Generate Engine")

batch_col1, batch_col2 = st.columns(2)

with batch_col1:
    batch_count = st.selectbox(
        "Number of Variations",
        batch_counts,
        index=index_or_default(batch_counts, config.get("last_batch_count", 1)) if "config" in globals() else 0
    )

with batch_col2:
    batch_strategy = st.selectbox(
        "Batch Strategy",
        batch_strategies,
        index=index_or_default(batch_strategies, config.get("last_batch_strategy", "Single Best Output")) if "config" in globals() else 0
    )

advisor_mode = st.selectbox(
    "Prompt Advisor Mode",
    advisor_modes,
    index=index_or_default(advisor_modes, config.get("last_advisor_mode", "Current Setup Audit")) if "config" in globals() else 0
)

youtube_link = st.text_input("YouTube Reference Link")

st.subheader("YouTube Intelligence Engine")

yt_col1, yt_col2 = st.columns(2)

with yt_col1:
    if st.button("Analyze YouTube Metadata / Transcript", use_container_width=True):
        video_id = extract_youtube_video_id(youtube_link)
        st.session_state["youtube_video_id"] = video_id

        if not youtube_link.strip():
            st.error("Masukkan YouTube link dulu.")
        elif not video_id:
            st.error("Video ID tidak terbaca dari link YouTube.")
        else:
            with st.spinner("Mengambil metadata dan transcript YouTube..."):
                metadata = fetch_youtube_oembed(youtube_link)
                transcript_result = fetch_youtube_transcript(video_id)

            st.session_state["youtube_metadata"] = metadata
            st.session_state["youtube_transcript_result"] = transcript_result

with yt_col2:
    if st.button("Clear YouTube Preview", use_container_width=True):
        st.session_state["youtube_video_id"] = ""
        st.session_state["youtube_metadata"] = {}
        st.session_state["youtube_transcript_result"] = {}
        st.success("Preview YouTube dibersihkan.")

youtube_video_id = st.session_state.get("youtube_video_id", "")
youtube_metadata = st.session_state.get("youtube_metadata", {})
youtube_transcript_result = st.session_state.get("youtube_transcript_result", {})

youtube_metadata_text = ""
youtube_transcript_text = ""

if youtube_metadata:
    if "error" in youtube_metadata:
        st.warning("Metadata YouTube tidak berhasil diambil.")
        st.code(youtube_metadata.get("error", "Unknown error"))
    else:
        youtube_metadata_text = f"""Title: {youtube_metadata.get("title", "")}
Author / Channel: {youtube_metadata.get("author_name", "")}
Provider: {youtube_metadata.get("provider_name", "")}
Video ID: {youtube_video_id}
"""
        with st.expander("YouTube Metadata Preview"):
            st.text_area("Metadata", youtube_metadata_text, height=120)

if youtube_transcript_result:
    if youtube_transcript_result.get("success"):
        youtube_transcript_text = youtube_transcript_result.get("text", "")
        st.success(f"Transcript berhasil diambil. Language: {youtube_transcript_result.get('language', '')}")
        with st.expander("YouTube Transcript Preview"):
            st.text_area("Transcript", youtube_transcript_text, height=260)
    else:
        st.warning("Transcript YouTube belum berhasil diambil.")
        st.code(youtube_transcript_result.get("error", ""))

extra_style = st.text_area(
    "Extra Style / Instruksi Tambahan",
    value=default_extra,
    height=120,
    placeholder="Contoh: Make it emotional Future Rave, female vocal, European festival energy, no car audio theme."
)

manual_lyrics = st.text_area(
    "Optional: Paste Lyrics / Transcript Manual jika YouTube transcript tidak terbaca",
    height=180
)

# -----------------------------
# SAVE CURRENT SETTINGS
# -----------------------------
if st.button("Save Current Settings", use_container_width=True):
    config.update({
        "gemini_api_key": api_key,
        "model_name": model_name,
        "last_preset": preset_name,
        "last_creation_mode": creation_mode,
        "last_output_mode": output_mode,
        "last_genre": genre,
        "last_target": target,
        "last_vocal": vocal,
        "last_source_language": source_language,
        "last_target_language": target_language,
        "last_market_language": market_language,
        "last_bass": bass,
        "last_mood": mood,
        "last_bpm": bpm,
        "last_extra": extra_style,
        "last_batch_count": batch_count,
        "last_batch_strategy": batch_strategy,
        "last_advisor_mode": advisor_mode
    })
    save_config(config)
    st.success("Setting terakhir berhasil disimpan ke config.json.")

# -----------------------------
# CUSTOM PRESET SAVE / DELETE
# -----------------------------
st.divider()
st.subheader("Custom Preset Manager")

preset_col1, preset_col2 = st.columns(2)

with preset_col1:
    new_preset_name = st.text_input("Nama Custom Preset Baru", placeholder="Contoh: My German Future Rave")
    if st.button("Save Current Setting as Custom Preset", use_container_width=True):
        if not new_preset_name.strip():
            st.error("Isi nama preset dulu.")
        else:
            custom_presets[new_preset_name.strip()] = {
                "creation_mode": creation_mode,
                "output_mode": output_mode,
                "genre": genre,
                "target": target,
                "vocal": vocal,
                "source_language": source_language,
                "target_language": target_language,
                "market_language": market_language,
                "bass": bass,
                "mood": mood,
                "bpm": bpm,
                "extra": extra_style,
                "batch_count": batch_count,
                "batch_strategy": batch_strategy
            }
            save_custom_presets(custom_presets)
            st.success("Custom preset berhasil disimpan. Refresh aplikasi untuk melihat preset baru di daftar.")

with preset_col2:
    custom_names = list(custom_presets.keys())
    if custom_names:
        delete_preset_name = st.selectbox("Hapus Custom Preset", custom_names)
        if st.button("Delete Selected Custom Preset", use_container_width=True):
            if delete_preset_name in custom_presets:
                del custom_presets[delete_preset_name]
                save_custom_presets(custom_presets)
                st.success("Custom preset berhasil dihapus. Refresh aplikasi untuk memperbarui daftar.")
    else:
        st.info("Belum ada custom preset.")

st.divider()

# -----------------------------
# GENRE RULES ENGINE
# -----------------------------
genre_rules = {
    "Future Rave": """
Future Rave only: emotional festival anthem, supersaw leads, big-room drop, powerful kick, euphoric build-up, club energy, European rave atmosphere.
Do not turn it into car audio, normal pop, or generic EDM.
""",
    "EDM Festival": """
EDM Festival only: massive crowd energy, anthem hook, festival drums, melodic drop, wide synths, high-energy arrangement, strong build-up, global festival sound.
""",
    "Big Room EDM": """
Big Room EDM only: huge kick, simple powerful melody, stadium energy, massive build-up, explosive drop, chantable hook, festival peak-time sound.
""",
    "Progressive House": """
Progressive House only: emotional chord progression, uplifting build, smooth groove, melodic lead, wide atmosphere, festival-friendly but elegant.
""",
    "Melodic Techno": """
Melodic Techno only: hypnotic groove, deep synth arpeggios, emotional progression, dark club atmosphere, modern European underground sound.
""",
    "Afro House": """
Afro House only: organic percussion, warm groove, melodic atmosphere, deep rhythm, tribal-inspired but modern and premium, European club-friendly.
""",
    "Deep House": """
Deep House only: warm bassline, smooth groove, soulful atmosphere, relaxed club energy, elegant vocal chops, late-night European lounge feel.
""",
    "Tech House": """
Tech House only: punchy groove, rolling bassline, minimal vocal hook, club-focused drums, strong rhythm, underground dancefloor energy.
""",
    "Trance": """
Trance only: uplifting melody, long emotional build-up, euphoric breakdown, arpeggiated leads, powerful release, classic European energy.
""",
    "Eurodance 90s/2000s": """
Eurodance only: 90s/2000s European dance energy, catchy chorus, driving beat, bright synths, nostalgic club feeling, male rap/female hook optional.
""",
    "Hardstyle": """
Hardstyle only: distorted hard kick, euphoric melody, dramatic build-up, festival energy, powerful reverse bass, intense drop.
""",
    "Drum and Bass": """
Drum and Bass only: fast breakbeats, deep rolling bass, energetic rhythm, modern UK/EU sound, atmospheric intro, high-speed drop.
""",
    "UK Garage": """
UK Garage only: shuffled drums, 2-step groove, chopped vocal, deep bassline, smooth urban UK club energy.
""",
    "Future Garage": """
Future Garage only: atmospheric pads, emotional vocal chops, deep sub-bass, broken garage rhythm, rainy night mood, cinematic texture.
""",
    "Synthwave": """
Synthwave only: retro 80s synths, neon night drive, analog bass, nostalgic cinematic atmosphere, steady electronic groove.
""",
    "Industrial Techno": """
Industrial Techno only: dark warehouse energy, hard mechanical drums, distorted synths, aggressive underground atmosphere, minimal vocals.
""",
    "Car Audio Subwoofer Test": """
Car Audio Subwoofer Test only: deep narrator, long instrumental sections, low-frequency pressure, subwoofer showcase, SPL/SQL audio test.
Mandatory Bass Test Looping Engine must be used. No normal song lyrics.
""",
    "Subwoofer Bass Test": """
Subwoofer Bass Test only: minimal narrator lines, extended bass drops, 20Hz-40Hz pressure, speaker test energy, instrumental focus.
Mandatory Bass Test Looping Engine must be used. No normal song lyrics.
""",
    "Home Theater Bass Test": """
Home Theater Bass Test only: cinematic surround energy, channel separation test, deep LFE pressure, minimal narrator, long instrumental test sections.
Mandatory Bass Test Looping Engine must be used.
""",
    "Dolby Surround Bass Test": """
Dolby Surround Bass Test only: cinematic spatial audio, 5.1/7.1 surround feeling, LFE sub-bass, panning test, minimal narrator, long instrumental loops.
Mandatory Bass Test Looping Engine must be used.
""",
    "Pop": """
Pop only: catchy chorus, emotional verse, commercial melody, clean radio structure, global mainstream sound.
""",
    "European Pop Dance": """
European Pop Dance only: catchy pop vocal, danceable rhythm, clean chorus, European radio sound, polished production, club-friendly hook.
""",
    "Cinematic Pop": """
Cinematic Pop only: emotional vocal, orchestral atmosphere, big chorus, dramatic arrangement, modern pop polish, trailer-like energy.
""",
    "Indie Pop": """
Indie Pop only: intimate vocal, dreamy guitar/synth texture, catchy but softer chorus, emotional alternative atmosphere.
""",
    "K-Pop EDM": """
K-Pop EDM only.

Create authentic modern Korean idol music mixed with premium EDM production.

Mandatory rules:
- Use Korean + English bilingual lyrics.
- Korean verses are required.
- English hook phrases are required.
- Include catchy repeated chorus.
- Include short rap section.
- Include idol-style ad-libs.
- Include dance break section.
- Female idol, male idol, or mixed idol group energy.
- Bright polished Seoul pop production.
- Modern EDM drop.
- Layered harmonies.
- Radio-ready commercial quality.
- Global K-Pop audience appeal.
- Do NOT create normal EDM lyrics.
- Do NOT create Future Rave lyrics.
- Must feel like real K-Pop.
""",
    "Hip-Hop / Trap": """
Hip-Hop / Trap only: modern 808s, tight drums, confident vocal rhythm, urban atmosphere, catchy rap/pop hook, dark or luxury energy.
""",
    "Boom Bap Hip-Hop": """
Boom Bap Hip-Hop only: 90s-inspired drums, dusty sample feel, lyrical flow, warm bassline, street storytelling, classic hip-hop groove.
""",
    "Trap Soul": """
Trap Soul only: smooth emotional vocal, moody 808s, late-night R&B atmosphere, melodic rap/singing blend, intimate lyrics.
""",
    "Drift Phonk": """
Drift Phonk only: aggressive cowbell, distorted 808, dark driving atmosphere, car drift energy, slow heavy phonk beat.
""",
    "Jazz Hop": """
Jazz Hop only: mellow jazz chords, dusty drums, sax/piano textures, chill groove, late-night study/cafe atmosphere, instrumental-friendly.
""",
    "Lo-Fi Jazz": """
Lo-Fi Jazz only: soft jazz harmony, vinyl texture, warm Rhodes, relaxed drum loop, cozy rainy night atmosphere.
""",
    "Chillhop": """
Chillhop only: relaxing hip-hop groove, soft samples, warm bass, study/work atmosphere, smooth melodic loop.
""",
    "Smooth Jazz Electronic": """
Smooth Jazz Electronic only: elegant sax/piano, soft electronic drums, smooth bass, premium lounge mood, clean modern mix.
""",
    "Country Pop": """
Country Pop only: acoustic guitar, heartfelt storytelling, polished pop chorus, American road/countryside feeling, emotional vocal.
""",
    "Dark Country": """
Dark Country only: gritty acoustic guitar, dark western atmosphere, deep storytelling, cinematic tension, raw vocal emotion.
""",
    "Rock Country Hybrid": """
Rock Country Hybrid only: acoustic guitar, gritty vocal emotion, cinematic country-rock atmosphere, strong storytelling, powerful chorus.
""",
    "Alternative Rock": """
Alternative Rock only: guitar-driven energy, emotional vocal, powerful chorus, modern rock drums, raw but polished production.
""",
    "Nordic Folk Cinematic Bass": """
Nordic Folk Cinematic Bass only: Scandinavian atmosphere, acoustic folk textures, cinematic drones, emotional storytelling, deep sub-bass support.
Do not turn it into normal EDM.
""",
    "Cinematic Folk": """
Cinematic Folk only: acoustic storytelling, orchestral atmosphere, emotional melody, earthy texture, cinematic build.
""",
    "Latin House": """
Latin House only: Latin percussion, dance groove, warm vocal, club-ready rhythm, summer energy, elegant modern production.
""",
    "Amapiano": """
Amapiano only: log drum bass, South African groove, smooth keys, percussive rhythm, warm dance atmosphere.
""",
    "Organic House": """
Organic House only: natural percussion, deep melodic groove, warm pads, spiritual atmosphere, elegant festival/lounge energy.
""",
    "Reggaeton Pop": """
Reggaeton Pop only: dembow rhythm, catchy vocal hook, Latin pop energy, danceable beat, polished commercial production.
"""
}

selected_genre_rule = genre_rules.get(genre, "")

# -----------------------------
# SPECIAL STRUCTURE ENGINE
# -----------------------------
bass_test_structure = """
BASS TEST LOOPING ENGINE - MANDATORY FOR BASS TEST / SUBWOOFER / CAR AUDIO:
- The track must NOT start with lyrics or long narration.
- Start with a long instrumental intro loop.
- Use very short narrator cues only.
- 90% instrumental / 10% narrator maximum.
- Long loop sections are mandatory.
- Drop sections must be longer than vocal sections.
- Include frequency sweep and subwoofer pressure moments.
- Use loop-friendly arrangement for long YouTube videos.

Required structure:
[Intro - Long Instrumental Loop]
[System Warm Up - No Vocal]
[Low Frequency Sweep - 20Hz to 40Hz]
[Build Up Loop]
[Short Narrator Cue]
[First Bass Drop]
[Long Instrumental Bass Loop]
[Breakdown - Air Pressure Moment]
[Subwoofer Pressure Loop]
[Second Build Up Loop]
[Huge Bass Drop]
[Extended Car Audio Showcase]
[Final Bass Loop]
[Outro Loop]
"""

kpop_structure = """
K-POP EDM SPECIAL ENGINE:
- Lyrics MUST contain Korean and English.
- Korean verses are mandatory.
- English hook phrases are mandatory.
- Include K-Pop style repetition.
- Include short rap section.
- Include idol group vocal energy.
- Include ad-libs.
- Include dance break.
- Do NOT generate plain EDM lyrics.
- Do NOT generate Future Rave lyrics.
- Do NOT generate Western-only lyrics.
- The song must feel like modern K-Pop.

Required structure:
[Intro]
[Verse 1 - Korean]
[Pre-Chorus - Korean + English]
[Chorus - English Hook + Korean]
[EDM Dance Break]
[Rap Verse - Korean + English]
[Bridge]
[Final Chorus]
[Dance Break Outro]
[Outro]
"""


# -----------------------------
# DROPDOWN OPTIONS TEXT FOR AI ADVISOR
# -----------------------------
available_options_text = f"""
AVAILABLE DROPDOWN OPTIONS IN THIS APP:

Creation Mode:
{", ".join(creation_modes)}

Output Mode:
{", ".join(output_modes)}

Genre Musik:
{", ".join(genres)}

Target Audience:
{", ".join(targets)}

Vocal Type:
{", ".join(vocals)}

Source Language:
{", ".join(source_languages)}

Target Lyrics Language:
{", ".join(target_languages)}

Market Language:
{", ".join(market_languages)}

Bass Level:
{", ".join(bass_levels)}

Mood / Energy:
{", ".join(moods)}

Batch Variations:
{", ".join([str(x) for x in batch_counts])}

Batch Strategy:
{", ".join(batch_strategies)}
"""

# -----------------------------
# MASTER PROMPT
# -----------------------------
master_prompt = f"""
You are a professional AI music prompt engineer, Suno AI specialist,
YouTube metadata and transcript analyst, international lyric adaptation expert,
YouTube music SEO strategist, and cinematic thumbnail prompt designer.

Create a complete music content package based on the inputs below.

APP VERSION:
Music Prompt Studio Pro v2.5.4.1

PRESET NAME:
{preset_name}

CREATION MODE:
{creation_mode}

OUTPUT MODE:
{output_mode}

BATCH VARIATIONS:
{batch_count}

BATCH STRATEGY:
{batch_strategy}

PROMPT ADVISOR MODE:
{advisor_mode}

MAIN SELECTED GENRE:
{genre}

GENRE RULE:
{selected_genre_rule}

TARGET AUDIENCE:
{target}

VOCAL TYPE:
{vocal}

SOURCE LANGUAGE:
{source_language}

TARGET LYRICS LANGUAGE:
{target_language}

MARKET LANGUAGE FOR TITLE / DESCRIPTION / THUMBNAIL:
{market_language}

BASS LEVEL:
{bass}

MOOD / ENERGY:
{mood}

BPM:
{bpm}

YOUTUBE REFERENCE LINK:
{youtube_link}

YOUTUBE METADATA PREVIEW FROM APP:
{youtube_metadata_text}

YOUTUBE TRANSCRIPT PREVIEW FROM APP:
{youtube_transcript_text}

USER EXTRA STYLE / REFERENCE NOTES:
{extra_style}

MANUAL LYRICS / TRANSCRIPT BACKUP:
{manual_lyrics}


BATCH GENERATE ENGINE:
- If BATCH VARIATIONS is 1, create one complete best output.
- If BATCH VARIATIONS is 3, 5, 10, or 20, create that exact number of complete variations.
- Each variation must include all required output sections:
  1. YouTube Reference Analysis
  2. Suno Style Metadata
  3. Lyrics + Structure Tags
  4. YouTube SEO Titles
  5. YouTube Description
  6. Tags and Keywords
  7. Background Image Prompt
  8. Thumbnail Prompt
  9. Quality Check
- Each variation must be meaningfully different, not just small word changes.
- Variation names must be clear, for example:
  Variation 1 - Festival Anthem Version
  Variation 2 - Dark Club Version
  Variation 3 - Emotional Vocal Version

BATCH STRATEGY RULES:
- Single Best Output: create only the strongest single version.
- Random Creative Variations: create different creative angles, moods, hooks, arrangements, and title concepts.
- Genre Expansion: keep the selected main genre, but explore different sub-styles inside that genre.
- Audience Expansion: create versions optimised for different audiences such as USA, UK, Germany, France, Netherlands, Italy, and Global.
- Language Expansion: create variations using different lyrics/market language combinations while respecting the selected target language when required.
- Commercial Expansion: create platform-specific versions such as YouTube Long Mix, Spotify Version, TikTok Hook Version, Festival Version, Radio Edit, Club Version, and Thumbnail-Focused Version.
- Never break the selected MAIN GENRE rule.
- Never turn non-bass genres into car audio or subwoofer test.
- For Bass Test genres, every variation must keep long instrumental loops and minimal narrator.

LANGUAGE OUTPUT RULES:
- TARGET LYRICS LANGUAGE controls the song lyrics language.
- MARKET LANGUAGE controls:
  * YouTube SEO Titles
  * YouTube Description
  * Thumbnail Text
  * Call-To-Action text
- If MARKET LANGUAGE is German, create titles, descriptions, thumbnail text, and CTA in natural German.
- If MARKET LANGUAGE is French, create titles, descriptions, thumbnail text, and CTA in natural French.
- If MARKET LANGUAGE is Spanish, create titles, descriptions, thumbnail text, and CTA in natural Spanish.
- If MARKET LANGUAGE is Dutch, create titles, descriptions, thumbnail text, and CTA in natural Dutch.
- If MARKET LANGUAGE is Italian, create titles, descriptions, thumbnail text, and CTA in natural Italian.
- If MARKET LANGUAGE is Indonesian, create titles, descriptions, thumbnail text, and CTA in natural Indonesian.
- If MARKET LANGUAGE is English (US), use American English.
- If MARKET LANGUAGE is English (UK), use British English.
- If MARKET LANGUAGE is bilingual, mix both languages naturally for title and description.
- Tags and keywords should be 70% in MARKET LANGUAGE and 30% English SEO keywords.

VERY IMPORTANT YOUTUBE ADAPTATION ENGINE:
- If YOUTUBE TRANSCRIPT PREVIEW FROM APP is available, use it as the highest-priority lyrical reference.
- If YOUTUBE METADATA PREVIEW FROM APP is available, use it as the highest-priority metadata reference.
- If Creation Mode is "Rewrite / Translate Lyrics from YouTube", treat the YouTube transcript, captions, metadata, title, and description as the main reference.
- First analyze available YouTube metadata, title, description, transcript, captions, audio mood, vocal language, music genre, song structure, hook placement, and emotional direction.
- If transcript, captions, or lyrics are available from the YouTube video, use them as the main lyrical reference.
- If the YouTube transcript is Indonesian, rewrite the meaning into the selected Target Lyrics Language.
- If the target language is English, rewrite into natural, polished, singable American English.
- If the target language is German, French, Spanish, Dutch, or Italian, rewrite into natural modern pop/EDM phrasing in that language.
- Do not copy original lyrics exactly.
- Do not provide literal word-for-word translation.
- Preserve emotional meaning, story, theme, hook idea, and song progression.
- Make final lyrics original and copyright-safe.
- If YouTube transcript/captions are not accessible, clearly say: "YouTube transcript was not accessible, using manual lyrics or user notes instead."
- If manual lyrics are provided, use them as the main lyrical reference when YouTube transcript is not accessible.

STRICT GENRE RULES:
- The MAIN SELECTED GENRE is the highest priority.
- Follow the GENRE RULE strictly.
- Do NOT turn the result into Car Audio Test unless selected genre is Car Audio/Subwoofer/Home Theater/Dolby Bass Test, or Output Mode is Bass Test.
- Lyrics must match the selected genre, not a different genre.
- For Bass Test genres only, lyrics should be minimal narrator-style lines.
- For Instrumental mode, use only short vocal guide phrases and mostly instrumental structure.

OUTPUT MODE RULES:
- Full Song: complete song lyrics with standard structure.
- Extended Mix: longer build-ups, longer drops, extended instrumental sections.
- DJ Festival Mix: stronger crowd energy, festival call-outs, big drop moments.
- Radio Edit: shorter, hook-focused, catchy, commercial structure.
- Bass Test: minimal narrator lines, long bass drops, instrumental testing sections.
- Instrumental: mostly instrumental, only short vocal guide phrases.

SPECIAL ENGINE RULES:
{bass_test_structure if ("Bass Test" in genre or "Subwoofer" in genre or "Car Audio" in genre or "Dolby" in genre or "Home Theater" in genre or output_mode == "Bass Test") else ""}

{kpop_structure if genre == "K-Pop EDM" else ""}

COPYRIGHT SAFETY RULES:
- Do not copy any original lyric line exactly.
- Do not imitate original artist name, song title, or protected branding.
- Use source only for meaning, emotion, structure, and inspiration.
- Final output must be original enough for new music creation.

OUTPUT FORMAT:

If BATCH VARIATIONS is more than 1, repeat the full output format for each variation.
Use this format:

VARIATION 1 - [Clear Version Name]

1. YOUTUBE REFERENCE ANALYSIS
Briefly summarize:
- Detected language
- Main emotion
- Possible story/message
- Song structure
- Vocal style
- Genre/mood inspiration
- Whether transcript was accessible or not

2. SUNO STYLE METADATA
Put inside one clean code block.
Maximum 999 characters.
Must match the selected genre.
Must be ready to copy into Suno AI style prompt.

3. LYRICS + STRUCTURE TAGS
Create complete rewritten lyrics in TARGET LYRICS LANGUAGE.
Use structure tags suitable for selected genre and output mode.
For bass test, use BASS TEST LOOPING ENGINE structure and keep narrator minimal.
For K-Pop EDM, use Korean + English bilingual lyrics and K-Pop structure.

4. YOUTUBE SEO TITLES
Create 10 SEO-friendly titles in MARKET LANGUAGE.
Titles must match selected genre, output mode, target audience, and video concept.

5. YOUTUBE DESCRIPTION
Create a professional YouTube description in MARKET LANGUAGE.
Use 2-4 paragraphs.
Add warning note if the content is bass test / subwoofer test.
Add CTA in MARKET LANGUAGE.

6. TAGS AND KEYWORDS
Create many SEO tags and keywords separated by commas.
Use 70% MARKET LANGUAGE and 30% English SEO keywords.

7. BACKGROUND IMAGE PROMPT
Create a cinematic 16:9 image prompt with no text, matching selected genre.
Always specify: no text, no logo, no watermark.

8. THUMBNAIL PROMPT
Create a 16:9 YouTube thumbnail prompt with clear text overlay in MARKET LANGUAGE.
Make text short, bold, readable, mobile-friendly, and SEO-focused.

9. QUALITY CHECK
Give short ratings:
- Genre Accuracy: /100
- Lyrics Adaptation: /100
- Suno Compatibility: /100
- SEO Strength: /100
- Thumbnail Clarity: /100
- Overall Score: /100
"""


# -----------------------------
# PROMPT INTELLIGENCE ANALYZER + OPTIMIZER
# -----------------------------
st.divider()
st.subheader("Separated Advisor + 90 Plus Optimizer")
st.caption("Analyze = mencari masalah. Optimize to 90+ = membuat setting pengganti dan versi setelah perbaikan, bukan mengulang skor lama.")

intelligence_prompt = f"""
You are a senior AI music producer, Suno AI prompt engineer, YouTube SEO strategist,
music market analyst, and prompt improvement advisor for Europe and USA.

Your job is NOT only to score the prompt.
Your job is to explain WHY each score is low and EXACTLY what settings must be changed
to reach a target score of 90/100 or higher.

Analyze the current music project settings below.

PRESET NAME:
{preset_name}

CREATION MODE:
{creation_mode}

OUTPUT MODE:
{output_mode}

BATCH VARIATIONS:
{batch_count}

BATCH STRATEGY:
{batch_strategy}

PROMPT ADVISOR MODE:
{advisor_mode}

MAIN SELECTED GENRE:
{genre}

GENRE RULE:
{selected_genre_rule}

TARGET AUDIENCE:
{target}

VOCAL TYPE:
{vocal}

SOURCE LANGUAGE:
{source_language}

TARGET LYRICS LANGUAGE:
{target_language}

MARKET LANGUAGE:
{market_language}

BASS LEVEL:
{bass}

MOOD / ENERGY:
{mood}

BPM:
{bpm}

YOUTUBE LINK:
{youtube_link}

YOUTUBE METADATA:
{youtube_metadata_text if "youtube_metadata_text" in globals() else ""}

YOUTUBE TRANSCRIPT PREVIEW:
{youtube_transcript_text[:4000] if "youtube_transcript_text" in globals() else ""}

EXTRA STYLE:
{extra_style}

MANUAL LYRICS:
{manual_lyrics[:4000]}

{available_options_text}

TASK:
Do not generate the full song package.
Analyze the current setup and give a practical improvement plan.
The user wants to know which settings must be changed to reach 90/100 or higher.

DROPDOWN-AWARE ADVISOR RULES:
- You MUST only recommend values that exist in AVAILABLE DROPDOWN OPTIONS IN THIS APP.
- Do NOT invent new dropdown values.
- If your ideal recommendation is not available, choose the closest available option and explain why.
- For example, if you want "Late-Night Club Groove" but it is not available, choose "Luxury Night Drive", "Relaxing Late Night", or "European Club Atmosphere".
- For Target Audience, only use: Europe, USA, Global, Indonesia.
- For Mood / Energy, only use the listed Mood / Energy options.
- For Genre Musik, only use the listed Genre Musik options.
- For Batch Strategy, only use the listed Batch Strategy options.
- Every "Recommended" setting must be copyable directly into the app dropdown.

STABLE SCORING CALIBRATION RULES:
- Do NOT give random low scores without direct evidence from the selected settings or user text.
- Do NOT punish the user for missing YouTube transcript if Creation Mode is Original Song.
- Do NOT score Lyrics Adaptation low if no source lyrics are required.
- Do NOT punish USA Market Fit if Target Audience is Europe, unless the user explicitly wants USA.
- Do NOT punish European Market Fit if Target Audience is USA, unless the user explicitly wants Europe.
- If the user already followed the previous recommendation, score the relevant area higher unless there is a clear remaining conflict.
- A score below 70 requires a specific concrete reason and a specific setting conflict.
- A score below 50 is only allowed for severe contradictions, such as selecting K-Pop EDM but forbidding Korean, or selecting Bass Test but requesting full pop lyrics.
- If settings are internally consistent, baseline scores should usually be 80-90.
- If settings are internally consistent and the Extra Style is focused, target score should be 90+.
- Always separate CURRENT SCORE from EXPECTED SCORE AFTER FIX.
- In After Optimization Validation mode, validate whether the current settings match the recommended 90+ setup. If they do, give improved scores.

OUTPUT FORMAT:

1. CURRENT SCORE SUMMARY
Give scores and one-line reason for each score.
IMPORTANT: Use STABLE SCORING CALIBRATION RULES.
If a score is below 70, the reason must mention an exact setting conflict.
If there is no exact conflict, do not score below 70.

- Overall Score: /100 + reason
- Genre Accuracy: /100 + reason
- Suno Compatibility: /100 + reason
- Commercial Potential: /100 + reason
- SEO Potential: /100 + reason
- European Market Fit: /100 + reason
- USA Market Fit: /100 + reason
- Originality Score: /100 + reason
- YouTube Potential: /100 + reason

2. WHY THE SCORE IS LOW
For every score below 90, explain:
- What is causing the low score?
- Which setting is conflicting?
- Which instruction is too weak, too broad, or contradictory?
- Is the problem caused by genre conflict, language conflict, market mismatch, unclear hook, weak SEO, or Suno prompt overload?

Use this format:
Score Area:
Current Score:
Main Problem:
Cause:
Impact:

3. SETTINGS TO CHANGE FOR 90+
Give exact recommended setting changes.
IMPORTANT: Recommended values MUST exist in AVAILABLE DROPDOWN OPTIONS.

Use this format:

CHANGE 1
Setting:
Current:
Recommended:
Why:
Expected Score Improvement:

CHANGE 2
Setting:
Current:
Recommended:
Why:
Expected Score Improvement:

Include these settings when relevant:
- Creation Mode
- Output Mode
- Genre Musik
- Target Audience
- Vocal Type
- Source Language
- Target Lyrics Language
- Market Language
- Bass Level
- Mood / Energy
- BPM
- Batch Variations
- Batch Strategy
- Extra Style / Instruksi Tambahan
- Manual Lyrics / Transcript Backup

4. WHAT TO REMOVE
List words, genres, instructions, or style conflicts that should be removed.
Example:
Remove:
- Dark Country
- Drift Phonk
- Too much cinematic orchestral language
- Too many unrelated subgenres

5. WHAT TO ADD
List specific words, style tags, production direction, lyrical direction, SEO angle, and thumbnail angle that should be added.

6. OPTIMAL SETTINGS FOR 90+
Give the ideal final settings using ONLY available dropdown values:

Creation Mode:
Output Mode:
Genre Musik:
Target Audience:
Vocal Type:
Source Language:
Target Lyrics Language:
Market Language:
Bass Level:
Mood / Energy:
BPM:
Batch Variations:
Batch Strategy:

7. REWRITE EXTRA STYLE FIELD
Write a ready-to-copy improved Extra Style / Instruksi Tambahan field.
This must be practical and directly usable in the app.

8. EXPECTED SCORE AFTER FIX
Estimate new scores after applying your recommendations:
- Overall Score: /100
- Genre Accuracy: /100
- Suno Compatibility: /100
- Commercial Potential: /100
- SEO Potential: /100
- European Market Fit: /100
- USA Market Fit: /100
- Originality Score: /100
- YouTube Potential: /100

9. SCORE VALIDATION TABLE
Create a table:
Area | Current Score | Why | Exact Fix | Expected Score After Fix

10. FINAL DECISION
Tell the user:
- Generate now
- Optimize first
- Change settings first
- Add manual transcript
- Change batch strategy
- Change target market

11. IF SCORE IS STILL BELOW 90
If any expected score is still below 90, explain exactly what app dropdown limitation or missing user input prevents 90+.
Do not just repeat low scores.

Be direct and practical.
"""


optimizer_prompt = f"""
You are an elite AI music producer, Suno AI prompt optimizer, YouTube SEO strategist,
and commercial music consultant.

VERY IMPORTANT:
This is the OPTIMIZER button, not the analyzer button.
Do NOT repeat the current low score summary.
Do NOT output the same result as the analysis.
Your job is to CREATE a corrected 90+ version.

You must transform the current weak setup into an optimized setup that can realistically reach 90/100 or higher.

CURRENT SETTINGS:

PRESET NAME:
{preset_name}

CREATION MODE:
{creation_mode}

OUTPUT MODE:
{output_mode}

BATCH VARIATIONS:
{batch_count}

BATCH STRATEGY:
{batch_strategy}

PROMPT ADVISOR MODE:
{advisor_mode}

MAIN SELECTED GENRE:
{genre}

GENRE RULE:
{selected_genre_rule}

TARGET AUDIENCE:
{target}

VOCAL TYPE:
{vocal}

SOURCE LANGUAGE:
{source_language}

TARGET LYRICS LANGUAGE:
{target_language}

MARKET LANGUAGE:
{market_language}

BASS LEVEL:
{bass}

MOOD / ENERGY:
{mood}

BPM:
{bpm}

YOUTUBE LINK:
{youtube_link}

YOUTUBE METADATA:
{youtube_metadata_text if "youtube_metadata_text" in globals() else ""}

YOUTUBE TRANSCRIPT PREVIEW:
{youtube_transcript_text[:4000] if "youtube_transcript_text" in globals() else ""}

EXTRA STYLE:
{extra_style}

MANUAL LYRICS:
{manual_lyrics[:4000]}

{available_options_text}

DROPDOWN-AWARE OPTIMIZER RULES:
- You MUST only recommend settings that exist in AVAILABLE DROPDOWN OPTIONS IN THIS APP.
- Do NOT invent new dropdown values.
- If an ideal musical term is not available as a dropdown option, choose the closest available dropdown option.
- Every recommended dropdown setting must be directly selectable in the app.
- Extra Style may contain creative words, but dropdown recommendations must use existing dropdown values.

90+ OPTIMIZATION RULES:
- Your output must be the corrected version, not the current audit.
- If current settings conflict, replace them with compatible settings.
- If Creation Mode is "Rewrite / Translate Lyrics from YouTube" but no transcript/manual lyrics exist, recommend either:
  A) Change Creation Mode to "Original Song", or
  B) Add Manual Lyrics / Transcript Backup.
- If selected genre is Deep House, do not recommend Festival Energy, Extreme Subwoofer Bass, or aggressive BPM.
- If selected genre is Deep House, prefer:
  Mood / Energy: Luxury Night Drive, Relaxing Late Night, or European Club Atmosphere
  Bass Level: Normal Bass or Heavy Bass
  BPM: 120-124
  Output Mode: Extended Mix or Full Song
- If the genre is a lounge/club genre, optimize for clean groove, warm bass, smooth vocal, and sophisticated mix.
- If the target is Europe, prioritize elegant, clean, club-friendly, market-specific aesthetics.
- Do not punish the optimized setup for missing USA fit if the target audience is Europe.
- Do not score below 90 after optimization unless there is an unavoidable missing input, and explain it clearly.

OUTPUT FORMAT:

1. OPTIMIZATION RESULT
Say clearly:
"Optimized setup created. This is the recommended 90+ version."

2. WHY THE PREVIOUS SCORE WAS LOW
Briefly explain the main conflicts in the current setup.
Do not repeat the full score table from the analyzer.

3. EXACT SETTINGS TO CHANGE
Use this exact table:

Setting | Current | Change To | Reason | Expected Improvement

Only use values available in the app dropdown for "Change To".

4. OPTIMAL SETTINGS FOR 90+
Use this exact format:

Creation Mode:
Output Mode:
Genre Musik:
Target Audience:
Vocal Type:
Source Language:
Target Lyrics Language:
Market Language:
Bass Level:
Mood / Energy:
BPM:
Batch Variations:
Batch Strategy:

All values must exist in the app dropdown, except BPM.

5. REWRITE EXTRA STYLE FIELD
Write a ready-to-copy Extra Style field that fixes the problem.
It must be focused, non-contradictory, and optimized for the selected genre.

6. OPTIMIZED SUNO STYLE METADATA
One code block under 999 characters.
Must be clean, genre-focused, and Suno-ready.

7. OPTIMIZED STRUCTURE
Give structure tags suitable for the optimized genre/output mode.

8. OPTIMIZED SEO ANGLE
Give:
- Title angle
- Description angle
- Keyword angle
- Thumbnail text angle
- Market language angle

9. EXPECTED SCORE AFTER OPTIMIZATION
Now score the OPTIMIZED setup, not the old setup:
- Overall Score: /100
- Genre Accuracy: /100
- Suno Compatibility: /100
- Commercial Potential: /100
- SEO Potential: /100
- European Market Fit: /100
- USA Market Fit: /100 or "Not primary target"
- Originality Score: /100
- YouTube Potential: /100

Target: 90+ where possible.

10. COPY-PASTE ACTION PLAN
Give a simple checklist:
1. Change ...
2. Change ...
3. Paste this Extra Style ...
4. Generate again.
"""


intel_col1, intel_col2 = st.columns(2)

with intel_col1:
    if st.button("Analyze Prompt Advisor", use_container_width=True):
        if not api_key:
            st.error("Masukkan Gemini API Key dulu.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                with st.spinner("Gemini AI sedang menganalisis kualitas prompt..."):
                    intel_response = client.models.generate_content(
                        model=model_name,
                        contents=intelligence_prompt
                    )
                intel_text = intel_response.text
                st.session_state["last_prompt_advisor"] = intel_text

                analysis_path = save_history(
                    intel_text,
                    f"{genre}_prompt_advisor",
                    preset_name
                )

                st.success(f"Analisis selesai. Tersimpan: {analysis_path.name}")
            except Exception as e:
                st.error("Terjadi error saat analisis.")
                st.code(str(e))

with intel_col2:
    if st.button("Optimize Prompt to 90+", use_container_width=True):
        if not api_key:
            st.error("Masukkan Gemini API Key dulu.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                with st.spinner("Gemini AI sedang membuat versi optimasi 90+..."):
                    opt_response = client.models.generate_content(
                        model=model_name,
                        contents=optimizer_prompt
                    )
                opt_text = opt_response.text
                st.session_state["last_prompt_optimization"] = opt_text

                opt_path = save_history(
                    opt_text,
                    f"{genre}_prompt_optimization",
                    preset_name
                )

                st.success(f"Optimasi selesai. Tersimpan: {opt_path.name}")
            except Exception as e:
                st.error("Terjadi error saat optimasi.")
                st.code(str(e))

if st.session_state.get("last_prompt_advisor"):
    with st.expander("Prompt Intelligence Advisor Result", expanded=True):
        st.markdown(st.session_state["last_prompt_advisor"])
        st.download_button(
            label="Download Prompt Advisor TXT",
            data=st.session_state["last_prompt_advisor"],
            file_name=f"{safe_filename(genre)}_prompt_advisor.txt",
            mime="text/plain"
        )

if st.session_state.get("last_prompt_optimization"):
    with st.expander("Prompt Optimization 90+ Result", expanded=True):
        st.markdown(st.session_state["last_prompt_optimization"])
        st.download_button(
            label="Download Prompt Optimization 90+ TXT",
            data=st.session_state["last_prompt_optimization"],
            file_name=f"{safe_filename(genre)}_prompt_optimization.txt",
            mime="text/plain"
        )


# -----------------------------
# GENERATE BUTTON
# -----------------------------
if st.button("Generate with Gemini AI", use_container_width=True):
    if not api_key:
        st.error("Masukkan Gemini API Key dulu.")
    else:
        try:
            config.update({
                "gemini_api_key": api_key,
                "model_name": model_name,
                "last_preset": preset_name,
                "last_creation_mode": creation_mode,
                "last_output_mode": output_mode,
                "last_genre": genre,
                "last_target": target,
                "last_vocal": vocal,
                "last_source_language": source_language,
                "last_target_language": target_language,
                "last_market_language": market_language,
                "last_bass": bass,
                "last_mood": mood,
                "last_bpm": bpm,
                "last_extra": extra_style,
                "last_batch_count": batch_count,
                "last_batch_strategy": batch_strategy,
                "last_advisor_mode": advisor_mode
            })
            save_config(config)

            client = genai.Client(api_key=api_key)

            if youtube_link.strip():
                contents_input = [
                    master_prompt,
                    youtube_link.strip()
                ]
            else:
                contents_input = master_prompt

            with st.spinner("Gemini AI sedang membuat prompt, adaptasi lirik, SEO, dan thumbnail..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents_input
                )

            result_text = response.text

            history_path = save_history(result_text, f"{genre}_batch_{batch_count}", preset_name)

            st.success(f"Generate berhasil. History tersimpan: {history_path.name}")

            st.subheader("Hasil Gemini AI")
            st.markdown(result_text)

            st.download_button(
                label="Download Hasil TXT",
                data=result_text,
                file_name=f"{safe_filename(genre)}_music_prompt_result.txt",
                mime="text/plain"
            )

        except Exception as e:
            st.error("Terjadi error.")
            st.code(str(e))

# -----------------------------
# HISTORY VIEWER
# -----------------------------
st.divider()
st.subheader("Recent History")

recent_files = read_recent_history(limit=10)

if not recent_files:
    st.info("Belum ada history. Generate prompt dulu.")
else:
    selected_history = st.selectbox(
        "Pilih history untuk dibaca",
        [file.name for file in recent_files]
    )

    selected_path = HISTORY_DIR / selected_history

    if selected_path.exists():
        with st.expander("Lihat isi history"):
            st.text_area(
                "History Content",
                selected_path.read_text(encoding="utf-8"),
                height=300
            )

        st.download_button(
            label="Download History TXT",
            data=selected_path.read_text(encoding="utf-8"),
            file_name=selected_path.name,
            mime="text/plain"
        )

# -----------------------------
# FOOTER NOTES
# -----------------------------
st.divider()
st.caption("Music Prompt Studio Pro v2.5.4 - Built for Suno AI music workflow, YouTube SEO, European/USA market targeting, custom presets, saved settings, YouTube intelligence preview, batch generation, prompt intelligence, stable dropdown-aware prompt optimization, and bass test content production.")
