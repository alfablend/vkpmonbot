import vkp_app.vkp_bus as bus #Шина обмена данными

import vkp_app.vkp_settings
import vkp_app.vkp_db as db #База данных
from  vkp_app.vkp_logging import log #Подключение модуля вывода сообщений
from vkp_app.vkp_docx import getdocx

from bs4 import BeautifulSoup  
from time import sleep
from random import randint
import datetime
import requests


cookies = {
    'Kodeks': '1721005753',
    'KodeksData': 'XzE3NjIwMzk2OF8xNzkzMjA1',
    }

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Sec-GPC': '1',
    'Priority': 'u=0, i',
}

    
        
def scrapepage(pagenum):
    global bus
    log ('Запрашиваем страницу антикоррупц. экспертиз № %s' % (str(pagenum)), type_='info')
    link='https://www.gov.spb.ru/norm_baza/antikorrupcionnaya-ekspertiza-i-obshestvennoe-obsuzhdenie-proektov-nor/antikorrupcionnaya-ekspertiza-proektov-normativnyh-pravovyh-aktov/?page=%s' % (str(pagenum))
    response = requests.get(link,
    cookies=cookies,
    headers=headers,).text
    soup = BeautifulSoup(response, "lxml")
    eventtypesall = soup.find_all('a')
    log ("Список из %s экспертиз получен. Начинаем загрузку экспертиз"%(len(eventtypesall)), type_='info')
    sleep(1)
        
    count=1
    for i in eventtypesall:
        if bus.stop==True: #Обнаружен флаг остановки
            log('Обнаружен флаг остановки в модуле Антикор', type_='info')
            raise bus.UserStopError()
        if 'docx' in i['href']:
            link="https://www.gov.spb.ru" + i['href']
            count+=1
            #Проверяем, был ли уже загружен документ в архив (тогда пропускаем его, возвращаемся в начало цикла)
            if db.indb(link): 
                log ("Документ по ссылке " + link + "уже есть в архиве, пропускаем его", type_='info')
                continue
            else: #Иначе продолжаем работу  
                text = getdocx(link, cookies, headers)
                log ("Получен документ:\n", text[:1000] , '<...>')
               
                #Добавляем в архив документ
                
                db.todb('antikor', link, text)
                    
                sleep(randint(3,5))  
      
#Просматриваем две страницы    
def start_antikor():  
    for i in range (1, 2):
        scrapepage(i)










