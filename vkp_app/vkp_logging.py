#Модуль вывода сообщений 

#Цвета вывода сообщений
class bcolors: 
    BREAK = '\033[0m' #Команда для сброса цвета на стандартный белый
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
#Функция вывода сообщений

def log (*text, type_='regular'):  
    if type_ == 'regular': #Обычный текст
        print (*text) #Распаковка кортежа аргументов и вывод его в терминал  
    if type_ == 'info': #Информационное сообщение
        print (bcolors.BOLD, *text, bcolors.BREAK) 
    if type_ == 'warning': #Ошибка
       print (bcolors.WARNING, *text, bcolors.BREAK) 
        
