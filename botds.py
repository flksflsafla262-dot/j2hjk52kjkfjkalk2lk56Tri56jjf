# ============================================================
# TRIUMPHMANIA DISCORD BOT — Version X.2.0
# Файл: botds.py
# HWID система полностью работает, язык нормальный
# Все функции сохранены, ничего не урезано
# ============================================================

import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
import io
import csv
import json
import os
import sys
import re
import time
import hashlib
import hmac
import secrets
import base64
import socket
import traceback
import logging
import logging.handlers
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any, Set
from dataclasses import dataclass, field

# ============================================================
# CONFIG
# ============================================================
@dataclass(frozen=True)
class BotConfig:
    BOT_TOKEN: str = "MTUwNTIyMzg5NTQ0NjE5MjM2OQ.G5QkmW.NurkyNU-rhupnCytXME5HVovvFqGUY9F2QzCxU"
    GUILD_ID: int = 1507343173729390734
    MGMT_CHANNEL_ID: int = 1507343173729390737
    STORAGE_CHANNEL_ID: int = 1507359564322963637
    WEBHOOK_URL: str = "https://discord.com/api/webhooks/1507348237894287472/lGvh0CK5isaSwnU1MiMpwILelDncoZJc6tERjYeMbvD-Nz5k8wgNSAWsFS62qpMq-7iE"
    AUTH_USERS: Set[int] = field(default_factory=lambda: {1389945313225080953})
    API_PORT: int = 14880
    MAX_DAILY_REQ: int = 80
    CLEANUP_INTERVAL: int = 300
    DB_RELOAD_INTERVAL: int = 900
    MASTER_FILE: str = "licenses.txt"
    COUNTERS_FILE: str = "counters.txt"
    STATE_FILE: str = "state.txt"
    AUDIT_FILE: str = "audit.txt"
    KEY_PATTERN: str = r'^[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$'

CFG = BotConfig()

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger("TriumphBot")
logger.setLevel(logging.DEBUG)

file_handler = logging.handlers.RotatingFileHandler(
    "triumph_bot.log", maxBytes=20*1024*1024, backupCount=10, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%H:%M:%S [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
))
logger.addHandler(console_handler)

# ============================================================
# PORT CHECKER
# ============================================================
def check_and_free_port(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('0.0.0.0', port))
        sock.close()
        return True
    except OSError:
        if sys.platform == 'win32':
            try:
                result = os.popen(f'netstat -ano | findstr :{port}').read()
                for line in result.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 5:
                        os.system(f'taskkill /PID {parts[-1]} /F 2>nul')
                time.sleep(2)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', port))
                sock.close()
                return True
            except:
                pass
        return False

# ============================================================
# COLOR PALETTE
# ============================================================
class Palette:
    NEON_PINK = 0xFF1493
    DEEP_PINK = 0xC70067
    NEON_BLUE = 0x00BFFF
    DEEP_BLUE = 0x0A0A2E
    NEON_GREEN = 0x39FF14
    NEON_RED = 0xFF3131
    NEON_ORANGE = 0xFF8C00
    NEON_PURPLE = 0xBF00FF
    DARK_GREY = 0x1A1A1A
    MID_GREY = 0x2A2A2A
    LIGHT_GREY = 0x444444
    WHITE = 0xFFFFFF
    BLACK = 0x000000

# ============================================================
# WEBHOOK LOGGER
# ============================================================
class WebhookLogger:
    def __init__(self, wh_url: str):
        self.wh_url = wh_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running = True
        self.worker: Optional[asyncio.Task] = None

    async def init(self):
        conn = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=conn,
            headers={"User-Agent": "TriumphMania/X.2", "Content-Type": "application/json"}
        )
        self.worker = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        while self.running:
            try:
                data = await asyncio.wait_for(self.queue.get(), timeout=2.0)
                await self._send(data)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Webhook worker error: {e}")

    async def _send(self, data: Dict):
        if not self.session:
            return
        try:
            wh = discord.Webhook.from_url(self.wh_url, session=self.session)
            embed = discord.Embed(
                title=data.get('title', ''),
                description=data.get('desc', '')[:1800],
                color=data.get('color', Palette.DARK_GREY),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="TriumphMania Audit")
            await wh.send(embed=embed)
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")

    def log(self, title: str, desc: str, color: int = Palette.DARK_GREY):
        safe = desc.replace(CFG.BOT_TOKEN, "[REDACTED]")
        try:
            self.queue.put_nowait({'title': title, 'desc': safe[:1800], 'color': color})
        except asyncio.QueueFull:
            pass

    async def shutdown(self):
        self.running = False
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()

webhook = WebhookLogger(CFG.WEBHOOK_URL)

