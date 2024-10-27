from flask import Flask, request, jsonify
import discord
from discord.ext import commands
import asyncio
import threading
from functools import wraps
import os
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'TOKEN ID')
    API_USERNAME = os.getenv('API_USERNAME', 'Username')
    API_PASSWORD = os.getenv('API_PASSWORD', ' Password ')
    PORT = int(os.getenv('PORT', 5000))

app = Flask(__name__)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

bot_ready = asyncio.Event()

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def check_auth(username, password):
    return username == Config.API_USERNAME and password == Config.API_PASSWORD

def authenticate():
    return jsonify({'error': 'Authentication required'}), 401, {
        'WWW-Authenticate': 'Basic realm="Login Required"'
    }

@bot.event
async def on_ready():
    logger.info(f"Bot is ready and logged in as {bot.user}")
    logger.info(f"Bot is in {len(bot.guilds)} servers")
    for guild in bot.guilds:
        logger.info(f"- {guild.name} (id: {guild.id})")
    bot_ready.set()

@bot.event
async def on_guild_join(guild):
    logger.info(f"Bot joined new server: {guild.name} (id: {guild.id})")

@bot.event
async def on_guild_remove(guild):
    logger.info(f"Bot left server: {guild.name} (id: {guild.id})")


#api routes will begin here
@app.route('/servers', methods=['GET'])
@require_auth
def list_servers():
    if not bot_ready.is_set():
        return jsonify({'error': 'Bot not ready'}), 503
    
    servers = [{
        'id': guild.id,
        'name': guild.name,
        'member_count': guild.member_count,
        'roles': [{'id': role.id, 'name': role.name} for role in guild.roles]
    } for guild in bot.guilds]
    
    return jsonify({'servers': servers})

@app.route('/check-user-in-server', methods=['GET'])
@require_auth
def check_user_in_server():
    if not bot_ready.is_set():
        return jsonify({'error': 'Bot not ready'}), 503
        
    user_id = request.args.get('userId')
    server_id = request.args.get('serverId')
    
    if not user_id or not server_id:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        guild = bot.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        member = guild.get_member(int(user_id))
        return jsonify({
            'joined': member is not None,
            'server_name': guild.name,
            'joined_at': member.joined_at.isoformat() if member else None
        })
    except ValueError:
        return jsonify({'error': 'Invalid ID format'}), 400
    except Exception as e:
        logger.error(f"Error checking user in server: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/check-user-role', methods=['GET'])
@require_auth
def check_user_role():
    if not bot_ready.is_set():
        return jsonify({'error': 'Bot not ready'}), 503
        
    user_id = request.args.get('userId')
    server_id = request.args.get('serverId')
    
    if not all([user_id, server_id]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        guild = bot.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        member = guild.get_member(int(user_id))
        if not member:
            return jsonify({'error': 'User not found'}), 404
            
        user_roles = []
        for role in member.roles:
            if role.name != "@everyone":
                user_roles.append({
                    'role_id': role.id,
                    'role_name': role.name,
                    'color': str(role.color),
                    'position': role.position,
                    'is_hoisted': role.hoist,
                    'is_mentionable': role.mentionable
                })
        
        return jsonify({
            'user_id': str(member.id),
            'username': member.name,
            'nickname': member.nick,
            'server_name': guild.name,
            'server_id': str(guild.id),
            'roles': user_roles,
            'highest_role': member.top_role.name if len(user_roles) > 0 else None,
            'has_roles': len(user_roles) > 0
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid ID format'}), 400
    except Exception as e:
        logger.error(f"Error checking user role: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/user-info', methods=['GET'])
@require_auth
def get_user_info():
    if not bot_ready.is_set():
        return jsonify({'error': 'Bot not ready'}), 503
        
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({'error': 'Missing userId parameter'}), 400
    
    try:
        user_id = int(user_id)
        server_memberships = []
        
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                server_memberships.append({
                    'server_id': guild.id,
                    'server_name': guild.name,
                    'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                    'roles': [{'id': role.id, 'name': role.name} for role in member.roles],
                    'nickname': member.nick
                })
        
        if not server_memberships:
            return jsonify({'error': 'User not found in any server'}), 404
            
        return jsonify({
            'user_id': user_id,
            'server_memberships': server_memberships
        })
    except ValueError:
        return jsonify({'error': 'Invalid user ID format'}), 400
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def run_bot():
    asyncio.run(bot.start(Config.DISCORD_TOKEN))

def run_flask():
    
    app.run(host='0.0.0.0', port=Config.PORT)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    run_flask()