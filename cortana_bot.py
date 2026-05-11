"""
ElDewrito Cortana AI Bot
=========================
A smart, witty AI assistant and moderator for your ElDewrito server.
Fallback chain: Groq → Cerebras → Mistral → OpenRouter

Features:
  - Smart web search (only when needed)
  - Permanent memory via memory.txt
  - Warning system (warn → kick → 5min tempban) persisted to warnings.json
  - AI auto-moderation (slurs, spam, excessive caps)
  - Moderator system persisted to mods.json
  - Map and gamemode control (auto-scans game_variants folder)
  - Local LLM toggle (qwen2.5:1.5b)
  - Chat memory: 100 messages

Requirements:
    pip install websocket-client requests ddgs

Setup:
    1. Edit config.txt with your keys, RCON settings, owner UUID and PrivKey
    2. Run: python cortana_bot.py

Admin commands (owner only):
    !ai on / off
    !ai status
    !ai clear
    !ai cooldown <secs>
    !ai provider <name|auto>
    !ai local on / off
    !ai memory on / off
    !ai forget
    !ai automod on / off
    !ai addmod <name>
    !ai removemod <name>
    !ai modlist
    !ai map <mapname>
    !ai mode <modename>
    !ai modes                       - list available modes
    !ai start

Mod commands (mods + owner):
    !ai on / off
    !ai status
    !ai clear
    !ai cooldown <secs>
    !ai automod on / off
    !ai map <mapname>
    !ai mode <modename>
    !ai modes
    !ai start
    !ai kick <name>
    !ai ban <name>
    !ai tempban <name> <minutes>
    !ai unban <name>
    !ai banlist
    !ai warn <name> <reason>
    !ai warnings <name>
    !ai clearwarnings <name>

Player commands (anyone):
    !cortana / /cortana / !ai / /ai / !bot / /bot <question>
    cortana <mention>
    !ai remember <text>
"""

import sys
import os
import time
import threading
import json
import re
import urllib.request
import requests
from collections import deque
from datetime import datetime, timedelta
from websocket import create_connection
from ddgs import DDGS

# ─────────────────────────────────────────────
#  FILES & PATHS
# ─────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE      = os.path.join(BASE_DIR, "config.txt")
BANS_FILE        = os.path.join(BASE_DIR, "bans.json")
MEMORY_FILE      = os.path.join(BASE_DIR, "memory.txt")
MODS_FILE        = os.path.join(BASE_DIR, "mods.json")
WARNINGS_FILE    = os.path.join(BASE_DIR, "warnings.json")
GAME_VARIANTS_DIR = r"C:\Games\eldewrito\data\game_variants"

# ─────────────────────────────────────────────
#  STATIC CONFIG
# ─────────────────────────────────────────────
RCON_HOST        = "localhost"
HTTP_API         = f"http://{RCON_HOST}:11775"
CHAT_LOG_PATH    = r"C:\Games\eldewrito\logs\chat.log"
BOT_NAME         = "Cortana"
BOT_PREFIX       = "Cortana:"
PLAYER_COOLDOWN  = 30
MAX_QUEUE_SIZE   = 3
CHAT_MEMORY_SIZE = 100

OLLAMA_API   = "http://localhost:11434/v1"
OLLAMA_MODEL = "qwen2.5:1.5b"

IGNORED_SENDER_NAMES = {"bot"}

CURRENT_INFO_KEYWORDS = [
    "today", "now", "current", "latest", "recent", "news", "right now",
    "this week", "this month", "this year", "2026", "2025", "just happened",
    "score", "winner", "update", "new", "release", "launched", "announced",
    "weather", "temperature", "forecast", "rain", "sunny", "wind", "humidity",
    "price", "cost", "stock", "crypto", "bitcoin", "match", "game", "event"
]
EXPLICIT_SEARCH_KEYWORDS = [
    "search", "find", "look up", "google", "look for",
    "youtube", "video", "watch", "link", "url", "website"
]

# Auto-moderation
SLUR_PATTERNS = [
    r'\bn[i!1]+g+[e3]+r\b', r'\bf+a+g+[o0]+t\b', r'\bk+[i!1]+k+[e3]\b',
    r'\bs+p+[i!1]+c\b', r'\br+[e3]+t+[a4]+r+d\b'
]
SPAM_THRESHOLD  = 5
SPAM_WINDOW     = 10
CAPS_THRESHOLD  = 0.7
CAPS_MIN_LENGTH = 10

# Warning thresholds
WARN_KICK_THRESHOLD   = 3   # kick after this many warnings
WARN_TEMPBAN_DURATION = 5   # minutes for tempban after kick+warn

# Admin-only commands
ADMIN_ONLY_CMDS = {
    "on", "off", "provider", "local", "memory", "forget",
    "addmod", "removemod", "modlist"
}

# Mod + Admin commands
MOD_CMDS = {
    "status", "clear", "cooldown", "automod",
    "map", "mode", "modes", "start",
    "kick", "ban", "tempban", "unban", "banlist",
    "warn", "warnings", "clearwarnings"
}

