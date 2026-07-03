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

class ContainerParser:
    """Парсер для контейнеров"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Контейнеры"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/containers"
        self.user = fake_useragent.UserAgent().random

        self.containers_data = {
            'containers': [],    
            'images': [],       
            'links': [],        
            'quantity': []       
        }

        self._container_details_cache = {}
        self._container_details_lock = threading.Lock()
        self._container_details_ttl = 86400  # 24 часа
        self._CACHE_FILE = "container_details_cache.json"
        
        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }

        self._load_details_cache()

    
    def parse_containers_list(self):
        """Парсит список контейнеров"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            self.containers_data = {
                'containers': [],
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
                        self.containers_data['containers'].append(item_text)

                        container_link = ''
                        parent_a = item.find_parent('a')
                        
                        if parent_a and parent_a.get('href'):
                            container_link = parent_a['href']

                            if container_link.startswith('containers/'):
                                container_link = f"items/{container_link}"
                            elif container_link.startswith('/containers/'):
                                container_link = f"items{container_link}"
                            elif 'containers/' in container_link and not container_link.startswith('items/'):
                                container_link = f"items/{container_link}"
                            
                            if not container_link.startswith('http'):
                                container_link = urljoin(self.BASE_URL, container_link)
                        
                        self.containers_data['links'].append(container_link)

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
                            
                            self.containers_data['images'].append(final_img_src)

                            if i < 5:
                                print(f"[{self.CATEGORY_NAME}] Изображение {i+1}: {item_text}")
                                print(f"    URL: {final_img_src}")
                        else:
                            self.containers_data['images'].append('')
                            if i < 10:  
                                print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено изображение для: {item_text}")
                
                self.containers_data['quantity'].append(len(self.containers_data['containers']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено контейнеров: {len(self.containers_data['containers'])}")

                self._start_background_parsing()
                
                return self.containers_data
                
            else:
                print(f"[{self.CATEGORY_NAME}] Основной блок не найден")
                return self.containers_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.containers_data
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей контейнеров"""
        thread = threading.Thread(target=self._parse_all_containers_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_containers_background(self):
        """Фоновая функция парсинга всех контейнеров"""
        try:
            if not self.containers_data['containers']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список контейнеров пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.containers_data['containers'])} контейнеров...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (container_name, container_url) in enumerate(zip(self.containers_data['containers'], self.containers_data['links']), 1):
                if not container_url:
                    failed_parses += 1
                    continue
                
                with self._container_details_lock:
                    if container_name in self._container_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.containers_data['containers'])}] Парсим {container_name}...")
                    details = self._parse_container_details_internal(container_name, container_url)
                    
                    if details:
                        with self._container_details_lock:
                            self._container_details_cache[container_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {container_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {container_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {container_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_container_details_internal(self, container_name: str, container_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей контейнера"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {container_url}")

            if not container_url.startswith('https://stalcraft.wiki/items/containers/'):
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠ Неправильный URL: {container_url}")
                print(f"[{self.CATEGORY_NAME}-PARSER] Ожидается: https://stalcraft.wiki/items/containers/[id]")
                return None
            
            response = requests.get(container_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            container_data = {
                'name': container_name,
                'url': container_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                container_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {container_data['name']}")

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        container_data['rank'] = text.replace('Ранг:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Ранг: {container_data['rank']}")
                    elif 'Класс:' in text:
                        container_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {container_data['class']}")
                    elif 'Тип:' in text:
                        container_data['type'] = text.replace('Тип:', '').strip()

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    container_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {container_data['region']}")

            image_found = False

            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    container_data['image'] = img_src
                    container_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 1)")

            if not image_found:
                all_images = soup.find_all('img')
                for img_tag in all_images:
                    img_src = img_tag.get('src', '')
                    if img_src and 'exbo_item_parser' in img_src:
                        if not img_src.startswith('http'):
                            img_src = urljoin(self.BASE_URL, img_src)
                        container_data['image'] = img_src
                        container_data['image_alt'] = img_tag.get('alt', '')
                        image_found = True
                        print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 2)")
                        break
            
            if not image_found and hasattr(self, 'containers_data') and 'containers' in self.containers_data:
                try:
                    if container_name in self.containers_data['containers']:
                        idx = self.containers_data['containers'].index(container_name)
                        if idx < len(self.containers_data.get('images', [])):
                            list_image = self.containers_data['images'][idx]
                            if list_image:
                                container_data['image'] = list_image
                                image_found = True
                                print(f"[{self.CATEGORY_NAME}-PARSER] Изображение взято из списка (метод 3)")
                except Exception as e:
                    print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при поиске изображения в списке: {e}")
            
            if image_found:
                print(f"[{self.CATEGORY_NAME}-PARSER] 🖼️ Изображение для {container_name}: {container_data.get('image', '')[:80]}...")
            else:
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠️ Изображение не найдено для {container_name}")
                container_data['image'] = None

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    container_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")

            container_data['characteristics'] = {}
            container_data['container_specific'] = {}

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
                            container_data['characteristics'][char_name] = char_value
                            print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value}")
            
            page_text = soup.get_text()
            
            container_types = ['Медицинский', 'Боеприпасы', 'Технический', 'Пищевой', 'Универсальный']
            for ctype in container_types:
                if ctype in page_text:
                    container_data['container_type'] = ctype
                    break
            
            capacity_keys = ['Вместимость', 'Слоты', 'Размер', 'Объём', 'Количество слотов']
            for key in capacity_keys:
                if key in container_data['characteristics']:
                    container_data['container_specific']['capacity'] = container_data['characteristics'][key]
                    break

            if 'description' in container_data:
                desc = container_data['description'].lower()
                if 'медицин' in desc:
                    container_data['container_specific']['purpose'] = 'medical'
                elif 'патрон' in desc or 'боеприпас' in desc:
                    container_data['container_specific']['purpose'] = 'ammo'
                elif 'технич' in desc or 'инструмент' in desc:
                    container_data['container_specific']['purpose'] = 'technical'
                elif 'еда' in desc or 'пища' in desc or 'пищев' in desc:
                    container_data['container_specific']['purpose'] = 'food'
                else:
                    container_data['container_specific']['purpose'] = 'general'

            page_text = soup.get_text()
            additional_chars = [
                ('Вместимость', r'Вместимость[:\s]+([\d.,]+)'),
                ('Слоты', r'Слоты[:\s]+(\d+)'),
                ('Размер', r'Размер[:\s]+([\d.,]+)'),
                ('Вес', r'Вес[:\s]+([\d.,]+\s*кг)'),
            ]
            
            for char_name, pattern in additional_chars:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match and char_name not in container_data['characteristics']:
                    container_data['characteristics'][char_name] = match.group(1).strip()
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {container_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Характеристик: {len(container_data['characteristics'])}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📦 Специфических данных: {len(container_data.get('container_specific', {}))}")
            
            return container_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {container_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def get_container_details(self, container_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали контейнера из кэша или парсит заново"""
        with self._container_details_lock:
            if not force_refresh and container_name in self._container_details_cache:
                cache_entry = self._container_details_cache[container_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._container_details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {container_name}")
                    return cache_entry['data']
        
        if container_name not in self.containers_data['containers']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Контейнер {container_name} не найден в списке")
            return None
        
        idx = self.containers_data['containers'].index(container_name)
        container_url = self.containers_data['links'][idx]
        
        if not container_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {container_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {container_name}...")
        details = self._parse_container_details_internal(container_name, container_url)
        
        if details:
            with self._container_details_lock:
                self._container_details_cache[container_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._container_details_lock:
                cache_to_save = {}
                for container_name, cache_entry in self._container_details_cache.items():
                    cache_to_save[container_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} контейнеров)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._container_details_lock:
                    self._container_details_cache.clear()
                    self._container_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} контейнеров)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_container_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали контейнеров"""
        with self._container_details_lock:
            result = {}
            current_time = time.time()
            
            for container_name, cache_entry in self._container_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._container_details_ttl:
                    result[container_name] = cache_entry['data']
            
            return result
    
    def refresh_all_container_details(self):
        """Принудительно обновляет все детали контейнеров"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._container_details_lock:
            self._container_details_cache.clear()
        
        self._parse_all_containers_background()
        
        return True
    
    
    def get_data(self):
        """Возвращает данные о контейнерах"""
        if not self.containers_data['containers']:
            self.parse_containers_list()
        
        return {
            'containers': self.containers_data['containers'],
            'img': self.containers_data['images'],
            'links': self.containers_data['links'],
            'quantity': self.containers_data['quantity']
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._container_details_lock:
            total_containers = len(self.containers_data['containers'])
            cached_containers = len(self._container_details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._container_details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_containers': total_containers,
                'cached_containers': cached_containers,
                'coverage_percentage': (cached_containers / total_containers * 100) if total_containers > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._container_details_ttl / 3600
            }


container_parser = ContainerParser()

def Container():
    """Основная функция для парсинга контейнеров"""
    return container_parser.parse_containers_list()

def get_cached_container():
    """Возвращает данные о контейнерах"""
    return container_parser.get_data()

def get_container_details(container_name: str, force_refresh: bool = False):
    """Получает детали контейнера"""
    return container_parser.get_container_details(container_name, force_refresh)

def get_all_container_details():
    """Получает все детали контейнеров"""
    return container_parser.get_all_container_details()

def refresh_all_container_details():
    """Обновляет все детали контейнеров"""
    return container_parser.refresh_all_container_details()