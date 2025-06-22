import os
import re
import logging
import traceback
import random
import shutil
import numpy as np
from typing import Tuple, Dict, List
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageChops

import cv2
import qrcode
import requests
import fitz
from pypdf import PdfReader
import ocrmypdf

import vkp_app.vkp_bus as bus
import vkp_app.vkp_telegram

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
DEFAULT_TIMEOUT = 30  # seconds
MAX_PAGES = 50  # Максимальное количество обрабатываемых страниц
MAX_IMAGE_SIZE = (1200, 1600)  # Максимальный размер изображений
THUMBNAIL_SIZE = (250, 250)  # Размер миниатюр
BG_COLOR = (241, 241, 241)  # Цвет фона
TEXT_COLOR = (9, 53, 46)  # Цвет текста

def extract_data(txt: str) -> Dict[str, str]:
    """Извлекает структурированные данные из текста PDF."""
    patterns = {
        'Объект экспертизы': r'объекта? культурного наследия',
        'Собственник объекта': r'(?<=.обственник)([\w|\W]{1,45})наследия',
        'По объекту': r'по объекту:',
        'Адрес объекта': r'по адресу', 
        'Проект предусматривает': r'(?<=.роект)([\w|\W]{1,45})н?е? ?предусматрива.тс?я?',
        'Заключение экспертизы': r'(?<=.ывод)([\w|\W]{1,4500})(?=заключение)',
        'Архитектурные решения': r'(?i)Архитектурн.. решени.'
    }
    
    result = {}
    for key, pattern in patterns.items():
        try:
            match = re.search(pattern, txt)
            if match:
                extracted = txt[match.span()[1]:]
                result[key] = vkp_app.vkp_telegram.string_shorter(extracted, 1000)
            else:
                result[key] = ''
        except Exception:
            logger.error(f"Ошибка извлечения '{key}': {traceback.format_exc()}")
            result[key] = ''
    
    return result

def resize_and_pad(img: np.ndarray, size: Tuple[int, int], pad_color: int = 0) -> np.ndarray:
    """Изменяет размер изображения с сохранением пропорций."""
    h, w = img.shape[:2]
    sh, sw = size

    # Выбор метода интерполяции
    interp = cv2.INTER_AREA if (h > sh or w > sw) else cv2.INTER_CUBIC
    aspect = w / h

    # Вычисление новых размеров
    if aspect > 1:  # Горизонтальное изображение
        new_w = sw
        new_h = int(new_w / aspect)
        pad_top = pad_bot = (sh - new_h) // 2
        pad_left = pad_right = 0
    elif aspect < 1:  # Вертикальное изображение
        new_h = sh
        new_w = int(new_h * aspect)
        pad_left = pad_right = (sw - new_w) // 2
        pad_top = pad_bot = 0
    else:  # Квадратное изображение
        new_h, new_w = sh, sw
        pad_left = pad_right = pad_top = pad_bot = 0

    # Масштабирование и добавление отступов
    scaled_img = cv2.resize(img, (new_w, new_h), interpolation=interp)
    scaled_img = cv2.copyMakeBorder(
        scaled_img, pad_top, pad_bot, pad_left, pad_right,
        borderType=cv2.BORDER_CONSTANT, value=pad_color
    )
    
    return scaled_img

def make_qr(link: str) -> np.ndarray:
    """Генерирует QR-код для ссылки."""
    qr = qrcode.QRCode(
        version=4,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=2,
        border=2,
    )
    qr.add_data(link)
    qr.make(fit=False)
    
    qr_img = np.array(qr.make_image(fill_color='green', back_color=BG_COLOR))
    return cv2.cvtColor(qr_img, cv2.COLOR_RGB2BGR)

def process_image_page(page: fitz.Page, matrix: fitz.Matrix) -> Tuple[np.ndarray, bool]:
    """Обрабатывает одну страницу PDF, извлекая изображение."""
    try:
        pix = page.get_pixmap(matrix=matrix)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        pil_img = Image.fromarray(img)
        is_color = not is_greyscale(pil_img)
        h, w = img.shape[:2]
        
        # Фильтрация по размеру и ориентации
        if w / h < 1:  # Вертикальная ориентация
            return img, is_color
    except Exception:
        logger.error(f"Ошибка обработки страницы: {traceback.format_exc()}")
    
    return None, False

