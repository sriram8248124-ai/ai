# 🤖 Advanced Discord AI Chatbot & Server Manager

A powerful Discord bot with **AI chat that responds to EVERY message** (no prefix needed!), server management, moderation tools, and FREE image generation - all powered by **FREE Groq AI**.

## ✨ Features

- 🤖 **FREE AI Chat** - Set up channels where bot responds to EVERY message (no @ or prefix needed!)
- 💬 **DM Support** - Chat with the bot in direct messages
- 🎨 **Image Generation** - AI-powered images sent via DM (FREE!)
- 🛡️ **Server Moderation** - Ban, kick, timeout, auto-mod with spam detection
- 🎙️ **Voice Management** - Mute all, unmute all, create/delete voice channels
- 💬 **Channel Management** - Create, delete, and manage channels
- 👥 **Member Management** - Change nicknames, manage permissions
- 📊 **Server Info** - Detailed server and user statistics
- 🚫 **Anti-Spam** - Mention spam detection (10+ mentions in 30 seconds = timeout)

## 🚀 Quick Setup Guide

### Step 1: Get Your Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" tab on the left
4. Click "Add Bot"
5. Under "TOKEN", click "Reset Token" and copy it (save this for later!)
6. **IMPORTANT**: Enable these settings under "Privileged Gateway Intents":
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent
7. Go to "OAuth2" > "URL Generator"
8. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
9. Select permissions (check ALL):
   - ✅ Administrator (or select specific permissions below)
   - ✅ Manage Channels
   - ✅ Manage Roles
   - ✅ Kick Members
   - ✅ Ban Members
   - ✅ Manage Nicknames
   - ✅ Manage Messages
   - ✅ Mute Members
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Attach Files
   - ✅ Use Slash Commands
10. Copy the generated URL and open it in your browser to invite the bot to your server!

### Step 2: Get Your FREE Groq API Key

