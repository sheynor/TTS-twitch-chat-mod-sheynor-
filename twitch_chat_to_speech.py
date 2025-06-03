import asyncio
import edge_tts
import io
import os
import pygame
import sounddevice as sd
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox
import threading
import pystray
from PIL import Image, ImageDraw

# Трей
def create_tray_icon(root):
    def on_exit(icon, item):
        icon.stop()
        root.quit()

    def on_restore(icon, item):
        root.after(0, lambda: root.deiconify())

    image = Image.new('RGB', (64, 64), color=(145, 70, 255))  # Twitch фиолетовый
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), fill=(255, 255, 255))

    menu = pystray.Menu(
        pystray.MenuItem("Открыть", on_restore),
        pystray.MenuItem("Выход", on_exit)
    )

    icon = pystray.Icon("Twitch TTS", image, "Twitch TTS", menu)
    threading.Thread(target=icon.run, daemon=True).start()


# Настройки подключения
SERVER = 'irc.chat.twitch.tv'
PORT = 6667
message_queue = asyncio.Queue()

# Глобальные переменные
selected_device_name = None
selected_voice = "ru-RU-SvetlanaNeural"

# Получение списка аудиоустройств
def get_audio_output_devices():
    try:
        seen = set()
        devices = []
        for device in sd.query_devices():
            name = device['name']
            if device['max_output_channels'] > 0 and name not in seen:
                seen.add(name)
                devices.append(name)
        return devices

    except Exception as e:
        print(f"❌ Не удалось получить устройства вывода: {e}")
        return ["Default"]

# Озвучка текста
async def speak(text):
    try:
        communicate = edge_tts.Communicate(text, voice=selected_voice)
        stream = communicate.stream()

        audio_bytes = b""
        async for chunk in stream:
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        buffer = io.BytesIO(audio_bytes)

        pygame.mixer.quit()
        pygame.mixer.init(devicename=selected_device_name)
        pygame.mixer.music.load(buffer)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)

    except Exception as e:
        print(f"❌ Ошибка при озвучке: {e}")

# Очередь озвучки
async def speak_worker():
    while True:
        text = await message_queue.get()
        await speak(text)
        message_queue.task_done()

# Слушаем Twitch чат
async def listen(NICKNAME, TOKEN, CHANNEL):
    try:
        reader, writer = await asyncio.open_connection(SERVER, PORT)
        if not TOKEN.startswith("oauth:"):
            TOKEN = f"oauth:{TOKEN}"

        writer.write(f"PASS {TOKEN}\r\n".encode())
        writer.write(f"NICK {NICKNAME}\r\n".encode())
        writer.write(f"JOIN {CHANNEL}\r\n".encode())
        await writer.drain()

        print(f"📡 Подключено к чату {CHANNEL}")

        while True:
            data = await reader.readline()
            message = data.decode().strip()

            if message.startswith("PING"):
                writer.write("PONG :tmi.twitch.tv\r\n".encode())
                await writer.drain()
            elif "PRIVMSG" in message:
                parts = message.split('!', 1)
                if len(parts) > 1:
                    username = parts[0][1:]
                    msg_text = message.split('PRIVMSG', 1)[1].split(':', 1)[1].strip()
                    print(f"{username}: {msg_text}")

                    if (
                        len(msg_text) < 500 and
                        not msg_text.startswith('!') and
                        'http' not in msg_text and
                        username.lower() != 'nightbot'
                    ):
                        await message_queue.put(msg_text)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        input("Нажмите Enter для выхода...")

# Основной запуск
async def main_logic(nickname, token, channel):
    asyncio.create_task(speak_worker())
    await listen(nickname, token, channel)

# Кнопка подключения
def on_connect_button_click(entry_nickname, entry_token, voice_var, device_var, root):
    global selected_voice, selected_device_name
    NICKNAME = entry_nickname.get()
    TOKEN = entry_token.get()
    selected_voice = voice_var.get()
    selected_device_name = device_var.get()

    if not NICKNAME or not TOKEN:
        messagebox.showerror("Ошибка", "Заполните все поля!")
        return

    CHANNEL = f"#{NICKNAME}"

    # Скрытие окна и запуск трея
    root.withdraw()
    create_tray_icon(root)

    # Запуск логики в отдельном потоке
    threading.Thread(
        target=lambda: asyncio.run(main_logic(NICKNAME, TOKEN, CHANNEL)),
        daemon=True
    ).start()


# Современный интерфейс
def create_interface():
    root = tb.Window(themename="cyborg")  # Темы: flatly, minty, vapor, superhero, darkly и др.
    root.title("🎙️ Twitch Chat to Speech")
    root.geometry("420x450")
    root.resizable(False, False)

    tb.Label(root, text="👤 Twitch никнейм:", font=("Segoe UI", 10)).pack(pady=(20, 5))
    entry_nickname = tb.Entry(root, width=30, bootstyle="info")
    entry_nickname.pack()

    tb.Label(root, text="🔒 OAuth токен:", font=("Segoe UI", 10)).pack(pady=(15, 5))
    entry_token = tb.Entry(root, width=30, show="*", bootstyle="info")
    entry_token.pack()

    tb.Label(root, text="🗣️ Голос:", font=("Segoe UI", 10)).pack(pady=(15, 5))
    voice_var = tk.StringVar(value="ru-RU-SvetlanaNeural")
    voice_menu = tb.OptionMenu(
    root,
    voice_var,
    "ru-RU-SvetlanaNeural",
    "ru-RU-SvetlanaNeural",
    "ru-RU-DmitryNeural",
    bootstyle="dark"
    )
    voice_menu.config(width=25)  # фикс ширина
    voice_menu.pack(padx=20, fill='x')


    tb.Label(root, text="🔊 Аудиовыход:", font=("Segoe UI", 10)).pack(pady=(15, 5))
    devices = get_audio_output_devices()
    device_var = tk.StringVar(value=devices[0])
    device_menu = tb.OptionMenu(root, device_var, *devices, bootstyle="dark")
    device_menu.pack()

    tb.Button(
    root,
    text="🚀 Подключиться",
    command=lambda: on_connect_button_click(entry_nickname, entry_token, voice_var, device_var, root),
    bootstyle="success",
    width=25
    ).pack(pady=30)


    root.mainloop()

# Запуск
if __name__ == "__main__":
    create_interface()