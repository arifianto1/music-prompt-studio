import streamlit as st
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import sqlite3
import re
from datetime import datetime

# ==========================================
# 1. KONFIGURASI HALAMAN & DATABASE
# ==========================================
st.set_page_config(page_title="Music Prompt Studio Pro Ultimate", page_icon="🎧", layout="wide")

def init_db():
    conn = sqlite3.connect('studio_storage.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, prompt TEXT, result TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(prompt_text, result_text):
    conn = sqlite3.connect('studio_storage.db')
    c = conn.cursor()
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO history (date, prompt, result) VALUES (?, ?, ?)", (waktu, prompt_text, result_text))
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. FUNGSI EKSTRAKSI YOUTUBE
# ==========================================
def extract_youtube_data(url):
    try:
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        if not video_id_match:
            return "ID Video tidak ditemukan."
        
        video_id = video_id_match.group(1)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t['text'] for t in transcript])
        return text[:5000] 
    except Exception as e:
        return f"Gagal mengekstrak referensi YouTube: {str(e)}"

# ==========================================
# 3. ANTARMUKA (UI) PANEL SAMPING (SIDEBAR)
# ==========================================
st.sidebar.title("⚙️ Engine Settings")
api_key = st.sidebar.text_input("🔑 Masukkan Gemini API Key", type="password")

st.sidebar.divider()
st.sidebar.subheader("🎬 Mode Produksi")
mode_produksi = st.sidebar.radio(
    "Pilih Target Output:",
    ["Single Track (1 Lagu)", "Kompilasi (Long Duration)"]
)

jumlah_lagu = 1
if mode_produksi == "Kompilasi (Long Duration)":
    jumlah_lagu = st.sidebar.slider("Jumlah Variasi Lagu (Tracklist)", min_value=2, max_value=10, value=5)

st.sidebar.divider()
st.sidebar.subheader("🎛️ Pengaturan Genre (Fusion)")
genre_utama = st.sidebar.selectbox("Genre Utama", ["EDM", "Phonk", "Trap", "Synthwave", "Cinematic", "Rock", "Pop", "Lo-Fi"])
genre_kombinasi = st.sidebar.selectbox("Gabungkan Dengan", ["Tidak Ada", "Orchestral", "Cyberpunk", "Jazz", "Acoustic", "Metal", "Ambient", "Classical"])

st.sidebar.divider()
st.sidebar.subheader("⚖️ Kontrol Takaran & Mode Pro")
bobot_referensi = st.sidebar.slider("Pengaruh Referensi YouTube (%)", min_value=0, max_value=100, value=60, step=10)
bobot_genre = 100 - bobot_referensi
st.sidebar.caption(f"Sisa Bobot Genre: {bobot_genre}%")

auto_pilot_90 = st.sidebar.checkbox("🚀 Auto Pilot 90+ (Override Mode)", value=True, help="Memaksa AI meracik transisi ekstrem & parameter Hi-Fi tingkat dewa, meskipun persentase diatur manual.")

# ==========================================
# 4. ANTARMUKA UTAMA (MAIN AREA)
# ==========================================
st.title("🎧 Music Prompt Studio Pro v5.0")
st.markdown("Mesin Arsitektur Musik AI dengan **Dinamika Vokal Otomatis, Master Packaging SEO, dan Auto Pilot 90+ Override.**")

url_youtube = st.text_input("🔗 Link Lagu Referensi YouTube (Opsional)", placeholder="https://www.youtube.com/watch?v=...")
ide_tambahan = st.text_area("💡 Ide Tema / Lirik Spesifik (Opsional)", placeholder="Misal: Saya ingin tema frekuensi menembus batas dimensi...")

