import vkp_app.vkp_bus as bus #Шина обмена данными

import vkp_app.vkp_settings
import vkp_app.vkp_db as db #База данных
from  vkp_app.vkp_logging import log #Подключение модуля вывода сообщений
from vkp_app.vkp_pdf import getpdf

import requests
from bs4 import BeautifulSoup  
from io import BytesIO
import os
from time import sleep
from random import randint
from tqdm import tqdm
import json



headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Sec-GPC': '1',
    'Priority': 'u=0, i',
}


#https://stackoverflow.com/questions/71603314/ssl-error-unsafe-legacy-renegotiation-disabled
import urllib3
import ssl


class CustomHttpAdapter (requests.adapters.HTTPAdapter):
    # "Transport adapter" that allows us to use custom ssl_context.

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)


def get_legacy_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount('https://', CustomHttpAdapter(ctx))
    return session



def start_egrz():
    global bus
    response = requests.get('https://open-api.egrz.ru/api/PublicRegistrationBook/?$filter=contains(tolower(SubjectRf),tolower(%27%D0%A1%D0%B0%D0%BD%D0%BA%D1%82-%D0%9F%D0%B5%D1%82%D0%B5%D1%80%D0%B1%D1%83%D1%80%D0%B3%20-%2078%27))&$orderby=ExpertiseDate%20desc%20&$count=true&$top=5&',
    headers=headers, verify=False)
    #response = get_legacy_session().get('https://open-api.egrz.ru/api/PublicRegistrationBook/?$filter=contains(tolower(SubjectRf),tolower(%27%D0%A1%D0%B0%D0%BD%D0%BA%D1%82-%D0%9F%D0%B5%D1%82%D0%B5%D1%80%D0%B1%D1%83%D1%80%D0%B3%20-%2078%27))&$orderby=ExpertiseDate%20desc%20&$count=true&$top=5&',
    #headers=headers, verify=False)
    response.raise_for_status()
    response = response.json()

    eventtypesall = response['value']
    
    for i in eventtypesall:
        if bus.stop==True: #Обнаружен флаг остановки
            log('Обнаружен флаг остановки в модуле ЕГРЗ', type_='info')
            raise bus.UserStopError()
        #Проверяем, был ли уже загружен документ в архив (тогда пропускаем его, возвращаемся в начало цикла)
        if db.indb(i['Key']): 
            log ("Документ с кодом " + i['Key'] + "уже есть в архиве, пропускаем его", type_='info')
            continue
            
        text = "Объект: %s, Адрес: %s, Застройщик: %s, Вид заключения: %s" % (i['ExpertiseObjectName'], i['ExpertiseObjectAddress'],i['DeveloperOrganizationInfo'], i['ExpertiseResultType'])
        log(text)
        db.todb('egrz', i['Key'], text)

