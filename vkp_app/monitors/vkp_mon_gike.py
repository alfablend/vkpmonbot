
import vkp_app.vkp_bus as bus #Шина обмена данными
import vkp_app.vkp_settings
import vkp_app.vkp_db as db #База данных
from  vkp_app.vkp_logging import log #Подключение модуля вывода сообщений
import vkp_app.vkp_extract #Обработка PDF и подготовка миниатюр для ГИКЭ
import vkp_app.vkp_telegram

import requests
from bs4 import BeautifulSoup  
from time import sleep
from random import randint
from tqdm import tqdm
import datetime
import json

import re


import traceback
import logging

import os

from collections import OrderedDict




cookies = {
    
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
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

mkrf_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Referer': 'https://culture.gov.ru/documents/',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Sec-GPC': '1',
    'Priority': 'u=0, i',
}


mkrf_params = {
    'DOCS[KEYWORDS]': 'санкт-',
    'DOCS[VIEW_DOCUMENTS]': '',
    'DOCS[AUTHORITY]': '',
    'DOCS[TYPE_DOCUMENTS]': '',
    'DOCS[DATE_1]': '',
    'DOCS[DATE_2]': '',
    'DOCS[NUMBER]': '',
}



#https://sky.pro/media/udalenie-soderzhimogo-papki-v-python/

