import os
import re
import time
import json
import requests
import base64
import pymysql
import io
from pathlib import Path
from datetime import datetime, timedelta
from zai import ZhipuAiClient
from dotenv import find_dotenv, load_dotenv
from qcloud_cos import CosConfig, CosS3Client
from mutagen.mp3 import MP3

# Load environment variables from backend/.env first, then fall back to cwd lookup.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(find_dotenv(), override=False)
zhipu_api_key = os.getenv("ZHIPU_AI_API_KEY", "")
inworld_api_key = os.getenv("INWORLD_API_KEY", "")

# Tencent COS Configuration
cos_secret_id = os.getenv("TENCENT_COS_SECRET_ID", "")
cos_secret_key = os.getenv("TENCENT_COS_SECRET_KEY", "")
cos_region = "ap-chengdu"
cos_bucket = "ai-news-1354350417"

# MySQL Configuration
mysql_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'port': int(os.getenv("MYSQL_PORT", 3306)),
    'user': os.getenv("MYSQL_TTS_USER", "ainews"),
    'password': os.getenv("MYSQL_TTS_PASSWORD", "5518909Zk"),
    'database': os.getenv("MYSQL_DATABASE", "ai_news"),
    'charset': 'utf8mb4'
}

# Category mapping for podcast selection
CATEGORY_MAPPING = {
    "Interesting Stories": ["Culture", "Sport", "Travel"],
    "Science & Economy": ["Technology", "Business", "Science"],
    "Culture & Arts": ["Culture", "Arts"],
    "Controversy & Social Commentary": ["Politics", "Environment"],
    "Lifestyle Tips": ["Health", "Travel"]
}


def get_mysql_connection():
    """Create MySQL connection"""
    return pymysql.connect(**mysql_config)


def format_seconds_to_time(seconds):
    """Convert seconds to mm:ss format."""
    if seconds is None:
        return "Unknown"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:02d}"


