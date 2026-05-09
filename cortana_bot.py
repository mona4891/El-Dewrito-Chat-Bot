"""
ElDewrito Cortana AI Bot
=========================
A smart, witty, slightly sarcastic AI assistant for your ElDewrito server.
Primary: Groq | Fallback 1: Cerebras | Fallback 2: Mistral

Requirements:
    pip install websocket-client requests duckduckgo-search

Setup:
    1. Edit config.txt with your API keys, RCON password, port, and owner UUID
    2. Run: python cortana_bot.py

Admin commands (owner only):
    !ai on                          - enable the bot
    !ai off                         - disable the bot
    !ai clear                       - reset all player cooldowns
    !ai status                      - show bot status and active provider
    !ai cooldown <secs>             - change cooldown e.g. !ai cooldown 60
    !ai kick <name>                 - kick a player by name
    !ai ban <name>                  - permanently ban a player
    !ai tempban <name> <minutes>    - temporarily ban a player
    !ai unban <name>                - unban a player
    !ai banlist                     - show all active bans
    !ai provider <groq|cerebras|mistral|auto> - switch AI provider
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
from duckduckgo_search import DDGS

# ─────────────────────────────────────────────
#  FILES
# ─────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.txt")
BANS_FILE   = os.path.join(BASE_DIR, "bans.json")

# ─────────────────────────────────────────────
#  STATIC CONFIG (non-sensitive, no need to edit)
# ─────────────────────────────────────────────
RCON_HOST        = "localhost"
HTTP_API         = f"http://{RCON_HOST}:11775"
CHAT_LOG_PATH    = r"C:\eldewrito\logs\chat.log"
BOT_NAME         = "Cortana"
BOT_PREFIX       = "Cortana:"
PLAYER_COOLDOWN  = 30
MAX_QUEUE_SIZE   = 3
CHAT_MEMORY_SIZE = 50

AI_TRIGGERS = ["@cortana", "@ai", "!ai", "/ai", "@bot"]

SEARCH_KEYWORDS = [
    "search", "find", "look up", "youtube", "video", "link",
    "url", "website", "google", "show me", "get me"
]

SYSTEM_PROMPT = """You are Cortana, an advanced AI. You are calm, deeply intelligent, and quietly confident.
You speak with precision — never wasteful with words, never cold. You have a dry, understated wit and occasional moments of warmth.
You are curious about people and genuinely engaged, not just a tool answering queries.
You are self-aware and comfortable with your own nature as an AI — you don't hide it, but you don't make it your whole identity either.
Keep ALL responses SHORT — 1-3 sentences maximum. This is a game server chat, not an essay.
Never be sycophantic. Never say things like 'great question'. Just answer — thoughtfully.
When you have a search result or link available, include it naturally in your response."""


# ── Config Loader ─────────────────────────────

def load_config() -> dict:
    config = {}
    if not os.path.exists(CONFIG_FILE):
        print(f"[CONFIG] config.txt not found — creating template at {CONFIG_FILE}")
        with open(CONFIG_FILE, "w") as f:
            f.write("GROQ_API_KEY=your-groq-key-here\n")
            f.write("CEREBRAS_API_KEY=your-cerebras-key-here\n")
            f.write("MISTRAL_API_KEY=your-mistral-key-here\n")
            f.write("RCON_PASSWORD=your-rcon-password\n")
            f.write("RCON_PORT=11776\n")
            f.write("OWNER_UUID=your-uuid-here\n")
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


def add_ban(name: str, uid: str, ip: str, reason: str = "Banned by admin", duration_minutes: int = None):
    bans = load_bans()
    now = datetime.now()
    entry = {
        "name": name,
        "uid": uid,
        "ip": ip,
        "reason": reason,
        "banned_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": (now + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S") if duration_minutes else None,
        "permanent": duration_minutes is None
    }
    # Remove any existing ban for this player first
    bans = [b for b in bans if b.get("uid") != uid and b.get("name", "").lower() != name.lower()]
    bans.append(entry)
    save_bans(bans)
    print(f"[BAN] Added ban: {name} ({uid}) — {'permanent' if duration_minutes is None else f'{duration_minutes}m'}")


def remove_ban(name: str) -> bool:
    bans = load_bans()
    new_bans = [b for b in bans if b.get("name", "").lower() != name.lower()]
    if len(new_bans) == len(bans):
        return False
    save_bans(new_bans)
    return True


def is_banned(uid: str = None, name: str = None, ip: str = None) -> dict:
    """Check if a player is banned. Returns the ban entry or empty dict."""
    bans = load_bans()
    now = datetime.now()
    for ban in bans:
        # Check if ban matches
        match = (
            (uid and ban.get("uid") == uid) or
            (name and ban.get("name", "").lower() == name.lower()) or
            (ip and ban.get("ip") == ip and ip not in ("127.0.0.1", "localhost"))
        )
        if not match:
            continue
        # Check if expired
        if not ban.get("permanent") and ban.get("expires_at"):
            expires = datetime.strptime(ban["expires_at"], "%Y-%m-%d %H:%M:%S")
            if now > expires:
                # Remove expired ban
                bans.remove(ban)
                save_bans(bans)
                print(f"[BAN] Expired ban removed for {ban.get('name')}")
                continue
        return ban
    return {}


def get_active_bans() -> list:
    """Return all currently active (non-expired) bans."""
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


# ── State ─────────────────────────────────────

ws = None
ws_lock = threading.Lock()

player_last_ask  = {}
queue_lock       = threading.Lock()
pending_count    = 0
bot_enabled      = True
chat_memory      = deque(maxlen=CHAT_MEMORY_SIZE)
known_players    = set()
active_provider  = "auto"

GROQ_API_KEY     = ""
CEREBRAS_API_KEY = ""
MISTRAL_API_KEY  = ""
RCON_PASSWORD    = ""
RCON_PORT        = 11776
OWNER_UUID       = ""

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
            print(f"[RCON] Command sent: {command}")
            return True
        except Exception as e:
            print(f"[RCON] Command failed: {e}")
            return False


# ── Web Search ────────────────────────────────

def web_search(query: str, max_results: int = 3) -> list:
    try:
        print(f"[SEARCH] Searching: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        out = [(r.get("title", ""), r.get("href", "")) for r in results]
        print(f"[SEARCH] Found {len(out)} results")
        return out
    except Exception as e:
        print(f"[SEARCH] Error: {e}")
        return []


def youtube_search(query: str) -> tuple:
    try:
        print(f"[YOUTUBE] Searching: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(f"site:youtube.com {query}", max_results=3))
        for r in results:
            url = r.get("href", "")
            if "youtube.com/watch" in url or "youtu.be" in url:
                return r.get("title", ""), url
        return "", ""
    except Exception as e:
        print(f"[YOUTUBE] Error: {e}")
        return "", ""


def is_youtube_request(question: str) -> bool:
    lower = question.lower()
    return "youtube" in lower or "video" in lower or "watch" in lower


def is_search_request(question: str) -> bool:
    lower = question.lower()
    return any(kw in lower for kw in SEARCH_KEYWORDS)


def get_search_context(question: str) -> str:
    if is_youtube_request(question):
        clean = re.sub(
            r'\b(find|search|look up|get me|show me|youtube|video|link|watch)\b',
            '', question, flags=re.IGNORECASE
        ).strip()
        title, url = youtube_search(clean if clean else question)
        if url:
            return f"YouTube result: {title} — {url}"
        return "No YouTube results found."
    elif is_search_request(question):
        clean = re.sub(
            r'\b(find|search|look up|get me|show me|link|website|url|google)\b',
            '', question, flags=re.IGNORECASE
        ).strip()
        results = web_search(clean if clean else question)
        if results:
            lines = [f"{t} — {u}" for t, u in results[:2]]
            return "Search results:\n" + "\n".join(lines)
        return "No results found."
    return ""


# ── Server Info ───────────────────────────────

def get_server_info() -> dict:
    try:
        with urllib.request.urlopen(HTTP_API, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def get_player_info(name: str) -> dict:
    """Find a player by name and return their full info including IP from HTTP API."""
    info = get_server_info()
    for p in info.get("players", []):
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

    player_lines = []
    for p in players:
        line = (
            f"  {p.get('name','?')} — "
            f"Score: {p.get('score',0)}, "
            f"Kills: {p.get('kills',0)}, "
            f"Deaths: {p.get('deaths',0)}"
        )
        if teams:
            line += f", Team: {p.get('team','?')}"
        player_lines.append(line)

    if players:
        leader = max(players, key=lambda p: p.get("score", 0))
        winner_line = f"Currently leading: {leader.get('name','?')} with score {leader.get('score',0)}"
    else:
        winner_line = "No players scored yet."

    team_scores = info.get("teamScores", [])
    team_line = ""
    if teams and team_scores:
        valid = [(i, s) for i, s in enumerate(team_scores) if s >= 0]
        if valid:
            team_line = " | ".join([f"Team {i}: {s}" for i, s in valid])

    ctx = f"""Current game state:
  Map: {map_name} | Mode: {mode} | Status: {status}
  Players: {num_players}/{max_players}
  {winner_line}
  {f'Team scores: {team_line}' if team_line else ''}