def start_gike():
   
    ##НАЧАЛО БЛОКА ДЛЯ ОТЛАДКИ ПО ВАРИАНТУ С ГОТОВОЙ ССЫЛКОЙ (ОБЫЧНО ДОЛЖЕН БЫТЬ ЗАКОММЕНТИРОВАН)
    #ЗАГРУЗКА ЭКСПЕРТИЗЫ БУДЕТ ВЫПОЛНЕНА ПО ЗАДАННОЙ В ЭТОМ БЛОКЕ ССЫЛКЕ, РЕЗУЛЬТАТ ОТПРАВЛЕН ТОЛЬКО ОДНОМУ ПОЛЬЗОВАТЕЛЮ
    # print('РЕЖИМ ОТЛАДКИ С ГОТОВОЙ ССЫЛКОЙ')
    # link='https://kgiop.gov.spb.ru/media/uploads/userfiles/2024/12/19/1_fi3f3V2.pdf'
    # link_caption='земельного участка по адресу: Санкт-Петербург, город Колпино, Загородная улица, участок 72 (восточнее дома 35 литера А по Загородной улице) (кадастровый номер: 78:37:1722003:5)'
    # img, data=vkp_app.vkp_extract.getgike (link, cookies=cookies, headers=headers, short_link='disk.yandex.ru')    
    # rgb = Image.fromarray(img)
    # caption = text_shorter (data, link, link_caption) 
    # unique_filename='cafe1fe8-d12f-4275-9cb1-272912f5e4d6.jpg'
    # markup = telebot.types.InlineKeyboardMarkup()
    # button1 = telebot.types.InlineKeyboardButton(text='Узнать подробности и загрузить', callback_data='describe:{}'.format(unique_filename))
    # markup.row(button1)
    # bot.send_photo('Код пользователя', rgb, 'ОТЛАДКА ' + caption, reply_markup=markup, parse_mode="html")
    
    # return
    ##КОНЕЦ БЛОКА ДЛЯ ОТЛАДКИ
    
    global bus
    log('ВКП ГИКЭ', type_='info')
    
    
    #Сначала работаем с экспертизами КГИОП
    log('Запрашиваем страницу экспертиз', type_='info')
        
        
    #Получаем нынешний год для подстановки в ссылку
    dt = datetime.datetime.now()
    year_only = dt.year
        
    response = requests.get('https://kgiop.gov.spb.ru/deyatelnost/zaklyucheniya-gosudarstvennyh-istoriko-kulturnyh-ekspertiz/gosudarstvennye-istoriko-kulturnye-ekspertizy-za-{year_only}-g/'.format(year_only=year_only),
    cookies=cookies,
    headers=headers, verify=False)
    response.raise_for_status()
    response=response.text
    soup = BeautifulSoup(response, "lxml")
    eventtypesall = soup.find_all('a')
    log("Список из %s ссылок получен. Начинаем загрузку экспертиз"%(len(eventtypesall)), type_="info")
    sleep(1)
    index=0
    for i in eventtypesall: 
        link_capt='' #Титул экспертизы
        if bus.stop==True: #Обнаружен флаг остановки
            log('Обнаружен флаг остановки в модуле ГИКЕ', type_='info')
            raise bus.UserStopError()
        if "Срок рассмотрения обращений" in i.text in i.text:
            link_capt='Экспертиза ' + i.find_parent('td').find_previous_sibling('td').text + ' (часть составной экспертизы)'
            print('Взят заголовок ссылки сбоку: ', link_capt)
        if "Срок рассмотрения обращений" in i.text in i.text:
            link_capt='Экспертиза ' + i.find_parent('td').find_previous_sibling('td').text + ' (часть составной экспертизы)'
            print('Взят заголовок ссылки сбоку: ', link_capt)    
        if 'disk.yandex.ru' in i['href']: #если файл выложен на яндекс-диск
            index+=1
            if index > 19:
                break
            log ('Загружаем экспертизу № %s' % (str(index)), type_='info')
            log (i.text)
            apilink='https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=%s' % (i['href']) #Адрес страницы скачивания подставляется в поле ключа API для загрузки публичного файла https://github.com/sermelipharo/YandexDown/blob/main/yandown.py
            response_json=requests.get(apilink).json()
            link = response_json.get("href")
       		
            #Есть ли уже в архиве этот документ?
            if db.indb(i['href']): #Проверяем исходную ссылку, а не ссылку яндекса, поскольку последняя меняется 
                log ("Документ по ссылке " + link + "уже есть в архиве, пропускаем его", type_='info')
                continue
        
            log (link)
          
            
            img, data=vkp_app.vkp_extract.getgike (link, cookies=cookies, headers=headers, short_link=i['href']) 
            if link_capt=='': link_capt='Экспертиза ' + i.text
            
            
            txt='__Выдержки для предварительного просмотра__. '
            for el in data:
                txt=txt+ el + ':' + '\n\n' + data[el]
            if data['Проект предусматривает']!='':
                data4telegram=OrderedDict([('Пытаемся определить, что предусматривается проектом', data['Проект предусматривает'])])
            elif data['По объекту']!='': data4telegram=OrderedDict([('Пытаемся определить, что предусматривается проектом', data['По объекту'])])   
            else: data4telegram=OrderedDict()               

            #Если экспертиза состоит из нескольких файлов, ее названия нет в тексте ссылки
            if "Срок рассмотрения обращений" in i.text and "Часть 1" in i.text:
                txt= 'Составная экспертиза. Часть 1.' +'\n\n' + txt
            elif "Срок рассмотрения обращений" in i.text and "Часть 2" in i.text:
                txt= 'Составная экспертиза. Часть 2.' +'\n\n' + txt    
            else:         
                txt= 'Экспертиза ' + i.text[:225] +'...\n\n' + txt
          
            
            txt=i['href'] + '\n\n' + txt 
            
            
            unique_filename=db.todb('gike', i['href'], txt, img) #Записываем исходную ссылку, а не ссылку яндекса, поскольку последняя меняется 
            mon_type="gike"
            vkp_app.vkp_telegram.to_telegram(mon_type, img, i['href'], link_capt, data4telegram, unique_filename)
           
            print(txt)
            #print('Отправляем в телеграм')
            #vkp_app.vkp_telegram.send_photo("-1002424968506", "temp_thumbnail.jpg", image_caption=txt[:1024])
            
            print('Ожидание следующего запроса к сайту')
            sleep(randint(5,10))
            
                 
        elif '/media/uploads/userfiles/' in i['href']: #если файл выложен на сайте кгиоп
            index+=1
            if index > 19:
                break
            log ('Загружаем экспертизу № %s' % (str(index)), type_='info')
            link="https://kgiop.gov.spb.ru" + i['href']
        
            #Есть ли уже в архиве этот документ?
            if db.indb(link): 
                log ("Документ по ссылке " + link + "уже есть в архиве, пропускаем его", type_='info')
                continue
        
            log (link)
            #input()
            img, data=vkp_app.vkp_extract.getgike (link, cookies=cookies, headers=headers) 
                        
            txt='__Выдержки для предварительного просмотра__.'
            for el in data:
                txt=txt+ el + ':' + '\n\n' + data[el]
            
            
            if data['Проект предусматривает']!='':
                data4telegram=OrderedDict([('Пытаемся определить, что предусматривается проектом', data['Проект предусматривает'])])
            elif data['По объекту']!='': data4telegram=OrderedDict([('Пытаемся определить, что предусматривается проектом', data['По объекту'])])   
            else: data4telegram=OrderedDict()       
            
            
            
            #Если экспертиза состоит из нескольких файлов, ее названия нет в тексте ссылки
            if "Срок рассмотрения обращений" in i.text and "Часть 1" in i.text:
                txt= 'Составная экспертиза. Часть 1.' +'\n\n' + txt
            elif "Срок рассмотрения обращений" in i.text and "Часть 2" in i.text:
                txt= 'Составная экспертиза. Часть 2.' +'\n\n' + txt    
            else:         
                txt= 'Экспертиза ' + i.text[:200] +'...\n\n' + txt
            
            
            txt= link + '\n\n' + txt 
            
            log (txt)
            #unique_filename='' #заглушка
            unique_filename=db.todb('gike', link, txt, img)
            if link_capt=='': link_capt= 'Экспертиза ' + i.text
            mon_type="gike"
            vkp_app.vkp_telegram.to_telegram(mon_type, img, link, link_capt, data4telegram, unique_filename)



            print('Ожидание следующего запроса к сайту')
            sleep(randint(5,10))
            
    #Теперь занимаемся экспертизами Минкульта        
    
    print ('Начинаем обработку историко-культурных экспертиз на сайте Минкульта')
    
    response = requests.get('https://culture.gov.ru/documents/', params=mkrf_params, headers=mkrf_headers)

    response.raise_for_status()

    soup = BeautifulSoup(response.content, "lxml")
    
    sleep(2)
    index=0
    
    eventtypesall = soup.find_all('a')
    print("Список из %s ссылок получен. Начинаем загрузку экспертиз"%(len(eventtypesall)))

    for i in eventtypesall: 
        if "Акт" in i.text and "государственной историко-культурной экспертизы" in i.text and not 'водка предложений' in i.text:
            index+=1
            print ('Загружаем экспертизу № %s' % (str(index)))
            #print(i.text)
            link="https://culture.gov.ru" + i['href']
            if db.indb(link): #Проверяем, есть ли в базе
                print ("Документ по ссылке " + link + "уже есть в архиве, пропускаем его")
                continue
            
            #Загружаем промежуточную страницу
            response = requests.get(link, params=mkrf_params, headers=mkrf_headers)
            soup2=BeautifulSoup(response.content, "lxml")
            eventtypesall2 = soup2.find_all('a')
            for j in  eventtypesall2:
                if 'pdf' in j['href'] and j.findChild().text == 'скачать документ':
                    link2 = "https://culture.gov.ru" + j['href']
                    print (link2)
            sleep(2)
            img, data=vkp_app.vkp_extract.getgike (link2, cookies=cookies, headers=mkrf_headers) 
            
            txt=''
            for el in data:
                txt=txt+ el + ':' + '\n\n' + data[el] + '\n\n'
            txt= link + '\n\n' + txt 
            
            if data['Проект предусматривает']!='':
                data4telegram=OrderedDict([('Пытаемся определить, что предусматривается проектом', data['Проект предусматривает'])])
            elif data['По объекту']!='': data4telegram=OrderedDict([('Пытаемся определить, что предусматривается проектом', data['По объекту'])])   
            else: data4telegram=OrderedDict()          

            print(txt)
            unique_filename=db.todb('gike', link, txt, img)
            link_capt=i.text
            mon_type="gike"
            vkp_app.vkp_telegram.to_telegram(mon_type, img, link, link_capt, data4telegram, unique_filename)
            print('Ожидание следующего запроса к сайту')
            sleep(randint(5,10))
