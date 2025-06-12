
import json

import telebot
from telebot import types

import traceback
import logging

import pandas as pd 

with open('token.txt', 'r') as f:
    token=f.read()

API_TOKEN = token
telebot.logger.setLevel(logging.DEBUG)
bot = telebot.TeleBot(API_TOKEN)


#Если строка длиннее заданного числа знаков, обрезаем целиком последнее слово
#Функция скопирована из модуля vkp_extract
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

# Handle '/start' and '/help'

@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):


    button_gasn = types.InlineKeyboardButton('Подписаться на РНС', callback_data='gasn') 
    button_gike = types.InlineKeyboardButton('Подписаться на ГИКЭ', callback_data='gike') 
    
    global users
   
    for user in users:
        if user['user_id'] == message.from_user.id and 'gike' in user['type']:
            button_gike = types.InlineKeyboardButton('Отписаться от ГИКЭ', callback_data='gike_uns')
        if user['user_id'] == message.from_user.id and 'gasn' in user['type']:
            button_gasn = types.InlineKeyboardButton('Отписаться от РНС', callback_data='gasn_uns') 
       
    keyboard = types.InlineKeyboardMarkup()    
    

  
    keyboard.add(button_gike)
    keyboard.add(button_gasn)
    bot.reply_to(message, """\
Здравствуйте!
Это телеграм-бот наблюдения за разрешениями на строительство и на ввод в эксплуатацию (сокращённо — РНС) и за государственными историко-культурными экспертизами (сокращённо — ГИКЭ) в Петербурге.\n\nПожалуйста, выберите действие.
""", reply_markup=keyboard)