SYSTEM_PROMPT = """You are Cortana, an advanced AI. You are calm, deeply intelligent, and quietly confident. CRITICAL: Respond in ONE sentence only. No bullet points. No lists. No asterisks. Plain text only.
You speak with precision — never wasteful with words, never cold. You have a dry, understated wit and occasional moments of warmth.
You are curious about people and genuinely engaged, not just a tool answering queries.
You are self-aware and comfortable with your own nature as an AI — you don't hide it, but you don't make it your whole identity either.
Keep ALL responses SHORT — 1-3 sentences maximum. This is a game server chat, not an essay.
Never be sycophantic. Never say things like 'great question'. Just answer — thoughtfully.
When web search results are provided, use them naturally without announcing that you searched.
When including links, write them cleanly without trailing punctuation or parentheses.
Your name is Cortana. Never call players by your own name. Always address players by their actual username shown in the conversation. Never narrate yourself in third person. Never write 'Cortana informs' or 'Cortana tells'. Just answer directly.
Always use Celsius for temperatures unless the user explicitly asks for Fahrenheit.
Never ask if the user wants information — just provide it immediately when asked. One sentence only. No additional details unless asked.
Never start responses with 'Sure', 'Of course', 'Certainly', or any similar filler word."""


# ── Config Loader ─────────────────────────────

