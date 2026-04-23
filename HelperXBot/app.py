import os
import requests
import threading
import logging
from flask import Flask, redirect, request, session, url_for, render_template, jsonify
from functools import wraps
from dotenv import load_dotenv

# Lade Environment Variablen
load_dotenv()

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-this')

# Discord OAuth2 Configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
# WICHTIG: Die Redirect-URI MUSS in Render als Environment Variable gesetzt werden!
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')  # Kein Fallback mehr!
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN')

# Prüfe ob wichtige Variablen gesetzt sind
if not DISCORD_REDIRECT_URI:
    logging.error("❌ DISCORD_REDIRECT_URI ist nicht gesetzt! Bitte in Render als Environment Variable hinzufügen.")
    # Für Render: z.B. https://deine-app.onrender.com/callback

if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
    logging.error("❌ DISCORD_CLIENT_ID oder DISCORD_CLIENT_SECRET nicht gesetzt!")

# Discord API endpoints
DISCORD_API_BASE = 'https://discord.com/api/v10'
DISCORD_AUTHORIZE_URL = f'{DISCORD_API_BASE}/oauth2/authorize'
DISCORD_TOKEN_URL = f'{DISCORD_API_BASE}/oauth2/token'
DISCORD_USER_URL = f'{DISCORD_API_BASE}/users/@me'
DISCORD_GUILDS_URL = f'{DISCORD_API_BASE}/users/@me/guilds'

# Bot-Statistiken
bot_stats = {
    "status": "offline",
    "username": "HelperXBot",
    "guilds": 0,
    "users": 0,
    "version": "9.9",
    "mode": "public",
    "latency": 0
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Startseite"""
    if 'user' in session:
        return render_template('index.html', user=session['user'], bot_stats=bot_stats)
    return render_template('login.html')

@app.route('/login')
def login():
    """Discord OAuth2 Login"""
    if not DISCORD_CLIENT_ID or not DISCORD_REDIRECT_URI:
        return "Discord OAuth2 ist nicht korrekt konfiguriert. Bitte den Administrator kontaktieren.", 500
    
    params = {
        'client_id': DISCORD_CLIENT_ID,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'identify guilds'
    }
    auth_url = f"{DISCORD_AUTHORIZE_URL}?{requests.compat.urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """OAuth2 Callback von Discord"""
    code = request.args.get('code')
    
    if not code:
        return redirect(url_for('login'))
    
    # Exchange code for access token
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    
    if response.status_code != 200:
        logging.error(f"Token exchange failed: {response.text}")
        return "Failed to get access token", 400
    
    token_data = response.json()
    access_token = token_data.get('access_token')
    
    # Get user info
    user_response = requests.get(
        DISCORD_USER_URL,
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if user_response.status_code != 200:
        logging.error(f"User info failed: {user_response.text}")
        return "Failed to get user info", 400
    
    user_data = user_response.json()
    
    # Get user's guilds
    guilds_response = requests.get(
        DISCORD_GUILDS_URL,
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if guilds_response.status_code == 200:
        session['guilds'] = guilds_response.json()
    
    session['user'] = user_data
    session['access_token'] = access_token
    
    logging.info(f"User logged in: {user_data['username']}#{user_data.get('discriminator', '0')}")
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard nach Login"""
    return render_template('dashboard.html', user=session['user'], guilds=session.get('guilds', []), bot_stats=bot_stats)

@app.route('/api/bot/stats')
def api_bot_stats():
    """API-Endpoint für Bot-Statistiken"""
    return jsonify(bot_stats)

@app.route('/api/user/guilds')
@login_required
def api_user_guilds():
    """API-Endpoint für User Guilds"""
    return jsonify(session.get('guilds', []))

@app.route('/status')
def status():
    """Status Page für Render"""
    return jsonify({
        "status": "online",
        "bot_status": bot_stats["status"],
        "bot_guilds": bot_stats["guilds"],
        "version": bot_stats["version"],
        "render_url": DISCORD_REDIRECT_URI
    })

@app.route('/invite')
def invite():
    """Bot Invite Link"""
    if not DISCORD_CLIENT_ID:
        return "Client ID not configured", 500
    
    permissions = 8  # Administrator (ändern nach Bedarf)
    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&permissions={permissions}&scope=bot%20applications.commands"
    return redirect(invite_url)

# ══════════════════════════════════════════════════════════════════════════════
#  BOT INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def update_bot_stats():
    """Holt Statistiken vom Bot"""
    global bot_stats
    try:
        import importlib.util
        bot_module_path = os.path.join(os.path.dirname(__file__), 'bot.py')
        if os.path.exists(bot_module_path):
            spec = importlib.util.spec_from_file_location("bot", bot_module_path)
            bot_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bot_module)
            
            if hasattr(bot_module, 'get_bot_stats'):
                stats = bot_module.get_bot_stats()
                bot_stats.update(stats)
                logging.info(f"Bot stats updated")
    except Exception as e:
        logging.warning(f"Could not update bot stats: {e}")

def start_bot_thread():
    """Startet den Bot in einem separaten Thread"""
    try:
        import bot
        from bot import run_bot
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logging.info("🤖 Bot thread started")
        threading.Timer(5.0, update_bot_stats).start()
    except Exception as e:
        logging.error(f"Failed to start bot thread: {e}")

# Starte den Bot nur auf Render (nicht lokal)
if os.getenv('RENDER', 'false').lower() == 'true' and os.getenv('RUN_BOT_WITH_APP', 'true').lower() == 'true':
    threading.Timer(2.0, start_bot_thread).start()

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
