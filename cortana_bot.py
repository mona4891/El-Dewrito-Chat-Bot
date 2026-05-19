"""
ElDewrito Cortana AI Bot
Fallback: Groq - Cerebras - Mistral - OpenRouter - Local (Ollama)

Features:
  - Server settings, map rotation, AFK kick, match summary, first blood
  - Discord bridge, player stats, moderation (kick/ban/warn/mute)
  - Auto-mod (slurs/spam/caps), web/YouTube search, TTS voice

Setup:
  1. Edit config.txt
  2. Edit rotation.json for map rotation
  3. Edit ANNOUNCEMENTS list
  4. Set AFK_TIMEOUT_MINUTES
  5. Run: python cortana_bot.py
"""

import sys
import os
import time
import random
import asyncio
import threading
import json
import re
import urllib.request
import requests
from collections import deque
from datetime import datetime, timedelta
from websocket import create_connection
from ddgs import DDGS
import pygame
import tempfile
from gtts import gTTS

# ─────────────────────────────────────────────
#  FILES & PATHS
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.txt")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.txt")
MODS_FILE = os.path.join(BASE_DIR, "mods.json")
ROTATION_FILE = os.path.join(BASE_DIR, "rotation.json")
MATCH_LOG_FILE = os.path.join(BASE_DIR, "match_history.json")
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
BANS_FILE = os.path.join(BASE_DIR, "bans.json")
WARNINGS_FILE = os.path.join(BASE_DIR, "warnings.json")
BAN_LOG_FILE = os.path.join(BASE_DIR, "ban_log.txt")
WARNING_LOG_FILE = os.path.join(BASE_DIR, "warning_log.txt")
GAME_VARIANTS_DIR = r"C:\Games\eldewrito\data\game_variants"
GAME_MAPS_DIR = r"C:\Games\eldewrito\data\map_variants"
ELDEWRITO_BAN_LIST = r"C:\Games\eldewrito\data\server\banlist.txt"

# ─────────────────────────────────────────────
#  BACKUP SYSTEM
# ─────────────────────────────────────────────
import shutil
from datetime import datetime