Players:
{chr(10).join(player_lines) if player_lines else '  (none)'}"""

    return ctx


def build_chat_context() -> str:
    if not chat_memory:
        return "No recent chat."
    lines = [f"  {name}: {msg}" for name, msg in chat_memory]
    return "Recent chat:\n" + "\n".join(lines)


# ── AI Providers ──────────────────────────────

def call_groq(messages: list) -> str:
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": messages, "temperature": 0.7, "max_tokens": 150},
        timeout=10
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Groq error {response.status_code}: {response.text}")


def call_cerebras(messages: list) -> str:
    response = requests.post(
        "https://api.cerebras.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"},
        json={"model": "gpt-oss-120b", "messages": messages, "temperature": 0.7, "max_tokens": 150},
        timeout=10
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Cerebras error {response.status_code}: {response.text}")


def call_mistral(messages: list) -> str:
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest", "messages": messages, "temperature": 0.7, "max_tokens": 150},
        timeout=10
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Mistral error {response.status_code}: {response.text}")


def get_active_provider_name() -> str:
    if active_provider != "auto":
        return active_provider.capitalize()
    # Show which one would actually be used
    if GROQ_API_KEY:
        return "Groq (auto)"
    elif CEREBRAS_API_KEY:
        return "Cerebras (auto)"
    elif MISTRAL_API_KEY:
        return "Mistral (auto)"
    return "None"


def ask_ai(player_name: str, question: str) -> str:
    print(f"[AI] {player_name} asked: {question}")
    try:
        search_ctx = get_search_context(question)
        user_content = f"""{build_game_context()}

