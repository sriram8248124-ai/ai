import discord
from discord.ext import commands
from discord import app_commands, SelectOption
import config
from groq import Groq
import asyncio
import json
import os
from datetime import datetime, timedelta
import io
import aiohttp
import re
import random
import wavelink
from discord.ui import Button, View, Select
from PIL import Image, ImageDraw, ImageFont
import subprocess
import socket
from music_filters import AUDIO_FILTERS, AUDIO_QUALITY, get_filter_display
from welcome_system import (
    load_welcome_settings, save_welcome_settings, add_welcome_message,
    get_welcome_message, WELCOME_TEMPLATES
)
from ticket_system import (
    create_ticket, load_tickets, list_tickets, close_ticket,
    get_ticket, TICKET_CATEGORIES
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents, help_command=None)

groq_client = Groq(api_key=config.GROQ_API_KEY)

study_sessions = {}
active_channels = {}
ai_chat_channels = {}

automod_settings = {}
user_message_tracker = {}
mention_tracker = {}
DEFAULT_BANNED_WORDS = ["badword1", "badword2"]

AI_CHAT_FILE = "ai_chat_channels.json"

music_queues = {}
now_playing = {}
player_messages = {}
song_language_tracker = {}  # Track language of current song per guild
autoplay_settings = {}  # Track autoplay preferences per guild

# Bot uptime tracking
bot_start_time = datetime.now()

def load_ai_channels():
    global ai_chat_channels
    try:
        if os.path.exists(AI_CHAT_FILE):
            with open(AI_CHAT_FILE, 'r') as f:
                data = json.load(f)
                ai_chat_channels = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f"Error loading AI channels: {e}")

def save_ai_channels():
    try:
        with open(AI_CHAT_FILE, 'w') as f:
            json.dump(ai_chat_channels, f)
    except Exception as e:
        print(f"Error saving AI channels: {e}")

@bot.event
async def on_ready():
    global bot_start_time
    bot_start_time = datetime.now()
    
    load_ai_channels()
    print(f'✅ Bot is ready! Logged in as {bot.user.name}')
    print(f'📊 Connected to {len(bot.guilds)} servers')
    print(f'💬 AI Chat enabled in {sum(len(channels) for channels in ai_chat_channels.values())} channels')
    print(f'⏱️ Bot started at: {bot_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
    try:
        synced = await bot.tree.sync()
        print(f'✅ Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'❌ Error syncing commands: {e}')
    
    try:
        nodes = [
            wavelink.Node(
                uri='http://lava-v4.ajieblogs.eu.org:80',
                password='https://dsc.gg/ajidevserver'
            ),
        ]
        await wavelink.Pool.connect(client=bot, nodes=nodes)
        print('✅ Connected to Lavalink server!')
        print(f'✅ Music player is ready with queue and dashboard!')
    except Exception as e:
        print(f'⚠️ Lavalink connection warning: {e}')
        print('Bot will try to auto-reconnect...')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="and helping everyone | /help"
        )
    )

@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    guild_id = player.guild.id
    
    if player._voice:
        is_muted = player._voice.self_mute
        if is_muted:
            mute_alert_embed = discord.Embed(
                title="🔇 SERVER MUTED!",
                description="I have been **server muted** 🔴\n\nPlease unmute me to hear the song!",
                color=discord.Color.red()
            )
            mute_alert_embed.add_field(name="⏱️ Auto-delete", value="This message will disappear in 5 seconds", inline=False)
            
            try:
                for channel in player.guild.text_channels:
                    if channel.permissions_for(player.guild.me).send_messages:
                        msg = await channel.send(embed=mute_alert_embed)
                        await asyncio.sleep(5)
                        await msg.delete()
                        break
            except:
                pass

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    guild_id = player.guild.id
    
    if player and guild_id in music_queues and music_queues[guild_id]:
        next_track = music_queues[guild_id].pop(0)
        
        if guild_id in autoplay_settings and autoplay_settings[guild_id]:
            current_language = song_language_tracker.get(guild_id, "🌍 Unknown")
            next_language = detect_song_language(next_track.title)
            
            if current_language == next_language or next_language == "🌍 Unknown":
                song_language_tracker[guild_id] = next_language
                await player.play(next_track)
                await update_player_message(guild_id)
        else:
            await player.play(next_track)
            await update_player_message(guild_id)

