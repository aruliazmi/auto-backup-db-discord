import os
import json
import requests
import subprocess
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MYSQL_BIN = "/usr/bin/mysql"
DUMP_BIN = "/usr/bin/mysqldump"

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
            print("❌ File konfigurasi JSON rusak. Mengabaikan dan melanjutkan dengan konfigurasi kosong.")
            return {}
    return {}

def save_backup_config(config):
    with open(BACKUP_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def restore_jobs():
    config = load_backup_config()
    for job_id, job in config.items():
        db = job['db']
        uid = job['user_id']
        hour = job['hour']
        scheduler.add_job(send_backup_to_user, "cron", hour=hour, minute=10, args=[db, uid], id=job_id)
        scheduled_jobs[job_id] = True

# ====== Backup Database Tertentu ke User Tertentu ======
async def send_backup_to_user(db_name, user_id):
    try:
        user = await bot.fetch_user(user_id)
        filename = f"{db_name}_{datetime.now().strftime('%d %m %Y')}.sql"
        dump_cmd = [
            DUMP_BIN,
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

# ====== Backup Manual All Database ======
async def backup_all_databases():
    if not notify_channel or not file_channel:
        print("❌ Channel belum diatur.")
        return

    success = []
    failed = []

    try:
        show_db_cmd = [
            MYSQL_BIN,
            f"-h{MYSQL_HOST}",
            f"-u{MYSQL_USER}",
            f"-p{MYSQL_PASSWORD}",
            "-e", "SHOW DATABASES;"
        ]
        result = subprocess.run(show_db_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            embed = discord.Embed(
                title="❌ Backup Gagal",
                description=f"```{result.stderr}```",
                color=discord.Color.red()
            )
            await notify_channel.send(embed=embed)
            return

        databases = result.stdout.splitlines()[1:]

        for db in databases:
            if db in EXCLUDED_DATABASES:
                continue

            filename = f"{db}_{datetime.now().strftime('%d %m %Y')}.sql"
            dump_cmd = [
                DUMP_BIN,
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

        status = "✅ Backup Semua Database Selesai"
        color = discord.Color.green()
        if failed:
            status = "⚠️ Backup Sebagian Gagal"
            color = discord.Color.orange()

        embed = discord.Embed(title=status, color=color)
        embed.add_field(name="📂 Sukses", value="\n".join(success) or "-", inline=False)

        if failed:
            failed_text = "\n".join(f"❌ `{name}`: {err[:100]}..." for name, err in failed)
            embed.add_field(name="❌ Gagal", value=failed_text, inline=False)

        embed.set_footer(text=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await notify_channel.send(embed=embed)

    except Exception as e:
        embed = discord.Embed(
            title="❌ Error Backup",
            description=f"```{str(e)}```",
            color=discord.Color.red()
        )
        await notify_channel.send(embed=embed)

# ====== Command Manual untuk Owner: backup all ======
@bot.command(name="backupnow")
@is_owner()
async def backup_now(ctx):
    await ctx.send("🔁 Memulai backup manual...")
    await backup_all_databases()

# ====== Command Manual untuk Owner: backup 1 db + tag user opsional ======
@bot.command(name="backup")
@is_owner()
async def backup_command(ctx, *, args: str = None):
    if not args:
        await ctx.send("⚠️ Kamu harus menyebutkan nama database.\nContoh: `!backup nama_database` atau `!backup nama_database @user`")
        return

    parts = args.split()
    db_name = parts[0]
    mentioned_users = ctx.message.mentions

    if db_name in EXCLUDED_DATABASES:
        await ctx.send(f"⚠️ Database `{db_name}` termasuk dalam daftar EXCLUDED.")
        return

    await ctx.send(f"🔁 Memulai backup untuk database `{db_name}`...")

    filename = f"{db_name}_{datetime.now().strftime('%d %m %Y')}.sql"
    dump_cmd = [
        DUMP_BIN,
        f"-h{MYSQL_HOST}",
        f"-u{MYSQL_USER}",
        f"-p{MYSQL_PASSWORD}",
        db_name
    ]

    with open(filename, "w") as f:
        dump = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True)

    if dump.returncode == 0:
        target = mentioned_users[0] if mentioned_users else file_channel

        if isinstance(target, discord.User) or isinstance(target, discord.Member):
            try:
                await target.send(file=discord.File(filename))
                embed_dm = discord.Embed(
                    title="📦 Backup Diterima",
                    description=f"Berikut adalah backup untuk database `{db_name}`.",
                    color=discord.Color.blue()
                )
                embed_dm.set_footer(text=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                await target.send(embed=embed_dm)
                await ctx.send(f"✅ Backup dikirim ke DM {target.mention}")
            except discord.Forbidden:
                await ctx.send(f"❌ Gagal mengirim DM ke {target.mention}. DM mungkin dinonaktifkan.")
        else:
            await file_channel.send(file=discord.File(filename))
            await ctx.send("✅ Berikut File Backupnya.")

        embed = discord.Embed(
            title="✅ Backup Database Sukses",
            description=f"Database `{db_name}` berhasil di-backup.",
            color=discord.Color.green()
        )
        await notify_channel.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Backup Gagal",
            description=f"Database: `{db_name}`\nError: ```{dump.stderr.strip()[:100]}...```",
            color=discord.Color.red()
        )
        await notify_channel.send(embed=embed)

    if os.path.exists(filename):
        os.remove(filename)

# ====== Command Ping ======
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latency: `{round(bot.latency * 1000)}ms`")
    
# ====== Command Set Jadwal Backup Otomatis ======
@bot.command(name="setautobackup")
@is_owner()
async def set_auto_backup(ctx, *, args: str = None):
    if not args:
        await ctx.send("⚠️ Penggunaan: `!setautobackup nama_database [jam_backup] @user`")
        return

    parts = args.split()
    mentioned = ctx.message.mentions
    if not mentioned:
        await ctx.send("⚠️ Kamu harus tag user yang akan menerima backup.")
        return

    user = mentioned[0]
    db_name = None
    hour = 0  

    for part in parts:
        if part.isdigit():
            hour = int(part)
        elif not part.startswith("<@"):
            db_name = part

    if not db_name:
        await ctx.send("⚠️ Format salah. Contoh: `!setautobackup nama_database [jam] @user`")
        return

    job_id = f"auto_backup_{db_name}_{user.id}"

    if job_id in scheduled_jobs:
        scheduler.remove_job(job_id)

    scheduler.add_job(send_backup_to_user, "cron", hour=hour, minute=10, args=[db_name, user.id], id=job_id)
    scheduled_jobs[job_id] = True

    config = load_backup_config()
    config[job_id] = {"db": db_name, "user_id": user.id, "hour": hour}
    save_backup_config(config)

    await ctx.send(f"✅ Backup otomatis untuk database `{db_name}` ke {user.mention} diatur jam {hour:02d}:10 WIB.")

# ====== Command Unset Jadwal Backup Otomatis ======
@bot.command(name="unsetautobackup")
@is_owner()
async def unset_auto_backup(ctx, db_name: str = None):
    mentioned = ctx.message.mentions
    if not db_name or not mentioned:
        await ctx.send("⚠️ Penggunaan: `!unsetautobackup nama_database @user`")
        return

    user = mentioned[0]
    job_id = f"auto_backup_{db_name}_{user.id}"

    if job_id in scheduled_jobs:
        scheduler.remove_job(job_id)
        del scheduled_jobs[job_id]

        config = load_backup_config()
        if job_id in config:
            del config[job_id]
            save_backup_config(config)

        await ctx.send(f"🗑️ Jadwal backup database `{db_name}` ke {user.mention} telah dihapus.")
    else:
        await ctx.send("⚠️ Jadwal tidak ditemukan atau belum diset.")

# ====== Command List Semua Jadwal Aktif ======
@bot.command(name="listautobackup")
@is_owner()
async def list_auto_backup(ctx):
    config = load_backup_config()
    if not config:
        await ctx.send("📭 Tidak ada jadwal backup otomatis yang aktif.")
        return

    embed = discord.Embed(title="📋 Jadwal Backup Otomatis Aktif", color=discord.Color.blue())
    for job_id, job in config.items():
        db_name = job['db']
        user_id = job['user_id']
        hour = job['hour']
        try:
            user = await bot.fetch_user(user_id)
            embed.add_field(
                name=f"🛠️ {db_name}",
                value=f"📤 Ke: {user.mention}\n🕒 Waktu: {str(hour).zfill(2)}:10 WIB",
                inline=False
            )
        except:
            embed.add_field(
                name=f"🛠️ {db_name}",
                value=f"📤 Ke: (User tidak ditemukan)\n🕒 Waktu: {str(hour).zfill(2)}:10 WIB",
                inline=False
            )
    await ctx.send(embed=embed)

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