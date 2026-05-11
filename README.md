# Cortana Bot 🤖
An AI-powered chat assistant and moderation tool for **ElDewrito 0.7.1** dedicated servers.

Players can ask questions directly in game chat and get real-time responses. Cortana also handles server moderation, web search, YouTube link fetching, kill streak announcements, map/gamemode control, a warning system, and more.

---

## Features

- **AI chat** — players ask questions by mentioning Cortana's name or using `!cortana`, `/cortana`, `!ai`, `/ai`, `!bot`, `/bot`
- **Smart web search** — automatically searches when current info is needed (weather, news, scores, etc.) or when explicitly asked
- **YouTube search** — ask for a video and get a direct link in chat
- **Live game context** — knows the current map, mode, scores, players, and who is winning
- **Chat memory** — remembers the last 100 messages for conversational context
- **Permanent memory** — `memory.txt` persists facts between sessions; players can add notes with `!ai remember`
- **Warning system** — warn → kick → 5 minute tempban, persisted to `warnings.json`
- **AI auto-moderation** — detects slurs, spam, and excessive caps automatically
- **Moderator system** — admins can assign moderators persisted to `mods.json`
- **Map control** — change maps via RCON with `!ai map <name>`
- **Gamemode control** — auto-scans `data/game_variants/` folder and loads modes with `!ai mode <name>`
- **Kill streak announcements** — automatic comments at 5, 10, 15, and 20 kill streaks
- **Player join greeting** — welcomes new players automatically
- **Ban system** — permanent bans, temporary bans, auto-enforcement on rejoin, saved to `bans.json`
- **UUID-based admin auth** — admin commands verified by UUID + PrivKey, impossible to spoof
- **Admin/Mod protection** — server owner can never be kicked or banned; mods cannot act against other mods or the owner
- **Multiple AI providers** — Groq → Cerebras → Mistral → OpenRouter with automatic fallback
- **Local LLM support** — toggle an Ollama local model on/off as a fallback or primary
- **Anti-spam** — per-player cooldown and global queue limit; admin exempt from cooldown
- **No personal data in script** — everything sensitive lives in `config.txt`

---

## Requirements