1. Visit [console.groq.com](https://console.groq.com)
2. Sign up for a FREE account (no credit card required!)
3. Once logged in, go to "API Keys" section
4. Click "Create API Key"
5. Give it a name (e.g., "Discord Bot")
6. Copy the API key (save this for later!)

### Step 3: Configure the Bot on Replit

1. In Replit, go to the **Secrets** tab (🔒 icon on the left sidebar)
2. Add these two secrets:
   - Key: `DISCORD_TOKEN` → Value: (paste your Discord bot token)
   - Key: `GROQ_API_KEY` → Value: (paste your Groq API key)

### Step 4: Run the Bot

1. Click the **Run** button in Replit
2. Wait for the bot to start
3. You should see: `✅ Bot is ready! Logged in as YourBotName`

## 📖 Command List

### 🤖 AI Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/ask` | Ask the AI anything | `/ask How do I solve this problem?` |
| `/imagine` | Generate AI image (sent via DM) | `/imagine a futuristic city` |
| `/help` | Show all commands | `/help` |
| `/setup` | Setup AI chat channel (no prefix needed!) | `/setup channel:#general` |

### 🛡️ Moderation Commands

| Command | Description | Permissions Required | Usage |
|---------|-------------|---------------------|-------|
| `/ban` | Ban a member from the server | Ban Members | `/ban @user spam` |
| `/kick` | Kick a member from the server | Kick Members | `/kick @user breaking rules` |
| `/timeout` | Timeout a member | Moderate Members | `/timeout @user 10 spam` |
| `/clear` | Delete messages (1-100) | Manage Messages | `/clear 50` |
| `/automod` | Configure auto-moderation (spam, word filter) | Administrator | `/automod enabled:True anti_spam:True` |

### 🎙️ Voice Management

| Command | Description | Permissions Required | Usage |
|---------|-------------|---------------------|-------|
| `/muteall` | Mute everyone in a voice channel | Mute Members | `/muteall #voice-channel` |
| `/unmuteall` | Unmute everyone in a voice channel | Mute Members | `/unmuteall #voice-channel` |
| `/createvc` | Create a new voice channel | Manage Channels | `/createvc Study Room` |
| `/deletevc` | Delete a voice channel | Manage Channels | `/deletevc #old-vc` |

### 💬 Channel Management

| Command | Description | Permissions Required | Usage |
|---------|-------------|---------------------|-------|
| `/createchannel` | Create a text channel | Manage Channels | `/createchannel announcements` |
| `/deletechannel` | Delete a channel | Manage Channels | `/deletechannel #old-channel` |

### 👥 Member Management

| Command | Description | Permissions Required | Usage |
|---------|-------------|---------------------|-------|
| `/nick` | Change a member's nickname | Manage Nicknames | `/nick @user NewName` |

### 📊 Information Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/serverinfo` | Get server statistics | `/serverinfo` |
| `/userinfo` | Get user information | `/userinfo @user` |

### 💬 AI Chat Setup

**Main Feature:** Use `/setup` to designate a channel where the bot responds to **EVERY message** (no prefix or @ needed!)

```
/setup channel:#ai-chat
```

After setup, just chat normally in that channel:
```
User: What's the weather like?
Bot: [AI Response]

User: Tell me a joke
Bot: [AI Response]
```

**DM Support:** You can also DM the bot directly - it will respond to all DMs!

**Mentions:** Bot also responds when you @ mention it or reply to its messages in any channel

## 🎯 Common Use Cases

### Server Moderation
```
/ban @spammer Spamming links
/kick @troublemaker Breaking rules
/timeout @user 30 Excessive caps
/clear 20
```

### Voice Channel Management
```
/createvc Study Session
/muteall #general-vc
/unmuteall #general-vc
```

### Channel Organization
```
/createchannel announcements
/createchannel general-chat
/deletechannel #old-channel
```

### AI Assistance
```
/ask How do I code a Discord bot?
/imagine a beautiful sunset over mountains
@BotName tell me a joke
```

### Study Tracking
```
/setup #study-room #study-chat
[Join the voice channel]
/studytime
```

## 🔧 Configuration

The bot uses these environment variables:

- `DISCORD_TOKEN` - Your Discord bot token (required)
- `GROQ_API_KEY` - Your Groq API key (required)
- `BOT_PREFIX` - Command prefix for text commands (default: `!`)

## 🛡️ Permission Setup

For best performance, give the bot these permissions:
- ✅ Administrator (easiest)

Or individually:
- Manage Channels
- Manage Roles
- Kick Members
- Ban Members
- Timeout Members
- Manage Nicknames
- Manage Messages
- Mute Members
- Send Messages
- Embed Links
- Read Message History

## 🐛 Troubleshooting

### Bot doesn't respond to commands
- Make sure you enabled "Message Content Intent" in Discord Developer Portal
- Wait a few minutes for Discord to sync slash commands
- Re-invite the bot with all permissions

### Permission errors
- Ensure the bot's role is higher than the role of members you're trying to moderate
- Check that the bot has the required permissions for each command

### "Invalid Token" error
- Double-check your DISCORD_TOKEN in Replit Secrets
- Make sure you copied the entire token

### Groq API errors
- Verify your GROQ_API_KEY is correct
- Check if you've hit the free tier rate limit
- Visit [console.groq.com](https://console.groq.com) to check API status

## 💡 Pro Tips

- Use `/help` to see all available commands anytime
- The bot responds to mentions - try chatting naturally!
- Create dedicated study voice channels for automatic tracking
- Use `/serverinfo` to quickly check server stats
- `/clear` can only delete up to 100 messages at once
- Bot needs proper role hierarchy to moderate members

## 🎮 Example Workflow

1. **Setup your server:**
   ```
   /createvc Study Room
   /createchannel study-chat
   /setup #Study-Room #study-chat
   ```

2. **Moderate as needed:**
   ```
   /timeout @user 10 Spamming
   /muteall #general-vc
   ```

3. **Chat with AI:**
   ```
   @BotName help me understand this topic
   /ask What's the best way to learn programming?
   ```

4. **Track your progress:**
   ```
   [Join voice channel]
   /studytime
   ```

## 📝 Tech Stack

- **Python 3.11** - Programming language
- **discord.py** - Discord bot framework
- **Groq API** - FREE AI (Llama 3.3 70B model)
- **Replit** - Hosting platform

## 🆓 Cost

**Completely FREE!**
- Discord bots are free
- Groq API has a generous free tier
- Replit offers free hosting

## 📄 License

Free to use for personal and community servers!

---

**Made with ❤️ for Discord communities!**

Need help? Use `/help` in Discord or check the troubleshooting section above.
