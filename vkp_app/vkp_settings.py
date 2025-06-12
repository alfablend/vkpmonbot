#Модуль глобальных настроек

ver = '0.1' #Версия программы
welcome = 'ВКП. Система наблюдения' #Приветственное сообщение
debug = False

with open('token.txt', 'r') as f:
    token=f.read()
_TOKEN = token