import os
import sys
import json
import time
import tempfile
import yt_dlp
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from groq import Groq
from google import genai
from google.genai import types

load_dotenv()

INDEX_FILE = "baps_video_index.json"
PLAYLIST_URL = os.getenv("PLAYLIST_URL", "https://www.youtube.com/playlist?list=PLOX7n0cygMYA19eaokQqliIzEhz--1BoK")

groq_keys_env = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
groq_api_keys = [k.strip() for k in groq_keys_env.split(",") if k.strip()]
current_groq_idx = 0

gemini_keys_env = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
gemini_api_keys = [k.strip() for k in gemini_keys_env.split(",") if k.strip()]
current_gemini_idx = 0

IS_ONCE_MODE = (os.getenv("RUN_ONCE", "false").lower() in ("true", "1") or "--once" in sys.argv)
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "25"))
ALL_APIS_EXHAUSTED = False

print(f"API Setup: {len(groq_api_keys)} Groq key(s), {len(gemini_api_keys)} Gemini key(s). Mode: {'BATCH (--once)' if IS_ONCE_MODE else 'CONTINUOUS DAEMON'}")

def get_groq_client():
    if not groq_api_keys: return None
    return Groq(api_key=groq_api_keys[current_groq_idx])

def get_gemini_client():
    if not gemini_api_keys: return None
    return genai.Client(api_key=gemini_api_keys[current_gemini_idx])

def rotate_groq():
    global current_groq_idx
    if not groq_api_keys: return False
    current_groq_idx = (current_groq_idx + 1) % len(groq_api_keys)
    print(f"  [ROTATION] Switched to Groq Key #{current_groq_idx + 1}/{len(groq_api_keys)}")
    return current_groq_idx != 0

def rotate_gemini():
    global current_gemini_idx
    if not gemini_api_keys: return False
    current_gemini_idx = (current_gemini_idx + 1) % len(gemini_api_keys)
    print(f"  [ROTATION] Switched to Gemini Key #{current_gemini_idx + 1}/{len(gemini_api_keys)}")
    return current_gemini_idx != 0

def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_index(index_data):
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=4, ensure_ascii=False)

def get_playlist_videos(url):
    print(f"Fetching video list from Playlist: {url}")
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }
    videos = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    videos.append({
                        'id': entry['id'],
                        'title': entry['title'],
                        'link': f"https://www.youtube.com/watch?v={entry['id']}"
                    })
    except Exception as e:
        print(f"Error fetching playlist: {e}")
    return videos

def get_transcript(video_id):
    try:
        t_list = YouTubeTranscriptApi().list(video_id)
        t = list(t_list)[0]
        if t.language_code != 'en':
            try: t = t.translate('en')
            except: pass
        return TextFormatter().format_transcript(t.fetch())
    except Exception as e:
        return None

def parse_gemini_json(text):
    clean_text = text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(clean_text)

