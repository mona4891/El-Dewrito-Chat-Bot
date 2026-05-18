# Cortana Bot 🤖
> AI-powered chat assistant and moderation tool for **ElDewrito 0.7.1** dedicated servers

Players can ask questions directly in game chat and get real-time AI responses. Cortana also handles full server moderation, web search, YouTube link fetching, kill streak announcements, map/gamemode control, a warning system, a Dewritos credit economy, a betting system, a Discord bridge, player stats tracking, match summaries, TTS voice, map rotation, AFK detection, AI provider load balancing, automatic backups, and more.

---

## Features

- **AI chat** — players trigger Cortana by mentioning her name or using `!cortana`, `/cortana`, `!ai`, `/ai`, `!bot`, `/bot`
- **Smart web search** — automatically searches for current info (weather, news, scores) or when explicitly asked
- **YouTube search** — ask for a video, get a direct link in chat
- **Live game context** — knows the current map, mode, scores, players, and who is winning
- **Chat memory** — remembers the last 100 messages for conversational context
- **Permanent memory** — `memory.txt` persists facts between sessions; players can add notes with `!ai remember`
- **Warning system** — warn → kick → 5-minute tempban, persisted to `warnings.json`
- **AI auto-moderation** — automatically detects slurs, spam, and excessive caps
- **Moderator system** — admins can assign moderators, persisted to `mods.json`
- **Map control** — change maps via RCON with `!ai map <name>`
- **Gamemode control** — auto-scans `data/game_variants/` and loads modes with `!ai mode <name>`
- **Kill streak announcements** — automatic comments at 5, 10, 15, and 20 kill streaks
- **Player join greeting** — welcomes new players automatically
- **Ban system** — permanent bans, temporary bans, auto-enforcement on rejoin, saved to `bans.json`
- **UUID-based admin auth** — admin commands verified by UUID + PrivKey, impossible to spoof
- **Admin/Mod protection** — owner can never be kicked or banned; mods cannot act against other mods or the owner
- **Multiple AI providers** — Groq → Cerebras → Mistral → OpenRouter with automatic fallback
- **Local LLM support** — toggle an Ollama model on/off as a fallback or primary
- **Anti-spam** — per-player cooldown and global queue limit; admin exempt from cooldown
- **No personal data in script** — all sensitive values live in `config.txt`
- 🎮 **Dewritos Credit System** — earn currency by playing matches, getting first blood, and winning games
- 🎲 **Betting System** — bet Dewritos on match winners, top killers, or winning teams
- 🔄 **Map Rotation** — automatic map/mode cycling after each match via `rotation.json`
- 🎯 **Match Summaries** — automatic post-match stats with MVP and most kills/deaths
- 🎤 **Text-to-Speech (TTS)** — Cortana speaks messages using Google TTS
- 📊 **Player Stats** — persistent K/D, wins, matches, and leaderboards
- 🔗 **Discord Bridge** — bidirectional chat between game and a Discord channel
- ⚖️ **Server Voting Control** — configure voting system, options, revotes, and pass percentage
- 💾 **Backup & Restore** — automatic daily backups and manual backup/restore commands
- 📝 **Comprehensive Logging** — rotating logs with ban/warning history

---

## Requirements

- Windows PC running **ElDewrito 0.7.1**
- ElDewrito dedicated server (`dedicated_server.bat`)
- Python 3.10 or newer
- At least one free API key (Groq recommended)
- *(Optional)* Ollama for local LLM support
- *(Optional)* `discord.py` for the Discord bridge

---

## Quick Start

