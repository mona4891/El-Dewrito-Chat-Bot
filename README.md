# El-Dewrito-Chat-Bot
El Dewrito Chat Bot an AI-powered chat assistant and moderation tool for **ElDewrito 0.7.1** dedicated servers🤖.

Players can ask questions directly in game chat and receive real-time responses. The bot also handles server moderation, web search, YouTube link fetching, kill streak announcements, and more.

---

## Features

- **AI chat** — players ask questions in game chat using `@cortana`, `@ai`, `!ai`, `/ai`, or `@bot`
- **Web search** — Cortana can search the internet and return links on demand
- **YouTube search** — ask for a video and get a direct link in chat
- **Live game context** — Cortana knows the current map, mode, scores, and who is winning
- **Chat memory** — remembers the last 50 messages for conversational context
- **Kill streak announcements** — automatic comments at 5, 10, 15, and 20 kill streaks
- **Player join greeting** — welcomes new players automatically
- **Ban system** — permanent bans, temporary bans, and auto-enforcement on rejoin
- **Admin commands** — kick, ban, tempban, unban, cooldown control, provider switching
- **UUID-based admin auth** — admin commands are verified by UUID, not just name (spoof-proof)
- **Admin protection** — the server owner can never be kicked or banned by the bot
- **Multiple AI providers** — Groq (primary) → Cerebras → Mistral with automatic fallback
- **Anti-spam** — per-player cooldown and global queue limit
- **No personal data in script** — everything sensitive lives in `config.txt`

---

## Requirements

- Windows PC running ElDewrito 0.7.1
- ElDewrito dedicated server (`dedicated_server.bat`)
- Python 3.10 or newer
- At least one free API key (Groq recommended)

---

## Quick Start

**1. Install Python**

Download from [python.org](https://python.org/downloads). During installation, check **"Add Python to PATH"**.

**2. Install dependencies**

```bash
pip install websocket-client requests duckduckgo-search
```

**3. Clone or download this repo**

```
CortanaBot/
    cortana_bot.py
    config.txt
    CORTANA_BOT_GUIDE.txt
```

**4. Get a free Groq API key**

Sign up at [console.groq.com](https://console.groq.com), create an API key, and copy it.

**5. Edit `config.txt`**

```
GROQ_API_KEY=your-groq-key-here
CEREBRAS_API_KEY=your-cerebras-key-here
MISTRAL_API_KEY=your-mistral-key-here
RCON_PASSWORD=your-server-rcon-password
RCON_PORT=11776
OWNER_UUID=your-player-uuid-here
```

To find your UUID, start your server, join it, and open `http://localhost:11775` in your browser. Find your player entry and copy the `uid` field.

**6. Enable RCON in ElDewrito**

Add these lines to `dewrito_prefs.cfg`:
```
Server.RconPassword "yourpassword"
Server.SendChatToRconClients "1"
```

**7. Start the dedicated server, then run the bot**

```bash
python cortana_bot.py
```

---

## Player Commands

| Command | Description |
|---|---|
| `@cortana <question>` | Ask Cortana anything |
| `@ai <question>` | Same as @cortana |
| `!ai <question>` | Same as @cortana |
| `/ai <question>` | Same as @cortana |
| `@bot <question>` | Same as @cortana |

**Examples:**
```
@cortana what is the best weapon in Halo 3?
@ai find me the Halo theme on YouTube
@cortana who is winning right now?
@ai search for ElDewrito download
```

---

## Admin Commands

Admin commands are verified by UUID and can only be used by the server owner.

| Command | Description |
|---|---|
| `!ai on` | Enable the bot |
| `!ai off` | Disable the bot |
| `!ai status` | Show status, active provider, cooldown, queue |
| `!ai clear` | Reset all player cooldowns |
| `!ai cooldown <seconds>` | Change per-player cooldown |
| `!ai kick <name>` | Kick a player |
| `!ai ban <name>` | Permanently ban a player |
| `!ai tempban <name> <minutes>` | Temporarily ban a player |
| `!ai unban <name>` | Remove a ban |
| `!ai banlist` | Show active bans |
| `!ai provider groq` | Force Groq as AI provider |
| `!ai provider cerebras` | Force Cerebras as AI provider |
| `!ai provider mistral` | Force Mistral as AI provider |
| `!ai provider auto` | Return to automatic fallback mode |

---

## AI Providers

The bot uses a fallback chain — if the primary provider fails or hits its rate limit, it automatically switches to the next one without interrupting service.

| Provider | Tier | Notes |
|---|---|---|
| [Groq](https://console.groq.com) | Free | Primary — fast, recommended |
| [Cerebras](https://cloud.cerebras.ai) | Free | First fallback |
| [Mistral](https://console.mistral.ai) | Free | Second fallback — 1B tokens/month |

---

## Ban System

Bans are stored in `bans.json` (created automatically on first ban) and include:
- Player name
- Player UUID
- Player IP address
- Reason
- Date and time of ban
- Expiry time (for temporary bans)

Banned players are automatically kicked if they rejoin the server.

---

## File Structure

```
CortanaBot/
    cortana_bot.py          Main bot script
    config.txt              API keys, RCON settings, owner UUID
    bans.json               Ban list (auto-created)
    CORTANA_BOT_GUIDE.txt   Full installation and usage guide
```

---

## Configuration Reference

| Key | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key |
| `CEREBRAS_API_KEY` | Cerebras API key (optional) |
| `MISTRAL_API_KEY` | Mistral API key (optional) |
| `RCON_PASSWORD` | Must match `Server.RconPassword` in dewrito_prefs.cfg |
| `RCON_PORT` | RCON port — almost always `11776` for dedicated servers |
| `OWNER_UUID` | Your player UUID — no `0x` prefix |

---

## Troubleshooting

**Connection refused**
→ Make sure the dedicated server is running before starting the bot.
→ Make sure you are running a dedicated server, not a listen server.

**Bot connects but no chat messages**
→ Add `Server.SendChatToRconClients "1"` to `dewrito_prefs.cfg` and restart the server.

**Admin commands not working**
→ Check that `OWNER_UUID` in `config.txt` matches your actual UUID from `http://localhost:11775`.

**API errors**
→ Check your API key in `config.txt`. If Groq is rate limited it will fall back automatically.

---

## License

MIT — do whatever you want with it.

---

## Credits

Built for the ElDewrito community. Powered by [Groq](https://groq.com), [Cerebras](https://cerebras.ai), and [Mistral](https://mistral.ai).

