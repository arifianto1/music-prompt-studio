import streamlit as st
from google import genai
from datetime import datetime
from pathlib import Path
import json
import re
import urllib.parse
import urllib.request

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

# ============================================================
# MUSIC PROMPT STUDIO PRO v2.6
# New in v2.6:
# - Genre Fusion Engine
# - YouTube Reference + Genre Percentage Mixing
# - Fusion Director 90+
# - Auto Pilot 90+ professional prompt optimizer
# - Compatible with previous v2.5.x workflow concept
# ============================================================

st.set_page_config(
    page_title="Music Prompt Studio Pro v2.6",
    page_icon="🎵",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
HISTORY_DIR = BASE_DIR / "history"
EXPORT_DIR = BASE_DIR / "exports"
CONFIG_FILE = BASE_DIR / "config.json"
CUSTOM_PRESET_FILE = BASE_DIR / "custom_presets.json"

HISTORY_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)


def safe_filename(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:70] if text else "music_prompt"


def read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config():
    return read_json(CONFIG_FILE, {})


def save_config(data):
    write_json(CONFIG_FILE, data)


def load_custom_presets():
    return read_json(CUSTOM_PRESET_FILE, {})


def save_custom_presets(data):
    write_json(CUSTOM_PRESET_FILE, data)


def save_history(content: str, genre_name: str, preset_name: str = "custom") -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}_{safe_filename(preset_name)}_{safe_filename(genre_name)}.txt"
    path = HISTORY_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def read_recent_history(limit=10):
    return sorted(HISTORY_DIR.glob("*.txt"), reverse=True)[:limit]


def index_or_default(options, value, default=0):
    try:
        return options.index(value)
    except Exception:
        return default


def extract_youtube_video_id(url: str) -> str:
    url = str(url).strip()
    if not url:
        return ""
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    return ""


def fetch_youtube_oembed(url: str):
    if not str(url).strip():
        return {}
    try:
        endpoint = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url)
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def fetch_youtube_transcript(video_id: str, preferred_languages=None):
    if preferred_languages is None:
        preferred_languages = ["id", "en", "jv", "ms", "de", "fr", "es", "nl", "it", "ko"]
    if not video_id:
        return {"success": False, "language": "", "text": "", "error": "Video ID kosong atau tidak valid."}
    if YouTubeTranscriptApi is None:
        return {
            "success": False,
            "language": "",
            "text": "",
            "error": "Package youtube-transcript-api belum terinstall. Jalankan: pip install youtube-transcript-api",
        }
    try:
        rows = None
        transcript_language = ""

        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            try:
                rows = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_languages)
                transcript_language = "auto"
            except Exception:
                rows = None

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

        if rows is None:
            try:
                api = YouTubeTranscriptApi()
                rows = api.fetch(video_id)
                transcript_language = "auto"
            except Exception as newer_error:
                return {"success": False, "language": "", "text": "", "error": str(newer_error)}

        lines = []
        for row in rows:
            if isinstance(row, dict):
                text_line = row.get("text", "")
            else:
                text_line = getattr(row, "text", "")
            text_line = str(text_line).replace("\n", " ").strip()
            if text_line:
                lines.append(text_line)
        text = "\n".join(lines)
        if not text.strip():
            return {"success": False, "language": "", "text": "", "error": "Transcript kosong atau tidak bisa dibaca."}
        return {"success": True, "language": transcript_language, "text": text, "error": ""}
    except Exception as e:
        return {"success": False, "language": "", "text": "", "error": str(e)}