def is_greyscale(im: Image.Image) -> bool:
    """Проверяет, является ли изображение монохромным."""
    if im.mode == "L":
        return True
    if im.mode == "RGB":
        rgb = im.split()
        return (ImageChops.difference(rgb[0], rgb[1]).getextrema()[1] == 0 and 
               ImageChops.difference(rgb[0], rgb[2]).getextrema()[1] == 0)
    return False

def make_thumbnails(images_collection: List[np.ndarray], link: str) -> np.ndarray:
    """Создает миниатюры из коллекции изображений."""
    if not images_collection:
        logger.warning("Нет изображений для создания миниатюр")
        return None

    # Подготовка миниатюр
    thumbnails = []
    for img in tqdm(images_collection[1:], desc='Сжатие изображений'):
        try:
            thumb = resize_and_pad(img, THUMBNAIL_SIZE, BG_COLOR)
            thumbnails.append(thumb)
        except Exception:
            logger.error(f"Ошибка создания миниатюры: {traceback.format_exc()}")

    # Создание матрицы миниатюр
    try:
        img_h, img_w, img_c = THUMBNAIL_SIZE[1], THUMBNAIL_SIZE[0], 3
        margin_x, margin_y = 567, 20
        mat_x = img_w * 2 + margin_x
        mat_y = img_h * 3 + margin_y * 2
        
        imgmatrix = np.full((mat_y, mat_x, img_c), BG_COLOR, dtype=np.uint8)
        
        # Расположение миниатюр в матрице
        for i, thumb in enumerate(thumbnails[:6]):  # Максимум 6 миниатюр (2x3)
            row = i // 2
            col = i % 2
            x = col * (img_w + margin_x)
            y = row * (img_h + margin_y)
            imgmatrix[y:y+img_h, x:x+img_w] = thumb
        
        # Добавление основной страницы
        imgmatrix = cv2.copyMakeBorder(imgmatrix, 40, 190, 25, 25, cv2.BORDER_CONSTANT, value=BG_COLOR)
        main_img = images_collection[0]
        y_offset, x_offset = 30, 260
        imgmatrix[y_offset:y_offset+main_img.shape[0], x_offset:x_offset+main_img.shape[1]] = main_img
        
        # Добавление текста
        font = cv2.FONT_HERSHEY_COMPLEX
        texts = [
            (link, 0.5, 1),
            ("Предпросмотр материалов общественных обсуждений.".upper(), 0.3, 1),
            ("Возможны ошибки, проверяйте информацию в первоисточнике.".upper(), 0.3, 1),
            ("Текст и иллюстрации могут охраняться авторским правом.".upper(), 0.3, 1),
            ("Этот сервис не имеет отношения к органам власти.".upper(), 0.3, 1),
            ("Электронная почта для связи: alfablend@gmail.com".upper(), 0.3, 1)
        ]
        
        offset = 900
        for i, (text, font_scale, thickness) in enumerate(texts):
            text_size = cv2.getTextSize(text, font, font_scale, thickness)
            pos = (imgmatrix.shape[1] // 2 - text_size[0][0] // 2, offset + 40 * i)
            
            if i == 0:  # Основная надпись с фоном
                cv2.rectangle(
                    imgmatrix,
                    (pos[0]-5, pos[1]-text_size[0][1]*3),
                    (pos[0]+text_size[0][0]+5, pos[1]+text_size[0][1]*2),
                    (0, 255, 0),
                    -1
                )
            
            cv2.putText(imgmatrix, text, pos, font, font_scale, TEXT_COLOR, thickness)
        
        return imgmatrix
    except Exception:
        logger.error(f"Ошибка создания матрицы миниатюр: {traceback.format_exc()}")
        return None

def process_pdf(docpath: str) -> Tuple[str, List[np.ndarray]]:
    """Обрабатывает PDF файл, извлекая текст и изображения."""
    try:
        # Извлечение текста
        with PdfReader(docpath) as pdf:
            pages_txt = "".join(page.extract_text() or "" for page in pdf.pages[:MAX_PAGES])
        
        # Извлечение изображений
        images_collection = []
        images_collection_color = []
        images_collection_bw = []
        
        with fitz.open(docpath) as doc:
            matrix = fitz.Matrix(1, 1)  # Масштаб 100%
            
            # Используем ThreadPool для ускорения обработки страниц
            with ThreadPoolExecutor() as executor:
                futures = []
                for page_num in range(min(len(doc), MAX_PAGES)):
                    futures.append(executor.submit(
                        process_image_page, 
                        doc.load_page(page_num), 
                        matrix
                    ))
                
                for future in tqdm(futures, desc="Обработка страниц"):
                    img, is_color = future.result()
                    if img is not None:
                        if is_color:
                            images_collection_color.append(img)
                        else:
                            images_collection_bw.append(img)
        
        # Выбор коллекции изображений (предпочтение цветным)
        images_collection = images_collection_color or images_collection_bw
        random.shuffle(images_collection)
        
        # Добавление титульной страницы
        if images_collection:
            with fitz.open(docpath) as doc:
                pix = doc.load_page(0).get_pixmap(matrix=matrix)
                title_img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                images_collection.insert(0, cv2.cvtColor(title_img, cv2.COLOR_RGB2BGR))
        
        return pages_txt, images_collection
    
    except Exception:
        logger.error(f"Ошибка обработки PDF: {traceback.format_exc()}")
        return "", []

def clean_temp_files():
    """Очищает временные файлы."""
    try:
        for fname in ['temp.pdf', 'tempocr.pdf']:
            if os.path.exists(fname):
                os.remove(fname)
        logger.info("Временные файлы очищены")
    except Exception:
        logger.error(f"Ошибка очистки временных файлов: {traceback.format_exc()}")

def getgike(link: str, cookies: dict, headers: dict, short_link: str = '') -> Tuple[np.ndarray, Dict[str, str]]:
    """Основная функция для обработки PDF по ссылке."""
    try:
        # Загрузка PDF
        with requests.get(link, cookies=cookies, headers=headers, stream=True, timeout=DEFAULT_TIMEOUT, verify=False) as r:
            r.raise_for_status()
            
            with open('temp.pdf', 'wb') as f:
                for chunk in tqdm(r.iter_content(chunk_size=8192), desc="Загрузка PDF", unit='KB'):
                    if bus.stop:
                        raise bus.UserStopError()
                    if chunk:
                        f.write(chunk)
        
        # Попытка OCR
        docpath = 'temp.pdf'
        try:
            ocrmypdf.ocr(
                'temp.pdf', 'tempocr.pdf', 
                language='rus', 
                pages='1-50',  # Ограничение количества страниц
                optimize=0,
                progress_bar=False
            )
            docpath = 'tempocr.pdf'
            logger.info("OCR применен успешно")
        except (ocrmypdf.exceptions.PriorOcrFoundError, ocrmypdf.exceptions.TaggedPDFError):
            logger.info("OCR не требуется")
        except Exception:
            logger.error(f"Ошибка OCR: {traceback.format_exc()}")
        
        # Обработка PDF
        pages_txt, images_collection = process_pdf(docpath)
        data = extract_data(pages_txt)
        
        # Создание миниатюр
        img = make_thumbnails(
            images_collection, 
            short_link if short_link else link
        )
        
        return img, data
    
    except requests.RequestException as e:
        logger.error(f"Ошибка загрузки PDF: {str(e)}")
        return None, {}
    except bus.UserStopError:
        logger.info("Обработка остановлена пользователем")
        raise
    except Exception:
        logger.error(f"Неожиданная ошибка: {traceback.format_exc()}")
        return None, {}
    finally:
        clean_temp_files()