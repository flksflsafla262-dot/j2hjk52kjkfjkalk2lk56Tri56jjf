# proxy_bot.py
# Размести на Bothost как нового бота
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Данные твоего приложения с my.telegram.org
API_ID = 33451128
API_HASH = "a650f1c575f22f8bb35a00bdf93a7709"

# Токен бота-прокси (получил у @BotFather)
BOT_TOKEN = "8825077658:AAGLUJDN87VG4CQ5l2EtW2NanDJBQ1Fgv50"

# Бот Discord Sensor
SENSOR_BOT = "@discords_sennors_bot"

# HTTP сервер для приложухи
from aiohttp import web

# Клиент для общения с Discord Sensor
client = None

async def init_telegram():
    global client
    client = TelegramClient('proxy_bot_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print("Bot started!")

async def lookup_discord(discord_id):
    """Запрашивает данные у Discord Sensor"""
    try:
        entity = await client.get_entity(SENSOR_BOT)
        for cmd in [discord_id, f'/lookup {discord_id}', f'/search {discord_id}', f'/id {discord_id}']:
            try:
                await client.send_message(entity, cmd)
                await asyncio.sleep(2)
                messages = await client.get_messages(entity, limit=1)
                if messages and messages[0] and messages[0].text:
                    text = messages[0].text
                    if text.startswith('/') or 'error' in text.lower():
                        continue
                    return {'success': True, 'data': text}
            except:
                continue
        return {'success': False, 'error': 'not found'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def handle_lookup(request):
    """Обрабатывает HTTP-запрос от приложухи"""
    try:
        data = await request.json()
        discord_id = data.get('id', '').strip()
        
        if not discord_id or not discord_id.isdigit():
            return web.json_response({'success': False, 'error': 'invalid id'})
        
        result = await lookup_discord(discord_id)
        return web.json_response(result)
    except:
        return web.json_response({'success': False, 'error': 'internal error'})

async def handle_ping(request):
    return web.json_response({'status': 'ok'})

async def main():
    await init_telegram()
    
    app = web.Application()
    app.router.add_post('/lookup', handle_lookup)
    app.router.add_get('/ping', handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    print("HTTP server on port 8080")
    print("Bot is ready!")
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())