# ============================================================
# DISCORD FILE STORAGE
# ============================================================
class DiscordFileStorage:
    def __init__(self, bot_ref):
        self.bot = bot_ref
        self._cache: Dict[str, Dict] = {}
        self._cache_loaded = False
        self._lock = asyncio.Lock()

    @property
    def storage_channel(self) -> Optional[discord.TextChannel]:
        return self.bot.get_channel(CFG.STORAGE_CHANNEL_ID)

    async def _find_msg_with_file(self, filename: str) -> Optional[discord.Message]:
        ch = self.storage_channel
        if not ch:
            return None
        try:
            async for msg in ch.history(limit=50):
                if msg.attachments:
                    for att in msg.attachments:
                        if att.filename == filename:
                            return msg
        except:
            pass
        return None

    async def _read_master(self) -> str:
        msg = await self._find_msg_with_file(CFG.MASTER_FILE)
        if msg:
            for att in msg.attachments:
                if att.filename == CFG.MASTER_FILE:
                    try:
                        return (await att.read()).decode('utf-8', errors='replace')
                    except:
                        pass
        return ""

    async def _write_master(self, content: str):
        ch = self.storage_channel
        if not ch:
            return
        try:
            old = await self._find_msg_with_file(CFG.MASTER_FILE)
            if old:
                try:
                    await old.delete()
                except:
                    pass
        except:
            pass
        try:
            file = discord.File(io.BytesIO(content.encode('utf-8')), filename=CFG.MASTER_FILE)
            total = len(self._cache)
            active = sum(1 for lic in self._cache.values() 
                        if not lic['is_frozen'] and lic['expires_at'] > time.time())
            frozen = sum(1 for lic in self._cache.values() if lic['is_frozen'])
            
            embed = discord.Embed(
                title="License DB Updated",
                color=Palette.NEON_PINK,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Total", value=f"**{total}**", inline=True)
            embed.add_field(name="Active", value=f"**{active}**", inline=True)
            embed.add_field(name="Frozen", value=f"**{frozen}**", inline=True)
            embed.set_footer(text=f"TriumphMania X.2 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            await ch.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"write_master error: {e}")

    async def load_cache(self):
        async with self._lock:
            self._cache.clear()
            content = await self._read_master()
            if content:
                for line in content.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('|')
                    if len(parts) >= 10:
                        key = parts[0]
                        # КЛЮЧЕВОЙ МОМЕНТ: правильно читаем hwid_hash
                        raw_hwid = parts[3] if len(parts) > 3 else 'None'
                        if raw_hwid and raw_hwid.strip() not in ('', 'None', 'null'):
                            hwid_hash = raw_hwid.strip()
                        else:
                            hwid_hash = None
                        
                        self._cache[key] = {
                            'license_key': key,
                            'user_id': int(parts[1]),
                            'discord_name': parts[2],
                            'hwid_hash': hwid_hash,  # <-- Правильно сохранённый HWID
                            'created_at': float(parts[4]),
                            'expires_at': float(parts[5]),
                            'days_total': int(parts[6]),
                            'is_frozen': int(parts[7]),
                            'frozen_at': float(parts[8]) if len(parts) > 8 and parts[8] and parts[8] != 'None' else None,
                            'was_unfrozen': int(parts[9]) if len(parts) > 9 else 0
                        }
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._cache)} licenses")

    def _serialize(self) -> str:
        lines = []
        for k, lic in self._cache.items():
            hwid_str = lic['hwid_hash'] if lic['hwid_hash'] else 'None'
            frozen_at_str = str(lic['frozen_at']) if lic['frozen_at'] else 'None'
            lines.append(
                f"{lic['license_key']}|{lic['user_id']}|{lic['discord_name']}|"
                f"{hwid_str}|{lic['created_at']}|{lic['expires_at']}|"
                f"{lic['days_total']}|{lic['is_frozen']}|{frozen_at_str}|{lic['was_unfrozen']}"
            )
        return '\n'.join(lines)

    async def _save(self):
        await self._write_master(self._serialize())

    def gen_key(self) -> str:
        for _ in range(100):
            raw = secrets.token_hex(10).upper()
            segments = [raw[i:i+4] for i in range(0, 16, 4)]
            key = "-".join(segments)
            if key not in self._cache:
                return key
        raise RuntimeError("Failed to generate key")

    async def create_license(self, uid: int, days: int, name: str) -> str:
        async with self._lock:
            key = self.gen_key()
            now = time.time()
            exp = now + (days * 86400)
            self._cache[key] = {
                'license_key': key, 'user_id': uid, 'discord_name': name,
                'hwid_hash': None, 'created_at': now, 'expires_at': exp,
                'days_total': days, 'is_frozen': 0, 'frozen_at': None, 'was_unfrozen': 0
            }
            await self._save()
            await self._append_audit("LICENSE_CREATED", uid, f"Key={key} Days={days}")
            return key

    async def delete_license(self, key: str) -> bool:
        async with self._lock:
            if key not in self._cache:
                return False
            uid = self._cache[key]['user_id']
            del self._cache[key]
            await self._save()
            await self._append_audit("LICENSE_DELETED", uid, f"Key={key}")
            return True

    async def get_license(self, key: str) -> Optional[Dict]:
        return self._cache.get(key)

    async def get_all(self) -> List[Dict]:
        return list(self._cache.values())

    async def get_user_licenses(self, uid: int) -> List[Dict]:
        return [lic for lic in self._cache.values() if lic['user_id'] == uid]

    async def add_days(self, key: str, days: int) -> bool:
        async with self._lock:
            if key not in self._cache:
                return False
            self._cache[key]['expires_at'] += days * 86400
            self._cache[key]['days_total'] += days
            await self._save()
            await self._append_audit("DAYS_ADDED", self._cache[key]['user_id'], f"Key={key} Days=+{days}")
            return True

    async def freeze(self, key: str) -> Tuple[bool, str]:
        async with self._lock:
            if key not in self._cache:
                return False, "InvalidKey"
            lic = self._cache[key]
            if lic['was_unfrozen']:
                return False, "AlreadyUnfrozen"
            if lic['is_frozen']:
                return False, "AlreadyFrozen"
            lic['is_frozen'] = 1
            lic['frozen_at'] = time.time()
            await self._save()
            await self._append_audit("LICENSE_FROZEN", lic['user_id'], f"Key={key}")
            return True, "OK"

    async def unfreeze(self, key: str) -> Tuple[bool, str]:
        async with self._lock:
            if key not in self._cache:
                return False, "InvalidKey"
            lic = self._cache[key]
            if not lic['is_frozen']:
                return False, "NotFrozen"
            dur = time.time() - lic['frozen_at']
            lic['is_frozen'] = 0
            lic['expires_at'] += dur
            lic['was_unfrozen'] = 1
            lic['frozen_at'] = None
            await self._save()
            await self._append_audit("LICENSE_UNFROZEN", lic['user_id'], f"Key={key}")
            return True, "OK"

    async def validate(self, key: str, hwid: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Валидация лицензионного ключа с проверкой HWID.
        
        Логика HWID:
        1. Если hwid_hash в базе пустой или None — это первый вход, привязываем HWID
        2. Если hwid_hash заполнен и совпадает с переданным — доступ разрешён
        3. Если hwid_hash заполнен и НЕ совпадает — доступ запрещён (InvalidHwid)
        """
        async with self._lock:
            # Проверка глобальной заморозки
            state = await self._read_state()
            if 'global_freeze=1' in state:
                return False, "Testing. Wait please", None
            
            # Поиск лицензии в кеше
            lic = self._cache.get(key)
            if not lic:
                return False, "InvalidKey", None
            
            now = time.time()
            
            # Проверка истечения срока (только для незамороженных ключей)
            if not lic['is_frozen'] and lic['expires_at'] <= now:
                # Ключ истёк — удаляем из базы
                del self._cache[key]
                await self._save()
                await self._append_audit("LICENSE_EXPIRED", None, f"Key={key}")
                return False, "InvalidKey", None
            
            # ПРОВЕРКА HWID — САМЫЙ ВАЖНЫЙ МОМЕНТ
            if lic['hwid_hash'] is not None:
                # HWID уже привязан — проверяем совпадение
                if lic['hwid_hash'] != hwid:
                    # HWID не совпадает — отказ в доступе
                    await self._append_audit("HWID_MISMATCH", lic['user_id'], f"Key={key[:10]}...")
                    return False, "InvalidHwid", None
                # HWID совпадает — доступ разрешён
            else:
                # HWID ещё не привязан — привязываем текущий
                lic['hwid_hash'] = hwid
                await self._save()
                await self._append_audit("HWID_BOUND", lic['user_id'], f"Key={key[:10]}...")
            
            # Все проверки пройдены
            await self._append_audit("LICENSE_VALIDATED", lic['user_id'], f"Key={key[:10]}...")
            
            # Возвращаем копию данных лицензии, включая hwid_hash
            license_copy = dict(lic)
            return True, "OK", license_copy

    async def _read_state(self) -> str:
        msg = await self._find_msg_with_file(CFG.STATE_FILE)
        if msg:
            for att in msg.attachments:
                if att.filename == CFG.STATE_FILE:
                    try:
                        return (await att.read()).decode('utf-8', errors='replace')
                    except:
                        pass
        return ""

    async def _write_state(self, content: str):
        ch = self.storage_channel
        if not ch:
            return
        try:
            old = await self._find_msg_with_file(CFG.STATE_FILE)
            if old:
                try:
                    await old.delete()
                except:
                    pass
        except:
            pass
        try:
            file = discord.File(io.BytesIO(content.encode('utf-8')), filename=CFG.STATE_FILE)
            await ch.send(
                embed=discord.Embed(
                    title="System State Updated",
                    color=Palette.NEON_PURPLE,
                    timestamp=datetime.utcnow()
                ),
                file=file
            )
        except:
            pass

    async def set_global_freeze(self, state: bool, by: str):
        c = f"global_freeze={'1' if state else '0'}\nupdated_by={by}\nupdated_at={time.time()}"
        await self._write_state(c)
        await self._append_audit("GLOBAL_FREEZE" if state else "GLOBAL_UNFREEZE", None, f"By={by}")

    async def is_global_frozen(self) -> bool:
        return 'global_freeze=1' in await self._read_state()

    async def _read_counters(self) -> str:
        msg = await self._find_msg_with_file(CFG.COUNTERS_FILE)
        if msg:
            for att in msg.attachments:
                if att.filename == CFG.COUNTERS_FILE:
                    try:
                        return (await att.read()).decode('utf-8', errors='replace')
                    except:
                        pass
        return ""

    async def _write_counters(self, content: str):
        ch = self.storage_channel
        if not ch:
            return
        try:
            old = await self._find_msg_with_file(CFG.COUNTERS_FILE)
            if old:
                try:
                    await old.delete()
                except:
                    pass
        except:
            pass
        try:
            file = discord.File(io.BytesIO(content.encode('utf-8')), filename=CFG.COUNTERS_FILE)
            await ch.send(
                embed=discord.Embed(
                    title="Request Counters Updated",
                    color=Palette.NEON_ORANGE,
                    timestamp=datetime.utcnow()
                ),
                file=file
            )
        except:
            pass

    async def check_and_increment(self, key: str) -> Tuple[bool, int]:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        content = await self._read_counters()
        counters = {}
        for line in content.strip().split('\n'):
            parts = line.strip().split('|')
            if len(parts) >= 3:
                counters[f"{parts[0]}|{parts[1]}"] = int(parts[2])
        ck = f"{key}|{today}"
        curr = counters.get(ck, 0)
        if curr >= CFG.MAX_DAILY_REQ:
            return False, curr
        counters[ck] = curr + 1
        await self._write_counters('\n'.join([f"{k}|{v}" for k, v in counters.items()]))
        return True, curr + 1

    async def get_requests(self, key: str) -> int:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        content = await self._read_counters()
        for line in content.strip().split('\n'):
            parts = line.strip().split('|')
            if len(parts) >= 3 and parts[0] == key and parts[1] == today:
                return int(parts[2])
        return 0

    async def _read_audit(self) -> str:
        msg = await self._find_msg_with_file(CFG.AUDIT_FILE)
        if msg:
            for att in msg.attachments:
                if att.filename == CFG.AUDIT_FILE:
                    try:
                        return (await att.read()).decode('utf-8', errors='replace')
                    except:
                        pass
        return ""

    async def _write_audit(self, content: str):
        ch = self.storage_channel
        if not ch:
            return
        try:
            old = await self._find_msg_with_file(CFG.AUDIT_FILE)
            if old:
                try:
                    await old.delete()
                except:
                    pass
        except:
            pass
        try:
            file = discord.File(io.BytesIO(content.encode('utf-8')), filename=CFG.AUDIT_FILE)
            await ch.send(
                embed=discord.Embed(
                    title="Audit Log Updated",
                    color=Palette.NEON_BLUE,
                    timestamp=datetime.utcnow()
                ),
                file=file
            )
        except:
            pass

    async def _append_audit(self, act: str, uid: Optional[int], dets: str):
        ts = time.time()
        line = f"{ts}|{act}|{uid or 'N/A'}|{dets.replace('|', '/')}"
        ex = await self._read_audit()
        if ex.strip():
            lines = ex.strip().split('\n')
            lines.append(line)
            if len(lines) > 500:
                lines = lines[-500:]
            await self._write_audit('\n'.join(lines))
        else:
            await self._write_audit(line)

    async def get_audit(self, limit: int = 50) -> List[str]:
        c = await self._read_audit()
        lines = c.strip().split('\n')
        return lines[-limit:] if lines and lines[0] else []

    async def cleanup(self):
        now = time.time()
        td = [k for k, lic in self._cache.items() if not lic['is_frozen'] and lic['expires_at'] <= now]
        if td:
            async with self._lock:
                for k in td:
                    del self._cache[k]
                await self._save()
                await self._append_audit("EXPIRED_CLEANUP", None, f"Removed={len(td)}")

# ============================================================
# SEARCH DB MANAGER
# ============================================================
class SearchDBManager:
    def __init__(self, bot_ref):
        self.bot = bot_ref
        self.databases: Dict[str, Tuple[Tuple[str, ...], List[List[str]]]] = {}
        self.loaded = False
        self.total = 0

    @property
    def storage_channel(self) -> Optional[discord.TextChannel]:
        return self.bot.get_channel(CFG.STORAGE_CHANNEL_ID)

    async def load_all(self):
        ch = self.storage_channel
        if not ch:
            return 0
        self.databases.clear()
        count = 0
        try:
            async for msg in ch.history(limit=200):
                if not msg.attachments:
                    continue
                for att in msg.attachments:
                    fn = att.filename.lower()
                    if fn in (CFG.MASTER_FILE, CFG.COUNTERS_FILE, CFG.STATE_FILE, CFG.AUDIT_FILE):
                        continue
                    if not fn.endswith(('.csv', '.txt', '.json')):
                        continue
                    try:
                        cnt = await att.read()
                        if fn.endswith('.csv'):
                            await self._parse_csv(att.filename, cnt)
                        elif fn.endswith('.json'):
                            await self._parse_json(att.filename, cnt)
                        elif fn.endswith('.txt'):
                            await self._parse_txt(att.filename, cnt)
                        count += 1
                    except:
                        pass
        except:
            pass
        self.loaded = True
        self.total = sum(len(v[1]) for v in self.databases.values())
        return count

    async def _parse_csv(self, fn, cnt):
        t = cnt.decode('utf-8', errors='replace')
        r = list(csv.reader(io.StringIO(t)))
        if r:
            self.databases[fn] = (tuple(h.strip() for h in r[0]), [list(x) for x in r[1:] if any(c.strip() for c in x)])

    async def _parse_json(self, fn, cnt):
        p = json.loads(cnt.decode('utf-8'))
        if isinstance(p, list) and p:
            if isinstance(p[0], dict):
                h = tuple(p[0].keys())
                self.databases[fn] = (h, [[str(i.get(k, '')) for k in h] for i in p])
            else:
                self.databases[fn] = (('value',), [[str(i)] for i in p])

    async def _parse_txt(self, fn, cnt):
        l = [x.strip() for x in cnt.decode('utf-8', errors='replace').split('\n') if x.strip()]
        if l:
            self.databases[fn] = (('data',), [[x] for x in l])

    def search(self, q: str, limit: int = 50) -> List[Dict]:
        if not self.loaded:
            return []
        q = q.lower().strip()
        r = []
        for fn, (h, d) in self.databases.items():
            for row in d:
                rt = ' '.join(str(c).lower() for c in row)
                if q in rt:
                    sc = rt.count(q)
                    if any(str(c).lower() == q for c in row):
                        sc += 15
                    r.append({'source': fn, 'data': dict(zip(h, row)), 'score': sc})
        r.sort(key=lambda x: x['score'], reverse=True)
        return r[:limit]

    def stats(self):
        return {'files': len(self.databases), 'records': self.total}

# ============================================================
# EMBED BUILDER
# ============================================================
class EmbedBuilder:
    @staticmethod
    def main_menu() -> discord.Embed:
        e = discord.Embed(
            title="TriumphMania License Management",
            description="Welcome to the license management system.\n\n**Available actions:**",
            color=Palette.NEON_PINK,
            timestamp=datetime.utcnow()
        )
        e.add_field(name="[+] Create Key", value="Generate a new license key.", inline=False)
        e.add_field(name="[-] Delete Key", value="Remove an existing license.", inline=False)
        e.add_field(name="[*] History", value="Browse all licenses.", inline=False)
        e.add_field(name="[!] Freeze All", value="Global freeze - blocks logins.", inline=False)
        e.add_field(name="[?] Unfreeze All", value="Restore normal operation.", inline=False)
        e.add_field(name="[#] Statistics", value="View system statistics.", inline=False)
        e.add_field(name="[@] Reload DB", value="Refresh search databases.", inline=False)
        e.set_footer(text="TriumphMania X.2 | use !key to open")
        return e

    @staticmethod
    def license_created(key: str, uid: int, name: str, days: int) -> discord.Embed:
        e = discord.Embed(title="[+] Key Created", color=Palette.NEON_GREEN, timestamp=datetime.utcnow())
        e.add_field(name="Key", value=f"`{key}`", inline=False)
        e.add_field(name="User", value=f"<@{uid}>", inline=True)
        e.add_field(name="Name", value=name, inline=True)
        e.add_field(name="Duration", value=f"**{days}d**", inline=True)
        e.add_field(name="Expires", value=f"<t:{int(time.time()+days*86400)}:R>", inline=True)
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def license_deleted(key: str) -> discord.Embed:
        e = discord.Embed(
            title="[-] Key Deleted",
            description=f"`{key}` has been **permanently removed**.",
            color=Palette.NEON_RED,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def days_added(key: str, days: int, new_exp: float) -> discord.Embed:
        e = discord.Embed(title="[+] Days Added", color=Palette.NEON_GREEN, timestamp=datetime.utcnow())
        e.add_field(name="Key", value=f"`{key}`", inline=False)
        e.add_field(name="Added", value=f"**+{days}d**", inline=True)
        e.add_field(name="New Expiry", value=f"<t:{int(new_exp)}:R>", inline=True)
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def license_frozen(key: str) -> discord.Embed:
        e = discord.Embed(
            title="[!] License Frozen",
            description=f"`{key}` has been **frozen**. Timer paused.",
            color=Palette.NEON_BLUE,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def license_unfrozen(key: str) -> discord.Embed:
        e = discord.Embed(
            title="[?] License Unfrozen",
            description=f"`{key}` has been **unfrozen**. Timer resumed.",
            color=Palette.NEON_ORANGE,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def global_freeze(state: bool) -> discord.Embed:
        if state:
            e = discord.Embed(
                title="[!!!] Global Freeze",
                description="All licenses **frozen**. Users see: `Testing. Wait please`",
                color=Palette.NEON_RED,
                timestamp=datetime.utcnow()
            )
        else:
            e = discord.Embed(
                title="[?] Global Unfreeze",
                description="All licenses **active**. Normal operation restored.",
                color=Palette.NEON_GREEN,
                timestamp=datetime.utcnow()
            )
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def license_info(lic: Dict) -> discord.Embed:
        dl = max(0, int((lic['expires_at'] - time.time()) / 86400))
        if lic['is_frozen']:
            st = "**FROZEN**"
            sc = Palette.NEON_BLUE
        elif dl > 0:
            st = "**ACTIVE**"
            sc = Palette.NEON_GREEN
        else:
            st = "**EXPIRED**"
            sc = Palette.NEON_RED
        e = discord.Embed(title=f"[ {lic['discord_name']} ]", color=sc, timestamp=datetime.utcnow())
        e.add_field(name="Key", value=f"`{lic['license_key']}`", inline=False)
        e.add_field(name="User", value=f"<@{lic['user_id']}>", inline=True)
        e.add_field(name="Status", value=st, inline=True)
        e.add_field(name="Days Left", value=f"**{dl}**", inline=True)
        e.add_field(name="Total Days", value=str(lic['days_total']), inline=True)
        if lic['hwid_hash']:
            e.add_field(name="HWID", value=f"`{str(lic['hwid_hash'])[:24]}...`", inline=True)
        e.add_field(name="Created", value=f"<t:{int(lic['created_at'])}:D>", inline=True)
        e.add_field(name="Expires", value=f"<t:{int(lic['expires_at'])}:R>", inline=True)
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def system_stats(bot_ref, lics: List[Dict]) -> discord.Embed:
        act = [l for l in lics if not l['is_frozen'] and l['expires_at'] > time.time()]
        frz = [l for l in lics if l['is_frozen']]
        exp = [l for l in lics if not l['is_frozen'] and l['expires_at'] <= time.time()]
        up = int(time.time() - bot_ref.start_time)
        e = discord.Embed(title="[#] System Statistics", color=Palette.NEON_PINK, timestamp=datetime.utcnow())
        e.add_field(name="Uptime", value=f"{up//86400}d {(up%86400)//3600}h", inline=True)
        e.add_field(name="Total", value=str(len(lics)), inline=True)
        e.add_field(name="Active", value=str(len(act)), inline=True)
        e.add_field(name="Frozen", value=str(len(frz)), inline=True)
        e.add_field(name="Expired", value=str(len(exp)), inline=True)
        e.add_field(name="DB Files", value=str(bot_ref.db_mgr.stats()['files']), inline=True)
        e.add_field(name="DB Records", value=str(bot_ref.db_mgr.stats()['records']), inline=True)
        e.add_field(name="API Port", value=str(CFG.API_PORT), inline=True)
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def error(title: str, desc: str) -> discord.Embed:
        e = discord.Embed(title=f"[X] {title}", description=desc, color=Palette.NEON_RED, timestamp=datetime.utcnow())
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def history_header(total: int) -> discord.Embed:
        e = discord.Embed(
            title="[*] License History",
            description=f"**Total licenses:** {total}\nSelect a license from dropdown.",
            color=Palette.NEON_PINK,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def audit_header(count: int) -> discord.Embed:
        e = discord.Embed(
            title="[@] Audit Log",
            description=f"**Entries:** {count}",
            color=Palette.NEON_BLUE,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text="TriumphMania X.2")
        return e

    @staticmethod
    def reload_success(files: int, lic: int) -> discord.Embed:
        e = discord.Embed(
            title="[@] DB Reloaded",
            description=f"Files: **{files}**\nLicenses: **{lic}**",
            color=Palette.NEON_GREEN,
            timestamp=datetime.utcnow()
        )
        e.set_footer(text="TriumphMania X.2")
        return e

# ============================================================
# UI COMPONENTS
# ============================================================
class TriumphButton(discord.ui.Button):
    def __init__(self, label, style=discord.ButtonStyle.secondary, row=0, custom_id=None, emoji=None):
        super().__init__(label=label, style=style, custom_id=custom_id or f"btn_{secrets.token_hex(4)}", row=row, emoji=emoji)

class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        self.add_item(TriumphButton("[+] Create Key", discord.ButtonStyle.green, 0, "menu_create", "🔑"))
        self.add_item(TriumphButton("[-] Delete Key", discord.ButtonStyle.red, 0, "menu_delete", "🗑️"))
        self.add_item(TriumphButton("[*] History", discord.ButtonStyle.blurple, 1, "menu_history", "📋"))
        self.add_item(TriumphButton("[!] Freeze All", discord.ButtonStyle.red, 1, "menu_freeze", "❄️"))
        self.add_item(TriumphButton("[?] Unfreeze All", discord.ButtonStyle.green, 1, "menu_unfreeze", "🔥"))
        self.add_item(TriumphButton("[#] Statistics", discord.ButtonStyle.blurple, 2, "menu_stats", "📊"))
        self.add_item(TriumphButton("[@] Reload DB", discord.ButtonStyle.grey, 2, "menu_reload", "🔄"))

    async def interaction_check(self, interaction):
        if interaction.channel_id != CFG.MGMT_CHANNEL_ID:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Access Denied", "Wrong channel."), ephemeral=True
            )
            return False
        if interaction.user.id not in CFG.AUTH_USERS:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Access Denied", "Unauthorized."), ephemeral=True
            )
            webhook.log("ACCESS_DENIED", f"User {interaction.user} attempted menu", Palette.NEON_RED)
            return False
        return True

class CreateKeyModal(discord.ui.Modal):
    def __init__(self, storage: DiscordFileStorage):
        super().__init__(title="[+] Create New License Key", timeout=300)
        self.storage = storage
        self.days_inp = discord.ui.TextInput(
            label="Days (1-365)",
            placeholder="Enter number of days",
            min_length=1, max_length=3, required=True
        )
        self.add_item(self.days_inp)
        self.uid_inp = discord.ui.TextInput(
            label="Discord User ID",
            placeholder="Enter Discord ID",
            min_length=17, max_length=20, required=True
        )
        self.add_item(self.uid_inp)

    async def on_submit(self, interaction):
        try:
            days = int(self.days_inp.value.strip())
            uid = int(self.uid_inp.value.strip())
        except ValueError:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Invalid Input", "Enter valid numbers."), ephemeral=True
                )
            return
        if days < 1 or days > 365:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Invalid Days", "Must be 1-365."), ephemeral=True
                )
            return
        member = interaction.guild.get_member(uid) if interaction.guild else None
        name = member.display_name if member else f"User_{uid}"
        key = await self.storage.create_license(uid, days, name)
        embed = EmbedBuilder.license_created(key, uid, name, days)
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.followup.send(embed=embed)
        webhook.log("KEY_CREATED", f"Key={key} User={uid} Days={days}", Palette.NEON_GREEN)

class DeleteKeyModal(discord.ui.Modal):
    def __init__(self, storage: DiscordFileStorage):
        super().__init__(title="[-] Delete License Key", timeout=300)
        self.storage = storage
        self.key_inp = discord.ui.TextInput(
            label="License Key",
            placeholder="XXXX-XXXX-XXXX-XXXX",
            min_length=19, max_length=19, required=True
        )
        self.add_item(self.key_inp)

    async def on_submit(self, interaction):
        key = self.key_inp.value.strip().upper()
        if not re.match(CFG.KEY_PATTERN, key):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Invalid Format", "Use XXXX-XXXX-XXXX-XXXX"), ephemeral=True
                )
            return
        if await self.storage.delete_license(key):
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=EmbedBuilder.license_deleted(key))
            else:
                await interaction.followup.send(embed=EmbedBuilder.license_deleted(key))
            webhook.log("KEY_DELETED", f"Key={key}", Palette.NEON_RED)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Not Found", "Key not in system."), ephemeral=True
                )

class AddDaysModal(discord.ui.Modal):
    def __init__(self, storage: DiscordFileStorage, key: str):
        super().__init__(title=f"[+] Add Days - {key}", timeout=300)
        self.storage = storage
        self.key = key
        self.days_inp = discord.ui.TextInput(
            label="Days to add (1-365)",
            placeholder="Enter days",
            min_length=1, max_length=3, required=True
        )
        self.add_item(self.days_inp)

    async def on_submit(self, interaction):
        try:
            days = int(self.days_inp.value.strip())
        except ValueError:
            if not interaction.response.is_done():
                await interaction.response.send_message("Invalid number.", ephemeral=True)
            return
        await self.storage.add_days(self.key, days)
        lic = await self.storage.get_license(self.key)
        embed = EmbedBuilder.days_added(self.key, days, lic['expires_at'])
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.followup.send(embed=embed)
        webhook.log("DAYS_ADDED", f"Key={self.key} Days=+{days}", Palette.NEON_GREEN)

class LicenseSelect(discord.ui.Select):
    def __init__(self, storage: DiscordFileStorage, lics: List[Dict], page: int = 0):
        self.storage = storage
        self.all_lic = lics
        self.page = page
        per_page = 25
        items = lics[page*per_page:(page+1)*per_page]
        opts = []
        for lic in items:
            dl = max(0, int((lic['expires_at']-time.time())/86400))
            s = "FROZEN" if lic['is_frozen'] else ("ACTIVE" if dl>0 else "EXPIRED")
            opts.append(discord.SelectOption(
                label=lic['discord_name'][:80],
                value=lic['license_key'],
                description=f"ID:{lic['user_id']} | {dl}d | {s}"
            ))
        super().__init__(
            placeholder=f"Select license (Page {page+1})...",
            options=opts,
            custom_id=f"sel_{page}"
        )

    async def callback(self, interaction):
        key = self.values[0]
        lic = await self.storage.get_license(key)
        if not lic:
            if not interaction.response.is_done():
                await interaction.response.send_message("Not found.", ephemeral=True)
            return
        embed = EmbedBuilder.license_info(lic)
        view = LicenseActionView(self.storage, key)
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)

class LicenseActionView(discord.ui.View):
    def __init__(self, storage: DiscordFileStorage, key: str):
        super().__init__(timeout=300)
        self.storage = storage
        self.key = key
        self.add_item(TriumphButton("[+] Add Days", discord.ButtonStyle.green, 0, f"act_add_{key[:8]}", "➕"))
        self.add_item(TriumphButton("[-] Delete", discord.ButtonStyle.red, 0, f"act_del_{key[:8]}", "🗑️"))
        lic = storage._cache.get(key, {})
        if lic.get('is_frozen'):
            self.add_item(TriumphButton("[?] Unfreeze", discord.ButtonStyle.green, 1, f"act_unf_{key[:8]}", "🔥"))
        else:
            self.add_item(TriumphButton("[!] Freeze", discord.ButtonStyle.grey, 1, f"act_frz_{key[:8]}", "❄️"))

class HistoryPagination(discord.ui.View):
    def __init__(self, storage: DiscordFileStorage, lics: List[Dict], page: int = 0):
        super().__init__(timeout=600)
        self.storage = storage
        per_page = 25
        self.page = page
        self.total = max(1, (len(lics) + per_page - 1) // per_page)
        self.add_item(LicenseSelect(storage, lics, page))
        if self.total > 1:
            prev = TriumphButton("Previous", discord.ButtonStyle.grey, 1, "hist_prev", "◀️")
            prev.disabled = (page == 0)
            nxt = TriumphButton("Next", discord.ButtonStyle.grey, 1, "hist_next", "▶️")
            nxt.disabled = (page >= self.total - 1)
            ind = TriumphButton(f"Page {page+1}/{self.total}", discord.ButtonStyle.blurple, 1, "hist_ind")
            ind.disabled = True
            self.add_item(prev)
            self.add_item(ind)
            self.add_item(nxt)

# ============================================================
# HTTP API SERVER
# ============================================================
from aiohttp import web

class APIServer:
    def __init__(self, storage: DiscordFileStorage, db_mgr: SearchDBManager, port: int):
        self.storage = storage
        self.db_mgr = db_mgr
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.req_count = 0
        self._routes()

    def _routes(self):
        self.app.router.add_post('/api/v8/validate', self.handle_validate)
        self.app.router.add_post('/api/v8/search', self.handle_search)
        self.app.router.add_get('/api/v8/ping', self.handle_ping)
        self.app.router.add_post('/api/v8/freeze', self.handle_freeze)
        self.app.router.add_post('/api/v8/unfreeze', self.handle_unfreeze)

    async def handle_validate(self, req):
        self.req_count += 1
        try:
            d = await req.json()
            key = d.get('key', '').strip().upper()
            hwid = d.get('hwid', '')
            if not key or not hwid:
                return web.json_response({'valid': False, 'message': 'InvalidKey'}, status=400)
            v, m, lic = await self.storage.validate(key, hwid)
            r = {'valid': v, 'message': m, 'timestamp': time.time(), 'server': 'X.2'}
            if v and lic:
                # ВАЖНО: включаем hwid_hash в ответ API
                r['license'] = {
                    'user_id': lic['user_id'],
                    'discord_name': lic['discord_name'],
                    'expires_at': lic['expires_at'],
                    'days_left': max(0, int((lic['expires_at']-time.time())/86400)),
                    'is_frozen': bool(lic['is_frozen']),
                    'requests_today': await self.storage.get_requests(key),
                    'max_requests': CFG.MAX_DAILY_REQ,
                    'hwid_hash': lic.get('hwid_hash')  # <-- HWID в ответе
                }
            return web.json_response(r)
        except Exception as e:
            return web.json_response({'valid': False, 'message': str(e)}, status=500)

    async def handle_search(self, req):
        self.req_count += 1
        try:
            d = await req.json()
            key = d.get('key', '').strip().upper()
            hwid = d.get('hwid', '')
            q = d.get('query', '').strip()
            if not q:
                return web.json_response({'error': 'Empty query', 'results': []}, status=400)
            v, m, _ = await self.storage.validate(key, hwid)
            if not v:
                return web.json_response({'error': m, 'results': []}, status=403)
            can, cnt = await self.storage.check_and_increment(key)
            if not can:
                return web.json_response({
                    'error': 'DAILY_LIMIT', 'results': [],
                    'requests': cnt, 'max': CFG.MAX_DAILY_REQ
                }, status=429)
            res = self.db_mgr.search(q)
            return web.json_response({
                'results': res, 'count': len(res),
                'requests_today': cnt, 'max_requests': CFG.MAX_DAILY_REQ
            })
        except Exception as e:
            return web.json_response({'error': str(e), 'results': []}, status=500)

    async def handle_ping(self, req):
        f = await self.storage.is_global_frozen()
        return web.json_response({'status': 'ok', 'version': 'X.2', 'timestamp': time.time(), 'frozen': f})

    async def handle_freeze(self, req):
        try:
            d = await req.json()
            key = d.get('key', '').strip().upper()
            hwid = d.get('hwid', '')
            v, m, _ = await self.storage.validate(key, hwid)
            if not v:
                return web.json_response({'success': False, 'message': m}, status=403)
            ok, msg = await self.storage.freeze(key)
            return web.json_response({'success': ok, 'message': msg})
        except:
            return web.json_response({'success': False, 'message': 'Internal error'}, status=500)

    async def handle_unfreeze(self, req):
        try:
            d = await req.json()
            key = d.get('key', '').strip().upper()
            hwid = d.get('hwid', '')
            v, m, _ = await self.storage.validate(key, hwid)
            if not v:
                return web.json_response({'success': False, 'message': m}, status=403)
            ok, msg = await self.storage.unfreeze(key)
            return web.json_response({'success': ok, 'message': msg})
        except:
            return web.json_response({'success': False, 'message': 'Internal error'}, status=500)

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"API server on port {self.port}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()

# ============================================================
# BOT
# ============================================================
class TriumphBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None,
            activity=discord.Activity(type=discord.ActivityType.watching, name="TriumphMania X.2"),
            status=discord.Status.online
        )
        self.storage = DiscordFileStorage(self)
        self.db_mgr = SearchDBManager(self)
        self.api = APIServer(self.storage, self.db_mgr, CFG.API_PORT)
        self.start_time = time.time()

    async def setup_hook(self):
        await webhook.init()
        await self.storage.load_cache()
        await self.db_mgr.load_all()
        await self.api.start()
        self.cleanup_loop.start()
        self.reload_loop.start()

    async def on_ready(self):
        logger.info(f"Bot online: {self.user}")
        g = self.get_guild(CFG.GUILD_ID)
        webhook.log("BOT_ONLINE", f"Bot {self.user} on {g.name if g else 'Unknown'}", Palette.NEON_PINK)

    @tasks.loop(seconds=CFG.CLEANUP_INTERVAL)
    async def cleanup_loop(self):
        await self.storage.cleanup()

    @tasks.loop(seconds=CFG.DB_RELOAD_INTERVAL)
    async def reload_loop(self):
        await self.storage.load_cache()
        await self.db_mgr.load_all()

    @cleanup_loop.before_loop
    @reload_loop.before_loop
    async def before_loops(self):
        await self.wait_until_ready()

    async def close(self):
        webhook.log("BOT_SHUTDOWN", "Bot stopping...", Palette.NEON_RED)
        self.cleanup_loop.cancel()
        self.reload_loop.cancel()
        await self.api.stop()
        await webhook.shutdown()
        await super().close()

bot = TriumphBot()

# ============================================================
# PERMISSION CHECK
# ============================================================
def check_mgmt(ctx):
    return ctx.channel.id == CFG.MGMT_CHANNEL_ID and ctx.author.id in CFG.AUTH_USERS

# ============================================================
# COMMANDS
# ============================================================
@bot.command(name='key')
async def key_cmd(ctx):
    if not check_mgmt(ctx):
        await ctx.reply(embed=EmbedBuilder.error("Access Denied", "Insufficient permissions."), delete_after=10)
        return
    await ctx.reply(embed=EmbedBuilder.main_menu(), view=MainMenuView())
    webhook.log("MENU_OPENED", f"User {ctx.author}", Palette.NEON_PINK)

@bot.command(name='stats')
async def stats_cmd(ctx):
    if not check_mgmt(ctx):
        return
    lics = await bot.storage.get_all()
    await ctx.reply(embed=EmbedBuilder.system_stats(bot, lics))

@bot.command(name='reload')
async def reload_cmd(ctx):
    if not check_mgmt(ctx):
        return
    await bot.storage.load_cache()
    n = await bot.db_mgr.load_all()
    await ctx.reply(embed=EmbedBuilder.reload_success(n, len(bot.storage._cache)))

@bot.command(name='lookup')
async def lookup_cmd(ctx, *, identifier: str):
    if not check_mgmt(ctx):
        return
    identifier = identifier.strip()
    if re.match(CFG.KEY_PATTERN, identifier.upper()):
        lic = await bot.storage.get_license(identifier.upper())
        if lic:
            await ctx.reply(embed=EmbedBuilder.license_info(lic), view=LicenseActionView(bot.storage, identifier.upper()))
        else:
            await ctx.reply(embed=EmbedBuilder.error("Not Found", "Key not found."))
        return
    try:
        uid = int(identifier)
        lics = await bot.storage.get_user_licenses(uid)
        if lics:
            e = discord.Embed(
                title=f"Licenses for User {uid}",
                description=f"Found **{len(lics)}**",
                color=Palette.NEON_PINK,
                timestamp=datetime.utcnow()
            )
            for lic in lics[:10]:
                dl = max(0, int((lic['expires_at']-time.time())/86400))
                e.add_field(
                    name=f"Key: {lic['license_key'][:12]}...",
                    value=f"Status: **{'FROZEN' if lic['is_frozen'] else 'ACTIVE'}**\nDays: **{dl}**",
                    inline=True
                )
            await ctx.reply(embed=e)
        else:
            await ctx.reply(embed=EmbedBuilder.error("Not Found", "No licenses."))
    except ValueError:
        await ctx.reply(embed=EmbedBuilder.error("Invalid", "Provide key or user ID."))

@bot.command(name='audit')
async def audit_cmd(ctx, limit: int = 20):
    if not check_mgmt(ctx):
        return
    lines = await bot.storage.get_audit(limit)
    if not lines:
        await ctx.reply(embed=EmbedBuilder.error("Empty", "No audit entries."))
        return
    e = EmbedBuilder.audit_header(len(lines))
    for line in lines[-15:]:
        parts = line.split('|')
        if len(parts) >= 4:
            ts = datetime.fromtimestamp(float(parts[0])).strftime('%Y-%m-%d %H:%M:%S')
            e.add_field(name=f"{ts} - {parts[1]}", value=f"User: {parts[2]}\n{parts[3][:150]}", inline=False)
    await ctx.reply(embed=e)

# ============================================================
# INTERACTION HANDLER
# ============================================================
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    if interaction.user == bot.user:
        return

    cid = interaction.data.get('custom_id', '')

    if interaction.channel_id != CFG.MGMT_CHANNEL_ID:
        if not interaction.response.is_done():
            await interaction.response.send_message("Wrong channel.", ephemeral=True)
        return
    if interaction.user.id not in CFG.AUTH_USERS:
        if not interaction.response.is_done():
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
        webhook.log("ACCESS_DENIED", f"User {interaction.user} tried: {cid}", Palette.NEON_RED)
        return

    try:
        if cid == 'menu_create':
            if not interaction.response.is_done():
                await interaction.response.send_modal(CreateKeyModal(bot.storage))

        elif cid == 'menu_delete':
            if not interaction.response.is_done():
                await interaction.response.send_modal(DeleteKeyModal(bot.storage))

        elif cid == 'menu_history':
            lics = await bot.storage.get_all()
            if not lics:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=EmbedBuilder.error("Empty", "No licenses."), ephemeral=True
                    )
                return
            v = HistoryPagination(bot.storage, lics)
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=EmbedBuilder.history_header(len(lics)), view=v)

        elif cid == 'menu_freeze':
            await bot.storage.set_global_freeze(True, str(interaction.user))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=EmbedBuilder.global_freeze(True))
            webhook.log("GLOBAL_FREEZE", f"By {interaction.user}", Palette.NEON_RED)

        elif cid == 'menu_unfreeze':
            await bot.storage.set_global_freeze(False, str(interaction.user))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=EmbedBuilder.global_freeze(False))
            webhook.log("GLOBAL_UNFREEZE", f"By {interaction.user}", Palette.NEON_GREEN)

        elif cid == 'menu_stats':
            lics = await bot.storage.get_all()
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=EmbedBuilder.system_stats(bot, lics))

        elif cid == 'menu_reload':
            await bot.storage.load_cache()
            n = await bot.db_mgr.load_all()
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=EmbedBuilder.reload_success(n, len(bot.storage._cache)))

        elif cid.startswith('act_add_'):
            kp = cid.replace('act_add_', '')
            f = next((k for k in bot.storage._cache if k.startswith(kp)), None)
            if f:
                if not interaction.response.is_done():
                    await interaction.response.send_modal(AddDaysModal(bot.storage, f))
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Not found.", ephemeral=True)

        elif cid.startswith('act_del_'):
            kp = cid.replace('act_del_', '')
            f = next((k for k in bot.storage._cache if k.startswith(kp)), None)
            if f:
                await bot.storage.delete_license(f)
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=EmbedBuilder.license_deleted(f))
                webhook.log("KEY_DELETED", f"Key={f}", Palette.NEON_RED)
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Not found.", ephemeral=True)

        elif cid.startswith('act_frz_'):
            kp = cid.replace('act_frz_', '')
            f = next((k for k in bot.storage._cache if k.startswith(kp)), None)
            if f:
                ok, msg = await bot.storage.freeze(f)
                if ok:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(embed=EmbedBuilder.license_frozen(f))
                    webhook.log("LICENSE_FROZEN", f"Key={f}", Palette.NEON_BLUE)
                else:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"Error: {msg}", ephemeral=True)
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Not found.", ephemeral=True)

        elif cid.startswith('act_unf_'):
            kp = cid.replace('act_unf_', '')
            f = next((k for k in bot.storage._cache if k.startswith(kp)), None)
            if f:
                ok, msg = await bot.storage.unfreeze(f)
                if ok:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(embed=EmbedBuilder.license_unfrozen(f))
                    webhook.log("LICENSE_UNFROZEN", f"Key={f}", Palette.NEON_ORANGE)
                else:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"Error: {msg}", ephemeral=True)
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Not found.", ephemeral=True)

        elif cid in ('hist_prev', 'hist_next'):
            lics = await bot.storage.get_all()
            v = HistoryPagination(bot.storage, lics, 0)
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=EmbedBuilder.history_header(len(lics)), view=v)

    except Exception as e:
        logger.error(f"Interaction error: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"Error: {e}", ephemeral=True)
        except:
            pass

# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    if not check_and_free_port(CFG.API_PORT):
        logger.error(f"Failed to free port {CFG.API_PORT}.")
        sys.exit(1)
    try:
        bot.run(CFG.BOT_TOKEN)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Fatal: {e}")
        traceback.print_exc()
    finally:
        try:
            asyncio.run(bot.close())
        except:
            pass