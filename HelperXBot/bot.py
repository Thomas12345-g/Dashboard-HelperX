import discord
from discord.ext import commands
import os
import logging
import traceback
import shutil
import sys
import asyncio
from dotenv import load_dotenv

# Lade Environment Variablen
load_dotenv()

# Cache löschen
if os.path.exists("./features/__pycache__"):
    shutil.rmtree("./features/__pycache__")

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ══════════════════════════════════════════════════════════════════════════════
#  MODUS
# ══════════════════════════════════════════════════════════════════════════════
BOT_MODE = os.getenv("BOT_MODE", "public")  # ← jetzt über .env konfigurierbar

# ══════════════════════════════════════════════════════════════════════════════
#  SERVER-IDs
# ══════════════════════════════════════════════════════════════════════════════
GUILD_IDS = [
    1477774300508590332,
    1493276175429013735,
    # ← Weitere Server-IDs hier einfügen
]

# ══════════════════════════════════════════════════════════════════════════════
#  BOT-VERSION
# ══════════════════════════════════════════════════════════════════════════════
BOT_VERSION = "9.9"

# ══════════════════════════════════════════════════════════════════════════════
#  API-KEYS — Jetzt sicher über Environment Variablen
# ══════════════════════════════════════════════════════════════════════════════
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # KEIN Hardcoded Token mehr!
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Prüfe ob Token vorhanden ist
if not DISCORD_TOKEN:
    logging.error("❌ DISCORD_TOKEN nicht in .env Datei gefunden!")
    sys.exit(1)

if not GROQ_API_KEY:
    logging.warning("⚠️ GROQ_API_KEY nicht in .env Datei gefunden -某些 Funktionen könnten nicht arbeiten")

# ══════════════════════════════════════════════════════════════════════════════
#  INTENTS
# ══════════════════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ══════════════════════════════════════════════════════════════════════════════
#  GLOBALE VARIABLEN FÜR WEB-INTERFACE
# ══════════════════════════════════════════════════════════════════════════════
bot_instance = None  # Wird für Flask-Zugriff verwendet

# ══════════════════════════════════════════════════════════════════════════════
#  BOT-KLASSE
# ══════════════════════════════════════════════════════════════════════════════
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.groq_api_key = GROQ_API_KEY
        
    async def setup_hook(self):
        logging.info("🔧 setup_hook gestartet...")
        logging.info(f"🌐 BOT_MODE: {BOT_MODE}")

        # Lade Features, falls vorhanden
        features_dir = "./features"
        if os.path.exists(features_dir):
            for filename in sorted(os.listdir(features_dir)):
                if filename.endswith(".py") and not filename.startswith("__"):
                    ext = f"features.{filename[:-3]}"
                    try:
                        await self.load_extension(ext)
                        logging.info(f"✅ Feature '{filename}' geladen.")
                    except Exception:
                        logging.error(f"❌ Fehler beim Laden von '{filename}':")
                        traceback.print_exc()
        else:
            logging.info("📁 Kein 'features' Verzeichnis gefunden - fahre ohne Cogs fort")

        # Sync Commands basierend auf Modus
        if BOT_MODE == "dev":
            for gid in GUILD_IDS:
                guild = discord.Object(id=gid)
                try:
                    synced = await self.tree.sync(guild=guild)
                    logging.info(
                        f"🔄 [DEV] Guild {gid}: {len(synced)} Command(s) gesynct: "
                        f"{[c.name for c in synced]}"
                    )
                except Exception:
                    logging.error(f"❌ Sync-Fehler für Guild {gid}:")
                    traceback.print_exc()

        elif BOT_MODE == "public":
            # Globale Commands syngen
            try:
                synced = await self.tree.sync()
                logging.info(
                    f"🌍 [PUBLIC] Global gesynct: {len(synced)} Command(s): "
                    f"{[c.name for c in synced]}"
                )
            except Exception:
                logging.error("❌ Globaler Sync-Fehler:")
                traceback.print_exc()

            # Guild-spezifische Commands syngen
            for gid in GUILD_IDS:
                guild = discord.Object(id=gid)
                try:
                    synced_guild = await self.tree.sync(guild=guild)
                    logging.info(
                        f"🔄 [PUBLIC] Guild {gid}: {len(synced_guild)} guild-spez. "
                        f"Command(s) gesynct: {[c.name for c in synced_guild]}"
                    )
                except Exception:
                    logging.error(f"❌ Guild-Sync-Fehler für {gid}:")
                    traceback.print_exc()
        else:
            logging.error(f"❌ Unbekannter BOT_MODE: '{BOT_MODE}'")

    async def on_ready(self):
        logging.info(f"✅ {self.user} ist online! (v{BOT_VERSION} | Modus: {BOT_MODE})")
        logging.info(f"📋 Registrierte Commands: {[c.name for c in self.tree.get_commands()]}")
        logging.info(f"🏠 Aktive Server: {len(self.guilds)}")
        
        # Setze Status
        await self.change_presence(
            activity=discord.Game(name=f"HelperXBot v{BOT_VERSION} | /help")
        )

