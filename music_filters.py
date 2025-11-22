"""
Audio Filters & Effects for Discord Music Bot
20+ Premium Audio Filters
"""

AUDIO_FILTERS = {
    # Equalizer Presets
    "bass_boost": {"band": [0.2, 0.15, 0.1, 0.05, 0, 0, 0], "name": "🔊 Bass Boost"},
    "treble_boost": {"band": [0, 0, 0, 0, 0, 0.15, 0.2], "name": "✨ Treble Boost"},
    "vocal": {"band": [-0.1, 0.05, 0.1, 0.15, 0.1, 0.05, -0.1], "name": "🎤 Vocal Enhancer"},
    "soft": {"band": [-0.1, -0.05, 0, 0.05, 0.1, 0.05, -0.1], "name": "☁️ Soft"},
    "bright": {"band": [0.1, 0.05, 0, 0, 0, 0.1, 0.15], "name": "💫 Bright"},
    
    # Studio Effects
    "reverb": {"band": [0.05, 0.05, 0.05, 0.1, 0.1, 0.1, 0.05], "name": "🏰 Reverb"},
    "echo": {"band": [0.15, 0.1, 0.05, 0, -0.05, -0.1, -0.15], "name": "🔊 Echo"},
    "chorus": {"band": [0, 0.1, 0.15, 0.1, 0, -0.1, -0.15], "name": "🎶 Chorus"},
    "delay": {"band": [0.1, 0.05, 0, 0, 0, -0.05, -0.1], "name": "⏱️ Delay"},
    
    # Genre Presets
    "pop": {"band": [0.1, 0, 0, 0.05, 0.1, 0.15, 0.2], "name": "🎵 Pop"},
    "rock": {"band": [0.2, 0.15, 0.1, 0, 0, 0.1, 0.05], "name": "🎸 Rock"},
    "edm": {"band": [0.3, 0.2, 0.1, 0, 0.1, 0.2, 0.25], "name": "⚡ EDM"},
    "hiphop": {"band": [0.2, 0.1, 0.05, 0, -0.05, 0.05, 0.1], "name": "🎤 Hip-Hop"},
    "jazz": {"band": [-0.1, 0, 0.05, 0.1, 0.05, 0, -0.1], "name": "🎷 Jazz"},
    "metal": {"band": [0.25, 0.2, 0.15, -0.1, 0.1, 0.15, 0.2], "name": "🤘 Metal"},
    "lofi": {"band": [-0.1, -0.05, 0, 0.05, 0.05, 0, -0.15], "name": "😌 Lo-Fi"},
    "classical": {"band": [-0.15, -0.1, -0.05, 0.1, 0.15, 0.1, 0.05], "name": "🎻 Classical"},
    
    # Spatial Effects
    "surround": {"band": [0.1, 0.15, 0.1, 0.05, 0.1, 0.15, 0.2], "name": "🔊 Surround"},
    "stereo": {"band": [0.05, 0.1, 0.15, 0.1, 0.05, 0, -0.05], "name": "🎧 Stereo"},
    "mono": {"band": [0, 0, 0, 0, 0, 0, 0], "name": "○ Mono"},
    
    # Utility
    "flat": {"band": [0, 0, 0, 0, 0, 0, 0], "name": "➖ Flat (Off)"},
    "lossless": {"band": [0.02, 0.01, 0, 0, 0, 0.01, 0.02], "name": "💎 Lossless"},
    "highfidelity": {"band": [0.05, 0.02, 0, 0, 0, 0.02, 0.05], "name": "🎼 Hi-Fi"},
}

AUDIO_QUALITY = {
    "lossless": {"bitrate": 320, "quality": "🎼 Lossless (320kbps)", "format": "FLAC"},
    "hq": {"bitrate": 256, "quality": "💎 High Quality (256kbps)", "format": "MP3"},
    "normal": {"bitrate": 128, "quality": "📻 Normal (128kbps)", "format": "MP3"},
}

def get_filter_info(filter_name):
    """Get filter information"""
    return AUDIO_FILTERS.get(filter_name, AUDIO_FILTERS["flat"])

def list_all_filters():
    """List all available filters"""
    return list(AUDIO_FILTERS.keys())

def get_filter_display():
    """Get formatted filter list for display"""
    filters = []
    for name, data in AUDIO_FILTERS.items():
        filters.append(f"• {data['name']} - `{name}`")
    return "\n".join(filters)
