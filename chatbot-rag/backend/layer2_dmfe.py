"""
LAYER 2 - Dynamic Metadata Filter Engine
"""

import json
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are a metadata filter extractor.
When given a query, extract implied metadata constraints.
Return ONLY a valid JSON object - no explanation, no markdown.

Available fields:
{
  "department": "HR" | "IT" | "Finance" | "Operations",
  "document_type": "policy" | "procedure" | "handbook",
  "topic_tags": ["tag1", "tag2"]
}

Rules:
- Only include fields you are confident about
- If nothing can be inferred, return: {}
- Return ONLY JSON
-IMPORTANT: For company-wide policies (leave, expense, travel, 
  maternity, salary, benefits), do NOT set department — these belong 
  to HR, not to the department the user mentions.
  Example: 'leave policy for finance team' → {"document_type": "policy"}
  NOT → {"department": "Finance", "document_type": "policy"}
- Only set department if the question is clearly about something 
  created BY or exclusively FOR that department."""


def extract_filters(query):
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            max_tokens=150,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ]
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        filters = json.loads(raw)
        return filters
    except Exception as e:
        print(f"[DMFE] Error: {e}")
        return {}
