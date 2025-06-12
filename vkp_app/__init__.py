#Модуль инициализации

import traceback
import logging, logging.config
import sys

#Уровень логирования устанавливается до импортирования модулей мониторов, поскольку библиотека rosreestr2coord,
#которая используется в мониторе vkp_mon_gasn для преобразования кадастровых номеров в координаты, пытается его 
#устанавливать по-своему, и иначе это влияет на весь проект
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


from  vkp_app.vkp_logging import log #Подключение модуля вывода сообщений
import vkp_app.vkp_settings #Подключение модуля настроек
import vkp_app.vkp_db as db #Подключение модуля базы данных
#import vkp_app.vkp_telegram

#Подключение мониторов
import vkp_app.monitors.vkp_mon_gasn
import vkp_app.monitors.vkp_mon_egrz
import vkp_app.monitors.vkp_mon_gradplan
import vkp_app.monitors.vkp_mon_ago
import vkp_app.monitors.vkp_mon_gike
import vkp_app.monitors.vkp_mon_antikor
import vkp_app.monitors.vkp_mon_slush



import pandas as pd

import os # для поддержки перезапуска

from tqdm import tqdm

import json

import datetime

from time import sleep

#Подключение Фласк
from flask import Flask, render_template, redirect, url_for, send_file

#Подключение многопоточности
import threading

#Шина обмена статусом между фронтендом и бэкэндом
import vkp_app.vkp_bus 


'''
root = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
root.addHandler(handler)
'''





#Все мониторы включены при запуске
mon_list=[vkp_app.monitors.vkp_mon_gike.start_gike,
vkp_app.monitors.vkp_mon_gradplan.start_gradplan, 
vkp_app.monitors.vkp_mon_ago.start_ago,
vkp_app.monitors.vkp_mon_gasn.start_gasn,
vkp_app.monitors.vkp_mon_egrz.start_egrz,
vkp_app.monitors.vkp_mon_antikor.start_antikor,
vkp_app.monitors.vkp_mon_slush.start_slush,
]

log (vkp_app.vkp_settings.welcome, 'версия', vkp_app.vkp_settings.ver, type_='info') #Вывод строки приветствия

host_name = "0.0.0.0"
port = 23336
app = Flask(__name__)
status = 1

#Получение статуса
#https://stackoverflow.com/questions/24251898/flask-app-update-progress-bar-while-function-runs
@app.route('/status', methods=['GET'])
def getStatus():
  statusList = {'status':status}
  return json.dumps(statusList)


#https://stackoverflow.com/questions/8637153/how-to-return-images-in-flask-response
#Загрузка картинок
@app.route('/get_image/<filename>')
def get_image(filename):
    if 'nan' in filename: return
    filename = 'database\\' + filename.replace(r"/","\\").replace(r"&","\\")
    app.logger.info('Имя файла' + filename)
    return send_file(filename, mimetype='image/gif')

@app.route('/repair')
def repair():
    log('Получена команда исправления БД', type_='info')
    db.db_repair()
    return index()

#Перезапуск наблюдения по запросу (заодно перезагружается и фласк)
#В дальнейшем, нужно подключить Celery и разделить логику веб-сервера и сборщика новостей
#Либо использовать asyncio для асинхронности

time_of_coverage='0'
@app.route('/restart')
def restart():
    global time_of_coverage
    global mon_list
    
    #Перезапускаем все мониторы
    mon_list=[vkp_app.monitors.vkp_mon_gike.start_gike,
    vkp_app.monitors.vkp_mon_gasn.start_gasn,
    vkp_app.monitors.vkp_mon_gradplan.start_gradplan,
    vkp_app.monitors.vkp_mon_ago.start_ago,
    
    vkp_app.monitors.vkp_mon_egrz.start_egrz,
    vkp_app.monitors.vkp_mon_antikor.start_antikor,
    vkp_app.monitors.vkp_mon_slush.start_slush,
    ]
    
    log('Получена команда перезапуска сбора информации', type_='info')
    vkp_app.vkp_bus.stop=True 
    vkp_app.vkp_bus.auto_run=False
    vkp_app.vkp_bus.finish=False
    return redirect(url_for("index")) #Перебрасываем на главную страницу с вызовом ее функции


