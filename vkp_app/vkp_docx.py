#Модуль выгрузки docx

import vkp_app.vkp_bus as bus #Шина обмена данными

import requests
from io import BytesIO
import os
import docx2txt
from tqdm import tqdm

def getdocx (link, cookies, headers):
    with requests.get(link, cookies=cookies, headers=headers, stream=True) as docbytes:
        docbytes.raise_for_status()
        # We load the bytes into an in memory file (to avoid saving the PDF on disk)
        with BytesIO(docbytes.content) as p:
            pbar = tqdm(total=int(docbytes.headers['Content-Length']))
            for chunk in docbytes.iter_content(chunk_size=128):
                if bus.stop==True: #Обнаружен флаг остановки
                    raise bus.UserStopError()
                if chunk:  # filter out keep-alive new chunks
                    p.write(chunk)
                    pbar.update(len(chunk))
            p.seek(0, os.SEEK_END)
            docx = p
            text = docx2txt.process(docx)
            text=text.replace('\n', '')
            text=text.replace('\r', '')
            return text