GENRE_RULES = {
    "Future Rave": "emotional festival anthem, supersaw leads, big-room drop, powerful kick, euphoric build-up, European rave atmosphere",
    "EDM Festival": "massive crowd energy, anthem hook, festival drums, melodic drop, wide stereo, explosive mainstage sound",
    "Big Room EDM": "huge kick, simple powerful lead, crowd chant energy, festival drop, wide reverb, mainstage impact",
    "Progressive House": "emotional chord progression, smooth build-up, uplifting melody, polished dance production, warm stereo atmosphere",
    "Melodic Techno": "hypnotic arps, dark melodic tension, rolling groove, cinematic synth layers, late-night European club sound",
    "Afro House": "organic percussion, warm groove, deep bass pulse, tribal rhythmic movement, soulful atmosphere",
    "Deep House": "smooth groove, warm bassline, soft chord stabs, elegant night club mood, relaxed vocal tone",
    "Tech House": "punchy groove, tight percussion, rolling bass, minimal vocal hook, club-ready rhythm",
    "Trance": "emotional arpeggios, long build-ups, uplifting breakdown, euphoric drop, high-energy melodic atmosphere",
    "Eurodance 90s/2000s": "catchy piano stabs, energetic beat, nostalgic European dance hook, bright synths, memorable chorus",
    "Hardstyle": "reverse bass, hard kicks, euphoric melody, festival energy, aggressive drop, powerful climax",
    "Drum and Bass": "fast breakbeats, rolling bass, energetic rhythm, atmospheric pads, modern club pressure",
    "UK Garage": "swinging drums, chopped vocals, deep sub bass, urban late-night groove, syncopated rhythm",
    "Future Garage": "emotional chopped vocals, dark atmospheric pads, deep sub, shuffled drums, introspective mood",
    "Synthwave": "retro analog synths, neon night drive mood, 80s drums, cinematic nostalgia, warm bass",
    "Industrial Techno": "brutal kick, metallic percussion, dark warehouse atmosphere, aggressive low-end, hypnotic repetition",
    "Hard Techno": "relentless kick, distorted bass pressure, underground warehouse energy, fast BPM, raw industrial tension",
    "Dark Techno": "deep hypnotic groove, dark synth pulses, low-end pressure, minimal warehouse atmosphere, cinematic tension",
    "European Pop Dance": "commercial pop hooks, polished vocal melody, danceable rhythm, modern European radio-ready production",
    "Cinematic Pop": "emotional vocal, cinematic drums, wide atmosphere, dramatic build-up, polished modern pop sound",
    "Dark Pop": "moody vocal, minor-key hook, sleek electronic production, emotional tension, modern dark radio appeal",
    "K-Pop EDM": "bilingual Korean-English hook, glossy vocal layers, EDM drops, dynamic sections, energetic pop production",
    "Hip-Hop / Trap": "deep 808 bass, crisp hi-hats, modern trap rhythm, urban atmosphere, confident vocal flow",
    "Drift Phonk": "cowbell motif, distorted bass, aggressive drift energy, gritty Memphis-inspired rhythm, night-drive intensity",
    "Car Audio Subwoofer Test": "extreme low bass, 20Hz-40Hz pressure, minimal narrator, long test drops, SPL/SQL subwoofer showcase",
    "Subwoofer Bass Test": "ultra-deep bass sweeps, long sustained low-end drops, clean sub control, minimal vocal guide, speaker test energy",
    "Home Theater Bass Test": "cinematic impact, deep LFE rumble, surround atmosphere, controlled sub-bass, movie-trailer tension",
    "Dolby Surround Bass Test": "wide immersive soundstage, cinematic surround movement, deep LFE impact, spatial bass testing",
    "Nordic Folk Cinematic Bass": "Nordic folk atmosphere, cinematic drums, deep bass, ethereal vocals, ancient-meets-modern sound",
    "Latin House": "Latin percussion, warm bass, dance groove, catchy vocal rhythm, summer club atmosphere",
    "Amapiano": "log drum bass, shuffling percussion, smooth groove, African club rhythm, hypnotic piano patterns",
}

GENRES = list(GENRE_RULES.keys())

