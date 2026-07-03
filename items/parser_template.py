import requests
import fake_useragent
from bs4 import BeautifulSoup
import time
import json
import random
from urllib.parse import urljoin
import threading
from typing import Dict, Any, List, Optional
import os
import re

class UniversalParser:
    """
    Универсальный парсер для категорий 
    Наследуйте этот класс и переопределите:
    - CATEGORY_NAME
    - CATEGORY_URL
    - _parse_specific_details()
    """
    
    CATEGORY_NAME = "Категория"  
    CATEGORY_URL = "https://stalcraft.wiki/items/category"  
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.user = fake_useragent.UserAgent().random

        self.items_data = {
            'items': [],      
            'images': [],     
            'links': [],     
            'quantity': []   
        }

        self._details_cache = {}
        self._details_lock = threading.Lock()
        self._details_ttl = 86400  # 24 часа

        cache_name = f"{self.CATEGORY_NAME.lower().replace(' ', '_')}_details_cache.json"
        self._CACHE_FILE = cache_name

        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }

        self._load_details_cache()

    
    def parse_items_list(self):
        """Парсит список предметов категории"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            self.items_data = {
                'items': [],
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
                        self.items_data['items'].append(item_text)

                        parent = item.parent
                        while parent and parent.name != 'a':
                            parent = parent.parent
                        
                        if parent and parent.name == 'a' and parent.get('href'):
                            item_link = parent['href']

                            if not item_link.startswith('http'):
                                item_link = urljoin(self.BASE_URL, item_link)
                            
                            self.items_data['links'].append(item_link)
                        else:
                            self.items_data['links'].append('')

                        if i < len(img_items):
                            img_src = img_items[i].get('src', '')
                            if img_src:
                                if img_src.startswith('/'):
                                    img_src = urljoin(self.BASE_URL, img_src)
                                self.items_data['images'].append(img_src)
                            else:
                                self.items_data['images'].append('')
                        else:
                            self.items_data['images'].append('')
                
                self.items_data['quantity'].append(len(self.items_data['items']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено предметов: {len(self.items_data['items'])}")

                self._start_background_parsing()
                
            else:
                print(f"[{self.CATEGORY_NAME}] Основной блок не найден, альтернативный поиск...")
                self._alternative_parse(soup)
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            self.items_data = {
                'items': [],
                'images': [],
                'links': [],
                'quantity': [0]
            }
    
    def _alternative_parse(self, soup):
        """Альтернативный метод парсинга если основной не сработал"""
        try:
            item_cards = soup.find_all('a', href=True, class_=lambda x: x and 'group' in (x or ''))
            
            for card in item_cards:
                name_tag = card.find('p', class_='truncate')
                if name_tag:
                    item_name = name_tag.text.strip()
                    self.items_data['items'].append(item_name)
                    
                    item_link = card['href']
                    if not item_link.startswith('http'):
                        item_link = urljoin(self.BASE_URL, item_link)
                    self.items_data['links'].append(item_link)
                    
                    img_tag = card.find('img')
                    if img_tag and img_tag.get('src'):
                        img_src = img_tag['src']
                        if img_src.startswith('/'):
                            img_src = urljoin(self.BASE_URL, img_src)
                        self.items_data['images'].append(img_src)
                    else:
                        self.items_data['images'].append('')
            
            if self.items_data['items']:
                self.items_data['quantity'].append(len(self.items_data['items']))
                print(f"[{self.CATEGORY_NAME}] Альтернативным методом найдено: {len(self.items_data['items'])} предметов")
            else:
                print(f"[{self.CATEGORY_NAME}] Ничего не найдено альтернативным методом")
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка альтернативного парсинга: {e}")
    
    def get_item_details(self, item_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали предмета из кэша или парсит заново"""
        with self._details_lock:
            if not force_refresh and item_name in self._details_cache:
                cache_entry = self._details_cache[item_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {item_name}")
                    return cache_entry['data']
        
        if item_name not in self.items_data['items']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Предмет {item_name} не найден в списке")
            return None
        
        idx = self.items_data['items'].index(item_name)
        item_url = self.items_data['links'][idx]
        
        if not item_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {item_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {item_name}...")
        details = self._parse_item_details_internal(item_name, item_url)
        
        if details:
            with self._details_lock:
                self._details_cache[item_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _parse_item_details_internal(self, item_name: str, item_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей предмета"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {item_url}")
            response = requests.get(item_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] Неожиданный статус: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            page_text = soup.get_text()

            item_data = {
                'name': item_name,
                'url': item_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                item_data['name'] = title_tag.text.strip()

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        item_data['rank'] = text.replace('Ранг:', '').strip()
                    elif 'Класс:' in text:
                        item_data['class'] = text.replace('Класс:', '').strip()
                    elif 'Тип:' in text:
                        item_data['type'] = text.replace('Тип:', '').strip()
                    elif 'Редкость:' in text:
                        item_data['rarity'] = text.replace('Редкость:', '').strip()

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    item_data['region'] = region_text.replace('Доступен на регионе:', '').strip()

            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    item_data['image'] = img_src
                    item_data['image_alt'] = img_tag.get('alt', '')

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    item_data['description'] = description

            item_data['characteristics'] = self._parse_all_characteristics(soup)

            self._parse_specific_details(soup, item_data)
            
            print(f"[{self.CATEGORY_NAME}-PARSER] Успешно спарсено: {item_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] Характеристик найдено: {len(item_data['characteristics'])}")
            
            return item_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {item_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_all_characteristics(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Парсит все характеристики разными методами"""
        characteristics = {}

        char_block = soup.find('div', class_='space-y-4')
        if char_block:
            char_list = char_block.find('ul', class_='space-y-2')
            if char_list:
                items = char_list.find_all('li')
                for item in items:
                    spans = item.find_all('span')
                    if len(spans) >= 2:
                        char_name = spans[0].text.strip()
                        char_value = spans[1].text.strip()
                        characteristics[char_name] = char_value

        page_text = soup.get_text()
        if 'Характеристики' in page_text:
            chars_start = page_text.find('Характеристики')
            if chars_start != -1:
                chars_text = page_text[chars_start + len('Характеристики'):]
                
                end_match = re.search(r'\n\s*\n', chars_text)
                if end_match:
                    chars_text = chars_text[:end_match.start()]
                
                lines = chars_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            char_name = parts[0].strip()
                            char_value = parts[1].strip()
                            if char_name and char_value:
                                characteristics[char_name] = char_value
                    else:
                        match = re.search(r'([А-Яа-яA-Za-z\s\-]+?)(-?\d+[,.]?\d*\s*%?.*)', line)
                        if match and len(match.group(1).strip()) > 1:
                            char_name = match.group(1).strip()
                            char_value = match.group(2).strip()
                            characteristics[char_name] = char_value
        
        char_elements = soup.find_all(['div', 'li'], class_=re.compile(r'flex justify-between|space-y-2'))
        for elem in char_elements:
            spans = elem.find_all('span')
            if len(spans) >= 2:
                char_name = spans[0].text.strip()
                char_value = spans[1].text.strip()
                if char_name and char_value and len(char_name) > 1:
                    characteristics[char_name] = char_value
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    char_name = cells[0].text.strip()
                    char_value = cells[1].text.strip()
                    if char_name and char_value and ':' not in char_name:
                        characteristics[char_name] = char_value
        
        return characteristics
    
    def _parse_specific_details(self, soup: BeautifulSoup, item_data: Dict[str, Any]):
        """
        Метод для парсинга специфических данных категории
        Переопределите в дочерних классах
        """
        pass
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей"""
        thread = threading.Thread(target=self._parse_all_items_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_items_background(self):
        """Фоновая функция парсинга всех предметов"""
        try:
            if not self.items_data['items']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список предметов пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.items_data['items'])} предметов...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (item_name, item_url) in enumerate(zip(self.items_data['items'], self.items_data['links']), 1):
                if not item_url:
                    failed_parses += 1
                    continue
                
                with self._details_lock:
                    if item_name in self._details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.items_data['items'])}] Парсим {item_name}...")
                    details = self._parse_item_details_internal(item_name, item_url)
                    
                    if details:
                        with self._details_lock:
                            self._details_cache[item_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                    else:
                        failed_parses += 1
                    
                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {item_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Успешно: {successful_parses}, Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._details_lock:
                cache_to_save = {}
                for item_name, cache_entry in self._details_cache.items():
                    cache_to_save[item_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} предметов)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._details_lock:
                    self._details_cache.clear()
                    self._details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} предметов)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали предметов"""
        with self._details_lock:
            result = {}
            current_time = time.time()
            
            for item_name, cache_entry in self._details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._details_ttl:
                    result[item_name] = cache_entry['data']
            
            return result
    
    def refresh_all_details(self):
        """Принудительно обновляет все детали"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._details_lock:
            self._details_cache.clear()
        
        self._parse_all_items_background()
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._details_lock:
            total_items = len(self.items_data['items'])
            cached_items = len(self._details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_items': total_items,
                'cached_items': cached_items,
                'coverage_percentage': (cached_items / total_items * 100) if total_items > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._details_ttl / 3600
            }
    
    def get_data(self):
        """Основной метод для получения данных (для обратной совместимости)"""
        if not self.items_data['items']:
            self.parse_items_list()
        
        return self.items_data