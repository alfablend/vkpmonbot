#Создание карты по списку кадастровых номеров

import traceback, logging

import cv2
from PIL import ImageFont, ImageDraw, Image
import numpy as np

from rosreestr2coord import Area

import contextily as cx
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

import json


#Функция для изменения расстояния между символами
#https://stackoverflow.com/questions/49530282/python-pil-decrease-letter-spacing
def draw_text_psd_style(draw, xy, text, font, tracking=0, leading=None, **kwargs):
    """
    usage: draw_text_psd_style(draw, (0, 0), "Test", 
                tracking=-0.1, leading=32, fill="Blue")

    Leading is measured from the baseline of one line of text to the
    baseline of the line above it. Baseline is the invisible line on which most
    letters—that is, those without descenders—sit. The default auto-leading
    option sets the leading at 120% of the type size (for example, 12‑point
    leading for 10‑point type).

    Tracking is measured in 1/1000 em, a unit of measure that is relative to 
    the current type size. In a 6 point font, 1 em equals 6 points; 
    in a 10 point font, 1 em equals 10 points. Tracking
    is strictly proportional to the current type size.
    """
    def stutter_chunk(lst, size, overlap=0, default=None):
        for i in range(0, len(lst), size - overlap):
            r = list(lst[i:i + size])
            while len(r) < size:
                r.append(default)
            yield r
    x, y = xy
    font_size = font.size
    lines = text.splitlines()
    if leading is None:
        leading = font.size * 1.2
    for line in lines:
        for a, b in stutter_chunk(line, 2, 1, ' '):
            w = font.getlength(a + b) - font.getlength(b)
            # dprint("[debug] kwargs")
            print("[debug] kwargs:{}".format(kwargs))
                
            draw.text((x, y), a, font=font, **kwargs)
            x += w + (tracking / 1000) * font_size
        y += leading
        x = xy[0]


def plotmap (kadastr):
    print('Вызвана подготовка карты')
    gdf_merged=gpd.GeoDataFrame()
    for i in kadastr:
        print (i)
        area = Area(i, with_proxy=True, use_cache=True)
        
        # Получение координат
        coords = area.to_geojson_poly()
        
        if coords == False:
            print ('Координаты участка {} не получены'.format(i))
            continue
    
        coords=json.loads(coords)
        coords=coords['geometry']['coordinates'][0]
        
       
        polygon_geom = Polygon(coords)
        #gpd.GeoDataFrame.from_features(coords['geometry'])
        #gdf=gpd.GeoDataFrame.from_features([coords])
        gdf = gpd.GeoDataFrame(index=[0], crs='epsg:4326', geometry=[polygon_geom]) 
        gdf_merged=gdf_merged._append(gdf, ignore_index=True)
    
    
    gdf=gdf_merged
    print(gdf)
    assert not gdf.empty, "Не удалось получить координаты ни одного участка"
    gdf=gdf.set_geometry('geometry')
    gdf = gdf.to_crs(4326) 
   
    cmap = ListedColormap(['red'], name='allred')
    ax = gdf.plot(cmap=cmap, edgecolor="#00ff00", figsize=(10,10), alpha=.5)
    ax.set_xlim(gdf.bounds.iloc[0].minx-0.01, gdf.bounds.iloc[0].maxx+0.01)  
    ax.set_ylim(gdf.bounds.iloc[0].miny-0.005, gdf.bounds.iloc[0].maxy+0.005)


    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    print('Карта с полигоном построена')
    cx.add_basemap(ax=ax, crs='EPSG:4326', source=cx.providers.OpenStreetMap.Mapnik)
    print('Базовая карта наложена')
    plt.savefig("tempmap.jpg", bbox_inches='tight', transparent="True", pad_inches=0)
    img = cv2.imread('tempmap.jpg')
    
    height, width, channels = img.shape
   
    #Отрезаем черные полосы по краям
    img = img[1:height,1:width]
    
    #Преобразуем картинку в PIL для наложения надписи

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    im_pil = Image.fromarray(img)

    fontSize=11.45
    font=ImageFont.truetype('tahoma.ttf', fontSize)
    draw = ImageDraw.Draw(im_pil)
    msg='. Инфографика: @vkpgikebot'
    w = draw.textlength(msg, font=font)
    h = fontSize
    W, H = im_pil.size

    overlay = im_pil.copy()
    draw = ImageDraw.Draw(overlay)  # Create a context for drawing things on it.
    draw.rectangle(((182,(H-h)), (182+w+10, (H-5))),  fill='white')

    im_pil = Image.blend(im_pil, overlay, 0.5) 

    draw = ImageDraw.Draw(im_pil) 
    
    draw_text_psd_style(draw, (182,(H-h-5)), msg, font, tracking=40, leading=None,fill="#171314")
    
    # Снова возвращаемся к объекту cv2
    img = np.asarray(im_pil)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    #Добавляем рамку
    img = cv2.copyMakeBorder(img, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = (0, 255, 0)) 
        
    compression_params = [cv2.IMWRITE_JPEG_QUALITY, 90]
    
    cv2.imwrite('tempmap.jpg', img)
    return(img)