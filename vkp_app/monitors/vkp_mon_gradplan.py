import logging, logging.config
import traceback

import vkp_app.vkp_bus as bus #Шина обмена данными

import vkp_app.vkp_settings
import vkp_app.vkp_db as db #База данных
from  vkp_app.vkp_logging import log #Подключение модуля вывода сообщений
from vkp_app.vkp_pdf import getpdf
from vkp_app.vkp_plotmap import plotmap
import vkp_app.vkp_telegram

import datetime

import requests
import os, sys
from time import sleep
from random import randint
from tqdm import tqdm
import json
import re

import pandas as pd


from collections import OrderedDict



headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Referer': 'https://kgainfo.spb.ru/',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-User': '?1',
    'Sec-GPC': '1',
    'Priority': 'u=0, i',
}



def checkgp(row):
    if db.indb(row['Номер']): 
        log ("Документ с кодом " + row['Номер'] + "уже есть в архиве, пропускаем его", type_='info')
        return
    text = 'Градплан № %s' % (row['Номер'])
    data4telegram=OrderedDict([('Номер', row['Номер']), ('Дата', row['Дата']), ('Адрес', row['Адрес']), ('Кадастровый номер', str(row['Кадастровый номер'])), ('Площадь', row['Площадь']), ('Цель использования', row['Цель использования'])])
    print(text)        
    #Определяем кадастровый номер
    kadastr = re.findall(r'\d{1,10}\:\d{1,10}\:\d{1,10}\:\d{1,10}', str(row['Кадастровый номер']))
    print(kadastr)
    try:
        img = plotmap(kadastr)
    except:
        img=''
    log(text)
    #imgcv2fordb = cv2.cvtColor(imgcv2fordb, cv2.COLOR_RGB2BGR)
    #unique_filename='' #заглушка для отладки
    unique_filename=db.todb('gradplan', row['Номер'], text, img)
    link='https://kgainfo.spb.ru/current_activities/%D0%BE%D1%82%D0%BA%D1%80%D1%8B%D1%82%D1%8B%D0%B5-%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D0%B5/opendata/7830000994-gpzu/' #Переопределяем ссылку для отправки в телеграм
    vkp_app.vkp_telegram.to_telegram('gradplan', img, link, text, data4telegram)
    sleep(randint(5,10))  

def start_gradplan():
   
    df=pd.read_html('https://kgainfo.spb.ru/current_activities/%D0%BE%D1%82%D0%BA%D1%80%D1%8B%D1%82%D1%8B%D0%B5-%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D0%B5/opendata/7830000994-gpzu/')[1]
    df=df.head(25)
    
    df.apply(checkgp, axis=1)
    
    
    
    
    
    

    
   