CREATION_MODES = ["Original Song", "Rewrite / Translate Lyrics from YouTube", "Inspired by YouTube Reference"]
OUTPUT_MODES = ["Full Song", "Extended Mix", "DJ Festival Mix", "Radio Edit", "Bass Test", "Instrumental"]
TARGETS = ["Europe", "USA", "Global", "Indonesia"]
VOCALS = ["Female Vocal", "Male Vocal", "Female Narrator", "Deep Male Narrator", "Male + Female Duet", "Instrumental Only", "Minimal Vocal Guide"]
SOURCE_LANGUAGES = ["Auto Detect from YouTube", "Indonesian", "English", "Javanese", "Malay", "Korean", "German", "French", "Spanish", "Dutch", "Italian", "Other"]
TARGET_LANGUAGES = ["English", "German", "French", "Spanish", "Dutch", "Italian", "Indonesian", "Korean"]
MARKET_LANGUAGES = ["English (US)", "English (UK)", "German", "French", "Spanish", "Dutch", "Italian", "Indonesian", "Bilingual: English + German", "Bilingual: English + French", "Bilingual: English + Dutch"]
BASS_LEVELS = ["Normal Bass", "Heavy Bass", "Extreme Subwoofer Bass", "20Hz-40Hz Ultra Low Bass", "Car Audio SPL Pressure", "Hi-Fi Low-End Control"]
MOODS = ["Auto Follow YouTube Reference", "Dark Cinematic", "Festival Energy", "Luxury Night Drive", "Aggressive Bass Test", "Emotional Cinematic", "European Club Atmosphere", "Futuristic Neon", "Relaxing Late Night", "Romantic Emotional", "Powerful Motivational", "Dark Underground"]
MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
BATCH_COUNTS = [1, 3, 5, 10, 20]
BATCH_STRATEGIES = ["Single Best Output", "Random Creative Variations", "Genre Expansion", "Audience Expansion", "Language Expansion", "Commercial Expansion", "Fusion Variations"]
FUSION_MODES = ["Off", "Genre A + Genre B", "Genre A + Genre B + Genre C", "YouTube Reference + Genre Fusion"]
AUTOPILOT_LEVELS = ["Off", "Auto Pilot 80+", "Auto Pilot 90+", "Auto Pilot 95+ Experimental"]

BUILT_IN_PRESETS = {
    "Custom Manual": {},
    "My Future Rave Europe": {
        "creation_mode": "Rewrite / Translate Lyrics from YouTube",
        "output_mode": "DJ Festival Mix",
        "genre": "Future Rave",
        "target": "Europe",
        "vocal": "Female Vocal",
        "target_language": "English",
        "market_language": "English (US)",
        "bass": "Heavy Bass",
        "mood": "Festival Energy",
        "bpm": "130",
        "extra": "Emotional European Future Rave anthem, female vocal, supersaw lead, big room drop, euphoric festival energy, no car audio theme.",
    },
    "Berlin Hard Techno x Dark Pop": {
        "creation_mode": "Original Song",
        "output_mode": "Extended Mix",
        "genre": "Hard Techno",
        "target": "Europe",
        "vocal": "Female Vocal",
        "target_language": "English",
        "market_language": "English (US)",
        "bass": "Extreme Subwoofer Bass",
        "mood": "Dark Underground",
        "bpm": "145",
        "extra": "Dark emotional vocal hook over brutal Berlin hard techno drums, professional club mastering, cinematic tension.",
    },
    "Subwoofer Challenge Europe": {
        "creation_mode": "Original Song",
        "output_mode": "Bass Test",
        "genre": "Subwoofer Bass Test",
        "target": "Europe",
        "vocal": "Deep Male Narrator",
        "target_language": "English",
        "market_language": "English (UK)",
        "bass": "20Hz-40Hz Ultra Low Bass",
        "mood": "Dark Cinematic",
        "bpm": "128",
        "extra": "Dark cinematic subwoofer challenge, long looped drops, minimal narrator, extreme low-frequency pressure.",
    },
}


def normalize_percentages(values):
    total = sum(values)
    if total == 0:
        return values
    return [round(v / total * 100) for v in values]


def build_fusion_summary(fusion_mode, yt_pct, genre_a, genre_a_pct, genre_b, genre_b_pct, genre_c, genre_c_pct):
    if fusion_mode == "Off":
        return "Fusion Mode is Off. Use the main selected genre only."
    parts = []
    if "YouTube" in fusion_mode:
        parts.append(f"YouTube Reference Influence: {yt_pct}%")
    parts.append(f"Genre A - {genre_a}: {genre_a_pct}% | Rule: {GENRE_RULES.get(genre_a, '')}")
    if "Genre B" in fusion_mode:
        parts.append(f"Genre B - {genre_b}: {genre_b_pct}% | Rule: {GENRE_RULES.get(genre_b, '')}")
    if "Genre C" in fusion_mode:
        parts.append(f"Genre C - {genre_c}: {genre_c_pct}% | Rule: {GENRE_RULES.get(genre_c, '')}")
    return "\n".join(parts)


