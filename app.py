import streamlit as st
from google import genai

try:
    from openai import OpenAI
except Exception:
    OpenAI = None
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
# MUSIC PROMPT STUDIO PRO v2.7.5-alpha MUSIC ENGINE
# New in v2.6.1:
# - Gemini or ChatGPT/OpenAI generation provider
# - Bass/Subwoofer/Test genre long looping structure engine
# - Narrator-only-as-instruction mode for test genres
#
# New in v2.6:
# - Genre Fusion Engine
# - YouTube Reference + Genre Percentage Mixing
# - Fusion Director 90+
# - Auto Pilot 90+ professional prompt optimizer
# - Compatible with previous v2.5.x workflow concept
# ============================================================

st.set_page_config(
    page_title="Music Prompt Studio Pro v2.7.5-alpha Final",
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

CREATION_MODES = [
    "Original Song",
    "Rewrite / Translate Lyrics from YouTube",
    "Inspired by YouTube Reference",
    "Professional Reference Analysis",
    "Emotional DNA Extraction",
    "Professional Songwriter Mode",
    "Human Emotion Engine"
]
OUTPUT_MODES = ["Full Song", "Extended Mix", "DJ Festival Mix", "Radio Edit", "Bass Test", "Instrumental"]
TARGETS = ["Europe", "USA", "Global", "Indonesia"]
VOCALS = ["Female Vocal", "Male Vocal", "Female Narrator", "Deep Male Narrator", "Male + Female Duet", "Instrumental Only", "Minimal Vocal Guide"]
SOURCE_LANGUAGES = ["Auto Detect from YouTube", "Indonesian", "English", "Javanese", "Malay", "Korean", "German", "French", "Spanish", "Dutch", "Italian", "Other"]
TARGET_LANGUAGES = ["English", "German", "French", "Spanish", "Dutch", "Italian", "Indonesian", "Korean"]
MARKET_LANGUAGES = ["English (US)", "English (UK)", "German", "French", "Spanish", "Dutch", "Italian", "Indonesian", "Bilingual: English + German", "Bilingual: English + French", "Bilingual: English + Dutch"]
BASS_LEVELS = ["Normal Bass", "Heavy Bass", "Extreme Subwoofer Bass", "20Hz-40Hz Ultra Low Bass", "Car Audio SPL Pressure", "Hi-Fi Low-End Control"]
MOODS = ["Auto Follow YouTube Reference", "Dark Cinematic", "Festival Energy", "Luxury Night Drive", "Aggressive Bass Test", "Emotional Cinematic", "European Club Atmosphere", "Futuristic Neon", "Relaxing Late Night", "Romantic Emotional", "Powerful Motivational", "Dark Underground"]
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
OPENAI_MODELS = ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-4.1", "gpt-4.1-mini"]
GENERATION_PROVIDERS = ["Gemini", "ChatGPT / OpenAI", "Hybrid Mode"]
BATCH_COUNTS = [1, 3, 5, 10, 20]
BATCH_STRATEGIES = ["Single Best Output", "Random Creative Variations", "Genre Expansion", "Audience Expansion", "Language Expansion", "Commercial Expansion", "Fusion Variations"]
FUSION_MODES = ["Off", "Genre A + Genre B", "Genre A + Genre B + Genre C", "YouTube Reference + Genre Fusion"]
AUTOPILOT_LEVELS = ["Off", "Auto Pilot 80+", "Auto Pilot 90+", "Auto Pilot 95+ Experimental"]
REFERENCE_PROCESSING_LEVELS = ["Basic", "Advanced", "Professional", "Auto Pilot 90+"]
HUMANITY_LEVELS = [0, 25, 50, 75, 100]
SONGWRITER_DNA_MODES = [
    "Commercial Pop",
    "Emotional Storytelling",
    "Deep Romantic",
    "Festival Anthem",
    "Cinematic Narrative",
    "Radio Friendly",
    "Viral Hook Focus",
    "Indie Honest Confession",
    "Dark Emotional Club",
]
COPYRIGHT_SAFETY_LEVELS = ["Low", "Medium", "High", "Extreme"]

VOCAL_DNA_MODES = [
    "Auto Vocal DNA",
    "Breathy Female Vocal",
    "Soft Intimate Female Vocal",
    "Dreamy Atmospheric Female Vocal",
    "Powerful Festival Female Vocal",
    "Emotional Cinematic Female Vocal",
    "Dark Melodic Female Vocal",
    "Deep Warm Male Vocal",
    "Breathy Male Vocal",
    "Raspy Emotional Male Vocal",
    "Powerful Anthemic Male Vocal",
    "Dark Cinematic Male Vocal",
    "Male + Female Layered Vocals",
    "Call & Response Vocals",
    "Minimal Vocal Texture"
]

VOCAL_DELIVERY_MODES = [
    "Auto Delivery",
    "Intimate and close",
    "Powerful and anthemic",
    "Emotional and vulnerable",
    "Dark and hypnotic",
    "Festival-ready",
    "Smooth radio vocal",
    "Cinematic narration-like vocal",
    "Dreamy atmospheric vocal"
]

COMMERCIAL_TARGETS = [
    "Auto Market Fit",
    "Spotify Streaming",
    "YouTube Music",
    "TikTok Viral",
    "Festival Anthem",
    "Night Drive",
    "Workout Energy",
    "Club / DJ Set",
    "Radio Friendly",
    "Cinematic Experience",
    "Luxury Lounge",
    "Bass Test / Subwoofer Audience"
]

PROJECT_OUTPUT_MODES = [
    "Individual Tracks",
    "Long Mix Project",
    "YouTube Compilation",
    "Multi-Track Album / EP"
]

BATCH_VARIATION_STRENGTHS = [
    "Low",
    "Medium",
    "High",
    "Extreme"
]

REFERENCE_WEIGHT_LEVELS = [
    "Auto",
    "25%",
    "50%",
    "75%",
    "100%"
]
CLICHE_BLACKLIST_DEFAULT = "neon lights, electric dreams, midnight sky, lost in the night, fire in my soul, dancing in the dark, shadows, broken dreams"

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



def is_test_genre(output_mode: str, main_genre: str) -> bool:
    text = f"{output_mode} {main_genre}".lower()
    keywords = ["bass test", "subwoofer", "car audio", "home theater", "dolby", "speaker test", "test"]
    return any(keyword in text for keyword in keywords)


def build_auto_bpm_guidance(data) -> str:
    """Return professional BPM guidance for Auto Pilot mode."""
    genre = str(data.get("main_genre", "")).lower()
    output_mode = str(data.get("output_mode", "")).lower()
    mood = str(data.get("mood", "")).lower()
    bass = str(data.get("bass", "")).lower()
    bpm_mode = data.get("bpm_mode", "Auto Pilot BPM")
    manual_bpm = str(data.get("bpm", "")).strip()

    if "manual" in str(bpm_mode).lower() and manual_bpm:
        return f"""
BPM CONTROL:
- User selected Manual BPM: {manual_bpm}
- Keep this BPM unless it strongly conflicts with the selected genre/output mode.
- If adjustment is needed, explain the recommended BPM in the quality check.
"""

    ranges = []
    if "drum and bass" in genre:
        ranges.append("Drum and Bass: 170-176 BPM")
    if "hardstyle" in genre:
        ranges.append("Hardstyle: 145-155 BPM")
    if "hard techno" in genre or "industrial techno" in genre:
        ranges.append("Hard/Industrial Techno: 140-155 BPM")
    if "future rave" in genre or "big room" in genre or "edm festival" in genre:
        ranges.append("Future Rave / Festival EDM: 126-132 BPM")
    if "progressive house" in genre:
        ranges.append("Progressive House: 124-128 BPM")
    if "deep house" in genre or "afro house" in genre or "organic house" in genre:
        ranges.append("Deep/Afro/Organic House: 118-124 BPM")
    if "tech house" in genre:
        ranges.append("Tech House: 124-128 BPM")
    if "trance" in genre:
        ranges.append("Trance: 132-140 BPM")
    if "uk garage" in genre or "future garage" in genre:
        ranges.append("UK/Future Garage: 130-140 BPM")
    if "dubstep" in genre:
        ranges.append("Dubstep: 140 BPM feel or 70 BPM half-time")
    if "hip-hop" in genre or "trap" in genre or "phonk" in genre:
        ranges.append("Hip-Hop/Trap/Phonk: 70-95 BPM or 140-190 double-time feel")
    if "pop" in genre:
        ranges.append("Pop/Dance Pop: 95-125 BPM depending on emotion")
    if "synthwave" in genre:
        ranges.append("Synthwave: 85-115 BPM")
    if "bass test" in output_mode or "bass test" in genre or "subwoofer" in genre or "car audio" in genre:
        ranges.append("Bass/Subwoofer Test: 120-135 BPM for pulse tests, or 70-90 BPM for slow pressure sweeps")

    if not ranges:
        ranges.append("Auto-select a professional BPM based on genre, mood, vocal type, bass level, and target audience.")

    return f"""

BASS TEST STRUCTURE TEMPLATE:
If this is Bass Test / Subwoofer Test / Car Audio Test / Dolby Test, follow this kind of structure in Section 3:

```text
[Cinematic Intro]
[Atmospheric Sub-Rumble 35Hz]
[Reference-Inspired Synth Motif]

[Deep Male Narrator]
(spoken slowly)
Prepare your system.

[Pressure Build-Up]
[Minimal Kick Pulse]
[Subwoofer Warm-Up 40Hz]

[First Impact Section]
[32Hz Sustained Pressure Wave]
[Cabin Flex Demonstration]

[Dark Groove Variation]
[Reference-Aware Melodic Bass Movement]
[Low-End Motion 35Hz to 28Hz]

[Deep Male Narrator]
(spoken)
Thirty hertz.
Pressure incoming.

[Second Impact Section]
[30Hz SPL Pressure]
[Controlled Subwoofer Excursion]

[Recovery Atmosphere]
[Wide Stereo Air]
[Low Rumble Bed]

[Melodic Bass Evolution]
[New Synth Motif Variation]
[Heavy Sub Layer 28Hz]

[Deep Male Narrator]
(spoken)
Twenty-five hertz.
Feel the displacement.

[Infrasonic Descent]
[25Hz Long Decay Sweep]
[20Hz Sub Pressure Extension]

[Final Pressure Demonstration]
[Maximum Low Frequency Movement]
[System Recovery Section]

[Outro]
[Sub-Rumble Fade Out]
[End]
```

AUTO BPM PILOT:
- BPM is controlled by Auto Pilot.
- Choose the most professional BPM based on genre, mood, bass level, output mode, vocal type, and target market.
- Do not blindly use 130 BPM for every song.
- If this is a fusion genre, choose a BPM that makes the hybrid feel natural and commercially usable.
- If this is a bass/subwoofer test, choose BPM based on the bass-cycle purpose: slower for pressure sweeps, faster for rhythmic punch.
- Recommended BPM logic:
  {chr(10).join("- " + item for item in ranges)}
- In the final output, clearly state the chosen BPM and why it fits.
"""


def build_bass_experience_spec(data) -> str:
    """Dedicated Bass Experience Engine v2.7.5-alpha instruction block."""
    bass_mode = data.get("bass_experience_mode", "Auto Bass Experience")
    bass_runtime = data.get("bass_runtime", data.get("test_duration", "5 Minutes"))
    narrator_role = data.get("narrator_role", "Minimal Announcer")
    narrator_density = data.get("narrator_density", "Minimal")
    melody_influence = data.get("melody_influence", 50)
    frequency_focus = data.get("frequency_focus", "Auto Frequency Journey")
    structure_depth = data.get("structure_depth", "Extended Variation")
    atmosphere_mode = data.get("atmosphere_mode", "Auto Pilot")
    atmosphere_a = data.get("atmosphere_a", "")
    atmosphere_b = data.get("atmosphere_b", "")
    atmosphere_c = data.get("atmosphere_c", "")

    atmosphere_items = [x for x in [atmosphere_a, atmosphere_b, atmosphere_c] if str(x).strip()]
    atmosphere_text = ", ".join(atmosphere_items) if atmosphere_items else "Auto-select from YouTube reference, genre, mood, bass level, and target market."

    runtime_sections = {
        "3 Minutes": "6-8 varied global music sections",
        "5 Minutes": "8-12 varied global music sections",
        "10 Minutes": "12-18 varied global music sections",
        "15 Minutes": "18-25 varied global music sections",
        "30 Minutes": "25-40 varied global music sections",
        "Auto": "8-12 varied global music sections",
        "4-6 minutes": "8-12 varied global music sections",
        "6-8 minutes": "10-14 varied global music sections",
        "8-10 minutes": "12-18 varied global music sections",
        "10+ minutes": "15-25 varied global music sections",
    }.get(str(bass_runtime), "8-12 varied global music sections")

    return f"""
BASS EXPERIENCE ENGINE v2.7.5-alpha:
This mode creates a professional audio demonstration experience, not a normal short song.

Core principle:
- Narrator follows the music.
- Music does not follow the narrator.
- Target balance: 95% music / 5% narrator.

Bass Experience Mode:
- {bass_mode}

Runtime Target:
- {bass_runtime}
- Required arrangement density: {runtime_sections}
- Extend the structure with evolving musical sections, not rigid Cycle 1 / Cycle 2 duration tables.

Atmosphere Mode:
- {atmosphere_mode}

Atmosphere DNA:
- {atmosphere_text}

Narrator Intelligence:
- Role: {narrator_role}
- Density: {narrator_density}
- Narrator enters only before important bass/frequency chapters.
- Narrator should be short, spoken, instructional, and cinematic if appropriate.

Melody Influence from YouTube Reference:
- {melody_influence}%
- Read Melody DNA from the reference: movement, emotion, density, synth motif direction, tension, and musical character.
- Do not copy the original melody.
- Create a new melody/motif with similar musical DNA and atmosphere.

Frequency Focus:
- {frequency_focus}

Structure Depth:
- {structure_depth}

Reference-Aware Bass Generation:
If a YouTube reference is provided, analyze and use:
1. Atmosphere DNA
2. Bass DNA
3. Melody DNA
4. Energy Curve DNA
5. Arrangement DNA
6. Sound Design DNA

Do not copy:
- Exact lyrics
- Exact words
- Direct melody
- Vocal hook

Long Arrangement Rules:
- Start with an atmosphere intro.
- Add a short narrator cue.
- Let the music take over with long bass movement.
- Narrator returns only before a new bass/frequency chapter.
- Add different musical chapters: pressure build, first impact, recovery, melodic bass variation, frequency descent, cabin pressure, infrasonic section, final excursion, outro.
- Avoid monotonous repeated Loop Cycle labels.
- Use global music structure tags that feel like a real audio experience.

Bass Auto Pilot 90+ scoring priorities:
- Pressure Quality
- Bass Evolution
- Atmosphere Quality
- Melody Integration
- Frequency Coverage
- Narrator Balance
- Runtime Utilization
- Sound Design Quality
- Loop Experience
- Excursion Potential
"""


def build_reference_weight_rules(data) -> str:
    ref_weight = data.get("reference_weight", "Auto")
    if ref_weight == "Auto":
        weight_text = "Auto-balance reference influence based on creation mode, YouTube availability, genre fusion percentages, and user settings."
    else:
        weight_text = f"Use approximately {ref_weight} YouTube Reference DNA influence while staying copyright-safe."

    return f"""
REFERENCE DNA PRIORITY ENGINE:
- Reference Weight: {ref_weight}
- {weight_text}
- Genre sets the boundary. YouTube Reference sets the identity.
- If two users use the same genre/settings but different YouTube references, the generated songs must feel clearly different.
- Extract these from the reference when available:
  1. Atmosphere DNA
  2. Melody DNA
  3. Instrument DNA
  4. Emotion DNA
  5. Arrangement DNA
  6. Sound Design DNA
  7. Vocal DNA
  8. Energy Curve DNA
  9. Intro DNA
  10. Transition DNA
- Never copy exact melody, exact lyric lines, exact hook, or recognizable copyrighted phrases.
"""


def build_vocal_dna_rules(data) -> str:
    return f"""
VOCAL DNA ENGINE:
Vocal DNA Mode:
- {data.get('vocal_dna_mode', 'Auto Vocal DNA')}

Vocal Delivery:
- {data.get('vocal_delivery', 'Auto Delivery')}

Main Vocal Type:
- {data.get('vocal', '')}

Rules:
- Do not treat Male Vocal / Female Vocal as generic.
- If YouTube reference is available, extract Vocal DNA: texture, emotion, intensity, range, delivery, breathiness, power, darkness, intimacy, and commercial suitability.
- Match vocal direction to genre, reference, mood, target market, and commercial target.
- For romantic/emotional songs, vocals should feel human, natural, and emotionally believable.
- For festival/club songs, vocals should be more hook-focused, anthemic, and memorable.
- For dark/melodic techno, vocals can be atmospheric, hypnotic, intimate, or minimal.
- Do not copy a singer's exact vocal identity; use broad vocal characteristics only.
"""


def build_commercial_target_rules(data) -> str:
    commercial_target = data.get("commercial_target", "Auto Market Fit")
    return f"""
COMMERCIAL TARGET ENGINE:
Commercial Target:
- {commercial_target}

Rules:
- Shape the song for the selected market/use case.
- Spotify Streaming: strong replay value, polished structure, memorable hook, not too overlong.
- YouTube Music: cinematic title potential, strong mood identity, immersive arrangement.
- TikTok Viral: fast hook payoff, memorable phrase, short catchy motif.
- Festival Anthem: bigger build-ups, stronger drop, crowd energy, anthem vocal.
- Night Drive: atmosphere, emotional movement, smooth low-end, immersive stereo.
- Workout Energy: momentum, punch, intensity, clear rhythm drive.
- Club / DJ Set: mixable intro/outro, groove, extended sections, DJ-friendly progression.
- Radio Friendly: clean hook, concise structure, accessible vocal.
- Cinematic Experience: wide dynamics, dramatic atmosphere, emotional arc.
- Luxury Lounge: premium, smooth, elegant, warm, refined.
- Bass Test / Subwoofer Audience: low-frequency experience, pressure, clean sub movement.

Auto Pilot 90+ must rate:
- Commercial Target Match
- Streaming Potential
- Replay Value
- Hook Strength
- Market Fit
"""


def build_variation_engine_rules(data) -> str:
    return f"""
INTELLIGENT VARIATION ENGINE:
Project Output Mode:
- {data.get('project_output_mode', 'Individual Tracks')}

Batch Variation Strength:
- {data.get('batch_variation_strength', 'Medium')}

Rules:
- If batch count is more than 1, every track must stay inside the selected Genre DNA and Reference DNA.
- Variation must change melody, motif, pitch range, vocal delivery, arrangement, intro, transition, instrument DNA, chord feeling, and energy curve.
- Do not make batch tracks sound copy-pasted.
- Do not let variations drift into unrelated genres unless the user selected that fusion.
- Same genre + same settings + different YouTube reference = different identity.
- Same genre + same YouTube reference + batch 5 = same family, different tracks.

If Project Output Mode = Individual Tracks:
- Generate title, SEO, description, tags, thumbnail, and background per track.

If Project Output Mode = Long Mix Project / YouTube Compilation / Multi-Track Album:
- Generate per-track: track title, style metadata, lyrics/structure.
- Generate one project-level YouTube title, one description, one tag set, one background prompt, and one thumbnail prompt for the whole project.
- Make all tracks feel like one coherent mix/album while still being musically varied.
"""


def build_anti_copyright_rules(data) -> str:
    copyright_safety = data.get("copyright_safety", "High")
    return f"""
ANTI-COPYRIGHT / ORIGINALITY SAFETY ENGINE:
Copyright Safety Level:
- {copyright_safety}

Hard rules:
- Do not copy lyrics, unique phrases, chorus, hook text, melody, chord progression in a recognizable way, artist identity, vocal identity, or famous arrangement signature.
- You may extract broad emotional DNA, theme, atmosphere, energy, arrangement logic, vocal texture, and sound design direction.
- For LOW: Light transformation allowed, but still avoid direct copying.
- For MEDIUM: Keep theme/emotion, change wording and structure clearly.
- For HIGH: Preserve only emotional/story/music DNA; create new lyrics, new hook, new structure, new melody direction.
- For EXTREME: Extract only abstract DNA: theme, mood, conflict, energy, atmosphere, broad vocal texture, and commercial function. Make everything else new.
- Always maximize copyright distance while keeping the reference's emotional and musical spirit.
- If the reference includes lyrics, treat them as theme/emotional input, not text to rewrite line-by-line.
- Include a short copyright-safe transformation strategy in the analysis section.
"""

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
9. Keep target audience, Auto BPM Pilot, bass level, vocal type, output mode, and market language aligned.
10. If Auto Pilot is Off, do normal generation without forced quality upgrading.
"""

    test_mode_active = is_test_genre(data["output_mode"], data["main_genre"])
    bpm_guidance = build_auto_bpm_guidance(data)
    bass_experience_spec = build_bass_experience_spec(data) if test_mode_active else ""
    reference_weight_rules = build_reference_weight_rules(data)
    vocal_dna_rules = build_vocal_dna_rules(data)
    commercial_target_rules = build_commercial_target_rules(data)
    variation_engine_rules = build_variation_engine_rules(data)
    anti_copyright_rules = build_anti_copyright_rules(data)

    bass_test_rules = f"""
BASS / SUBWOOFER / SPEAKER TEST LONG ARRANGEMENT ENGINE:
This mode is ACTIVE. Treat this as a professional bass experience / subwoofer demonstration, not a normal lyrical song.

Required direction:
- Target runtime: {data['test_duration']}
- Looping method: {data['looping_method']}
- Bass cycle count setting: {data['bass_cycle_count']} (use as intensity guidance, not literal cycle labels)
- Narrator mode: {data['narrator_mode']}

Hard rules:
1. Do NOT write a normal verse-chorus pop song.
2. Do NOT make it too short. Build a long evolving audio experience.
3. Do NOT use rigid labels like Cycle 1 = 60 seconds.
4. Narrator must only appear as short spoken instruction cues before major music/frequency transitions.
5. Main content must be instrumental and musical: sub-bass sweeps, pressure waves, kick pulses, groove sections, dark synth movement, melodic motifs, atmosphere layers, LFE rumbles, phase-safe bass movement, and clean mastering.
6. Use YouTube reference melody DNA, atmosphere DNA, arrangement DNA, and sound design DNA when available.
7. Do not copy melody directly; create a new motif inspired by the reference character.
8. In SUNO STYLE METADATA, explicitly include: long bass experience, reference-aware melody DNA, minimal narrator instructions, sub-bass sweeps, controlled low-end chapters, not a normal short song.
9. IMPORTANT COPY FORMAT RULE: Section 3. LYRICS + STRUCTURE TAGS must be inside one copyable code block.
10. Use v2.6-style bracket tags because the user needs copy-ready Suno structure.
11. Narrator should be sparse and strategic: intro cue, frequency transition cue, final warning/impact cue.
12. The arrangement should feel like: Intro → narrator cue → music chapter → narrator cue → new bass/frequency chapter → melodic variation → pressure section → recovery → final impact → outro.
13. Make every bass chapter musically different and non-monotonous.
""" if test_mode_active else ""

    emotional_dna_rules = f"""
PROFESSIONAL MUSIC DIRECTOR v2.7 - EMOTIONAL DNA ENGINE:
Reference Processing Level: {data.get('reference_processing', 'Auto Pilot 90+')}
Humanity Level: {data.get('humanity_level', 100)}%
Songwriter DNA: {data.get('songwriter_dna', 'Emotional Storytelling')}
Copyright Safety: {data.get('copyright_safety', 'High')}
Forbidden / Cliche Lyric Phrases: {data.get('cliche_blacklist', '')}

Core mission:
1. Use YouTube reference lyrics/transcript as EMOTIONAL DNA, not as text to copy.
2. Preserve the theme, core emotion, story direction, romantic/human feeling, conflict, and message.
3. Do NOT drift too far from the theme of the reference, but create completely fresh wording.
4. Avoid AI-generic lines, especially phrases listed in the forbidden/cliche list.
5. Replace generic imagery with human details: memory, place, object, small gesture, regret, silence, timing, conversation, room, weather, personal habit.
6. Make lyrics singable, natural, emotionally honest, and commercially professional.
7. If the reference is romantic, make it genuinely romantic and human, not cold/futuristic unless requested.
8. If the selected genre is electronic/future/techno, keep the sound modern but keep lyrics emotionally grounded.
9. Build lyrics around a strong central hook that feels original and memorable.
10. Do not directly imitate famous artists or copyrighted songs; use only broad songwriting qualities like emotional depth, clarity, hook strength, and storytelling.

Copyright-safe lyric handling:
- LOW: Light rewrite allowed, but still avoid direct copying.
- MEDIUM: Preserve topic and emotion, change wording and structure.
- HIGH: Preserve emotional/story DNA only; create new lyrics, new hook, new verse structure.
- EXTREME: Extract only theme, perspective, conflict, emotional arc, and message. Completely new lyrics and structure.

Professional lyric scoring target:
- Emotional Depth: 90+
- Human Naturalness: 90+
- Hook Memorability: 90+
- Singability: 90+
- Copyright Distance: 90+
"""

    return f"""
You are an elite AI music producer, Suno AI prompt architect, genre-fusion director,
YouTube music SEO strategist, international lyric adaptation expert, professional songwriter, emotional DNA analyst, and thumbnail concept designer.

Create a complete professional music content package based on the inputs below.

APP VERSION:
Music Prompt Studio Pro v2.7.5-alpha Music Engine - Full v2.6.1 + Emotional DNA Engine + Human Emotion Engine + Professional Songwriter Mode + Hybrid AI + Bass Test Looping Engine

{emotional_dna_rules}

{reference_weight_rules}

{vocal_dna_rules}

{commercial_target_rules}

{variation_engine_rules}

{anti_copyright_rules}

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

BPM / AUTO BPM:
Mode: {data.get('bpm_mode', 'Auto Pilot BPM')}
Manual BPM Input: {data['bpm']}

{bpm_guidance}

{bass_experience_spec}

BATCH VARIATIONS:
{data['batch_count']}

BATCH STRATEGY:
{data['batch_strategy']}

PROJECT OUTPUT MODE:
{data.get('project_output_mode', 'Individual Tracks')}

BATCH VARIATION STRENGTH:
{data.get('batch_variation_strength', 'Medium')}

COMMERCIAL TARGET:
{data.get('commercial_target', 'Auto Market Fit')}

REFERENCE WEIGHT:
{data.get('reference_weight', 'Auto')}

VOCAL DNA MODE:
{data.get('vocal_dna_mode', 'Auto Vocal DNA')}

VOCAL DELIVERY:
{data.get('vocal_delivery', 'Auto Delivery')}

BASS TEST / LOOPING SETTINGS:
Test Mode Active: {is_test_genre(data['output_mode'], data['main_genre'])}
Target Runtime: {data['test_duration']}
Looping Method: {data['looping_method']}
Bass Cycle Count: {data['bass_cycle_count']}
Narrator Mode: {data['narrator_mode']}

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

YOUTUBE / LYRIC REFERENCE RULES:
- If YouTube transcript is accessible, use it as the main emotional, thematic, and story reference.
- If YouTube metadata is accessible, use it to understand context, title direction, audience, and SEO angle.
- If transcript is not accessible but manual lyrics exist, use manual lyrics.
- Do not copy original lyrics, hook, chorus, unique phrases, or verse structure.
- The goal is not translation-only. The goal is professional new songwriting based on the reference's emotional DNA.
- Keep the new lyrics aligned with the theme of the reference so it does not drift too far.
- Rewrite meaning into original, copyright-safe, singable lyrics in the selected target lyrics language.
- Make lyrics human, romantic/natural when relevant, and avoid forced futuristic/cyber/neon language unless explicitly requested.

FUSION ENGINE RULES:
- If Fusion Mode is Off, follow the main selected genre only.
- If Fusion Mode uses Genre A/B/C, create a natural hybrid identity.
- If Fusion Mode uses YouTube Reference + Genre Fusion, the reference influence must shape emotion, structure, groove, and vocal mood according to its percentage.
- Genre percentages are not math for tag quantity; they are creative influence weights.
- Mention the final fusion identity clearly.

BATCH RULES:
PROJECT-LEVEL OUTPUT RULE:
- If Project Output Mode is Individual Tracks, each variation must include its own SEO, description, tags, background, and thumbnail.
- If Project Output Mode is Long Mix Project / YouTube Compilation / Multi-Track Album, create all track prompts first, then create ONE combined project-level YouTube title, ONE description, ONE tag set, ONE background prompt, and ONE thumbnail prompt for the full project.
- Keep all tracks coherent under the same genre/reference DNA, but make melody, pitch, vocal delivery, intro, instrument, arrangement, and energy curve varied.

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

1. PROFESSIONAL REFERENCE / EMOTIONAL DNA ANALYSIS
- Reference theme
- Emotional DNA
- Story DNA
- Perspective
- Core conflict
- Human details to preserve
- Cliches removed
- Copyright-safe transformation strategy
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
MUST be inside one single copyable code block.
Create complete lyrics or structure in target lyrics language.
Use proper Suno structure tags.
For instrumental or bass test, use mostly instrumental long arrangement structure and narrator only as short spoken instruction cues.
For bass/subwoofer/test output, use v2.6-style bracket tags like [Cinematic Intro], [Deep Male Narrator], [Extreme Sub-Drop 30Hz].
For Bass Experience Engine output, create a long varied structure: intro atmosphere, narrator cue, music chapter, narrator transition, new bass/frequency chapter, melodic variation, pressure section, recovery, frequency demonstration, final impact, outro.

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
- Emotional DNA Accuracy: /100
- Human Naturalness: /100
- Lyric Professionalism: /100
- Copyright Safety Distance: /100
- Fusion Accuracy: /100
- Genre Balance: /100
- Suno Compatibility: /100
- Commercial Appeal: /100
- Commercial Target Match: /100
- Streaming Potential: /100
- Replay Value: /100
- Vocal DNA Match: /100
- Reference DNA Accuracy: /100
- Variation Quality: /100
- SEO Strength: /100
- Auto BPM Fit: /100
- Bass Experience Quality: /100
- Melody DNA Integration: /100
- Narrator Balance: /100
- Runtime Utilization: /100
- Chosen BPM: [state BPM here]
- Overall Score: /100
Then give short improvement notes.
"""


config = load_config()
custom_presets = load_custom_presets()
all_presets = {**BUILT_IN_PRESETS, **custom_presets}

st.title("Music Prompt Studio Pro v2.7.5-alpha Music Engine")
st.write("Full app: v2.6.1 features + v2.7.5 Music Engine Alpha: Reference DNA Priority, Vocal DNA Engine, Commercial Target Engine, Intelligent Variation, Multi-Track Project Mode, Anti-Copyright Safety, Auto BPM Pilot, Auto Pilot 90+, Bass Experience Engine, SEO, thumbnail, and batch content engine.")
st.divider()

with st.sidebar:
    st.header("API & Preset")
    generation_provider = st.selectbox(
        "Generate Pakai AI",
        GENERATION_PROVIDERS,
        index=index_or_default(GENERATION_PROVIDERS, config.get("generation_provider", "Gemini"), 0),
        help="Metadata/transkrip YouTube tetap diambil dari fitur YouTube app. Untuk generate hasil akhir, pilih Gemini, ChatGPT/OpenAI, atau Hybrid Mode."
    )

    gemini_api_key = st.text_input("Gemini API Key", value=config.get("gemini_api_key", config.get("api_key", "")), type="password")
    gemini_model_name = st.selectbox("Gemini Model", GEMINI_MODELS, index=index_or_default(GEMINI_MODELS, config.get("gemini_model_name", config.get("model_name", "gemini-2.5-flash")), 1))

    openai_api_key = st.text_input("OpenAI API Key", value=config.get("openai_api_key", ""), type="password")
    openai_model_name = st.selectbox("ChatGPT / OpenAI Model", OPENAI_MODELS, index=index_or_default(OPENAI_MODELS, config.get("openai_model_name", "gpt-4.1"), 3))

    preset_name = st.selectbox("Preset", list(all_presets.keys()))
    preset = all_presets.get(preset_name, {})

    save_settings = st.button("Save API & Model")
    if save_settings:
        config["generation_provider"] = generation_provider
        config["gemini_api_key"] = gemini_api_key
        config["gemini_model_name"] = gemini_model_name
        config["openai_api_key"] = openai_api_key
        config["openai_model_name"] = openai_model_name
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
    bpm_mode = st.selectbox(
        "BPM Mode",
        ["Auto Pilot BPM", "Manual BPM"],
        index=index_or_default(["Auto Pilot BPM", "Manual BPM"], config.get("bpm_mode", "Auto Pilot BPM"), 0),
        help="Auto Pilot akan memilih BPM paling cocok berdasarkan genre, mood, bass level, output mode, vocal, dan target market."
    )
    bpm = st.text_input("Manual BPM / BPM Note", value=preset.get("bpm", config.get("bpm", "Auto")), help="Isi angka jika Manual BPM. Jika Auto Pilot, boleh biarkan 'Auto'.")

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
st.subheader("Professional Music Director v2.7")

pmd_col1, pmd_col2, pmd_col3, pmd_col4 = st.columns(4)
with pmd_col1:
    reference_processing = st.selectbox("Reference Processing", REFERENCE_PROCESSING_LEVELS, index=3)
with pmd_col2:
    humanity_level = st.selectbox("Humanity Level", HUMANITY_LEVELS, index=4, help="Semakin tinggi, lirik makin human, natural, romantis, dan anti kalimat AI generik.")
with pmd_col3:
    songwriter_dna = st.selectbox("Songwriter DNA", SONGWRITER_DNA_MODES, index=1)
with pmd_col4:
    copyright_safety = st.selectbox("Copyright Safety", COPYRIGHT_SAFETY_LEVELS, index=2)

cliche_blacklist = st.text_area(
    "Cliche Killer / Forbidden Lyric Phrases",
    value=CLICHE_BLACKLIST_DEFAULT,
    height=80,
    help="Pisahkan dengan koma. AI akan diminta menghindari frasa yang terlalu generik atau terasa seperti lagu AI."
)

st.caption("Fitur ini menjaga lirik tetap mengikuti jiwa/tema referensi YouTube, tapi tidak menyalin kata-kata/hook. Fokusnya: Emotional DNA, human storytelling, Auto BPM Pilot, dan hasil lirik 90+ yang lebih profesional.")


st.markdown("### Music Engine v2.7.5-alpha")

me_col1, me_col2, me_col3 = st.columns(3)
with me_col1:
    reference_weight = st.selectbox(
        "Reference Weight Control",
        REFERENCE_WEIGHT_LEVELS,
        index=index_or_default(REFERENCE_WEIGHT_LEVELS, config.get("reference_weight", "Auto"), 0),
        help="Mengatur seberapa kuat DNA referensi YouTube mempengaruhi hasil. Tetap copyright-safe."
    )
    project_output_mode = st.selectbox(
        "Project Output Mode",
        PROJECT_OUTPUT_MODES,
        index=index_or_default(PROJECT_OUTPUT_MODES, config.get("project_output_mode", "Individual Tracks"), 0),
        help="Individual = SEO per lagu. Long Mix/Compilation/Album = satu SEO/artwork untuk seluruh project."
    )

with me_col2:
    vocal_dna_mode = st.selectbox(
        "Vocal DNA Mode",
        VOCAL_DNA_MODES,
        index=index_or_default(VOCAL_DNA_MODES, config.get("vocal_dna_mode", "Auto Vocal DNA"), 0)
    )
    vocal_delivery = st.selectbox(
        "Vocal Delivery",
        VOCAL_DELIVERY_MODES,
        index=index_or_default(VOCAL_DELIVERY_MODES, config.get("vocal_delivery", "Auto Delivery"), 0)
    )

with me_col3:
    commercial_target = st.selectbox(
        "Commercial Target",
        COMMERCIAL_TARGETS,
        index=index_or_default(COMMERCIAL_TARGETS, config.get("commercial_target", "Auto Market Fit"), 0)
    )
    batch_variation_strength = st.selectbox(
        "Batch Variation Strength",
        BATCH_VARIATION_STRENGTHS,
        index=index_or_default(BATCH_VARIATION_STRENGTHS, config.get("batch_variation_strength", "Medium"), 1),
        help="Mengatur seberapa berbeda tiap track dalam batch, tapi tetap di genre/reference DNA yang sama."
    )

st.caption("Music Engine v2.7.5-alpha: Reference DNA Priority, Vocal DNA, Commercial Target, Intelligent Variation, Multi-Track Project Mode, dan Anti-Copyright Safety.")

st.divider()
st.subheader("Bass / Subwoofer / Test Looping Engine")

test_mode_detected = is_test_genre(output_mode, main_genre)
if test_mode_detected:
    st.success("Test genre terdeteksi. Mode long looping akan dipaksa agar tidak menjadi lagu pendek biasa.")
else:
    st.caption("Mode ini otomatis aktif jika Output Mode atau genre mengandung Bass Test, Subwoofer, Car Audio, Dolby, Home Theater, atau Test.")

loop_col1, loop_col2, loop_col3, loop_col4 = st.columns(4)
with loop_col1:
    test_duration = st.selectbox("Target Runtime", ["Auto", "4-6 minutes", "6-8 minutes", "8-10 minutes", "10+ minutes"], index=2 if test_mode_detected else 0)
with loop_col2:
    looping_method = st.selectbox("Looping Method", ["Auto", "Evolving Bass Cycles", "Clean Repeating Test Loop", "Cinematic LFE Waves", "SPL Pressure Cycles"], index=1 if test_mode_detected else 0)
with loop_col3:
    bass_cycle_count = st.slider("Bass Cycle Count", min_value=2, max_value=12, value=6 if test_mode_detected else 3)
with loop_col4:
    narrator_mode = st.selectbox("Narrator Mode", ["Instruction cues only", "Minimal countdown only", "No narrator", "Intro/outro warning only"], index=0)

st.markdown("### Bass Experience Engine v2.7.5-alpha")
if test_mode_detected:
    st.caption("Mode ini membuat Bass Test sebagai audio experience: musik panjang dan variatif, narrator hanya masuk sebagai instruksi singkat sebelum transisi bass/frequency.")
else:
    st.caption("Panel ini akan aktif sebagai instruksi utama jika Output Mode atau genre adalah Bass/Subwoofer/Car Audio/Home Theater/Test.")

be_col1, be_col2, be_col3 = st.columns(3)
with be_col1:
    bass_experience_mode = st.selectbox(
        "Bass Experience Mode",
        [
            "Auto Bass Experience",
            "Deep Subwoofer Demo",
            "Extreme SPL Competition",
            "Night Drive Bass Experience",
            "Future Rave Bass Experience",
            "Dark Techno Bass Experience",
            "Home Theater Impact Experience",
            "Frequency Sweep Experience",
            "Car Audio Pressure Experience",
            "Cinematic Bass Showcase"
        ],
        index=index_or_default([
            "Auto Bass Experience",
            "Deep Subwoofer Demo",
            "Extreme SPL Competition",
            "Night Drive Bass Experience",
            "Future Rave Bass Experience",
            "Dark Techno Bass Experience",
            "Home Theater Impact Experience",
            "Frequency Sweep Experience",
            "Car Audio Pressure Experience",
            "Cinematic Bass Showcase"
        ], config.get("bass_experience_mode", "Auto Bass Experience"), 0)
    )
    bass_runtime = st.selectbox("Bass Runtime Target", ["3 Minutes", "5 Minutes", "10 Minutes", "15 Minutes", "30 Minutes"], index=index_or_default(["3 Minutes", "5 Minutes", "10 Minutes", "15 Minutes", "30 Minutes"], config.get("bass_runtime", "5 Minutes"), 1))
    frequency_focus = st.selectbox("Frequency Focus", ["Auto Frequency Journey", "40Hz to 20Hz Linear Sweep", "35Hz Cabin Pressure", "30Hz SPL Pressure", "25Hz Excursion Focus", "20Hz Infrasonic Descent", "Mixed 20Hz-40Hz Bass Journey"], index=index_or_default(["Auto Frequency Journey", "40Hz to 20Hz Linear Sweep", "35Hz Cabin Pressure", "30Hz SPL Pressure", "25Hz Excursion Focus", "20Hz Infrasonic Descent", "Mixed 20Hz-40Hz Bass Journey"], config.get("frequency_focus", "Auto Frequency Journey"), 0))

with be_col2:
    narrator_role = st.selectbox("Narrator Role", ["Frequency Guide", "Bass Demonstrator", "System Calibrator", "SPL Judge", "Cinematic Voice", "Minimal Announcer"], index=index_or_default(["Frequency Guide", "Bass Demonstrator", "System Calibrator", "SPL Judge", "Cinematic Voice", "Minimal Announcer"], config.get("narrator_role", "Minimal Announcer"), 5))
    narrator_density = st.selectbox("Narrator Density", ["Off", "Minimal", "Low", "Medium"], index=index_or_default(["Off", "Minimal", "Low", "Medium"], config.get("narrator_density", "Minimal"), 1))
    melody_influence = st.slider("Melody Influence from YouTube Reference", 0, 100, int(config.get("melody_influence", 50)), 25, help="0% = bass dominan. 100% = karakter musikal/melodi referensi sangat terasa, tanpa menyalin melodi.")

with be_col3:
    atmosphere_mode = st.selectbox("Atmosphere Mode", ["Auto Pilot", "Manual", "Fusion"], index=index_or_default(["Auto Pilot", "Manual", "Fusion"], config.get("atmosphere_mode", "Auto Pilot"), 0))
    structure_depth = st.selectbox("Bass Structure Depth", ["Standard", "Extended Variation", "Long Cinematic Journey", "Maximum Variation"], index=index_or_default(["Standard", "Extended Variation", "Long Cinematic Journey", "Maximum Variation"], config.get("structure_depth", "Extended Variation"), 1))

atmosphere_options = [
    "Auto Select", "Berlin Warehouse", "Amsterdam Rave", "London Underground", "Concrete Basement", "Tunnel Rave",
    "Future Rave Arena", "European Mega Festival", "Mainstage Experience", "Midnight Autobahn", "Rainy Highway",
    "Cyberpunk Highway", "Luxury GT Cruise", "SPL Competition", "SQL Showcase", "Parking Lot Demo",
    "Basshead Gathering", "IMAX Inspired", "Dolby Atmos Showcase", "Earthquake Simulation", "Alien Arrival",
    "Black Hole Descent", "Apocalyptic Atmosphere", "Interstellar Journey", "Frequency Laboratory",
    "Pressure Wave Simulation", "Infrasonic Research Facility", "Deep Ocean Pressure", "Thunderstorm Impact",
    "Luxury Audio Showcase", "Abandoned Factory", "Dark Future Metropolis", "Subsonic Research Lab"
]
atm_col1, atm_col2, atm_col3 = st.columns(3)
with atm_col1:
    atmosphere_a = st.selectbox("Atmosphere A", atmosphere_options, index=index_or_default(atmosphere_options, config.get("atmosphere_a", "Auto Select"), 0))
with atm_col2:
    atmosphere_b = st.selectbox("Atmosphere B", atmosphere_options, index=index_or_default(atmosphere_options, config.get("atmosphere_b", "Auto Select"), 0))
with atm_col3:
    atmosphere_c = st.selectbox("Atmosphere C", atmosphere_options, index=index_or_default(atmosphere_options, config.get("atmosphere_c", "Auto Select"), 0))

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
    "test_duration": test_duration,
    "looping_method": looping_method,
    "bass_cycle_count": bass_cycle_count,
    "narrator_mode": narrator_mode,
    "bass_experience_mode": bass_experience_mode,
    "bass_runtime": bass_runtime,
    "narrator_role": narrator_role,
    "narrator_density": narrator_density,
    "melody_influence": melody_influence,
    "frequency_focus": frequency_focus,
    "structure_depth": structure_depth,
    "atmosphere_mode": atmosphere_mode,
    "atmosphere_a": "" if atmosphere_a == "Auto Select" else atmosphere_a,
    "atmosphere_b": "" if atmosphere_b == "Auto Select" else atmosphere_b,
    "atmosphere_c": "" if atmosphere_c == "Auto Select" else atmosphere_c,
    "fusion_mode": fusion_mode,
    "autopilot_level": autopilot_level,
    "reference_processing": reference_processing,
    "humanity_level": humanity_level,
    "songwriter_dna": songwriter_dna,
    "copyright_safety": copyright_safety,
    "cliche_blacklist": cliche_blacklist,
    "reference_weight": reference_weight,
    "project_output_mode": project_output_mode,
    "vocal_dna_mode": vocal_dna_mode,
    "vocal_delivery": vocal_delivery,
    "commercial_target": commercial_target,
    "batch_variation_strength": batch_variation_strength,
    "yt_pct": yt_pct,
    "genre_a": genre_a,
    "genre_a_pct": genre_a_pct,
    "genre_b": genre_b,
    "genre_b_pct": genre_b_pct,
    "genre_c": genre_c,
    "genre_c_pct": genre_c_pct,
}

master_prompt = build_master_prompt(current_data)

with st.expander("Preview Master Prompt yang dikirim ke AI Generator"):
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
        "bpm_mode": bpm_mode,
        "extra": extra_style,
    }
    save_custom_presets(custom_presets)
    st.success(f"Preset tersimpan: {name}")

if export_prompt_clicked:
    path = save_history(master_prompt, main_genre, "master_prompt_only")
    st.success(f"Master prompt diekspor: {path.name}")
    st.download_button("Download Master Prompt", data=master_prompt, file_name=path.name, mime="text/plain")

if generate_clicked:
    if generation_provider == "Gemini" and not gemini_api_key.strip():
        st.error("Masukkan Gemini API Key dulu.")
    elif generation_provider == "ChatGPT / OpenAI" and not openai_api_key.strip():
        st.error("Masukkan OpenAI API Key dulu.")
    elif generation_provider == "Hybrid Mode" and (not gemini_api_key.strip() or not openai_api_key.strip()):
        st.error("Hybrid Mode membutuhkan Gemini API Key dan OpenAI API Key.")
    elif generation_provider in ["ChatGPT / OpenAI", "Hybrid Mode"] and OpenAI is None:
        st.error("Package openai belum terinstall. Jalankan: pip install openai")
    elif fusion_mode != "Off" and active_total != 100:
        st.error("Total persentase fusion harus 100% sebelum generate.")
    else:
        config.update({
            "generation_provider": generation_provider,
            "gemini_api_key": gemini_api_key,
            "gemini_model_name": gemini_model_name,
            "openai_api_key": openai_api_key,
            "openai_model_name": openai_model_name,
            "bpm": bpm,
            "bpm_mode": bpm_mode,
            "youtube_link": youtube_link,
            "reference_weight": reference_weight,
            "project_output_mode": project_output_mode,
            "vocal_dna_mode": vocal_dna_mode,
            "vocal_delivery": vocal_delivery,
            "commercial_target": commercial_target,
            "batch_variation_strength": batch_variation_strength,
        })
        save_config(config)

        try:
            if generation_provider == "Gemini":
                client = genai.Client(api_key=gemini_api_key)
                with st.spinner("Gemini AI sedang membuat package musik v2.7 dengan Emotional DNA + Fusion Pilot 90+..."):
                    response = client.models.generate_content(
                        model=gemini_model_name,
                        contents=master_prompt,
                    )
                result_text = getattr(response, "text", str(response))

            elif generation_provider == "ChatGPT / OpenAI":
                client = OpenAI(api_key=openai_api_key)
                with st.spinner("ChatGPT / OpenAI sedang membuat package musik v2.7 dengan Emotional DNA + Fusion Pilot 90+..."):
                    response = client.responses.create(
                        model=openai_model_name,
                        input=master_prompt,
                    )
                result_text = getattr(response, "output_text", None) or str(response)

            else:
                gemini_client = genai.Client(api_key=gemini_api_key)
                with st.spinner("Hybrid step 1/2: Gemini menganalisis YouTube/reference Emotional DNA..."):
                    analysis_prompt = """
Analyze the reference material below as a professional music producer and lyric analyst.
Return a concise Emotional DNA, Story DNA, genre influence, human lyric direction, cliche risks, and copyright-safe transformation plan.
Do not write the final song yet.

""" + master_prompt[:25000]
                    gemini_response = gemini_client.models.generate_content(
                        model=gemini_model_name,
                        contents=analysis_prompt,
                    )
                    gemini_analysis = getattr(gemini_response, "text", str(gemini_response))

                openai_client = OpenAI(api_key=openai_api_key)
                hybrid_prompt = master_prompt + """

HYBRID MODE - GEMINI REFERENCE ANALYSIS:
Use the following Gemini analysis as an additional producer note. Improve it, do not blindly copy it.

""" + gemini_analysis
                with st.spinner("Hybrid step 2/2: ChatGPT/OpenAI membuat hasil final profesional..."):
                    response = openai_client.responses.create(
                        model=openai_model_name,
                        input=hybrid_prompt,
                    )
                result_text = getattr(response, "output_text", None) or str(response)
                result_text = "## Hybrid Gemini Analysis Notes\n\n" + gemini_analysis + "\n\n---\n\n## Final Generated Result\n\n" + result_text

            st.session_state["last_result"] = result_text
            path = save_history(result_text, main_genre, preset_name)
            st.success(f"Selesai pakai {generation_provider}. History tersimpan: {path.name}")
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
st.caption("Music Prompt Studio Pro v2.7.5-alpha Music Engine - v2.6.1 full features + Emotional DNA Engine + Human Emotion Engine + Professional Songwriter Mode + Genre Fusion Pilot 90+ + Hybrid AI + Bass Test Looping Engine.")
