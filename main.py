import os
import argparse
import json
import time
import tempfile
from dotenv import load_dotenv
from youtube_search import YoutubeSearch
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from google import genai
from google.genai import types
import yt_dlp

# Load environment variables from .env file
load_dotenv()

# Initialize Gemini Client
try:
    client = genai.Client()
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    print("Did you forget to set GEMINI_API_KEY in your .env file?")
    exit(1)

def search_youtube(query, limit=3):
    print(f"Searching YouTube for: '{query}'...")
    try:
        results = YoutubeSearch(query, max_results=limit).to_dict()
        videos = []
        for result in results:
            videos.append({
                'id': result['id'],
                'title': result['title'],
                'link': f"https://www.youtube.com{result.get('url_suffix', '/watch?v=' + result['id'])}"
            })
        return videos
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        return []

def get_translated_transcript(video_id):
    print(f"Fetching transcript for video ID: {video_id}...")
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        transcript = list(transcript_list)[0]
        if transcript.language_code != 'en':
            try:
                transcript = transcript.translate('en')
            except Exception as e:
                pass # Ignore translation notes
        
        transcript_data = transcript.fetch()
        formatter = TextFormatter()
        text_content = formatter.format_transcript(transcript_data)
        return text_content
    except Exception as e:
        error_msg = str(e)
        if "YouTube is blocking requests" in error_msg:
            print("  -> Transcript blocked by YouTube IP limits.")
        elif "Subtitles are disabled" in error_msg:
            print("  -> Subtitles are disabled for this video.")
        else:
            print(f"  -> No transcript available.")
        return None

def analyze_transcript(transcript_text, topic):
    print(f"Analyzing transcript text for topic: '{topic}'...")
    prompt = f"""
    You are an expert content analyzer. Read the following video transcript and determine if it discusses the topic: "{topic}".
    Please provide your analysis in the following JSON format ONLY, without any markdown blocks around it:
    {{
        "relevance_score": <int from 0 to 10>,
        "is_relevant": <boolean, true if score >= 4>,
        "summary": "<A 2-3 sentence summary of how the topic is discussed, or why it's not relevant>"
    }}
    Transcript to analyze:
    {transcript_text[:20000]}
    """
    return call_gemini(prompt)

def analyze_audio_with_gemini(video_url, topic):
    print("  -> Extracting audio stream for Gemini to listen to directly...")
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, 'temp_audio.webm')
    
    # Grab the smallest/lowest quality audio stream just so Gemini can hear the words
    ydl_opts = {
        'format': 'worstaudio/worst',
        'outtmpl': temp_file,
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        print("  -> Audio downloaded. Uploading to Gemini...")
        audio_file = client.files.upload(file=temp_file)
        
        prompt = f"""
        You are an expert content analyzer. Listen to this audio and determine if the speaker discusses the topic: "{topic}".
        Please provide your analysis in the following JSON format ONLY, without any markdown blocks around it:
        {{
            "relevance_score": <int from 0 to 10>,
            "is_relevant": <boolean, true if score >= 4>,
            "summary": "<A 2-3 sentence summary of how the topic is discussed, or why it's not relevant>"
        }}
        """
        
        print(f"Analyzing audio for topic: '{topic}'...")
        result = call_gemini([audio_file, prompt])
        
        # Clean up the file from Google servers and local temp folder
        client.files.delete(name=audio_file.name)
        os.remove(temp_file)
        
        return result
    except Exception as e:
        print(f"  -> Error analyzing audio: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return None

def call_gemini(contents):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg and attempt < max_retries - 1:
                print(f"  -> Gemini API is busy (503). Retrying in 2 seconds...")
                time.sleep(2)
            elif "429" in error_msg and attempt < max_retries - 1:
                print(f"  -> Rate limit hit (429). Pausing for 30 seconds...")
                time.sleep(30)
            else:
                print(f"  -> Error communicating with Gemini: {error_msg.split('!')[0]}")
                return None
    return None

def main():
    parser = argparse.ArgumentParser(description="YouTube Topic Parser")
    parser.add_argument("--query", type=str, default="Mahant Swami Maharaj Guruhari Ashirwad", help="YouTube search query")
    parser.add_argument("--topic", type=str, default="Respect", help="The topic to filter the videos by")
    parser.add_argument("--limit", type=int, default=5, help="Number of videos to check")
    
    args = parser.parse_args()
    
    # Restored the Guruhari Ashirwad query constraint 
    combined_query = f"{args.query} {args.topic}"
    videos = search_youtube(combined_query, limit=args.limit)
    
    if not videos:
        print("No videos found.")
        return

    print(f"\nFound {len(videos)} candidate videos. Processing...\n")
    
    relevant_videos = []

    for video in videos:
        print(f"--- Processing: {video['title']} ---")
        
        analysis = None
        transcript = get_translated_transcript(video['id'])
        
        if transcript:
            analysis = analyze_transcript(transcript, args.topic)
        else:
            # The Magic Fallback: If no transcript, listen to the audio directly!
            analysis = analyze_audio_with_gemini(video['link'], args.topic)
            
        if analysis:
            print(f"Score: {analysis.get('relevance_score', 0)}/10")
            print(f"Summary: {analysis.get('summary', '')}\n")
            
            if analysis.get('is_relevant'):
                video['analysis'] = analysis
                relevant_videos.append(video)
        else:
            print("Could not analyze video.\n")
            
        print("  -> (Waiting 15 seconds to avoid API rate limits...)")
        time.sleep(15)

    print("\n==================================================")
    print(f"FINAL RESULTS: VIDEOS ABOUT '{args.topic.upper()}'")
    print("==================================================")
    
    if not relevant_videos:
        print(f"No videos strongly relevant to the topic '{args.topic}' were found.")
    
    for rv in relevant_videos:
        print(f"\nTitle: {rv['title']}")
        print(f"Link: {rv['link']}")
        print(f"Relevance Score: {rv['analysis'].get('relevance_score', '?')}/10")
        print(f"Summary: {rv['analysis'].get('summary', '')}")

if __name__ == "__main__":
    main()