def build_master_prompt(data):
    fusion_summary = build_fusion_summary(
        data["fusion_mode"], data["yt_pct"], data["genre_a"], data["genre_a_pct"],
        data["genre_b"], data["genre_b_pct"], data["genre_c"], data["genre_c_pct"]
    )

    autopilot_rules = f"""
AUTO PILOT QUALITY MODE:
{data['autopilot_level']}

AUTO PILOT 90+ / FUSION DIRECTOR RULES:
1. Do not simply stack genre tags. Blend emotional DNA, groove, rhythm, bass character, vocal identity, arrangement, and atmosphere.
2. Preserve the selected percentages as creative influence weights.
3. If the combination is weak or conflicting, repair it professionally without ignoring the user's settings.
4. Strengthen hook, bass movement, transitions, drop design, sound design, structure, and commercial appeal.
5. Remove contradictory directions, but explain the correction briefly in the quality check.
6. Final Suno style metadata must be clean, focused, and maximum 999 characters.
7. The result should feel like a professional producer made a 90+/100 direction brief.
8. Do not make the result generic. Keep a distinct identity.
9. Keep target audience, BPM, bass level, vocal type, output mode, and market language aligned.
10. If Auto Pilot is Off, do normal generation without forced quality upgrading.
"""

    bass_test_rules = """
BASS TEST RULES:
- Use minimal narrator lines only.
- Prioritize long instrumental low-frequency sections, bass sweeps, sub drops, and controlled low-end movement.
- Include warnings for headphones, speakers, and subwoofers in YouTube description.
- Do not create normal verse-heavy pop lyrics unless user explicitly asks.
""" if ("Bass Test" in data["output_mode"] or "Subwoofer" in data["main_genre"] or "Car Audio" in data["main_genre"] or "Dolby" in data["main_genre"] or "Home Theater" in data["main_genre"]) else ""

    return f"""
You are an elite AI music producer, Suno AI prompt architect, genre-fusion director,
YouTube music SEO strategist, international lyric adaptation expert, and thumbnail concept designer.

Create a complete professional music content package based on the inputs below.

APP VERSION:
Music Prompt Studio Pro v2.6 - Genre Fusion Pilot 90+

CREATION MODE:
{data['creation_mode']}

OUTPUT MODE:
{data['output_mode']}

MAIN SELECTED GENRE:
{data['main_genre']}

MAIN GENRE RULE:
{GENRE_RULES.get(data['main_genre'], '')}

GENRE FUSION MODE:
{data['fusion_mode']}

FUSION PERCENTAGE PLAN:
{fusion_summary}

{autopilot_rules}

TARGET AUDIENCE:
{data['target']}

VOCAL TYPE:
{data['vocal']}

SOURCE LANGUAGE:
{data['source_language']}

TARGET LYRICS LANGUAGE:
{data['target_language']}

MARKET LANGUAGE FOR SEO / DESCRIPTION / THUMBNAIL:
{data['market_language']}

BASS LEVEL:
{data['bass']}

MOOD / ENERGY:
{data['mood']}

BPM:
{data['bpm']}

BATCH VARIATIONS:
{data['batch_count']}

BATCH STRATEGY:
{data['batch_strategy']}

YOUTUBE REFERENCE LINK:
{data['youtube_link']}

YOUTUBE METADATA PREVIEW:
{data['youtube_metadata_text']}

YOUTUBE TRANSCRIPT PREVIEW:
{data['youtube_transcript_text']}

USER EXTRA STYLE / NOTES:
{data['extra_style']}

MANUAL LYRICS / TRANSCRIPT BACKUP:
{data['manual_lyrics']}

{bass_test_rules}

YOUTUBE ADAPTATION RULES:
- If YouTube transcript is accessible, use it as the main lyrical/emotional reference.
- If YouTube metadata is accessible, use it to understand context, title direction, and SEO angle.
- If transcript is not accessible but manual lyrics exist, use manual lyrics.
- Do not copy original lyrics exactly.
- Rewrite meaning into original, copyright-safe, singable lyrics in the selected target lyrics language.
- Use the YouTube reference as emotional DNA, not as something to plagiarize.

FUSION ENGINE RULES:
- If Fusion Mode is Off, follow the main selected genre only.
- If Fusion Mode uses Genre A/B/C, create a natural hybrid identity.
- If Fusion Mode uses YouTube Reference + Genre Fusion, the reference influence must shape emotion, structure, groove, and vocal mood according to its percentage.
- Genre percentages are not math for tag quantity; they are creative influence weights.
- Mention the final fusion identity clearly.

BATCH RULES:
- If batch count is 1, create one strongest output.
- If batch count is more than 1, create exactly that number of full variations.
- Each variation must have a different musical angle.
- For Fusion Variations, keep the same percentage plan but explore different execution styles.

LANGUAGE RULES:
- Target lyrics language controls lyrics.
- Market language controls YouTube titles, description, CTA, thumbnail text.
- Tags should be mostly in market language with some English SEO keywords.

OUTPUT FORMAT:

VARIATION 1 - [Clear Version Name]

1. FUSION DIRECTOR ANALYSIS
- Final fusion identity
- Influence percentage interpretation
- YouTube/reference role
- Main emotion
- Groove/rhythm direction
- Vocal direction
- Bass direction
- Commercial potential

2. SUNO STYLE METADATA
Put inside one code block.
Maximum 999 characters.
Must be ready to copy into Suno AI.
Must be focused, professional, and not overloaded.

3. LYRICS + STRUCTURE TAGS
Create complete lyrics or structure in target lyrics language.
Use proper Suno structure tags.
For instrumental or bass test, use mostly instrumental structure and minimal vocal guide.

4. YOUTUBE SEO TITLES
Create 10 SEO-friendly titles in market language.

5. YOUTUBE DESCRIPTION
Create a professional YouTube description in market language.
Use 2-4 paragraphs.
Add CTA.
Add safety/listening note for bass test content.

6. TAGS AND KEYWORDS
Create SEO tags separated by commas.

7. BACKGROUND IMAGE PROMPT
Create a cinematic 16:9 image prompt with no text, no logo, no watermark.

8. THUMBNAIL PROMPT
Create a 16:9 YouTube thumbnail prompt with clear short text overlay in market language.
Text must be bold, readable, mobile-friendly, and SEO-focused.

9. AUTO PILOT 90+ QUALITY CHECK
Rate:
- Fusion Accuracy: /100
- Genre Balance: /100
- Suno Compatibility: /100
- Commercial Appeal: /100
- SEO Strength: /100
- Overall Score: /100
Then give short improvement notes.
"""


