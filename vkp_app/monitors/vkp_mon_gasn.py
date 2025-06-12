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


from collections import OrderedDict


cookies = {
    
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
    'Accept': '*/*',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://lkexpertiza.spb.ru',
    'Connection': 'keep-alive',
    'Referer': 'https://lkexpertiza.spb.ru/Reestr/ReestrRazrStr',
    # 'Cookie': 'TWz1ce5ZsGQ=CfDJ8KvolaKhGHdIkqbjLzL2fl4jGbnf3-PiYxCYsB8yQxGscCwA9MgFSqAayYgUs8hJgeIzH6CWv42GyvOhkrtxwzlsS29uMMIO2W_7RNflza1nNXMxgjvFtGJS5ynEtJcdRUWuRhV68kjWvYcFi2r-KHs; .AspNet.Session=5dad6e32-8903-a4eb-9f7a-101aa8cdd165',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
    'Priority': 'u=0',
}

#Для разрешений на строительство и ввод
data1 = {
    'Number': '',
    'Rajon': '',
    'Address': '',
    'ZastrName': '',
    'ObjectType': '',
    'ObjectName': '',
    'MarjetingName': '',
    'KadastrNumber': '',
    'DateFrom': '22.10.2024',
    'DateTo': '29.10.2024',
    'DocType1': 'true',
    'OnlyNew': 'true',
}

#Для продленных разрешений на строительство


data2 = {
    'Number': '',
    'Rajon': '',
    'Address': '',
    'ZastrName': '',
    'ObjectType': '',
    'ObjectName': '',
    'MarjetingName': '',
    'KadastrNumber': '',
    'DateFrom': '13.01.2025',
    'DateTo': '20.01.2025',
    'DocTypeProdl': 'true',
    'OnlyNew': 'true'}

#Для уведомлений о сносе
data3 = {
    'Address': '',
    'Nazvanie': '',
    'Rajon': '',
    'Number': '',
    'Zayavitel': '',
    'DateFrom': '22.10.2024',
    'DateTo': '29.10.2024',
}







def read_approve_registry(link, registry_type, data):
    global bus
    if bus.stop==True: #Обнаружен флаг остановки
            raise bus.UserStopError()
    response = requests.post(link, cookies=cookies, headers=headers, data=data)
    response = response.json()
    eventtypesall = response
    for i in eventtypesall:
        #Проверяем, был ли уже загружен документ в архив (тогда пропускаем его, возвращаемся в начало цикла)
        if db.indb(i['Number']): 
            log ("Документ с кодом " + i['Number'] + "уже есть в архиве, пропускаем его", type_='info')
            continue 
        text = '%s № %s' % (registry_type, i['Number'])
        data4telegram=OrderedDict([('Объект', i['ObjectName']), ('Застройщик', i['ZastrName']), ('Адрес', i['Address'])])
        print(text)        
        #Определяем кадастровый номер
        kadastr = re.findall(r'\d{1,10}\:\d{1,10}\:\d{1,10}\:\d{1,10}', i['Address'])
        print(kadastr)
        img = plotmap(kadastr)
        log(text)
        #imgcv2fordb = cv2.cvtColor(imgcv2fordb, cv2.COLOR_RGB2BGR)
        #unique_filename='' #заглушка для отладки
        unique_filename=db.todb('gasn', i['Number'], text, img)
        link='https://lkexpertiza.spb.ru/' #Переопределяем ссылку для отправки в телеграм
        vkp_app.vkp_telegram.to_telegram('gasn', img, link, text, data4telegram)
        sleep(randint(5,10))  

def read_destroy_registry(link, registry_type, data):
    global bus
    if bus.stop==True: #Обнаружен флаг остановки
        log('Обнаружен флаг остановки в модуле ГАСН', type_='info')
        raise bus.UserStopError()
    response = requests.post(link, cookies=cookies, headers=headers, data=data)
    response = response.json()
    eventtypesall = response
    for i in eventtypesall:
        #Проверяем, был ли уже загружен документ в архив (тогда пропускаем его, возвращаемся в начало цикла)
        if db.indb(i['Number']): 
            log ("Документ с кодом " + i['Number'] + "уже есть в архиве, пропускаем его", type_='info')
            continue 
        text = "%s %s. Объект: %s, Адрес: %s, Заявитель: %s" % (registry_type, i['Number'], i['ObjectName'], i['Address'],i['Zayavitel'])
        log(text)
        db.todb('gasn', i['Number'], text)
        sleep(randint(5,10))  



def start_gasn():
    ##НАЧАЛО БЛОКА ДЛЯ ОТЛАДКИ ПО ВАРИАНТУ С ГОТОВОЙ ССЫЛКОЙ (ОБЫЧНО ДОЛЖЕН БЫТЬ ЗАКОММЕНТИРОВАН)
    #ЗАГРУЗКА ЭКСПЕРТИЗЫ БУДЕТ ВЫПОЛНЕНА ПО ЗАДАННОЙ В ЭТОМ БЛОКЕ ССЫЛКЕ, РЕЗУЛЬТАТ ОТПРАВЛЕН ТОЛЬКО ОДНОМУ ПОЛЬЗОВАТЕЛЮ
    #print('РЕЖИМ ОТЛАДКИ С ГОТОВОЙ ССЫЛКОЙ')
    #plotmap('78:40:0850106:1963')
    #img=open('tempmap.jpg', 'rb')
    #bot.send_photo('323157743', img, 'Отладка', parse_mode="html")
    #return
    ##КОНЕЦ БЛОКА ДЛЯ ОТЛАДКИ
    sleep(1)
    #Устанавливаем период запроса
    today = datetime.datetime.now()
    delta = datetime.timedelta(days = 7)
    time_before=(today-delta).strftime('%d.%m.%Y')
    
    #Разрешения на строительство и на ввод
    data=data1
    data['DateFrom'] = time_before
    data['DateTo'] = datetime.date.today().strftime('%d.%m.%Y')
    read_approve_registry('https://lkexpertiza.spb.ru/Reestr/ReestrRazr', 'Новое разрешение на строительство', data)
    read_approve_registry('https://lkexpertiza.spb.ru/Reestr/ReestrVvod', 'Разрешение на ввод в эксплуатацию', data)
    
    #Продленные разрешения на строительство
    data=data2
    data['DateFrom'] = time_before
    data['DateTo'] = datetime.date.today().strftime('%d.%m.%Y')
    read_approve_registry('https://lkexpertiza.spb.ru/Reestr/ReestrRazr', 'Продленное разрешение на строительство', data)
   
    #Уведомления о сносе
    data=data3
    data['DateFrom'] = time_before
    data['DateTo'] = datetime.date.today().strftime('%d.%m.%Y')
    read_destroy_registry('https://lkexpertiza.spb.ru/Reestr/ReestrUvedPlanData', 'Уведомление о сносе', data)
    
    

    
   

