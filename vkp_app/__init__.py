"""
Модуль инициализации и запуска мониторов недвижимости с веб-интерфейсом
"""

import os
import traceback
import sys
import logging
from logging.handlers import RotatingFileHandler
import threading
import json
import datetime
from time import sleep
from typing import List, Dict, Any

import pandas as pd
from tqdm import tqdm
from flask import Flask, abort, render_template, redirect, url_for, send_file
from werkzeug.utils import secure_filename
# Импорт модулей проекта
import vkp_app.vkp_settings as settings
import vkp_app.vkp_db as db
import vkp_app.vkp_bus

# Импорт мониторов
from vkp_app.monitors import (
    vkp_mon_gasn,
    vkp_mon_egrz,
    vkp_mon_gradplan,
    vkp_mon_ago,
    vkp_mon_gike,
    vkp_mon_antikor,
    vkp_mon_slush
)

# Настройка корневого логгера
logging.root.handlers = []  # Сбрасываем все обработчики
logging.basicConfig(force=True)  # Принудительная перезагрузка конфигурации
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
        RotatingFileHandler('app.log', maxBytes=5*1024*1024, backupCount=3)  # В файл
    ]
)
logger = logging.getLogger(__name__)
logger.info("Логгер успешно настроен")  # Проверочное сообщение

# Конфигурация приложения
APP_VERSION = settings.VERSION
HOST_NAME = "0.0.0.0"
PORT = 23336
TIME_OF_COVERAGE = '0'

# Инициализация Flask
app = Flask(__name__)

# Список мониторов для запуска
MONITORS = {
    'all': [
        vkp_mon_gike.start_gike,
        vkp_mon_gradplan.start_gradplan,
        vkp_mon_ago.start_ago,
        vkp_mon_gasn.start_gasn,
        vkp_mon_egrz.start_egrz,
        vkp_mon_antikor.start_antikor,
        vkp_mon_slush.start_slush,
    ],
    'gasn': [vkp_mon_gasn.start_gasn],
    'gike': [
        vkp_mon_gike.start_gike
    ]
}

# Глобальное состояние
current_monitors = MONITORS['all']
status = 1
posts_data: List[Dict[str, Any]] = []

def initialize_app():
    """Инициализация приложения"""
    logger.info(f"{settings.WELCOME_MESSAGE} версия {APP_VERSION}")
    
    # Запуск Flask в отдельном потоке (НЕ демон)
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host=HOST_NAME, 
            port=PORT, 
            debug=True, 
            use_reloader=False
        ),
        name="Flask Thread"
    )
    flask_thread.start()
    
    # Запуск мониторов в отдельном потоке (НЕ демон)
    monitor_thread = threading.Thread(
        target=run_monitors,
        name="Monitor Thread"
    )
    monitor_thread.start()
    
    logger.info("Инициализация приложения завершена")

def get_posts_from_db() -> List[Dict[str, Any]]:
    """Получение постов из базы данных"""
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {settings.TABLE_NAME} ORDER BY date DESC")
            columns = [column[0] for column in cursor.description]
            posts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Обработка текста поста
            for post in posts:
                if post.get('text'):
                    post['text'] = post['text'].split('\n')
                else:
                    post['text'] = []
            
            return posts
    except sqlite3.Error as error:
        logger.error(f"Ошибка получения данных из БД: {error}")
        return []

def run_monitors():
    global TIME_OF_COVERAGE
    
    logger.info("Мониторы запущены. Ожидание команд...")
    
    while True:
        if vkp_app.vkp_bus.stop:
            logger.info("Обнаружен флаг STOP, сбрасываем состояние...")
            vkp_app.vkp_bus.stop = False
            vkp_app.vkp_bus.finish = False
            vkp_app.vkp_bus.force_run = False  # Сбрасываем и этот флаг
            sleep(0.5)
            continue
        
        # Проверяем как обычные условия, так и флаг принудительного запуска
        if getattr(vkp_app.vkp_bus, 'force_run', False) or (not vkp_app.vkp_bus.auto_run and not vkp_app.vkp_bus.finish):
            logger.info(f"Условия запуска: force_run={getattr(vkp_app.vkp_bus, 'force_run', False)}, "
                       f"auto_run={vkp_app.vkp_bus.auto_run}, finish={vkp_app.vkp_bus.finish}")
            
            if getattr(vkp_app.vkp_bus, 'force_run', False):
                vkp_app.vkp_bus.force_run = False  # Сбрасываем флаг после использования
            
            with tqdm(total=len(current_monitors), desc="Общий ход:") as pbar:
                for monitor in current_monitors:
                    if vkp_app.vkp_bus.stop:
                        break
                    try:
                        logger.info(f"Запускаем монитор: {monitor.__name__}")
                        monitor()
                        pbar.update(1)
                    except Exception as e:
                        logger.error(f"Ошибка в мониторе {monitor.__name__}: {str(e)}")
            
            vkp_app.vkp_bus.finish = True
            TIME_OF_COVERAGE = datetime.datetime.now()
        
        sleep(0.1)

