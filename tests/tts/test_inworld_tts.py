import os
import wave
import re
import time
import json
import requests
import base64
from zai import ZhipuAiClient
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
zhipu_api_key = os.getenv("ZHIPU_AI_API_KEY", "")
inworld_api_key = os.getenv("INWORLD_API_KEY", "")

# Set up the wave file helper
def save_wave_file(filename, pcm_data, channels=1, rate=24000, sample_width=2):
    """
    Saves raw PCM16 data into a playable WAV file.
    """
    try:
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
        print(f"Successfully saved: {filename}")
    except Exception as e:
        print(f"Error saving wave file: {e}")

def save_audio_file(filename, audio_data):
    """Saves audio data (MP3 format) to a file."""
    try:
        with open(filename, 'wb') as f:
            f.write(audio_data)
        print(f"✓ Successfully saved: {filename} (MP3, {len(audio_data)} bytes)")
        return True
    except Exception as e:
        print(f"✗ Error saving audio file: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_podcast_data_via_glm(news_list):
    """
    Uses GLM-4-Plus to generate:
    1. A pure English conversational podcast script (Strict immersion).
    2. A standalone vocabulary list with STRICT JSON keys for the DB.
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
     * *Dry Humor/Sarcasm*: "36 holes in one bathroom? Sounds like a party I'd skip.", "A VIP line for department stores? So fancy."
     * *Thoughtful Insight*: "It makes sense if you think about the climate...", "It's a clash of cultures, really."
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
     * "You know what else is underground? History."
     * "From people hiding from winter to people hiding from... the sun?"
   - **Direct dive-in**: Sometimes just start the next story naturally without any transition phrase.
     * "So, Jessica, have you heard about the bikini situation in Sydney?"
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
   - **OPENING** (2-3 exchanges): Brief, warm welcome. Introduce yourselves naturally. Example:
     * Brian: "Hey everyone, welcome back! I'm Brian."
     * Jessica: "And I'm Jessica. We've got some fascinating stories today."
     * Brian: "Let's dive in."
   - **MAIN CONTENT**: Cover all news stories with depth (4-6 exchanges each).
   - **CLOSING** (2-3 exchanges): Natural wrap-up. Thank listeners, sign off warmly. Example:
     * Jessica: "Well, that's all we have for today."
     * Brian: "Thanks for listening, everyone. Catch you next time!"
     * Jessica: "See you soon!"

## VOCABULARY DATA (STRICT JSON KEYS):
Extract EXACTLY 10 words. You MUST use these exact keys:
- "word", "phonetic", "translation", "explanation", "example_sentence"

## JSON OUTPUT SCHEMA:
{{
  "script": "string",
  "vocabulary": [{{
      "word": "string",
      "phonetic": "string",
      "translation": "string",
      "explanation": "string",
      "example_sentence": "string"
  }}]
}}
"""

    user_prompt = f"### INPUT NEWS ###\n{context}\n\n### TASK ###\nGenerate the JSON with proper structure:\n1. OPENING: 2-3 exchanges - warm welcome, introduce Brian and Jessica\n2. MAIN CONTENT: Cover all {len(news_list)} stories with depth (4-6 exchanges per story)\n   - Let hosts discover surprising details together\n   - Include playful disagreements on controversial topics\n   - Use emotion-based transitions (NO template phrases like 'Switching gears', 'Moving on', 'Finally')\n3. CLOSING: 2-3 exchanges - natural wrap-up, thank listeners\n\nRules: NO 'Exactly!' or 'Absolutely!'. Use alternatives: 'Right!', 'True!', 'For sure!', 'Totally!'. Verify: 10 vocabulary items with all required keys."

    print("Requesting GLM-4-Plus to generate immersion data...")
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
    """
    Hard-fixes logical errors and removes banned words before TTS.
    """
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
    """
    Cleans structural markers for TTS processing.
    """
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'^(Part|PART|Transition|###|---).*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'Brian:', 'Host_A:', text)
    text = re.sub(r'Jessica:', 'Host_B:', text)
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

def generate_audio_via_inworld(script_text, output_file="daily_podcast.mp3"):
    """
    Converts script to audio using Inworld TTS API with multi-speaker support.
    Uses Brian (male) and Jessica (female) voices with enhanced audio settings.
    """
    if not inworld_api_key:
        print("Error: INWORLD_API_KEY not found.")
        return

    clean_text = clean_script_for_tts(script_text)

    # Parse script into speaker segments
    lines = clean_text.split('\n')
    audio_segments = []

    max_retries = 5
    print("\n" + "="*60)
    print("Generating immersion podcast audio via Inworld TTS...")
    print("Using voices: Brian (male), Jessica (female)")
    print("="*60)

    for line in lines:
        if not line.strip():
            continue

        # Determine speaker and text
        if line.startswith("Host_A:"):
            voice_id = "Brian"  # Male voice for Host_A (Brian)
            text = line.replace("Host_A:", "").strip()
        elif line.startswith("Host_B:"):
            voice_id = "Jessica"  # Female voice for Host_B (Jessica)
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
                        "temperature": 1.2,  # 增加自然度和语气变化 (0.5-1.5, 默认1.0)
                        "speed": 1.03,  # 稍微加快语速，更像播客节奏 (0.5-2.0, 默认1.0)
                        "applyTextNormalization": "ON"  # 自动处理数字、缩写等
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    # Decode base64 audio data (field name is 'audioContent')
                    audio_b64 = result.get("audioContent", "")
                    if audio_b64:
                        audio_data = base64.b64decode(audio_b64)
                        audio_segments.append(audio_data)
                        print(f"✓ Success! Generated {len(audio_data)} bytes of MP3 audio for {voice_id}")
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
                    print(f"Failed to generate audio for segment after {max_retries} retries")

    # Combine all audio segments
    if audio_segments:
        combined_audio = b''.join(audio_segments)
        save_audio_file(output_file, combined_audio)
        print(f"\n✓ Successfully saved combined podcast to: {output_file}")
        print(f"✓ Total audio size: {len(combined_audio)} bytes")
    else:
        print("No audio segments were generated.")

if __name__ == "__main__":
    # Use the specific news list from your crawl
    news_items = [
    {
        "title": "Where is everybody? Inside Canada’s invisible underworlds", 
        "content": "It’s lunch hour on a wintry Wednesday afternoon and the streets of Toronto’s Financial District feel eerily abandoned. Snow flurries are blowing at an angle, the sky is a leaden grey, and visibility is poor. Only a handful of pedestrians mummified in puffer coats can be seen waddling down the snow and slush-covered sidewalks of Adelaide Street West braving the 7F (-14C) windchill under the shadow of monolithic office towers . Otherwise, the streets are unsettlingly quiet. First-time visitors could be forgiven for mistaking Canada’s largest and most populous city (also the city in North America) for an abandoned, quasi-dystopian concrete jungle, rather than the humming economic engine that it is. Until, that is, they venture underground. Because come winter, many Torontonians who live and work in the heart of Canada’s finance industry move into the sprawling subterranean underworld known as the PATH, a 30-kilometer network of labyrinthine pedestrian walkways that connect shops, restaurants, residences, office towers and subway stations, as well as tourist attractions. On social media forums, users jokingly refer to the thousands of downtown office workers as gnomes, gophers or “mole people” who live and work underground. Or, that the workers in the maze of passageways are people who entered the PATH, got lost and couldn’t find their way out. In the city’s Financial District, home to Canada’s major banks, locals are easily distinguishable from tourists and visitors by the conspicuous absence of winter paraphernalia. In place of winter coats, finance bros strut the halls in their puffer and fleece vests. Sartorial sightings among the smartly dressed, badge-wearing women include bare-footed sling backs, sleeveless tops and crisply-pressed, floor-length dress pants, with nary a salt stain to be seen. “The PATH isn’t just underground shopping. It’s a part of how downtown Toronto works every day,” explains Amy Harrell, executive director of the Toronto Financial District Business Improvement Area. “It’s a weather-protected city within a city that connects people who work, travel, eat and explore downtown Toronto.” Toronto is one of several Canadian cities with built-in, climate-controlled infrastructure to protect pedestrians from frigid Canadian winters and punishing summer heat waves. Montreal’s underground is the RÉSO. The Edmonton Pedway and Winnipeg Skywalk are made up of tunnels and skywalks, while Calgary’s Plus 15 network is made up of elevated bridges and walkways. In the cult Canadian indie 2000 film “ ,” a group of young office workers bet a month’s salary on who can last the longest living in Calgary’s Plus 15 without going outside. Needless to say, cabin fever brings on their demise . The buzzing underground networks are an important part of the modern, urban lifestyle in Canada’s coldest metropolises, and can be fascinating — and disorienting — for visitors. For locals, these sheltered passages can also make surfacing almost unnecessary. When Jadiel Teófilo moved from Brazil to Toronto three years ago, it was his first time experiencing snow, sub-zero temperatures and polar vortexes. But strangely, the 28-year-old confesses the transition was relatively smooth. “Since I have the PATH, I didn’t really spend that much time in the cold,” the software engineer tells CNN Travel. Teófilo lives near the Scotiabank Arena and works in the Scotia Plaza. Apart from a short hop across the street from his apartment, he spends his entire day indoors as his 15-minute walk to work connects through the PATH.  His typical winter work attire is a light raincoat, a T-shirt and a pair of sneakers — he has yet to buy snow boots. Along with work, the PATH is also where Teófilo does his weekly grocery shopping, drug store errands, and even physiotherapy for a sprained wrist. “My first impression was that it was all very nice. It has all the shops and stores that you want,” he says. “It’s very clean and all the buildings are well maintained. But it’s just hard to navigate.” That’s because the wayfinding system is notoriously confusing. Even its own tenants say so. “If you can get lunch down here and not get lost, you can direct invest,” reads a digital ad from a major Canadian bank in the PATH. Toronto’s first underground pedestrian path was built in 1900 when the T. Eaton Co. dug a passageway to connect its main store on downtown Yonge Street (now the CF Toronto Eaton Centre) to its bargain annex building. A tunnel linking Union Station to the luxurious Royal York Hotel (now the Fairmont Royal York), was also built to protect its elite guests from the public riff raff downtown, explains Laura Miller, an associate professor of architecture at the University of Toronto. “Eaton’s was intended to contain you within their retail environment, while the Union Station Royal York tunnel was to ensure a continuity of class, like a VIP line,” Miller explains. In other words, the network was built less for weatherproofing the general public and more as a commercial strategy. The concept of private development continues to underpin the PATH’s contemporary growth, as each segment of the network today is also owned by private developers. The result is a patchwork of ad-hoc extensions that can lead to abrupt dead ends and head-scratching configurations After months of struggling with the PATH’s wayfinding system which directs visitors to neighborhoods and landmarks, Teófilo decided to create a navigational app of his own, “I wanted to maximize the usage of the path for people like me so that I don’t have to walk outside as much.” For eight months, the software engineer explored the tunnels and pathways every weekend and mapped the PATH using 3D scanning and modeling software on his phone. “I realized it was definitely bigger than I thought,” he says. The underground tunnels also link major tourist attractions in the downtown core. Technically, a visitor could book a stay at any of the hotels with PATH access — the landmark Fairmont Royal York or InterContinental Toronto Centre among others — and hit several of the city’s major attractions without stepping foot in the brisk or boiling outdoors. A dry, covered, sports-centered itinerary, for instance, could include shopping at the historic CF Toronto Eaton Centre shopping complex and a visit to the Hockey Hall of Fame at Brookfield Place. Fans headed to a Toronto Raptors or Toronto Maple Leafs hockey game at the Scotiabank Arena could grab a pre-game meal of ramen or sourdough pizza at the premium Chefs Hall in the Richmond Adelaide Centre, or a hot fried chicken sandwich and craft beer at Union Chicken in Union Station. And a more high-brow, indoor Toronto experience might include fine dining at Bymark, helmed by local celebrity chef and restaurateur Mark McEwan, or a meal at Canoe which offers sweeping views of the city from atop the TD Centre’s 54th floor, followed by a concert at Roy Thomson Hall. For years, Toronto held bragging rights to being the largest pedestrian subway network in the world. Travel websites and content creators continue to refer to the PATH as the world’s largest underground shopping complex today. But in November 2023, quietly updated its guide and passed the official title to Toronto’s friendly rival, Montreal. A spokesperson for Guinness World Records confirmed in an email to CNN that Toronto was the previous titleholder up until 2023, when Montreal’s underground network edged past Toronto with a distance of 32 kilometers. “There’s more diversity connected to our network than Toronto. We have more cultural, residential and universities while Toronto is more financial and commercial,” says Danny Pavlopoulos, founder of , which conducts walking tours in both cities. Indeed, Montreal’s underground city connects to museums and points of interest like the Place des Arts, the Musée d’art contemporain de Montréal, and hosts the annual , an underground arts festival that will host its 18th edition in April and May. Founder Frédéric Loury says the goal of the art show has always been to democratize the contemporary art scene and to meet the people where they are: along their commute or their daily errands. “I noticed that contemporary art remained an art form that was perceived as very exclusive, closed off from itself. There was no renewal of audiences,” Loury says. “Art Souterrain is about changing the access and making art more universal, more democratic.” When told that Montreal is now the new official Guinness titleholder, though, Pavlopoulos expressed cool indifference, pointing out that therein lies a key difference in the tale of two cities. “I love Toronto, I go all the time. But in Montreal we don’t care about stuff like that. It’s a very Toronto thing, to try to one up something else.” While no longer the record holder, Toronto’s PATH shows signs of growth and revival. On a busy weekday lunch hour, food courts in Toronto’s underground are packed with office workers. It’s a strong sign of recovery after the pandemic shuttered businesses and turned the underground into a ghost town. Harrell says 60 new businesses and amenities have opened in the last 18 months, including pilates and yoga studies, an indoor golf simulator and DIY painting and art event spaces. The arrival of new experiential businesses also fits into the PATH’s evolving, post-pandemic role as a third space outside work and home during the winter months Toronto resident Adam Chen recognized the underground’s potential as a third space and has been hosting since last winter. Every Saturday morning at 8 a.m. Chen meets with 20 or so strangers who have signed up to his Happy Town walks that start at the CF Toronto Eaton Centre and loop around to hit landmarks like the Metro Toronto Convention Centre and Roy Thomson Hall. The walks are not intended as guided tours, but as a warm, dry, safe space where strangers can share some friendly conversation and community during the long, cold winters. By 9:30 a.m., participants have gotten in their 10,000 steps. The only rule: talking about work is off limits. “The winter is pretty tough for a lot of people downtown,” Chen says, as the weather can be confining. “There’s a vacuum of connection and people can feel isolated. This is a time when people need to congregate the most and probably the best place for that right now, which is filled with empty spaces where people can sit and connect, is the PATH.”"
    }, 
    {
        "title": "Tines up or down? ‘Zigzag’ or ‘Continental’? Dining abroad comes with landmines to navigate", 
        "content": "When Brooke Black and her Danish husband first lived together in the United States, she doesn’t recall their different dining habits ever really being a thing. It wasn’t until the 44-year-old mother of two moved to Denmark in 2020 that she became acutely aware that she didn’t use eating utensils like her husband — or pretty much any of the Europeans around her. Growing up in Illinois, Black says her mother only set their family dinner table with forks, unless there was something being served, such as steak, that warranted a knife to cut it. “I have not used a knife my whole life,” says Black, who shares cultural commentary about her daily life in Denmark on her account. While she jokes that she “stands by that a fork can also be a knife,” she never learned to eat in the “zigzagging” manner of many Americans who will cut meat with the knife in their dominant hand before switching the fork back into that one to eat. But in Denmark at family gatherings, with her fork held in her right hand from the get-go — tines up — and her knife largely untouched beside the plate, Black soon realized she stuck out. “I get made fun of constantly by my husband’s family. At the dinner table at my mother-in-law’s house, they’re all just like, ‘What are you doing?’ because they do all eat with the fork in their left hand, tines upside down, and the knife in their right,” she says. Black says she has adapted, in public at least, to what’s widely called the Continental style of dining, digging into Danish foods like the dainty open-faced sandwiches called Smørrebrød with her fork in her left hand, turned down to eat, and the knife in her right to cut. But even when dining like a Dane, she still often feels like the odd woman out. “They all have their quiet, sensible ways of doing things. And I’m just a loud lady stabbing things,” she says. The nuances of how silverware gets wielded on either side of the pond can be dizzying. While there are some obvious differences, the subtleties can be harder to master — and how those differences came to be is murky. Tables may be set similarly across the Western world, but it’s clear that the two dominant styles of using silverware (or cutlery) — American and Continental — have some variations to navigate. , a business etiquette expert and founder of The Protocol School of Palm Beach, Florida, offers her summary of the differences between the two main styles of dining with a fork and a knife. “In the Continental style, you use both the knife and fork at the same time, bringing the fork to your mouth with the tines upside down, never putting the knife down while you’re eating,” she says. The knife remains in the dominant hand, poised to cut when necessary or push food that can’t be speared atop the fork’s overturned tines. What’s considered American style takes a cut-and-switch approach. The knife is held in the dominant hand to cut, with the fork in the non-dominant hand pinning food in place, tines down. The knife is then placed into resting position on the plate so that the fork can be switched to the dominant hand, tines facing upward to eat. “The American style is kind of like a zigzag style. You cut your meat, you put the knife down on the side of the plate, and you switch the fork from one hand to the next. So it’s a little more labor-intensive,” Whitmore says. To make matters more confusing, British dining has its own style that differs, however subtly, from Continental, according to British etiquette coach and expert , author of the book “Just Good Manners.” British and Continental styles are often confused, says Hanson, who has nearly 4 million followers on Instagram. As if that’s not varied enough, not all etiquette experts are on exactly the same page about which practices define each style. But at its essence, etiquette is about being gracious and making guests feel comfortable, no matter how they’re holding their forks. So if you’re visiting Europe, or other places where Continental-style dining dominates, as an American accustomed to zigzagging, should you switch up the way you use your silverware? It depends on the nature of your visit, says and the great-great-granddaughter of renowned etiquette expert Emily Post. When on a business trip in Europe, Post says she might try to fit in by dining the Continental way. That said, she would not expect anyone visiting her in the US from overseas to choose the American way of dining. Overall, it’s okay to dine in the way you feel most skilled and comfortable, Post says. “If you come from somewhere else, do the best you can with what you know how to do — and how to do it comfortably,” she says. But if you’re up for a challenge, Post says it’s great to have the ability to adapt to the country you’re visiting. Instead of wondering if you’re being rude by holding your fork with the tines up or down, it’s far more important you don’t hold your silverware improperly in your hand, Post says. (Clutching it in your fist, for example, is never appropriate). A fork should be held with the handle of the fork resting in the palm of your hand with your index finger stopping before the bridge of the fork, Hanson says. The knife is held with your index finger stopping where the blade and handle meet with the rest of your fingers tucked around the handle in your palm. Post laments that general dining etiquette is not something that’s taught widely in the US. “There’s nothing in our school system that teaches this to make it universal for us, and it really ends up being a household-by-household moment for people,” she says, referring to the rules of the table. Some etiquette is standard across all styles of dining. Silverware, for example, should never touch the table once you start eating, says Post, resting instead on the plate when you’re taking a pause. But other practices, for example where silverware comes to rest when you want to put your fork and knife down while eating, vary. In the American style, says Whitmore, the resting signal is when the knife, blade pointed inward, is placed across the top right edge of the plate at a subtle angle. The fork, with its tines up and handle facing outward, should be placed with its handle pointing at 4 o’clock, midway down the plate to indicate resting. (For servers who understand the etiquette, this position is a silent service message not to ask, “Are you still working on your meal?”). In the Continental (and British) styles, resting position involves a crisscross of the fork and knife in the middle of the plate, with the fork placed atop the knife, tines facing down, according to Hanson and Whitmore. There are also different silverware positions that indicate you are finished. Whitmore, who says she dines in the Continental style despite being American and living in the US, finds the technique “less noisy and obtrusive” and says learning it will allow you to fit in anywhere in the world that silverware is used to eat. “Why not learn another way so that you can have options — so that you can blend in and that your table manners are secondary to the conversation,” she says. In addition to the American and Continental styles of dining with silverware, which are the most widely used, there are other variations around the world. In British style dining, for example, fork tines should never, ever be facing upward in formal settings when the knife is also being used, according to Hanson. (In informal settings, when , that is considered acceptable, he says). Beyond which hand holds what and which direction tines are turned, some questionable table habits definitely will be noticed. “We wouldn’t say anything, but we would notice if an American cut all of their food up on the plate, which is what we really do for children in this country,” says Hanson, referring to the United Kingdom. Whitmore says that among her world travels she has seen the most “egregious acts” of improper tableside etiquette at home in the US, ranging from people licking their knives or stirring something like iced tea with a fork or knife because a spoon wasn’t handy. As with all rules of etiquette, Hanson says “knowledge is power.” “You can choose when to use it and when not to use it, or how formal or informal you want to sort of turn the dial depending on the context of your environment,” he says. And while many people in Britain, the US and Europe know how to dine casually, “there are still occasions, and there always will be occasions when, actually, you do need to do this end of the dial,” Hanson says, referring to dining more formally. Rest assured that encountering “minefields” when dining outside of your own culture is normal, says Hugo Strachwitz, a director at , an authority on British and international etiquette protocol. But he says any confusion is secondary to the importance of being a good guest in someone’s home or at their table. “Be kind, courteous, accepting of the dominant culture or whatever rules prevail. And if you encounter something you haven’t encountered before, or you’re not familiar or comfortable with, you might inquire, politely, ‘Gosh, I’ve never seen that before. How does that work?’” he suggests. It’s a host’s responsibility to put guests at ease in their company, Strachwitz says. “Be unapologetically yourself. So that can mean dining in your own style. So for an American dining in a non-American environment, the onus is on the host not to draw attention to the difference in a way that would cause offense or cause the guest to be self-conscious,” Strachwitz says. How these dining differences came to be is not entirely clear. But that table forks arrived on the scene much later than knives and spoons. century, forks were commonly used at tables in Italy, according to an article in , and their use later spread throughout Europe. But it wasn’t until the mid-19th century that the use of tables forks was well-established in the United States. It’s safe to say that how people dined influenced how they used their silverware, says Strachwitz. In the period before the early 19th century Napoleonic Wars, he says, the typical way of dining in Europe was service à la Française, or banquet-style, with all the dishes set on the table at once. By the beginning of the 19th century, however, service à la Russe, with course-by-course platings that required different cutlery for different dishes, was introduced to France from Russia. By midway through the 19th century, it had truly taken off, spreading to Britain, too. Where and when exactly the manners of wielding silverware drifted apart,  however, is harder to pinpoint. A food scholar that Americans took the cut-and-switch method from the French, who ultimately abandoned it. , associate professor of history at Michigan State University in East Lansing, worked as a historical consultant for season one of HBO’s “The Gilded Age” (CNN and HBO share the same parent company). When she set about researching how Americans held their silverware in the United States in the 1880s, when the show is set, she wondered whether it was in keeping with the British style or not. “It’s not like there was some definitive authority,” Veit says. What was clear, however, is that by the mid to late-19th century, Americans were “very insecure about their manners.” “They were really trying to establish what it meant to be elite, what it meant to be fancy, what it meant to be educated and refined. And so they were trying to establish an American set of manners,” she says. And people disagreed. “They didn’t always know what that meant, wondering if they should follow British etiquette or what the French do. And some people said, ‘To heck with Europe. We should just establish our own way of doing things culturally,’” Veit says. That might provide some solace for Americans who find themselves befuddled at a European table. “I think as long as people are eating nicely, we don’t hear any noise, you can keep the food on your plate and it doesn’t roll off onto the table and down your shirt,” Hanson says, it should suffice, adding that there are bigger things in life to worry about. The most important thing Hanson tells his students to remember is to hold their cutlery properly and to only begin eating when everyone is seated and has their food in front of them. Strachwitz puts it more simply still: “The essence of good etiquette, wherever you are, is care and consideration of others.” On that note, be nice and dig in. Terry Ward is a Florida-based travel writer and freelance journalist in Tampa who has lived in France, Australia and New Zealand and has invented her own hybrid method of dining at international tables."
    }, 
    {
        "title": "The ancient Roman city 10 times the size of Disneyland", 
        "content": "This CNN Travel series may have adjacent ads by the country it highlights. CNN retains full editorial control over subject matter, reporting and frequency of the articles and videos, The security lines at the entrance move with airport-like efficiency. Beyond them, the concrete of the 21st century falls away, replaced by creamy pillars and marble paving stretching into the distance, with green hills beyond. It feels like stepping back 2,000 years in time. In a country overflowing with archaeological treasures, the ancient city of Ephesus, in western Turkey’s İzmir Province, remains the crown jewel. Around 2.5 million people visited the remains of this Greco-Roman port city in 2025. Founded in the 10th century BCE the 1,600-acre UNESCO World Heritage site is around 10 times the size of Disneyland — packed with so many historical marvels it’s almost overwhelming. And it’s always been popular. “In the summer season, 70,000 ships were coming to Ephesus,” says tour guide Fatma Günaltay, leading visitors downhill along the sacred road that once connected the city to the 6th-century BCE Temple of Artemis, one of the Seven Wonders of the Ancient World. “This city was very wealthy.” Built in the estuary of what was once the River Kaystros, near the Aegean coast, Ephesus thrived as a trading hub connecting east and west. Leaders including Alexander the Great and Antony and Cleopatra left their mark here. The ruins explored today largely date from the city’s time as a busy Roman metropolis and remain among the best-preserved examples from that era. Curetes Street, one of the city’s three main thoroughfares and its streets are still paved with marble that can become slippery when it rains. Statues of prominent citizens line the route, many missing heads or limbs, while religious and civic buildings once painted in bright colors now appear butter-yellow. Günaltay explains that silk and incense shops once lined the street, and flowering trees shaded sumptuously dressed pedestrians from the blazing sun. Oval holes in the walls once held lamps to light the street after dark. Summertime night tours have recently been introduced, which aim to help visitors imagine how the city once felt after sunset. The Temple of Hadrian, a modest-sized Corinthian-style structure facing Curetes Street, is among the most elegant buildings in Ephesus. Completed in 138 CE with a wooden roof, its ornate eight-meter-tall arches still stand nearly 2,000 years later. The inner arch features a relief of Medusa, the snake-headed female figure in Greek or Roman mythology, used here to ward off evil spirits. At the bottom of the hill stands the city’s star attraction and most photographed landmark: the Library of Celsus. While you should never judge a book by its cover, only the facade of this 56-foot-tall Roman masterpiece survives. Blue squares of sky cut through the empty windows, while tapered marble columns create an optical illusion that makes the two-story structure even grander. More than 12,000 scrolls were once stored inside this second-century center of learning before a fire destroyed them in 262 CE. The building was also a monumental tomb, constructed by Consul Gaius Julius Aquila in honor of his father, Gaius Julius Celus Polemeanus, who is buried here. The less cerebral side of life is visible just across the street. The remains of a brothel sit opposite the library, and a nearby carving on a paving stone on Curetes Street is believed to be one of the world’s earliest advertisements. Featuring the outline of a foot, a money purse, and a woman, it suggests that visitors with adult-sized feet and sufficient funds could purchase the services offered there — an early version of the “you must be this tall to ride” signs at theme parks. Built around the 1st century CE, the brothel includes a ground-floor reception area and bathing pool, with an upper story for entertaining clients. A statue of Priapus, the Greek and Roman fertility god traditionally depicted with an outsize phallus, was found during excavation work here and is now on display in the Ephesus Museum in nearby Selçuk. Romans are renowned for their engineering skills, even when it came to handling sewage. At the city’s public latrines, 36 holes upon which people took their comfort breaks line the walls above a drainage system. It’s believed those using them cleaned themselves afterward using a xylospongium —  a sponge on a stick, dipped in vinegar. The latrines formed part of the Scholastica Baths, the city’s largest bathing complex, capable of accommodating up to 1,000 people, and an important social center. “The guys are using the Roman baths as a cafeteria,” says Günaltay. “They are meeting in Roman Baths for talking, for gossip, sometimes for discussing the gladiator games and elections of the Roman Empire, important issues.” Visitors can explore the nearby Terrace Houses — seven well-preserved Roman aristocratic homes — for an extra 15 euros, on top of the 40-euro entrance fee to the archaeological site. Inside are private baths which were supplied with hot and cold water through clay pipes, along with painted frescoes, colorful mosaics and handwritten wall graffiti. “The Prytaneion is the second-most important building of Ephesus, after the Artemis temple,” says Günaltay, pointing to the arched columns that remain. Priestesses once kept a sacred flame burning there day and night, believed to represent the life force of the city. “If the holy fire is alive,” the city is alive, she says, adding that an extinguished flame would signal that “the ending of the Roman Empire is coming. So the people are very scared of this reality.” Two statues of Artemis were discovered here, depicting the Greek goddess of hunting and abundance with fertility symbols around her torso —  interpreted variously as breasts or testicles. They are now on display at the Ephesus Museum. The Temple of Artemis, whose origins date back as early as the 7th century BCE, was one of the largest Greek temples ever built. Arsinoe IV, the younger sister of Cleopatra, was executed on the temple’s steps in 41 CE by order of Mark Antony and Cleopatra. The temple, more than 330 feet long and 150 feet wide (roughly 100 meters by 46 meters), was burnt down in 356 by an arsonist named Herostratus. He was executed for the deed and the case is considered one of the earliest recorded acts of terrorism. Today, only one reconstructed pillar remains at the original temple site, located outside of the main archaeological park. Ephesus later became an important religious center in early Christianity. From 52 to 55 CE, the apostle Saint Paul spent three years here preaching the Gospel and is said to have brought Mary, the mother of Jesus, here to spend her final days. The House of the Virgin Mary is a popular site of Christian pilgrimage on the slopes of Mount Brianssos, about three miles from the archaeological site. One of the city’s star attractions is the huge 25,000-seat Great Theater, used for theatrical performances, public assemblies, religious ceremonies and, in the Roman era, gladiatorial battles. “Your seats are separated according to your occupation,” says Günaltay, explaining the strict social hierarchy that was in place, with people divided by social class, status and gender. The theater appears in the Bible in “Acts of the Apostles” as the site of a sparked by a silversmith named Demetrius, angered by Saint Paul’s preaching against the Artemis statues from which he made his trade. Harbour Street once a bustling colonnaded road leading to the city’s now-dry port, where traders once sold luxury imported goods. Over centuries, silt gradually pushed the shoreline further away, contributing to Ephesus’ abandonment by the time of the Ottoman era in the 15th century. Looking at the arid landscape today, with the sea roughly four miles away, it’s hard to picture the port as it once was, but this could be set to change. Günaltay says there are government plans to refill the canal and reconnect the harbor to the sea. “The seawater will come here, just like in ancient times.” The , first announced in 2017, will the construction of a new canal and marina for excursion boats. No timeline for completion has been announced. If realized, the project could allow visitors to once again arrive by sea at Ephesus, for the first time in more than two millennia."
    }, 
    {
        "title": "‘Off-putting’ and ‘confronting’: Bikinis banned on Sydney bus after modesty complaints", 
        "content": "A Sydney council has banned beachgoers from boarding a community bus while shirtless or wearing bikinis, reigniting a decades-old debate over public decency in “Please dress appropriately. Clothing must be worn over swimwear,” reads a sign for the Hop, Skip and Jump bus, which is funded by Northern Beaches Council and drives through the northern Sydney suburbs of Manly, Fairlight and Balgowlah. The sign was shown in a by CNN affiliate 7News Sydney on Friday. Bus is the main form of public transportation in the coastal region, the council’s Denying passengers a ride due to their clothing, or lack of it, will be down to the driver’s discretion, according to 7News. The change follows complaints from passengers, according to CNN affiliate , with many older commuters in support of the restriction. “We’re a bit old-fashioned. We’d probably like people to dress properly, especially if you’re on public transport,” one woman told 7News. Another woman described passengers wearing swimwear as “confronting,” adding that the bus is “small” and “very contained.” “I think it’s a little off-putting sometimes when you see people get on with virtually no clothes on,” one man said. However, “the problem becomes where you draw the line,” a younger woman said, adding that “a lot of people will wear activewear on buses.” The council has not yet added the new rule to its for the bus service on its website. The code already instructs passengers not to eat, drink or smoke on the bus, or board with large objects such as surfboards when the bus is full. CNN had reached out to the council for further comment. Australia has a long history of controversy over beachwear. In the early 1960s, decades of tensions between female beachgoers and the local authority in the eastern Sydney suburb of Waverley rose to the point of being dubbed “the bikini war” by local media, according to local council archives. Similar “wars” raged elsewhere in Sydney, 7News reported. It followed the arrests of more than 50 women on Bondi Beach during a long weekend in October 1961, after a 1935 ordinance required bathing suits to meet strict measurements, with beach inspectors enforcing the rule. While the ordinance was abandoned later in 1961 in favor of a simpler requirement for “proper and adequate” swimsuits, debate over appropriate beachwear continues. In 2024, a call for a ban on wearing G-string bikinis on the streets of Australia’s eastern Gold Coast sparked protests and nationwide debate."
    }, 
    {
        "title": "You’re trapped in a blizzard. Do you know what to do next to survive?", 
        "content": "Warm thoughts of young romance  – not the cold, harsh possibilities of a Midwestern road trip in winter – were on Dawn O’Hair’s mind as she left Chicago for Indianapolis to see her boyfriend. Her weekend visit, back in the winter of 1997-98, did not go well. After a spat with her beau, O’Hair got back into her car very early on a Monday morning to return to Chicago and her job. She should have stayed put. The 23-year-old was driving up Interstate 65 straight into a blizzard. “I ended up in whiteout conditions. I had trouble maintaining control in my 1995 Chevrolet Cavalier,” she said. “The wind was crazy. The snow was blowing sideways. It was super hard to see. It was horrible.” “I got nervous and decided to pull over [but] my car got stuck,” she said. “I didn’t know what to do. I got out and tried to figure out a way to get traction, but without luck.” And there she was – in a real mess. She hadn’t checked the forecasts. She had nothing particularly warm to wear. No blankets. No winter kit. Just her Chevy and time to ponder how things went so wrong so fast. O’Hair’s story is a far too common one of people caught off guard by a blizzard or some other onslaught of wintry weather. Blizzards can happen over a surprisingly wide range of the calendar – just ask these runners caught in a Of course, we expect rough winter weather in January. And on the first days of January 2024, with possibly dangerous blizzards in portions of it threatened much of the central and eastern United States. Unless you live in a year-round warm climate and plan to stay there, it’s important to know how winter storms behave, how to avoid and prepare for them, and heaven forbid, what to do in the worst-case scenario. First, not every ol’ winter storm is technically a blizzard. must have large amounts of falling snow or blowing snow, winds greater than 35 mph (56 kph) and visibility of less than a quarter mile (0.4 km) for at least three hours. A ground blizzard has no falling snow; instead, it blows around snow that had fallen before the blizzard kicked up. Any weather system with below freezing temperatures along with snow and ice can be a safety hazard. Blizzards, however, are one of the most dangerous types of winter storms. They can lead not only “to perilous driving conditions under low visibility and snow-covered roads, but can also lead to disorientation for anyone walking or driving, resulting in the person not knowing where they are or where they are going,” said Michael Muccilli, meteorologist with the National Oceanic and Atmospheric Administration’s NWS, in an email interview with “Oftentimes the strong winds and cold temperatures associated with blizzards can produce dangerous wind chills, which can lead to hypothermia and frostbite, especially if stuck outside for extended periods,” he said. Awareness and avoidance are your best weapons against blizzards and other bad winter weather. If you’re taking a road trip, “begin checking weather conditions about a week in advance of your trip and make sure to check again each day as the weather forecasts become more fine-tuned,” Muccilli said. “Have alternate plans for your travel, and if weather conditions are looking increasingly unfavorable, use those alternate plans or delay travel.” Muccilli said you should check conditions along your entire route, not just the starting and ending points, especially if you’re crossing through high mountain passes. If you’re going hiking or camping, checking forecasts is a must, said Beth Pratt, the California regional executive director for the National Wildlife Federation. Don’t skip a forecast check just because it’s fall, spring or even summer in some locations. They can lull you into a false sense of security because your guard might not be up as much as the dead of winter, Pratt said. She resides on the border of Yosemite National Park in the Sierra Nevadas, where you might start out on a hike on a late fall day while it’s still warm but suddenly encounter a dangerous wintry blast. you can check online to see what might be ahead. A little geographical and climate knowledge helps, too. “Blizzards are most common in the upper Midwest and Great Plains in the United States, but can occur in most areas of the country except the Gulf Coast and coastal California,” Muccilli said. , you’ll encounter them most often in Russia, central and northeastern Asia (including China), northern Europe, Canada and Antarctica. Just as it’s important to know blizzards aren’t a winter-only event, you must also realize they might happen in places you usually associate with hot weather. that killed thousands. At least four people in a rare blizzard. And parts of inland Alabama, Georgia and the Carolinas were slammed by blizzard conditions in the Having the right clothing is crucial if you’re going to a place where blizzards and other cold-weather storms might happen. says to “wear layered clothing, mittens or gloves, and a hat. Outer garments should be tightly woven and water repellent. Mittens or gloves and a hat will prevent the loss of body heat.” Remember O’Hair’s predicament. It’s important to bring along winter clothing even if it’s not that cold or threatening as you depart or you just plan on staying in your car. Layering is important, says the : “Dress in several layers of loose-fitting, lightweight clothing instead of a single heavy layer.” points out another reason to layer: You might need to take a layer or two off to avoid overheating, perspiring too much and then subsequently getting chilled. The website advises mittens over gloves. If you’re outside, the Red Cross also says to cover your mouth to protect your lungs from severely cold air. Don’t gulp in deep breaths of frigid air and talk as little as possible. before you head out. Muccilli said the kit should include: – Road salt and a shovel – A flashlight and road flares – A cell phone charger You should also fill your wiper fluid and check your tire pressure, tire tread and oil before leaving. Make sure What if you run into bad winter weather? “If the weather becomes too severe to continue driving, pull over, and if possible move your car to the closest gas station or hotel and ride out the storm,” Muccilli said. Don’t drive around barriers onto closed-off roads. What if your car is stuck in the snow? If conditions are safe enough, you can “attempt to shovel out your tires and throw down sand, rock salt, dirt, cardboard or kitty litter to give your vehicle more traction. If this does not work, call for roadside assistance or emergency services.” Otherwise, Muccilli said stay inside your vehicle except long enough to set road flares or put out a colorful cloth to make yourself visible. Contact emergency services with as much information about your situation as you can. not to leave your vehicle to walk for help during a blizzard. You could get disoriented. You should run the motor about 10 minutes each hour for heat, it says, but open the window a crack for fresh air. Clear snow away from the exhaust pipe if possible. Whether you are camping, hiking, backcountry skiing or doing other similar types of outside activities, carry the correct safety gear. Muccilli said this might include but is not limited to: – Enough water and food – A headlamp and a lighter – A map or other navigation tools – A transceiver to transmit your location in case you are trapped in an avalanche – A probe to pinpoint your exact location – A shovel to dig out – An airbag pack to increase your chances of staying near the surface of an avalanche. “Never hike or ski alone and make sure someone knows where you are going,” he said. People enjoying a day (or night) at a ski resort should check the local weather forecast just before heading out to the slopes, said Rick Shandler, national program director of the Safety Team at National Ski Patrol. He cautions skiers to not let their investment in a pricey lift ticket cloud their judgment. “People want to get the most value out of their lift tickets and may stay out past what common sense dictates” when blizzards, dense fog or other bad weather is approaching, he said. He suggested taking the following with you on the slopes: – A fully charged cell phone in an inner pocket. The cold can quickly sap your battery if it’s in an outer pocket. Get the number of the ski patrol at the resort before you head out and add it to your phone. – A whistle. The sound carries farther than yelling if you’re down and a ski patrol needs to find you. – A space blanket. Made of Mylar, they are inexpensive, easy to tote and can keep you warmer and easier to spot if you become stranded. Pratt said the closest she ever came to dying in a blizzard was in her college years back in 1990. It was in June of all months, while she was hiking with two friends on Mount Washington in New Hampshire. The mountain is notorious for its dangerous, fickle weather, even in summer. “The storm came up very fast. We were in college, and young and broke and didn’t have great gear either.” With the wind whipping and whiteout conditions of a blizzard, “the only thing that saved us is we found the tracks to the Mount Washington Cog Railway. So we had breadcrumbs to follow. If we had not been near those train tracks, we would have had to hunker down. The wind was so fierce it had shredded our rain gear.” What if you end up in a worst-case scenario like Pratt? She said there are “two things to focus on: Stay warm and stay still.” “It’s ill-advised to walk yourself out of a blizzard. Navigation is tough, and you burn more energy when you are cold, so conserve it. Find shelter. If there is none to find, build a snow cave if there’s enough snow. Wait it out.” for dire situations when it’s just you vs. the raw elements: Also, attempt to stay dry and cover all of your body. See if you can make a lean-to, windbreak or snow cave for protection from the wind.  Try to set a fire. If there are rocks nearby, put those around the fire to retain heat. even low-hanging tree branches could provide some protection. You should melt snow for drinking water. The NWS and Global Rescue warn that eating unmelted snow will lower your body temperature. From time to time, move your arms, legs, fingers and toes to keep your blood pumping and stay warm. But don’t overdo it. “The strain from the cold and the hard labor may cause a heart attack. Sweating could lead to a chill and hypothermia,” the NWS website says. Fortunately for Dawn O’Hair, what she lacked in winter preparation she made up for in a good decision, good luck and good connections with people in northern Indiana. She wisely stayed with her car instead of walking off into the blizzard for help. Less than an hour later, a young woman pulled up and offered her a ride to a gas station. That woman had a boyfriend who was a police officer, and he took her to an Indiana state police post. From the post, she was able to reach a cousin to give her refuge and was transported to that cousin’s house via snowmobile. It ended up taking her several days and more on-the-road misadventures to make the roughly 170-mile drive back home. So what did Dawn O’Hair Czanik – yes, she ended up marrying the boyfriend with whom she had the spat – learn from the experience? “I would have paid more attention to the weather forecast and planned ahead better! I probably would have left the day before, but young love is kinda stupid, ya know?” This article was first published in October 2021 and is updated periodically for major winter weather events."
    }
]

    podcast_result = generate_podcast_data_via_glm(news_items)

    if podcast_result:
        raw_script = podcast_result.get("script", "")
        vocabulary = podcast_result.get("vocabulary", [])

        fixed_script = post_process_script(raw_script)
        final_script = fixed_script.replace("Brian:", "Host_A:").replace("Jessica:", "Host_B:")
        podcast_result["script"] = final_script

        with open("podcast_data.json", "w", encoding="utf-8") as f:
            json.dump(podcast_result, f, ensure_ascii=False, indent=2)

        print("\n" + "="*20 + " FINAL CLEANED SCRIPT PREVIEW " + "="*20)
        print(final_script)
        print("="*60 + "\n")

        # Ask for confirmation before generating audio
        user_input = input("\nDo you want to generate audio from this script? (yes/no): ").strip().lower()
        if user_input == "yes":
            generate_audio_via_inworld(final_script)
        else:
            print("Audio generation skipped.")