def select_news_for_podcast():
    """
    Select 5 news articles from MySQL for podcast generation.
    One from each category: Interesting Stories, Science & Economy, Culture & Arts, Controversy & Social Commentary, Lifestyle Tips
    Returns news in the specified order.
    """
    conn = get_mysql_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    selected_news = []
    category_order = [
        "Interesting Stories",
        "Science & Economy",
        "Culture & Arts",
        "Controversy & Social Commentary",
        "Lifestyle Tips",
    ]

    try:
        # Get the latest publish date
        cursor.execute("SELECT MAX(publish_date) as latest_date FROM news")
        result = cursor.fetchone()
        latest_date = result['latest_date']

        if not latest_date:
            print("No news found in database")
            return []

        # For each category, select one random news within the last 7 days
        for category_key in category_order:
            categories = CATEGORY_MAPPING[category_key]
            placeholders = ','.join(['%s'] * len(categories))

            query = f"""
                SELECT id, title, content, category, cover_image, original_url,
                       source, publish_date
                FROM news
                WHERE category IN ({placeholders})
                AND publish_date >= DATE_SUB(%s, INTERVAL 7 DAY)
                ORDER BY publish_date DESC, RAND()
                LIMIT 1
            """

            cursor.execute(query, (*categories, latest_date))
            news = cursor.fetchone()

            if news:
                selected_news.append(news)
                print(f"✓ Selected from {category_key}: {news['title'][:50]}...")
            else:
                print(f"✗ No news found for category: {category_key}")

        return selected_news

    except Exception as e:
        print(f"Error selecting news: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def generate_podcast_data_via_glm(news_list):
    """
    Uses GLM-4-Plus to generate podcast script.
    """
    if not zhipu_api_key:
        print("Error: ZHIPU_AI_API_KEY not found.")
        return None

    client = ZhipuAiClient(api_key=zhipu_api_key)

    context = ""
    for i, news in enumerate(news_list):
        context += f"--- NEWS {i+1} ---\nTITLE: {news['title']}\nCONTENT: {news['content']}\n\n"

    system_prompt = f"""
You are a professional Podcast Producer. Your hosts are Brian (Male) and Jessica (Female).

## THE MISSION:
Create a high-energy, 100% English deep-dive news chat covering ALL {len(news_list)} provided articles. This should feel like a top-tier trending podcast—witty, surprising, and human.

## DIALOGUE RULES (The 'script' field):
1. **STRICT IMMERSION**: 100% natural English. No teaching, no Chinese in script.
2. **NAME LOGIC**: Brian is Host_A, Jessica is Host_B. Address EACH OTHER by name naturally (but not every turn).
3. **BANNED WORDS**: NEVER use "Exactly!" or "Absolutely!". Use alternatives like "Right!", "True!", "For sure!", "I know!", "Totally!".
4. **TURN LENGTH**: 1-3 sentences per turn. Vary the length - some quick reactions, some deeper thoughts.
5. **EMOTIONAL DYNAMICS & VARIETY**:
   - **Mix it Up**: Do NOT start every sentence with an exclamation like "Wait, what?" or "That's wild!".
   - **Vary Reactions**: Use a blend of:
     * *Shock*: "No way...", "Are you serious?", "Hold on..."
     * *Curiosity*: "How does that even work?", "I wonder why...", "What's the story behind that?"
     * *Dry Humor/Sarcasm*: "Sounds like a party I'd skip.", "So fancy."
     * *Thoughtful Insight*: "It makes sense if you think about...", "It's a clash of cultures, really."
     * *Personal Connection*: "I've always wondered about that...", "That reminds me of...", "I can totally see why..."
     * *Playful Disagreement*: "Come on, that's a bit much...", "I don't know about that...", "Really? I see it differently..."
   - **Rhetorical Questions**: Use them to engage the partner.
   - **Build on Each Other**: Don't just react - add new information, make connections, or challenge each other's points.
   - **Show Discovery**: Let hosts guess wrong, be surprised by unexpected details, or have "aha!" moments.
6. **NATURAL TRANSITIONS** (CRITICAL):
   - **AVOID template transitions**: NEVER use "Switching gears", "Moving on", "Next up", "Finally", "Which brings us to".
   - **Use emotion-based bridges**: Let the previous topic's emotion lead into the next.
     * After something shocking: "Well, if you think that was wild, wait until you hear this..."
     * After something funny: "Okay, from ancient bathroom humor to... modern bus rules?"
     * After something serious: "On a lighter note..." or "Here's something completely different..."
   - **Use thematic connections**: Find natural links between stories.
   - **Direct dive-in**: Sometimes just start the next story naturally without any transition phrase.
7. **DEPTH OVER BREADTH**:
   - Spend 4-6 exchanges per story minimum. Really dig in.
   - Pick 2-3 interesting details per story and explore them deeply.
   - Ask "why" questions, make comparisons, share reactions.
   - Let one host play devil's advocate or represent a different viewpoint occasionally.
8. **PODCAST FEEL**:
   - Use filler words naturally: "I mean...", "You know...", "Like...", "Right?", "Honestly..."
   - Interrupt naturally sometimes (but not too much).
   - Show genuine curiosity and surprise.
   - Make it conversational, not scripted.
   - Let hosts have slightly different perspectives on controversial topics.
9. **STRUCTURE**:
   - **OPENING** (2-3 exchanges): Brief, warm welcome. Introduce yourselves naturally.
   - **MAIN CONTENT**: Cover all news stories with depth (4-6 exchanges each).
   - **CLOSING** (2-3 exchanges): Natural wrap-up. Thank listeners, sign off warmly.

## JSON OUTPUT SCHEMA:
{{
  "script": "string"
}}
"""

    user_prompt = f"### INPUT NEWS ###\n{context}\n\n### TASK ###\nGenerate the JSON with proper structure:\n1. OPENING: 2-3 exchanges - warm welcome, introduce Brian and Jessica\n2. MAIN CONTENT: Cover all {len(news_list)} stories with depth (4-6 exchanges per story)\n   - Let hosts discover surprising details together\n   - Include playful disagreements on controversial topics\n   - Use emotion-based transitions (NO template phrases like 'Switching gears', 'Moving on', 'Finally')\n3. CLOSING: 2-3 exchanges - natural wrap-up, thank listeners\n\nRules: NO 'Exactly!' or 'Absolutely!'. Use alternatives: 'Right!', 'True!', 'For sure!', 'Totally!'."

    print("Requesting GLM-4-Plus to generate podcast script...")
    try:
        response = client.chat.completions.create(
            model="glm-4-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        raw_content = response.choices[0].message.content
        return json.loads(raw_content)
    except Exception as e:
        print(f"Error generating podcast data: {e}")
        return None


def post_process_script(script):
    """Hard-fixes logical errors and removes banned words before TTS."""
    lines = script.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith("Host_A:"):
            line = line.replace("Brian,", "Jessica,").replace("Brian!", "Jessica!")
        elif line.startswith("Host_B:"):
            line = line.replace("Jessica,", "Brian,").replace("Jessica!", "Brian!")

        # Replace banned words with alternatives
        line = re.sub(r'\bExactly!?\b', 'Right!', line, flags=re.IGNORECASE)
        line = re.sub(r'\bAbsolutely!?\b', 'Totally!', line, flags=re.IGNORECASE)
        new_lines.append(line)
    return '\n'.join(new_lines)


def clean_script_for_tts(text):
    """Cleans structural markers for TTS processing."""
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'^(Part|PART|Transition|###|---).*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'Brian:', 'Host_A:', text)
    text = re.sub(r'Jessica:', 'Host_B:', text)
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)


def generate_audio_via_inworld(script_text):
    """
    Converts script to audio using Inworld TTS API.
    Returns the combined audio data as bytes.
    """
    if not inworld_api_key:
        print("Error: INWORLD_API_KEY not found.")
        return None

    clean_text = clean_script_for_tts(script_text)
    lines = clean_text.split('\n')
    audio_segments = []

    max_retries = 5
    print("\n" + "="*60)
    print("Generating podcast audio via Inworld TTS...")
    print("Using voices: Brian (male), Jessica (female)")
    print("="*60)

    for line in lines:
        if not line.strip():
            continue

        # Determine speaker and text
        if line.startswith("Host_A:"):
            voice_id = "Brian"
            text = line.replace("Host_A:", "").strip()
        elif line.startswith("Host_B:"):
            voice_id = "Jessica"
            text = line.replace("Host_B:", "").strip()
        else:
            continue

        if not text:
            continue

        # Call Inworld TTS API for each segment
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.inworld.ai/tts/v1/voice",
                    headers={
                        "Authorization": f"Bearer {inworld_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": text,
                        "voiceId": voice_id,
                        "modelId": "inworld-tts-1.5-max",
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "sampleRateHertz": 24000
                        },
                        "temperature": 1.2,
                        "speed": 1.03,
                        "applyTextNormalization": "ON"
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    audio_b64 = result.get("audioContent", "")
                    if audio_b64:
                        audio_data = base64.b64decode(audio_b64)
                        audio_segments.append(audio_data)
                        print(f"✓ Generated {len(audio_data)} bytes for {voice_id}")
                        break
                    else:
                        print(f"✗ No audio data found in response for {voice_id}")
                        break
                elif response.status_code == 429:
                    wait_time = 10
                    print(f"Rate limit (429). Waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"Error {response.status_code}: {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)

            except Exception as e:
                print(f"✗ Exception: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"Failed to generate audio after {max_retries} retries")

    # Combine all audio segments
    if audio_segments:
        combined_audio = b''.join(audio_segments)
        print(f"\n✓ Successfully generated combined podcast audio")
        print(f"✓ Total audio size: {len(combined_audio)} bytes")

        # Calculate duration by summing each segment's duration
        try:
            total_duration = 0.0
            for segment in audio_segments:
                audio_file = MP3(io.BytesIO(segment))
                total_duration += audio_file.info.length
            duration = int(total_duration)
            print(f"✓ Audio duration: {duration} seconds")
            return combined_audio, duration
        except Exception as e:
            print(f"⚠ Warning: Could not calculate duration: {e}")
            return combined_audio, None
    else:
        print("No audio segments were generated.")
        return None, None


def upload_to_tencent_cos(audio_data, filename):
    """
    Upload audio file to Tencent COS.
    Returns the public URL of the uploaded file.
    """
    if not cos_secret_id or not cos_secret_key:
        print("Error: Tencent COS credentials not found.")
        return None

    try:
        # Initialize COS client
        config = CosConfig(Region=cos_region, SecretId=cos_secret_id, SecretKey=cos_secret_key)
        client = CosS3Client(config)

        # Upload file to daily_podcast folder
        key = f"daily_podcast/{filename}"

        response = client.put_object(
            Bucket=cos_bucket,
            Body=audio_data,
            Key=key,
            ContentType='audio/mpeg'
        )

        # Construct public URL
        public_url = f"https://{cos_bucket}.cos.{cos_region}.myqcloud.com/{key}"
        print(f"✓ Successfully uploaded to Tencent COS: {public_url}")
        return public_url

    except Exception as e:
        print(f"Error uploading to Tencent COS: {e}")
        return None


def save_podcast_to_mysql(title, script, audio_url, duration, news_ids):
    """
    Save podcast data to MySQL database.
    Saves to podcasts and podcast_news_mapping tables.
    """
    conn = get_mysql_connection()
    cursor = conn.cursor()

    try:
        # Insert into podcasts table
        podcast_sql = """
            INSERT INTO podcasts (title, script, audio_url, duration, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(podcast_sql, (title, script, audio_url, duration, datetime.now()))
        podcast_id = cursor.lastrowid

        # Insert podcast-news mapping
        mapping_sql = """
            INSERT INTO podcast_news_mapping (podcast_id, news_id)
            VALUES (%s, %s)
        """

        for news_id in news_ids:
            cursor.execute(mapping_sql, (podcast_id, news_id))

        conn.commit()
        cursor.close()

        print(f"✓ Successfully saved podcast to MySQL (ID: {podcast_id})")
        return podcast_id

    except Exception as e:
        conn.rollback()
        print(f"Error saving podcast to MySQL: {e}")
        return None
    finally:
        conn.close()


def generate_daily_podcast():
    """Main function to generate daily podcast"""
    print("="*60)
    print("Starting Daily Podcast Generation")
    print("="*60)

    # Step 1: Select news from MySQL
    print("\n[Step 1] Selecting news from MySQL...")
    news_list = select_news_for_podcast()

    if len(news_list) < 3:
        print(f"Error: Only found {len(news_list)} news articles. Need at least 3.")
        return

    if len(news_list) < 5:
        print(f"⚠ Warning: Only found {len(news_list)}/5 categories. Continuing anyway...")

    # Step 2: Generate podcast script and vocabulary via GLM
    print("\n[Step 2] Generating podcast script via GLM-4-Plus...")
    podcast_result = generate_podcast_data_via_glm(news_list)

    if not podcast_result:
        print("Error: Failed to generate podcast data")
        return

    raw_script = podcast_result.get("script", "")

    # Post-process script
    fixed_script = post_process_script(raw_script)
    final_script = fixed_script.replace("Brian:", "Host_A:").replace("Jessica:", "Host_B:")

    print("\n" + "="*20 + " FULL SCRIPT " + "="*20)
    print(final_script)
    print("="*60)

    # Confirmation before TTS
    print("\nReview the script above.")
    confirm = input("Proceed with TTS generation and COS upload? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted. Script was not sent to TTS.")
        return

    # Step 3: Generate audio via Inworld TTS
    print("\n[Step 3] Generating audio via Inworld TTS...")
    result = generate_audio_via_inworld(final_script)

    if not result or result[0] is None:
        print("Error: Failed to generate audio")
        return

    audio_data, duration = result

    # --- Print the detailed mm:ss duration ---
    readable_time = format_seconds_to_time(duration)
    print(f"✓ Audio generation successful!")
    print(f"✓ Total Duration: {duration} seconds ({readable_time})")
    # --------------------------

    # Step 4: Upload to Tencent COS
    print("\n[Step 4] Uploading audio to Tencent COS...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"daily_podcast_{timestamp}.mp3"
    audio_url = upload_to_tencent_cos(audio_data, filename)

    if not audio_url:
        print("Error: Failed to upload audio")
        return

    # Step 5: Save to MySQL
    print("\n[Step 5] Saving podcast data to MySQL...")
    podcast_title = f"Daily News Podcast - {datetime.now().strftime('%Y-%m-%d')}"
    news_ids = [news['id'] for news in news_list]

    podcast_id = save_podcast_to_mysql(
        title=podcast_title,
        script=final_script,
        audio_url=audio_url,
        duration=duration,
        news_ids=news_ids
    )

    if podcast_id:
        print("\n" + "="*60)
        print("✓ Daily Podcast Generation Complete!")
        print(f"✓ Podcast ID: {podcast_id}")
        print(f"✓ Audio URL: {audio_url}")
        print(f"✓ Accurate Duration: {format_seconds_to_time(duration)} ({duration}s)")
        print("="*60)
    else:
        print("\nError: Failed to save podcast to database")


if __name__ == "__main__":
    generate_daily_podcast()