config = load_config()
custom_presets = load_custom_presets()
all_presets = {**BUILT_IN_PRESETS, **custom_presets}

st.title("Music Prompt Studio Pro v2.6")
st.write("Genre Fusion Pilot 90+ — Suno AI prompt generator, YouTube reference mixing, genre percentage fusion, SEO, thumbnail, and batch content engine.")
st.divider()

with st.sidebar:
    st.header("API & Preset")
    api_key = st.text_input("Gemini API Key", value=config.get("api_key", ""), type="password")
    model_name = st.selectbox("Gemini Model", MODELS, index=index_or_default(MODELS, config.get("model_name", "gemini-2.5-flash"), 1))

    preset_name = st.selectbox("Preset", list(all_presets.keys()))
    preset = all_presets.get(preset_name, {})

    save_settings = st.button("Save API & Model")
    if save_settings:
        config["api_key"] = api_key
        config["model_name"] = model_name
        save_config(config)
        st.success("Settings tersimpan.")

    st.divider()
    st.caption("History terakhir")
    for item in read_recent_history(5):
        st.caption(item.name)

col1, col2 = st.columns(2)

with col1:
    creation_mode = st.selectbox("Creation Mode", CREATION_MODES, index=index_or_default(CREATION_MODES, preset.get("creation_mode", "Original Song")))
    output_mode = st.selectbox("Output Mode", OUTPUT_MODES, index=index_or_default(OUTPUT_MODES, preset.get("output_mode", "Full Song")))
    main_genre = st.selectbox("Main Genre", GENRES, index=index_or_default(GENRES, preset.get("genre", "Future Rave")))
    target = st.selectbox("Target Audience", TARGETS, index=index_or_default(TARGETS, preset.get("target", "Europe")))
    vocal = st.selectbox("Vocal Type", VOCALS, index=index_or_default(VOCALS, preset.get("vocal", "Female Vocal")))
    bpm = st.text_input("BPM", value=preset.get("bpm", config.get("bpm", "130")))