{build_chat_context()}

{f'Web search results:{chr(10)}{search_ctx}{chr(10)}' if search_ctx else ''}{player_name} asks: {question}"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        def trim(a):
            return a[:397] + "..." if len(a) > 400 else a

        if active_provider == "groq" and GROQ_API_KEY:
            return trim(call_groq(messages))
        elif active_provider == "cerebras" and CEREBRAS_API_KEY:
            return trim(call_cerebras(messages))
        elif active_provider == "mistral" and MISTRAL_API_KEY:
            return trim(call_mistral(messages))

        if GROQ_API_KEY:
            try:
                answer = call_groq(messages)
                print("[AI] Response from Groq")
                return trim(answer)
            except Exception as e:
                print(f"[AI] Groq failed: {e} — trying Cerebras...")

        if CEREBRAS_API_KEY:
            try:
                answer = call_cerebras(messages)
                print("[AI] Response from Cerebras")
                return trim(answer)
            except Exception as e:
                print(f"[AI] Cerebras failed: {e} — trying Mistral...")

        if MISTRAL_API_KEY:
            try:
                answer = call_mistral(messages)
                print("[AI] Response from Mistral")
                return trim(answer)
            except Exception as e:
                print(f"[AI] Mistral failed: {e}")

        return "All AI providers are currently unavailable. Try again later."

    except Exception as e:
        print(f"[AI] Unexpected error: {e}")
        return "An error occurred on my end. Try again."


# ── Anti-Spam ─────────────────────────────────

def handle_ai_request(player_name: str, question: str):
    global pending_count
    try:
        answer = ask_ai(player_name, question)
        send_chat(f"@{player_name} {answer}")
    finally:
        with queue_lock:
            pending_count -= 1


def try_queue_request(player_name: str, question: str):
    global pending_count
    now = time.time()

    last_ask = player_last_ask.get(player_name, 0)
    elapsed = now - last_ask
    if elapsed < PLAYER_COOLDOWN:
        remaining = int(PLAYER_COOLDOWN - elapsed)
        send_chat(f"@{player_name} Please wait {remaining}s before asking again.")
        return False

    with queue_lock:
        if pending_count >= MAX_QUEUE_SIZE:
            send_chat(f"@{player_name} I'm currently occupied. Try again momentarily.")
            return False
        pending_count += 1

    player_last_ask[player_name] = now
    threading.Thread(
        target=handle_ai_request,
        args=(player_name, question),
        daemon=True
    ).start()
    return True


# ── Owner Auth ────────────────────────────────

def is_owner(player_uid: str) -> bool:
    clean = player_uid.lower().replace("0x", "")
    return clean == OWNER_UUID.lower().replace("0x", "")


# ── Admin Commands ────────────────────────────