#Если только ГАСН
@app.route('/only_gasn')
def only_gasn():
    global time_of_coverage
    global mon_list
    
    #Перезапускаем (или запускаем) только гикэ, остальные мониторы останавливаем
    mon_list=[vkp_app.monitors.vkp_mon_gasn.start_gasn]
    
    log('Получена команда перезапуска сбора только ГАСН', type_='info')
    vkp_app.vkp_bus.stop=True 
    vkp_app.vkp_bus.auto_run=False
    vkp_app.vkp_bus.finish=False
    return redirect(url_for("index")) #Перебрасываем на главную страницу с вызовом ее функции



#Если нужно проверить только историко-культурные экспертизы и ГАСН
@app.route('/only_gike')
def only_gike():
    global time_of_coverage
    global mon_list
    
    #Перезапускаем (или запускаем) только гикэ, остальные мониторы останавливаем
    mon_list=[vkp_app.monitors.vkp_mon_gasn.start_gasn, vkp_app.monitors.vkp_mon_gradplan.start_gradplan,
    vkp_app.monitors.vkp_mon_ago.start_ago,
    vkp_app.monitors.vkp_mon_gike.start_gike]
    
    log('Получена команда перезапуска сбора только ГАСН и ГИКЭ, другие мониторы отключены', type_='info')
    vkp_app.vkp_bus.stop=True 
    vkp_app.vkp_bus.auto_run=False
    vkp_app.vkp_bus.finish=False
    return redirect(url_for("index")) #Перебрасываем на главную страницу с вызовом ее функции



@app.route('/')
def index():
    global stop
    global finish   
    global mon_list
    #Читаем базу данных, предварительно сортируя её по времени добавления записей
    db.df_merged['date'] = pd.to_datetime(db.df_merged['date'], format='%Y-%m-%d %H:%M:%S.%f')
    db.df_merged = db.df_merged.sort_values(by='date')
    
    posts=db.df_merged.iloc[::-1].to_dict('records') 
    
    #Разбиваем на абзацы, чтобы в шаблоне заменить на <br>
    #https://stackoverflow.com/questions/12244057/any-way-to-add-a-new-line-from-a-string-with-the-n-character-in-flask
    for post in posts:
        post['text'] = post['text'].split('\n')
    
    return render_template("index.html",
        #title = db.df['type'].values.tolist(),
        posts = posts, count_of_posts=len(db.df_merged), time_of_coverage=time_of_coverage, total_mons=len(mon_list), finish=vkp_app.vkp_bus.finish)


    
#Запуск Фласк
threading.Thread(target=lambda: app.run(host=host_name, port=port, debug=True, use_reloader=False)).start()
#Запуск Телебота
#threading.Thread(target=vkp_telegram.start_bot).start()

#Запуск мониторов

#В списке мониторов функции даны без скобок, чтобы они не запустились сразу при перечислении в этом списке
'''mon_list=[vkp_app.monitors.vkp_mon_gike.start_gike,
    vkp_app.monitors.vkp_mon_gasn.start_gasn,
    vkp_app.monitors.vkp_mon_egrz.start_egrz,
    vkp_app.monitors.vkp_mon_antikor.start_antikor,
    vkp_app.monitors.vkp_mon_slush.start_slush,
    ]
'''

def start_all_mons():
    global status
    while True:
        sleep(1)  #Чтобы бесконечный цикл не грузил процессор
        
        if vkp_app.vkp_bus.auto_run==False \
        and vkp_app.vkp_bus.finish==False: #Если не нажимали кнопку "Обновить", мониторы сами не запускаются
            pbar = tqdm(total=len(mon_list), desc='Общий ход:')
            for mon in mon_list: #Перебираем список мониторов
                if vkp_app.vkp_bus.stop==True:
                    vkp_app.vkp_bus.stop=False
                    break
                try:
                    print(str(datetime.datetime.now()) + ' Запускаем МОНИТОР' )
                    mon() #Если нет флага остановки, собираем информацию
                    print(str(datetime.datetime.now()) + ' Выполнение монитора завершено' )
                    status +=1
                    pbar.update()
                    #Наличие флага также проверяется внутри мониторов
                except vkp_app.vkp_bus.UserStopError:
                    log('Перезапускаем наблюдение', type_='info')
                    break #Рекурсия
                except Exception as e:
                    #https://stackoverflow.com/questions/4990718/how-can-i-write-a-try-except-block-that-catches-all-exceptions
                    logging.error(traceback.format_exc())
                    continue
                vkp_app.vkp_bus.finish=True            
        #log('Обнаружен флаг остановки в цикле вызова мониторов', type_='info')
        vkp_app.vkp_bus.stop=False
        

        time_of_coverage=datetime.datetime.now() 

#Запускаем мониторы
threading.Thread(start_all_mons())