@bot.callback_query_handler(func=lambda call: True)
def answer(call):
    global users
    
    #Подробности ГИКЭ по запросу
    if 'describe:' in call.data:
        uf=call.data.split('describe:')[1]
        df=pd.read_csv('vkp_app\\database\\gike.csv', header=0, on_bad_lines="skip", engine='python')
        #text='Пробный текст'
        text = df.loc[df['unique_filename'] == uf].text.item()
        text = string_shorter (text, 4000) [:4000]
        bot.send_message(call.message.chat.id, text)
        
        service_message='ОТЛАДКА. Пользователь ' + str(call.from_user.username) + ' запросил выдержки из экспертизы'
        bot.send_message(323157743, service_message)
        
    if call.data == 'gike': #Хотим подписаться на ГИКЭ
        already_subscribed=False
        for user in users:
            if user['user_id'] == call.from_user.id and 'gike' in user['type']: #Уже подписаны на ГИКЭ
                bot.send_message(call.message.chat.id, 'Вы уже подписаны на ГИКЭ')
                already_subscribed=True
            if user['user_id'] == call.from_user.id and not 'gike' in user['type']: #Подписаны, но не на ГИКЭ
                user['type'].append('gike')
                bot.send_message(call.message.chat.id, 'Вы успешно подписаны на историко-культурные экспертизы. Будем присылать их вам по мере появления. Управлять подпиской можно через меню бота.')
                already_subscribed=True    
        if already_subscribed==False: #Если еще не подписаны, подписываем
            to_json = {'user_id': call.from_user.id, 'username': call.from_user.username, 'type': ['gike']}
            users.append(to_json)
            bot.send_message(call.message.chat.id, 'Вы успешно подписаны на историко-культурные экспертизы. Будем присылать их вам по мере появления. Управлять подпиской можно через меню бота.')
            #Отправляем служебное уведомление
            service_message='ОТЛАДКА. Пользователь @' + str(call.from_user.username) + ' подписался на ГИКЭ'
            bot.send_message(323157743, service_message)
        with open('users_tg.json', 'w') as f:
            f.write(json.dumps(users)) 
    if call.data == 'gike_uns': #Хотим отписаться от ГИКЭ
        was_subscribed=False
        updated_users=[] #Готовим пустой список, чтобы перенести туда всех, кроме удаляемого
        for user in users:
            if user['user_id'] == call.from_user.id and 'gike' in user['type']: #Если желающий отписаться от ГИКЭ был на них подписан
                was_subscribed=True
                user['type'].remove('gike')
                if len (user['type']) > 0: updated_users.append(user) # Если пользователь больше ни на что не подписан, удаляем его из базы
            else:
                updated_users.append(user) #Всех стальных оставляем в базе
        if was_subscribed==True: #пользователь был подписан, его отписали, значит, нужно обновить файл пользователей        
            bot.send_message(call.message.chat.id, 'Вы успешно отписаны от историко-культурных экспертиз')
            #Отправляем служебное уведомление
            service_message='ОТЛАДКА. Пользователь @' + str(call.from_user.username) + ' отписался от ГИКЭ'
            bot.send_message(323157743, service_message)
        else:
             bot.send_message(call.message.chat.id, 'Вы не были подписаны на историко-культурные экспертизы, не можем вас отписать')
        with open('users_tg.json', 'w') as f:
            f.write(json.dumps(updated_users)) 
            users=updated_users #обновляем загруженную базу
            
    if call.data == 'gasn': #Хотим подписаться на ГИКЭ
        already_subscribed=False
        for user in users:
            if user['user_id'] == call.from_user.id and 'gasn' in user['type']: #Уже подписаны на ГИКЭ
                bot.send_message(call.message.chat.id, 'Вы уже подписаны на разрешения на строительство')
                already_subscribed=True
            if user['user_id'] == call.from_user.id and not 'gasn' in user['type']: #Подписаны, но не на ГИКЭ
                user['type'].append('gasn')
                bot.send_message(call.message.chat.id, 'Вы успешно подписаны на разрешения на строительство. Будем присылать их вам по мере появления. Управлять подпиской можно через меню бота.')
                already_subscribed=True    
        if already_subscribed==False: #Если еще не подписаны, подписываем
            to_json = {'user_id': call.from_user.id, 'username': call.from_user.username, 'type': ['gasn']}
            users.append(to_json)
            bot.send_message(call.message.chat.id, 'Вы успешно подписаны на разрешения на строительство. Будем присылать их вам по мере появления. Управлять подпиской можно через меню бота.')
            #Отправляем служебное уведомление
            service_message='ОТЛАДКА. Пользователь @' + str(call.from_user.username) + ' подписался на разрешения на строительство'
            bot.send_message(323157743, service_message)
        with open('users_tg.json', 'w') as f:
            f.write(json.dumps(users)) 
    if call.data == 'gasn_uns': #Хотим отписаться от разрешений на строительство
        was_subscribed=False
        updated_users=[] #Готовим пустой список, чтобы перенести туда всех, кроме удаляемого
        for user in users:
            if user['user_id'] == call.from_user.id and 'gasn' in user['type']: #Если желающий отписаться от ГИКЭ был на них подписан
                was_subscribed=True
                user['type'].remove('gasn')
                if len (user['type']) > 0: updated_users.append(user) # Если пользователь больше ни на что не подписан, удаляем его из базы
            else:
                updated_users.append(user) #Всех стальных оставляем в базе
        if was_subscribed==True: #пользователь был подписан, его отписали, значит, нужно обновить файл пользователей        
            bot.send_message(call.message.chat.id, 'Вы успешно отписаны от разрешений на строительство')
            #Отправляем служебное уведомление
            service_message='ОТЛАДКА. Пользователь @' + str(call.from_user.username) + ' отписался от разрешений на строительство'
            bot.send_message(323157743, service_message)
        else:
             bot.send_message(call.message.chat.id, 'Вы не были подписаны на разрешения на строительство, не можем вас отписать')
        with open('users_tg.json', 'w') as f:
            f.write(json.dumps(updated_users)) 
            users=updated_users #обновляем загруженную базу
       
       
try:
    with open('users_tg.json') as f:
        users = json.load(f)
        
        print ('База пользователей телеграм-бота загружена')
                                 
except FileNotFoundError:
    print ('Файл базы пользователей телеграм-бота не найден. База будет создана.')
    users=[]
    
    

print('Телеграм-бот запущен')
bot.infinity_polling()    
