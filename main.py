import os
import re
from datetime import datetime
from collections import deque
from typing import Deque, Dict, List
import pytz
import discord
from discord.ext import commands
from storage_json import get_whitelist

# =============================================================================
# 🔐 Config
# =============================================================================
COMMAND_PREFIX = "!!"
SERVER_ID = 1216444463262470324
TZ = pytz.timezone("Europe/Paris")

# =============================================================================
# 🚀 Bot
# =============================================================================
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True            # nécessaire pour create/edit/delete
intents.message_content = True     # lire le contenu pour les liens
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# =============================================================================
# 🧠 Caches
# =============================================================================
# Derniers snipes et edits par salon
snipes: Dict[int, dict] = {}
edits: Dict[int, dict] = {}

# Historique circulaire des derniers messages par salon (évite l'écrasement)
# On garde 5 messages récents par channel
last_messages: Dict[int, Deque[discord.Message]] = {}

# Cache persistant par message.id → infos utiles (texte + PJ + liens)
message_cache: Dict[int, dict] = {}
CACHE_LIMIT = 500  # sécurité mémoire

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
VID_EXT = (".mp4", ".mov", ".webm")

# =============================================================================
# 🧰 Utils
# =============================================================================

def _fmt_hhmm(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%H:%M")


def _convert_tenor(url: str) -> str:
    """Convertit une URL Tenor 'page' en lien direct .gif si possible."""
    if "tenor.com/view/" in url:
        match = re.search(r"tenor\.com/view/.+?-(\d+)", url)
        if match:
            gif_id = match.group(1)
            return f"https://media.tenor.com/{gif_id}.gif"
    return url


def _gather_links_from_content(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"https?://[^\s>]+", text)

# =============================================================================
# 🎨 Embeds
# =============================================================================

def embed_snipe(author: discord.Member, content: str, attachments: List[str], when: datetime) -> discord.Embed:
    """Snipe suppression : affiche texte + image/GIF/vidéo sans 'Message vide' inutile."""
    has_attachments = bool(attachments)
    description = content if content else ("" if has_attachments else "*[Message vide]*")

    embed = discord.Embed(description=description, color=discord.Color.red())
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.set_footer(text=_fmt_hhmm(when))

    if attachments:
        first = _convert_tenor(attachments[0])
        lower = first.lower()
        # Image/GIF intégré dans l'embed
        if lower.endswith(IMG_EXT):
            embed.set_image(url=first)
        # Vidéo → rien dans l'embed (Discord prévisualisera l'URL brute qu'on enverra)
    return embed


def embed_edit(author: discord.Member, before: str, after: str, when: datetime) -> discord.Embed:
    embed = discord.Embed(color=discord.Color.from_rgb(52, 152, 219))
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.add_field(name="Avant :", value=before or "*[Vide]*", inline=False)
    embed.add_field(name="Après :", value=after or "*[Vide]*", inline=False)
    embed.set_footer(text=_fmt_hhmm(when))
    return embed

# =============================================================================
# 🔒 Accès
# =============================================================================

def is_authorized(ctx: commands.Context) -> bool:
    if getattr(ctx.author, "premium_since", None):
        return True
    wl = set(get_whitelist())
    if any(role.id in wl for role in getattr(ctx.author, "roles", [])):
        return True
    return False

# =============================================================================
# 👂 Listeners
# =============================================================================

@bot.event
async def on_message(message: discord.Message):
    """Capture *proactive* : on enregistre chaque message (texte + liens + PJ)
    dès son arrivée, pour ne plus dépendre des données manquantes à la suppression."""
    if message.guild and message.guild.id == SERVER_ID and not message.author.bot:
        # ---- Cache persistant par message.id ----
        attachments = [att.url for att in message.attachments if att.url]
        inline_links = _gather_links_from_content(message.content or "")
        message_cache[message.id] = {
            "author": message.author,
            "content": message.content,
            "attachments": attachments + inline_links,
            "created_at": message.created_at,
            "channel_id": message.channel.id,
        }
        # GC simple
        if len(message_cache) > CACHE_LIMIT:
            oldest_key = next(iter(message_cache))
            message_cache.pop(oldest_key, None)

        # ---- Deque par salon (fallback local récent) ----
        dq = last_messages.setdefault(message.channel.id, deque(maxlen=5))
        dq.append(message)

    # Indispensable pour que les commandes texte fonctionnent
    await bot.process_commands(message)


@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.guild.id != SERVER_ID:
        return
    if message.author.bot:
        return

    # 1) Priorité : cache persistant par message.id
    data = message_cache.get(message.id)
    if data:
        snipes[message.channel.id] = {
            "author": data["author"],
            "content": data["content"],
            "attachments": data["attachments"],
            "when": datetime.now(TZ),
        }
        return

    # 2) Fallback : tenter de retrouver un message équivalent dans le deque
    dq = last_messages.get(message.channel.id)
    chosen = message
    if dq:
        # même ID si encore présent
        for m in reversed(dq):
            if m.id == message.id:
                chosen = m
                break
        # sinon dernier message du même auteur avec PJ
        if (not getattr(chosen, "attachments", None)) or len(chosen.attachments) == 0:
            for m in reversed(dq):
                if m.author.id == message.author.id and m.attachments:
                    chosen = m
                    break

    # Collecte
    attachments: List[str] = []
    for att in getattr(chosen, "attachments", []) or []:
        if att.url:
            attachments.append(att.url)
    attachments.extend(_gather_links_from_content(getattr(chosen, "content", "") or ""))

    snipes[message.channel.id] = {
        "author": getattr(chosen, "author", message.author),
        "content": getattr(chosen, "content", ""),
        "attachments": attachments,
        "when": datetime.now(TZ),
    }


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not before.guild or before.guild.id != SERVER_ID:
        return
    if before.author.bot or before.content == after.content:
        return

    edits[before.channel.id] = {
        "author": before.author,
        "before": before.content,
        "after": after.content,
        "when": datetime.now(TZ),
    }

# =============================================================================
# 🧾 Commandes
# =============================================================================

@bot.command(name="snipe")
async def snipe_cmd(ctx: commands.Context):
    if not is_authorized(ctx):
        return await ctx.send("Bien tenté mais non.")

    data = snipes.get(ctx.channel.id)
    if not data:
        return await ctx.send("Aucun message supprimé à afficher 😶")

    embed = embed_snipe(data["author"], data["content"], data["attachments"], data["when"]) 

    # Si c'est une vidéo → on envoie l'URL brute à côté pour le lecteur auto
    first_list = data.get("attachments") or []
    first = first_list[0].lower() if first_list else ""
    if first and first.endswith(VID_EXT):
        return await ctx.send(content=first_list[0], embed=embed)

    await ctx.send(embed=embed)


@bot.command(name="snipee")
async def snipee_cmd(ctx: commands.Context):
    if not is_authorized(ctx):
        return await ctx.send("Bien tenté mais non.")

    data = edits.get(ctx.channel.id)
    if not data:
        return await ctx.send("Aucune édition récente à afficher 😶")

    embed = embed_edit(data["author"], data["before"], data["after"], data["when"]) 
    await ctx.send(embed=embed)

# =============================================================================
# 🕶️ Présence
# =============================================================================

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.watching, name="vos messages"),
    )
    print(f"✅ Connecté en tant que {bot.user} ({bot.user.id})")

# =============================================================================
# ▶️ Run
# =============================================================================

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("❌ Token manquant (variable d'environnement DISCORD_TOKEN)")
    bot.run(TOKEN)