### 1. Install Python
Download from [python.org](https://python.org). During installation, check **"Add Python to PATH"**.

### 2. Install dependencies
```bash
pip install websocket-client requests ddgs pygame gtts

# Optional — Discord bridge:
pip install discord.py
```

### 3. Clone or download this repo
```
CortanaBot/
    cortana_bot.py
    config.txt
    rotation.json           # Map rotation (optional, auto-created)
    CORTANA_BOT_GUIDE.txt
```

### 4. Get a free Groq API key
Sign up at [console.groq.com](https://console.groq.com), create a key, and copy it.

### 5. Edit `config.txt`
```
GROQ_API_KEY=your-groq-key-here
CEREBRAS_API_KEY=your-cerebras-key-here
MISTRAL_API_KEY=your-mistral-key-here
OPENROUTER_API_KEY=your-openrouter-key-here
RCON_PASSWORD=your-server-rcon-password
RCON_PORT=11776
OWNER_UUID=your-player-uuid-here
OWNER_PRIVKEY=your-privkey-here

# Discord Bridge (optional)
DISCORD_WEBHOOK_URL=your-webhook-url-here
DISCORD_BOT_TOKEN=your-bot-token-here
DISCORD_CHANNEL_ID=your-channel-id-here
```

> **Finding your UUID:** Start your server, join it, open `http://localhost:11775` in your browser, find your player entry, and copy the `uid` field.

> **Finding your PrivKey:** Open `keys.cfg` in your ElDewrito folder, find `Player.PrivKey`, and copy everything before the first `+` sign.

### 6. (Optional) Create `rotation.json` for map rotation
```json
[
    {"map": "Guardian", "mode": "MLG TS 8"},
    {"map": "Valhalla", "mode": "MLG FFA 8"},
    {"map": "The Pit", "mode": "Slayer Pro"}
]
```

### 7. Enable RCON in ElDewrito
Add to `dewrito_prefs.cfg`:
```
Server.RconPassword "yourpassword"
Server.SendChatToRconClients "1"
```

### 8. Start the dedicated server, then run the bot
```bash
python cortana_bot.py
```

---

## Commands

### Player Commands
| Command | Description |
|---|---|
| `cortana <question>` | Mention Cortana anywhere in your message |
| `!cortana <question>` | Ask Cortana anything |
| `/cortana <question>` | Same as `!cortana` |
| `!ai <question>` | Same as `!cortana` |
| `!bot <question>` | Same as `!cortana` |
| `!ai remember <text>` | Save a note to permanent memory |
| `!ai dewritos` / `!ai balance` | Check your Dewritos credit balance |
| `!ai bet <amount> on winner <name>` | Bet Dewritos on a player to win |
| `!ai bet <amount> on topkiller <name>` | Bet Dewritos on the top killer |
| `!ai bet <amount> on team <color>` | Bet Dewritos on a team (red/blue/orange/green/etc.) |
| `!ai leaderboard` / `!ai topdewritos` | Show top 5 richest players |
| `!ai mystats` | View your personal K/D, wins, and matches |

### Moderator Commands
Moderators are assigned by the server owner and cannot act against the owner or other moderators.

| Command | Description |
|---|---|
| `!ai on` / `!ai off` | Enable or disable the bot |
| `!ai status` | Show bot status, provider, queue, and automod state |
| `!ai clear` | Reset all player cooldowns |
| `!ai cooldown <seconds>` | Change per-player cooldown |
| `!ai automod on/off` | Toggle AI auto-moderation |
| `!ai map <name>` | Change the map |
| `!ai maps` | List all available maps |
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
| `!ai mute <name>` / `!ai unmute <name>` | Mute or unmute a player |
| `!ai pm <name> <message>` | Send a private message to a player |
| `!ai say <message>` | Make Cortana speak a message via TTS |
| `!ai voice on/off` | Enable/disable TTS voice responses |
| `!ai rotation on/off` | Enable/disable map rotation |
| `!ai nextmap` | Advance to the next map in rotation |
| `!ai shufflerotation` | Randomize map rotation order |
| `!ai servername <name>` | Change the server name |
| `!ai serverpassword <pass>` | Set server password (`clear` to remove) |
| `!ai teams <number>` | Set number of teams |
| `!ai votingon` / `!ai votingoff` | Enable/disable map voting |
| `!ai votingsystem <0-3>` | Set voting system (0=Disabled, 1=Standard, 2=Instant, 3=Majority) |
| `!ai votingoptions <number>` | Set number of voting options |
| `!ai revotes <number>` | Set number of revotes allowed |
| `!ai votepass <percentage>` | Set vote pass percentage |
| `!ai reloadvoting` | Reload voting JSON configuration |
| `!ai afk on/off` | Enable/disable AFK detection |
| `!ai loadbalance on/off` | Enable/disable API provider load balancing |
| `!ai local on/off` | Toggle local Ollama model |
| `!ai provider <name\|auto>` | Switch AI provider |
| `!ai stats <name>` | View any player's stats |
| `!ai gamestatus` | Show current game state from API |
| `!ai reload` | Reload configuration from files |
| `!ai forget` | Clear permanent memory |
| `!ai memory on/off` | Toggle permanent memory |
| `!ai modlist` | List all moderators |

### Admin Commands
Admin commands are verified by UUID + PrivKey and can only be used by the server owner.

| Command | Description |
|---|---|
| `!ai addmod <name>` | Add a moderator (player must be in server) |
| `!ai removemod <name>` | Remove a moderator |
| `!ai backup` | Create a manual backup of all data |
| `!ai backuplist` | List all available backups |
| `!ai restore <name>` | Restore from a backup |
| `!ai discord on/off` | Enable/disable Discord bridge |
| `!ai debugall` | Show detailed debug information |

---

## Dewritos Credit System 🎮

Cortana features a built-in in-game economy.

**Earning Dewritos:**
- New players start with **100 Dewritos**
- Match win → **+50 Dewritos**
- Match participation → **+10 Dewritos**
- First blood → **+5 Dewritos**

**Betting** — wager Dewritos on match outcomes before the game starts. All bets resolve automatically at match end.

| Bet Type | Description | Payout |
|---|---|---|
| `winner` | Bet on a specific player to win | 2x |
| `topkiller` | Bet on the player with most kills | 2x |
| `team` | Bet on a winning team color | 2x |

*Minimum bet: 10 Dewritos*

---

## AI Providers

The bot uses a fallback chain — if the primary provider fails or hits a rate limit, it automatically switches to the next one.

| Provider | Tier | Notes |
|---|---|---|
| Groq | Free | Primary — fast, recommended |
| Cerebras | Free | First fallback |
| Mistral | Free | Second fallback — 1B tokens/month |
| OpenRouter | Free | Third fallback — auto-selects best free model |
| Local (Ollama) | Free | Optional — toggle with `!ai local on/off` |

Switch providers manually:
```
!ai provider groq
!ai provider cerebras
!ai provider mistral
!ai provider openrouter
!ai provider auto
```

---

## Local LLM Setup (Optional)

1. Download and install [Ollama](https://ollama.com)
2. Pull a model:
```bash
# Recommended
ollama pull huihui_ai/gemma3-abliterated:1b

# Lighter alternative
ollama pull qwen2.5:1.5b
```
3. Make sure Ollama is running (check system tray)
4. In game: `!ai local on`

The local model runs entirely on your machine — no API key needed, works offline, uses ~1GB RAM.

---

## Discord Bridge 🔗

Bridge chat between your game server and a Discord channel.

**Setup:**
1. Create a Discord webhook (Server Settings → Integrations → Webhooks)
2. *(Optional)* Create a Discord bot for bidirectional chat
3. Add to `config.txt`:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_CHANNEL_ID=123456789012345678
```
4. Enable in-game: `!ai discord on`

**Features:**
- Game → Discord: all game chat appears in Discord via webhook
- Discord → Game: Discord messages appear in game (requires bot token)
- Match summaries posted to Discord automatically

---

## Map & Gamemode Control

The bot auto-scans your `data\game_variants\` folder at startup. Whatever folders exist there become available as modes.

```
!ai map Valhalla
!ai mode MLG TS 8
!ai modes          ← lists all available modes
!ai maps           ← lists all available maps
!ai start          ← starts the game
```

**Mod support** — Cortana detects modded maps and automatically loads the required `.pak` files:

| Mod | File |
|---|---|
| Customization++ | `customization_173b1d9d_v4_5.pak` |
| Halo 3 Pack | `halo_3_pack_39106b4c_v2_3.pak` |
| KN Map Pack 1 | `kn_map_pack_1_e61a5929_v1_6.pak` |
| KN Map Pack 2 | `kn_map_pack_2_0a671a0e_v1_6.pak` |
| H3EK | `H3EK_CUSTOM_Maps.pak` |

---

## Warning System

Warnings persist across sessions in `warnings.json`.

| Threshold | Action |
|---|---|
| 1–2 warnings | Player notified with warnings remaining |
| 3rd warning | Player is kicked |
| 4th+ warning | Player is temp-banned for 5 minutes |

Warnings can be issued manually by mods/admin with `!ai warn <name> <reason>`, or automatically by AI auto-moderation (slurs, spam, excessive caps).

---

## Logging System 📝

| File | Contents |
|---|---|
| `logs/cortana.log` | Main bot log (rotating, 5MB max, 5 backups) |
| `ban_log.txt` | All ban/unban actions with timestamps |
| `warning_log.txt` | All warning actions with timestamps |

---

## File Structure

```
CortanaBot/
    cortana_bot.py          Main bot script
    config.txt              API keys, RCON settings, owner UUID and PrivKey
    rotation.json           Map rotation configuration (optional)
    bans.json               Ban list (auto-created)
    warnings.json           Warning records (auto-created)
    mods.json               Moderator list (auto-created)
    stats.json              Player statistics (auto-created)
    dewritos.json           Dewritos credit balances (auto-created)
    bets.json               Active bets (auto-created)
    match_history.json      Match results history (auto-created)
    memory.txt              Permanent memory (auto-created)
    ban_log.txt             Ban action log (auto-created)
    warning_log.txt         Warning action log (auto-created)
    backups/                Automatic backup folder
    logs/                   Rotating log files
    CORTANA_BOT_GUIDE.txt   Full installation and usage guide
```

---

## Configuration Reference

### `config.txt`
| Key | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key |
| `CEREBRAS_API_KEY` | Cerebras API key (optional) |
| `MISTRAL_API_KEY` | Mistral API key (optional) |
| `OPENROUTER_API_KEY` | OpenRouter API key (optional) |
| `RCON_PASSWORD` | Must match `Server.RconPassword` in `dewrito_prefs.cfg` |
| `RCON_PORT` | RCON port — almost always `11776` for dedicated servers |
| `OWNER_UUID` | Your player UUID — no `0x` prefix |
| `OWNER_PRIVKEY` | Your PrivKey from `keys.cfg` — everything before the first `+` |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL for game → Discord |
| `DISCORD_BOT_TOKEN` | Discord bot token for Discord → game |
| `DISCORD_CHANNEL_ID` | Discord channel ID for bidirectional bridge |

### `cortana_bot.py` script variables
| Variable | Default | Description |
|---|---|---|
| `PLAYER_COOLDOWN` | `30` | Seconds between AI requests per player |
| `MAX_QUEUE_SIZE` | `3` | Maximum concurrent AI requests |
| `CHAT_MEMORY_SIZE` | `100` | Number of chat messages to remember |
| `AFK_TIMEOUT_MINUTES` | `0` | Minutes before AFK kick (0 = disabled) |
| `ANNOUNCEMENT_INTERVAL` | `600` | Seconds between scheduled announcements |
| `ANNOUNCEMENTS` | `[]` | List of messages to announce |
| `WARN_KICK_THRESHOLD` | `3` | Warnings before kick |
| `WARN_TEMPBAN_DURATION` | `5` | Minutes for tempban after 4+ warnings |
| `PROVIDER_FAILURE_THRESHOLD` | `3` | Failures before marking a provider dead |
| `PROVIDER_COOLDOWN_SECONDS` | `60` | Seconds before retrying a failed provider |
| `MAX_BACKUPS` | `30` | Number of backups to keep (0 = unlimited) |

---

## Troubleshooting

**Connection refused**
→ Make sure the dedicated server is running before starting the bot.
→ Use a dedicated server, not a listen server.

**Bot connects but no chat messages**
→ Add `Server.SendChatToRconClients "1"` to `dewrito_prefs.cfg` and restart.

**Admin commands not working**
→ Check that `OWNER_UUID` and `OWNER_PRIVKEY` in `config.txt` match your actual values.

**API errors / rate limits**
→ The bot automatically falls back to the next provider. Add more API keys for more fallbacks.
→ Enable load balancing: `!ai loadbalance on`

**Local model not responding**
→ Make sure Ollama is running (check system tray) and the model is pulled.

**`!ai mode` crashes the server**
→ Make sure the variant folder exists in `data\game_variants\`. Use `!ai modes` to see what's available.

**Discord bridge not working**
→ Install discord.py: `pip install discord.py`
→ Verify webhook URL and bot token are correct, then enable with `!ai discord on`

**TTS not working**
→ Install pygame and gtts: `pip install pygame gtts`
→ Enable with `!ai voice on`

**Dewritos or betting not working**
→ Player stats must be enabled (`stats_enabled = True`)
→ Players must join while the bot is running to initialize their balance

**Backup/restore fails**
→ Check that the backup folder exists and has write permissions
→ Max 30 backups kept by default (configurable via `MAX_BACKUPS`)

---

## License

MIT — do whatever you want with it.

---

## Credits

Built for the ElDewrito community.
Powered by [Groq](https://groq.com), [Cerebras](https://cerebras.ai), [Mistral](https://mistral.ai), [OpenRouter](https://openrouter.ai), and [Ollama](https://ollama.com).