if st.button("✨ Generate Arsitektur Musik", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ Gemini API Key belum dimasukkan!")
    else:
        with st.spinner("🚀 Menghitung probabilitas frekuensi dan meracik Master Blueprint..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                
                # --- LOGIKA KOMPOSISI & PERSENTASE ---
                data_youtube_teks = ""
                teks_genre = f"{genre_utama}" if genre_kombinasi == "Tidak Ada" else f"Peleburan (Fusion) mulus antara {genre_utama} dan {genre_kombinasi}"
                
                if url_youtube:
                    hasil_ekstrak = extract_youtube_data(url_youtube)
                    data_youtube_teks = f"\nREFERENSI YOUTUBE (Analisis data ini):\n{hasil_ekstrak}\n"
                    instruksi_komposisi = f"KOMPOSISI MUSIK (WAJIB IKUTI TAKARAN INI):\n- {bobot_referensi}% Fondasi Utama: Inti sari, tempo, dan 'vibe' dari referensi YouTube.\n- {bobot_genre}% Bumbu Pelengkap: {teks_genre}.\nCiptakan aransemen di mana referensi YouTube tetap menjadi pemegang kendali utama sesuai persentase."
                else:
                    instruksi_komposisi = f"KOMPOSISI MUSIK:\nFokus 100% pada {teks_genre}."

                # --- LOGIKA AUTO PILOT 90+ (STEROID MODE) ---
                if auto_pilot_90:
                    teks_autopilot = "🔥 AUTO PILOT 90+ (OVERRIDE KREATIVITAS): Walaupun takaran komposisi di atas telah ditentukan, kamu WAJIB memaksa kualitas aransemen ke level DEWA. Ciptakan transisi tak tertebak, drop ekstrem, dan WAJIB gunakan parameter Hi-Fi tingkat tinggi ('Deep Sub-Bass Resonance', 'Immersive Stereo Panning', 'Sidechained Bassline'). Ini adalah mahakarya pengujian audio (Hi-Fi Testing)."
                else:
                    teks_autopilot = "Kualitas audio standar produksi profesional tanpa parameter ekstrem."

                # --- LOGIKA MODE PRODUKSI (SINGLE VS KOMPILASI) ---
                if mode_produksi == "Kompilasi (Long Duration)":
                    teks_mode = f"""
                    TUGAS UTAMA: Buat Master Blueprint untuk VIDEO KOMPILASI YOUTUBE berdurasi panjang yang berisi {jumlah_lagu} variasi trek berurutan.

                    📦 BAGIAN 1: MASTER PACKAGING SEO (Hanya tulis 1 kali)
                    - 5 VARIASI JUDUL YOUTUBE SEO: Bombastis, penargetan audiens internasional (contoh: Ultimate Bass Test, Hi-Fi System Check).
                    - 1 DESKRIPSI MASTER: SEO friendly, menarik, wajib berisi template Timestamps (00:00 Track 1, 03:00 Track 2, dst).
                    - 1 PROMPT THUMBNAIL MASTER: Instruksi visual detail bergaya sinematik/teknis untuk sampul depan.
                    - 1 PROMPT BACKGROUND LOOP: Instruksi deskripsi visual untuk gambar latar/animasi (seperti glowing subwoofers, neon cyber soundwaves) yang sangat estetik untuk di-looping berjam-jam sebagai background video.

                    🎵 BAGIAN 2: TRACKLIST GENERATOR ({jumlah_lagu} Lagu)
                    Buat {jumlah_lagu} instruksi trek (prompt Suno) yang mengalir sebagai satu "Perjalanan Audio" berdasarkan instruksi komposisi dasar.
                    🎤 ROTASI VOKAL DINAMIS (PENTING): Untuk setiap trek, kamu WAJIB merotasi/mengubah jenis dan nada vokal secara drastis (misal: Trek 1 Deep Male Baritone, Trek 2 Ethereal Female Soprano, Trek 3 Robotic Vocoder, dst) agar penonton tidak bosan menguji rentang frekuensi speaker mereka.
                    
                    Format setiap trek:
                    - NAMA TREK: [Beri judul unik trek ini]
                    - STYLE OF MUSIC (Maks 120 Karakter): Gabungkan instruksi komposisi, kekuatan Auto Pilot 90+, dan Vokal Dinamis di sini.
                    - LIRIK & TAG STRUKTUR: (Tulis lengkap)
                    """
                else:
                    teks_mode = """
                    TUGAS UTAMA: Buat Master Blueprint untuk 1 SINGLE TRACK.
                    Sediakan: 1 Judul YouTube SEO, 1 Deskripsi Singkat, 1 Prompt Thumbnail/Background Visual, Style of Music (Maks 120 Karakter), dan lirik lengkap.
                    """

                # --- RAKIT PROMPT FINAL UNTUK AI ---
                prompt_sistem = f"""
                Bertindaklah sebagai Produser Musik Global, Ahli Strategi SEO YouTube, dan Master Prompt Suno AI.
                {data_youtube_teks}
                IDE TEMA TAMBAHAN PENGGUNA: "{ide_tambahan if ide_tambahan else 'Gunakan imajinasi kreatifmu untuk dunia audiophile.'}"

                {instruksi_komposisi}
                {teks_autopilot}

                {teks_mode}

                🛡️ VAKSIN ANTI-COPYRIGHT & ATURAN STRUKTUR MUTLAK (WAJIB PATUHI):
                1. Lirik WAJIB 100% ORIGINAL dalam bahasa Inggris. Gunakan metafora teknis/ruang. DILARANG KERAS menyalin lirik, melodi, atau frasa klise lagu pop komersial.
                2. KUNCI STRUKTUR AUDIO: Pastikan tag instruksi (seperti [Verse], [Build-up], [Heavy Sub-Bass Drop], [Chorus]) TETAP MENYATU dalam satu blok teks dengan liriknya. Jangan pernah memisahkan lirik dari tag pembentuk suaranya agar render vokal tidak rusak.
                
                Tampilkan hasil akhir menggunakan format Markdown yang sangat rapi.
                """

                # --- EKSEKUSI ---
                response = model.generate_content(prompt_sistem)
                hasil_prompt = response.text
                
                st.success("✅ Master Blueprint Berhasil Dibuat!")
                st.markdown("### 📋 Hasil Ekstraksi (Siap Dieksekusi):")
                st.info(hasil_prompt)
                
                save_to_db(prompt_sistem, hasil_prompt)

            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")

# ==========================================
# 5. RIWAYAT DATABASE (EXPANDER)
# ==========================================
st.divider()
with st.expander("📂 Buka Riwayat Master Blueprint Sebelumnya"):
    try:
        conn = sqlite3.connect('studio_storage.db')
        c = conn.cursor()
        c.execute("SELECT date, result FROM history ORDER BY id DESC LIMIT 5")
        rows = c.fetchall()
        for row in rows:
            st.markdown(f"**🗓️ {row[0]}**")
            st.code(row[1][:200] + "...", language="markdown")
            st.divider()
        conn.close()
    except Exception as e:
        st.write("Belum ada riwayat atau database tidak terbaca.")