def analyze_text_robust(transcript_text):
    prompt = """
    You are an expert in BAPS Swaminarayan theology. Analyze this discourse by Mahant Swami Maharaj in detail.
    Categorize the discourse into 1 to 4 of the following EXACT Gujarati spiritual concepts ONLY. Do not invent any other categories.
    Valid Categories: ["Samp", "Ekta", "Suhradbhav", "Divyabhav", "Mahima", "Niyam-Dharma", "Agna", "Daspanu", "Katha-Varta", "Bhakti", "Satsang", "Seva", "Satpurush", "Akshar-Purushottam", "Moksha", "Atma-Nishtha", "Nirdosh Buddhi", "Gnan", "Vairagya", "Samagam", "Prarthana", "Shanti", "Anand", "Yagna", "Dhyan", "Gunatit", "Guru", "Nishtha", "Sanyam", "Sankhya", "Purusharth", "Sadhana"]
    Return ONLY a valid JSON object in this precise format without any markdown blocks:
    {
        "categories": ["Samp", "Ekta"],
        "detailed_summary_en": "<A comprehensive 3-5 sentence summary of the core messages in English>",
        "detailed_summary_gu": "<તે જ આધ્યાત્મિક સંદેશનો ૩-૫ વાક્યોમાં સુંદર અને શુદ્ધ ગુજરાતીમાં સારાંશ>"
    }
    """
    payload = f"{prompt}\n\nTranscript:\n{transcript_text[:20000]}"
    
    while True:
        # 1. Groq LLM Loop
        groq_client = get_groq_client()
        if groq_client:
            # We multiply attempts by 2 to allow for transient JSON validation retries
            for _ in range((len(groq_api_keys) if groq_api_keys else 1) * 2):
                try:
                    chat_completion = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": payload}],
                        model="qwen/qwen3.8-27b",
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    return json.loads(chat_completion.choices[0].message.content)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str:
                        rotate_groq() 
                        groq_client = get_groq_client()
                    elif "json_validate_failed" in error_str:
                        # Groq model occasionally hallucinates an extra brace (e.g., "}}").
                        print("  -> Groq made a JSON typo (Validation Failed). Retrying Groq...")
                        time.sleep(2)
                    else:
                        print(f"  -> Groq Text error: {e}. Falling back to Gemini...")
                        break
            
        # 2. Gemini LLM Loop
        gemini_client = get_gemini_client()
        if gemini_client:
            # Allow multiple retries per key for 503s
            for _ in range((len(gemini_api_keys) if gemini_api_keys else 1) * 3):
                try:
                    resp = gemini_client.models.generate_content(
                        model='gemini-3.5-flash', 
                        contents=payload, 
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    return parse_gemini_json(resp.text)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str:
                        rotate_gemini()
                        gemini_client = get_gemini_client()
                    elif "503" in error_str:
                        print("  -> Gemini 503 (Server Busy). Retrying in 5s...")
                        time.sleep(5)
                    else:
                        print(f"  -> Gemini Text error: {e}")
                        break
                        
        # 3. Exhausted All Keys
        if IS_ONCE_MODE:
            print("  -> All API Keys exhausted for this cycle. Exiting analyze_text_robust (batch mode).")
            global ALL_APIS_EXHAUSTED
            ALL_APIS_EXHAUSTED = True
            return None
        print("  -> Exhausted ALL API Keys on both services. Sleeping for 1 hour (3600s) to reset limits...")
        time.sleep(3600)

def analyze_audio_robust(temp_file):
    prompt = """
    You are an expert in BAPS Swaminarayan theology. Analyze this discourse by Mahant Swami Maharaj in detail.
    Categorize the discourse into 1 to 4 of the following EXACT Gujarati spiritual concepts ONLY. Do not invent any other categories.
    Valid Categories: ["Samp", "Ekta", "Suhradbhav", "Divyabhav", "Mahima", "Niyam-Dharma", "Agna", "Daspanu", "Katha-Varta", "Bhakti", "Satsang", "Seva", "Satpurush", "Akshar-Purushottam", "Moksha", "Atma-Nishtha", "Nirdosh Buddhi", "Gnan", "Vairagya", "Samagam", "Prarthana", "Shanti", "Anand", "Yagna", "Dhyan", "Gunatit", "Guru", "Nishtha", "Sanyam", "Sankhya", "Purusharth", "Sadhana"]
    Return ONLY a valid JSON object in this precise format without any markdown blocks:
    {
        "categories": ["Samp", "Ekta"],
        "detailed_summary_en": "<A comprehensive 3-5 sentence summary of the core messages in English>",
        "detailed_summary_gu": "<તે જ આધ્યાત્મિક સંદેશનો ૩-૫ વાક્યોમાં સુંદર અને શુદ્ધ ગુજરાતીમાં સારાંશ>"
    }
    """
    while True:
        # 1. Groq Whisper Loop
        groq_client = get_groq_client()
        if groq_client:
            for _ in range(len(groq_api_keys) if groq_api_keys else 0):
                try:
                    with open(temp_file, "rb") as file:
                        transcription = groq_client.audio.transcriptions.create(
                            file=(temp_file, file.read()),
                            model="whisper-large-v3",
                            response_format="json"
                        )
                    transcript_text = transcription.text
                    print("  -> Groq Whisper successful. Passing to LLM...")
                    return analyze_text_robust(transcript_text) 
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str:
                        rotate_groq()
                        groq_client = get_groq_client()
                    else:
                        print(f"  -> Groq Whisper error: {e}. Falling back to Gemini Audio...")
                        break
                        
        # 2. Gemini Audio Loop
        gemini_client = get_gemini_client()
        if gemini_client:
            for _ in range((len(gemini_api_keys) if gemini_api_keys else 1) * 3):
                audio_file = None
                try:
                    audio_file = gemini_client.files.upload(file=temp_file)
                    resp = gemini_client.models.generate_content(
                        model='gemini-3.5-flash', 
                        contents=[audio_file, prompt], 
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    gemini_client.files.delete(name=audio_file.name)
                    return parse_gemini_json(resp.text)
                except Exception as e:
                    if audio_file:
                        try: gemini_client.files.delete(name=audio_file.name)
                        except: pass
                    
                    error_str = str(e)
                    if "429" in error_str:
                        rotate_gemini()
                        gemini_client = get_gemini_client()
                    elif "503" in error_str:
                        print("  -> Gemini Audio 503 (Server Busy). Retrying in 5s...")
                        time.sleep(5)
                    else:
                        print(f"  -> Gemini Audio error: {e}")
                        break
                        
        # 3. Exhausted All Keys
        if IS_ONCE_MODE:
            print("  -> All Audio API Keys exhausted for this cycle. Exiting analyze_audio_robust (batch mode).")
            global ALL_APIS_EXHAUSTED
            ALL_APIS_EXHAUSTED = True
            return None
        print("  -> Exhausted ALL Audio API Keys on both services. Sleeping for 1 hour (3600s) to reset limits...")
        time.sleep(3600)

def index_video(video):
    vid_id = video['id']
    transcript = get_transcript(vid_id)
    
    analysis = None
    if transcript:
        analysis = analyze_text_robust(transcript)
        if analysis and not analysis.get('categories'):
            print(f"  -> YouTube transcript yielded no categories (likely auto-generated garbage). Discarding and falling back to audio...")
            analysis = None
            
    if not analysis:
        print(f"  -> Fetching audio for {video['title']}...")
        temp_file = os.path.join(tempfile.gettempdir(), f"{vid_id}.m4a")
        ydl_opts = {
            'format': 'ba/b',
            'outtmpl': os.path.join(tempfile.gettempdir(), f"{vid_id}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            },
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '64',
            }]
        }
        
        for download_attempt in range(3):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video['link']])
                break
            except Exception as e:
                print(f"  -> Download error (attempt {download_attempt+1}): {e}")
                time.sleep(5)
        
        if not os.path.exists(temp_file):
            candidates = [os.path.join(tempfile.gettempdir(), f) for f in os.listdir(tempfile.gettempdir()) if f.startswith(vid_id) and f.endswith(('.m4a', '.mp3', '.opus', '.aac', '.mp4'))]
            if candidates:
                temp_file = candidates[0]
            else:
                print("  -> Failed to download audio entirely. Skipping.")
                return None
            
        print("  -> Transcribing/Analyzing audio with Key Rotation System...")
        analysis = analyze_audio_robust(temp_file)
        
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
            
    return analysis