# Flask routes
@app.route('/status', methods=['GET'])
def get_status():
    """Получение статуса работы системы"""
    status_list = {'status': status}
    return json.dumps(status_list)

@app.route('/get_image/<path:filename>')
@app.route('/get_image/<path:subpath>')
def get_image(subpath):
    """Загрузка изображений из подпапок image_storage"""
    try:
        # Логирование входящего запроса
        logger.info(f"Получен запрос изображения: {subpath}")
        
        # Проверка на пустое имя или специальные значения
        if not subpath or 'nan' in subpath.lower():
            logger.warning("Пустое имя файла или содержит 'nan'")
            abort(400, description="Некорректное имя файла")

        # Нормализация пути (замена слешей и удаление небезопасных элементов)
        subpath = subpath.replace('\\', '/').strip('/')
        
        # Полный путь к файлу
        full_path = os.path.abspath(os.path.join(settings.IMAGE_BASE_DIR, subpath))
        base_dir = os.path.abspath(settings.IMAGE_BASE_DIR)
        
        # Логирование путей для отладки
        logger.debug(f"Базовая директория: {base_dir}")
        logger.debug(f"Полный путь к файлу: {full_path}")
        
        # Проверка безопасности
        if not full_path.startswith(base_dir):
            logger.error(f"Попытка доступа вне разрешенной директории: {full_path}")
            abort(403, description="Доступ запрещен")
        
        # Проверка существования файла
        if not os.path.isfile(full_path):
            logger.error(f"Файл не найден: {full_path}")
            logger.info(f"Содержимое директории: {os.listdir(os.path.dirname(full_path))}")
            abort(404, description="Файл не найден")
        
        # Определение MIME-типа
        ext = os.path.splitext(subpath)[1].lower()
        mimetype = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }.get(ext, 'application/octet-stream')
        
        logger.info(f"Успешно отправляю файл: {full_path}")
        return send_file(full_path, mimetype=mimetype)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при загрузке изображения: {str(e)}", exc_info=True)
        abort(500, description="Внутренняя ошибка сервера")
        
@app.route('/repair')
def repair():
    """Ремонт базы данных"""
    logger.info('Получена команда исправления БД')
    db.optimize_db()
    return redirect(url_for("index"))

@app.route('/restart')
def restart():
    """Перезапуск всех мониторов"""
    global current_monitors
    current_monitors = MONITORS['all']
    
    logger.info('Получена команда перезапуска сбора информации')
    vkp_app.vkp_bus.stop = True 
    vkp_app.vkp_bus.auto_run = False
    vkp_app.vkp_bus.finish = False
    return redirect(url_for("index"))

@app.route('/only_gasn')
def only_gasn():
    """Запуск только монитора ГАСН"""
    global current_monitors
    current_monitors = MONITORS['gasn']
    
    logger.info('Получена команда перезапуска сбора только ГАСН')
    vkp_app.vkp_bus.stop = True 
    vkp_app.vkp_bus.auto_run = False
    vkp_app.vkp_bus.finish = False
    return redirect(url_for("index"))

@app.route('/only_gike')
def only_gike():
    logger.info('Получена команда перезапуска ГИКЭ')
    global current_monitors
    current_monitors = MONITORS['gike']
    
    # Явный сброс всех флагов
    vkp_app.vkp_bus.stop = False
    vkp_app.vkp_bus.finish = False
    vkp_app.vkp_bus.auto_run = False
    
    return redirect(url_for("index"))



@app.route('/')
def index():
    """Главная страница"""
    global posts_data
    posts_data = get_posts_from_db()
    
    return render_template(
        "index.html",
        posts=posts_data, 
        count_of_posts=len(posts_data), 
        time_of_coverage=TIME_OF_COVERAGE, 
        total_mons=len(current_monitors), 
        finish=vkp_app.vkp_bus.finish
    )

initialize_app()

try:
    # Бесконечный цикл, чтобы программа не завершалась
    while True:
        sleep(1)
except KeyboardInterrupt:
    logger.info("Получен сигнал прерывания, завершение работы...")
    vkp_app.vkp_bus.stop = True