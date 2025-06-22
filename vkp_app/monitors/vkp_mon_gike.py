import vkp_app.vkp_bus as bus
import vkp_app.vkp_settings
import vkp_app.vkp_db as db
import vkp_app.vkp_extract
import vkp_app.vkp_telegram

import requests
from bs4 import BeautifulSoup
from time import sleep
from random import randint
import datetime
import json
import re
import traceback
import logging
import os
from collections import OrderedDict

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('vkp_mon_gike')

# Конфигурация запросов
COOKIES = {}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
}

MKRF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
}

MKRF_PARAMS = {
    'DOCS[KEYWORDS]': 'санкт-',
    'DOCS[VIEW_DOCUMENTS]': '',
    'DOCS[AUTHORITY]': '',
    'DOCS[TYPE_DOCUMENTS]': '',
    'DOCS[DATE_1]': '',
    'DOCS[DATE_2]': '',
    'DOCS[NUMBER]': '',
}

def process_kgiop_expertise(link: str, link_caption: str = "") -> None:
    """Обрабатывает одну экспертизу с сайта КГИОП."""
    if bus.stop:
        logger.info('Обнаружен флаг остановки в модуле ГИКЕ')
        raise bus.UserStopError()

    if db.is_post_exists(link):
        logger.info(f"Документ по ссылке {link} уже есть в архиве, пропускаем")
        return

    try:
        logger.info(f"Загружаем экспертизу: {link}")
        img, data = vkp_app.vkp_extract.getgike(link, cookies=COOKIES, headers=HEADERS)
        
        txt = '__Выдержки для предварительного просмотра__. '
        for el in data:
            txt += f"{el}:\n\n{data[el]}\n\n"
        
        if data.get('Проект предусматривает'):
            data4telegram = OrderedDict([('Пытаемся определить, что предусматривается проектом', 
                                       data['Проект предусматривает'])])
        elif data.get('По объекту'):
            data4telegram = OrderedDict([('Пытаемся определить, что предусматривается проектом', 
                                       data['По объекту'])])
        else:
            data4telegram = OrderedDict()

        if not link_caption:
            link_caption = f"Экспертиза {link[:225]}..."

        txt = f"{link}\n\n{txt}"
        image_path = db.add_post('gike', link, txt, img)
        if image_path:
            unique_filename = os.path.splitext(os.path.basename(image_path))[0]
            vkp_app.vkp_telegram.to_telegram("gike", img, link, link_caption, data4telegram, unique_filename)
        else:
            logger.error(f"Не удалось сохранить экспертизу {link} в базу данных")

    except Exception as e:
        logger.error(f"Ошибка при обработке экспертизы {link}: {str(e)}")
        logger.error(traceback.format_exc())

