import asyncio
import edge_tts
import io
import os
import pygame
import tkinter as tk
import sounddevice as sd
from tkinter import messagebox

# Настройки подключения
SERVER = 'irc.chat.twitch.tv'
PORT = 6667
message_queue = asyncio.Queue()

# Глобальные переменные для настроек
selected_device_name = None
selected_voice = "ru-RU-SvetlanaNeural"

# Получение списка устройств вывода
def get_audio_output_devices():
    try:
        return [device['name'] for device in sd.query_devices() if device['max_output_channels'] > 0]
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

# Постоянный воркер озвучки
async def speak_worker():
    while True:
        text = await message_queue.get()
        await speak(text)
        message_queue.task_done()

# Прослушивание Twitch чата
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

# Основной асинхронный запуск
async def main_logic(nickname, token, channel):
    asyncio.create_task(speak_worker())
    await listen(nickname, token, channel)

# Обработка кнопки
def on_connect_button_click(entry_nickname, entry_token, voice_var, device_var):
    global selected_voice, selected_device_name
    NICKNAME = entry_nickname.get()
    TOKEN = entry_token.get()
    selected_voice = voice_var.get()
    selected_device_name = device_var.get()

    if not NICKNAME or not TOKEN:
        messagebox.showerror("Ошибка", "Заполните все поля!")
        return

    CHANNEL = f"#{NICKNAME}"
    asyncio.run(main_logic(NICKNAME, TOKEN, CHANNEL))

# Графический интерфейс
def create_interface():
    root = tk.Tk()
    root.title("Twitch Chat to Speech")

    tk.Label(root, text="Twitch никнейм:").pack(pady=5)
    entry_nickname = tk.Entry(root, width=40)
    entry_nickname.pack()

    tk.Label(root, text="OAuth токен:").pack(pady=5)
    entry_token = tk.Entry(root, width=40, show="*")
    entry_token.pack()

    tk.Label(root, text="Голос:").pack(pady=5)
    voice_var = tk.StringVar(value="ru-RU-SvetlanaNeural")
    voice_menu = tk.OptionMenu(root, voice_var, "ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural")
    voice_menu.pack()

    tk.Label(root, text="Аудиовыход:").pack(pady=5)
    devices = get_audio_output_devices()
    device_var = tk.StringVar(value=devices[0])
    device_menu = tk.OptionMenu(root, device_var, *devices)
    device_menu.pack()

    tk.Button(root, text="Подключиться", command=lambda:
              on_connect_button_click(entry_nickname, entry_token, voice_var, device_var)).pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    create_interface()