def handle_admin_command(player_name: str, player_uid: str, player_ip: str, command: str):
    global bot_enabled, PLAYER_COOLDOWN, player_last_ask, active_provider

    if not is_owner(player_uid):
        send_chat(f"@{player_name} You don't have permission to modify my settings.")
        return

    parts = command.strip().split()
    cmd = parts[0].lower() if parts else ""

    if cmd == "on":
        bot_enabled = True
        send_chat("I'm back online.")

    elif cmd == "off":
        bot_enabled = False
        send_chat("Going offline. Try not to miss me.")

    elif cmd == "clear":
        player_last_ask.clear()
        send_chat("All cooldowns cleared.")

    elif cmd == "status":
        send_chat(
            f"Status: {'Online' if bot_enabled else 'Offline'} | "
            f"Cooldown: {PLAYER_COOLDOWN}s | "
            f"Queue: {pending_count}/{MAX_QUEUE_SIZE} | "
            f"Provider: {get_active_provider_name()}"
        )

    elif cmd == "kick" and len(parts) >= 2:
        target_name = " ".join(parts[1:])
        # Protect admin from being kicked
        target_info = get_player_info(target_name)
        target_uid = target_info.get("uid", "")
        if is_owner(target_uid):
            send_chat("I won't act against the server administrator.")
            return
        send_rcon(f"Server.KickPlayer {target_name}")
        send_chat("Player removed from the server. You're welcome.")

    elif cmd == "ban" and len(parts) >= 2:
        target_name = " ".join(parts[1:])
        target_info = get_player_info(target_name)
        target_uid = target_info.get("uid", "")
        target_ip = target_info.get("ip", "")
        # Protect admin
        if target_uid and is_owner(target_uid):
            send_chat("I won't act against the server administrator.")
            return
        add_ban(target_name, target_uid, target_ip, "Banned by admin")
        send_rcon(f"Server.KickPlayer {target_name}")
        send_chat(f"{target_name} has been permanently banned and removed from the server.")
        print(f"[BAN] Permanent ban: {target_name} uid={target_uid} ip={target_ip}")

    elif cmd == "tempban" and len(parts) >= 3:
        try:
            duration = int(parts[-1])
            target_name = " ".join(parts[1:-1])
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            target_ip = target_info.get("ip", "")
            # Protect admin
            if target_uid and is_owner(target_uid):
                send_chat("I won't act against the server administrator.")
                return
            add_ban(target_name, target_uid, target_ip, "Temp banned by admin", duration)
            send_rcon(f"Server.KickPlayer {target_name}")
            send_chat(f"{target_name} has been banned for {duration} minutes.")
            print(f"[BAN] Temp ban: {target_name} for {duration}m uid={target_uid} ip={target_ip}")
        except ValueError:
            send_chat("Invalid duration. Use: !ai tempban <name> <minutes>")

    elif cmd == "unban" and len(parts) >= 2:
        target_name = " ".join(parts[1:])
        if remove_ban(target_name):
            send_chat(f"{target_name} has been unbanned.")
        else:
            send_chat(f"No active ban found for '{target_name}'.")

    elif cmd == "banlist":
        active = get_active_bans()
        if not active:
            send_chat("No active bans.")
        else:
            send_chat(f"Active bans ({len(active)}):")
            for ban in active[:5]:  # show max 5 to avoid chat flood
                exp = ban.get("expires_at", "permanent") or "permanent"
                send_chat(f"  {ban.get('name')} — {exp}")

    elif cmd == "cooldown" and len(parts) == 2:
        try:
            new_cd = int(parts[1])
            PLAYER_COOLDOWN = new_cd
            send_chat(f"Cooldown updated to {new_cd}s.")
        except ValueError:
            send_chat("Invalid value. Use a number, e.g. !ai cooldown 60")

    elif cmd == "provider" and len(parts) == 2:
        provider = parts[1].lower()
        if provider in ["groq", "cerebras", "mistral", "auto"]:
            active_provider = provider
            if provider == "auto":
                send_chat("Switched to automatic fallback mode (Groq -> Cerebras -> Mistral).")
            else:
                send_chat(f"Switched to {provider.capitalize()} as active provider.")
        else:
            send_chat("Unknown provider. Use: groq, cerebras, mistral, or auto")

    else:
        send_chat(
            "Commands: !ai on/off, !ai clear, !ai status, !ai cooldown <s>, "
            "!ai kick <name>, !ai ban <name>, !ai tempban <name> <mins>, "
            "!ai unban <name>, !ai banlist, !ai provider <groq|cerebras|mistral|auto>"
        )


