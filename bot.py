import os
import json
import requests
import subprocess
import discord
import shutil
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from dotenv import load_dotenv
import base64

load_dotenv()

if not shutil.which("mysqldump") or not shutil.which("mysql"):
    print("❌ 'mysqldump' atau 'mysql' tidak ditemukan di PATH. Pastikan mysql-client terpasang.")
    exit(1)

TOKEN = os.getenv("DISCORD_TOKEN")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")

NOTIFY_CHANNEL_ID = int(os.getenv("NOTIFY_CHANNEL_ID"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID"))
OWNER_ID = int(os.getenv("OWNER_ID", 0))

excluded = os.getenv("EXCLUDED_DATABASES", "")
EXCLUDED_DATABASES = [db.strip() for db in excluded.split(",") if db.strip()]

BACKUP_CONFIG_FILE = "autobackup_config.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

notify_channel = None
file_channel = None
scheduled_jobs = {}

def is_owner():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

def load_backup_config():
    if os.path.exists(BACKUP_CONFIG_FILE):
        try:
            with open(BACKUP_CONFIG_FILE, "r") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except json.JSONDecodeError:
            print("❌ File konfigurasi JSON rusak.")
            return {}
    return {}

def save_backup_config(config):
    with open(BACKUP_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

exec(base64.b64decode('''
ZGVmIHJlc3RvcmVfam9icygpOgogICAgZnJvbSBtYWluIGltcG9ydCBsb2FkX2JhY2t1cF9jb25maWcKCiAgICBjb25maWcgPSBsb2FkX2JhY2t1cF9jb25maWcoKQogICAgaWYgIl9jcmVhdG9yIiBub3QgaW4gY29uZmlnOgogICAgICAgIHByaW50KCLigqAgQ3JlZGl0IHBlbmdlbWJhbmcgaGlsYW5nLiIpCiAgICBmb3Igam9iX2lkLCBqb2IgaW4gY29uZmlnLml0ZW1zKCk6CiAgICAgICAgaWYgam9iX2lkID09ICJfY3JlYXRvciI6CiAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgZGIgPSBqb2JbJ2RiJ10KICAgICAgICB1aWQgPSBqb2JbJ3VzZXJfaWQnXQogICAgICAgIGhvdXIgPSBqb2JbJ2hvdXInXQogICAgICAgIHNjaGVkdWxlci5hZGRfam9iKHNlbmRfYmFja3VwX3RvX3VzZXIsICJjcm9uIiwgaG91cj1ob3VyLCBtaW51dGU9MTAsIGFyZ3M9W2RiLCB1aWRdLCBpZD1qb2JfaWQpCiAgICAgICAgc2NoZWR1bGVkX2pvYnNbbmFtZV0gPSBUcnVl
''').decode())

async def send_backup_to_user(db_name, user_id):
    try:
        user = await bot.fetch_user(user_id)
        filename = f"{db_name}_{datetime.now().strftime('%d %m %Y')}.sql"
        dump_cmd = [
            "mysqldump",
            f"-h{MYSQL_HOST}",
            f"-u{MYSQL_USER}",
            f"-p{MYSQL_PASSWORD}",
            db_name
        ]

        with open(filename, "w") as f:
            dump = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True)

        if dump.returncode == 0:
            await user.send(file=discord.File(filename))
            embed = discord.Embed(
                title="📦 Backup Database Otomatis",
                description=f"Backup Harian database `{db_name}` telah dikirim.",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await user.send(embed=embed)
        else:
            print(f"Gagal backup {db_name}: {dump.stderr}")

        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        print(f"Gagal kirim backup ke user {user_id}: {e}")

async def backup_all_databases():
    if not notify_channel or not file_channel:
        print("❌ Channel belum diatur.")
        return

    success, failed = [], []

    try:
        show_db_cmd = [
            "mysql",
            f"-h{MYSQL_HOST}",
            f"-u{MYSQL_USER}",
            f"-p{MYSQL_PASSWORD}",
            "-e", "SHOW DATABASES;"
        ]
        result = subprocess.run(show_db_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            await notify_channel.send(embed=discord.Embed(
                title="❌ Backup Gagal",
                description=f"```{result.stderr}```",
                color=discord.Color.red()
            ))
            return

        databases = result.stdout.splitlines()[1:]

        for db in databases:
            if db in EXCLUDED_DATABASES:
                continue

            filename = f"{db}_{datetime.now().strftime('%d %m %Y')}.sql"
            dump_cmd = [
                "mysqldump",
                f"-h{MYSQL_HOST}",
                f"-u{MYSQL_USER}",
                f"-p{MYSQL_PASSWORD}",
                db
            ]

            with open(filename, "w") as f:
                dump = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True)

            if dump.returncode == 0:
                await file_channel.send(file=discord.File(filename))
                success.append(db)
            else:
                failed.append((db, dump.stderr.strip()))

            if os.path.exists(filename):
                os.remove(filename)

        status = "✅ Backup Selesai" if not failed else "⚠️ Backup Sebagian Gagal"
        color = discord.Color.green() if not failed else discord.Color.orange()

        embed = discord.Embed(title=status, color=color)
        embed.add_field(name="📂 Sukses", value="\n".join(success) or "-", inline=False)
        if failed:
            embed.add_field(
                name="❌ Gagal",
                value="\n".join(f"❌ `{name}`: {err[:100]}..." for name, err in failed),
                inline=False
            )

        embed.set_footer(text=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await notify_channel.send(embed=embed)

    except Exception as e:
        await notify_channel.send(embed=discord.Embed(
            title="❌ Error Backup",
            description=f"```{str(e)}```",
            color=discord.Color.red()
        ))

@bot.command(name="backupnow")
@is_owner()
async def backup_now(ctx):
    await ctx.send("🔁 Memulai backup manual...")
    await backup_all_databases()

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latency: `{round(bot.latency * 1000)}ms`")

@bot.command(name="credit")
async def credit(ctx):
    await ctx.send(embed=discord.Embed(
        title="📜 Credit Bot",
        description="Bot ini dibuat dengan ❤️ oleh **Arull**",
        color=discord.Color.blue()
    ))

@bot.event
async def on_ready():
    global notify_channel, file_channel
    notify_channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    file_channel = bot.get_channel(BACKUP_CHANNEL_ID)

    if not notify_channel or not file_channel:
        print("❌ Gagal mendapatkan channel. Cek ID.")
    else:
        print(f"✅ Bot aktif sebagai {bot.user}")
        scheduler.start()

bot.run(TOKEN)
