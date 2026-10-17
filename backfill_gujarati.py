import os
import json
import time
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types

load_dotenv()

INDEX_FILE = "baps_video_index.json"

groq_keys_env = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
groq_api_keys = [k.strip() for k in groq_keys_env.split(",") if k.strip()]
current_groq_idx = 0

gemini_keys_env = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
gemini_api_keys = [k.strip() for k in gemini_keys_env.split(",") if k.strip()]
current_gemini_idx = 0

def get_groq_client():
    if not groq_api_keys: return None
    return Groq(api_key=groq_api_keys[current_groq_idx])

def rotate_groq():
    global current_groq_idx
    if not groq_api_keys: return False
    current_groq_idx = (current_groq_idx + 1) % len(groq_api_keys)
    print(f"  [ROTATION] Switched to Groq Key #{current_groq_idx + 1}/{len(groq_api_keys)}")
    return current_groq_idx != 0

def translate_to_gujarati(summary_en):
    prompt = f"""
    You are an expert translator specializing in BAPS Swaminarayan spiritual discourses.
    Translate the following discourse summary into natural, fluent, and reverent Gujarati.
    Return ONLY the Gujarati translation text with no preamble or English explanation:

    {summary_en}
    """
    groq_client = get_groq_client()
    if groq_client:
        for _ in range(len(groq_api_keys) * 2 if groq_api_keys else 1):
            try:
                resp = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="openai/gpt-oss-20b",
                    temperature=0.1
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                if "429" in str(e):
                    rotate_groq()
                    groq_client = get_groq_client()
                else:
                    time.sleep(2)
    return None

def main():
    if not os.path.exists(INDEX_FILE):
        print("Database file not found.")
        return

    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    to_translate = [vid_id for vid_id, info in data.items() if not info.get('summary_gu') and info.get('summary')]
    print(f"Total videos needing Gujarati translation: {len(to_translate)} / {len(data)}")

    count = 0
    for vid_id in to_translate:
        info = data[vid_id]
        print(f"[{count+1}/{len(to_translate)}] Translating: {info.get('title', vid_id)}")
        gu_text = translate_to_gujarati(info.get('summary'))
        if gu_text:
            data[vid_id]['summary_gu'] = gu_text
            count += 1
            if count % 5 == 0:
                with open(INDEX_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                print(f"  -> Progress saved ({count} translated).")
        time.sleep(0.5)

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Done! Successfully translated {count} videos.")

if __name__ == "__main__":
    main()
