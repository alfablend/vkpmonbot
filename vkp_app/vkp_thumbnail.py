    
#https://stackoverflow.com/questions/50881227/display-images-in-a-grid
    
import itertools

import cv2
import qrcode

import os
import numpy as np

from tqdm import tqdm 

import datetime

    
def make_thumbnails():
    #User defined variables
    dirname = "tempimg" #Name of the directory containing the images
    name = "temp_thumbnail" + ".jpg" #Name of the exported file
    margin = 20 #Margin between pictures in pixels
    w = 8 # Width of the matrix (nb of images)
    h = 8 # Height of the matrix (nb of images)
    n = w*h

    filename_list = []

    for file in os.listdir(dirname):
        #if file.endswith(".jpg"):
            filename_list.append(file)

    filename_list.sort();

    print(filename_list)

    imgs2 = [cv2.imread(os.getcwd()+"\\"+dirname+"\\"+file) for file in tqdm(filename_list, desc='Чтение')]
    imgs=[]


    #Нужно привести картинки к одному размеру
    for image in tqdm(imgs2, desc='сжатие'):
        try:
            height, width, channels = image.shape 
            if height > 240 and width > 320:
                imgs.append(cv2.resize(image, dsize=(320, 240)))
        except: continue
    #Define the shape of the image to be replicated (all images should have the same shape)
    try:
        img_h, img_w, img_c = imgs[0].shape
    except IndexError:
        print ('Картинок не найдено')
        return False

    #Define the margins in x and y directions
    m_x = margin
    m_y = margin

    #Size of the full size image
    mat_x = img_w * w + m_x * (w - 1)
    mat_y = img_h * h + m_y * (h - 1)

    #Create a matrix of zeros of the right size and fill with 255 (so margins end up white)
    imgmatrix = np.zeros((mat_y, mat_x, img_c),np.uint8)
    imgmatrix.fill(255)

    #Prepare an iterable with the right dimensions
    positions = itertools.product(range(h), range(w))

    for (y_i, x_i), img in tqdm(zip(positions, imgs), desc='совмещение'):
     
        x = x_i * (img_w + m_x)
        y = y_i * (img_h + m_y)
        imgmatrix[y:y+img_h, x:x+img_w, :] = img
        

    resized = cv2.resize(imgmatrix, (mat_x//3,mat_y//3), interpolation = cv2.INTER_AREA)
    color_yellow = (0,0,0)

    #https://ru.stackoverflow.com/questions/804541/%D0%A4%D0%BE%D0%BD-%D1%82%D0%B5%D0%BA%D1%81%D1%82%D0%B0-%D0%B2-opencv
    img=resized
    overlay = img.copy()
    font = cv2.FONT_HERSHEY_COMPLEX
    fontScale = 0.7

    #https://sky.pro/media/kak-preobrazovat-obekt-datetime-v-date-v-python/
    dt = datetime.datetime.now()
    date_only = dt.date()
    #https://ru.stackoverflow.com/questions/1412271/%D0%A4%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-%D0%B4%D0%B0%D1%82%D1%8B-datetime
    new_date = date_only.strftime("%d.%m.%Y")

    label = 'Предпросмотр документа. Источник: http://kgiop.gov.spb.ru.'
    thickness = 2
    text_color = (77,77,77)
    text_width, text_height = cv2.getTextSize(label, font, fontScale, thickness)
    text_coord = (5,text_height+20)

    cv2.rectangle(overlay, 
                  (text_coord[0]-5, text_coord[1]+text_height),
                  (text_width[0]+10, 0),
                  (0, 255, 0),
                  -1)
    opacity = 0.25
    cv2.addWeighted(overlay, opacity, img, 1 - opacity, 0, img)

    cv2.putText(img, label, text_coord, font, fontScale, text_color,thickness)

    '''
    qr = qrcode.QRCode(version = 1,
                       box_size = 10,
                       border = 5)
    data = 'https://t.me/spbgike'
    qr.add_data(data)
     
    qr.make(fit = True)
    qr = qr.make_image(fill_color = 'green',
                        back_color = 'white')
    qr = qrcode.make()
    qr_array = np.asarray(qr)
    qr_reshape = qr_array[..., np.newaxis]
    qr_reshape=cv2.resize(qr_reshape, dsize=(50, 50))
    img[300:350,100:150,:] = qr_reshape
    '''

    #imgmatrix[y:y+img_h, x:x+img_w, :] = img

    compression_params = [cv2.IMWRITE_JPEG_QUALITY, 90]

    #cv2.imshow('image', img)
    cv2.imwrite(name, img, compression_params)

    #resized = cv2.putText(imgmatrix, "Данные: kgiop.gov.spb.ru. Коллаж: телеграм-канал @spbgike", (50,50), cv2.FONT_HERSHEY_COMPLEX, 2, color_yellow, 2)

    return True

