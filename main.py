# =============================================================================
# 📦 Imports
# =============================================================================
import os
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
# 🧠 Cache (dernier snipe par salon)
# =============================================================================
# snipes[channel_id] = {
#   "author": Member, "content": str, "attachments": list[str], "when": datetime
# }
snipes: dict[int, dict] = {}

# edits[channel_id] = {
#   "author": Member, "before": str, "after": str, "when": datetime
# }
edits: dict[int, dict] = {}

# =============================================================================
# 🎨 Embeds
# =============================================================================
def _fmt_hhmm(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%H:%M")

def embed_snipe(author, content: str, attachments: list[str], when: datetime) -> discord.Embed:
    """Snipe suppression : affiche le texte + met l'image si jointe."""
    parts = []
    parts.append(content if content else "*[Message vide]*")
    if attachments:
        parts.append("\n🖼️ *Image/GIF supprimé*")

    embed = discord.Embed(description="\n".join(parts), color=discord.Color.red())
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.set_footer(text=_fmt_hhmm(when))

    # Affiche la première image/GIF si dispo
    if attachments:
        embed.set_image(url=attachments[0])
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
    # Boosters → accès natif
    if ctx.author.premium_since:
        return True
    # Rôles whitelist → accès
    wl = set(get_whitelist())
    if any(role.id in wl for role in ctx.author.roles):
        return True
    return False

# =============================================================================
# 👂 Listeners
# =============================================================================
@bot.event
async def on_message_delete(message: discord.Message):
    # Serveur ciblé uniquement
    if not message.guild or message.guild.id != SERVER_ID:
        return
    if message.author.bot:
        return

    # Texte + URLs des pièces jointes
    attachments = [att.url for att in message.attachments] if message.attachments else []

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
