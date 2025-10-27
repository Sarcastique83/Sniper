# =============================================================================
# 📦 Imports
# =============================================================================
import os
import re
from datetime import datetime
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
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# =============================================================================
# 🧠 Cache
# =============================================================================
snipes: dict[int, dict] = {}
edits: dict[int, dict] = {}

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
VID_EXT = (".mp4", ".mov", ".webm")

# =============================================================================
# 🧰 Fonctions utilitaires
# =============================================================================
def _fmt_hhmm(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%H:%M")

def _convert_tenor(url: str) -> str:
    """Convertit une URL Tenor classique en lien direct .gif si possible."""
    if "tenor.com/view/" in url:
        # Exemple : https://tenor.com/view/dancing-cat-12345678
        match = re.search(r"tenor\.com/view/.+?-(\d+)", url)
        if match:
            gif_id = match.group(1)
            return f"https://media.tenor.com/{gif_id}.gif"
    return url

# =============================================================================
# 🎨 Embeds
# =============================================================================
def embed_snipe(author, content: str, attachments: list[str], when: datetime) -> discord.Embed:
    """Snipe suppression : texte + image/GIF/vidéo si jointe."""
    parts = [content if content else "*[Message vide]*"]

    # Indication fichiers si présents
    if attachments:
        first_lower = attachments[0].lower()
        if first_lower.endswith(IMG_EXT):
            parts.append("\n🖼️ *Image/GIF supprimé*")
        elif first_lower.endswith(VID_EXT):
            parts.append("\n🎞️ *Vidéo supprimée*")
        else:
            parts.append("\n📎 *Fichier supprimé*")

        if len(attachments) > 1:
            parts.append(f"\n📁 *(+{len(attachments)-1} autre(s) pièce(s) jointe(s))*")

    embed = discord.Embed(description="\n".join(parts), color=discord.Color.red())
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.set_footer(text=_fmt_hhmm(when))

    # Affiche l'image/GIF Tenor si applicable
    if attachments:
        first = attachments[0]
        first = _convert_tenor(first)  # conversion automatique
        if first.lower().endswith(IMG_EXT):
            embed.set_image(url=first)

    return embed

def embed_edit(author, before: str, after: str, when: datetime) -> discord.Embed:
    """Snipe édition : fields Avant / Après (couleur bleue)."""
    embed = discord.Embed(color=discord.Color.from_rgb(52, 152, 219))
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.add_field(name="Avant :", value=before or "*[Vide]*", inline=False)
    embed.add_field(name="Après :", value=after or "*[Vide]*", inline=False)
    embed.set_footer(text=_fmt_hhmm(when))
    return embed

# =============================================================================
# 🔒 Accès commandes
# =============================================================================
def is_authorized(ctx: commands.Context) -> bool:
    if ctx.author.premium_since:
        return True
    wl = set(get_whitelist())
    if any(role.id in wl for role in ctx.author.roles):
        return True
    return False

# =============================================================================
# 👂 Listeners
# =============================================================================
@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.guild.id != SERVER_ID:
        return
    if message.author.bot:
        return

    attachments = [att.url for att in (message.attachments or [])]

    # Si le message contient un lien Tenor dans le texte, on le capture aussi
    tenor_links = re.findall(r"https?://(?:www\.)?tenor\.com/[^\s>]+", message.content or "")
    attachments.extend(tenor_links)

    snipes[message.channel.id] = {
        "author": message.author,
        "content": message.content,
        "attachments": attachments,
        "when": datetime.now(TZ)
    }

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not before.guild or before.guild.id != SERVER_ID:
        return
    if before.author.bot:
        return
    if before.content == after.content:
        return

    edits[before.channel.id] = {
        "author": before.author,
        "before": before.content,
        "after": after.content,
        "when": datetime.now(TZ)
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

    # Si c’est une vidéo, envoie le lien brut pour forcer le lecteur Discord
    first = (data["attachments"][0].lower() if data.get("attachments") else "")
    if first and first.endswith(VID_EXT):
        return await ctx.send(content=data["attachments"][0], embed=embed)

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
        activity=discord.Activity(type=discord.ActivityType.watching, name="vos messages")
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
