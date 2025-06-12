#Модуль выгрузки и распознания pdf

import vkp_app.vkp_bus as bus #Шина обмена данными
import vkp_app.vkp_settings

import requests
from io import BytesIO
import os
from pypdf import PdfReader
from tqdm import tqdm
import ocrmypdf

import traceback
import logging
import re



def getpdf (link, cookies, headers, extract_images=False):
            
    with requests.get(link, cookies=cookies, headers=headers, stream=True, timeout=10) as pdf_bytes:
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
                #https://ocrmypdf.readthedocs.io/en/v10.2.0/api.html
                ocrmypdf.ocr('temp.pdf', 'tempocr.pdf', l='rus', use_threads=True, pages='1-100', output_type='pdf', optimize=0) 
                docpath='tempocr.pdf' #имя файла, из которого будем извлекать текст, меняется в зависимости от того, было нужно ocr или нет
            except (ocrmypdf.exceptions.PriorOcrFoundError, ocrmypdf.exceptions.TaggedPDFError) as e:
                print ('OCR не требуется.')
                docpath='temp.pdf'
            except: 
                print('Произошла ошибка в модуле распознавания')
                docpath='temp.pdf'
                logging.error(traceback.format_exc())
            # Now we can load our PDF in PyPDF2 from memory
            print('ИСТОЧНИК ДЛЯ ИЗВЛЕЧЕНИЯ СТРАНИЦ ', docpath)
            read_pdf = PdfReader(docpath)
            count = len(read_pdf.pages)
            pages_txt = ''
            # For each page we extract the text
            found_page=0 #Сюда будем сохранять страницу, на которой найдено слово "распоряжение"
            for x in tqdm(range(count), desc='Извлекаем страницы:'):
                page = read_pdf.pages[x]    
                page_text = page.extract_text()
                pages_txt = pages_txt + page_text
                #Если нужно извлечь картинки
                if extract_images:
                    indice = re.findall('(?i)распоряжени', page_text) #[0].span()[1]
                    #indice = re.findall('(?s)(?<=Приложение)(.{1,5})(?=к распоряжению КГИОП)', page_text) #[0].span()[1]
                    if(len(indice))>0: #Если страница определена как документ КГИОП, берем из нее картинки
                        print('ОБНАРУЖЕН ТЕКСТ РАСПОРЯЖЕНИЕ на странице ', str(x+1))
                        found_page = x
                    
                    if found_page <= x <= (found_page+2): #Берем картинки со страницы со словом "распоряжение" и со следующих двух
                        try:
                            for image_file_object in page.images:
                                with open('tempimg\\' + str(count) + image_file_object.name, "wb") as fp:
                                    print('Извлекаем изображение ', image_file_object.name, ' со страницы ', str(x))
                                    fp.write(image_file_object.data)
                                    count += 1            
                        except: 
                            logging.error(traceback.format_exc())
    with open ('temp_txt.txt', 'w', encoding='utf-8') as f:
        f.write(pages_txt)
    return pages_txt