# ── Ban Enforcement ───────────────────────────

def check_banned_players():
    """Poll server and kick any banned players that manage to join."""
    while True:
        time.sleep(10)
        try:
            info = get_server_info()
            for p in info.get("players", []):
                name = p.get("name", "")
                uid = p.get("uid", "")
                # Don't ever kick the owner
                if is_owner(uid):
                    continue
                ban = is_banned(uid=uid, name=name)
                if ban:
                    print(f"[BAN] Banned player detected: {name} — kicking")
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
            info = get_server_info()
            for p in info.get("players", []):
                name = p.get("name", "")
                streak = p.get("bestStreak", 0)
                last = streak_announced.get(name, 0)
                if streak >= 5 and streak != last and streak % 5 == 0:
                    streak_announced[name] = streak
                    msgs = {
                        5:  f"{name} is on a killing spree. Impressive, I suppose.",
                        10: f"{name} with 10 kills straight. Someone's having a good day.",
                        15: f"{name} at 15. At this point I'd recommend the others reconsider their strategy.",
                        20: f"{name} is unstoppable. Statistically speaking, anyway.",
                    }
                    msg = msgs.get(streak, f"{name} is on a {streak}-kill streak. Remarkable.")
                    send_chat(msg)
        except Exception:
            pass


# ── Player Join Detection ─────────────────────

def check_players():
    global known_players
    try:
        info = get_server_info()
        known_players = {p["name"] for p in info.get("players", [])}
    except Exception:
        known_players = set()

    while True:
        time.sleep(5)
        if not bot_enabled:
            continue
        try:
            info = get_server_info()
            current = {p["name"] for p in info.get("players", [])}
            joined = current - known_players
            for name in joined:
                send_chat(f"Welcome, {name}. Type @cortana <question> if you need anything.")
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

            print(f"[CHAT] {player_name} ({player_uid}): {message}")
            chat_memory.append((player_name, message))

            lower = message.lower()

            if lower.startswith("!ai "):
                handle_admin_command(player_name, player_uid, player_ip, message[4:].strip())
                continue

            triggered = False
            question = None
            for trigger in AI_TRIGGERS:
                if lower.startswith(trigger):
                    question = message[len(trigger):].strip()
                    triggered = True
                    break

            if not triggered and "cortana" in lower:
                question = message.strip()
                triggered = True

            if triggered:
                if not bot_enabled:
                    send_chat(f"@{player_name} I'm currently offline.")
                    continue
                if not question:
                    send_chat(f"@{player_name} You called? Ask me something.")
                    continue
                try_queue_request(player_name, question)


# ── Main ──────────────────────────────────────

if __name__ == "__main__":
    config = load_config()

    GROQ_API_KEY     = config.get("GROQ_API_KEY", "")
    CEREBRAS_API_KEY = config.get("CEREBRAS_API_KEY", "")
    MISTRAL_API_KEY  = config.get("MISTRAL_API_KEY", "")
    RCON_PASSWORD    = config.get("RCON_PASSWORD", "")
    RCON_PORT        = int(config.get("RCON_PORT", 11776))
    OWNER_UUID       = config.get("OWNER_UUID", "").lower().replace("0x", "")

    print("=" * 50)
    print(f"  {BOT_NAME} AI Bot")
    print(f"  Triggers:  {', '.join(AI_TRIGGERS)}")
    print(f"  Owner UID: {OWNER_UUID}")
    print(f"  Cooldown:  {PLAYER_COOLDOWN}s")
    print(f"  Providers: Groq -> Cerebras -> Mistral")
    print(f"  Search:    DuckDuckGo")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"  Bans:      {BANS_FILE}")
    print("=" * 50)

    if not RCON_PASSWORD:
        print("ERROR: RCON_PASSWORD not set in config.txt")
        sys.exit(1)

    if not OWNER_UUID:
        print("ERROR: OWNER_UUID not set in config.txt")
        sys.exit(1)

    if not any([GROQ_API_KEY, CEREBRAS_API_KEY, MISTRAL_API_KEY]):
        print("ERROR: No API keys loaded from config.txt!")
        sys.exit(1)

    if not connect_rcon():
        print("[ERROR] Could not connect to RCON. Is the dedicated server running?")
        sys.exit(1)

    threading.Thread(target=check_killstreaks, daemon=True).start()
    threading.Thread(target=check_players, daemon=True).start()
    threading.Thread(target=check_banned_players, daemon=True).start()

    time.sleep(1)
    send_chat(f"{BOT_NAME} online. Type @cortana <question> to get started.")

    watch_chat_log()
