#Модуль обмена данными о состоянии между фронтендом и бэкэндом

#Обработка исключения при остановке сбора информации нажатием кнопки на сайте
#Необходимо для прерывания потока из модулей обработки PDF и DOCX без оставления пустых ячеек
#https://sky.pro/wiki/python/ponimanie-i-ispolzovanie-klyuchevogo-slova-raise-v-python/
class UserStopError(Exception):
    def __init__(self):
        message = "Сбор информации остановлен пользователем"
        super().__init__(message)
    
stop=False #Флаг остановки сбора информации
finish=False #Флаг завершения сбора информации 
auto_run=True #Флаг первого запуска