with col2:
    source_language = st.selectbox("Source Language", SOURCE_LANGUAGES, index=index_or_default(SOURCE_LANGUAGES, preset.get("source_language", "Auto Detect from YouTube")))
    target_language = st.selectbox("Target Lyrics Language", TARGET_LANGUAGES, index=index_or_default(TARGET_LANGUAGES, preset.get("target_language", "English")))
    market_language = st.selectbox("Market Language", MARKET_LANGUAGES, index=index_or_default(MARKET_LANGUAGES, preset.get("market_language", "English (US)")))
    bass = st.selectbox("Bass Level", BASS_LEVELS, index=index_or_default(BASS_LEVELS, preset.get("bass", "Heavy Bass")))
    mood = st.selectbox("Mood / Energy", MOODS, index=index_or_default(MOODS, preset.get("mood", "Festival Energy")))
    batch_count = st.selectbox("Batch Variations", BATCH_COUNTS, index=0)
    batch_strategy = st.selectbox("Batch Strategy", BATCH_STRATEGIES, index=0)

st.divider()
st.subheader("Genre Fusion Pilot 90+")

fusion_col1, fusion_col2, fusion_col3, fusion_col4 = st.columns(4)

with fusion_col1:
    fusion_mode = st.selectbox("Fusion Mode", FUSION_MODES, index=0)
    autopilot_level = st.selectbox("Auto Pilot Quality", AUTOPILOT_LEVELS, index=2)

with fusion_col2:
    yt_pct = st.number_input("YouTube Ref %", min_value=0, max_value=100, value=50 if "YouTube" in fusion_mode else 0, step=5)
    genre_a = st.selectbox("Genre A", GENRES, index=index_or_default(GENRES, main_genre))
    genre_a_pct = st.number_input("Genre A %", min_value=0, max_value=100, value=50 if fusion_mode == "Genre A + Genre B" else 25, step=5)

with fusion_col3:
    genre_b = st.selectbox("Genre B", GENRES, index=index_or_default(GENRES, "Hard Techno"))
    genre_b_pct = st.number_input("Genre B %", min_value=0, max_value=100, value=50 if fusion_mode == "Genre A + Genre B" else 25, step=5)

with fusion_col4:
    genre_c = st.selectbox("Genre C", GENRES, index=index_or_default(GENRES, "European Pop Dance"))
    genre_c_pct = st.number_input("Genre C %", min_value=0, max_value=100, value=25, step=5)

active_total = 100
if fusion_mode == "Off":
    active_total = 100
elif fusion_mode == "Genre A + Genre B":
    active_total = genre_a_pct + genre_b_pct
elif fusion_mode == "Genre A + Genre B + Genre C":
    active_total = genre_a_pct + genre_b_pct + genre_c_pct
elif fusion_mode == "YouTube Reference + Genre Fusion":
    active_total = yt_pct + genre_a_pct + genre_b_pct + genre_c_pct

if fusion_mode != "Off":
    if active_total == 100:
        st.success(f"Fusion percentage valid: {active_total}%")
    else:
        st.warning(f"Total persentase saat ini {active_total}%. Idealnya harus 100% agar mixing influence jelas.")

st.divider()

youtube_link = st.text_input("YouTube Reference Link", value=config.get("youtube_link", ""))

meta_col, transcript_col = st.columns(2)
with meta_col:
    if st.button("Fetch YouTube Metadata"):
        metadata = fetch_youtube_oembed(youtube_link)
        st.session_state["youtube_metadata"] = metadata
        if metadata.get("error"):
            st.error(metadata.get("error"))
        else:
            st.success("Metadata berhasil diambil.")

with transcript_col:
    if st.button("Fetch YouTube Transcript"):
        video_id = extract_youtube_video_id(youtube_link)
        transcript = fetch_youtube_transcript(video_id)
        st.session_state["youtube_transcript"] = transcript
        if transcript.get("success"):
            st.success(f"Transcript berhasil diambil. Language: {transcript.get('language', '')}")
        else:
            st.error(transcript.get("error", "Transcript gagal diambil."))

metadata = st.session_state.get("youtube_metadata", {})
transcript = st.session_state.get("youtube_transcript", {})

youtube_metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2) if metadata else ""
youtube_transcript_text = transcript.get("text", "") if transcript.get("success") else ""

if youtube_metadata_text or youtube_transcript_text:
    with st.expander("YouTube Preview"):
        if youtube_metadata_text:
            st.code(youtube_metadata_text[:3000])
        if youtube_transcript_text:
            st.text_area("Transcript Preview", youtube_transcript_text[:5000], height=200)

