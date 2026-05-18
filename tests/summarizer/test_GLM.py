import json
import os
from zai import ZhipuAiClient
from dotenv import load_dotenv

# 初始化客户端
load_dotenv()
api_key = os.getenv("ZHIPU_AI_API_KEY", "")
client = ZhipuAiClient(api_key=api_key)

raw_news = {
    "title": "Race for AI is making Hindenburg-style disaster ‘a real risk’, says leading expert",
    "content": "The race to get artificial intelligence to market has raised the risk of a Hindenburg-style disaster that shatters global confidence in the technology, a leading researcher has warned. Michael Wooldridge, a professor of AI at Oxford University, said the danger arose from the immense commercial pressures that technology firms were under to release new AI tools, with companies desperate to win customers before the products’ capabilities and potential flaws are fully understood. The surge in AI chatbots with guardrails that are showed how commercial incentives were prioritised over more cautious development and safety testing, he said. “It’s the classic technology scenario,” he said. “You’ve got a technology that’s very, very promising, but not as rigorously tested as you would like it to be, and the commercial pressure behind it is unbearable.” Wooldridge, who will deliver the Royal Society’s Michael Faraday prize lecture on Wednesday evening, titled “ ”, said a Hindenburg moment was “very plausible” as companies rushed to deploy more advanced AI tools. The Hindenburg, a 245-metre airship that made round trips across the Atlantic, was preparing to land in New Jersey in 1937 when it burst into flames, killing 36 crew, passengers and ground staff. The inferno was caused by a spark that ignited the 200,000 cubic metres of hydrogen that kept the airship aloft. “The Hindenburg disaster destroyed global interest in airships; it was a dead technology from that point on, and a similar moment is a real risk for AI,” Wooldridge said. Because AI is embedded in so many systems, a major incident could strike almost any sector. The scenarios Wooldridge imagines include a deadly software update for self-driving cars, an AI-powered hack that grounds global airlines, or a Barings bank-style collapse of a major company, triggered by AI doing something stupid. “These are very, very plausible scenarios,” he said. “There are all sorts of ways AI could very publicly go wrong.” Despite the concerns, Wooldridge said he did not intend to attack modern AI. His starting point is the gap between what researchers expected and what has emerged. Many experts anticipated AI that computed solutions to problems and provided answers that were sound and complete. “Contemporary AI is neither sound nor complete: it’s very, very approximate,” he said. This arises because large language models, which underpin today’s AI chatbots, rattle out answers by predicting the next word, or part of a word, based on probability distributions learned in training. It leads to AIs with : incredibly effective at some tasks, yet terrible at others. The problem, Wooldridge said, was that AI chatbots failed in unpredictable ways and had no idea when they were wrong, but were designed to provide confident answers regardless. When delivered in human-like and sycophantic responses, the answers could easily mislead people, he added. The risk is that people start treating AIs as if they were human. In a by the Center for Democracy and Technology, nearly a third of students reported that they or a friend had had a romantic relationship with an AI. “Companies want to present AIs in a very human-like way, but I think that is a very dangerous path to take,” Wooldridge said. “We need to understand that these are just glorified spreadsheets, they are tools and nothing more than that.” Wooldridge sees positives in the kind of AI depicted in the early years of Star Trek. In one 1968 episode, The Day of the Dove, Mr Spock quizzes the Enterprise’s computer only to be told in a distinctly non-human voice that it has . “That’s not what we get. We get an overconfident AI that says: yes, here’s the answer,” he said. “Maybe we need AIs to talk to us in the voice of the Star Trek computer. You would never believe it was a human being.” Prof Michael Wooldridge says scenario such as deadly self-driving car update or AI hack could destroy global interest"
  }

def process_news_refined(news_data):
    # Prompt updated to remove vocabulary level tagging
    system_prompt = """
    You are a professional News Data Architect. Your goal is to process complex news for English learners (A2-B1 level).
    
    ## INSTRUCTIONS:
    1. "simple_title": Create an easy title for beginners (max 8 words).
    2. "simple_content": This is NOT a summary. It is a COMPREHENSIVE REWRITE of the full article. 
       - Cover every major point and detail of the source content.
       - Use simple vocabulary (A2-B1) and clear sentence structures.
    3. "difficulty_score": 1-10.
    4. "tags": 3-5 keywords.
    5. "qa_suggestions": 3 engaging questions for a user to ask an AI about this news.
    6. "vocabulary": Extract EXACTLY 30 items. 
       - STRICT COUNT: You MUST provide exactly 30 vocabulary items. No more, no less.
       - VERBATIM RULE: Every word MUST be physically present in the "INPUT DATA" content. 
       - "example_sentence": Write a clear example sentence describing the events of THIS news article.
    7. "background_info": Descriptions MUST be in English.
    8. "en_summary": Concise summary (60-80 words).

    ## JSON SCHEMA:
    {
      "simple_title": "string",
      "difficulty_score": number,
      "tags": ["string"],
      "en_summary": "string",
      "simple_content": "string",
      "qa_suggestions": ["string"],
      "vocabulary": [{"word": "string", "phonetic": "string", "translation": "string", "explanation": "string", "example_sentence": "string"}],
      "background_info": [{"entity_name": "string", "entity_type": "string", "description": "string", "is_web_searched": true}],
      "viewpoint_analysis": [{"entity_name": "string", "viewpoint": "string", "sentiment": "Positive/Negative/Neutral"}],
      "entity_relation": [{"subject_entity": "string", "relation": "string", "object_entity": "string"}]
    }
    """

    user_prompt = f"""
    ### INPUT DATA ###
    Title: {news_data.get('title')}
    Content: {news_data.get('content')}

    ### CRITICAL REQUIREMENT ###
    1. Vocabulary count MUST be EXACTLY 30.
    2. All words must be from the Content provided.
    """

    try:
        response = client.chat.completions.create(
            model="glm-4-air-250414", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Use temperature 0.1 for deterministic count enforcement
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        return json.loads(raw_content)
    except Exception as e:
        print(f"Error during API call: {e}")
        return None

if __name__ == "__main__":
    if not api_key:
        print("Error: ZHIPU_AI_API_KEY not found in environment variables or .env file.")
    else:
        print("Calling AI to process news (extracting exactly 30 contextual items)...")
        result = process_news_refined(raw_news)
        
        if result:
            output_file = "ai_processed_result_v2.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            vocab_count = len(result.get('vocabulary', []))
            print(f"\nProcessing complete!")
            print(f"Title: {result.get('simple_title')}")
            print(f"Vocabulary count: {vocab_count}")
            
            if vocab_count != 30:
                print(f"Warning: Count mismatch! Expected 30, got {vocab_count}.")
                
            print(f"Results saved to {output_file}")