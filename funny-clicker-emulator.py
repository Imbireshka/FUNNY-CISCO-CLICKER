#!/usr/bin/env python3
"""
Эмулятор реконнекта Cisco AnyConnect

Автоматизирует периодическое переподключение к Cisco AnyConnect через эмуляцию кликов мыши.
Предназначен для случаев, когда CLI-управление недоступно или ненадёжно.

⚠️ Использует pyautogui — убедитесь, что окно Cisco AnyConnect в фокусе и разрешение экрана стабильно.

Запускается через systemd или cron. Логирует всё в файл и может отправлять алерты в Telegram.
"""

import pyautogui
import time
import logging
import sys
import subprocess
import requests
from dotenv import load_dotenv
import os

# Загружаем переменные окружения
load_dotenv()

# === НАСТРОЙКИ (указываются в .env) ===
ICON_X = int(os.getenv("ICON_X", "32"))
ICON_Y = int(os.getenv("ICON_Y", "607"))
TAB_X = int(os.getenv("TAB_X", "122"))
TAB_Y = int(os.getenv("TAB_Y", "79"))
BUTTON_X = int(os.getenv("BUTTON_X", "309"))
BUTTON_Y = int(os.getenv("BUTTON_Y", "528"))

WAKEUP_DELAY = int(os.getenv("WAKEUP_DELAY", "5"))      # задержка после клика по иконке cisco
TAB_DELAY = int(os.getenv("TAB_DELAY", "2"))           # задержка после клика по вкладке VPN
CHECK_DELAY = int(os.getenv("CHECK_DELAY", "15"))      # задержка после клика по кнопке Connect

VPN_CLI_PATH = os.getenv("VPN_CLI_PATH", "/opt/cisco/anyconnect/bin/vpn")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/cisco-reconnector.log")

# Опционально: Telegram-алерты
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

def is_vpn_connected():
    """Проверка подключения к VPN через CLI."""
    try:
        result = subprocess.run(
            [VPN_CLI_PATH, "status"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return result.returncode == 0 and "state: Connected" in result.stdout
    except Exception as e:
        logging.error(f"Ошибка проверки статуса VPN: {e}")
        return False

def send_telegram_alert(message):
    """Отправляет алерт в Telegram (если настроено)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        logging.error(f"Ошибка отправки Telegram-алерта: {e}")

def perform_click_sequence(attempt_name):
    """Выполняет последовательность кликов: иконка → вкладка → кнопка."""
    pyautogui.moveTo(ICON_X, ICON_Y)
    pyautogui.click()
    logging.info(f"{attempt_name}: клик по иконке")
    time.sleep(WAKEUP_DELAY)

    pyautogui.moveTo(TAB_X, TAB_Y)
    pyautogui.click()
    logging.info(f"{attempt_name}: клик по вкладке")
    time.sleep(TAB_DELAY)

    pyautogui.moveTo(BUTTON_X, BUTTON_Y)
    pyautogui.click()
    logging.info(f"{attempt_name}: клик по кнопке")
    time.sleep(CHECK_DELAY)

# === ОСНОВНАЯ ЛОГИКА ===
if __name__ == "__main__":
    logging.info("=== Эмулятор реконнекта Cisco AnyConnect запущен ===")
    try:
        # Первая попытка: отключиться
        perform_click_sequence("Попытка 1")
        time.sleep(5)

        if is_vpn_connected():
            logging.warning("После первой попытки VPN еще подключен.")
            send_telegram_alert(
                "Алерт: не удалось отключить VPN с первой попытки. "
                "Проверьте фокус окна или координаты."
            )

            # Вторая попытка
            logging.info("Запуск второй попытки...")
            perform_click_sequence("Попытка 2")
            time.sleep(5)

            if is_vpn_connected():
                logging.error("Все попытки отключения не сработали.")
                send_telegram_alert(
                    "АЛЕРТ: эмулятор не смог отключить VPN после двух попыток. "
                    "Требуется вмешательство."
                )
                sys.exit(1)
            else:
                logging.info("VPN отключён. Ждём 20 сек перед переподключением...")
                time.sleep(20)
                perform_click_sequence("Переподключение")
                if is_vpn_connected():
                    logging.info("VPN успешно переподключён.")
                else:
                    logging.error("Переподключение не удалось.")
                    send_telegram_alert("VPN не восстановлен после переподключения.")
        else:
            logging.info("VPN отключён. Переподключение...")
            time.sleep(20)
            perform_click_sequence("Переподключение")
            if is_vpn_connected():
                logging.info("VPN успешно переподключен.")
            else:
                logging.error("Переподключение не удалось.")
                send_telegram_alert("VPN не восстановлен после переподключения.")

        logging.info("=== Работа эмулятора завершена ===")

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        send_telegram_alert(f"Эмулятор аварийно завершил работу: {e}")
        sys.exit(1)
