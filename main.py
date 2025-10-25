import os
from datetime import datetime
import pytz
import discord
from discord.ext import commands
from storage_json import get_whitelist

# =============================================================================
# 🔐 Config de base
# =============================================================================
COMMAND_PREFIX = "!!"
SERVER_ID = 1216444463262470324
TZ = pytz.timezone("Europe/Paris")  # ✅ Fuseau horaire global

# =============================================================================
# 🚀 Initialisation du bot
# =============================================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# =============================================================================
# 🧠 Stockage des snipes
# =============================================================================
snipes = {}
edits = {}

# =============================================================================
# 🎨 Embeds
# =============================================================================
def _fmt_hhmm(dt: datetime) -> str:
    """Formate l'heure au format HH:MM en Europe/Paris"""
    return dt.astimezone(TZ).strftime("%H:%M")

def embed_snipe(author, content, when):
    embed = discord.Embed(description=content or "*[Message vide]*", color=discord.Color.red())
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.set_footer(text=_fmt_hhmm(when))
    return embed

def embed_edit(author, before, after, when):
    embed = discord.Embed(color=discord.Color.from_rgb(52, 152, 219))
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    embed.add_field(name="Avant", value=before or "*[Vide]*", inline=False)
    embed.add_field(name="Après", value=after or "*[Vide]*", inline=False)
    embed.set_footer(text=_fmt_hhmm(when))
    return embed

# =============================================================================
# 🔒 Vérification d’accès
# =============================================================================
def is_authorized(ctx):
    """Vérifie si un utilisateur est autorisé à utiliser les commandes snipe."""
    # Booster du serveur
    if ctx.author.premium_since:
        return True
    # Rôle whitelisté
    if any(role.id in get_whitelist() for role in ctx.author.roles):
        return True
    return False

# =============================================================================
# 👂 Listeners
# =============================================================================
@bot.event
async def on_message_delete(message):
    if not message.guild or message.guild.id != SERVER_ID:
        return
    if message.author.bot:
        return
    snipes[message.channel.id] = {
        "author": message.author,
        "content": message.content,
        "when": datetime.now(TZ)  # ✅ heure locale
    }

@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.guild.id != SERVER_ID:
        return
    if before.author.bot or before.content == after.content:
        return
    edits[before.channel.id] = {
        "author": before.author,
        "before": before.content,
        "after": after.content,
        "when": datetime.now(TZ)  # ✅ heure locale
    }

# =============================================================================
# 🧾 Commandes
# =============================================================================
@bot.command()
async def snipe(ctx):
    if not is_authorized(ctx):
        return await ctx.send("Bien tenté mais non.")
    data = snipes.get(ctx.channel.id)
    if not data:
        return await ctx.send("Aucun message supprimé à afficher 😶")
    await ctx.send(embed=embed_snipe(**data))

@bot.command()
async def snipee(ctx):
    if not is_authorized(ctx):
        return await ctx.send("Bien tenté mais non.")
    data = edits.get(ctx.channel.id)
    if not data:
        return await ctx.send("Aucune édition récente à afficher 😶")
    await ctx.send(embed=embed_edit(**data))

# =============================================================================
# 🕶️ Présence du bot
# =============================================================================
@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.watching, name="vos messages")
    )
    print(f"✅ Connecté en tant que {bot.user} ({bot.user.id})")

# =============================================================================
# ▶️ Lancement
# =============================================================================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("❌ Token manquant (variable d'environnement DISCORD_TOKEN)")
    bot.run(TOKEN)
