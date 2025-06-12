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



def checkago(row):
    if db.indb(row['Номер решения']): 
        log ("Документ с кодом " + row['Номер решения'] + "уже есть в архиве, пропускаем его", type_='info')
        return
    text = 'Согласование АГО № %s' % (row['Номер решения'])
    data4telegram=OrderedDict([('Номер решения', row['Номер решения']), ('Дата решения', row['Дата решения']), ('Адрес', row['Адрес']), ('Кадастровый номер', str(row['Кадастровый номер'])), ('Функциональное назначение', row['Функциональное назначение'])])
    print(text)        
    #Определяем кадастровый номер
    kadastr = re.findall(r'\d{1,10}\:\d{1,10}\:\d{1,10}\:\d{1,10}', str(row['Кадастровый номер']))
    print(kadastr)
    try:
        img = plotmap(kadastr)
    except: img=''
    log(text)
    #imgcv2fordb = cv2.cvtColor(imgcv2fordb, cv2.COLOR_RGB2BGR)
    #unique_filename='' #заглушка для отладки
    unique_filename= db.todb('ago', row['Номер решения'], text, img)
    link='https://kgainfo.spb.ru/current_activities/%d0%be%d1%82%d0%ba%d1%80%d1%8b%d1%82%d1%8b%d0%b5-%d0%b4%d0%b0%d0%bd%d0%bd%d1%8b%d0%b5/opendata/7830000994-ago/' #Переопределяем ссылку для отправки в телеграм
    vkp_app.vkp_telegram.to_telegram('ago', img, link, text, data4telegram)
    sleep(randint(5,10))  

def start_ago():
   
    df=pd.read_html('https://kgainfo.spb.ru/current_activities/%d0%be%d1%82%d0%ba%d1%80%d1%8b%d1%82%d1%8b%d0%b5-%d0%b4%d0%b0%d0%bd%d0%bd%d1%8b%d0%b5/opendata/7830000994-ago/')[1]
    df=df.head(25)
    
    df.apply(checkago, axis=1)
    
    
    
    
    
    

    
   