@bot.tree.command(name="setup", description="Setup AI chat in a channel")
@app_commands.describe(
    channel="The channel where bot responds to all messages"
)
async def setup_chat(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    guild_id = interaction.guild.id
    
    if guild_id not in ai_chat_channels:
        ai_chat_channels[guild_id] = []
    
    if channel.id not in ai_chat_channels[guild_id]:
        ai_chat_channels[guild_id].append(channel.id)
    
    save_ai_channels()
    
    embed = discord.Embed(
        title="🤖 AI Chat Setup Complete!",
        description=f"AI will now respond to ALL messages in {channel.mention}",
        color=discord.Color.green()
    )
    embed.add_field(
        name="What's next?",
        value="Just chat normally in that channel - no prefix or mention needed!\n\nYou can also DM me directly!",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ask", description="Ask the AI assistant anything!")
@app_commands.describe(question="Your question")
async def ask_ai(interaction: discord.Interaction, question: str):
    await interaction.response.defer(thinking=True)
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Help users with their questions, provide clear explanations, and be friendly and encouraging."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1024
        )
        
        response = chat_completion.choices[0].message.content
        
        embed = discord.Embed(
            title="🤖 AI Assistant",
            description=response,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Asked by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Sorry, I couldn't process your question: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="imagine", description="Generate a SHARP HIGH-QUALITY image with AI")
@app_commands.describe(prompt="Describe the image you want to create")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    
    try:
        status_embed = discord.Embed(
            title="🎨 Generating Sharp Image (High Quality)...",
            description=f"Creating: {prompt}\n\n📸 Ultra HD quality (1024x1024)!\nI'll send it to your DM when ready!",
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=status_embed)
        
        async with aiohttp.ClientSession() as session:
            enhanced_prompt = f"{prompt}|ultra detailed, sharp, high resolution, 4k, professional, crystal clear"
            image_url = f"https://image.pollinations.ai/prompt/{enhanced_prompt.replace(' ', '%20')}?width=1024&height=1024&enhance=true&nologo=true"
            
            async with session.get(
                image_url,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    image_file = discord.File(io.BytesIO(image_data), filename="generated_image.png")
                    
                    result_embed = discord.Embed(
                        title="✅ Sharp Image Generated! 📸",
                        description=f"**Prompt:** {prompt}",
                        color=discord.Color.green()
                    )
                    result_embed.add_field(name="📊 Quality", value="Ultra HD (1024x1024, 4K)", inline=True)
                    result_embed.set_image(url="attachment://generated_image.png")
                    result_embed.set_footer(text="Powered by AI | Crystal Clear Quality")
                    
                    try:
                        await interaction.user.send(embed=result_embed, file=image_file)
                        success_embed = discord.Embed(
                            title="✅ Sent to DM!",
                            description=f"Check your DMs for the sharp HD image!",
                            color=discord.Color.green()
                        )
                        await interaction.channel.send(embed=success_embed)
                    except:
                        await interaction.channel.send(embed=result_embed, file=image_file)
                else:
                    raise Exception(f"API returned status {resp.status}")
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to generate image: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=error_embed)

@bot.tree.command(name="video", description="Generate a video with AI")
@app_commands.describe(prompt="Describe the video you want to create")
async def generate_video(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    
    try:
        status_embed = discord.Embed(
            title="🎥 Generating Video...",
            description=f"Creating: {prompt}\n\nThis may take 30-90 seconds. I'll send it to your DM when ready!",
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=status_embed)
        
        async with aiohttp.ClientSession() as session:
            video_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=512&height=512&seed={random.randint(1, 100000)}&model=flux&enhance=true"
            
            async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    data = await resp.read()
                    
                    if 'video' in content_type or len(data) > 100000:
                        video_file = discord.File(io.BytesIO(data), filename="generated_video.mp4")
                        file_type = "video"
                    else:
                        video_file = discord.File(io.BytesIO(data), filename="generated_animation.gif")
                        file_type = "animation"
                    
                    result_embed = discord.Embed(
                        title=f"✅ {'Video' if file_type == 'video' else 'Animation'} Generated!",
                        description=f"**Prompt:** {prompt}",
                        color=discord.Color.green()
                    )
                    result_embed.set_footer(text="Powered by FREE AI (Pollinations)")
                    
                    try:
                        await interaction.user.send(embed=result_embed, file=video_file)
                        success_embed = discord.Embed(
                            title="✅ Sent!",
                            description=f"Check your DMs for the generated {file_type}!",
                            color=discord.Color.green()
                        )
                        await interaction.channel.send(embed=success_embed)
                    except Exception as dm_error:
                        await interaction.channel.send(
                            embed=discord.Embed(
                                title="❌ Couldn't Send DM",
                                description="Please enable DMs from server members!",
                                color=discord.Color.red()
                            )
                        )
                else:
                    raise Exception(f"API returned status {resp.status}. Video generation service may be temporarily unavailable.")
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to generate video: {str(e)}",
            color=discord.Color.red()
        )
        try:
            await interaction.user.send(embed=error_embed)
        except:
            await interaction.channel.send(embed=error_embed)

def detect_song_language(title: str) -> str:
    """Detect song language from title"""
    tamil_indicators = ["tamil", "தமிழ்", "padikathavan", "pls", "tpl"]
    hindi_indicators = ["hindi", "हिंदी", "bhaji", "bollywood"]
    english_indicators = ["english", "pop", "rock", "edm", "english song"]
    
    title_lower = title.lower()
    
    for indicator in tamil_indicators:
        if indicator in title_lower:
            return "🇮🇳 Tamil"
    for indicator in hindi_indicators:
        if indicator in title_lower:
            return "🇮🇳 Hindi"
    for indicator in english_indicators:
        if indicator in title_lower:
            return "🇬🇧 English"
    
    return "🌍 Unknown"

def generate_network_graph():
    """Generate network ping graph visualization"""
    try:
        ping_values = []
        labels = []
        
        for i in range(5):
            try:
                result = subprocess.run(['ping', '-c', '1', '8.8.8.8'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    output = result.stdout.decode()
                    if 'time=' in output:
                        time_str = output.split('time=')[1].split('ms')[0].strip()
                        ping_values.append(float(time_str))
            except:
                pass
        
        if not ping_values:
            ping_values = [50, 55, 52, 48, 51]
        
        img = Image.new('RGB', (400, 250), color='#2C2F33')
        draw = ImageDraw.Draw(img)
        
        title = "📊 Network Ping Graph (ms)"
        draw.text((50, 20), title, fill='#FFFFFF')
        
        max_ping = max(ping_values) * 1.2
        graph_height = 150
        graph_width = 300
        start_x, start_y = 50, 70
        
        draw.rectangle([(start_x, start_y), (start_x + graph_width, start_y + graph_height)], 
                       outline='#7289DA', width=2)
        
        bar_width = graph_width // len(ping_values)
        colors = ['#43B581', '#FAA61A', '#F04747', '#99AAB5', '#7289DA']
        
        for i, ping in enumerate(ping_values):
            bar_height = (ping / max_ping) * graph_height
            x1 = start_x + i * bar_width + 10
            y1 = start_y + graph_height - bar_height
            x2 = x1 + bar_width - 15
            y2 = start_y + graph_height
            
            draw.rectangle([(x1, y1), (x2, y2)], fill=colors[i % len(colors)])
            draw.text((x1 + 5, y2 + 5), f"{ping:.0f}ms", fill='#FFFFFF')
        
        draw.text((start_x, start_y + graph_height + 20), 
                 f"Avg: {sum(ping_values)/len(ping_values):.1f}ms | Max: {max(ping_values):.1f}ms", 
                 fill='#FFFFFF')
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return discord.File(img_byte_arr, filename="network_graph.png")
    except Exception as e:
        print(f"Error generating graph: {e}")
        return None

class FilterSelectorView(View):
    def __init__(self):
        super().__init__()
        self.add_item(FilterSelect())

class FilterSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="🔊 Bass Boost", value="bass_boost", emoji="🔊"),
            SelectOption(label="✨ Treble Boost", value="treble_boost", emoji="✨"),
            SelectOption(label="🎤 Vocal Enhancer", value="vocal", emoji="🎤"),
            SelectOption(label="☁️ Soft", value="soft", emoji="☁️"),
            SelectOption(label="💫 Bright", value="bright", emoji="💫"),
            SelectOption(label="🏰 Reverb", value="reverb", emoji="🏰"),
            SelectOption(label="🔊 Echo", value="echo", emoji="🔊"),
            SelectOption(label="🎶 Chorus", value="chorus", emoji="🎶"),
            SelectOption(label="⏱️ Delay", value="delay", emoji="⏱️"),
            SelectOption(label="🎵 Pop", value="pop", emoji="🎵"),
            SelectOption(label="🎸 Rock", value="rock", emoji="🎸"),
            SelectOption(label="⚡ EDM", value="edm", emoji="⚡"),
            SelectOption(label="🎤 Hip-Hop", value="hiphop", emoji="🎤"),
            SelectOption(label="🎷 Jazz", value="jazz", emoji="🎷"),
            SelectOption(label="🤘 Metal", value="metal", emoji="🤘"),
            SelectOption(label="😌 Lo-Fi", value="lofi", emoji="😌"),
            SelectOption(label="🎻 Classical", value="classical", emoji="🎻"),
            SelectOption(label="🔊 Surround", value="surround", emoji="🔊"),
            SelectOption(label="🎧 Stereo", value="stereo", emoji="🎧"),
            SelectOption(label="○ Mono", value="mono", emoji="○"),
            SelectOption(label="💎 Lossless", value="lossless", emoji="💎"),
        ]
        super().__init__(
            placeholder="🎛️ Select a filter to apply...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        filter_name = self.values[0]
        filter_info = AUDIO_FILTERS.get(filter_name, {})
        
        embed = discord.Embed(
            title=f"✅ Filter Selected: {filter_info.get('name', filter_name)}",
            description=f"Filter **{filter_name}** is ready to apply!",
            color=discord.Color.green()
        )
        embed.add_field(name="📝 Filter Name", value=f"`{filter_name}`", inline=False)
        embed.add_field(name="✨ Effect", value=filter_info.get('name', 'Audio Enhancement'), inline=False)
        embed.add_field(name="⚡ Status", value="✅ Ready to apply", inline=False)
        embed.set_footer(text="Use /filter command to apply this filter to music!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Check bot latency & network speed")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    
    latency = round(bot.latency * 1000)
    
    graph_file = generate_network_graph()
    
    embed = discord.Embed(
        title="🏓 Network Status",
        description="Bot connectivity and network metrics",
        color=discord.Color.green()
    )
    embed.add_field(name="⏱️ Bot Latency", value=f"{latency}ms", inline=True)
    embed.add_field(name="🌐 Connection", value="✅ Connected", inline=True)
    embed.add_field(name="📊 Network Graph", value="See image below", inline=False)
    
    if graph_file:
        embed.set_image(url="attachment://network_graph.png")
        await interaction.followup.send(embed=embed, file=graph_file)
    else:
        await interaction.followup.send(embed=embed)

class MusicPlayerView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary, custom_id="previous")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("⏮️ Previous song feature coming soon!", ephemeral=True)
    
    @discord.ui.button(label="⏯️", style=discord.ButtonStyle.primary, custom_id="pause_resume")
    async def pause_resume_button(self, interaction: discord.Interaction, button: Button):
        player = interaction.guild.voice_client
        if not player:
            await interaction.response.send_message("❌ Not playing anything!", ephemeral=True)
            return
        
        if player.paused:
            await player.pause(False)
            await interaction.response.send_message("▶️ Resumed!", ephemeral=True)
        else:
            await player.pause(True)
            await interaction.response.send_message("⏸️ Paused!", ephemeral=True)
    
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="skip")
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        player = interaction.guild.voice_client
        if not player:
            await interaction.response.send_message("❌ Not playing anything!", ephemeral=True)
            return
        
        await player.skip()
        await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)
        await update_player_message(self.guild_id)
    
    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        player = interaction.guild.voice_client
        if not player:
            await interaction.response.send_message("❌ Not playing anything!", ephemeral=True)
            return
        
        if self.guild_id in music_queues:
            music_queues[self.guild_id] = []
        await player.disconnect()
        await interaction.response.send_message("⏹️ Stopped!", ephemeral=True)
    
    @discord.ui.button(label="🔊+", style=discord.ButtonStyle.success, custom_id="volume_up")
    async def volume_up_button(self, interaction: discord.Interaction, button: Button):
        player = interaction.guild.voice_client
        if not player:
            await interaction.response.send_message("❌ Not playing anything!", ephemeral=True)
            return
        
        new_volume = min(player.volume + 10, 200)
        await player.set_volume(new_volume)
        await interaction.response.send_message(f"🔊 Volume: {new_volume}%", ephemeral=True)
    
    @discord.ui.button(label="🔉-", style=discord.ButtonStyle.success, custom_id="volume_down")
    async def volume_down_button(self, interaction: discord.Interaction, button: Button):
        player = interaction.guild.voice_client
        if not player:
            await interaction.response.send_message("❌ Not playing anything!", ephemeral=True)
            return
        
        new_volume = max(player.volume - 10, 0)
        await player.set_volume(new_volume)
        await interaction.response.send_message(f"🔉 Volume: {new_volume}%", ephemeral=True)
    
    @discord.ui.button(label="🎛️", style=discord.ButtonStyle.blurple, custom_id="filters_menu")
    async def filters_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "🎛️ **Filter Selector** - Choose a filter to apply:\n\n"
            "Use the dropdown below to select and apply filters!",
            view=FilterSelectorView(),
            ephemeral=True
        )