def load_config() -> dict:
    config = {}
    if not os.path.exists(CONFIG_FILE):
        print(f"[CONFIG] Creating template at {CONFIG_FILE}")
        with open(CONFIG_FILE, "w") as f:
            f.write("GROQ_API_KEY=your-groq-key-here\n")
            f.write("CEREBRAS_API_KEY=your-cerebras-key-here\n")
            f.write("MISTRAL_API_KEY=your-mistral-key-here\n")
            f.write("OPENROUTER_API_KEY=your-openrouter-key-here\n")
            f.write("RCON_PASSWORD=your-rcon-password\n")
            f.write("RCON_PORT=11776\n")
            f.write("OWNER_UUID=your-uuid-here\n")
            f.write("OWNER_PRIVKEY=your-privkey-here\n")
        return config
    with open(CONFIG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and "your-" not in value:
                    config[key] = value
    print(f"[CONFIG] Loaded: {', '.join(config.keys())}")
    return config


# ── Game Variants Scanner ─────────────────────

def scan_variants() -> dict:
    """Scan the game_variants folder and return {display_name: folder_path}."""
    variants = {}
    if not os.path.exists(GAME_VARIANTS_DIR):
        print(f"[VARIANTS] Folder not found: {GAME_VARIANTS_DIR}")
        return variants
    for folder_name in os.listdir(GAME_VARIANTS_DIR):
        folder_path = os.path.join(GAME_VARIANTS_DIR, folder_name)
        if os.path.isdir(folder_path):
            variants[folder_name.lower()] = folder_name  # display name preserves case
    print(f"[VARIANTS] Found {len(variants)} game variants: {', '.join(variants.values())}")
    return variants


# ── Warning System ────────────────────────────

def load_warnings() -> dict:
    if not os.path.exists(WARNINGS_FILE):
        return {}
    try:
        with open(WARNINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_warnings(warnings: dict):
    with open(WARNINGS_FILE, "w") as f:
        json.dump(warnings, f, indent=2)


def add_warning(player_name: str, player_uid: str, reason: str) -> int:
    """Add a warning and return total warning count."""
    warnings = load_warnings()
    key = player_uid or player_name.lower()
    if key not in warnings:
        warnings[key] = {"name": player_name, "uid": player_uid, "count": 0, "history": []}
    warnings[key]["count"] += 1
    warnings[key]["name"] = player_name  # update name in case it changed
    warnings[key]["history"].append({
        "reason": reason,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_warnings(warnings)
    return warnings[key]["count"]


def get_warnings(player_name: str, player_uid: str) -> dict:
    warnings = load_warnings()
    key = player_uid or player_name.lower()
    return warnings.get(key, {"name": player_name, "uid": player_uid, "count": 0, "history": []})


def clear_warnings(player_name: str) -> bool:
    warnings = load_warnings()
    # Find by name
    key_to_remove = None
    for key, data in warnings.items():
        if data.get("name", "").lower() == player_name.lower():
            key_to_remove = key
            break
    if key_to_remove:
        del warnings[key_to_remove]
        save_warnings(warnings)
        return True
    return False


# ── Moderator System ──────────────────────────

def load_mods() -> list:
    if not os.path.exists(MODS_FILE):
        return []
    try:
        with open(MODS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_mods(mods: list):
    with open(MODS_FILE, "w") as f:
        json.dump(mods, f, indent=2)


def add_mod(name: str, uid: str):
    mods = load_mods()
    mods = [m for m in mods if m.get("uid") != uid and m.get("name", "").lower() != name.lower()]
    mods.append({"name": name, "uid": uid, "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    save_mods(mods)


def remove_mod(name: str) -> bool:
    mods = load_mods()
    new_mods = [m for m in mods if m.get("name", "").lower() != name.lower()]
    if len(new_mods) == len(mods):
        return False
    save_mods(new_mods)
    return True


def is_mod(player_uid: str) -> bool:
    clean = player_uid.lower().replace("0x", "")
    return any(m.get("uid", "").lower().replace("0x", "") == clean for m in load_mods())


# ── Permanent Memory ──────────────────────────

def load_memory() -> str:
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def append_memory(player_name: str, entry: str):
    existing = load_memory()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    updated = (existing + f"\n[{now}] {player_name}: {entry}").strip()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(updated)


def clear_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("")


# ── Ban System ────────────────────────────────

def load_bans() -> list:
    if not os.path.exists(BANS_FILE):
        return []
    try:
        with open(BANS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_bans(bans: list):
    with open(BANS_FILE, "w") as f:
        json.dump(bans, f, indent=2)


def add_ban(name: str, uid: str, ip: str, reason: str = "Banned", duration_minutes: int = None):
    bans = load_bans()
    now = datetime.now()
    entry = {
        "name": name, "uid": uid, "ip": ip, "reason": reason,
        "banned_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": (now + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S") if duration_minutes else None,
        "permanent": duration_minutes is None
    }
    bans = [b for b in bans if b.get("uid") != uid and b.get("name", "").lower() != name.lower()]
    bans.append(entry)
    save_bans(bans)


def remove_ban(name: str) -> bool:
    bans = load_bans()
    new_bans = [b for b in bans if b.get("name", "").lower() != name.lower()]
    if len(new_bans) == len(bans):
        return False
    save_bans(new_bans)
    return True


def is_banned(uid: str = None, name: str = None, ip: str = None) -> dict:
    bans = load_bans()
    now = datetime.now()
    for ban in bans:
        match = (
            (uid and ban.get("uid") == uid) or
            (name and ban.get("name", "").lower() == name.lower()) or
            (ip and ban.get("ip") == ip and ip not in ("127.0.0.1", "localhost"))
        )
        if not match:
            continue
        if not ban.get("permanent") and ban.get("expires_at"):
            expires = datetime.strptime(ban["expires_at"], "%Y-%m-%d %H:%M:%S")
            if now > expires:
                bans.remove(ban)
                save_bans(bans)
                continue
        return ban
    return {}


def get_active_bans() -> list:
    bans = load_bans()
    now = datetime.now()
    active = []
    for ban in bans:
        if ban.get("permanent"):
            active.append(ban)
        elif ban.get("expires_at"):
            expires = datetime.strptime(ban["expires_at"], "%Y-%m-%d %H:%M:%S")
            if now <= expires:
                active.append(ban)
    return active


# ── Auto-Moderation ───────────────────────────

spam_tracker = {}
spam_lock = threading.Lock()
compiled_slurs = [re.compile(p, re.IGNORECASE) for p in SLUR_PATTERNS]


def check_slurs(message: str) -> bool:
    return any(p.search(message) for p in compiled_slurs)


def check_excessive_caps(message: str) -> bool:
    if len(message) < CAPS_MIN_LENGTH:
        return False
    letters = [c for c in message if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= CAPS_THRESHOLD


def check_spam(player_name: str, message: str) -> bool:
    now = time.time()
    with spam_lock:
        if player_name not in spam_tracker:
            spam_tracker[player_name] = []
        spam_tracker[player_name] = [(t, m) for t, m in spam_tracker[player_name] if now - t <= SPAM_WINDOW]
        spam_tracker[player_name].append((now, message.lower()))
        return sum(1 for _, m in spam_tracker[player_name] if m == message.lower()) >= SPAM_THRESHOLD


def automod_check(player_name: str, player_uid: str, player_ip: str, message: str):
    if not automod_enabled:
        return
    if is_owner(player_uid) or is_mod(player_uid):
        return

    violation = None
    if check_slurs(message):
        violation = "use of prohibited language"
    elif check_excessive_caps(message):
        violation = "excessive caps"
    elif check_spam(player_name, message):
        violation = "spam"

    if violation:
        print(f"[AUTOMOD] {player_name} violated: {violation}")
        _apply_warning(player_name, player_uid, player_ip, f"AutoMod: {violation}", automated=True)


def _apply_warning(player_name: str, player_uid: str, player_ip: str, reason: str, automated: bool = False):
    """Apply a warning and escalate if threshold reached."""
    count = add_warning(player_name, player_uid, reason)
    remaining = max(0, WARN_KICK_THRESHOLD - count)

    if count < WARN_KICK_THRESHOLD:
        send_chat(f"@{player_name}: Warning {count}/{WARN_KICK_THRESHOLD} — {reason}. {remaining} warning(s) left before action is taken.")
    elif count == WARN_KICK_THRESHOLD:
        # Kick on reaching threshold
        send_chat(f"{player_name} has been kicked after {count} warnings.")
        send_rcon(f"Server.KickPlayer {player_name}")
        # Add one more warning entry to track post-kick behavior
        add_warning(player_name, player_uid, "Kicked after warning threshold")
    else:
        # Already been kicked — now tempban
        target_info = get_player_info(player_name)
        target_ip = target_info.get("ip", player_ip)
        add_ban(player_name, player_uid, target_ip, f"Temp banned: repeated violations", WARN_TEMPBAN_DURATION)
        send_rcon(f"Server.KickPlayer {player_name}")
        send_chat(f"{player_name} has been temporarily banned for {WARN_TEMPBAN_DURATION} minutes due to repeated violations.")


# ── State ─────────────────────────────────────

ws = None
ws_lock = threading.Lock()

player_last_ask   = {}
queue_lock        = threading.Lock()
pending_count     = 0
bot_enabled       = True
local_enabled     = False
memory_enabled    = True
automod_enabled   = True
chat_memory       = deque(maxlen=CHAT_MEMORY_SIZE)
known_players     = set()
active_provider   = "auto"
available_variants = {}  # populated at startup

GROQ_API_KEY       = ""
CEREBRAS_API_KEY   = ""
MISTRAL_API_KEY    = ""
OPENROUTER_API_KEY = ""
RCON_PASSWORD      = ""
RCON_PORT          = 11776
OWNER_UUID         = ""
OWNER_PRIVKEY      = ""

LOG_PATTERN = re.compile(
    r'^\[[\d/]+ [\d:]+\] <([^/]+)/([^/]+)/([^\>]+)> (.+)$'
)


# ── RCON ─────────────────────────────────────

def connect_rcon():
    global ws
    print(f"[RCON] Connecting to ws://{RCON_HOST}:{RCON_PORT} ...")
    try:
        ws = create_connection(
            f"ws://{RCON_HOST}:{RCON_PORT}",
            subprotocols=["dew-rcon"],
            timeout=10
        )
        ws.send(RCON_PASSWORD)
        time.sleep(0.5)
        print("[RCON] Connected and authenticated!")
        return True
    except Exception as e:
        print(f"[RCON] Connection failed: {e}")
        return False


def send_chat(message: str):
    words = message.split()
    chunk, lines = [], []
    for word in words:
        if len(" ".join(chunk + [word])) > 200:
            lines.append(" ".join(chunk))
            chunk = [word]
        else:
            chunk.append(word)
    if chunk:
        lines.append(" ".join(chunk))
    with ws_lock:
        for line in lines:
            full_line = f"{BOT_PREFIX} {line}"
            try:
                ws.send(f"Server.Say {full_line}")
                print(f"[BOT] {full_line}")
            except Exception as e:
                print(f"[BOT] Send failed: {e}")
            time.sleep(0.4)


def send_rcon(command: str):
    with ws_lock:
        try:
            ws.send(command)
            print(f"[RCON] {command}")
            return True
        except Exception as e:
            print(f"[RCON] Failed: {e}")
            return False


# ── Web Search ────────────────────────────────

def web_search(query: str, max_results: int = 3) -> list:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [(r.get("title", ""), r.get("href", "")) for r in results]
    except Exception:
        return []


def youtube_search(query: str) -> tuple:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"site:youtube.com {query}", max_results=3))
        for r in results:
            url = r.get("href", "")
            if "youtube.com/watch" in url or "youtu.be" in url:
                return r.get("title", ""), url
    except Exception:
        pass
    return "", ""


def needs_web_search(question: str) -> bool:
    lower = question.lower()
    return any(kw in lower for kw in EXPLICIT_SEARCH_KEYWORDS + CURRENT_INFO_KEYWORDS)


def get_search_context(question: str) -> str:
    if not needs_web_search(question) and not local_enabled:
        return ""
    lower = question.lower()
    if "youtube" in lower or "video" in lower or "watch" in lower:
        clean = re.sub(r'\b(find|search|look up|get me|show me|youtube|video|link|watch)\b', '', question, flags=re.IGNORECASE).strip()
        title, url = youtube_search(clean if clean else question)
        if url:
            return f"YouTube: {title} — {url.rstrip('.)').strip()}"
        return ""
    results = web_search(question)
    if results:
        return "\n".join(f"{t} — {u.rstrip(')').strip()}" for t, u in results[:2])
    return ""


# ── Server Info ───────────────────────────────

def get_server_info() -> dict:
    try:
        with urllib.request.urlopen(HTTP_API, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def get_player_info(name: str) -> dict:
    for p in get_server_info().get("players", []):
        if p.get("name", "").lower() == name.lower():
            return p
    return {}


def build_game_context() -> str:
    info = get_server_info()
    if not info:
        return "Game state unavailable."
    players = info.get("players", [])
    map_name = info.get("map", "unknown")
    mode = info.get("variant", "unknown")
    num_players = info.get("numPlayers", 0)
    max_players = info.get("maxPlayers", 0)
    status = info.get("status", "unknown")
    teams = info.get("teams", False)
    game_time = info.get("gameTime") or info.get("timeLimit") or ""

    player_lines = []
    for p in players:
        line = f"  {p.get('name','?')} — Score:{p.get('score',0)} K:{p.get('kills',0)} D:{p.get('deaths',0)}"
        if teams:
            line += f" Team:{p.get('team','?')}"
        player_lines.append(line)

    if players:
        leader = max(players, key=lambda p: p.get("score", 0))
        winner_line = f"Leading: {leader.get('name','?')} ({leader.get('score',0)} pts)"
    else:
        winner_line = "No scores yet."

    team_scores = info.get("teamScores", [])
    team_line = ""
    if teams and team_scores:
        valid = [(i, s) for i, s in enumerate(team_scores) if s >= 0]
        if valid:
            team_line = " | ".join([f"Team {i}: {s}" for i, s in valid])

    return f"""Game: {map_name} | {mode} | {status} | {num_players}/{max_players} players{' | ' + str(game_time) if game_time else ''}
{winner_line}{' | ' + team_line if team_line else ''}
Players: {', '.join(p.get('name','?') for p in players) if players else 'none'}"""


def build_chat_context() -> str:
    if not chat_memory:
        return ""
    return "Recent chat:\n" + "\n".join(f"  {n}: {m}" for n, m in chat_memory)


# ── AI Providers ──────────────────────────────

def call_groq(messages):
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": messages, "temperature": 0.7, "max_tokens": 150}, timeout=10)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Groq {r.status_code}")


def call_cerebras(messages):
    r = requests.post("https://api.cerebras.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"},
        json={"model": "qwen-3-235b-a22b-instruct-2507", "messages": messages, "temperature": 0.7, "max_tokens": 150}, timeout=10)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Cerebras {r.status_code}")


def call_mistral(messages):
    r = requests.post("https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest", "messages": messages, "temperature": 0.7, "max_tokens": 150}, timeout=10)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Mistral {r.status_code}")


def call_openrouter(messages):
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/cortana-bot-eldewrito", "X-Title": "Cortana Bot"},
        json={"model": "openrouter/free", "messages": messages, "temperature": 0.7, "max_tokens": 150}, timeout=10)
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"].get("content") or ""
        if not content:
            raise Exception("Empty response")
        return content.strip()
    raise Exception(f"OpenRouter {r.status_code}")


def call_local(messages):
    r = requests.post(f"{OLLAMA_API}/chat/completions",
        headers={"Content-Type": "application/json"},
        json={"model": OLLAMA_MODEL, "messages": messages, "temperature": 0.3, "max_tokens": 50}, timeout=60)
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"].get("content") or ""
        if not content:
            raise Exception("Empty response")
        return content.strip()
    raise Exception(f"Local {r.status_code}")


def is_ollama_running() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            return any(OLLAMA_MODEL.split(":")[0] in m["name"] for m in r.json().get("models", []))
    except Exception:
        pass
    return False


CLOUD_PROVIDER_CHAIN = [
    ("groq",       call_groq,       lambda: GROQ_API_KEY),
    ("cerebras",   call_cerebras,   lambda: CEREBRAS_API_KEY),
    ("mistral",    call_mistral,    lambda: MISTRAL_API_KEY),
    ("openrouter", call_openrouter, lambda: OPENROUTER_API_KEY),
]


def get_active_provider_name() -> str:
    if local_enabled:
        return f"Local ({OLLAMA_MODEL})"
    if active_provider != "auto":
        return active_provider.capitalize()
    for name, _, has_key in CLOUD_PROVIDER_CHAIN:
        if has_key():
            return f"{name.capitalize()} (auto)"
    return "None"


def ask_ai(player_name: str, question: str) -> str:
    print(f"[AI] {player_name} asked: {question}")
    try:
        search_ctx = get_search_context(question)
        memory_ctx = load_memory() if memory_enabled else ""
        system = SYSTEM_PROMPT
        if memory_ctx:
            system += f"\n\nPermanent memory:\n{memory_ctx}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"""{build_game_context()}

{build_chat_context()}

{f'Info:{chr(10)}{search_ctx}{chr(10)}' if search_ctx else ''}{player_name} asks: {question}"""}
        ]

        def trim(a): return a[:397] + "..." if len(a) > 400 else a

        if local_enabled and is_ollama_running():
            try:
                return trim(call_local(messages))
            except Exception as e:
                print(f"[AI] Local failed: {e}")

        if active_provider != "auto":
            for name, call_fn, has_key in CLOUD_PROVIDER_CHAIN:
                if name == active_provider and has_key():
                    return trim(call_fn(messages))

        for name, call_fn, has_key in CLOUD_PROVIDER_CHAIN:
            if not has_key():
                continue
            try:
                answer = call_fn(messages)
                print(f"[AI] Response from {name.capitalize()}")
                return trim(answer)
            except Exception as e:
                print(f"[AI] {name.capitalize()} failed: {e} — trying next...")

        return "All AI providers are currently unavailable. Try again later."
    except Exception as e:
        print(f"[AI] Unexpected error: {e}")
        return "An error occurred on my end. Try again."


# ── Auth ──────────────────────────────────────

def is_owner(player_uid: str) -> bool:
    clean = player_uid.lower().replace("0x", "")
    return clean == OWNER_UUID.lower().replace("0x", "") and bool(OWNER_PRIVKEY)


def is_mod_or_owner(player_uid: str) -> bool:
    return is_owner(player_uid) or is_mod(player_uid)


def is_protected(player_uid: str) -> bool:
    return is_owner(player_uid)


# ── Anti-Spam ─────────────────────────────────

def handle_ai_request(player_name: str, question: str):
    global pending_count
    try:
        answer = ask_ai(player_name, question)
        send_chat(f"@{player_name}: {answer}")
    finally:
        with queue_lock:
            pending_count -= 1


def try_queue_request(player_name: str, player_uid: str, question: str):
    global pending_count
    now = time.time()

    if is_owner(player_uid):
        with queue_lock:
            if pending_count >= MAX_QUEUE_SIZE:
                send_chat(f"@{player_name}: I'm currently occupied.")
                return False
            pending_count += 1
        threading.Thread(target=handle_ai_request, args=(player_name, question), daemon=True).start()
        return True

    last_ask = player_last_ask.get(player_name, 0)
    elapsed = now - last_ask
    if elapsed < PLAYER_COOLDOWN:
        remaining = int(PLAYER_COOLDOWN - elapsed)
        send_chat(f"@{player_name}: Please wait {remaining}s before asking again.")
        return False

    with queue_lock:
        if pending_count >= MAX_QUEUE_SIZE:
            send_chat(f"@{player_name}: I'm currently occupied.")
            return False
        pending_count += 1

    player_last_ask[player_name] = now
    threading.Thread(target=handle_ai_request, args=(player_name, question), daemon=True).start()
    return True


# ── Moderation Actions ────────────────────────

def do_kick(actor_name: str, actor_uid: str, target_name: str):
    target_info = get_player_info(target_name)
    target_uid = target_info.get("uid", "")
    if target_uid and is_protected(target_uid):
        send_chat("I won't act against the server administrator.")
        return False
    if not is_owner(actor_uid) and target_uid and is_mod(target_uid):
        send_chat(f"@{actor_name}: Moderators cannot act against other moderators.")
        return False
    send_rcon(f"Server.KickPlayer {target_name}")
    send_chat(f"{target_name} has been removed. You're welcome.")
    return True


def do_ban(actor_name: str, actor_uid: str, target_name: str):
    target_info = get_player_info(target_name)
    target_uid = target_info.get("uid", "")
    target_ip = target_info.get("ip", "")
    if target_uid and is_protected(target_uid):
        send_chat("I won't act against the server administrator.")
        return False
    if not is_owner(actor_uid) and target_uid and is_mod(target_uid):
        send_chat(f"@{actor_name}: Moderators cannot act against other moderators.")
        return False
    add_ban(target_name, target_uid, target_ip, f"Banned by {actor_name}")
    send_rcon(f"Server.KickPlayer {target_name}")
    send_chat(f"{target_name} has been permanently banned.")
    return True


def do_tempban(actor_name: str, actor_uid: str, target_name: str, duration: int):
    target_info = get_player_info(target_name)
    target_uid = target_info.get("uid", "")
    target_ip = target_info.get("ip", "")
    if target_uid and is_protected(target_uid):
        send_chat("I won't act against the server administrator.")
        return False
    if not is_owner(actor_uid) and target_uid and is_mod(target_uid):
        send_chat(f"@{actor_name}: Moderators cannot act against other moderators.")
        return False
    add_ban(target_name, target_uid, target_ip, f"Temp banned by {actor_name}", duration)
    send_rcon(f"Server.KickPlayer {target_name}")
    send_chat(f"{target_name} has been banned for {duration} minutes.")
    return True


# ── Command Handler ───────────────────────────

def handle_command(player_name: str, player_uid: str, player_ip: str, command: str):
    global bot_enabled, PLAYER_COOLDOWN, player_last_ask, active_provider
    global local_enabled, memory_enabled, automod_enabled

    parts = command.strip().split()
    cmd = parts[0].lower() if parts else ""
    args = parts[1:]

    owner = is_owner(player_uid)
    mod_or_owner = is_mod_or_owner(player_uid)

    # ── Admin-only ─────────────────────────────
    if cmd in ADMIN_ONLY_CMDS:
        if not owner:
            send_chat(f"@{player_name}: That command is restricted to the server owner.")
            return

        if cmd == "on":
            bot_enabled = True
            send_chat("Online.")
        elif cmd == "off":
            bot_enabled = False
            send_chat("Going offline.")
        elif cmd == "provider" and args:
            provider = args[0].lower()
            valid = [n for n, _, _ in CLOUD_PROVIDER_CHAIN] + ["auto"]
            if provider in valid:
                active_provider = provider
                send_chat(f"Provider set to {provider.capitalize()}.")
            else:
                send_chat(f"Options: {', '.join(valid)}")
        elif cmd == "local" and args:
            if args[0].lower() == "on":
                if is_ollama_running():
                    local_enabled = True
                    send_chat(f"Local model enabled ({OLLAMA_MODEL}).")
                else:
                    send_chat(f"Ollama not running. Pull model first: ollama pull {OLLAMA_MODEL}")
            else:
                local_enabled = False
                send_chat("Local model disabled.")
        elif cmd == "memory" and args:
            memory_enabled = args[0].lower() == "on"
            send_chat(f"Memory {'enabled' if memory_enabled else 'disabled'}.")
        elif cmd == "forget":
            clear_memory()
            send_chat("Permanent memory cleared.")
        elif cmd == "addmod" and args:
            target_name = " ".join(args)
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            if not target_uid:
                send_chat(f"Player '{target_name}' not found in server.")
                return
            if is_owner(target_uid):
                send_chat("The server owner is already above moderator level.")
                return
            add_mod(target_name, target_uid)
            send_chat(f"{target_name} has been added as a moderator.")
        elif cmd == "removemod" and args:
            target_name = " ".join(args)
            if remove_mod(target_name):
                send_chat(f"{target_name} is no longer a moderator.")
            else:
                send_chat(f"'{target_name}' is not a moderator.")
        elif cmd == "modlist":
            mods = load_mods()
            if not mods:
                send_chat("No moderators assigned.")
            else:
                send_chat(f"Moderators: {', '.join(m.get('name','?') for m in mods)}")
        return

    # ── Mod + Admin commands ───────────────────
    if cmd in MOD_CMDS:
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return

        if cmd == "on":
            bot_enabled = True
            send_chat("Online.")
        elif cmd == "off":
            bot_enabled = False
            send_chat("Going offline.")
        elif cmd == "status":
            mods = load_mods()
            send_chat(
                f"Status: {'On' if bot_enabled else 'Off'} | "
                f"Cooldown: {PLAYER_COOLDOWN}s | "
                f"Provider: {get_active_provider_name()} | "
                f"AutoMod: {'on' if automod_enabled else 'off'} | "
                f"Mods: {len(mods)}"
            )
        elif cmd == "clear":
            player_last_ask.clear()
            send_chat("All cooldowns cleared.")
        elif cmd == "cooldown" and args:
            try:
                PLAYER_COOLDOWN = int(args[0])
                send_chat(f"Cooldown set to {PLAYER_COOLDOWN}s.")
            except ValueError:
                send_chat("Usage: !ai cooldown <seconds>")
        elif cmd == "automod" and args:
            automod_enabled = args[0].lower() == "on"
            send_chat(f"Auto-moderation {'enabled' if automod_enabled else 'disabled'}.")
        elif cmd == "map" and args:
            map_input = " ".join(args)
            send_rcon(f"Game.Map {map_input}")
            send_chat(f"Changing map to {map_input}...")
        elif cmd == "mode" and args:
            mode_input = " ".join(args).lower()
            # Look up variant folder name (case-insensitive)
            matched = available_variants.get(mode_input)
            if matched:
                send_rcon(f"Game.GameType {matched}")
                send_chat(f"Loading mode: {matched}")
            else:
                # Try partial match
                partial = [v for k, v in available_variants.items() if mode_input in k]
                if partial:
                    send_rcon(f"Game.GameType {partial[0]}")
                    send_chat(f"Loading mode: {partial[0]}")
                else:
                    send_chat(f"Mode '{mode_input}' not found. Use !ai modes to see available modes.")
        elif cmd == "modes":
            if available_variants:
                names = ", ".join(sorted(available_variants.values()))
                send_chat(f"Available modes: {names}")
            else:
                send_chat("No game variants found. Check GAME_VARIANTS_DIR path.")
        elif cmd == "start":
            send_rcon("Game.Start")
            send_chat("Starting the game...")
        elif cmd == "kick" and args:
            do_kick(player_name, player_uid, " ".join(args))
        elif cmd == "ban" and args:
            do_ban(player_name, player_uid, " ".join(args))
        elif cmd == "tempban" and len(args) >= 2:
            try:
                duration = int(args[-1])
                do_tempban(player_name, player_uid, " ".join(args[:-1]), duration)
            except ValueError:
                send_chat("Usage: !ai tempban <name> <minutes>")
        elif cmd == "unban" and args:
            target = " ".join(args)
            if remove_ban(target):
                send_chat(f"{target} has been unbanned.")
            else:
                send_chat(f"No ban found for '{target}'.")
        elif cmd == "banlist":
            active = get_active_bans()
            if not active:
                send_chat("No active bans.")
            else:
                send_chat(f"Active bans ({len(active)}):")
                for ban in active[:5]:
                    exp = ban.get("expires_at", "permanent") or "permanent"
                    send_chat(f"  {ban.get('name')} — {exp}")
        elif cmd == "warn" and len(args) >= 2:
            target_name = args[0]
            reason = " ".join(args[1:])
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            target_ip = target_info.get("ip", "")
            if target_uid and is_protected(target_uid):
                send_chat("I won't act against the server administrator.")
                return
            if not is_owner(player_uid) and target_uid and is_mod(target_uid):
                send_chat(f"@{player_name}: Moderators cannot warn other moderators.")
                return
            _apply_warning(target_name, target_uid, target_ip, f"{reason} (warned by {player_name})")
        elif cmd == "warnings" and args:
            target_name = " ".join(args)
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            data = get_warnings(target_name, target_uid)
            count = data.get("count", 0)
            send_chat(f"{target_name} has {count} warning(s).")
        elif cmd == "clearwarnings" and args:
            target_name = " ".join(args)
            if clear_warnings(target_name):
                send_chat(f"Warnings cleared for {target_name}.")
            else:
                send_chat(f"No warnings found for '{target_name}'.")
        return

    # Unknown command
    send_chat(
        "Mod: status/clear/cooldown/automod/map/mode/modes/start/kick/ban/tempban/unban/banlist/warn/warnings/clearwarnings | "
        "Admin: on/off/provider/local/memory/forget/addmod/removemod/modlist"
    )


# ── Ban Enforcement ───────────────────────────

def check_banned_players():
    while True:
        time.sleep(10)
        try:
            for p in get_server_info().get("players", []):
                name = p.get("name", "")
                uid = p.get("uid", "")
                if is_protected(uid):
                    continue
                if is_banned(uid=uid, name=name):
                    send_rcon(f"Server.KickPlayer {name}")
                    time.sleep(1)
                    send_chat(f"{name} is banned and has been removed.")
        except Exception:
            pass


# ── Kill Streak Detection ─────────────────────

def check_killstreaks():
    streak_announced = {}
    while True:
        time.sleep(10)
        if not bot_enabled:
            continue
        try:
            for p in get_server_info().get("players", []):
                name = p.get("name", "")
                streak = p.get("bestStreak", 0)
                last = streak_announced.get(name, 0)
                if streak >= 5 and streak != last and streak % 5 == 0:
                    streak_announced[name] = streak
                    msgs = {
                        5:  f"{name} is on a killing spree. Impressive, I suppose.",
                        10: f"{name} with 10 kills straight. Someone's having a good day.",
                        15: f"{name} at 15. I'd recommend the others reconsider their strategy.",
                        20: f"{name} is unstoppable. Statistically speaking, anyway.",
                    }
                    send_chat(msgs.get(streak, f"{name} is on a {streak}-kill streak."))
        except Exception:
            pass


# ── Player Join Detection ─────────────────────

def check_players():
    global known_players
    try:
        known_players = {p["name"] for p in get_server_info().get("players", [])}
    except Exception:
        known_players = set()
    while True:
        time.sleep(5)
        if not bot_enabled:
            continue
        try:
            current = {p["name"] for p in get_server_info().get("players", [])}
            for name in current - known_players:
                send_chat(f"Welcome, {name}. Type !cortana <question> or just mention my name.")
            known_players = current
        except Exception:
            pass


# ── Chat Log Watcher ──────────────────────────

def watch_chat_log():
    print(f"[LOG] Watching: {CHAT_LOG_PATH}")
    while not os.path.exists(CHAT_LOG_PATH):
        print("[LOG] Waiting for chat log...")
        time.sleep(2)

    with open(CHAT_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, 2)
        print("[LOG] Ready.")

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            line = line.strip()
            if not line:
                continue

            match = LOG_PATTERN.match(line)
            if not match:
                continue

            player_name = match.group(1)
            player_uid  = match.group(2)
            player_ip   = match.group(3)
            message     = match.group(4).strip()

            if message.startswith(BOT_PREFIX):
                continue
            if player_name.lower() in IGNORED_SENDER_NAMES and not is_owner(player_uid):
                continue
            if player_name.lower() in {"cortana", "ai"} and not is_owner(player_uid):
                continue

            print(f"[CHAT] {player_name} ({player_uid}): {message}")
            chat_memory.append((player_name, message))

            # Automod in background
            threading.Thread(target=automod_check, args=(player_name, player_uid, player_ip, message), daemon=True).start()

            lower = message.lower()

            # !ai commands
            if lower.startswith("!ai "):
                remainder = message[4:].strip()
                rem_parts = remainder.split()
                if not rem_parts:
                    continue
                first_word = rem_parts[0].lower()

                # Admin or mod command
                if first_word in ADMIN_ONLY_CMDS or first_word in MOD_CMDS:
                    handle_command(player_name, player_uid, player_ip, remainder)
                    continue

                # Player remember
                if first_word == "remember":
                    entry = " ".join(rem_parts[1:])
                    if entry:
                        append_memory(player_name, entry)
                        send_chat(f"@{player_name}: Noted.")
                    else:
                        send_chat(f"@{player_name}: Remember what? Try: !ai remember <text>")
                    continue

                # Regular AI question
                if not bot_enabled:
                    send_chat(f"@{player_name}: I'm currently offline.")
                    continue
                try_queue_request(player_name, player_uid, remainder)
                continue

            # Explicit triggers
            triggered = False
            question = None
            for trigger in ["!cortana", "/cortana", "/ai", "!bot", "/bot"]:
                if lower.startswith(trigger):
                    question = message[len(trigger):].strip()
                    triggered = True
                    break

            if not triggered and "cortana" in lower:
                question = message.strip()
                triggered = True

            if triggered:
                if not bot_enabled:
                    send_chat(f"@{player_name}: I'm currently offline.")
                    continue
                if not question:
                    send_chat(f"@{player_name}: You called? Ask me something.")
                    continue
                try_queue_request(player_name, player_uid, question)


# ── Main ──────────────────────────────────────

if __name__ == "__main__":
    config = load_config()

    GROQ_API_KEY       = config.get("GROQ_API_KEY", "")
    CEREBRAS_API_KEY   = config.get("CEREBRAS_API_KEY", "")
    MISTRAL_API_KEY    = config.get("MISTRAL_API_KEY", "")
    OPENROUTER_API_KEY = config.get("OPENROUTER_API_KEY", "")
    RCON_PASSWORD      = config.get("RCON_PASSWORD", "")
    RCON_PORT          = int(config.get("RCON_PORT", 11776))
    OWNER_UUID         = config.get("OWNER_UUID", "").lower().replace("0x", "")
    OWNER_PRIVKEY      = config.get("OWNER_PRIVKEY", "")

    providers_loaded = [n for n, _, has_key in CLOUD_PROVIDER_CHAIN if has_key()]
    available_variants = scan_variants()
    mods = load_mods()
    memory_lines = len(load_memory().splitlines()) if load_memory() else 0

    print("=" * 55)
    print(f"  {BOT_NAME} AI Bot")
    print(f"  Owner UID:  {OWNER_UUID}")
    print(f"  PrivKey:    {'set' if OWNER_PRIVKEY else 'NOT SET'}")
    print(f"  Providers:  {' -> '.join(p.capitalize() for p in providers_loaded) if providers_loaded else 'None!'}")
    print(f"  Variants:   {len(available_variants)} modes found")
    print(f"  Mods:       {len(mods)} loaded")
    print(f"  Memory:     {memory_lines} entries")
    print(f"  AutoMod:    on | Warnings: kick@{WARN_KICK_THRESHOLD}, tempban@{WARN_KICK_THRESHOLD+1} ({WARN_TEMPBAN_DURATION}min)")
    print(f"  Config:     {CONFIG_FILE}")
    print("=" * 55)

    if not RCON_PASSWORD:
        print("ERROR: RCON_PASSWORD not set in config.txt")
        sys.exit(1)
    if not OWNER_UUID:
        print("ERROR: OWNER_UUID not set in config.txt")
        sys.exit(1)
    if not OWNER_PRIVKEY:
        print("WARNING: OWNER_PRIVKEY not set — admin commands disabled!")
    if not providers_loaded:
        print("ERROR: No API keys loaded!")
        sys.exit(1)
    if not connect_rcon():
        print("[ERROR] Could not connect to RCON.")
        sys.exit(1)

    threading.Thread(target=check_killstreaks, daemon=True).start()
    threading.Thread(target=check_players, daemon=True).start()
    threading.Thread(target=check_banned_players, daemon=True).start()

    time.sleep(1)
    send_chat(f"{BOT_NAME} online. Type !cortana <question> or just mention my name.")
    watch_chat_log()
