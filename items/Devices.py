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

class DeviceParser:
    """Парсер для устройств"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Устройства"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/devices"
        self.user = fake_useragent.UserAgent().random
        
        self.devices_data = {
            'devices': [],    
            'images': [],     
            'links': [],      
            'quantity': []    
        }

        self._device_details_cache = {}
        self._device_details_lock = threading.Lock()
        self._device_details_ttl = 86400  
        self._CACHE_FILE = "device_details_cache.json"

        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }
        
        self._load_details_cache()

    
    def parse_devices_list(self):
        """Парсит список устройств"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')
            
            self.devices_data = {
                'devices': [],
                'images': [],
                'links': [],
                'quantity': []
            }
            
            block = soup.find('div', class_='mt-6 rounded-lg bg-secondary/50 p-4 backdrop-blur-sm')
            
            if block:
                items = block.find_all('p', class_='truncate font-medium transition-colors group-hover:brightness-110')
                img_items = block.find_all('img', class_='max-h-[44px] object-contain')
                
                print(f"[{self.CATEGORY_NAME}] Найдено элементов: {len(items)}")
                print(f"[{self.CATEGORY_NAME}] Найдено изображений: {len(img_items)}")
                
                for i, item in enumerate(items):
                    item_text = item.text.strip()
                    if item_text:
                        self.devices_data['devices'].append(item_text)

                        device_link = ''
                        parent_a = item.find_parent('a')
                        
                        if parent_a and parent_a.get('href'):
                            device_link = parent_a['href']
                            
                            if device_link.startswith('devices/'):
                                device_link = f"items/{device_link}"
                            elif device_link.startswith('/devices/'):
                                device_link = f"items{device_link}"
                            elif 'devices/' in device_link and not device_link.startswith('items/'):
                                device_link = f"items/{device_link}"
                            
                            if not device_link.startswith('http'):
                                device_link = urljoin(self.BASE_URL, device_link)
                        
                        self.devices_data['links'].append(device_link)

                        img_src = ''

                        if i < len(img_items):
                            img_tag = img_items[i]
                            if img_tag and img_tag.get('src'):
                                img_src = img_tag.get('src')

                        if not img_src and parent_a:
                            img_tag = parent_a.find('img')
                            if img_tag and img_tag.get('src'):
                                img_src = img_tag.get('src')

                        if img_src:
                            if img_src.startswith('http'):
                                final_img_src = img_src
                            elif img_src.startswith('/'):
                                final_img_src = urljoin(self.BASE_URL, img_src)
                            elif not img_src.startswith(('http', '/')):
                                final_img_src = urljoin(self.BASE_URL, '/' + img_src.lstrip('/'))
                            else:
                                final_img_src = img_src
                            
                            self.devices_data['images'].append(final_img_src)

                            if i < 5:
                                print(f"[{self.CATEGORY_NAME}] Изображение {i+1}: {item_text}")
                                print(f"    URL: {final_img_src}")
                        else:
                            self.devices_data['images'].append('')
                            if i < 10: 
                                print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено изображение для: {item_text}")
                
                self.devices_data['quantity'].append(len(self.devices_data['devices']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено устройств: {len(self.devices_data['devices'])}")

                self._start_background_parsing()
                
                return self.devices_data
                
            else:
                print(f"[{self.CATEGORY_NAME}] Основной блок не найден")
                return self.devices_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.devices_data
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей устройств"""
        thread = threading.Thread(target=self._parse_all_devices_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_devices_background(self):
        """Фоновая функция парсинга всех устройств"""
        try:
            if not self.devices_data['devices']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список устройств пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.devices_data['devices'])} устройств...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (device_name, device_url) in enumerate(zip(self.devices_data['devices'], self.devices_data['links']), 1):
                if not device_url:
                    failed_parses += 1
                    continue
                
                with self._device_details_lock:
                    if device_name in self._device_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.devices_data['devices'])}] Парсим {device_name}...")
                    details = self._parse_device_details_internal(device_name, device_url)
                    
                    if details:
                        with self._device_details_lock:
                            self._device_details_cache[device_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {device_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {device_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {device_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_device_details_internal(self, device_name: str, device_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей устройства"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {device_url}")

            if not device_url.startswith('https://stalcraft.wiki/items/devices/'):
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠ Неправильный URL: {device_url}")
                print(f"[{self.CATEGORY_NAME}-PARSER] Ожидается: https://stalcraft.wiki/items/devices/[id]")
                return None
            
            response = requests.get(device_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            device_data = {
                'name': device_name,
                'url': device_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                device_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {device_data['name']}")

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        device_data['rank'] = text.replace('Ранг:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Ранг: {device_data['rank']}")
                    elif 'Класс:' in text:
                        device_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {device_data['class']}")
                    elif 'Тип:' in text:
                        device_data['type'] = text.replace('Тип:', '').strip()

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    device_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {device_data['region']}")

            image_found = False

            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    device_data['image'] = img_src
                    device_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 1)")

            if not image_found:
                all_images = soup.find_all('img')
                for img_tag in all_images:
                    img_src = img_tag.get('src', '')
                    if img_src and 'exbo_item_parser' in img_src:
                        if not img_src.startswith('http'):
                            img_src = urljoin(self.BASE_URL, img_src)
                        device_data['image'] = img_src
                        device_data['image_alt'] = img_tag.get('alt', '')
                        image_found = True
                        print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 2)")
                        break
            
            if not image_found and hasattr(self, 'devices_data') and 'devices' in self.devices_data:
                try:
                    if device_name in self.devices_data['devices']:
                        idx = self.devices_data['devices'].index(device_name)
                        if idx < len(self.devices_data.get('images', [])):
                            list_image = self.devices_data['images'][idx]
                            if list_image:
                                device_data['image'] = list_image
                                image_found = True
                                print(f"[{self.CATEGORY_NAME}-PARSER] Изображение взято из списка (метод 3)")
                except Exception as e:
                    print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при поиске изображения в списке: {e}")
            
            if image_found:
                print(f"[{self.CATEGORY_NAME}-PARSER] 🖼️ Изображение для {device_name}: {device_data.get('image', '')[:80]}...")
            else:
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠️ Изображение не найдено для {device_name}")
                device_data['image'] = None
            
            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    device_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")

            device_data['characteristics'] = {}
            device_data['device_specific'] = {}
            
            char_blocks = soup.find_all('div', class_='space-y-4')
            
            for char_block in char_blocks:
                char_list = char_block.find('ul', class_='space-y-2')
                if char_list:
                    items = char_list.find_all('li')
                    for item in items:
                        spans = item.find_all('span')
                        if len(spans) >= 2:
                            char_name = spans[0].text.strip()
                            char_value = spans[1].text.strip()
                            device_data['characteristics'][char_name] = char_value
                            print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value}")
            
            page_text = soup.get_text()

            device_types = ['Детектор', 'Измеритель', 'Сканер', 'Прибор', 'Устройство']
            for dtype in device_types:
                if dtype in page_text:
                    device_data['device_specific']['device_type'] = dtype
                    print(f"[{self.CATEGORY_NAME}-PARSER] Тип устройства: {dtype}")
                    break

            if 'description' in device_data:
                desc = device_data['description'].lower()
                if 'детект' in desc or 'обнаруж' in desc:
                    device_data['device_specific']['purpose'] = 'detection'
                elif 'измер' in desc or 'анализ' in desc:
                    device_data['device_specific']['purpose'] = 'measurement'
                elif 'сканир' in desc or 'сканер' in desc:
                    device_data['device_specific']['purpose'] = 'scanning'
                elif 'защит' in desc or 'защищает' in desc or 'защитный' in desc:
                    device_data['device_specific']['purpose'] = 'protection'
                elif 'лечен' in desc or 'медицин' in desc:
                    device_data['device_specific']['purpose'] = 'medical'
                elif 'связ' in desc or 'коммуникац' in desc:
                    device_data['device_specific']['purpose'] = 'communication'
                else:
                    device_data['device_specific']['purpose'] = 'utility'
                
                print(f"[{self.CATEGORY_NAME}-PARSER] Назначение: {device_data['device_specific']['purpose']}")

            battery_keys = ['Батарея', 'Заряд', 'Энергия', 'Питание', 'Время работы']
            for key in battery_keys:
                if key in device_data['characteristics']:
                    device_data['device_specific']['battery'] = device_data['characteristics'][key]
                    print(f"[{self.CATEGORY_NAME}-PARSER] Батарея: {device_data['device_specific']['battery']}")
                    break

            if 'Дальность' in device_data['characteristics']:
                device_data['device_specific']['range'] = device_data['characteristics']['Дальность']
            if 'Точность' in device_data['characteristics']:
                device_data['device_specific']['accuracy'] = device_data['characteristics']['Точность']
            if 'Вес' in device_data['characteristics']:
                device_data['device_specific']['weight'] = device_data['characteristics']['Вес']
            if 'Время зарядки' in device_data['characteristics']:
                device_data['device_specific']['charge_time'] = device_data['characteristics']['Время зарядки']

            page_text = soup.get_text()
            additional_chars = [
                ('Батарея', r'Батарея[:\s]+([\d.,]+)'),
                ('Дальность', r'Дальность[:\s]+([\d.,]+\s*м)'),
                ('Точность', r'Точность[:\s]+([\d.,]+\s*%)'),
                ('Время работы', r'Время работы[:\s]+([\d.,]+\s*ч)'),
                ('Вес', r'Вес[:\s]+([\d.,]+\s*кг)'),
            ]
            
            for char_name, pattern in additional_chars:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match and char_name not in device_data['characteristics']:
                    device_data['characteristics'][char_name] = match.group(1).strip()
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {device_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Характеристик: {len(device_data['characteristics'])}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 🔧 Специфических данных: {len(device_data.get('device_specific', {}))}")
            
            return device_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {device_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def get_device_details(self, device_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали устройства из кэша или парсит заново"""
        with self._device_details_lock:
            if not force_refresh and device_name in self._device_details_cache:
                cache_entry = self._device_details_cache[device_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._device_details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {device_name}")
                    return cache_entry['data']
        
        if device_name not in self.devices_data['devices']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Устройство {device_name} не найдено в списке")
            return None
        
        idx = self.devices_data['devices'].index(device_name)
        device_url = self.devices_data['links'][idx]
        
        if not device_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {device_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {device_name}...")
        details = self._parse_device_details_internal(device_name, device_url)
        
        if details:
            with self._device_details_lock:
                self._device_details_cache[device_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._device_details_lock:
                cache_to_save = {}
                for device_name, cache_entry in self._device_details_cache.items():
                    cache_to_save[device_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} устройств)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._device_details_lock:
                    self._device_details_cache.clear()
                    self._device_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} устройств)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_device_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали устройств"""
        with self._device_details_lock:
            result = {}
            current_time = time.time()
            
            for device_name, cache_entry in self._device_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._device_details_ttl:
                    result[device_name] = cache_entry['data']
            
            return result
    
    def refresh_all_device_details(self):
        """Принудительно обновляет все детали устройств"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._device_details_lock:
            self._device_details_cache.clear()
        
        self._parse_all_devices_background()
        
        return True

    
    def get_data(self):
        """Возвращает данные об устройствах"""
        if not self.devices_data['devices']:
            self.parse_devices_list()

        return {
            'devices': self.devices_data['devices'],
            'img': self.devices_data['images'],
            'links': self.devices_data['links'],
            'quantity': self.devices_data['quantity']
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._device_details_lock:
            total_devices = len(self.devices_data['devices'])
            cached_devices = len(self._device_details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._device_details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_devices': total_devices,
                'cached_devices': cached_devices,
                'coverage_percentage': (cached_devices / total_devices * 100) if total_devices > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._device_details_ttl / 3600
            }


device_parser = DeviceParser()

def Device():
    """Основная функция для парсинга устройств"""
    return device_parser.parse_devices_list()

def get_cached_device():
    """Возвращает данные об устройствах"""
    return device_parser.get_data()

def get_device_details(device_name: str, force_refresh: bool = False):
    """Получает детали устройства"""
    return device_parser.get_device_details(device_name, force_refresh)

def get_all_device_details():
    """Получает все детали устройств"""
    return device_parser.get_all_device_details()

def refresh_all_device_details():
    """Обновляет все детали устройств"""
    return device_parser.refresh_all_device_details()