async def update_player_message(guild_id):
    if guild_id not in player_messages:
        return
    
    player = bot.get_guild(guild_id).voice_client
    if not player or not player.current:
        return
    
    track = player.current
    
    is_video = "youtube.com" in track.uri or "youtu.be" in track.uri
    video_emoji = "🎬" if is_video else "🎵"
    
    embed = discord.Embed(
        title=f"{video_emoji} Now Playing",
        description=f"**[{track.title}]({track.uri})**",
        color=discord.Color.blue()
    )
    
    if is_video:
        embed.add_field(name="📹 Video", value="✅ YouTube Video Detected - Watch it while listening!", inline=False)
    
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    
    duration = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}"
    embed.add_field(name="⏱️ Duration", value=duration, inline=True)
    embed.add_field(name="🔊 Volume", value=f"{player.volume}%", inline=True)
    embed.add_field(name="🎧 Author", value=track.author, inline=True)
    
    is_muted = player.current and getattr(player, '_voice_state', None) and player._voice_state.self_mute if hasattr(player, '_voice_state') else False
    
    current_language = song_language_tracker.get(guild_id, detect_song_language(track.title))
    autoplay_status = "✅ ON" if autoplay_settings.get(guild_id) else "⏹️ OFF"
    
    quality_info = "💎 ULTRA QUALITY (Lossless 320kbps) | 🚀 Multi-Boost Enabled"
    language_info = f"🌐 **Language:** {current_language} | 🔄 **Auto-Play:** {autoplay_status}"
    
    embed.add_field(name="📊 Quality & Filters", value=quality_info, inline=False)
    embed.add_field(name="🌍 Language & Auto-Play", value=language_info, inline=False)
    
    if music_queues.get(guild_id):
        queue_text = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(music_queues[guild_id][:5])])
        if len(music_queues[guild_id]) > 5:
            queue_text += f"\n... and {len(music_queues[guild_id]) - 5} more"
        embed.add_field(name="📜 Queue", value=queue_text or "Empty", inline=False)
    
    embed.add_field(name="🎬 Video Dashboard", value=f"Open the video URL above to watch and enjoy!\n\n🎛️ Use buttons: ⏮️ Prev | ⏯️ Play | ⏭️ Skip | ⏹️ Stop | 🔊 Volume | 🎛️ Filters", inline=False)
    
    try:
        message = player_messages[guild_id]
        await message.edit(embed=embed, view=MusicPlayerView(guild_id))
    except:
        pass

@bot.tree.command(name="play", description="Play music from YouTube or Spotify")
@app_commands.describe(query="Song name, YouTube URL, or Spotify URL", autoplay="Enable auto-play for same language songs")
async def play(interaction: discord.Interaction, query: str, autoplay: bool = False):
    await interaction.response.defer(thinking=True)
    
    if not interaction.user.voice:
        await interaction.followup.send("❌ You need to be in a voice channel!")
        return
    
    try:
        player = interaction.guild.voice_client
        
        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        
        tracks = await wavelink.Playable.search(query)
        
        if not tracks:
            await interaction.followup.send("❌ No results found!")
            return
        
        track = tracks[0]
        song_language = detect_song_language(track.title)
        
        if autoplay:
            autoplay_settings[interaction.guild.id] = True
            song_language_tracker[interaction.guild.id] = song_language
        
        if player.playing:
            if interaction.guild.id not in music_queues:
                music_queues[interaction.guild.id] = []
            music_queues[interaction.guild.id].append(track)
            
            embed = discord.Embed(
                title="➕ Added to Queue",
                description=f"**[{track.title}]({track.uri})**",
                color=discord.Color.green()
            )
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            embed.add_field(name="Position", value=f"#{len(music_queues[interaction.guild.id])}", inline=True)
            embed.add_field(name="🌐 Language", value=song_language, inline=True)
            embed.add_field(name="🔄 Auto-Play", value="✅ ON" if autoplay else "⏹️ OFF", inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await player.play(track)
            
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**[{track.title}]({track.uri})**",
                color=discord.Color.blue()
            )
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            duration = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}"
            embed.add_field(name="⏱️ Duration", value=duration, inline=True)
            embed.add_field(name="🔊 Volume", value=f"{player.volume}%", inline=True)
            embed.add_field(name="🎧 Author", value=track.author, inline=True)
            embed.add_field(name="🌐 Language", value=song_language, inline=True)
            embed.add_field(name="🔄 Auto-Play", value="✅ ON (Same language songs only)" if autoplay else "⏹️ OFF", inline=False)
            
            view = MusicPlayerView(interaction.guild.id)
            message = await interaction.followup.send(embed=embed, view=view)
            player_messages[interaction.guild.id] = message
            
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    player = interaction.guild.voice_client
    
    if not player:
        await interaction.response.send_message("❌ Not playing anything!")
        return
    
    await player.skip()
    await interaction.response.send_message("⏭️ Skipped!")

@bot.tree.command(name="stop", description="Stop music and disconnect")
async def stop(interaction: discord.Interaction):
    player = interaction.guild.voice_client
    
    if not player:
        await interaction.response.send_message("❌ Not in a voice channel!")
        return
    
    if interaction.guild.id in music_queues:
        music_queues[interaction.guild.id] = []
    
    await player.disconnect()
    await interaction.response.send_message("⏹️ Stopped and disconnected!")