BACKUP_DIR = os.path.join(BASE_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

# Files to backup
FILES_TO_BACKUP = [
    "stats.json",
    "bans.json",
    "warnings.json",
    "mods.json",
    "memory.txt",
    "match_history.json",
    "rotation.json",
    "config.txt",
    "cortana_bot.py",
]

# Maximum number of backups to keep (0 = unlimited)
MAX_BACKUPS = 30

# ─────────────────────────────────────────────
#  LOGGING SYSTEM
# ─────────────────────────────────────────────
import logging
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
log_file = os.path.join(LOGS_DIR, "cortana.log")
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

logger = logging.getLogger('CortanaBot')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Replace all logger.info() statements with logger.info()
# Example:
# logger.info(f"[RCON] Connected") - logger.info(f"[RCON] Connected")

# ─────────────────────────────────────────────
#  STATIC CONFIG
# ─────────────────────────────────────────────
RCON_HOST = "localhost"
HTTP_API = f"http://{RCON_HOST}:11775"
CHAT_LOG_PATH = r"C:\Games\eldewrito\logs\chat.log"
BOT_NAME = "Cortana"
BOT_PREFIX = "Cortana:"
PLAYER_COOLDOWN = 30
MAX_QUEUE_SIZE = 3
CHAT_MEMORY_SIZE = 100

OLLAMA_API = "http://localhost:11434"
OLLAMA_MODEL = "huihui_ai/gemma3-abliterated:1b"

AFK_TIMEOUT_MINUTES = 0
AFK_CHECK_INTERVAL = 60

ANNOUNCEMENTS = []
ANNOUNCEMENT_INTERVAL = 600

ROTATION_VOTE_WAIT = 25
ROTATION_CHECK_INTERVAL = 5

IGNORED_SENDER_NAMES = {"bot"}

# ─────────────────────────────────────────────
#  TTS (Text-to-Speech)
# ─────────────────────────────────────────────
def speak_to_game(text):
    """Generate TTS audio using Google TTS and play it."""
    try:
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_audio.close()

        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(temp_audio.name)

        pygame.mixer.init()
        pygame.mixer.music.load(temp_audio.name)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        pygame.mixer.quit()
        os.unlink(temp_audio.name)

    except Exception as e:
        logger.info(f"[TTS ERROR] {e}")

# ─────────────────────────────────────────────
#  KEYWORDS & PATTERNS
# ─────────────────────────────────────────────
CURRENT_INFO_KEYWORDS = [
    "today", "now", "current", "latest", "recent", "news", "right now",
    "score", "winner", "update", "new", "release", "weather", "temperature",
    "price", "cost", "stock", "crypto", "bitcoin", "match"
]
EXPLICIT_SEARCH_KEYWORDS = [
    "search", "find", "look up", "google", "youtube", "video", "watch", "link", "url"
]

SLUR_PATTERNS = [
    r'\bn[i!1]+g+[e3]+r\b', r'\bf+a+g+[o0]+t\b', r'\bk+[i!1]+k+[e3]\b',
    r'\bs+p+[i!1]+c\b', r'\br+[e3]+t+[a4]+r+d\b'
]

SPAM_THRESHOLD = 5
SPAM_WINDOW = 10
CAPS_THRESHOLD = 0.7
CAPS_MIN_LENGTH = 15
WARN_KICK_THRESHOLD = 3
WARN_TEMPBAN_DURATION = 5

# ─────────────────────────────────────────────
#  PERMISSIONS
# ─────────────────────────────────────────────
ADMIN_ONLY_CMDS = {
    "addmod", "removemod",
    "backup", "restore", "backuplist",
    "discord"
}

MOD_CMDS = {
    "on", "off", "status", "clear", "cooldown", "automod",
    "map", "maps", "mode", "modes", "start",
    "kick", "ban", "tempban", "unban", "banlist",
    "warn", "warnings", "clearwarnings",
    "mute", "unmute", "reloadvoting", "pm",
    "mystats", "stats", "gamestatus",
    "provider", "local", "memory", "forget", "modlist",
    "servername", "serverpassword", "teams",
    "votingoptions", "revotes", "votepass", "votingsystem",
    "votingon", "votingoff", "shouldannounce", "announce",
    "rotation", "nextmap", "shufflerotation", "afk",
    "loadbalance", "say", "voice", "reload", "debugall", "dewritos", "balance", "bet", "leaderboard", "topdewritos",
}

# ─────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────
SYSTEM_PROMPT = "You are Cortana. One short sentence answers. No lists, no markdown, no fluff. Be witty but direct."

# ── Config Loader ─────────────────────────────

def load_config() -> dict:
    config = {}
    if not os.path.exists(CONFIG_FILE):
        logger.info(f"[CONFIG] Creating template at {CONFIG_FILE}")
        with open(CONFIG_FILE, "w") as f:
            f.write("GROQ_API_KEY=your-groq-key-here\n")
            f.write("CEREBRAS_API_KEY=your-cerebras-key-here\n")
            f.write("MISTRAL_API_KEY=your-mistral-key-here\n")
            f.write("OPENROUTER_API_KEY=your-openrouter-key-here\n")
            f.write("RCON_PASSWORD=your-rcon-password\n")
            f.write("RCON_PORT=11776\n")
            f.write("OWNER_UUID=your-uuid-here\n")
            f.write("OWNER_PRIVKEY=your-privkey-here\n")
            f.write("# Discord Bridge (optional)\n")
            f.write("DISCORD_WEBHOOK_URL=your-webhook-url-here\n")
            f.write("DISCORD_BOT_TOKEN=your-bot-token-here\n")
            f.write("DISCORD_CHANNEL_ID=your-channel-id-here\n")
        return config
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
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
    logger.info(f"[CONFIG] Loaded: {', '.join(config.keys())}")
    return config

# ── Player Stats ──────────────────────────────

def load_stats() -> dict:
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_stats(stats: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def update_player_stats(player_name: str, player_uid: str, kills: int, deaths: int, score: int, wins: int = 0):
    stats = load_stats()
    key = player_uid or player_name.lower()
    if key not in stats:
        stats[key] = {
            "name": player_name, "uid": player_uid,
            "kills": 0, "deaths": 0, "score": 0,
            "wins": 0, "matches": 0, "first_seen": datetime.now().strftime("%Y-%m-%d")
        }
    stats[key]["name"] = player_name
    stats[key]["kills"] += kills
    stats[key]["deaths"] += deaths
    stats[key]["score"] += score
    stats[key]["wins"] += wins
    stats[key]["matches"] += 1
    stats[key]["last_seen"] = datetime.now().strftime("%Y-%m-%d")
    save_stats(stats)

def get_player_stats(player_name: str, player_uid: str = "") -> dict:
    stats = load_stats()
    # Search by UID first, then by name
    if player_uid:
        key = player_uid
        if key in stats:
            return stats[key]
    for key, data in stats.items():
        if data.get("name", "").lower() == player_name.lower():
            return data
    return {}

def format_stats(data: dict) -> str:
    if not data:
        return "No stats found."
    name = data.get("name", "?")
    kills = data.get("kills", 0)
    deaths = data.get("deaths", 0)
    score = data.get("score", 0)
    wins = data.get("wins", 0)
    matches = data.get("matches", 0)
    kd = round(kills / deaths, 2) if deaths > 0 else kills
    return (f"{name} — K:{kills} D:{deaths} KD:{kd} "
            f"Score:{score} Wins:{wins} Matches:{matches}")

# ── Dewritos Credits System ─────────────────────────────

DEWRITOS_FILE = os.path.join(BASE_DIR, "dewritos.json")

def load_dewritos() -> dict:
    if not os.path.exists(DEWRITOS_FILE):
        return {}
    try:
        with open(DEWRITOS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_dewritos(dewritos: dict):
    with open(DEWRITOS_FILE, "w") as f:
        json.dump(dewritos, f, indent=2)

def get_dewritos(player_uid: str, player_name: str) -> int:
    dewritos = load_dewritos()
    if player_uid not in dewritos:
        dewritos[player_uid] = {"name": player_name, "balance": 100, "total_earned": 0, "total_bet": 0, "bets_won": 0, "bets_lost": 0}
        save_dewritos(dewritos)
    return dewritos[player_uid]["balance"]

def update_dewritos(player_uid: str, player_name: str, amount: int, reason: str = ""):
    dewritos = load_dewritos()
    if player_uid not in dewritos:
        dewritos[player_uid] = {"name": player_name, "balance": 100, "total_earned": 0, "total_bet": 0, "bets_won": 0, "bets_lost": 0}
    dewritos[player_uid]["balance"] += amount
    dewritos[player_uid]["name"] = player_name
    if amount > 0:
        dewritos[player_uid]["total_earned"] += amount
    save_dewritos(dewritos)

def award_match_dewritos(winner_name: str, winner_uid: str, participants: list):
    update_dewritos(winner_uid, winner_name, 50, "Match win")
    for p in participants:
        uid = p.get("uid", "")
        name = p.get("name", "")
        if uid and uid != winner_uid:
            update_dewritos(uid, name, 10, "Match participation")

# ── Betting System ─────────────────────────────

BETS_FILE = os.path.join(BASE_DIR, "bets.json")

def load_bets() -> dict:
    if not os.path.exists(BETS_FILE):
        return {}
    try:
        with open(BETS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_bets(bets: dict):
    with open(BETS_FILE, "w") as f:
        json.dump(bets, f, indent=2)

def place_bet(player_uid: str, player_name: str, amount: int, bet_type: str, target: str):
    dewritos = get_dewritos(player_uid, player_name)
    if amount < 10:
        return False, "Minimum bet is 10 Dewritos."
    if amount > dewritos:
        return False, f"Insufficient Dewritos. You have {dewritos}."
    update_dewritos(player_uid, player_name, -amount, f"Bet placed")
    bets = load_bets()
    bet_id = f"{player_uid}_{int(time.time())}"
    bets[bet_id] = {"player_uid": player_uid, "player_name": player_name, "amount": amount, "bet_type": bet_type, "target": target, "placed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "resolved": False}
    save_bets(bets)
    return True, f"Bet placed! {amount} Dewritos on {bet_type}: {target}"

def resolve_bets(winner_name: str, winner_uid: str, winning_team: str = None, top_killer: str = None):
    bets = load_bets()
    payouts = []
    for bet_id, bet in bets.items():
        if bet.get("resolved"):
            continue
        won = False
        if bet["bet_type"] == "winner" and bet["target"].lower() == winner_name.lower():
            won = True
        elif bet["bet_type"] == "top_killer" and top_killer and bet["target"].lower() == top_killer.lower():
            won = True
        elif bet["bet_type"] == "team" and winning_team and bet["target"].lower() == winning_team.lower():
            won = True
        
        if won:
            payout = bet["amount"] * 2
            update_dewritos(bet["player_uid"], bet["player_name"], payout, f"Bet won")
            payouts.append(f"{bet['player_name']} won {payout} Dewritos!")
        bet["resolved"] = True
    save_bets(bets)
    for payout in payouts[:3]:
        send_chat(payout)

def get_leaderboard() -> list:
    dewritos = load_dewritos()
    sorted_players = sorted(dewritos.items(), key=lambda x: x[1].get("balance", 0), reverse=True)
    return [(uid, data) for uid, data in sorted_players[:10]]

# ── Rotation ──────────────────────────────────

def load_rotation() -> list:
    if not os.path.exists(ROTATION_FILE):
        default = [
            {"map": "Guardian", "mode": "MLG TS 8"},
            {"map": "Valhalla", "mode": "MLG FFA 8"},
        ]
        with open(ROTATION_FILE, "w") as f:
            json.dump(default, f, indent=2)
        logger.info("[ROTATION] Created default rotation.json")
        return default
    try:
        with open(ROTATION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_rotation(rotation: list):
    with open(ROTATION_FILE, "w") as f:
        json.dump(rotation, f, indent=2)

# ── Match History ─────────────────────────────

def save_match(match_data: dict):
    history = []
    if os.path.exists(MATCH_LOG_FILE):
        try:
            with open(MATCH_LOG_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass
    history.append(match_data)
    history = history[-100:]
    with open(MATCH_LOG_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ── Game Variant & Map Scanners ───────────────

def scan_variants() -> dict:
    """Recursively scan for variant files"""
    variants = {}
    if not os.path.exists(GAME_VARIANTS_DIR):
        logger.info(f"[VARIANTS] Not found: {GAME_VARIANTS_DIR}")
        return variants
    
    # Generic names to skip
    skip_names = {"variant", "sandbox", "default", "unnamed"}
    
    for root, dirs, files in os.walk(GAME_VARIANTS_DIR):
        for file in files:
            if file.endswith(('.zombiez', '.slayer', '.ctf', '.koth', '.oddball')):
                full_path = os.path.join(root, file)
                folder_name = os.path.basename(root)
                if folder_name.lower() not in variants:
                    variants[folder_name.lower()] = full_path
                
                # Add filename without extension, but skip generic names
                name = os.path.splitext(file)[0]
                if (name.lower() not in variants and 
                    name.lower() != folder_name.lower() and 
                    name.lower() not in skip_names):
                    variants[name.lower()] = full_path
    
    return variants

def scan_maps() -> list:
    maps = []
    if not os.path.exists(GAME_MAPS_DIR):
        logger.info(f"[MAPS] Not found: {GAME_MAPS_DIR}")
        return maps
    
    for item in os.listdir(GAME_MAPS_DIR):
        item_path = os.path.join(GAME_MAPS_DIR, item)
        if os.path.isdir(item_path):
            maps.append(item.lower())  # <-- Add .lower()
        elif item.endswith('.map') or item.endswith('.bin'):
            maps.append(os.path.splitext(item)[0].lower())  # <-- Add .lower()
    
    return sorted(maps)

def get_mod_from_map_file(map_path: str) -> str:
    """Read the mod name from the .map file at offset 0xE1FC"""
    try:
        sandbox_map = os.path.join(map_path, "sandbox.map")
        if not os.path.exists(sandbox_map):
            return "base"
        
        with open(sandbox_map, 'rb') as f:
            f.seek(0xE1FC)
            mod_name_bytes = f.read(128)
            mod_name = mod_name_bytes.decode('utf-16le', errors='ignore').split('\x00')[0]
            
            if mod_name and len(mod_name) > 2:
                return mod_name
    except Exception as e:
        logger.info(f"[MAP] Error reading mod: {e}")
    
    return "base"

# Map internal mod names to actual .pak filenames
MOD_PAK_MAPPING = {
    "customization+": "customization_173b1d9d_v4_5.pak",
    "Customization++": "customization_173b1d9d_v4_5.pak",
    "customization": "customization_173b1d9d_v4_5.pak",
    "customization++": "customization_173b1d9d_v4_5.pak",
    "halo 3": "halo_3_pack_39106b4c_v2_3.pak",
    "kn map pack 1": "kn_map_pack_1_e61a5929_v1_6.pak",
    "kn map pack 2": "kn_map_pack_2_0a671a0e_v1_6.pak",
    "h3ek": "H3EK_CUSTOM_Maps.pak",
}

def get_mod_pak_name(raw_mod_name: str) -> str:
    """Convert internal mod name to actual .pak filename"""
    if not raw_mod_name or raw_mod_name == "base":
        return "base"
    
    raw_lower = raw_mod_name.lower().strip()
    
    for key, pak_name in MOD_PAK_MAPPING.items():
        if key in raw_lower or raw_lower in key:
            return pak_name
    
    return "base"
    
    
    # Map variants that need a base map loaded first
VARIANT_BASE_MAPS = {
    "Fast CW 1.0": "s3d_edge",
    "Fatkid Fort 3": "Guardian",
}

def get_base_map_for_variant(map_name: str) -> str:
    """Return the base map for a variant, or None if it's a regular map"""
    return VARIANT_BASE_MAPS.get(map_name)

# ── Warning System ────────────────────────────

def load_warnings() -> dict:
    if not os.path.exists(WARNINGS_FILE):
        return {}
    try:
        with open(WARNINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_warnings(w: dict):
    with open(WARNINGS_FILE, "w") as f:
        json.dump(w, f, indent=2)

def add_warning(player_name: str, player_uid: str, reason: str, moderator: str = "AutoMod") -> int:
    warnings = load_warnings()
    key = player_uid or player_name.lower()
    if key not in warnings:
        warnings[key] = {"name": player_name, "uid": player_uid, "count": 0, "history": []}
    warnings[key]["count"] += 1
    warnings[key]["name"] = player_name
    warnings[key]["history"].append({"reason": reason, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "moderator": moderator})
    save_warnings(warnings)
    
    # Log the warning
    log_warning_action(player_name, player_uid, moderator, reason, warnings[key]["count"])
    
    return warnings[key]["count"]

def get_warnings(player_name: str, player_uid: str) -> dict:
    warnings = load_warnings()
    key = player_uid or player_name.lower()
    return warnings.get(key, {"name": player_name, "uid": player_uid, "count": 0, "history": []})

def clear_warnings(player_name: str) -> bool:
    warnings = load_warnings()
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

# ── Ban/Warning Logging ─────────────────────────

def log_ban_action(action: str, player_name: str, player_uid: str, moderator: str, reason: str, duration: str = "permanent"):
    """Log ban actions to a text file"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(BAN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {action} | Player: {player_name} (UID: {player_uid}) | Mod: {moderator} | Duration: {duration} | Reason: {reason}\n")
    except Exception as e:
        logger.warning(f"[LOG] Failed to write ban log: {e}")

def log_warning_action(player_name: str, player_uid: str, moderator: str, reason: str, warning_count: int):
    """Log warning actions to a text file"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(WARNING_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] WARNING #{warning_count} | Player: {player_name} (UID: {player_uid}) | Mod: {moderator} | Reason: {reason}\n")
    except Exception as e:
        logger.info(f"[LOG] Failed to write warning log: {e}")

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

def remove_mod(identifier: str) -> bool:
    """Remove a moderator by name or UID"""
    mods = load_mods()
    identifier_lower = identifier.lower().replace("0x", "")
    
    new_mods = []
    found = False
    for m in mods:
        # Check by name
        if m.get("name", "").lower() == identifier_lower:
            found = True
            continue
        # Check by UID
        if m.get("uid", "").lower().replace("0x", "") == identifier_lower:
            found = True
            continue
        new_mods.append(m)
    
    if found:
        save_mods(new_mods)
        return True
    return False

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

def add_ban(name: str, uid: str, ip: str, reason: str = "Banned", duration_minutes: int = None, moderator: str = "AutoMod"):
    bans = load_bans()
    now = datetime.now()
    
    duration_str = f"{duration_minutes} minutes" if duration_minutes else "permanent"
    expires_at = (now + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S") if duration_minutes else None
    
    entry = {
        "name": name, "uid": uid, "ip": ip, "reason": reason,
        "banned_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expires_at,
        "permanent": duration_minutes is None,
        "moderator": moderator
    }
    bans = [b for b in bans if b.get("uid") != uid and b.get("name", "").lower() != name.lower()]
    bans.append(entry)
    save_bans(bans)
    
    # Add to ElDewrito ban list
    try:
        # Read existing ban list to avoid duplicates
        existing_lines = []
        if os.path.exists(ELDEWRITO_BAN_LIST):
            with open(ELDEWRITO_BAN_LIST, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()
        
        # Remove any existing entries for this player
        new_lines = []
        for line in existing_lines:
            line_stripped = line.strip()
            # Skip comments and empty lines
            if line_stripped.startswith("#") or not line_stripped:
                new_lines.append(line)
                continue
            
            # Remove lines that match this player
            should_remove = False
            if uid and f"uid {uid}" in line:
                should_remove = True
            elif name and f"name {name}" in line:
                should_remove = True
            elif ip and f"ip {ip}" in line:
                should_remove = True
            
            if not should_remove:
                new_lines.append(line)
        
        # Write back without duplicates, then add new bans
        with open(ELDEWRITO_BAN_LIST, "w", encoding="utf-8") as f:
            # Write existing lines (without this player's bans)
            f.writelines(new_lines)
            
            # Add new ban entries in the correct format
            if uid and len(uid) > 5:
                f.write(f"uid {uid}\n")
            if ip and ip not in ("127.0.0.1", "localhost", ""):
                f.write(f"ip {ip}\n")
            f.write(f"name {name}\n")
        
        logger.info(f"[BAN] Added {name} to ElDewrito ban list")
    except Exception as e:
        logger.info(f"[BAN] Failed to write to ElDewrito ban list: {e}")
    
    # Log the ban
    log_ban_action("BAN", name, uid, moderator, reason, duration_str)

def remove_ban(name: str, moderator: str = "Unknown") -> bool:
    bans = load_bans()
    
    # Find the ban to remove
    target_uid = None
    target_name = None
    
    for ban in bans:
        if ban.get("name", "").lower() == name.lower():
            target_name = ban.get("name", "")
            target_uid = ban.get("uid", "")
            log_ban_action("UNBAN", ban.get("name", name), ban.get("uid", "unknown"), moderator, "Unbanned", "N/A")
            break
    
    if not target_name:
        target_name = name
    
    # Remove from local ban list
    new_bans = [b for b in bans if b.get("name", "").lower() != name.lower()]
    save_bans(new_bans)
    
    # Remove from ElDewrito ban list - find and remove ALL lines for this player
    try:
        if not os.path.exists(ELDEWRITO_BAN_LIST):
            logger.info(f"[BAN] Ban list file not found")
            return True
        
        with open(ELDEWRITO_BAN_LIST, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        logger.info(f"[DEBUG] Read {len(lines)} lines from banlist.txt")
        
        # First, find the IP line that belongs to this player by looking near the UID
        found_ip = None
        for i, line in enumerate(lines):
            if target_uid and f"uid {target_uid}" in line:
                # Look for ip line in the surrounding lines (within 5 lines)
                for j in range(max(0, i-5), min(len(lines), i+6)):
                    if lines[j].strip().startswith("ip "):
                        found_ip = lines[j].strip().replace("ip ", "")
                        logger.info(f"[DEBUG] Found associated IP: {found_ip}")
                        break
                break
        
        # Now rewrite the file, removing ALL lines for this player
        with open(ELDEWRITO_BAN_LIST, "w", encoding="utf-8") as f:
            for line in lines:
                line_stripped = line.strip()
                should_remove = False
                
                # Remove name line
                if target_name and line_stripped == f"name {target_name}":
                    logger.info(f"[BAN] Removing name line: {line_stripped}")
                    should_remove = True
                # Remove uid line
                elif target_uid and line_stripped == f"uid {target_uid}":
                    logger.info(f"[BAN] Removing uid line: {line_stripped}")
                    should_remove = True
                # Remove ip line if it matches the found IP
                elif found_ip and line_stripped == f"ip {found_ip}":
                    logger.info(f"[BAN] Removing ip line: {line_stripped}")
                    should_remove = True
                # Also check if line contains the name (partial match fallback)
                elif target_name and target_name.lower() in line_stripped.lower():
                    logger.info(f"[BAN] Removing line (contains name): {line_stripped}")
                    should_remove = True
                
                if not should_remove:
                    f.write(line)
        
        logger.info(f"[BAN] Unban complete for {target_name}")
        
    except Exception as e:
        logger.info(f"[BAN] Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # RCON unban commands
    if target_uid:
        send_rcon(f"Server.Unban uid {target_uid}")
        time.sleep(0.3)
    if target_name:
        send_rcon(f'Server.Unban name "{target_name}"')
        time.sleep(0.3)
    
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

# ── Player Name Detection (for multi-word names) ──

def find_player_name(args: list, start_index: int = 0) -> tuple:
    """
    Find a player name from command arguments.
    Returns (player_name, next_index) where next_index is where the rest starts.
    """
    # Get current players from server
    players = get_server_info().get("players", [])
    player_names = [p.get("name", "") for p in players]
    
    # Try from longest to shortest possible name (max 5 words)
    max_words = min(5, len(args) - start_index)
    for word_count in range(max_words, 0, -1):
        possible_name = " ".join(args[start_index:start_index + word_count])
        # Remove @ symbol if present at start of first word
        if possible_name.startswith("@"):
            possible_name = possible_name[1:]
        # Check if this matches any player (case-insensitive)
        for p_name in player_names:
            if p_name.lower() == possible_name.lower():
                return possible_name, start_index + word_count
    
    # If no exact match, return first word as name
    first_arg = args[start_index]
    if first_arg.startswith("@"):
        first_arg = first_arg[1:]
    return first_arg, start_index + 1

def get_target_name(args: list) -> tuple:
    """Extract player name from args (supports @ prefix and multi-word names). Returns (name, next_index)"""
    # If first argument starts with @, it's likely the whole name might be split
    # Example: ["@Jeffrey", "Epstein"] should become "Jeffrey Epstein"
    
    first_arg = args[0]
    if first_arg.startswith("@"):
        # Remove @ from first arg
        args[0] = first_arg[1:]
    
    return find_player_name(args, 0)

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
        _apply_warning(player_name, player_uid, player_ip, f"AutoMod: {violation}")

def _apply_warning(player_name: str, player_uid: str, player_ip: str, reason: str):
    count = add_warning(player_name, player_uid, reason, moderator="AutoMod")
    remaining = max(0, WARN_KICK_THRESHOLD - count)
    if count < WARN_KICK_THRESHOLD:
        send_chat(f"@{player_name}: Warning {count}/{WARN_KICK_THRESHOLD} — {reason}. {remaining} left before action.")
    elif count == WARN_KICK_THRESHOLD:
        send_chat(f"{player_name} has been kicked after {count} warnings.")
        send_rcon(f"Server.KickPlayer {player_name}")
        add_warning(player_name, player_uid, "Kicked after warning threshold")
    else:
        target_info = get_player_info(player_name)
        target_ip = target_info.get("ip", player_ip)
        add_ban(player_name, player_uid, target_ip, "Temp banned: repeated violations", WARN_TEMPBAN_DURATION)
        send_rcon(f"Server.KickPlayer {player_name}")
        send_chat(f"{player_name} has been temporarily banned for {WARN_TEMPBAN_DURATION} minutes.")

# ── State ─────────────────────────────────────

# Connection & WebSocket
ws = None
ws_lock = threading.Lock()
ws_connected = False

# Bot State
bot_enabled = True
local_enabled = False
memory_enabled = True
automod_enabled = False
announce_enabled = True
rotation_enabled = False
afk_enabled = False
discord_enabled = False
stats_enabled = True
voice_enabled = False
load_balancing_enabled = False

# Queues & Cooldowns
player_last_ask = {}
queue_lock = threading.Lock()
pending_count = 0
chat_memory = deque(maxlen=CHAT_MEMORY_SIZE)

# Game State
available_variants = {}
available_maps = []
known_players = set()
afk_tracker = {}
last_game_status = ""
first_blood_given = False
rotation_index = 0
active_provider = "auto"

# Provider Cycling
provider_failures = {}
current_provider_index = 0
PROVIDER_FAILURE_THRESHOLD = 3
PROVIDER_COOLDOWN_SECONDS = 60

# API Keys (loaded from config)
GROQ_API_KEY = ""
CEREBRAS_API_KEY = ""
MISTRAL_API_KEY = ""
OPENROUTER_API_KEY = ""

# Server Config
RCON_PASSWORD = ""
RCON_PORT = 11776
OWNER_UUID = ""
OWNER_PRIVKEY = ""

# Discord
DISCORD_WEBHOOK_URL = ""
DISCORD_BOT_TOKEN = ""
DISCORD_CHANNEL_ID = ""

LOG_PATTERN = re.compile(
    r'^\[[\d/]+ [\d:]+\] <([^/]+)/([^/]+)/([^\>]+)> (.+)$'
)

def create_backup() -> str:
    """Create a timestamped backup of all important files"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_folder = os.path.join(BACKUP_DIR, timestamp)
    os.makedirs(backup_folder, exist_ok=True)
    
    # Call backup_script() to save a copy in the main directory
    backup_script()  # <-- ADD THIS LINE
    
    backed_up = 0
    for filename in FILES_TO_BACKUP:
        src = os.path.join(BASE_DIR, filename)
        if os.path.exists(src):
            dst = os.path.join(backup_folder, filename)
            shutil.copy2(src, dst)
            backed_up += 1
            logger.debug(f"Backed up: {filename}")
    
    # Also backup the logs directory
    logs_dir = os.path.join(BASE_DIR, "logs")
    if os.path.exists(logs_dir):
        backup_logs = os.path.join(backup_folder, "logs")
        shutil.copytree(logs_dir, backup_logs)
        logger.debug(f"Backed up logs directory")
    
    # Clean up old backups
    cleanup_old_backups()
    
    logger.info(f"Backup created: {timestamp} ({backed_up} files)")
    return backup_folder

def cleanup_old_backups():
    """Delete old backups, keeping only the most recent MAX_BACKUPS"""
    if MAX_BACKUPS <= 0:
        return
    
    try:
        # Get all backup folders with their creation times
        backups = []
        for folder in os.listdir(BACKUP_DIR):
            folder_path = os.path.join(BACKUP_DIR, folder)
            if os.path.isdir(folder_path):
                # Try to parse timestamp from folder name
                try:
                    timestamp = datetime.strptime(folder, "%Y-%m-%d_%H-%M-%S")
                    backups.append((timestamp, folder_path))
                except ValueError:
                    # If folder name isn't a timestamp, skip it
                    pass
        
        # Sort by timestamp (oldest first)
        backups.sort(key=lambda x: x[0])
        
        # Delete old backups
        to_delete = len(backups) - MAX_BACKUPS
        for i in range(to_delete):
            shutil.rmtree(backups[i][1])
            logger.info(f"Deleted old backup: {backups[i][0].strftime('%Y-%m-%d %H:%M:%S')}")
    
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")

def get_backup_list() -> list:
    """Return list of available backups with timestamps"""
    backups = []
    for folder in os.listdir(BACKUP_DIR):
        folder_path = os.path.join(BACKUP_DIR, folder)
        if os.path.isdir(folder_path):
            try:
                timestamp = datetime.strptime(folder, "%Y-%m-%d_%H-%M-%S")
                backups.append((timestamp, folder))
            except ValueError:
                pass
    backups.sort(reverse=True)  # Newest first
    return backups

# ========== ADD backup_script() HERE ==========
def backup_script():
    """Create a dated copy of the script in the main directory"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    script_backup = os.path.join(BASE_DIR, f"cortana_bot_backup_{timestamp}.py")
    shutil.copy2(os.path.join(BASE_DIR, "cortana_bot.py"), script_backup)
    logger.info(f"Script backup created: {script_backup}")
    
    # Clean up old script backups (keep last 10)
    script_backups = [f for f in os.listdir(BASE_DIR) if f.startswith("cortana_bot_backup_") and f.endswith(".py")]
    script_backups.sort(reverse=True)
    for old_backup in script_backups[10:]:
        os.remove(os.path.join(BASE_DIR, old_backup))
        logger.info(f"Deleted old script backup: {old_backup}")
# ==============================================

def restore_backup(backup_name: str) -> bool:
    """Restore files from a specific backup"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        logger.error(f"Backup not found: {backup_name}")
        return False
    
    try:
        # Create a safety backup of current state before restoring
        safety_backup = create_backup()
        logger.info(f"Created safety backup before restore: {safety_backup}")
        
        # Restore files
        for filename in FILES_TO_BACKUP:
            src = os.path.join(backup_path, filename)
            dst = os.path.join(BASE_DIR, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                logger.info(f"Restored: {filename}")
        
        logger.info(f"Restored from backup: {backup_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        return False

# ── RCON ─────────────────────────────────────

def connect_rcon():
    global ws, ws_connected
    logger.info(f"[RCON] Connecting to ws://{RCON_HOST}:{RCON_PORT} ...")
    try:
        ws = create_connection(
            f"ws://{RCON_HOST}:{RCON_PORT}",
            subprotocols=["dew-rcon"],
            timeout=10
        )
        ws.send(RCON_PASSWORD)
        time.sleep(0.5)
        ws_connected = True
        logger.info("[RCON] Connected and authenticated!")
        return True
    except Exception as e:
        ws_connected = False
        logger.error(f"[RCON] Connection failed: {e}")
        return False

def reconnect_rcon():
    global ws_connected
    while True:
        time.sleep(15)
        if not ws_connected:
            logger.info("[RCON] Attempting reconnect...")
            if connect_rcon():
                send_chat(f"{BOT_NAME} reconnected.")

def send_chat(message: str):
    global ws_connected
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
                logger.info(f"[BOT] {full_line}")
                
                # ========== ADD THIS BLOCK HERE ==========
                if voice_enabled:
                    speak_to_game(line)  # Speak the message without the prefix
                # ==========================================
                
            except Exception as e:
                logger.info(f"[BOT] Send failed: {e}")
                ws_connected = False
            time.sleep(0.4)

def send_rcon(command: str):
    global ws_connected
    with ws_lock:
        try:
            ws.send(command)
            return True
        except Exception as e:
            logger.info(f"[RCON] Failed: {e}")
            ws_connected = False
            return False

# ── Discord Bridge ────────────────────────────

def send_to_discord(player_name: str, message: str):
    """Send a game chat message to Discord via webhook (game - Discord)."""
    if not discord_enabled or not DISCORD_WEBHOOK_URL:
        return
    try:
        payload = {
            "username": f"[ElDewrito] {player_name}",
            "content": message,
            "avatar_url": "https://i.imgur.com/4M34hi2.png"
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        logger.info(f"[DISCORD] Webhook failed: {e}")

def start_discord_bot():
    """Start the Discord bot that reads Discord messages and forwards to game (Discord - game)."""
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        logger.info("[DISCORD] Bot token or channel ID not set — Discord - game bridge disabled.")
        return

    try:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            logger.info(f"[DISCORD] Bot connected as {client.user}")

        @client.event
        async def on_message(message):
            if message.author.bot:
                return
            if str(message.channel.id) != str(DISCORD_CHANNEL_ID):
                return
            if not discord_enabled:
                return
            # Forward Discord message to game
            content = message.content
            author = message.author.display_name
            # Trim long messages
            if len(content) > 150:
                content = content[:147] + "..."
            send_chat(f"[Discord] {author}: {content}")

        def run_bot():
            asyncio.run(client.start(DISCORD_BOT_TOKEN))

        threading.Thread(target=run_bot, daemon=True).start()

    except ImportError:
        logger.info("[DISCORD] discord.py not installed. Run: pip install discord.py")
    except Exception as e:
        logger.info(f"[DISCORD] Bot failed to start: {e}")

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
        json={"model": "llama-3.3-70b-versatile", "messages": messages, "temperature": 0.55, "max_tokens": 125}, timeout=10)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Groq {r.status_code}")

def call_cerebras(messages):
    r = requests.post("https://api.cerebras.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"},
        json={"model": "qwen-3-235b-a22b-instruct-2507", "messages": messages, "temperature": 0.55, "max_tokens": 125}, timeout=10)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Cerebras {r.status_code}")

def call_mistral(messages):
    r = requests.post("https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest", "messages": messages, "temperature": 0.55, "max_tokens": 125}, timeout=10)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Mistral {r.status_code}")

def call_openrouter(messages):
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/cortana-bot-eldewrito", "X-Title": "Cortana Bot"},
        json={"model": "openrouter/free", "messages": messages, "temperature": 0.55, "max_tokens": 125}, timeout=10)
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"].get("content") or ""
        if not content:
            raise Exception("Empty response")
        return content.strip()
    raise Exception(f"OpenRouter {r.status_code}")

def call_local(messages):
    try:
        # Extract the user message
        user_message = ""
        system_message = ""
        
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
            elif msg.get("role") == "system":
                system_message = msg.get("content", "")
        
        # Shorten system prompt for local model
        if len(system_message) > 200:
            system_message = "You are Cortana. Answer in 1 short sentence. Be direct and slightly witty."
        
        # Format as a simple conversation
        full_prompt = f"{system_message}\n\nUser: {user_message}\n\nCortana:"
        
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.55,      # Fine-tuned: more focused
                    "num_predict": 65,        # Fine-tuned: shorter responses
                    "top_p": 0.85,            # Fine-tuned: slightly more focused
                    "repeat_penalty": 1.1,    # NEW: prevents repetition
                    "stop": ["\nUser:", "\n\n"]  # NEW: stops at natural points
                }
            },
            timeout=45  # Fine-tuned: faster fallback
        )
        
        if r.status_code == 200:
            response = r.json().get("response", "").strip()
            if not response:
                raise Exception("Empty response from model")
            # Clean up any repetition of the prompt
            if response.startswith("Cortana:"):
                response = response[8:].strip()
            # Remove any trailing incomplete sentences
            if response.endswith(","):
                response = response[:-1] + "..."
            return response
        raise Exception(f"Ollama {r.status_code}")
    except requests.exceptions.Timeout:
        logger.info("[LOCAL] Request timed out")
        raise Exception("Local model timeout")
    except Exception as e:
        logger.info(f"[LOCAL] Error: {e}")
        raise

def is_ollama_running() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return any(OLLAMA_MODEL in m.get("name", "") for m in models)
    except Exception:
        pass
    return False

CLOUD_PROVIDER_CHAIN = [
    ("groq",       call_groq,       lambda: GROQ_API_KEY),
    ("cerebras",   call_cerebras,   lambda: CEREBRAS_API_KEY),
    ("mistral",    call_mistral,    lambda: MISTRAL_API_KEY),
    ("openrouter", call_openrouter, lambda: OPENROUTER_API_KEY),
]

def ask_ai(player_name: str, question: str) -> str:
    logger.info(f"[AI] {player_name} asked: {question}")
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

{f'Info from search:{chr(10)}{search_ctx}{chr(10)}' if search_ctx else ''}
{player_name} asks: {question}"""}
        ]

        def trim(a): return a[:397] + "..." if len(a) > 400 else a

        # Local model first if enabled
        if local_enabled and is_ollama_running():
            try:
                return trim(call_local(messages))
            except Exception as e:
                logger.info(f"[AI] Local failed: {e} — falling back to cloud...")

        # Cloud providers with cycling
        attempts = 0
        max_attempts = len([n for n,_,h in CLOUD_PROVIDER_CHAIN if h()]) * 2
        
        while attempts < max_attempts:
            provider_name, provider_func = get_next_available_provider()
            if not provider_name:
                break
            
            try:
                answer = provider_func(messages)
                logger.info(f"[AI] Response from {provider_name.capitalize()}")
                if provider_name in provider_failures:
                    del provider_failures[provider_name]
                return trim(answer)
            except Exception as e:
                logger.info(f"[AI] {provider_name.capitalize()} failed: {e}")
                mark_provider_failure(provider_name)
                attempts += 1

        return "All AI providers are currently unavailable. Try again later."
    except Exception as e:
        logger.info(f"[AI] Unexpected error: {e}")
        return "An error occurred on my end. Try again."

def get_active_provider_name() -> str:
    if local_enabled:
        return f"Local ({OLLAMA_MODEL})"
    if active_provider != "auto":
        return active_provider.capitalize()
    for name, _, has_key in CLOUD_PROVIDER_CHAIN:
        if has_key():
            return f"{name.capitalize()} (auto)"
    return "None"

# ── API Provider Cycling ───────────────────────

def get_next_available_provider():
    """Cycle through providers, skipping failed ones"""
    global current_provider_index
    
    # If load balancing is disabled, just return the first working provider
    if not load_balancing_enabled:
        for name, call_fn, has_key in CLOUD_PROVIDER_CHAIN:
            if has_key():
                # Check if provider is on cooldown
                if name in provider_failures:
                    last_fail, fail_count = provider_failures[name]
                    if fail_count >= PROVIDER_FAILURE_THRESHOLD:
                        if time.time() - last_fail < PROVIDER_COOLDOWN_SECONDS:
                            continue
                        else:
                            del provider_failures[name]
                return name, call_fn
        return None, None
    
    # Load balancing is enabled - cycle through providers
    available = []
    for name, call_fn, has_key in CLOUD_PROVIDER_CHAIN:
        if has_key():
            if name in provider_failures:
                last_fail, fail_count = provider_failures[name]
                if fail_count >= PROVIDER_FAILURE_THRESHOLD:
                    if time.time() - last_fail < PROVIDER_COOLDOWN_SECONDS:
                        continue
                    else:
                        del provider_failures[name]
            available.append((name, call_fn))
    
    if not available:
        return None, None
    
    if current_provider_index >= len(available):
        current_provider_index = 0
    
    provider_name, provider_func = available[current_provider_index]
    current_provider_index = (current_provider_index + 1) % len(available)
    
    return provider_name, provider_func

def mark_provider_failure(provider_name: str):
    """Mark a provider as failed for cycling"""
    now = time.time()
    if provider_name in provider_failures:
        last_fail, count = provider_failures[provider_name]
        provider_failures[provider_name] = (now, count + 1)
    else:
        provider_failures[provider_name] = (now, 1)
    logger.info(f"[API] Marked {provider_name} as failed ({provider_failures[provider_name][1]}/{PROVIDER_FAILURE_THRESHOLD})")

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

    # Skip cooldown and queue limits for owner AND moderators
    if is_owner(player_uid) or is_mod(player_uid):
        with queue_lock:
            if pending_count >= MAX_QUEUE_SIZE:
                send_chat(f"@{player_name}: I'm currently occupied.")
                return False
            pending_count += 1
        threading.Thread(target=handle_ai_request, args=(player_name, question), daemon=True).start()
        return True

    # Regular players get cooldown and queue limits
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
    
    # Pass the IP to add_ban
    add_ban(target_name, target_uid, target_ip, f"Banned by {actor_name}", moderator=actor_name)
    send_rcon(f"Server.KickBanPlayer {target_name}")
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
    
    add_ban(target_name, target_uid, target_ip, f"Temp banned by {actor_name}", duration, moderator=actor_name)
    send_rcon(f"Server.KickPlayer {target_name}")
    send_chat(f"{target_name} has been banned for {duration} minutes.")
    return True

# ── Match Summary ─────────────────────────────

def process_match_end(info: dict):
    """Called when a match ends. Generates summary, saves stats, logs match."""
    players = info.get("players", [])
    map_name = info.get("map", "unknown")
    mode = info.get("variant", "unknown")

    if not players:
        return

    winner = max(players, key=lambda p: p.get("score", 0))
    most_kills = max(players, key=lambda p: p.get("kills", 0))
    most_deaths = max(players, key=lambda p: p.get("deaths", 0))

    w_name = winner.get("name", "?")
    w_score = winner.get("score", 0)
    k_name = most_kills.get("name", "?")
    k_kills = most_kills.get("kills", 0)
    d_name = most_deaths.get("name", "?")
    d_deaths = most_deaths.get("deaths", 0)

    parts = [f"Match over on {map_name} ({mode})."]
    if w_score > 0:
        parts.append(f"{w_name} wins with {w_score} points.")
    if k_name != w_name and k_kills > 0:
        parts.append(f"Most kills: {k_name} ({k_kills}).")
    if d_deaths > 0 and len(players) > 1:
        parts.append(f"Most deaths: {d_name} ({d_deaths}) — better luck next time.")

    send_chat(" ".join(parts))

    # Update persistent stats
    if stats_enabled:
        winner_uid = winner.get("uid", "")
        for p in players:
            name = p.get("name", "")
            uid = p.get("uid", "")
            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0)
            score = p.get("score", 0)
            won = 1 if uid == winner_uid and w_score > 0 else 0
            update_player_stats(name, uid, kills, deaths, score, won)

    # Save match to history
    match_data = {
        "map": map_name, "mode": mode, "winner": w_name,
        "players": [{"name": p.get("name"), "score": p.get("score", 0),
                     "kills": p.get("kills", 0), "deaths": p.get("deaths", 0)} for p in players],
        "played_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_match(match_data)

    # Post to Discord
    if discord_enabled and DISCORD_WEBHOOK_URL:
        discord_summary = f"**Match ended** — {map_name} ({mode})\n"
        discord_summary += f"🏆 Winner: **{w_name}** ({w_score} pts)\n"
        for p in sorted(players, key=lambda x: x.get("score", 0), reverse=True):
            discord_summary += f"• {p.get('name','?')} — K:{p.get('kills',0)} D:{p.get('deaths',0)} Score:{p.get('score',0)}\n"
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "Cortana", "content": discord_summary}, timeout=5)
        except Exception:
            pass

    # ========== DEWRITOS & BETTING ==========
    # Determine winning team (ElDewrito colors)
    winning_team = None
    winning_team_score = -1
    team_scores = info.get("teamScores", [])
    team_colors = ["red", "blue", "orange", "green", "brown", "pink", "gold", "purple"]
    
    if team_scores and len(team_scores) > 0:
        for i, score in enumerate(team_scores):
            if score > winning_team_score:
                winning_team_score = score
                if i < len(team_colors):
                    winning_team = team_colors[i]
                else:
                    winning_team = f"team_{i + 1}"
    
    # Award Dewritos and resolve bets
    if stats_enabled:
        winner_uid = winner.get("uid", "")
        award_match_dewritos(w_name, winner_uid, players)
        most_kills_name = most_kills.get("name", "")
        resolve_bets(w_name, winner_uid, winning_team, most_kills_name)

# ── Command Handler ───────────────────────────

def handle_command(player_name: str, player_uid: str, player_ip: str, command: str):
    global bot_enabled, PLAYER_COOLDOWN, player_last_ask, active_provider
    global local_enabled, memory_enabled, automod_enabled
    global announce_enabled, rotation_enabled, afk_enabled, discord_enabled, stats_enabled
    global rotation_index, load_balancing_enabled, voice_enabled
    global GROQ_API_KEY, CEREBRAS_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY
    global RCON_PASSWORD, RCON_PORT, OWNER_UUID, OWNER_PRIVKEY
    global DISCORD_WEBHOOK_URL, DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
    global rotation, available_variants, available_maps

    parts = command.strip().split()
    cmd = parts[0].lower() if parts else ""
    args = parts[1:]

    owner = is_owner(player_uid)
    mod_or_owner = is_mod_or_owner(player_uid)

    # ========== DEBUG COMMAND ==========
    if cmd == "debugall":
        if not owner:
            send_chat(f"@{player_name}: Debug command restricted to owner.")
            return
        send_chat(f"[DEBUG] Bot: {BOT_NAME}")
        send_chat(f"[DEBUG] RCON: {'Connected' if ws_connected else 'Disconnected'}")
        send_chat(f"[DEBUG] Owner: {owner}")
        send_chat(f"[DEBUG] Bot Enabled: {bot_enabled}")
        send_chat(f"[DEBUG] Voice Enabled: {voice_enabled}")
        send_chat(f"[DEBUG] Local Enabled: {local_enabled}")
        send_chat(f"[DEBUG] Rotation Enabled: {rotation_enabled}")
        info = get_server_info()
        send_chat(f"[DEBUG] Game Status: {info.get('status', 'unknown')}")
        send_chat(f"[DEBUG] Map: {info.get('map', 'unknown')}")
        send_chat(f"[DEBUG] Players: {info.get('numPlayers', 0)}/{info.get('maxPlayers', 0)}")
        send_chat(f"[DEBUG] Maps: {len(available_maps)}")
        send_chat(f"[DEBUG] Modes: {len(available_variants)}")
        send_chat(f"[DEBUG] Rotation: {len(rotation)}")
        providers = [n for n, _, h in CLOUD_PROVIDER_CHAIN if h()]
        send_chat(f"[DEBUG] AI Providers: {', '.join(p.capitalize() for p in providers) if providers else 'None'}")
        send_chat(f"[DEBUG] Ollama: {'Running' if is_ollama_running() else 'Not running'}")
        send_chat(f"[DEBUG] === End Debug ===")
        return

    # ========== DIRECT HANDLERS (Before permission checks) ==========
    if cmd == "reload":
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return
        try:
            logger.info(f"Reloading configuration by {player_name}")
            new_config = load_config()
            GROQ_API_KEY = new_config.get("GROQ_API_KEY", "")
            CEREBRAS_API_KEY = new_config.get("CEREBRAS_API_KEY", "")
            MISTRAL_API_KEY = new_config.get("MISTRAL_API_KEY", "")
            OPENROUTER_API_KEY = new_config.get("OPENROUTER_API_KEY", "")
            RCON_PASSWORD = new_config.get("RCON_PASSWORD", "")
            RCON_PORT = int(new_config.get("RCON_PORT", 11776))
            OWNER_UUID = new_config.get("OWNER_UUID", "").lower().replace("0x", "")
            OWNER_PRIVKEY = new_config.get("OWNER_PRIVKEY", "")
            DISCORD_WEBHOOK_URL = new_config.get("DISCORD_WEBHOOK_URL", "")
            DISCORD_BOT_TOKEN = new_config.get("DISCORD_BOT_TOKEN", "")
            DISCORD_CHANNEL_ID = new_config.get("DISCORD_CHANNEL_ID", "")
            rotation = load_rotation()
            available_variants = scan_variants()
            available_maps = scan_maps()
            logger.info("Configuration reloaded successfully")
            send_chat("Configuration reloaded successfully. Changes applied.")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            send_chat(f"Failed to reload config: {e}")
        return

    if cmd == "forget":
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return
        clear_memory()
        send_chat("Permanent memory cleared.")
        return

    if cmd == "memory" and args:
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return
        if args[0].lower() == "on":
            memory_enabled = True
            send_chat("Memory enabled.")
        elif args[0].lower() == "off":
            memory_enabled = False
            send_chat("Memory disabled.")
        else:
            send_chat("Usage: !ai memory on/off")
        return

    if cmd == "voice" and args:
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return
        if args[0].lower() == "on":
            voice_enabled = True
            send_chat("Voice responses enabled.")
        elif args[0].lower() == "off":
            voice_enabled = False
            send_chat("Voice responses disabled.")
        else:
            send_chat("Usage: !ai voice on/off")
        return

    if cmd == "local" and args:
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return
        if args[0].lower() == "on":
            if is_ollama_running():
                local_enabled = True
                send_chat(f"Local model enabled ({OLLAMA_MODEL}).")
            else:
                send_chat(f"Ollama not running. Pull model: ollama pull {OLLAMA_MODEL}")
        else:
            local_enabled = False
            send_chat("Local model disabled.")
        return

    if cmd == "modlist":
        if not mod_or_owner:
            send_chat(f"@{player_name}: You don't have permission for that.")
            return
        mods = load_mods()
        if not mods:
            send_chat("No moderators assigned.")
        else:
            send_chat(f"Moderators: {', '.join(m.get('name','?') for m in mods)}")
        return

    if cmd == "gamestatus":
        info = get_server_info()
        status = info.get("status", "unknown")
        send_chat(f"Game status from API: '{status}'")
        return

    # ========== DEWRITOS COMMANDS ==========
    if cmd == "dewritos" or cmd == "balance":
        if not args:
            balance = get_dewritos(player_uid, player_name)
            send_chat(f"@{player_name}: You have {balance} Dewritos.")
        else:
            target_name = " ".join(args)
            if target_name.startswith("@"):
                target_name = target_name[1:]
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            if target_uid:
                balance = get_dewritos(target_uid, target_name)
                send_chat(f"{target_name} has {balance} Dewritos.")
            else:
                send_chat(f"Player '{target_name}' not found.")
        return

    if cmd == "bet" and len(args) >= 3:
        try:
            amount = int(args[0])
            if args[1].lower() != "on":
                send_chat("Usage: !ai bet <amount> on <winner/topkiller/team> <player/team>")
                return
            bet_type = args[2].lower()
            if bet_type not in ["winner", "topkiller", "top_killer", "team"]:
                send_chat("Bet type must be 'winner', 'topkiller', or 'team'")
                return
            
            if bet_type == "team":
                if len(args) < 4:
                    send_chat("Usage: !ai bet <amount> on team <color>")
                    return
                target = args[3].lower()
                # ElDewrito team colors
                valid_teams = ["red", "blue", "orange", "green", "brown", "pink", "gold", "purple"]
                if target not in valid_teams:
                    send_chat(f"Team must be one of: {', '.join(valid_teams)}")
                    return
                result, msg = place_bet(player_uid, player_name, amount, "team", target)
            elif bet_type == "winner":
                target = " ".join(args[3:])
                result, msg = place_bet(player_uid, player_name, amount, "winner", target)
            else:
                target = " ".join(args[3:])
                result, msg = place_bet(player_uid, player_name, amount, "top_killer", target)
            
            send_chat(f"@{player_name}: {msg}")
        except ValueError:
            send_chat("Usage: !ai bet <amount> on <winner/topkiller/team> <player/team>")
        return

    if cmd == "leaderboard" or cmd == "topdewritos":
        leaderboard = get_leaderboard()
        if not leaderboard:
            send_chat("No Dewritos data yet.")
        else:
            entries = []
            for i, (uid, data) in enumerate(leaderboard[:5], 1):
                entries.append(f"{i}. {data.get('name', '?')} ({data.get('balance', 0)})")
            send_chat(f"💰 Top 5 Richest Dewritos: {' | '.join(entries)}")
        return

    # ========== ADMIN-ONLY COMMANDS ==========
    if cmd in ADMIN_ONLY_CMDS:
        if not owner:
            send_chat(f"@{player_name}: That command is restricted to the server owner.")
            return

        if cmd == "addmod" and args:
            target_name, _ = get_target_name(args)
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
            target_name, _ = get_target_name(args)
            if remove_mod(target_name):
                send_chat(f"{target_name} is no longer a moderator.")
            else:
                send_chat(f"'{target_name}' is not a moderator.")

        elif cmd == "backup":
            try:
                backup_folder = create_backup()
                send_chat(f"Backup created successfully: {os.path.basename(backup_folder)}")
            except Exception as e:
                logger.error(f"Backup failed: {e}")
                send_chat(f"Backup failed: {e}")

        elif cmd == "backuplist":
            backups = get_backup_list()
            if not backups:
                send_chat("No backups found.")
            else:
                backup_names = [f"{b[1]} ({b[0].strftime('%Y-%m-%d %H:%M:%S')})" for b in backups[:10]]
                send_chat(f"Recent backups: {', '.join(backup_names[:5])}")
                if len(backup_names) > 5:
                    send_chat(f"Total {len(backups)} backups. Use !ai restore <name> to restore.")

        elif cmd == "restore" and args:
            backup_name = args[0]
            backup_name = backup_name.strip('"').strip("'")
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            if not os.path.exists(backup_path):
                send_chat(f"Backup '{backup_name}' not found. Use !ai backuplist to see available backups.")
                return
            send_chat(f"Restoring from backup '{backup_name}'... This may take a moment.")
            if restore_backup(backup_name):
                send_chat(f"Restored from backup '{backup_name}'. Some changes may require a restart to take effect.")
                logger.info(f"Restored from backup by {player_name}")
            else:
                send_chat(f"Failed to restore from backup '{backup_name}'.")

        elif cmd == "discord" and args:
            discord_enabled = args[0].lower() == "on"
            send_chat(f"Discord bridge {'enabled' if discord_enabled else 'disabled'}.")

        return

    # ========== MOD + ADMIN COMMANDS ==========
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
                f"LoadBalance: {'on' if load_balancing_enabled else 'off'} | "
                f"AutoMod: {'on' if automod_enabled else 'off'} | "
                f"Rotation: {'on' if rotation_enabled else 'off'} | "
                f"AFK: {'on' if afk_enabled else 'off'} | "
                f"Discord: {'on' if discord_enabled else 'off'} | "
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

        elif cmd == "provider" and args:
            provider = args[0].lower()
            valid = [n for n, _, _ in CLOUD_PROVIDER_CHAIN] + ["auto"]
            if provider in valid:
                active_provider = provider
                send_chat(f"Provider set to {provider.capitalize()}.")
            else:
                send_chat(f"Options: {', '.join(valid)}")

        elif cmd == "loadbalance" and args:
            if args[0].lower() == "on":
                load_balancing_enabled = True
                send_chat("Load balancing enabled. API providers will cycle on failures.")
            elif args[0].lower() == "off":
                load_balancing_enabled = False
                send_chat("Load balancing disabled. Sticking with first available provider.")
            else:
                send_chat("Usage: !ai loadbalance on/off")

        elif cmd == "say" and args:
            message = " ".join(args)
            speak_to_game(message)
            send_chat(f"Speaking: {message}")

        elif cmd == "maps":
            if available_maps:
                send_chat(f"Available maps: {', '.join(sorted(available_maps))}")
            else:
                send_chat("No maps found.")

        elif cmd == "map" and args:
            map_input = " ".join(args)
            map_input = map_input.strip('"').strip("'")
            matched = None
            for m in available_maps:
                if m.lower() == map_input.lower():
                    matched = m
                    break
            if not matched:
                for m in available_maps:
                    if map_input.lower() in m.lower():
                        matched = m
                        break
            if matched:
                map_folder = os.path.join(GAME_MAPS_DIR, matched)
                raw_mod_name = get_mod_from_map_file(map_folder)
                mod_pak_name = get_mod_pak_name(raw_mod_name)
                send_rcon(f'Server.Mod "{mod_pak_name}"')
                time.sleep(0.5)
                base_map = get_base_map_for_variant(matched)
                if base_map:
                    send_rcon(f'Game.Map "{base_map}"')
                    time.sleep(2)
                send_rcon(f'Game.Map "{matched}"')
                send_chat(f"Changing map to {matched}..." + (f" (on {base_map})" if base_map else ""))
            else:
                send_chat(f"Map '{map_input}' not found. Use !ai maps to list.")

        elif cmd == "modes":
            if available_variants:
                mode_list = sorted(set(available_variants.keys()))
                total = len(mode_list)
                send_chat(f"Available modes ({total} total):")
                for i in range(0, total, 10):
                    batch = mode_list[i:i+10]
                    send_chat(f"  {', '.join(batch)}")
                send_chat(f"Use !ai mode <name> to load. Example: !ai mode fatkid")
            else:
                send_chat("No game variants found.")

        elif cmd == "mode" and args:
            mode_input = " ".join(args).lower()
            matched = None
            for key in available_variants.keys():
                if key == mode_input:
                    matched = key
                    break
            if not matched:
                for key in available_variants.keys():
                    if mode_input in key:
                        matched = key
                        break
            if matched:
                send_rcon(f'Game.GameType "{matched}"')
                send_chat(f"Loading mode: {matched}")
            else:
                send_chat(f"Mode '{mode_input}' not found. Use !ai modes to list.")

        elif cmd == "votingsystem" and args:
            try:
                system_type = int(args[0])
                if 0 <= system_type <= 3:
                    send_rcon(f"Voting.SystemType {system_type}")
                    system_names = ["Disabled", "Standard", "Instant", "Majority"]
                    send_chat(f"Voting system set to: {system_names[system_type]} (type {system_type})")
                else:
                    send_chat("Invalid system type. Use 0=Disabled, 1=Standard, 2=Instant, 3=Majority")
            except ValueError:
                send_chat("Usage: !ai votingsystem <0-3>")

        elif cmd == "votingoptions" and args:
            try:
                send_rcon(f"Server.NumberOfVotingOptions {int(args[0])}")
                send_chat(f"Voting options set to {args[0]}.")
            except ValueError:
                send_chat("Usage: !ai votingoptions <number>")

        elif cmd == "revotes" and args:
            try:
                send_rcon(f"Server.NumberOfRevotesAllowed {int(args[0])}")
                send_chat(f"Revotes allowed set to {args[0]}.")
            except ValueError:
                send_chat("Usage: !ai revotes <number>")

        elif cmd == "votepass" and args:
            try:
                send_rcon(f"Server.VotePassPercentage {int(args[0])}")
                send_chat(f"Vote pass % set to {args[0]}%.")
            except ValueError:
                send_chat("Usage: !ai votepass <percentage>")

        elif cmd == "votingon":
            send_rcon("Server.VotingEnabled 1")
            send_chat("Map voting enabled.")

        elif cmd == "votingoff":
            send_rcon("Server.VotingEnabled 0")
            send_chat("Map voting disabled.")

        elif cmd == "servername" and args:
            name = " ".join(args)
            send_rcon(f'Server.Name "{name}"')
            send_chat(f"Server name set to: {name}")

        elif cmd == "serverpassword":
            if args and args[0].lower() == "clear":
                send_rcon('Server.Password ""')
                send_chat("Server password removed.")
            elif args:
                send_rcon(f'Server.Password "{args[0]}"')
                send_chat("Server password updated.")
            else:
                send_chat("Usage: !ai serverpassword <password> or !ai serverpassword clear")

        elif cmd == "teams" and args:
            try:
                send_rcon(f"Server.NumberOfTeams {int(args[0])}")
                send_chat(f"Teams set to {args[0]}.")
            except ValueError:
                send_chat("Usage: !ai teams <number>")

        elif cmd == "shouldannounce" and args:
            val = "1" if args[0].lower() == "on" else "0"
            send_rcon(f"Server.ShouldAnnounce {val}")
            send_chat(f"Server visibility {'enabled' if val == '1' else 'disabled'}.")

        elif cmd == "announce" and args:
            announce_enabled = args[0].lower() == "on"
            send_chat(f"Scheduled announcements {'enabled' if announce_enabled else 'disabled'}.")

        elif cmd == "rotation" and args:
            if args[0].lower() == "on":
                rotation_enabled = True
                send_chat("Map rotation enabled.")
            elif args[0].lower() == "off":
                rotation_enabled = False
                send_chat("Map rotation disabled.")
            else:
                send_chat("Usage: !ai rotation on/off")

        elif cmd == "nextmap":
            rotation = load_rotation()
            if not rotation:
                send_chat("Rotation list is empty. Edit rotation.json.")
                return
            rotation_index = (rotation_index + 1) % len(rotation)
            entry = rotation[rotation_index]
            map_name = entry.get("map", "")
            mode_name = entry.get("mode", "")
            
            if map_name:
                matched_map = None
                for m in available_maps:
                    if m.lower() == map_name.lower():
                        matched_map = m
                        break
                if not matched_map:
                    for m in available_maps:
                        if map_name.lower() in m.lower():
                            matched_map = m
                            break
                if matched_map:
                    map_folder = os.path.join(GAME_MAPS_DIR, matched_map)
                    raw_mod_name = get_mod_from_map_file(map_folder)
                    mod_pak_name = get_mod_pak_name(raw_mod_name)
                    send_rcon(f'Server.Mod "{mod_pak_name}"')
                    time.sleep(0.5)
                    base_map = get_base_map_for_variant(matched_map)
                    if base_map:
                        send_rcon(f'Game.Map "{base_map}"')
                        time.sleep(2)
                    send_rcon(f'Game.Map "{matched_map}"')
            
            if mode_name:
                matched_mode = None
                for key in available_variants.keys():
                    if key == mode_name.lower():
                        matched_mode = key
                        break
                if not matched_mode:
                    for key in available_variants.keys():
                        if mode_name.lower() in key:
                            matched_mode = key
                            break
                if matched_mode:
                    send_rcon(f'Game.GameType "{matched_mode}"')
            
            send_chat(f"Next rotation: {map_name} / {mode_name or 'current mode'}")

        elif cmd == "shufflerotation":
            rotation = load_rotation()
            random.shuffle(rotation)
            save_rotation(rotation)
            send_chat("Rotation shuffled.")

        elif cmd == "afk" and args:
            afk_enabled = args[0].lower() == "on"
            msg = f"AFK detection {'enabled' if afk_enabled else 'disabled'}."
            if afk_enabled and AFK_TIMEOUT_MINUTES == 0:
                msg += " Set AFK_TIMEOUT_MINUTES in the script to activate."
            send_chat(msg)

        elif cmd == "start":
            send_rcon("Game.Start")
            send_chat("Starting the game...")

        elif cmd == "kick" and args:
            target_name, _ = get_target_name(args)
            do_kick(player_name, player_uid, target_name)

        elif cmd == "ban" and args:
            target_name, _ = get_target_name(args)
            do_ban(player_name, player_uid, target_name)

        elif cmd == "tempban" and args:
            try:
                duration = int(args[-1])
                name_args = args[:-1]
            except ValueError:
                duration = 5
                name_args = args
            if not name_args:
                send_chat("Usage: !ai tempban <name> [minutes]")
                return
            target_name, _ = get_target_name(name_args)
            do_tempban(player_name, player_uid, target_name, duration)

        elif cmd == "unban" and args:
            target_name, _ = get_target_name(args)
            if remove_ban(target_name, moderator=player_name):
                send_chat(f"{target_name} has been unbanned.")
            else:
                send_chat(f"No ban found for '{target_name}'.")

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
            target_name, reason_start = get_target_name(args)
            reason = " ".join(args[reason_start:])
            if not reason:
                send_chat(f"@{player_name}: Please provide a reason for the warning.")
                return
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            target_ip = target_info.get("ip", "")
            if target_uid and is_protected(target_uid):
                send_chat("I won't act against the server administrator.")
                return
            if not is_owner(player_uid) and target_uid and is_mod(target_uid):
                send_chat(f"@{player_name}: Moderators cannot warn other moderators.")
                return
            count = add_warning(target_name, target_uid, f"{reason} (warned by {player_name})", moderator=player_name)
            remaining = max(0, WARN_KICK_THRESHOLD - count)
            if count < WARN_KICK_THRESHOLD:
                send_chat(f"@{target_name}: Warning {count}/{WARN_KICK_THRESHOLD} — {reason}. {remaining} left before action.")
            elif count == WARN_KICK_THRESHOLD:
                send_chat(f"{target_name} has been kicked after {count} warnings.")
                send_rcon(f"Server.KickPlayer {target_name}")

        elif cmd == "warnings" and args:
            target_name, _ = get_target_name(args)
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            data = get_warnings(target_name, target_uid)
            send_chat(f"{target_name} has {data.get('count', 0)} warning(s).")

        elif cmd == "clearwarnings" and args:
            target_name, _ = get_target_name(args)
            if clear_warnings(target_name):
                send_chat(f"Warnings cleared for {target_name}.")
            else:
                send_chat(f"No warnings found for '{target_name}'.")

        elif cmd == "mute" and args:
            target_name, _ = get_target_name(args)
            target_info = get_player_info(target_name)
            target_uid = target_info.get("uid", "")
            if target_uid and is_protected(target_uid):
                send_chat("I won't act against the server administrator.")
                return
            send_rcon(f"Server.MutePlayer {target_name}")
            send_chat(f"{target_name} has been muted.")

        elif cmd == "unmute" and args:
            target_name, _ = get_target_name(args)
            send_rcon(f"Server.UnmutePlayer {target_name}")
            send_chat(f"{target_name} has been unmuted.")

        elif cmd == "reloadvoting":
            send_rcon("Voting.ReloadJson")
            send_chat("Voting JSON reloaded.")

        elif cmd == "pm" and len(args) >= 2:
            target_name, msg_start = get_target_name(args)
            message = " ".join(args[msg_start:])
            send_rcon(f'Server.PM {target_name} "{message}"')
            send_chat(f"PM sent to {target_name}.")

        elif cmd == "mystats":
            data = get_player_stats(player_name, player_uid)
            send_chat(f"@{player_name}: {format_stats(data)}")

        elif cmd == "stats":
            if args:
                target_name = " ".join(args)
                data = get_player_stats(target_name)
                send_chat(format_stats(data))
            else:
                data = get_player_stats(player_name, player_uid)
                send_chat(f"@{player_name}: {format_stats(data)}")

        else:
            send_chat(
                "Commands: on/off/status/clear/cooldown/automod | "
                "map/maps/mode/modes/start | pm/kick/ban/tempban/unban/banlist | "
                "warn/warnings/clearwarnings | mute/unmute/reloadvoting | mystats/stats"
            )
        return

    send_chat(
        "Admin only: addmod/removemod/backup/restore/backuplist/discord | "
        "For help, ask a moderator."
    )

# ── Background Threads ────────────────────────

def check_banned_players():
    while True:
        time.sleep(10)
        try:
            for p in get_server_info().get("players", []):
                name = p.get("name", "")
                uid = p.get("uid", "")
                ip = p.get("ip", "")
                
                if is_protected(uid):
                    continue
                
                # Check local ban list (with expiration)
                ban = is_banned(uid=uid, name=name, ip=ip)
                if ban:
                    send_rcon(f"Server.KickPlayer {name}")
                    send_chat(f"{name} is banned and has been removed.")
        except Exception:
            pass

def scheduled_backup():
    """Run automatic backups daily"""
    last_backup = 0
    while True:
        time.sleep(3600)  # Check every hour
        now = time.time()
        if now - last_backup >= 86400:  # 24 hours
            create_backup()
            last_backup = now
            logger.info("Scheduled daily backup completed")

# Start scheduled backup thread (add this after other threads)
threading.Thread(target=scheduled_backup, daemon=True).start()

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

def check_first_blood():
    global first_blood_given
    kill_tracker = {}
    while True:
        time.sleep(5)
        if not bot_enabled:
            continue
        try:
            info = get_server_info()
            status = info.get("status", "")
            if status == "InGame" and not first_blood_given:
                for p in info.get("players", []):
                    name = p.get("name", "")
                    uid = p.get("uid", "")
                    kills = p.get("kills", 0)
                    prev = kill_tracker.get(name, 0)
                    if kills == 1 and prev == 0:
                        send_chat(f"First blood — {name}! (+5 Dewritos)")
                        update_dewritos(uid, name, 5, "First blood")
                        first_blood_given = True
                        break
                    kill_tracker[name] = kills
            elif status == "InLobby":
                first_blood_given = False
                kill_tracker.clear()
        except Exception:
            pass

def check_game_state():
    global last_game_status, rotation_index
    while True:
        time.sleep(ROTATION_CHECK_INTERVAL)
        if not bot_enabled:
            continue
        try:
            info = get_server_info()
            status = info.get("status", "")

            if last_game_status == "InGame" and status == "InLobby":
                process_match_end(info)

                if rotation_enabled:
                    rotation = load_rotation()
                    if rotation:
                        time.sleep(ROTATION_VOTE_WAIT)
                        current = get_server_info().get("status", "")
                        if current == "InLobby":
                            rotation_index = (rotation_index + 1) % len(rotation)
                            entry = rotation[rotation_index]
                            map_name = entry.get("map", "")
                            mode_name = entry.get("mode", "")
                            
                            # Load the map with mod support
                            if map_name:
                                matched_map = None
                                for m in available_maps:
                                    if m.lower() == map_name.lower():
                                        matched_map = m
                                        break
                                if not matched_map:
                                    for m in available_maps:
                                        if map_name.lower() in m.lower():
                                            matched_map = m
                                            break
                                
                                if matched_map:
                                    map_folder = os.path.join(GAME_MAPS_DIR, matched_map)
                                    raw_mod_name = get_mod_from_map_file(map_folder)
                                    mod_pak_name = get_mod_pak_name(raw_mod_name)
                                    
                                    send_rcon(f'Server.Mod "{mod_pak_name}"')
                                    time.sleep(0.5)
                                    
                                    base_map = get_base_map_for_variant(matched_map)
                                    if base_map:
                                        send_rcon(f'Game.Map "{base_map}"')
                                        time.sleep(2)
                                    
                                    send_rcon(f'Game.Map "{matched_map}"')
                                    send_chat(f"Rotation: Loading {matched_map}...")
                            
                            if mode_name:
                                matched_mode = None
                                for key in available_variants.keys():
                                    if key == mode_name.lower():
                                        matched_mode = key
                                        break
                                if not matched_mode:
                                    for key in available_variants.keys():
                                        if mode_name.lower() in key:
                                            matched_mode = key
                                            break
                                
                                if matched_mode:
                                    send_rcon(f'Game.GameType "{matched_mode}"')
                                    send_chat(f"Rotation: Loading mode {matched_mode}")

            last_game_status = status
        except Exception as e:
            logger.info(f"[ROTATION] Error: {e}")

def check_afk():
    while True:
        time.sleep(AFK_CHECK_INTERVAL)
        if not afk_enabled or AFK_TIMEOUT_MINUTES == 0 or not bot_enabled:
            continue
        try:
            now = time.time()
            info = get_server_info()
            if info.get("status") != "InGame":
                continue
            for p in info.get("players", []):
                name = p.get("name", "")
                uid = p.get("uid", "")
                kills = p.get("kills", 0)
                score = p.get("score", 0)
                if is_owner(uid) or is_mod(uid):
                    continue
                prev = afk_tracker.get(name, {"last_kills": kills, "last_score": score, "last_active": now})
                if kills != prev["last_kills"] or score != prev["last_score"]:
                    afk_tracker[name] = {"last_kills": kills, "last_score": score, "last_active": now}
                else:
                    idle_min = (now - prev["last_active"]) / 60
                    if idle_min >= AFK_TIMEOUT_MINUTES:
                        send_rcon(f"Server.KickPlayer {name}")
                        send_chat(f"{name} was kicked for being AFK.")
                        afk_tracker.pop(name, None)
        except Exception:
            pass

def check_players():
    global known_players
    try:
        known_players = {p.get("name", "") for p in get_server_info().get("players", []) if p.get("name", "").strip()}
    except Exception:
        known_players = set()
    
    while True:
        time.sleep(5)
        if not bot_enabled:
            continue
        try:
            current = {p.get("name", "") for p in get_server_info().get("players", []) if p.get("name", "").strip()}
            for name in current - known_players:
                # Get player info to initialize Dewritos
                player_info = get_player_info(name)
                player_uid = player_info.get("uid", "")
                if player_uid:
                    # This will create the player record with 100 Dewritos if not exists
                    get_dewritos(player_uid, name)
                
                if len(name) >= 2:
                    send_chat(f"Welcome, {name}. Type !cortana <question> or just mention my name.")
            known_players = current
        except Exception:
            pass

def scheduled_announcements():
    ann_index = 0
    while True:
        time.sleep(ANNOUNCEMENT_INTERVAL)
        if not announce_enabled or not bot_enabled or not ANNOUNCEMENTS:
            continue
        try:
            send_chat(ANNOUNCEMENTS[ann_index % len(ANNOUNCEMENTS)])
            ann_index += 1
        except Exception:
            pass

# ── Chat Log Watcher ──────────────────────────

def watch_chat_log():
    logger.info(f"[LOG] Watching: {CHAT_LOG_PATH}")
    while not os.path.exists(CHAT_LOG_PATH):
        logger.info("[LOG] Waiting for chat log...")
        time.sleep(2)

    with open(CHAT_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, 2)
        logger.info("[LOG] Ready.")

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

            logger.info(f"[CHAT] {player_name} ({player_uid}): {message}")
            chat_memory.append((player_name, message))

            # Forward to Discord
            if discord_enabled and not message.startswith("[Discord]"):
                threading.Thread(target=send_to_discord, args=(player_name, message), daemon=True).start()

            # Update AFK tracker on chat
            if player_name in afk_tracker:
                afk_tracker[player_name]["last_active"] = time.time()

            threading.Thread(target=automod_check, args=(player_name, player_uid, player_ip, message), daemon=True).start()

            lower = message.lower()

            if lower.startswith("!ai "):
                remainder = message[4:].strip()
                rem_parts = remainder.split()
                if not rem_parts:
                    continue
                first_word = rem_parts[0].lower()

                if first_word in ADMIN_ONLY_CMDS or first_word in MOD_CMDS:
                    handle_command(player_name, player_uid, player_ip, remainder)
                    continue

                if first_word == "remember":
                    entry = " ".join(rem_parts[1:])
                    if entry:
                        append_memory(player_name, entry)
                        send_chat(f"@{player_name}: Noted.")
                    else:
                        send_chat(f"@{player_name}: Remember what? Try: !ai remember <text>")
                    continue

                if not bot_enabled:
                    send_chat(f"@{player_name}: I'm currently offline.")
                    continue
                try_queue_request(player_name, player_uid, remainder)
                continue

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

    GROQ_API_KEY        = config.get("GROQ_API_KEY", "")
    CEREBRAS_API_KEY    = config.get("CEREBRAS_API_KEY", "")
    MISTRAL_API_KEY     = config.get("MISTRAL_API_KEY", "")
    OPENROUTER_API_KEY  = config.get("OPENROUTER_API_KEY", "")
    RCON_PASSWORD       = config.get("RCON_PASSWORD", "")
    RCON_PORT           = int(config.get("RCON_PORT", 11776))
    OWNER_UUID          = config.get("OWNER_UUID", "").lower().replace("0x", "")
    OWNER_PRIVKEY       = config.get("OWNER_PRIVKEY", "")
    DISCORD_WEBHOOK_URL = config.get("DISCORD_WEBHOOK_URL", "")
    DISCORD_BOT_TOKEN   = config.get("DISCORD_BOT_TOKEN", "")
    DISCORD_CHANNEL_ID  = config.get("DISCORD_CHANNEL_ID", "")

    providers_loaded = [n for n, _, has_key in CLOUD_PROVIDER_CHAIN if has_key()]
    available_variants = scan_variants()
    available_maps     = scan_maps()
    rotation           = load_rotation()
    mods               = load_mods()
    memory_lines       = len(load_memory().splitlines()) if load_memory() else 0
    stats_count        = len(load_stats())

    discord_configured = bool(DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN)

    # Check Ollama status for local model
    if not is_ollama_running():
        logger.info("WARNING: Ollama not running or model not pulled. Local model disabled.")

    logger.info("=" * 55)
    logger.info(f"  {BOT_NAME} AI Bot — Tier 1 + Tier 2")
    logger.info(f"  Owner UID:    {OWNER_UUID}")
    logger.info(f"  PrivKey:      {'set' if OWNER_PRIVKEY else 'NOT SET'}")
    logger.info(f"  Providers:    {' -> '.join(p.capitalize() for p in providers_loaded) if providers_loaded else 'None!'}")
    logger.info(f"  Variants:     {len(available_variants)} modes | {len(available_maps)} maps")
    logger.info(f"  Rotation:     {len(rotation)} entries (off by default)")
    logger.info(f"  Mods:         {len(mods)} loaded")
    logger.info(f"  Memory:       {memory_lines} entries")
    logger.info(f"  Stats:        {stats_count} players tracked")
    logger.info(f"  Announcements:{len(ANNOUNCEMENTS)} configured")
    logger.info(f"  Discord:      {'configured' if discord_configured else 'not configured'} (off by default)")
    logger.info(f"  AFK:          off | timeout: {AFK_TIMEOUT_MINUTES}min")
    logger.info(f"  AutoMod:      on")
    logger.info(f"  Local:        off | {OLLAMA_MODEL}")
    logger.info(f"  Config:       {CONFIG_FILE}")
    logger.info("=" * 55)
    logger.info(f"  {BOT_NAME} AI Bot — Ready!")
    logger.info("=" * 55)

    if not RCON_PASSWORD:
        logger.info("ERROR: RCON_PASSWORD not set in config.txt")
        sys.exit(1)
    if not OWNER_UUID:
        logger.info("ERROR: OWNER_UUID not set in config.txt")
        sys.exit(1)
    if not OWNER_PRIVKEY:
        logger.info("WARNING: OWNER_PRIVKEY not set — admin commands disabled!")
    if not providers_loaded:
        logger.info("ERROR: No API keys loaded!")
        sys.exit(1)
    if not connect_rcon():
        logger.info("[ERROR] Could not connect to RCON.")
        sys.exit(1)

    # Start Discord bot if configured
    if discord_configured:
        start_discord_bot()

    # Start background threads
    threading.Thread(target=reconnect_rcon, daemon=True).start()
    threading.Thread(target=check_killstreaks, daemon=True).start()
    threading.Thread(target=check_first_blood, daemon=True).start()
    threading.Thread(target=check_game_state, daemon=True).start()
    threading.Thread(target=check_players, daemon=True).start()
    threading.Thread(target=check_banned_players, daemon=True).start()
    threading.Thread(target=check_afk, daemon=True).start()
    threading.Thread(target=scheduled_announcements, daemon=True).start()
    
    # Start scheduled backup thread
    threading.Thread(target=scheduled_backup, daemon=True).start()

    time.sleep(1)
    send_chat(f"{BOT_NAME} online. Type !cortana <question> or just mention my name.")
    watch_chat_log()