def main():
    print("==================================================")
    print("Starting BAPS Playlist Indexer Run (Auto Key Rotation enabled)")
    print("==================================================")
    
    videos = get_playlist_videos(PLAYLIST_URL)
    
    if not videos:
        print("Failed to retrieve playlist or playlist is empty.")
        return 0
        
    index = load_index()
    print(f"Playlist contains {len(videos)} videos. Database currently has {len(index)} videos indexed.")
    
    newly_indexed_count = 0
    consecutive_fails = 0

    for video in videos:
        vid_id = video['id']
        
        if vid_id in index:
            continue
            
        print(f"\nProcessing: {video['title']}")
        analysis = index_video(video)
        
        if analysis:
            consecutive_fails = 0
            cats = analysis.get('categories', [])
            summary_en = analysis.get('detailed_summary_en') or analysis.get('detailed_summary', '')
            summary_gu = analysis.get('detailed_summary_gu', '')
            index[vid_id] = {
                'title': video['title'],
                'link': video['link'],
                'categories': cats,
                'summary': summary_en,
                'summary_gu': summary_gu
            }
            save_index(index)
            newly_indexed_count += 1
            if cats:
                print(f"  -> Saved! ({newly_indexed_count} indexed this run). Categories: {', '.join(cats)}")
            else:
                print(f"  -> Saved as Uncategorized (No spiritual content found).")

            if IS_ONCE_MODE and newly_indexed_count >= MAX_BATCH_SIZE:
                print(f"\n[BATCH LIMIT REACHED] Successfully indexed {MAX_BATCH_SIZE} videos this run. Exiting to allow Git commit & push!")
                break
        else:
            consecutive_fails += 1
            print("  -> Failed to analyze. (Will retry in next cycle)")
            if ALL_APIS_EXHAUSTED:
                print("\n[BATCH FINISHED] All API key quotas exhausted across Groq and Gemini. Exiting cleanly to commit progress.")
                break
            if IS_ONCE_MODE and consecutive_fails >= 8:
                print("\n[BATCH FINISHED] Encountered 8 consecutive failures (temporary glitch or bot block). Exiting to commit current progress.")
                break
            
        print("  -> Base Sleeping 2s...")
        time.sleep(2)
        
    pending = [v for v in videos if v['id'] not in index]
    if pending:
        print(f"\n[SCAN COMPLETE] {len(pending)} video(s) pending or missed out of {len(videos)}.")
    else:
        print(f"\n[SCAN COMPLETE] All {len(videos)} videos in playlist are fully indexed!")
    return len(pending)

if __name__ == "__main__":
    if os.getenv("RUN_ONCE", "false").lower() in ("true", "1") or "--once" in sys.argv:
        print("[MODE] Running single scan pass (Cloud Cron / GitHub Actions)...")
        main()
        sys.exit(0)
        
    while True:
        pending_count = 0
        try:
            pending_count = main() or 0
        except Exception as e:
            print(f"Fatal error in main loop: {e}")
            
        if pending_count > 0:
            wait_time = int(os.getenv("PENDING_RETRY_SECONDS", "60"))
            print(f"\n[AUTO-RECHECK] Retrying {pending_count} pending videos in {wait_time}s...\n")
            time.sleep(wait_time)
        else:
            wait_time = int(os.getenv("CHECK_INTERVAL_SECONDS", "600"))
            print(f"\n[MONITOR] All videos up to date. Constantly checking for new BAPS uploads in {wait_time//60} mins ({wait_time}s)...\n")
            time.sleep(wait_time) 
