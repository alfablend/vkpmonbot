#Модуль отправки в телеграм
#Также он готовит текст к отправке, сокращая его

import vkp_app.vkp_settings as settings
from vkp_app.vkp_plotmap import plotmap

import re, json

import cv2
from PIL import Image

from time import sleep

import traceback, logging

import telebot
from telebot.apihelper import ApiTelegramException

import copy
from collections import OrderedDict
import numpy as np

token = settings.TOKEN

try:    
    bot = telebot.TeleBot(token=token)
except: 
    print('Не указан ключ для телеграм-бота, бот не инициализирован')

#Если строка длиннее заданного числа знаков, обрезаем целиком последнее слово
def string_shorter(txt, length): 
    try:
        if len(txt)>length: 
            #Делим предложение по пробелам
            if len(txt[:length].split())>1: #Если фраза длиннее одного слова
                txt=txt[:length].split()[:-1]
            else: return txt[:length-3]+'...' #Иначе возвращаем исходное слово, обрезанное по предельной длине
            txt = ' '.join([str(elem) for elem in txt])
            if txt[-1].isalpha() or txt[-1].isdigit(): pass
            else: txt = txt.replace(txt[-1], '') 
            if txt[0].isalpha() or txt[0].isdigit(): pass
            else: txt = txt.replace(txt[0], '')
            txt=txt.strip()
            txt=txt+'...'    
        return txt    
    except IndexError: 
        print ('Произошла ошибка при сокращении строки', txt)    
        logging.error(traceback.format_exc())
    
def text_shorter (link, link_caption, data=[]):  
    
    link_caption = re.sub(r'(\W+)(?<![\., \\/№\-\(\)\-])', ' ', link_caption) #Убираем спецсимволы
    data_new=OrderedDict()
    for key, value in data.items():
        data_new[key] = re.sub(r'(\W+)(?<![\., \\/№\-\(\)\-])', ' ', value) #Убираем спецсимволы
    data=data_new    
           
    def is_text_short_enough ():
        text='<b>' + link_caption + '</b>\n\n'
        for key, value in data.items():
            text = text + '<b>' + key + ':</b> ' + value + '\n\n'
        final=text + link + '\n\n@vkpgikebot'
        if len(final)>1000: return False
        else: return final
    
    count=0
    data_new=OrderedDict()
    while not is_text_short_enough(): 
        for key, value in reversed(data.items()):
            shorted=string_shorter(value, len(value)-1)
            if len (shorted) > 100:
                data_new.update({key:shorted})
            count+=1    
            if count == len(data): 
                link_caption=string_shorter(link_caption, len(link_caption)-1) 
        data=data_new    
    return is_text_short_enough()
  

def to_telegram(mon_type, img, link, link_caption, data=[], unique_filename=''):
    print('*** ТИП ОТПРАВКИ ***', mon_type) 
    if isinstance(img, (np.ndarray) ):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb = Image.fromarray(img)
    
    #Готовим текст сообщения (подпись к фото)
    if data!=[]:
        caption = text_shorter (link, link_caption, data) 
    else:
        caption = text_shorter (link, link_caption) 
    
    
    updated_users=[] #Готовим пустой список, чтобы перенести туда всех, кроме тех, кто заблокировал бота
    remove_users=[] #Здесь будем хранить пользоователей, помеченных к удалению
    
    #Читаем базу пользователей для рассылки
    with open('users_tg.json', 'r+') as f:
        users = json.load(f)

    #Проверка режима отладки с отправкой только мне
    if vkp_app.vkp_settings.debug==True:
        print('РЕЖИМ ОТЛАДКИ В ТЕЛЕГРАМЕ, ОТПРАВКА ТОЛЬКО НА ID 323157743')
        users=[{"user_id": 323157743, "username": "alfablen", "type": ["gike", "gasn"]}]

    #Приступаем к рассылке
    print(users)
   
    for user in users:                  
        if mon_type in user['type']:                    
            print('Отправляем в телеграм пользователю ', user['user_id']) 
            try:
                # Send message
                markup = telebot.types.InlineKeyboardMarkup()
                button1 = telebot.types.InlineKeyboardButton(text='Подготовить выдержки', callback_data='describe:{}'.format(unique_filename))
                markup.row(button1)
                #Если есть ссылка на файл, отправляем с кнопкой "Подготовить выдержки" (актуально для ГИКЭ)
                if unique_filename!='' and isinstance(img, (np.ndarray) ):
                    bot.send_photo(user['user_id'], rgb, caption[:1000], reply_markup=markup, parse_mode="html")
                elif unique_filename=='' and isinstance(img, (np.ndarray) ):# Иначе отправляем без кнопки
                    bot.send_photo(user['user_id'], rgb, caption[:1000], parse_mode="html")
                elif unique_filename!='' and not isinstance(img, (np.ndarray) ):
                    bot.send_message(user['user_id'], caption[:1000], reply_markup=markup, parse_mode="html")    
                elif unique_filename=='' and not isinstance(img, (np.ndarray) ): 
                    bot.send_message(user['user_id'], caption[:1000], parse_mode="html")        
                sleep(0.2)
            except ApiTelegramException as e: #Ошибка отправки
                logging.error(traceback.format_exc())
                if e.description == "Forbidden: bot was blocked by the user": #Если пользователь заблокировал бота
                    remove_users.append(user) #Помечаем этого пользователя к удалению
                    service_message="ОТЛАДКА. Пользователь с id {} и именем {} заблокировал бота.".format(user['user_id'], user['username'])
                    print(service_message) 
                    bot.send_message(323157743, service_message)
                else: #В случае остальных ошибок нужно смотреть консоль
                    bot.send_message(323157743, 'ОТЛАДКА. Произошла ошибка рассылки в Телеграм в модуле ГАСН. Бот остановлен')
                    input() #Работа останавливается до нажатия клавиши
   
    #Заново читаем файл с базой пользователей, так как за время рассылки он мог быть изменён ботом, которой подписывает и отписывает пользователей
    #Занимаемся этим только если есть заблокировавшие пользователи
    if remove_users!=[]:
        with open('users_tg.json', 'r+') as f:   
            users = json.load(f)
            for user in users:
                if not user in remove_users:
                    updated_users.append(user)
            f.seek(0) #Возвращаемся в начало файла
            f.truncate(0) #Чистим файл
            f.seek(0) 
            f.write(json.dumps(updated_users))
            print('Файл пользователей обновлен')
            users=updated_users #На всякий случай обновляем загруженную базу            