def process_kgiop_page(year: int) -> None:
    """Обрабатывает страницу с экспертизами КГИОП за указанный год."""
    try:
        logger.info(f"Запрашиваем страницу экспертиз за {year} год")
        url = f'https://kgiop.gov.spb.ru/deyatelnost/zaklyucheniya-gosudarstvennyh-istoriko-kulturnyh-ekspertiz/gosudarstvennye-istoriko-kulturnye-ekspertizy-za-{year}-g/'
        response = requests.get(url, cookies=COOKIES, headers=HEADERS, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")

        # Выбираем только нужные ссылки при помощи лямбды
        links = soup.find_all('a', href=lambda href: href 
                              and ('disk.yandex.ru' in href
                                    or '/media/uploads/userfiles/' in href))
        logger.info(f"Найдено {len(links)} ссылок. Начинаем обработку")
        
        for i, link in enumerate(links):
            if bus.stop:
                logger.info("Обнаружен флаг остановки при обработке КГИОП")
                raise bus.UserStopError()
                
            try:
                link_caption = ''
                if "Срок рассмотрения обращений" in link.text:
                    parent_td = link.find_parent('td')
                    if parent_td:
                        prev_td = parent_td.find_previous_sibling('td')
                        if prev_td:
                            link_caption = f"Экспертиза {prev_td.text} (часть составной экспертизы)"
                            logger.debug(f"Взят заголовок ссылки сбоку: {link_caption}")
                
                if 'disk.yandex.ru' in link['href']:
                    process_yandex_disk_link(link, link_caption)
                elif '/media/uploads/userfiles/' in link['href']:
                    process_kgiop_direct_link(link, link_caption)
                
                sleep(randint(5, 10))
            
            except bus.UserStopError:
                raise  # Пробрасываем выше
            except Exception as e:
                logger.error(f"Ошибка обработки ссылки КГИОП: {str(e)}")
                logger.error(traceback.format_exc())

    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе страницы КГИОП: {str(e)}")
    except bus.UserStopError:
        logger.info("Обработка экспертиз КГИОП остановлена пользователем")
        raise  # Пробрасываем выше
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке страницы КГИОП: {str(e)}")
        logger.error(traceback.format_exc())

    logger.info(f"Обработка ГИКЭ завершена")

def process_yandex_disk_link(link, link_caption):
    """Обрабатывает ссылку на Яндекс.Диск."""
    logger.info(f"Начало обработки экспертизы с Яндекс.Диска по ссылке {link}")
    try:
        apilink = f'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={link["href"]}'
        response_json = requests.get(apilink).json()
        download_link = response_json.get("href")
        
        if download_link:
            process_kgiop_expertise(download_link, link_caption or f"Экспертиза {link.text}")
    except Exception as e:
        logger.error(f"Ошибка обработки ссылки Яндекс.Диск {link['href']}: {str(e)}")

def process_kgiop_direct_link(link, link_caption):
    """Обрабатывает прямую ссылку на файл КГИОП."""
    logger.info(f"Начало обработки экспертизы по прямой ссыклке {link}")
    try:
        direct_link = f"https://kgiop.gov.spb.ru{link['href']}"
        process_kgiop_expertise(direct_link, link_caption or f"Экспертиза {link.text}")
    except Exception as e:
        logger.error(f"Ошибка обработки прямой ссылки КГИОП {link['href']}: {str(e)}")

def process_mkrf_expertises():
    """Обрабатывает экспертизы с сайта Минкульта."""
    try:
        logger.info("Начинаем обработку экспертиз на сайте Минкульта")
        response = requests.get('https://culture.gov.ru/documents/', params=MKRF_PARAMS, headers=MKRF_HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "lxml")
        links = soup.find_all('a')
        logger.info(f"Найдено {len(links)} ссылок на Минкульте")
        
        for i, link in enumerate(links[:20]):  # Ограничиваем количество для теста
            if bus.stop:
                logger.info("Обнаружен флаг остановки в модуле ГИКЕ")
                raise bus.UserStopError()
                
            if ("Акт" in link.text and 
                "государственной историко-культурной экспертизы" in link.text and 
                'водка предложений' not in link.text):
                
                try:
                    process_single_mkrf_expertise(link)
                except bus.UserStopError:
                    raise  # Пробрасываем исключение выше
                except Exception as e:
                    logger.error(f"Ошибка обработки экспертизы: {str(e)}")
                    logger.error(traceback.format_exc())
                
                sleep(randint(5, 10))

    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе страницы Минкульта: {str(e)}")
    except bus.UserStopError:
        logger.info("Обработка экспертиз Минкульта остановлена пользователем")
        raise  # Пробрасываем исключение выше
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке страницы Минкульта: {str(e)}")
        logger.error(traceback.format_exc())


def start_gike():
    """Основная функция мониторинга ГИКЭ."""
    logger.info("=== НАЧАЛО РАБОТЫ start_gike() ===")
    logger.info(f"Состояние флагов: stop={vkp_app.vkp_bus.stop}, "
                f"finish={vkp_app.vkp_bus.finish}, "
                f"force_run={getattr(vkp_app.vkp_bus, 'force_run', False)}")
    
    try:
        # Обработка экспертиз КГИОП
        current_year = datetime.datetime.now().year
        logger.info(f"Обработка экспертиз КГИОП за {current_year} год")
        process_kgiop_page(current_year)
        
        # Обработка экспертиз Минкульта
        logger.info("Обработка экспертиз Минкульта")
        process_mkrf_expertises()
        
    except bus.UserStopError:
        logger.info("Мониторинг ГИКЭ остановлен по запросу пользователя")
        return
    except Exception as e:
        logger.error(f"Критическая ошибка в мониторинге ГИКЭ: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("=== ЗАВЕРШЕНИЕ start_gike() ===")