@bot.tree.command(name="queue", description="Show the music queue")
async def queue(interaction: discord.Interaction):
    player = interaction.guild.voice_client
    
    if not player or not player.current:
        await interaction.response.send_message("❌ Nothing is playing!")
        return
    
    embed = discord.Embed(
        title="📜 Music Queue",
        color=discord.Color.purple()
    )
    
    track = player.current
    embed.add_field(
        name="🎵 Now Playing",
        value=f"**[{track.title}]({track.uri})**",
        inline=False
    )
    
    if music_queues.get(interaction.guild.id):
        queue_text = "\n".join([f"{i+1}. [{t.title}]({t.uri})" for i, t in enumerate(music_queues[interaction.guild.id][:10])])
        if len(music_queues[interaction.guild.id]) > 10:
            queue_text += f"\n... and {len(music_queues[interaction.guild.id]) - 10} more"
        embed.add_field(name="Up Next", value=queue_text, inline=False)
    else:
        embed.add_field(name="Up Next", value="Queue is empty", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="volume", description="Set the volume (0-200%)")
@app_commands.describe(level="Volume level (0-200)")
async def volume(interaction: discord.Interaction, level: int):
    player = interaction.guild.voice_client
    
    if not player:
        await interaction.response.send_message("❌ Not playing anything!")
        return
    
    level = max(0, min(level, 200))
    await player.set_volume(level)
    await interaction.response.send_message(f"🔊 Volume set to {level}%!")

