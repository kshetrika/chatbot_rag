import os
from dotenv import load_dotenv

load_dotenv()

# GROQ API CONFIGURATION
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
EMBED_MODEL = "all-MiniLM-L6-v2"

# RETRIEVAL THRESHOLDS
ARO_THRESHOLD = 0.70
ARO_MAX_RETRY = 3

# HALLUCINATION DETECTION
HDP_WARNING = 0.55
HDP_REFUSAL = 0.30

# SEARCH SETTINGS
DEFAULT_TOP_K = 5
COMPREHENSIVE_TOP_K = 10

if GROQ_API_KEY:
    print("Config loaded - Groq API key found")
else:
    print("ERROR - GROQ_API_KEY not found in .env file")
