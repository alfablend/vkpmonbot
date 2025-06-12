#ВКП общественные обсуждения КГА

import vkp_app.vkp_bus as bus #Шина обмена данными
import vkp_app.vkp_settings
import vkp_app.vkp_db as db #База данных
from  vkp_app.vkp_logging import log #Подключение модуля вывода сообщений
from vkp_app.vkp_pdf import getpdf
from vkp_app.vkp_docx import getdocx


import requests
from bs4 import BeautifulSoup  
import os
from time import sleep
from random import randint
from tqdm import tqdm


cookies = {'eSi_state':'on'}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Accept': '*/*',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://kgainfo.spb.ru',
    'Connection': 'keep-alive',
    'Referer': 'https://kgainfo.spb.ru/reglamenti/publichnye-slushaniya/',
    # 'Cookie': 'eSi_state=on',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
}

def getnewpage (link, header, el_date):
    r=requests.get(link, cookies=cookies, headers=headers, verify=False).text
    soup2 = BeautifulSoup(r, "lxml")
    #header=soup2.find('h1', class_='entry-title')
    print (header)
    content=soup2.find('div', class_='entry-content')

    pagebuffer='' #готовим буфер
    links = content.find_all('a') #Ищем ссылки в блоке документов
    for i in links:
        #Есть ли уже в архиве этот документ?
        if db.indb(link): 
            log ("Документ по ссылке " + link + "уже есть в архиве, пропускаем его", type_='info')
            continue
        if 'docx' in i['href']: #обработка вордовских документов
            log ('Загружаем документ с заголовком: ', i.text, type_='info')
            txt=getdocx (i['href'], cookies=cookies, headers=headers)
            sleep(randint(10,15))
            db.todb('slush', link, txt)
            log(txt)

        if 'pdf' in i['href']: #обработка pdf файлов
            if not i.text: continue
            log ('Загружаем документ с заголовком: ', i.text, type_='info')
            txt=getpdf (i['href'], cookies=cookies, headers=headers)
            sleep(randint(10,15))
            db.todb('slush', link, txt)
            log(txt)
        
     
    sleep(randint(2,3))   


data = {'page': '1', 'tag': 'slushaniya'}


def start_slush():
    global bus
    log('Запрашиваем страницу слушаний', type_='info')

    response = requests.post('https://kgainfo.spb.ru/wp-content/work_elements/inc/slush_in_list1.php',
        data=data,
        cookies=cookies,
        headers=headers, verify=False).text
    soup = BeautifulSoup(response, "lxml")
    eventtypesall = soup.find_all('a', class_='news-link')
    log(("Список из %s слушаний получен. Начинаем загрузку слушания"%(len(eventtypesall))), type_="info")
    sleep(1)


    index=0
    for i in eventtypesall:
        if bus.stop==True: #Обнаружен флаг остановки
            log('Обнаружен флаг остановки в модуле Слуш', type_='info')
            raise bus.UserStopError()
        index+=1
        if index > 19:
            break
        log(("Загружаем слушание № %s"%(str(index))), type_="info")
        link=i['href']
        
        log (link)
        el_date=i.find_previous_sibling('span').text
        getnewpage (link, i.text, el_date)  
      