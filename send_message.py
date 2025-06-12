#Модуль для рассылки сообщений по списку

import logging
import traceback
import telebot
from telebot.apihelper import ApiTelegramException
import json
from time import sleep


caption = '<b>НОВАЯ ФУНКЦИЯ</b> \n\n Теперь бот в пробном режиме умеет оповещать о разрешениях на строительство и на ввод в эксплуатацию в Петербурге, выданных Госстройнадзором. \n\n А для большей наглядности и удобства мы наносим стройплощадки (участки под строительство) на карту, которая рассылается вместе с сообщениями (как над этим текстом). \n\n Если вы хотите узнавать о новых стройках, нажмите на кнопку "Подписаться на разрешения на строительство" под этим сообщением. \n\n Управлять подписками также можно через меню бота \n\n @vkpgikebot'

with open('token.txt', 'r') as f:
    token=f.read()

bot = telebot.TeleBot(token=token)


with open('users_tg.json', 'r+') as f:
    users = json.load(f)
            
for user in users[0:0]:                  
    if user['type'] == 'gike':                    
     
        try:
            # Send message
            print('Отправляем в телеграм пользователю ', user['user_id']) 
            button1 = telebot.types.InlineKeyboardButton(text='Подписаться на разрешения на строительство и на ввод', callback_data='gasn')
            markup = telebot.types.InlineKeyboardMarkup()
            markup.row(button1)
            img=open('tempmap.jpg', 'rb')
            bot.send_photo(user['user_id'], img, caption[:1000], parse_mode="html", reply_markup=markup)
            sleep(5)
        except ApiTelegramException as e: #Ошибка отправки
            logging.error(traceback.format_exc())
            if e.description == "Forbidden: bot was blocked by the user":
                #remove_users.append(user)
                print("Пользователь {} заблокировал бота. Ему невозможно ничего отправить".format(user['user_id'])) 