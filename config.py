import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
BOT_PREFIX = os.getenv('BOT_PREFIX', '!')

if not DISCORD_TOKEN:
    print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
    print("Please set up your .env file with your Discord bot token.")
    exit(1)

if not GROQ_API_KEY:
    print("❌ ERROR: GROQ_API_KEY not found in environment variables!")
    print("Please set up your .env file with your Groq API key.")
    exit(1)

STUDY_CHANNELS = {}
