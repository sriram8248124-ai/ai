"""
Welcome Message System with AI Image Generation
"""

import json
import os
from datetime import datetime

WELCOME_FILE = "welcome_settings.json"

def load_welcome_settings():
    """Load welcome settings"""
    if os.path.exists(WELCOME_FILE):
        with open(WELCOME_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_welcome_settings(settings):
    """Save welcome settings"""
    with open(WELCOME_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def add_welcome_message(guild_id, channel_id, message, image_url=None):
    """Add welcome message for guild"""
    settings = load_welcome_settings()
    if guild_id not in settings:
        settings[guild_id] = {}
    
    settings[guild_id]["channel_id"] = channel_id
    settings[guild_id]["message"] = message
    settings[guild_id]["image_url"] = image_url
    settings[guild_id]["created_at"] = datetime.now().isoformat()
    
    save_welcome_settings(settings)
    return True

def get_welcome_message(guild_id):
    """Get welcome message for guild"""
    settings = load_welcome_settings()
    return settings.get(guild_id, {})

def delete_welcome_message(guild_id):
    """Delete welcome message for guild"""
    settings = load_welcome_settings()
    if guild_id in settings:
        del settings[guild_id]
        save_welcome_settings(settings)
        return True
    return False

WELCOME_TEMPLATES = {
    "default": "👋 Welcome to our server! {user_mention}\n\nWe're excited to have you here! Please read the rules and have fun!",
    "creative": "🎉 **Welcome Aboard!** {user_mention}\n\nJoin us on this amazing journey! 🚀",
    "study": "📚 Welcome to our Study Server! {user_mention}\n\n🎯 Focus | 📖 Learn | 🏆 Grow",
    "coding": "💻 Welcome to our Coding Community! {user_mention}\n\n🔧 Code | 🚀 Build | 💡 Innovate",
    "gaming": "🎮 Welcome to the Gaming Hub! {user_mention}\n\nLet's play and have fun together! 🎯",
}

def get_template(template_name):
    """Get welcome template"""
    return WELCOME_TEMPLATES.get(template_name, WELCOME_TEMPLATES["default"])
