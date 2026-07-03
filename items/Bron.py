import requests
import fake_useragent
from bs4 import BeautifulSoup
import time
import json
import random
from urllib.parse import urljoin
import threading
from typing import Dict, Any, Optional, List
import os
import re

class ArmorParser:
    """Парсер для брони"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Броня"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/armor"
        self.user = fake_useragent.UserAgent().random

        self.armor_data = {
            'armor': [],     
            'images': [],    
            'links': [],      
            'quantity': []   
        }
        
        self._armor_details_cache = {}
        self._armor_details_lock = threading.Lock()
        self._armor_details_ttl = 86400  # 24 часа
        self._CACHE_FILE = "armor_details_cache.json"
        
        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }
        
        self._load_details_cache()
    
    def parse_armor_list(self):
        """Парсит список брони - ОТЛАДОЧНАЯ ВЕРСИЯ"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}] Статус ответа: {response.status_code}")
            
            with open('debug_armor_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"[{self.CATEGORY_NAME}] HTML сохранен в debug_armor_page.html")
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            self.armor_data = {
                'armor': [],
                'images': [],
                'links': [],
                'quantity': []
            }
            
            print(f"\n[{self.CATEGORY_NAME}] Метод 1: Поиск всех ссылок с 'armor/'")
            all_links = soup.find_all('a', href=True)
            armor_links = []
            
            for link in all_links:
                href = link.get('href', '')
                if 'armor/' in href and not href.startswith('http'):
                    armor_links.append((href, link))
            
            print(f"[{self.CATEGORY_NAME}] Найдено ссылок с 'armor/': {len(armor_links)}")
            
            processed_items = set()
            
            for href, link in armor_links:
                try:
                    armor_name = ''

                    if link.get('title'):
                        armor_name = link['title']
                    elif link.text and link.text.strip():
                        armor_name = link.text.strip()
                    else:
                        p_tag = link.find('p', class_=lambda x: x and 'truncate' in str(x))
                        if p_tag:
                            armor_name = p_tag.text.strip()
                    
                    if armor_name and armor_name not in processed_items and len(armor_name) > 2:
                        processed_items.add(armor_name)
                        self.armor_data['armor'].append(armor_name)
                        
                        armor_link = ''
                        if href.startswith('armor/'):
                            armor_link = f"items/{href}"
                        elif href.startswith('/armor/'):
                            armor_link = f"items{href}"
                        elif href.startswith('items/armor/'):
                            armor_link = href
                        
                        if armor_link and not armor_link.startswith('http'):
                            armor_link = urljoin(self.BASE_URL, armor_link)
                        
                        self.armor_data['links'].append(armor_link)

                        img_src = ''
                        img_tag = link.find('img')
                        if img_tag and img_tag.get('src'):
                            img_src = img_tag['src']
                            if not img_src.startswith('http'):
                                img_src = urljoin(self.BASE_URL, img_src)
                        
                        self.armor_data['images'].append(img_src)
                        
                        print(f"[{self.CATEGORY_NAME}] Добавлен: {armor_name}")
                
                except Exception as e:
                    print(f"[{self.CATEGORY_NAME}] Ошибка при обработке ссылки: {e}")
                    continue
           
            if not self.armor_data['armor']:
                print(f"\n[{self.CATEGORY_NAME}] Метод 2: Поиск по классам карточек")
                
                grid_divs = soup.find_all('div', class_=lambda x: x and 'grid' in str(x) and 'gap-3' in str(x))
                print(f"[{self.CATEGORY_NAME}] Найдено grid divs: {len(grid_divs)}")
                
                for i, grid in enumerate(grid_divs):
                    print(f"[{self.CATEGORY_NAME}] Grid {i}: классы={grid.get('class', [])}")

                    links_in_grid = grid.find_all('a', href=True)
                    print(f"[{self.CATEGORY_NAME}] Ссылок в grid {i}: {len(links_in_grid)}")
                    
                    for link in links_in_grid:
                        href = link.get('href', '')
                        if 'armor/' in href:
                            print(f"[{self.CATEGORY_NAME}] Найдена ссылка на броню: {href}")

            if not self.armor_data['armor']:
                print(f"\n[{self.CATEGORY_NAME}] Метод 3: Поиск по известным названиям брони")

                known_armor = [
                    "Костюм «Горка-3»", "Охотничий костюм", "ЗК-1 «Отмычка»",
                    "«Гражданин»", "Бандитский кожак", "ИП-4м"
                ]
                
                for armor_name in known_armor:
                    if armor_name in response.text:
                        print(f"[{self.CATEGORY_NAME}] Найден в тексте: {armor_name}")
            
            self.armor_data['quantity'].append(len(self.armor_data['armor']))
            
            elapsed = time.time() - start_time
            print(f"\n[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
            print(f"[{self.CATEGORY_NAME}] Получено брони: {len(self.armor_data['armor'])}")
            
            if self.armor_data['armor']:
                for i in range(min(10, len(self.armor_data['armor']))):
                    print(f"  {i+1}. {self.armor_data['armor'][i]}")
                
                self._start_background_parsing()
            else:
                print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено ни одной брони!")
                print(f"[{self.CATEGORY_NAME}] Рекомендуется проверить debug_armor_page.html")
                
            return self.armor_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.armor_data

    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей брони"""
        thread = threading.Thread(target=self._parse_all_armor_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_armor_background(self):
        """Фоновая функция парсинга всей брони"""
        try:
            if not self.armor_data['armor']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список брони пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.armor_data['armor'])} брони...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (armor_name, armor_url) in enumerate(zip(self.armor_data['armor'], self.armor_data['links']), 1):
                if not armor_url:
                    failed_parses += 1
                    continue
                
                with self._armor_details_lock:
                    if armor_name in self._armor_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.armor_data['armor'])}] Парсим {armor_name}...")
                    details = self._parse_armor_details_internal(armor_name, armor_url)
                    
                    if details:
                        with self._armor_details_lock:
                            self._armor_details_cache[armor_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {armor_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {armor_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {armor_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_armor_details_internal(self, armor_name: str, armor_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей брони"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {armor_url}")
            
            response = requests.get(armor_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            armor_data = {
                'name': armor_name,
                'url': armor_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                armor_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {armor_data['name']}")
            
            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        armor_data['rank'] = text.replace('Ранг:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Ранг: {armor_data['rank']}")
                    elif 'Класс:' in text:
                        armor_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {armor_data['class']}")
                    elif 'Совместимые рюкзаки:' in text:
                        armor_data['compatible_backpacks'] = text.replace('Совместимые рюкзаки:', '').strip()
                    elif 'Совместимые контейнеры:' in text:
                        armor_data['compatible_containers'] = text.replace('Совместимые контейнеры:', '').strip()
            
            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    armor_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {armor_data['region']}")

            image_found = False
            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    armor_data['image'] = img_src
                    armor_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено")
            
            if not image_found:
                if armor_name in self.armor_data['armor']:
                    idx = self.armor_data['armor'].index(armor_name)
                    if idx < len(self.armor_data.get('images', [])):
                        list_image = self.armor_data['images'][idx]
                        if list_image:
                            armor_data['image'] = list_image
                            image_found = True
            
            if not image_found:
                armor_data['image'] = None

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    armor_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")

            armor_data['characteristics'] = {}
            armor_data['protections'] = {}
            armor_data['bonuses'] = {}

            char_sections = soup.find_all('div', class_='rounded-lg border border-foreground/10 bg-secondary/50 p-4 backdrop-blur-sm')
            print(f"[{self.CATEGORY_NAME}-PARSER] Найдено блоков с классом: {len(char_sections)}")
            
            for char_section in char_sections:
                header = char_section.find('h2', class_='text-xl font-semibold text-foreground')
                
                if header and 'Характеристики' in header.text:
                    print(f"[{self.CATEGORY_NAME}-PARSER] Найден блок 'Характеристики'")
                    
                    char_list = char_section.find('ul', class_='space-y-2')
                    if char_list:
                        print(f"[{self.CATEGORY_NAME}-PARSER] Найден список характеристик")
                        items = char_list.find_all('li')
                        print(f"[{self.CATEGORY_NAME}-PARSER] Найдено {len(items)} характеристик")
                        
                        for item in items:
                            spans = item.find_all('span')
                            if len(spans) >= 2:
                                char_name = spans[0].text.strip()
                                char_value = spans[1].text.strip()

                                color_style = spans[0].get('style', '')
                                
                                armor_data['characteristics'][char_name] = char_value

                                protection_keywords = ['Пулестойкость', 'Защита от', 'стойкость', 'устойчивость', 
                                                      'Электрозащита', 'Химзащита', 'Защита от радиации',
                                                      'Защита от огня', 'Защита от температуры', 
                                                      'Защита от биозаражения', 'Защита от пси-излучения',
                                                      'Защита от кровотечения', 'Защита от разрыва',
                                                      'Защита от взрыва']
                                
                                if any(keyword in char_name for keyword in protection_keywords):
                                    armor_data['protections'][char_name] = char_value

                                if char_value.startswith('+') or 'rgb(83, 195, 83)' in color_style:
                                    armor_data['bonuses'][char_name] = char_value
                                
                                print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value} (цвет: {color_style})")

                    if not char_list:
                        all_li = char_section.find_all('li')
                        if all_li:
                            print(f"[{self.CATEGORY_NAME}-PARSER] Найдено li элементов: {len(all_li)}")
                            for li in all_li:
                                spans = li.find_all('span')
                                if len(spans) >= 2:
                                    char_name = spans[0].text.strip()
                                    char_value = spans[1].text.strip()
                                    armor_data['characteristics'][char_name] = char_value
                                    print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика (альт): {char_name} = {char_value}")
            
            if not armor_data['characteristics']:
                print(f"[{self.CATEGORY_NAME}-PARSER] Использую альтернативный поиск характеристик")
                page_text = soup.get_text()

                characteristics_patterns = [
                    (r'Вес[:\s]+([\d\sкгг]+)', 'Вес'),
                    (r'Прочность[:\s]+([\d%]+)', 'Прочность'),
                    (r'Макс\. прочность[:\s]+([\d%]+)', 'Макс. прочность'),
                    (r'Пулестойкость[:\s]+([\d.,]+)', 'Пулестойкость'),
                    (r'Защита от разрыва[:\s]+([\d.,]+)', 'Защита от разрыва'),
                    (r'Защита от взрыва[:\s]+([\d.,]+)', 'Защита от взрыва'),
                    (r'Электрозащита[:\s]+([\d.,]+)', 'Электрозащита'),
                    (r'Защита от огня[:\s]+([\d.,]+)', 'Защита от огня'),
                    (r'Химзащита[:\s]+([\d.,]+)', 'Химзащита'),
                    (r'Защита от радиации[:\s]+([\d.,]+)', 'Защита от радиации'),
                    (r'Защита от температуры[:\s]+([\d.,]+)', 'Защита от температуры'),
                    (r'Защита от биозаражения[:\s]+([\d.,]+)', 'Защита от биозаражения'),
                    (r'Защита от пси-излучения[:\s]+([\d.,]+)', 'Защита от пси-излучения'),
                    (r'Защита от кровотечения[:\s]+([\d%.,]+)', 'Защита от кровотечения'),
                    (r'Скорость передвижения[:\s]+([\+\-\d%.,]+)', 'Скорость передвижения'),
                    (r'Переносимый вес[:\s]+([\+\-\d.,]+)', 'Переносимый вес'),
                ]
                
                for pattern, char_name in characteristics_patterns:
                    match = re.search(pattern, page_text)
                    if match:
                        armor_data['characteristics'][char_name] = match.group(1).strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Найдено по шаблону: {char_name} = {match.group(1).strip()}")

            if 'characteristics' in armor_data and 'Вес' in armor_data['characteristics']:
                weight = armor_data['characteristics']['Вес']
                try:
                    if 'кг' in weight:
                        kg = float(weight.replace('кг', '').strip())
                        armor_data['weight_kg'] = kg
                        armor_data['weight_grams'] = kg * 1000
                    elif 'г' in weight:
                        armor_data['weight_grams'] = float(weight.replace('г', '').strip())
                    print(f"[{self.CATEGORY_NAME}-PARSER] Вес: {weight} -> {armor_data.get('weight_kg')} кг")
                except:
                    pass

            if 'characteristics' in armor_data and 'Прочность' in armor_data['characteristics']:
                armor_data['durability'] = armor_data['characteristics']['Прочность']
            
            if 'characteristics' in armor_data and 'Макс. прочность' in armor_data['characteristics']:
                armor_data['max_durability'] = armor_data['characteristics']['Макс. прочность']

            armor_types = ['Комбинезон', 'Костюм', 'Куртка', 'Жилет', 'Комбинированные', 'Легкие', 'Тяжелые', 
                          'Научная', 'Боевая', 'Одежда']
            page_text = soup.get_text()
            for armor_type in armor_types:
                if armor_type.lower() in page_text.lower():
                    armor_data['armor_type'] = armor_type
                    break
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {armor_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Характеристик: {len(armor_data.get('characteristics', {}))}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 🛡️ Защит: {len(armor_data.get('protections', {}))}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📈 Бонусов: {len(armor_data.get('bonuses', {}))}")

            if armor_data['characteristics']:
                print(f"\n[{self.CATEGORY_NAME}-PARSER] Все характеристики:")
                for key, value in armor_data['characteristics'].items():
                    print(f"  {key}: {value}")
            
            return armor_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {armor_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._armor_details_lock:
                cache_to_save = {}
                for armor_name, cache_entry in self._armor_details_cache.items():
                    cache_to_save[armor_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} брони)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._armor_details_lock:
                    self._armor_details_cache.clear()
                    self._armor_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} брони)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_armor_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали брони"""
        with self._armor_details_lock:
            result = {}
            current_time = time.time()
            
            for armor_name, cache_entry in self._armor_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._armor_details_ttl:
                    result[armor_name] = cache_entry['data']
            
            return result
    
    def refresh_all_armor_details(self):
        """Принудительно обновляет все детали брони"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._armor_details_lock:
            self._armor_details_cache.clear()
        
        self._parse_all_armor_background()
        
        return True
    
    def get_data(self):
        """Возвращает данные о броне"""
        if not self.armor_data['armor']:
            self.parse_armor_list()
        
        return {
            'armor': self.armor_data['armor'],
            'img': self.armor_data['images'],
            'links': self.armor_data['links'],
            'quantity': self.armor_data['quantity']
        }


armor_parser = ArmorParser()

def Bron():
    """Основная функция для парсинга брони"""
    return armor_parser.parse_armor_list()

def get_cached_bron():
    """Возвращает данные о броне (для обратной совместимости)"""
    return armor_parser.get_data()

def get_cached_armor():
    """Новая функция для получения данных о броне"""
    return armor_parser.get_data()

def get_armor_details(armor_name: str, force_refresh: bool = False):
    """Получает детали брони"""
    return armor_parser.get_armor_details(armor_name, force_refresh)

def get_all_armor_details():
    """Получает все детали брони"""
    return armor_parser.get_all_armor_details()

def refresh_all_armor_details():
    """Обновляет все детали брони"""
    return armor_parser.refresh_all_armor_details()

get_bron_details = get_armor_details
get_all_bron_details = get_all_armor_details
refresh_all_bron_details = refresh_all_armor_details