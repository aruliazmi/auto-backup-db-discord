import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === Path ke file bot utama ===
BOT_FILE = "bot.py"
PROCESS = None

class BotReloader(FileSystemEventHandler):
    def restart_bot(self):
        global PROCESS
        if PROCESS:
            PROCESS.terminate()
            PROCESS.wait()
        print("🔁 Restarting bot...")
        PROCESS = subprocess.Popen(["python3", BOT_FILE])

    def on_modified(self, event):
        if event.src_path.endswith(BOT_FILE):
            print(f"📄 Detected change in {BOT_FILE}")
            self.restart_bot()

if __name__ == "__main__":
    event_handler = BotReloader()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

    # Jalankan bot pertama kali
    event_handler.restart_bot()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if PROCESS:
            PROCESS.terminate()
    observer.join()