- Windows PC running ElDewrito 0.7.1
- ElDewrito dedicated server (`dedicated_server.bat`)
- Python 3.10 or newer
- At least one free API key (Groq recommended)
- Optional: [Ollama](https://ollama.com/download) for local LLM support

---

## Quick Start

**1. Install Python**

Download from [python.org](https://python.org/downloads). During installation check **"Add Python to PATH"**.

**2. Install dependencies**

```bash
pip install websocket-client requests ddgs
```

**3. Clone or download this repo**

```
CortanaBot/
    cortana_bot.py
    config.txt
    CORTANA_BOT_GUIDE.txt
```

**4. Get a free Groq API key**

Sign up at [console.groq.com](https://console.groq.com), create a key, and copy it.

**5. Edit `config.txt`**

```
GROQ_API_KEY=your-groq-key-here
CEREBRAS_API_KEY=your-cerebras-key-here
MISTRAL_API_KEY=your-mistral-key-here
OPENROUTER_API_KEY=your-openrouter-key-here
RCON_PASSWORD=your-server-rcon-password
RCON_PORT=11776
OWNER_UUID=your-player-uuid-here
OWNER_PRIVKEY=your-privkey-here
```

**Finding your UUID:** Start your server, join it, open `http://localhost:11775` in your browser, find your player entry and copy the `uid` field.

**Finding your PrivKey:** Open `keys.cfg` in your ElDewrito folder, find `Player.PrivKey`, and copy everything **before the first `+`** sign.

**6. Enable RCON in ElDewrito**

Add to `dewrito_prefs.cfg`:
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
| `cortana <question>` | Mention Cortana anywhere in your message |
| `!cortana <question>` | Ask Cortana anything |
| `/cortana <question>` | Same as !cortana |
| `!ai <question>` | Same as !cortana |
| `/ai <question>` | Same as !cortana |
| `!bot <question>` | Same as !cortana |
| `/bot <question>` | Same as !cortana |
| `!ai remember <text>` | Save a note to permanent memory |

---

## Moderator Commands

Moderators are assigned by the server owner. They cannot act against the owner or other moderators.

| Command | Description |
|---|---|
| `!ai on` / `!ai off` | Enable or disable the bot |
| `!ai status` | Show bot status, provider, queue, automod state |
| `!ai clear` | Reset all player cooldowns |
| `!ai cooldown <seconds>` | Change per-player cooldown |
| `!ai automod on/off` | Toggle AI auto-moderation |
| `!ai map <name>` | Change the map |
| `!ai mode <name>` | Change the gamemode |
| `!ai modes` | List all available gamemodes |
| `!ai start` | Start the game |
| `!ai kick <name>` | Kick a player |
| `!ai ban <name>` | Permanently ban a player |
| `!ai tempban <name> <minutes>` | Temporarily ban a player |
| `!ai unban <name>` | Remove a ban |
| `!ai banlist` | Show active bans |
| `!ai warn <name> <reason>` | Warn a player |
| `!ai warnings <name>` | Show warning count for a player |
| `!ai clearwarnings <name>` | Clear all warnings for a player |

---

## Admin Commands

Admin commands are verified by UUID + PrivKey and can only be used by the server owner.

| Command | Description |
|---|---|
| `!ai provider <name\|auto>` | Switch AI provider |
| `!ai local on/off` | Enable/disable local Ollama model |
| `!ai memory on/off` | Enable/disable permanent memory |
| `!ai forget` | Clear all permanent memory |
| `!ai addmod <name>` | Add a moderator (player must be in server) |
| `!ai removemod <name>` | Remove a moderator |
| `!ai modlist` | List all moderators |

---

## Warning System

Warnings persist across sessions in `warnings.json`.

| Threshold | Action |
|---|---|
| 1–2 warnings | Player is notified with warnings remaining |
| 3rd warning | Player is kicked |
| 4th+ warning | Player is temp banned for 5 minutes |

Warnings can be issued manually by mods/admin with `!ai warn <name> <reason>`, or automatically by the AI auto-moderation system (slurs, spam, excessive caps).

---

## AI Providers

The bot uses a fallback chain — if the primary provider fails or hits its rate limit, it automatically switches to the next one.

| Provider | Tier | Notes |
|---|---|---|
| [Groq](https://console.groq.com) | Free | Primary — fast, recommended |
| [Cerebras](https://cloud.cerebras.ai) | Free | First fallback |
| [Mistral](https://console.mistral.ai) | Free | Second fallback — 1B tokens/month |
| [OpenRouter](https://openrouter.ai) | Free | Third fallback — auto-selects best free model |
| Local (Ollama) | Free | Optional — toggle with `!ai local on/off` |

Switch providers manually with:
```
!ai provider groq
!ai provider cerebras
!ai provider mistral
!ai provider openrouter
!ai provider auto
```

---

## Local LLM Setup (Optional)

1. Download [Ollama](https://ollama.com/download) and install it
2. Pull the recommended model:
```bash
ollama pull qwen2.5:1.5b
```
3. Make sure Ollama is running (check system tray)
4. In game chat: `!ai local on`

The local model runs entirely on your machine — no API key needed, works offline, and uses ~1GB RAM.

---

## Map & Gamemode Control

The bot auto-scans your `data\game_variants\` folder at startup. Whatever folders exist there become available as modes.

```
!ai map Valhalla
!ai map Guardian
!ai mode MLG TS 8
!ai mode Infection V1
!ai modes              ← lists all available modes
!ai start              ← starts the game
```

---

## Permanent Memory

Cortana remembers things between sessions via `memory.txt`.

- **Players** can add notes: `!ai remember Sirius always camps the sniper tower`
- **Admin** can clear all memory: `!ai forget`
- **Admin** can toggle memory on/off: `!ai memory on/off`

Memory is included in every AI response as context, so Cortana will naturally reference it when relevant.

---

## File Structure

```
CortanaBot/
    cortana_bot.py          Main bot script
    config.txt              API keys, RCON settings, owner UUID and PrivKey
    bans.json               Ban list (auto-created)
    warnings.json           Warning records (auto-created)
    mods.json               Moderator list (auto-created)
    memory.txt              Permanent memory (auto-created)
    CORTANA_BOT_GUIDE.txt   Full installation and usage guide
```

---

## Configuration Reference

| Key | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key |
| `CEREBRAS_API_KEY` | Cerebras API key (optional) |
| `MISTRAL_API_KEY` | Mistral API key (optional) |
| `OPENROUTER_API_KEY` | OpenRouter API key (optional) |
| `RCON_PASSWORD` | Must match `Server.RconPassword` in dewrito_prefs.cfg |
| `RCON_PORT` | RCON port — almost always `11776` for dedicated servers |
| `OWNER_UUID` | Your player UUID — no `0x` prefix |
| `OWNER_PRIVKEY` | Your PrivKey from keys.cfg — everything before the first `+` |

---

## Troubleshooting

**Connection refused**
→ Make sure the dedicated server is running before starting the bot.
→ Use a dedicated server, not a listen server.

**Bot connects but no chat messages**
→ Add `Server.SendChatToRconClients "1"` to `dewrito_prefs.cfg` and restart.

**Admin commands not working**
→ Check `OWNER_UUID` and `OWNER_PRIVKEY` in `config.txt` match your actual values.

**API errors / rate limits**
→ The bot automatically falls back to the next provider. Add more API keys for more fallbacks.

**Local model not responding**
→ Make sure Ollama is running (check system tray) and the model is pulled.

**!ai mode crashes the server**
→ Make sure the variant folder exists in `data\game_variants\`. Use `!ai modes` to see what's available.

---

## License

MIT — do whatever you want with it.

---

## Credits

Built for the ElDewrito community.
Powered by [Groq](https://groq.com), [Cerebras](https://cerebras.ai), [Mistral](https://mistral.ai), [OpenRouter](https://openrouter.ai), and [Ollama](https://ollama.com).
