#Модуль разбирает ПДФ для ГИКЭ и готовит файл миниатюр

import vkp_app.vkp_bus as bus 
import vkp_app.vkp_telegram

import requests

from pypdf import PdfReader
import re
from tqdm import tqdm
import ocrmypdf

extract_images = True

import itertools

import cv2
import qrcode

import os
import numpy as np

import shutil

import traceback
import logging

import datetime

from PIL import Image, ImageChops
import fitz

import random


#Если строка длиннее заданного числа знаков, обрезаем целиком последнее слово
  
    

def extract_data(txt):
    patterns={'Объект экспертизы': 'объекта? культурного наследия',
    'Собственник объекта':'(?<=.обственник)([\w|\W]{1,45})наследия',
    'По объекту':'по объекту:',
    'Адрес объекта':'по адресу', 
    'Проект предусматривает':'(?<=.роект)([\w|\W]{1,45})н?е? ?предусматрива.тс?я?',
    'Заключение экспертизы':'(?<=.ывод)([\w|\W]{1,4500})(?=заключение)',
    'Архитектурные решения':'(?i)Архитектурн.. решени.'}
    for pattern in patterns:
        try:
            indice = re.search(patterns[pattern], txt).span()[1] ## this prints starting and end indices
            patterns[pattern] = vkp_app.vkp_telegram.string_shorter(txt[indice:], 1000)
        except:
            logging.error(traceback.format_exc())
            patterns[pattern] = ''
    return(patterns)        

#Изменение размера с учетом соотношения сторон
#https://stackoverflow.com/questions/44720580/resize-image-to-maintain-aspect-ratio-in-python-opencv    
def resizeAndPad(img, size, padColor=0):

    h, w = img.shape[:2]
    sh, sw = size

    # interpolation method
    if h > sh or w > sw: # shrinking image
        interp = cv2.INTER_AREA
    else: # stretching image
        interp = cv2.INTER_CUBIC

    # aspect ratio of image
    aspect = w/h  # if on Python 2, you might need to cast as a float: float(w)/h

    # compute scaling and pad sizing
    if aspect > 1: # horizontal image
        new_w = sw
        new_h = np.round(new_w/aspect).astype(int)
        pad_vert = (sh-new_h)/2
        pad_top, pad_bot = np.floor(pad_vert).astype(int), np.ceil(pad_vert).astype(int)
        pad_left, pad_right = 0, 0
    elif aspect < 1: # vertical image
        new_h = sh
        new_w = np.round(new_h*aspect).astype(int)
        pad_horz = (sw-new_w)/2
        pad_left, pad_right = np.floor(pad_horz).astype(int), np.ceil(pad_horz).astype(int)
        pad_top, pad_bot = 0, 0
    else: # square image
        new_h, new_w = sh, sw
        pad_left, pad_right, pad_top, pad_bot = 0, 0, 0, 0

    # set pad color
    if len(img.shape) is 3 and not isinstance(padColor, (list, tuple, np.ndarray)): # color image but only one color provided
        padColor = [padColor]*3

    # scale and pad
    scaled_img = cv2.resize(img, (new_w, new_h), interpolation=interp)
    scaled_img = cv2.copyMakeBorder(scaled_img, pad_top, pad_bot, pad_left, pad_right, borderType=cv2.BORDER_CONSTANT, value=padColor)

    return scaled_img
    

def make_qr(link):
    qr = qrcode.QRCode(
        version=4,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=2,
        border=2,
        )
    qr.add_data(link)
    qr.make(fit=False)

    #Делаем QR-код и превращаем его в массив
    qr = np.array(qr.make_image(fill_color='green', back_color=(241, 241, 241)))
    #Устанавливаем цветовую схему BGR
    qr = cv2.cvtColor(qr, cv2.COLOR_RGB2BGR) 
    return qr
    
    
