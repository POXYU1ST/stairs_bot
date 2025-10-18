from flask import Flask
from threading import Thread
import time
import requests

app = Flask('')

@app.route('/')
def ping():
    return "PONG"

def run():
    app.run(host='0.0.0.0', port=8080)

def ping_server():
    """
    Пингует сервер каждые 5 минут чтобы избежать сна
    Только для Replit
    """
    while True:
        try:
            # Пингуем собственный сервер
            requests.get('https://your-project.your-username.repl.co')
            print("Ping sent to keep alive")
        except:
            print("Ping failed")
        time.sleep(300)  # 5 минут

def keep_alive():
    """
    Запускает веб-сервер и пинг в отдельных потоках
    """
    # Запускаем веб-сервер
    t = Thread(target=run)
    t.daemon = True
    t.start()
    
    # Запускаем пинг (опционально)
    # t2 = Thread(target=ping_server)
    # t2.daemon = True
    # t2.start()
