"""Модуль для работы с базой данных SQLite в приложении VKP.

Обрабатывает все операции с базой данных: хранение постов,
проверку дубликатов и управление связанными изображениями.
"""

import os
import sqlite3
import logging
import uuid
from typing import Optional, Union, List, Dict, Any
from datetime import datetime

import cv2
import numpy as np

from vkp_app.vkp_logging import log
import vkp_app.vkp_settings as settings

DB_DIR = settings.DB_DIR
DB_PATH = settings.DB_PATH
IMAGE_BASE_DIR = settings.IMAGE_BASE_DIR
TABLE_NAME = settings.TABLE_NAME
POSTS_LIMIT =settings.POSTS_LIMIT

class DatabaseError(Exception):
    """Базовый класс для ошибок базы данных."""
    pass


def _ensure_dirs_exist() -> None:
    """Создает необходимые директории, если они не существуют."""
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        os.makedirs(IMAGE_BASE_DIR, exist_ok=True)
    except OSError as error:
        logging.error(f"Ошибка при создании директорий: {error}")
        raise DatabaseError("Не удалось создать директории для базы данных")


def _get_connection() -> sqlite3.Connection:
    """Возвращает соединение с базой данных с обработкой ошибок."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as error:
        logging.error(f"Ошибка подключения к базе данных: {error}")
        raise DatabaseError("Не удалось подключиться к базе данных")


def init_db() -> None:
    """Инициализирует базу данных, создает таблицы если их нет."""
    _ensure_dirs_exist()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        date TEXT NOT NULL,
        link TEXT UNIQUE NOT NULL,
        text TEXT,
        image_path TEXT,
        CONSTRAINT link_unique UNIQUE (link)
    );
    """

    try:
        with _get_connection() as conn:
            conn.execute(create_table_sql)
            conn.commit()
    except sqlite3.Error as error:
        logging.error(f"Ошибка инициализации базы данных: {error}")
        raise DatabaseError("Не удалось инициализировать базу данных")


def is_post_exists(link: str) -> bool:
    """Проверяет существует ли пост с указанной ссылкой.
    
    Args:
        link: Ссылка на пост для проверки
        
    Returns:
        bool: True если пост существует, False если нет
        
    Raises:
        DatabaseError: При ошибках запроса к базе
    """
    if settings.DEBUG:
        logging.debug("Режим отладки: проверка по базе пропущена")
        return False

    check_sql = f"SELECT 1 FROM {TABLE_NAME} WHERE link = ? LIMIT 1"

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(check_sql, (link,))
            return cursor.fetchone() is not None
    except sqlite3.Error as error:
        logging.error(f"Ошибка проверки существования поста: {error}")
        raise DatabaseError("Ошибка при проверке существования поста")


def _save_image(image: np.ndarray, post_type: str) -> Optional[str]:
    """Сохраняет изображение на диск и возвращает путь к файлу.
    
    Args:
        image: Изображение в формате numpy array
        post_type: Тип поста (для организации хранения)
        
    Returns:
        str: Относительный путь к сохраненному изображению или None при ошибке
    """
    if not isinstance(image, np.ndarray):
        return None

    try:
        # Создаем поддиректорию для типа поста
        image_dir = os.path.join(IMAGE_BASE_DIR, post_type)
        os.makedirs(image_dir, exist_ok=True)

        # Генерируем уникальное имя файла
        filename = f"{uuid.uuid4()}.jpg"
        filepath = os.path.join(image_dir, filename)

        # Конвертируем и сохраняем изображение
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        cv2.imwrite(filepath, image, [cv2.IMWRITE_JPEG_QUALITY, 90])

        return os.path.join(post_type, filename)
    except Exception as error:
        logging.error(f"Ошибка сохранения изображения: {error}")
        return None


def add_post(
    post_type: str,
    link: str,
    text: str = "",
    image: Optional[np.ndarray] = None
) -> Optional[str]:
    """Добавляет новый пост в базу данных.
    
    Args:
        post_type: Тип поста (категория)
        link: Ссылка на пост
        text: Текст поста
        image: Изображение в формате numpy array
        
    Returns:
        str: Путь к сохраненному изображению или None если изображения нет
        
    Raises:
        DatabaseError: При ошибках работы с базой
    """
    if settings.DEBUG:
        logging.debug("Режим отладки: запись в базу пропущена")
        return None

    # Сохраняем изображение если оно есть
    image_path = _save_image(image, post_type) if image is not None else None

    insert_sql = f"""
    INSERT INTO {TABLE_NAME} (type, date, link, text, image_path)
    VALUES (?, ?, ?, ?, ?)
    """

    try:
        with _get_connection() as conn:
            # Добавляем запись
            conn.execute(
                insert_sql,
                (post_type, datetime.now().isoformat(), link, text, image_path)
            )
            conn.commit()

            # Очищаем старые записи
            _clean_old_posts(post_type)
            
            return image_path
    except sqlite3.IntegrityError:
        logging.warning(f"Пост с ссылкой {link} уже существует")
        return None
    except sqlite3.Error as error:
        logging.error(f"Ошибка добавления поста: {error}")
        raise DatabaseError("Ошибка при добавлении поста в базу")


def _clean_old_posts(post_type: str) -> None:
    """Удаляет старые посты сверх установленного лимита.
    
    Args:
        post_type: Тип постов для очистки
    """
    select_sql = f"""
    SELECT id, image_path FROM {TABLE_NAME}
    WHERE type = ?
    ORDER BY date DESC
    LIMIT -1 OFFSET ?
    """

    delete_sql = f"DELETE FROM {TABLE_NAME} WHERE id = ?"

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем ID и пути к изображениям старых постов
            cursor.execute(select_sql, (post_type, POSTS_LIMIT))
            old_posts = cursor.fetchall()

            # Удаляем связанные изображения
            for post_id, image_path in old_posts:
                if image_path:
                    try:
                        full_path = os.path.join(IMAGE_BASE_DIR, image_path)
                        if os.path.exists(full_path):
                            os.remove(full_path)
                    except OSError as error:
                        logging.error(f"Ошибка удаления изображения: {error}")

            # Удаляем записи из базы
            for post_id, _ in old_posts:
                cursor.execute(delete_sql, (post_id,))
            
            conn.commit()
    except sqlite3.Error as error:
        logging.error(f"Ошибка очистки старых постов: {error}")


def optimize_db() -> None:
    """Оптимизирует базу данных (удаление дублей, уменьшение размера)."""
    try:
        with _get_connection() as conn:
            # Удаление дубликатов по ссылке
            conn.execute(f"""
            DELETE FROM {TABLE_NAME}
            WHERE id NOT IN (
                SELECT MIN(id) FROM {TABLE_NAME}
                GROUP BY link
            )
            """)
            
            # Оптимизация размера базы
            conn.execute("VACUUM")
            conn.commit()
    except sqlite3.Error as error:
        logging.error(f"Ошибка оптимизации базы данных: {error}")
        raise DatabaseError("Ошибка при оптимизации базы данных")


# Инициализация базы при импорте модуля
try:
    init_db()
except DatabaseError as error:
    logging.critical(f"Критическая ошибка инициализации базы: {error}")
    raise