def make_thumbnails(fname, images_collection, data, link):
    
    
    #User defined variables
    
    margin = 20 #Margin between pictures in pixels
    w = 2 # Width of the matrix (nb of images)
    h = 3 # Height of the matrix (nb of images)
    n = w*h
 

    imgs2 = images_collection
    imgs=[]

    #Нужно привести картинки к одному размеру
    for image in tqdm(imgs2[1:], desc='сжатие'):
        try:
            height, width, channels = image.shape 
        except AttributeError:
            logging.error(traceback.format_exc())
            continue
        imgs.append(resizeAndPad(image, (250,250), 241))
        
    #Define the shape of the image to be replicated (all images should have the same shape)
    try:
        img_h, img_w, img_c = imgs[0].shape
    except IndexError:
        print ('Картинок не найдено')     
        img_h, img_w, img_c = (250, 250, 3) #Будет сделана матрица из пустых картинок
        #Отключено return False


    #Define the margins in x and y directions
    m_x = 567
    m_y = margin

    #Size of the full size image
    mat_x = img_w * w + m_x * (w - 1)
    mat_y = img_h * h + m_y * (h - 1)

    #Create a matrix of zeros of the right size and fill with 255 (so margins end up white)
    imgmatrix = np.zeros((mat_y, mat_x, img_c),np.uint8)
    imgmatrix[:]= 241

    #Prepare an iterable with the right dimensionsdimensionsdimensionsdimensionsdimensionsdimensionsdimensionsdimensions
    positions = itertools.product(range(h), range(w))

    for (y_i, x_i), img in tqdm(zip(positions, imgs), desc='совмещение'):
     
        x = x_i * (img_w + m_x)
        y = y_i * (img_h + m_y)
        imgmatrix[y:y+img_h, x:x+img_w, :] = img
        
    resized=imgmatrix
    #resized = cv2.resize(imgmatrix, (mat_x//3,mat_y//3), interpolation = cv2.INTER_AREA)
    
    #Накладываем надпись

    #https://ru.stackoverflow.com/questions/804541/%D0%A4%D0%BE%D0%BD-%D1%82%D0%B5%D0%BA%D1%81%D1%82%D0%B0-%D0%B2-opencv
    img=resized
    
    #Добавляем рамку
    img = cv2.copyMakeBorder(img, 40, 190, 25, 25, cv2.BORDER_CONSTANT, None, value = (241, 241, 241)) 
    
    #Вставляем страницу по центру
    x_offset=260
    y_offset=30
    img[y_offset:y_offset+images_collection[0].shape[0], x_offset:x_offset+images_collection[0].shape[1]] = images_collection[0]

    
    overlay = img.copy()
    font = cv2.FONT_HERSHEY_COMPLEX #поддерживает русские буквы
    fontScale = 0.5

    #БОЛЬШИЕ НАДПИСИ

    #Начинаем подготовку надписей
    
    labelAbout= link

  
    thickness = 1
    text_color = (9,53,46)
    
    text_width_labelAbout, text_height_labelAbout = cv2.getTextSize(labelAbout, font, fontScale, thickness)
   
    offset = 900 #смещение по вертикали зеленой полосы с надписью
    interspace = 40 #расстояние между строками
    
    height, width, channels = overlay.shape #получаем размеры холста
    
    text_coord_labelAbout = (width // 2 - text_width_labelAbout[0] // 2 ,text_height_labelAbout + offset)
    
    #Ссылка
    cv2.rectangle(overlay, 
                  (text_coord_labelAbout[0]-5, text_coord_labelAbout[1]-text_height_labelAbout*3),
                  (text_width_labelAbout[0]+text_coord_labelAbout[0]+5, text_coord_labelAbout[1]+text_height_labelAbout*2),
                  (0, 255, 0),
                  -1) #Код цвета для OpenCV нужно указывать в формате BGR, а не RGB
                  
   
                  
    opacity = 0.75
    cv2.addWeighted(overlay, opacity, img, 1 - opacity, 0, img)

    #Вводим большие надписи
    cv2.putText(img, labelAbout, text_coord_labelAbout, font, fontScale, text_color,thickness)
   

    #Готовим и вводим маленькие надписи (им не нужен фон)
    
    fontScale = 0.3
    thickness = 1
    
    labelDesclimer='Предпросмотр материалов общественных обсуждений.'.upper()
    text_width_labelDesclimer, text_height_labelDesclimer = cv2.getTextSize(labelDesclimer, font, fontScale, thickness)
    text_coord_labelDesclimer = (width // 2 - text_width_labelDesclimer[0] // 2, text_height_labelDesclimer + offset + text_height_labelAbout + interspace)
    cv2.putText(img, labelDesclimer, text_coord_labelDesclimer, font, fontScale, text_color,thickness)
    
    labelDesclimerLine2='Возможны ошибки, проверяйте информацию в первоисточнике.'.upper()
    text_width_labelDesclimerLine2, text_height_labelDesclimerLine2 = cv2.getTextSize(labelDesclimerLine2, font, fontScale, thickness)
    text_coord_labelDesclimerLine2 = (width // 2 - text_width_labelDesclimerLine2[0] // 2,text_height_labelDesclimerLine2 + offset + text_height_labelAbout + interspace + 10)
    cv2.putText(img, labelDesclimerLine2, text_coord_labelDesclimerLine2, font, fontScale, text_color,thickness)
    
    labelDesclimerLine3='Текст и иллюстрации могут охраняться авторским правом.'.upper()
    text_width_labelDesclimerLine3, text_height_labelDesclimerLine3 = cv2.getTextSize(labelDesclimerLine3, font, fontScale, thickness)
    text_coord_labelDesclimerLine3 = (width // 2 - text_width_labelDesclimerLine3[0] // 2,text_height_labelDesclimerLine3 + offset + text_height_labelAbout + interspace + 20)
    cv2.putText(img, labelDesclimerLine3, text_coord_labelDesclimerLine3, font, fontScale, text_color,thickness)
    
    labelDesclimerLine4='Этот сервис не имеет отношения к органам власти.'.upper()
    text_width_labelDesclimerLine4, text_height_labelDesclimerLine4 = cv2.getTextSize(labelDesclimerLine4, font, fontScale, thickness)
    text_coord_labelDesclimerLine4 = (width // 2 - text_width_labelDesclimerLine4[0] // 2,text_height_labelDesclimerLine4 + offset + text_height_labelAbout + interspace + 30)
    cv2.putText(img, labelDesclimerLine4, text_coord_labelDesclimerLine4, font, fontScale, text_color,thickness)
    
    labelDesclimerLine5='Электронная почта для связи: alfablend@gmail.com'.upper()
    text_width_labelDesclimerLine5, text_height_labelDesclimerLine5 = cv2.getTextSize(labelDesclimerLine5, font, fontScale, thickness)
    text_coord_labelDesclimerLine5 = (width // 2 - text_width_labelDesclimerLine5[0] // 2,text_height_labelDesclimerLine5 + offset + text_height_labelAbout + interspace + 40)
    cv2.putText(img, labelDesclimerLine5, text_coord_labelDesclimerLine5, font, fontScale, text_color,thickness)
  
    return img

#https://stackoverflow.com/questions/72848330/how-to-read-pdf-images-as-opencv-images-using-pymupdf
def pix_to_image(pix):
    #Возможно, нужно еще конвертировать цвета
    bytes = np.frombuffer(pix.samples, dtype=np.uint8)
    img = bytes.reshape(pix.height, pix.width, pix.n)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    return img

def is_greyscale(im):
    """
    Check if image is monochrome (1 channel or 3 identical channels)
    """
    if im.mode not in ("L", "RGB"):
        raise ValueError("Unsuported image mode")

    if im.mode == "RGB":
        rgb = im.split()
        if ImageChops.difference(rgb[0],rgb[1]).getextrema()[1]!=0: 
            return False
        if ImageChops.difference(rgb[0],rgb[2]).getextrema()[1]!=0: 
            return False
    return True

def process_pdf(docpath):
    read_pdf = PdfReader(docpath) 
    
    count = len(read_pdf.pages)
    pages_txt = ''
    
     #Извлекаем страницы в виде картинок
    images_collection=[]
    images_collection_color=[]
    images_collection_bw=[]
    
    doc = fitz.open(docpath) 
    zoom = 1    # zoom factor
    mat = fitz.Matrix(zoom, zoom)
    

    # For each page we extract the text
    
    for x in tqdm(range(count)[:200], desc='Извлекаем страницы:'):
        page = read_pdf.pages[x]    
        try:
            page_text = page.extract_text()
        except:
            page_text = ''
        pages_txt = pages_txt + page_text
        #Если нужно извлечь картинки
        
        if extract_images:
            try:
                page = doc.load_page(x)
                   
                #https://stackoverflow.com/questions/76045074/python-determine-pdf-pages-containing-image
                img_refs = page.get_image_info(xrefs=True)
                img_refs_new = []
                for img in img_refs:
                    if img['width']>291 and img['height']>412: #Чтобы из распознаваемых файлов вытаскивались страницы с картинками-четвертинками
                        img_refs_new.append(img)
                
                 
                if img_refs_new != []: #На странице есть картинки 
                        pix = page.get_pixmap(matrix = mat)
                        img = pix_to_image(pix)
                        pil_image=Image.fromarray(img)
                        h, w = img.shape[:2]
                        aspect = w/h  
                        if aspect < 1:
                            if not is_greyscale(pil_image): #Берем только вертикальные страницы
                                images_collection_color.append(img) 
                            else:
                                images_collection_bw.append(img) 
                         
                         

            except AttributeError: continue
            except: logging.error(traceback.format_exc())
    
    if images_collection_color!=[]: #Предпочитаем цветные картинки
        images_collection = images_collection_color
    else: 
        images_collection = images_collection_bw 
        
    random.shuffle(images_collection)
    
    #Добавляем в начало титульный лист
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix = mat)
    img = pix_to_image(pix)
    images_collection.insert(0, img)
    return (pages_txt, images_collection)                    
                    

    
def delete_files_in_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print('Удален файл ', file_path)
        except Exception as e:
            print(f'Ошибка при удалении файла {file_path}. {e}')


def getgike(link, cookies, headers, short_link=''):
    with requests.get(link, cookies=cookies, headers=headers, stream=True, timeout=10, verify=False) as pdf_bytes:
        pdf_bytes.raise_for_status()
        with open('temp.pdf', 'wb') as p:
            pbar = tqdm(total=int(pdf_bytes.headers['Content-Length']))
            for chunk in pdf_bytes.iter_content(chunk_size=8192):
                if bus.stop==True: #Обнаружен флаг остановки
                    raise bus.UserStopError()
                if chunk:  # filter out keep-alive new chunks
                    p.write(chunk)
                    pbar.update(len(chunk))
            p.seek(0, os.SEEK_END)
            
            #Распознание PDF
            try:
                ocrmypdf.ocr('temp.pdf', 'tempocr.pdf', l='rus', use_threads=True, pages='1-200', output_type='pdf', optimize=0) 
                #аргумент use_threads=True нужен для корректной работы из импортированного модуля https://ocrmypdf.readthedocs.io/en/v10.2.0/api.html skip_text=True,
                docpath='tempocr.pdf' #имя файла, из которого будем извлекать текст, меняется в зависимости от того, было нужно ocr или нет
            except (ocrmypdf.exceptions.PriorOcrFoundError, ocrmypdf.exceptions.TaggedPDFError) as e:
                print ('OCR не требуется.')
                docpath='temp.pdf'
            except: 
                print('Произошла ошибка в модуле распознавания')
                docpath='temp.pdf'
                logging.error(traceback.format_exc())
            # Now we can load our PDF in PyPDF2 from memory
            read_pdf = PdfReader(docpath)
            
            pages_txt, images_collection=process_pdf(docpath)  
                       
            data=extract_data(pages_txt) 
             
            #В случае, когда файл загружается с яндекс-диска, указываем короткую ссылку
            if short_link!='':
                link_for_thumb=short_link
            else: link_for_thumb=link  

            img=make_thumbnails(docpath, images_collection, data, link_for_thumb)
            
            print('Очистка временной папки')
            delete_files_in_folder('tempimg\\')
    return (img, data)



#Далее код отключен, так как он был нужен для загрузки экспертиз из локальной папки
'''
dirname = "debug_source"
dst = "temp.pdf"
for file in os.listdir(dirname):
    print('Обрабатываем файл ', file) 
    shutil.copy(dirname + '\\' + file, dst)
    pages_txt=process_pdf()  
    data=extract_data(pages_txt)
    make_thumbnails(file, data)
    
'''
                
#with open ('temp_txt.txt', 'w', encoding='utf-8') as f:
#    f.write(pages_txt)