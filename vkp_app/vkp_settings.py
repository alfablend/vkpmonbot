"""
Модуль глобальных настроек приложения

Содержит основные конфигурационные параметры, настройки логирования 
и обработку критически важных данных (например, токенов).
"""

import os
import logging
from typing import Final

# Версия приложения
VERSION: Final[str] = '0.1'

# Приветственное сообщение
WELCOME_MESSAGE: Final[str] = 'ВКП. Система наблюдения'

# Режим отладки
DEBUG: bool = False

# Конфигурация базы данных
DB_DIR = os.path.join('vkp_app', 'database')
DB_PATH = os.path.join(DB_DIR, 'vkp_database.db')
IMAGE_BASE_DIR = os.path.join(DB_DIR, 'image_storage')
TABLE_NAME = 'posts'
POSTS_LIMIT = 500  # Максимальное количество хранимых постов для каждого типа


# Обработка токена
try:
    with open('token.txt', 'r', encoding='utf-8') as f:
        TOKEN: Final[str] = f.read().strip()
except FileNotFoundError:
    logging.error('Не найден файл ключа для отправки в телеграм! '
                'Создайте token.txt с ключом')
    TOKEN = None
except Exception as e:
    logging.error(f'Ошибка при чтении токена: {e}')
    TOKEN = None