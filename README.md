
# 🤖 MySQL Auto Backup Discord Bot

Bot Discord otomatis untuk melakukan **backup database MySQL** harian dan manual melalui perintah di server Discord. Cocok untuk admin yang ingin pengingat dan pengiriman file SQL langsung via DM atau channel.

---

## 🚀 Fitur Utama

- backup otomatis semua database tiap jam 12 malam
- backup semua database manual
- backup 1 database bisa di kirim ke channel file backupnya atau bisa di kirim ke user lewat chat pribadi pake tag
- backup otomatis 1 database bisa atur database yg mana kirim ke user siapa pake tag, sama bisa atur auto backup tiap jam berapa aja
- list auto backup yg lagi aktif
- hapus auto backup dari list
- bisa kecualiin database mana aja yg jngn di backup

---

## 📦 Instalasi

### 1. Clone Repository

```bash
git clone https://github.com/username/auto-backup-db-discord.git
cd auto-backup-db-discord
```

### 2. Install Dependensi

Pastikan kamu sudah punya Python 3.8+ dan pip:

```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment

Edit file `.env` di root folder:

```env
DISCORD_TOKEN=token_bot_discord_kamu
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_HOST=localhost
NOTIFY_CHANNEL_ID=ID CHANEL NOTIF EMBED
BACKUP_CHANNEL_ID=ID CHANNEL KIRIM FILE DB
OWNER_ID=ID OWNER
EXCLUDED_DATABASES=mysql,information_schema,performance_schema (berisi database apa saja yang ingin di kecualikan agar tidak di backup)
```

> Ganti semua nilai dengan milikmu.

---

## 🧪 Menjalankan Bot

```bash
python3 auto.py
```

---

## 🛠️ Perintah Bot

| Perintah               | Fungsi                                              |
|------------------------|-----------------------------------------------------|
| `!backupnow`           | Backup semua database (manual)                     |
| `!backup nama_db @user`      | Backup satu database ke channel atau user          |
| `!setautobackup db @user [jam]` | Set backup otomatis harian ke user |
| `!unsetautobackup db @user`    | Hapus jadwal backup                          |
| `!listautobackup`      | Daftar semua jadwal aktif                          |
| `!ping`                | Tes status bot                                     |
| `!credit`              | Menampilkan pembuat bot                            |

---

## 👤 Credit

Bot ini dibuat oleh [Aruli Azmi](https://github.com/aruliazmi).  
Wong Pintar Ora Hapus Credit.

---

## 📃 Lisensi

MIT LICENSE.