extra_style = st.text_area(
    "Extra Style / Instruksi Tambahan",
    value=preset.get("extra", ""),
    height=120,
    placeholder="Contoh: Make it dark European future rave with brutal sub bass, emotional female vocal, cinematic build-up, no generic EDM sound."
)

manual_lyrics = st.text_area(
    "Optional: Paste Lyrics / Transcript Manual",
    height=180,
    placeholder="Tempel lirik atau transkrip di sini jika transcript YouTube tidak terbaca."
)

st.divider()

current_data = {
    "creation_mode": creation_mode,
    "output_mode": output_mode,
    "main_genre": main_genre,
    "target": target,
    "vocal": vocal,
    "source_language": source_language,
    "target_language": target_language,
    "market_language": market_language,
    "bass": bass,
    "mood": mood,
    "bpm": bpm,
    "batch_count": batch_count,
    "batch_strategy": batch_strategy,
    "youtube_link": youtube_link,
    "youtube_metadata_text": youtube_metadata_text,
    "youtube_transcript_text": youtube_transcript_text[:12000],
    "extra_style": extra_style,
    "manual_lyrics": manual_lyrics,
    "fusion_mode": fusion_mode,
    "autopilot_level": autopilot_level,
    "yt_pct": yt_pct,
    "genre_a": genre_a,
    "genre_a_pct": genre_a_pct,
    "genre_b": genre_b,
    "genre_b_pct": genre_b_pct,
    "genre_c": genre_c,
    "genre_c_pct": genre_c_pct,
}

master_prompt = build_master_prompt(current_data)

with st.expander("Preview Master Prompt yang dikirim ke Gemini"):
    st.text_area("Master Prompt", master_prompt, height=450)

button_col1, button_col2, button_col3 = st.columns(3)

with button_col1:
    generate_clicked = st.button("Generate Music Package", type="primary")

with button_col2:
    save_preset_clicked = st.button("Save Current as Custom Preset")

with button_col3:
    export_prompt_clicked = st.button("Export Master Prompt Only")

if save_preset_clicked:
    name = f"Custom Fusion {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    custom_presets[name] = {
        "creation_mode": creation_mode,
        "output_mode": output_mode,
        "genre": main_genre,
        "target": target,
        "vocal": vocal,
        "source_language": source_language,
        "target_language": target_language,
        "market_language": market_language,
        "bass": bass,
        "mood": mood,
        "bpm": bpm,
        "extra": extra_style,
    }
    save_custom_presets(custom_presets)
    st.success(f"Preset tersimpan: {name}")

if export_prompt_clicked:
    path = save_history(master_prompt, main_genre, "master_prompt_only")
    st.success(f"Master prompt diekspor: {path.name}")
    st.download_button("Download Master Prompt", data=master_prompt, file_name=path.name, mime="text/plain")

if generate_clicked:
    if not api_key.strip():
        st.error("Masukkan Gemini API Key dulu.")
    elif fusion_mode != "Off" and active_total != 100:
        st.error("Total persentase fusion harus 100% sebelum generate.")
    else:
        config.update({
            "api_key": api_key,
            "model_name": model_name,
            "bpm": bpm,
            "youtube_link": youtube_link,
        })
        save_config(config)

        try:
            client = genai.Client(api_key=api_key)
            with st.spinner("Gemini AI sedang membuat package musik dengan Fusion Pilot 90+..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=master_prompt,
                )
            result_text = getattr(response, "text", str(response))
            st.session_state["last_result"] = result_text
            path = save_history(result_text, main_genre, preset_name)
            st.success(f"Selesai. History tersimpan: {path.name}")
        except Exception as e:
            st.error(f"Generate gagal: {e}")

if st.session_state.get("last_result"):
    st.subheader("Generated Result")
    st.markdown(st.session_state["last_result"])
    st.download_button(
        "Download Result TXT",
        data=st.session_state["last_result"],
        file_name=f"{safe_filename(main_genre)}_fusion_pilot_90_result.txt",
        mime="text/plain",
    )

st.divider()
st.caption("Music Prompt Studio Pro v2.6 - Genre Fusion Pilot 90+ for Suno AI, YouTube reference mixing, genre percentage blending, SEO, thumbnail, and batch music content production.")