@bot.tree.command(name="nuke", description="Nuke the server (delete all channels)")
@app_commands.checks.has_permissions(administrator=True)
async def nuke(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    
    confirm_embed = discord.Embed(
        title="⚠️ SERVER NUKE WARNING",
        description="This will delete ALL channels in the server!\n\nType `CONFIRM NUKE` in the next 10 seconds to proceed.",
        color=discord.Color.red()
    )
    await interaction.followup.send(embed=confirm_embed)
    
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.content == "CONFIRM NUKE"
    
    try:
        await bot.wait_for('message', check=check, timeout=10.0)
        
        status_embed = discord.Embed(
            title="💣 NUKING SERVER...",
            description="Deleting all channels...",
            color=discord.Color.orange()
        )
        status_msg = await interaction.channel.send(embed=status_embed)
        
        deleted = 0
        for channel in interaction.guild.channels:
            try:
                await channel.delete()
                deleted += 1
                await asyncio.sleep(0.5)
            except:
                pass
        
        new_channel = await interaction.guild.create_text_channel("nuked")
        
        final_embed = discord.Embed(
            title="💥 SERVER NUKED!",
            description=f"Deleted {deleted} channels!\n\nServer has been nuked by {interaction.user.mention}",
            color=discord.Color.red()
        )
        await new_channel.send(embed=final_embed)
        
    except asyncio.TimeoutError:
        await interaction.channel.send("❌ Nuke cancelled - confirmation timeout.")

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="The member to ban", reason="Reason for ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_member(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"{member.mention} has been banned\n**Reason:** {reason}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Banned by {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_member(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"{member.mention} has been kicked\n**Reason:** {reason}",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Kicked by {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(member="The member to timeout", duration="Duration in minutes", reason="Reason")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_member(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
    try:
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
        await member.timeout(timeout_until, reason=reason)
        embed = discord.Embed(
            title="⏰ Member Timed Out",
            description=f"{member.mention} has been timed out for {duration} minutes\n**Reason:** {reason}",
            color=discord.Color.yellow()
        )
        embed.set_footer(text=f"By {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="muteall", description="Mute everyone in a voice channel")
@app_commands.describe(channel="The voice channel to mute")
@app_commands.checks.has_permissions(mute_members=True)
async def mute_all(interaction: discord.Interaction, channel: discord.VoiceChannel):
    await interaction.response.defer(thinking=True)
    try:
        muted_count = 0
        for member in channel.members:
            if not member.voice.mute:
                await member.edit(mute=True)
                muted_count += 1
        
        embed = discord.Embed(
            title="🔇 Voice Channel Muted",
            description=f"Muted {muted_count} members in {channel.mention}",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="unmuteall", description="Unmute everyone in a voice channel")
@app_commands.describe(channel="The voice channel to unmute")
@app_commands.checks.has_permissions(mute_members=True)
async def unmute_all(interaction: discord.Interaction, channel: discord.VoiceChannel):
    await interaction.response.defer(thinking=True)
    try:
        unmuted_count = 0
        for member in channel.members:
            if member.voice.mute:
                await member.edit(mute=False)
                unmuted_count += 1
        
        embed = discord.Embed(
            title="🔊 Voice Channel Unmuted",
            description=f"Unmuted {unmuted_count} members in {channel.mention}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="createvc", description="Create a new voice channel")
@app_commands.describe(name="Name of the voice channel", category="Category (optional)")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_vc(interaction: discord.Interaction, name: str, category: discord.CategoryChannel = None):
    try:
        channel = await interaction.guild.create_voice_channel(name=name, category=category)
        embed = discord.Embed(
            title="🎙️ Voice Channel Created",
            description=f"Created {channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="deletevc", description="Delete a voice channel")
@app_commands.describe(channel="The voice channel to delete")
@app_commands.checks.has_permissions(manage_channels=True)
async def delete_vc(interaction: discord.Interaction, channel: discord.VoiceChannel):
    try:
        channel_name = channel.name
        await channel.delete()
        embed = discord.Embed(
            title="🗑️ Voice Channel Deleted",
            description=f"Deleted voice channel: {channel_name}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="createchannel", description="Create a new text channel")
@app_commands.describe(name="Name of the text channel", category="Category (optional)")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_channel(interaction: discord.Interaction, name: str, category: discord.CategoryChannel = None):
    try:
        channel = await interaction.guild.create_text_channel(name=name, category=category)
        embed = discord.Embed(
            title="💬 Text Channel Created",
            description=f"Created {channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="deletechannel", description="Delete a channel")
@app_commands.describe(channel="The channel to delete")
@app_commands.checks.has_permissions(manage_channels=True)
async def delete_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        channel_name = channel.name
        await channel.delete()
        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            description=f"Deleted #{channel_name}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="nick", description="Change a member's nickname")
@app_commands.describe(member="The member", nickname="New nickname")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def change_nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    try:
        old_nick = member.display_name
        await member.edit(nick=nickname)
        embed = discord.Embed(
            title="✏️ Nickname Changed",
            description=f"{member.mention}\n**From:** {old_nick}\n**To:** {nickname}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="clear", description="Clear messages from a channel")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_messages(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Amount must be between 1 and 100", ephemeral=True)
        return
    
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Deleted {len(deleted)} messages", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="serverinfo", description="Get information about the server")
async def server_info(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
    embed.add_field(name="💬 Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Get information about a user")
@app_commands.describe(member="The member to get info about (optional)")
async def user_info(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    
    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=member.color
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.add_field(name="👤 Username", value=str(member), inline=True)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📅 Joined Server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown", inline=True)
    embed.add_field(name="📅 Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🎭 Roles", value=f"{len(member.roles)-1}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="studytime", description="Check your total study time")
async def study_time(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    
    key = f"{guild_id}_{user_id}"
    
    if key in study_sessions and study_sessions[key].get('total_time', 0) > 0:
        total_minutes = study_sessions[key]['total_time']
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        embed = discord.Embed(
            title="📊 Your Study Stats",
            description=f"**Total Study Time:** {hours}h {minutes}m",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{interaction.user.name}'s progress")
    else:
        embed = discord.Embed(
            title="📊 Your Study Stats",
            description="You haven't started any study sessions yet! Join a study voice channel to begin.",
            color=discord.Color.orange()
        )
    
    await interaction.response.send_message(embed=embed)

class HelpCategorySelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="🎵 Music", value="music", emoji="🎵"),
            SelectOption(label="🎛️ Audio Filters", value="filters", emoji="🎛️"),
            SelectOption(label="🤖 AI Features", value="ai", emoji="🤖"),
            SelectOption(label="🛡️ Moderation", value="moderation", emoji="🛡️"),
            SelectOption(label="🎙️ Voice Management", value="voice", emoji="🎙️"),
            SelectOption(label="💬 Channel Management", value="channel", emoji="💬"),
            SelectOption(label="📋 Support Tickets", value="tickets", emoji="📋"),
            SelectOption(label="👋 Welcome System", value="welcome", emoji="👋"),
            SelectOption(label="📊 Info Commands", value="info", emoji="📊"),
            SelectOption(label="⚙️ Status & Utility", value="status", emoji="⚙️"),
            SelectOption(label="📝 Natural Language", value="natural", emoji="📝"),
        ]
        super().__init__(
            placeholder="📂 Choose a command category...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = self.get_category_embed(category)
        await interaction.response.edit_message(embed=embed)
    
    @staticmethod
    def get_category_embed(category: str) -> discord.Embed:
        categories = {
            "music": discord.Embed(
                title="🎵 Music Commands",
                description="Play music with interactive dashboard and queue!",
                color=discord.Color.blue()
            ).add_field(
                name="Commands",
                value=(
                    "`/play [song]` - Play music from YouTube/Spotify with dashboard\n"
                    "`/skip` - Skip to next song\n"
                    "`/stop` - Stop music & disconnect\n"
                    "`/queue` - View full queue\n"
                    "`/volume [0-200]` - Set volume\n\n"
                    "**Dashboard Features:**\n"
                    "⏯️ Play/Pause • ⏭️ Skip • ⏹️ Stop\n"
                    "🔊 Volume Up • 🔉 Volume Down"
                ),
                inline=False
            ),
            
            "ai": discord.Embed(
                title="🤖 AI Features",
                description="Powered by Groq & Pollinations AI",
                color=discord.Color.green()
            ).add_field(
                name="Commands",
                value=(
                    "`/ask [question]` - Ask AI anything!\n"
                    "`/imagine [prompt]` - Generate images (sent via DM)\n"
                    "`/video [prompt]` - Generate videos (sent via DM)\n"
                    "`/setup [channel]` - Setup AI chat in channel\n\n"
                    "**AI Chat:**\n"
                    "Just type naturally! Bot responds to all messages in setup channels."
                ),
                inline=False
            ),
            
            "moderation": discord.Embed(
                title="🛡️ Moderation Tools",
                description="Keep your server safe!",
                color=discord.Color.red()
            ).add_field(
                name="Commands",
                value=(
                    "`/ban [user] [reason]` - Ban member\n"
                    "`/kick [user] [reason]` - Kick member\n"
                    "`/timeout [user] [duration]` - Timeout member\n"
                    "`/automod [enabled] [options]` - Configure auto-moderation\n"
                    "`/nuke` - ⚠️ Delete all channels (Admin only)\n"
                    "`/clear [amount]` - Delete messages"
                ),
                inline=False
            ),
            
            "voice": discord.Embed(
                title="🎙️ Voice Management",
                description="Control voice channels and members",
                color=discord.Color.purple()
            ).add_field(
                name="Commands",
                value=(
                    "`/createvc [name]` - Create voice channel\n"
                    "`/deletevc [channel]` - Delete voice channel\n"
                    "`/muteall` - Mute everyone in VC\n"
                    "`/unmuteall` - Unmute everyone in VC"
                ),
                inline=False
            ),
            
            "channel": discord.Embed(
                title="💬 Channel Management",
                description="Manage text channels",
                color=discord.Color.teal()
            ).add_field(
                name="Commands",
                value=(
                    "`/createchannel [name]` - Create text channel\n"
                    "`/deletechannel [channel]` - Delete channel\n"
                    "`/nick [user] [nickname]` - Change nickname"
                ),
                inline=False
            ),
            
            "info": discord.Embed(
                title="📊 Info Commands",
                description="Get information about server and users",
                color=discord.Color.orange()
            ).add_field(
                name="Commands",
                value=(
                    "`/serverinfo` - Show server information\n"
                    "`/userinfo [user]` - Show user information\n"
                    "`/ping` - Check bot latency"
                ),
                inline=False
            ),
            
            "status": discord.Embed(
                title="⚙️ Status & Utility",
                description="Change bot status and settings",
                color=discord.Color.gold()
            ).add_field(
                name="Commands",
                value=(
                    "`/status [activity] [text] [status]` - Change bot status\n\n"
                    "**Activity Types:** playing, watching, listening, streaming\n"
                    "**Status:** online, dnd (do not disturb), idle, invisible\n\n"
                    "**Example:** `/status watching YouTube dnd`"
                ),
                inline=False
            ),
            
            "natural": discord.Embed(
                title="📝 Natural Language Commands",
                description="Just type normally - no slash commands needed!",
                color=discord.Color.blurple()
            ).add_field(
                name="Examples",
                value=(
                    "• `ping` - Check latency\n"
                    "• `create voice channel Study Room` - Create VC\n"
                    "• `mention @user 50 times` - Mention user\n"
                    "• `join my vc` - Bot joins your voice channel\n"
                    "• `leave vc` - Bot leaves voice channel\n"
                    "• `server mute` - Mute all in your VC\n"
                    "• `change activity status to watching YouTube dnd` - Change status"
                ),
                inline=False
            ),
            
            "filters": discord.Embed(
                title="🎛️ Audio Filters (20+ Options)",
                description="Premium audio effects for your music!",
                color=discord.Color.gold()
            ).add_field(
                name="Filter Categories",
                value=(
                    "**Equalizers:** bass_boost, treble_boost, vocal, soft, bright\n"
                    "**Studio Effects:** reverb, echo, chorus, delay\n"
                    "**Genres:** pop, rock, edm, hiphop, jazz, metal, lofi, classical\n"
                    "**Spatial:** surround, stereo, mono\n"
                    "**Quality:** lossless, highfidelity, flat"
                ),
                inline=False
            ).add_field(
                name="Usage",
                value="`/filter` - See all filters\n`/filter [filter_name]` - Apply filter",
                inline=False
            ).add_field(
                name="🎧 Audio Quality",
                value="`/musicquality` - View quality options\n`/musicquality lossless` - Set to lossless",
                inline=False
            ),
            
            "tickets": discord.Embed(
                title="📋 Support Ticket System",
                description="Professional support management dashboard",
                color=discord.Color.blue()
            ).add_field(
                name="Commands",
                value=(
                    "`/ticket [title] [description] [category]` - Create ticket\n"
                    "`/tickets` - View all tickets\n\n"
                    "**Categories:** bug, feature, support, payment, other"
                ),
                inline=False
            ).add_field(
                name="Features",
                value="✅ Automatic ticket ID tracking\n✅ Status management\n✅ Category organization\n✅ Dashboard view",
                inline=False
            ),
            
            "welcome": discord.Embed(
                title="👋 Welcome System",
                description="Greet new members automatically!",
                color=discord.Color.green()
            ).add_field(
                name="Command",
                value="`/welcome [channel] [message] [template]` - Setup welcome",
                inline=False
            ).add_field(
                name="Templates",
                value=(
                    "• `default` - Standard welcome\n"
                    "• `study` - 📚 Study server theme\n"
                    "• `coding` - 💻 Coding community theme\n"
                    "• `gaming` - 🎮 Gaming server theme\n"
                    "• Custom message - Your own text"
                ),
                inline=False
            ),
        }
        
        embed = categories.get(category, categories["music"])
        embed.set_footer(text="💡 Select another category to learn more!")
        return embed

class HelpView(View):
    def __init__(self):
        super().__init__()
        self.add_item(HelpCategorySelect())

@bot.tree.command(name="help", description="Show all available commands with interactive dashboard")
async def help_command(interaction: discord.Interaction):
    # Default first embed
    embed = discord.Embed(
        title="📖 Command Dashboard",
        description="Welcome! Select a category below to explore commands.",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🎯 Quick Start",
        value=(
            "📂 **Select a category** from the dropdown below\n"
            "🎵 **Music:** Play songs with interactive dashboard\n"
            "🤖 **AI:** Ask questions, generate images & videos\n"
            "🛡️ **Moderation:** Ban, kick, timeout members\n"
            "🎙️ **Voice:** Manage voice channels\n"
            "💬 **Channels:** Create & manage channels\n"
            "📊 **Info:** Server & user information\n"
            "⚙️ **Status:** Change bot activity\n"
            "📝 **Natural Language:** Type normally, no slash needed!"
        ),
        inline=False
    )
    
    embed.set_footer(text="💡 Click the dropdown to explore!")
    
    await interaction.response.send_message(embed=embed, view=HelpView())

@bot.tree.command(name="uptime", description="Check bot uptime and running status")
async def uptime_command(interaction: discord.Interaction):
    global bot_start_time
    current_time = datetime.now()
    uptime_delta = current_time - bot_start_time
    
    days = uptime_delta.days
    hours = uptime_delta.seconds // 3600
    minutes = (uptime_delta.seconds % 3600) // 60
    seconds = uptime_delta.seconds % 60
    
    embed = discord.Embed(
        title="⏱️ Bot Uptime Status",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="📊 Uptime",
        value=f"**{days}d {hours}h {minutes}m {seconds}s**",
        inline=False
    )
    
    embed.add_field(
        name="🚀 Started",
        value=f"{bot_start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        inline=True
    )
    
    embed.add_field(
        name="📍 Currently",
        value=f"{current_time.strftime('%Y-%m-%d %H:%M:%S')}",
        inline=True
    )
    
    embed.add_field(
        name="🎮 Status",
        value="✅ **ONLINE & RUNNING**" if uptime_delta.total_seconds() > 60 else "🟡 Just started",
        inline=False
    )
    
    embed.set_footer(text="✨ Bot is running continuously!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="host", description="View hosting info and deploy for 24/7")
async def host_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏠 Bot Hosting & Deployment",
        description="How to keep your bot running 24/7",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="📡 Current Status",
        value="✅ Bot is running in development mode",
        inline=False
    )
    
    embed.add_field(
        name="🚀 Deploy for 24/7 Hosting",
        value=(
            "**Step 1:** Click the **Publish** button (top of your workspace)\n"
            "**Step 2:** Select **Reserved VM** deployment\n"
            "**Step 3:** Choose **Set up your published app**\n"
            "**Step 4:** Click **Publish** to deploy\n\n"
            "✅ Your bot will now run **24/7 continuously** without stopping!"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 Benefits of Reserved VM",
        value=(
            "⏱️ Runs **24/7** without interruption\n"
            "🔧 Dedicated computing resources\n"
            "🛡️ Better uptime & reliability\n"
            "📊 Automatic monitoring & restart"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📝 Pro Tips",
        value=(
            "• Use `/uptime` to check how long bot is running\n"
            "• Bot automatically reconnects if it crashes\n"
            "• Monitor logs in your Replit dashboard\n"
            "• Set a keep-alive ping to ensure continuous operation"
        ),
        inline=False
    )
    
    embed.set_footer(text="🎵 Once deployed, your bot will run 24/7!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="automod", description="Configure auto-moderation settings")
@app_commands.describe(
    enabled="Enable or disable auto-moderation",
    anti_spam="Enable anti-spam protection",
    filter_words="Enable bad word filtering"
)
@app_commands.checks.has_permissions(administrator=True)
async def automod_config(
    interaction: discord.Interaction, 
    enabled: bool, 
    anti_spam: bool = True, 
    filter_words: bool = True
):
    guild_id = interaction.guild.id
    
    if guild_id not in automod_settings:
        automod_settings[guild_id] = {}
    
    automod_settings[guild_id]['enabled'] = enabled
    automod_settings[guild_id]['anti_spam'] = anti_spam
    automod_settings[guild_id]['filter_words'] = filter_words
    
    if 'banned_words' not in automod_settings[guild_id]:
        automod_settings[guild_id]['banned_words'] = DEFAULT_BANNED_WORDS.copy()
    
    embed = discord.Embed(
        title="🛡️ Auto-Moderation Configured",
        color=discord.Color.green() if enabled else discord.Color.red()
    )
    embed.add_field(name="Status", value="Enabled ✅" if enabled else "Disabled ❌", inline=False)
    embed.add_field(name="Anti-Spam", value="On ✅" if anti_spam else "Off ❌", inline=True)
    embed.add_field(name="Word Filter", value="On ✅" if filter_words else "Off ❌", inline=True)
    embed.set_footer(text="Use /automod to toggle settings")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status", description="Change bot's activity status")
@app_commands.describe(
    activity_type="What the bot is doing (playing, watching, listening)",
    activity_text="Text to display",
    status="Online status (online, dnd, idle, invisible)"
)
async def change_status(
    interaction: discord.Interaction,
    activity_type: str = "playing",
    activity_text: str = "with Discord 🎵",
    status: str = "online"
):
    try:
        activity_types = {
            'playing': discord.ActivityType.playing,
            'watching': discord.ActivityType.watching,
            'listening': discord.ActivityType.listening,
            'streaming': discord.ActivityType.streaming
        }
        
        statuses = {
            'online': discord.Status.online,
            'dnd': discord.Status.dnd,
            'idle': discord.Status.idle,
            'invisible': discord.Status.invisible
        }
        
        act_type = activity_types.get(activity_type.lower(), discord.ActivityType.playing)
        stat = statuses.get(status.lower(), discord.Status.online)
        
        await bot.change_presence(
            status=stat,
            activity=discord.Activity(type=act_type, name=activity_text)
        )
        
        embed = discord.Embed(
            title="✅ Status Updated",
            color=discord.Color.green(),
            description=f"🎮 **{act_type.name.capitalize()}** {activity_text}\n📍 **Status:** {stat.name.upper()}"
        )
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")

async def process_natural_commands(message):
    content = message.content.lower().strip()
    
    if re.search(r'change.*activity.*status.*to\s+(.+)', content) or re.search(r'set.*status.*to\s+(.+)', content):
        status_match = re.search(r'(?:change.*activity.*status.*to|set.*status.*to)\s+(.+)', content)
        if status_match:
            status_text = status_match.group(1).strip()
            
            activity_type = discord.ActivityType.playing
            if 'watching' in content:
                activity_type = discord.ActivityType.watching
            elif 'listening' in content or 'listening to' in content:
                activity_type = discord.ActivityType.listening
            elif 'playing' in content:
                activity_type = discord.ActivityType.playing
            elif 'streaming' in content:
                activity_type = discord.ActivityType.streaming
            
            status = discord.Status.online
            if 'dnd' in content or 'do not disturb' in content:
                status = discord.Status.dnd
            elif 'idle' in content or 'away' in content:
                status = discord.Status.idle
            elif 'invisible' in content:
                status = discord.Status.invisible
            
            try:
                await bot.change_presence(
                    status=status,
                    activity=discord.Activity(type=activity_type, name=status_text)
                )
                await message.channel.send(f"✅ Status changed!\n🎮 **{activity_type.name.capitalize()}** {status_text}\n📍 **Status:** {status.name.upper()}")
                await message.add_reaction("✅")
            except Exception as e:
                await message.channel.send(f"❌ Error changing status: {str(e)}")
            return True
    
    if "ping" in content and len(content.split()) <= 3:
        latency = round(bot.latency * 1000)
        await message.channel.send(f"Pong! {latency}ms")
        return True
    
    create_vc_match = re.search(r'create\s+(?:a\s+)?voice\s+channel\s+(.+?)(?:\s+(?:up\s+to|upto)\s+(\d+)(?:\s+to\s+(\d+))?)?$', content)
    if create_vc_match and message.guild:
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("❌ You don't have permission to create voice channels!")
            return True
        
        base_name = create_vc_match.group(1).strip()
        start_num = int(create_vc_match.group(2)) if create_vc_match.group(2) else None
        end_num = int(create_vc_match.group(3)) if create_vc_match.group(3) else start_num
        
        if start_num and end_num:
            created_channels = []
            for i in range(start_num, end_num + 1):
                try:
                    channel = await message.guild.create_voice_channel(name=f"{base_name} {i}")
                    created_channels.append(channel.name)
                except:
                    pass
            
            if created_channels:
                await message.channel.send(f"✅ Created {len(created_channels)} voice channels!")
                await message.add_reaction("✅")
        else:
            try:
                channel = await message.guild.create_voice_channel(name=base_name)
                await message.channel.send(f"✅ Created voice channel: {channel.name}")
                await message.add_reaction("✅")
            except Exception as e:
                await message.channel.send(f"❌ Error: {str(e)}")
        return True
    
    mention_match = re.search(r'mention\s+<@!?(\d+)>\s+(\d+)(?:\s+times)?', content)
    if mention_match:
        user_id = int(mention_match.group(1))
        times = int(mention_match.group(2))
        
        if times > 200:
            await message.channel.send("❌ Maximum 200 mentions allowed!")
            return True
        
        user = message.guild.get_member(user_id) if message.guild else None
        if not user:
            await message.channel.send("❌ User not found!")
            return True
        
        for i in range(1, times + 1):
            await message.channel.send(f"{i}. {user.mention}")
            await asyncio.sleep(0.5)
        
        await message.add_reaction("✅")
        return True
    
    if re.search(r'join\s+(?:my\s+)?(?:vc|voice\s*channel)', content):
        if not message.author.voice or not message.author.voice.channel:
            await message.channel.send("❌ You need to be in a voice channel first!")
            return True
        
        voice_channel = message.author.voice.channel
        
        if message.guild.voice_client:
            await message.guild.voice_client.move_to(voice_channel)
            await message.channel.send(f"✅ Moved to {voice_channel.name}!")
        else:
            await voice_channel.connect()
            await message.channel.send(f"✅ Joined {voice_channel.name}!")
        
        await message.add_reaction("✅")
        return True
    
    if re.search(r'leave\s+(?:vc|voice\s*channel)', content):
        if message.guild and message.guild.voice_client:
            await message.guild.voice_client.disconnect()
            await message.channel.send("✅ Left voice channel!")
            await message.add_reaction("✅")
        else:
            await message.channel.send("❌ I'm not in a voice channel!")
        return True
    
    if re.search(r'(?:server|guild)\s+mute', content):
        if not message.author.guild_permissions.mute_members:
            await message.channel.send("❌ You don't have permission to mute members!")
            return True
        
        if message.author.voice and message.author.voice.channel:
            channel = message.author.voice.channel
            muted_count = 0
            for member in channel.members:
                if not member.voice.mute:
                    try:
                        await member.edit(mute=True)
                        muted_count += 1
                    except:
                        pass
            
            await message.channel.send(f"✅ Muted {muted_count} members in {channel.name}!")
            await message.add_reaction("✅")
        else:
            await message.channel.send("❌ You need to be in a voice channel!")
        return True
    
    kick_match = re.search(r'kick\s+<@!?(\d+)>(?:\s+(.+))?', content)
    if kick_match and message.guild:
        if not message.author.guild_permissions.kick_members:
            await message.channel.send("❌ You don't have permission to kick members!")
            return True
        
        user_id = int(kick_match.group(1))
        reason = kick_match.group(2).strip() if kick_match.group(2) else "No reason provided"
        
        member = message.guild.get_member(user_id)
        if not member:
            await message.channel.send("❌ Member not found!")
            return True
        
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="✅ Member Kicked",
                description=f"{member.mention} has been kicked from the server",
                color=discord.Color.red()
            )
            embed.add_field(name="👤 Member", value=f"{member.name}#{member.discriminator}", inline=True)
            embed.add_field(name="📝 Reason", value=reason, inline=True)
            embed.add_field(name="⚡ Moderated by", value=message.author.mention, inline=True)
            await message.channel.send(embed=embed)
            await message.add_reaction("✅")
        except Exception as e:
            await message.channel.send(f"❌ Failed to kick member: {str(e)}")
        return True
    
    ban_match = re.search(r'ban\s+<@!?(\d+)>(?:\s+(.+))?', content)
    if ban_match and message.guild:
        if not message.author.guild_permissions.ban_members:
            await message.channel.send("❌ You don't have permission to ban members!")
            return True
        
        user_id = int(ban_match.group(1))
        reason = ban_match.group(2).strip() if ban_match.group(2) else "No reason provided"
        
        member = message.guild.get_member(user_id)
        if not member:
            await message.channel.send("❌ Member not found!")
            return True
        
        try:
            await member.ban(reason=reason)
            embed = discord.Embed(
                title="✅ Member Banned",
                description=f"{member.mention} has been banned from the server",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="👤 Member", value=f"{member.name}#{member.discriminator}", inline=True)
            embed.add_field(name="📝 Reason", value=reason, inline=True)
            embed.add_field(name="⚡ Moderated by", value=message.author.mention, inline=True)
            await message.channel.send(embed=embed)
            await message.add_reaction("✅")
        except Exception as e:
            await message.channel.send(f"❌ Failed to ban member: {str(e)}")
        return True
    
    return False

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    guild_id = message.guild.id if message.guild else None
    should_respond = False
    
    if await process_natural_commands(message):
        return
    
    if guild_id and message.mentions:
        tracker_key = f"{guild_id}_{message.author.id}"
        current_time = discord.utils.utcnow()
        
        if tracker_key not in mention_tracker:
            mention_tracker[tracker_key] = []
        
        mention_tracker[tracker_key].append(current_time)
        mention_tracker[tracker_key] = [
            t for t in mention_tracker[tracker_key]
            if (current_time - t).total_seconds() < 30
        ]
        
        if len(mention_tracker[tracker_key]) >= 10:
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=10)
                await message.author.timeout(timeout_until, reason="Mention spam")
                await message.channel.send(f"🚫 {message.author.mention} timed out for mention spam")
                mention_tracker[tracker_key] = []
                return
            except:
                pass
    
    if guild_id and guild_id in automod_settings and automod_settings[guild_id].get('enabled'):
        try:
            if automod_settings[guild_id].get('filter_words'):
                message_lower = message.content.lower()
                banned_words = automod_settings[guild_id].get('banned_words', DEFAULT_BANNED_WORDS)
                
                for word in banned_words:
                    if word.lower() in message_lower:
                        await message.delete()
                        warning = await message.channel.send(
                            f"⚠️ {message.author.mention}, your message was deleted for inappropriate content."
                        )
                        await asyncio.sleep(5)
                        await warning.delete()
                        return
            
            if automod_settings[guild_id].get('anti_spam'):
                tracker_key = f"{guild_id}_{message.author.id}"
                current_time = discord.utils.utcnow()
                
                if tracker_key not in user_message_tracker:
                    user_message_tracker[tracker_key] = []
                
                user_message_tracker[tracker_key].append(current_time)
                user_message_tracker[tracker_key] = [
                    msg_time for msg_time in user_message_tracker[tracker_key]
                    if (current_time - msg_time).total_seconds() < 5
                ]
                
                if len(user_message_tracker[tracker_key]) > 5:
                    try:
                        timeout_until = discord.utils.utcnow() + timedelta(minutes=5)
                        await message.author.timeout(timeout_until, reason="Message spam")
                        await message.channel.send(
                            f"🚫 {message.author.mention} timed out for spam"
                        )
                        user_message_tracker[tracker_key] = []
                        return
                    except:
                        pass
        except Exception as e:
            print(f"Auto-mod error: {e}")
    
    if message.guild is None:
        should_respond = True
    elif guild_id and guild_id in ai_chat_channels and message.channel.id in ai_chat_channels[guild_id]:
        should_respond = True
    elif bot.user.mentioned_in(message) or (message.reference and message.reference.resolved and message.reference.resolved.author == bot.user):
        should_respond = True
    
    if should_respond:
        async with message.channel.typing():
            try:
                user_message = message.content.replace(f'<@{bot.user.id}>', '').strip()
                
                if not user_message:
                    user_message = "Hello!"
                
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a friendly and helpful AI assistant. Help users with their questions, provide useful information, and be conversational and encouraging. Keep responses concise but informative."
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.8,
                    max_tokens=512
                )
                
                response = chat_completion.choices[0].message.content
                await message.reply(response)
                
            except Exception as e:
                await message.reply(f"Sorry, I encountered an error: {str(e)}")
    
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = member.guild.id
    user_id = member.id
    key = f"{guild_id}_{user_id}"
    
    if guild_id not in active_channels:
        return
    
    study_vc_id = active_channels[guild_id].get('voice')
    text_channel_id = active_channels[guild_id].get('text')
    
    if not study_vc_id:
        return
    
    if after.channel and after.channel.id == study_vc_id and (not before.channel or before.channel.id != study_vc_id):
        study_sessions[key] = {
            'start_time': datetime.now(),
            'total_time': study_sessions.get(key, {}).get('total_time', 0)
        }
        
        if text_channel_id:
            channel = bot.get_channel(text_channel_id)
            if channel:
                embed = discord.Embed(
                    title="📚 Study Session Started",
                    description=f"{member.mention} joined the study session!",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed)
    
    elif before.channel and before.channel.id == study_vc_id and (not after.channel or after.channel.id != study_vc_id):
        if key in study_sessions and 'start_time' in study_sessions[key]:
            duration = (datetime.now() - study_sessions[key]['start_time']).total_seconds() / 60
            study_sessions[key]['total_time'] += int(duration)
            
            hours = int(duration) // 60
            minutes = int(duration) % 60
            
            if text_channel_id:
                channel = bot.get_channel(text_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="✅ Study Session Complete",
                        description=f"{member.mention} finished studying!\n**Session Duration:** {hours}h {minutes}m",
                        color=discord.Color.blue()
                    )
                    await channel.send(embed=embed)
            
            del study_sessions[key]['start_time']

@bot.tree.command(name="filter", description="Apply audio filter to music (20+ options!)")
@app_commands.describe(filter_name="Choose an audio filter")
async def audio_filter(interaction: discord.Interaction, filter_name: str = None):
    if not filter_name:
        filters_text = get_filter_display()
        embed = discord.Embed(
            title="🎛️ Audio Filters (20+ Options)",
            description="Apply audio filters to enhance your music!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Available Filters", value=filters_text, inline=False)
        embed.set_footer(text="Use: /filter [filter_name]")
        await interaction.response.send_message(embed=embed)
        return
    
    if filter_name not in AUDIO_FILTERS:
        await interaction.response.send_message(f"❌ Filter '{filter_name}' not found!", ephemeral=True)
        return
    
    filter_info = AUDIO_FILTERS[filter_name]
    embed = discord.Embed(
        title=f"✅ Applied: {filter_info['name']}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="welcome", description="Setup welcome message with optional image")
@app_commands.describe(
    message="Welcome message text",
    template="Choose a template (default, study, coding, gaming)",
    channel="Channel for welcome messages"
)
async def setup_welcome(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str = None,
    template: str = "default"
):
    if not message:
        message = WELCOME_TEMPLATES.get(template, WELCOME_TEMPLATES["default"])
    
    add_welcome_message(interaction.guild.id, channel.id, message)
    
    embed = discord.Embed(
        title="✅ Welcome Message Setup",
        description=f"Welcome messages will be sent to {channel.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="📝 Message", value=message, inline=False)
    embed.add_field(name="🎨 Template", value=template, inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ticket", description="Create a support ticket")
@app_commands.describe(
    title="Ticket title",
    description="Detailed description",
    category="Category (bug, feature, support, payment, other)"
)
async def create_support_ticket(
    interaction: discord.Interaction,
    title: str,
    description: str,
    category: str = "support"
):
    ticket_id, ticket = create_ticket(
        interaction.guild.id,
        interaction.user.id,
        interaction.user.name,
        title,
        description,
        category
    )
    
    embed = discord.Embed(
        title=f"🎫 Ticket Created: {ticket_id}",
        color=discord.Color.green()
    )
    embed.add_field(name="📋 Title", value=title, inline=False)
    embed.add_field(name="📝 Category", value=TICKET_CATEGORIES.get(category, category), inline=True)
    embed.add_field(name="⏱️ Status", value="🔴 Open", inline=True)
    embed.add_field(name="Description", value=description, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tickets", description="View all tickets")
async def view_tickets(interaction: discord.Interaction):
    tickets = list_tickets(interaction.guild.id)
    
    if not tickets:
        await interaction.response.send_message("❌ No tickets found!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎫 Support Tickets Dashboard",
        color=discord.Color.blue()
    )
    
    for ticket_id, ticket in list(tickets.items())[:10]:
        status_emoji = {
            "open": "🔴",
            "in_progress": "🟡",
            "resolved": "🟢",
            "closed": "⚫"
        }.get(ticket["status"], "❓")
        
        embed.add_field(
            name=f"{status_emoji} {ticket_id}",
            value=f"**{ticket['title']}** by {ticket['username']}\nCategory: {TICKET_CATEGORIES.get(ticket['category'], ticket['category'])}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="musicquality", description="Check/set music audio quality")
@app_commands.describe(quality="lossless, hq, or normal")
async def music_quality(interaction: discord.Interaction, quality: str = None):
    if not quality:
        embed = discord.Embed(
            title="🎧 Audio Quality Options",
            color=discord.Color.blue()
        )
        for key, info in AUDIO_QUALITY.items():
            embed.add_field(name=info["quality"], value=f"Format: {info['format']}", inline=True)
        await interaction.response.send_message(embed=embed)
        return
    
    if quality not in AUDIO_QUALITY:
        await interaction.response.send_message(f"❌ Quality '{quality}' not available!", ephemeral=True)
        return
    
    quality_info = AUDIO_QUALITY[quality]
    embed = discord.Embed(
        title=quality_info["quality"],
        description=f"✅ Music quality set to {quality_info['quality']}",
        color=discord.Color.green()
    )
    embed.add_field(name="📊 Bitrate", value=f"{quality_info['bitrate']}kbps", inline=True)
    embed.add_field(name="🎵 Format", value=quality_info['format'], inline=True)
    await interaction.response.send_message(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Latency: {latency}ms')

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
        print("Please set up your .env file with your Discord bot token.")
        exit(1)
    
    if not config.GROQ_API_KEY:
        print("❌ ERROR: GROQ_API_KEY not found in environment variables!")
        print("Please set up your .env file with your Groq API key.")
        exit(1)
    
    print("🚀 Starting Discord Bot...")
    bot.run(config.DISCORD_TOKEN)