# ══════════════════════════════════════════════════════════════════════════════
#  BOT INITIALISIEREN
# ══════════════════════════════════════════════════════════════════════════════
bot = MyBot()
bot_instance = bot  # Für Zugriff von aussen (z.B. Flask)

# ══════════════════════════════════════════════════════════════════════════════
#  EINFACHE BEFEHLE FÜR TESTZECKE
# ══════════════════════════════════════════════════════════════════════════════
@bot.tree.command(name="ping", description="Teste die Bot-Latenz")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! 🏓 Latenz: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="info", description="Zeige Bot-Informationen")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 HelperXBot",
        description=f"Version {BOT_VERSION}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Bot Name", value=bot.user.name, inline=True)
    embed.add_field(name="Bot ID", value=bot.user.id, inline=True)
    embed.add_field(name="Server", value=len(bot.guilds), inline=True)
    embed.add_field(name="Modus", value=BOT_MODE, inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Zeige den Avatar eines Users")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user
    
    embed = discord.Embed(
        title=f"{member.name}'s Avatar",
        color=discord.Color.blue()
    )
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ══════════════════════════════════════════════════════════════════════════════
#  ON READY EVENT (Wurde bereits in MyClass definiert, aber wir fügen hinzu)
# ══════════════════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    # Dieser Event-Handler überschreibt den in MyBot, also rufen wir die Parent-Methode auf
    pass  # Wird bereits von MyBot.on_ready() behandelt

# ══════════════════════════════════════════════════════════════════════════════
#  FUNKTION FÜR FLASK (UM BOT-ZUGRIFF ZU ERMÖGLICHEN)
# ══════════════════════════════════════════════════════════════════════════════
def get_bot_stats():
    """Gibt Bot-Statistiken für das Web-Interface zurück"""
    if bot_instance and bot_instance.is_ready():
        return {
            "status": "online",
            "username": str(bot_instance.user),
            "guilds": len(bot_instance.guilds),
            "users": sum(guild.member_count for guild in bot_instance.guilds),
            "version": BOT_VERSION,
            "mode": BOT_MODE,
            "latency": round(bot_instance.latency * 1000)
        }
    return {"status": "offline"}

# ══════════════════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════════════════
def run_bot():
    """Startet den Bot (für separate Ausführung)"""
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logging.error("❌ Fehler: Ungültiger Discord Token!")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Unerwarteter Fehler: {e}")
        traceback.print_exc()
        sys.exit(1)

async def start_bot():
    """Startet den Bot asynchron (für Integration mit Flask)"""
    async with bot:
        await bot.start(DISCORD_TOKEN)

def main():
    """Hauptfunktion für direkte Ausführung"""
    run_bot()

if __name__ == "__main__":
    main()
