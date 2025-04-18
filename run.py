import subprocess
import sys
from datetime import datetime

def log_message(level, message):
    """Logs a message with a specific format and color."""
    time_str = datetime.now().strftime("%H:%M:%S")
    level_colors = {
        "INFO": "\033[37m",  # White
        "WARN": "\033[33m",  # Yellow
        "ERROR": "\033[31m"  # Red
    }
    color = level_colors.get(level, "\033[37m")  # Default to white if level is unknown
    print(f"{color}[{time_str} {level}]: [System] {message}\033[0m")

def start_bots():
    try:
        log_message("INFO", "Запуск DiscordBot...")
        discord_process = subprocess.Popen([sys.executable, "src/bots/discordbot/run.py"])

        #log_message("INFO", "Запуск ArisPriceBot...")
        #price_process = subprocess.Popen([sys.executable, "src/bots/pricebot/run.py"])

        discord_process.wait()
        #support_process.wait()

    except FileNotFoundError:
        log_message("ERROR", "Не найден один из файлов. Убедитесь, что файлы находятся в правильных директориях.")
    except Exception as e:
        log_message("ERROR", f"Произошла ошибка: {e}")
    except KeyboardInterrupt:
        log_message("WARN", "Bots stopped by user")
    finally:
        log_message("INFO", "All bots have stopped working")

if __name__ == "__main__":
    start_bots()
