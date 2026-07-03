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

class BackpackParser:
    """Парсер для рюкзаков"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Рюкзаки"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/backpacks"
        self.user = fake_useragent.UserAgent().random
        
        # Структура данных
        self.backpacks_data = {
            'backpacks': [],    
            'images': [],      
            'links': [],       
            'quantity': []     
        }

        self._backpack_details_cache = {}
        self._backpack_details_lock = threading.Lock()
        self._backpack_details_ttl = 86400  # 24 часа
        self._CACHE_FILE = "backpack_details_cache.json"

        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }

        self._load_details_cache()

    
    def parse_backpacks_list(self):
        """Парсит список рюкзаков"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            self.backpacks_data = {
                'backpacks': [],
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
                        self.backpacks_data['backpacks'].append(item_text)

                        backpack_link = ''
                        parent_a = item.find_parent('a')
                        
                        if parent_a and parent_a.get('href'):
                            backpack_link = parent_a['href']

                            if backpack_link.startswith('backpacks/'):
                                backpack_link = f"items/{backpack_link}"
                            elif backpack_link.startswith('/backpacks/'):

                                backpack_link = f"items{backpack_link}"
                            elif 'backpacks/' in backpack_link and not backpack_link.startswith('items/'):
                                backpack_link = f"items/{backpack_link}"
                            
                            if not backpack_link.startswith('http'):
                                backpack_link = urljoin(self.BASE_URL, backpack_link)
                        
                        self.backpacks_data['links'].append(backpack_link)

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
                            
                            self.backpacks_data['images'].append(final_img_src)

                            if i < 5:
                                print(f"[{self.CATEGORY_NAME}] Изображение {i+1}: {item_text}")
                                print(f"    URL: {final_img_src}")
                        else:
                            self.backpacks_data['images'].append('')
                            if i < 10:  
                                print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено изображение для: {item_text}")
                
                self.backpacks_data['quantity'].append(len(self.backpacks_data['backpacks']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено рюкзаков: {len(self.backpacks_data['backpacks'])}")

                self._start_background_parsing()
                
                return self.backpacks_data
                
            else:
                print(f"[{self.CATEGORY_NAME}] Основной блок не найден")
                return self.backpacks_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.backpacks_data
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей рюкзаков"""
        thread = threading.Thread(target=self._parse_all_backpacks_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_backpacks_background(self):
        """Фоновая функция парсинга всех рюкзаков"""
        try:
            if not self.backpacks_data['backpacks']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список рюкзаков пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.backpacks_data['backpacks'])} рюкзаков...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (backpack_name, backpack_url) in enumerate(zip(self.backpacks_data['backpacks'], self.backpacks_data['links']), 1):
                if not backpack_url:
                    failed_parses += 1
                    continue
                
                with self._backpack_details_lock:
                    if backpack_name in self._backpack_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.backpacks_data['backpacks'])}] Парсим {backpack_name}...")
                    details = self._parse_backpack_details_internal(backpack_name, backpack_url)
                    
                    if details:
                        with self._backpack_details_lock:
                            self._backpack_details_cache[backpack_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {backpack_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {backpack_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {backpack_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_backpack_details_internal(self, backpack_name: str, backpack_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей рюкзака"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {backpack_url}")

            if not backpack_url.startswith('https://stalcraft.wiki/items/backpacks/'):
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠ Неправильный URL: {backpack_url}")
                print(f"[{self.CATEGORY_NAME}-PARSER] Ожидается: https://stalcraft.wiki/items/backpacks/[id]")
                return None
            
            response = requests.get(backpack_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            backpack_data = {
                'name': backpack_name,
                'url': backpack_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                backpack_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {backpack_data['name']}")

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        backpack_data['rank'] = text.replace('Ранг:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Ранг: {backpack_data['rank']}")
                    elif 'Класс:' in text:
                        backpack_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {backpack_data['class']}")
                    elif 'Тип:' in text:
                        backpack_data['type'] = text.replace('Тип:', '').strip()

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    backpack_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {backpack_data['region']}")

            image_found = False

            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    backpack_data['image'] = img_src
                    backpack_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 1)")

            if not image_found:
                all_images = soup.find_all('img')
                for img_tag in all_images:
                    img_src = img_tag.get('src', '')
                    if img_src and 'exbo_item_parser' in img_src:
                        if not img_src.startswith('http'):
                            img_src = urljoin(self.BASE_URL, img_src)
                        backpack_data['image'] = img_src
                        backpack_data['image_alt'] = img_tag.get('alt', '')
                        image_found = True
                        print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 2)")
                        break

            if not image_found and hasattr(self, 'backpacks_data') and 'backpacks' in self.backpacks_data:
                try:
                    if backpack_name in self.backpacks_data['backpacks']:
                        idx = self.backpacks_data['backpacks'].index(backpack_name)
                        if idx < len(self.backpacks_data.get('images', [])):
                            list_image = self.backpacks_data['images'][idx]
                            if list_image:
                                backpack_data['image'] = list_image
                                image_found = True
                                print(f"[{self.CATEGORY_NAME}-PARSER] Изображение взято из списка (метод 3)")
                except Exception as e:
                    print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при поиске изображения в списке: {e}")
            
            if image_found:
                print(f"[{self.CATEGORY_NAME}-PARSER] 🖼️ Изображение для {backpack_name}: {backpack_data.get('image', '')[:80]}...")
            else:
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠️ Изображение не найдено для {backpack_name}")
                backpack_data['image'] = None

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    backpack_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")

            backpack_data['characteristics'] = {}
            backpack_data['backpack_specific'] = {}

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
                            backpack_data['characteristics'][char_name] = char_value
                            print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value}")

            capacity_keys = ['Вместимость', 'Слоты', 'Размер', 'Объём', 'Количество слотов', 'Ёмкость']
            for key in capacity_keys:
                if key in backpack_data['characteristics']:
                    backpack_data['backpack_specific']['capacity'] = backpack_data['characteristics'][key]
                    print(f"[{self.CATEGORY_NAME}-PARSER] Вместимость: {backpack_data['backpack_specific']['capacity']}")
                    break
            
            if 'Вес' in backpack_data['characteristics']:
                weight = backpack_data['characteristics']['Вес']
                backpack_data['backpack_specific']['weight'] = weight
                print(f"[{self.CATEGORY_NAME}-PARSER] Вес: {weight}")

            protection_keys = ['Защита', 'Броня', 'Прочность', 'Защитные свойства']
            for key in protection_keys:
                if key in backpack_data['characteristics']:
                    backpack_data['backpack_specific']['protection'] = backpack_data['characteristics'][key]
                    print(f"[{self.CATEGORY_NAME}-PARSER] Защита: {backpack_data['backpack_specific']['protection']}")
                    break

            page_text = soup.get_text()
            if 'Совместим с:' in page_text or 'Подходит для:' in page_text:
                lines = page_text.split('\n')
                for line in lines:
                    if 'Совместим с:' in line or 'Подходит для:' in line:
                        compatibility = line.replace('Совместим с:', '').replace('Подходит для:', '').strip()
                        backpack_data['backpack_specific']['compatibility'] = compatibility
                        print(f"[{self.CATEGORY_NAME}-PARSER] Совместимость: {compatibility}")
                        break

            if 'description' in backpack_data:
                desc = backpack_data['description'].lower()
                compatibility_keywords = {
                    'штурмовой': 'assault',
                    'легкий': 'light',
                    'тяжелый': 'heavy',
                    'разведчик': 'scout',
                    'сапер': 'sapper',
                    'снайпер': 'sniper'
                }
                
                for keyword, armor_type in compatibility_keywords.items():
                    if keyword in desc:
                        backpack_data['backpack_specific'][f'compatible_{armor_type}'] = True

            name_lower = backpack_name.lower()
            backpack_types = {
                'штурмовой': 'assault',
                'тактический': 'tactical',
                'туристический': 'tourist',
                'походный': 'hiking',
                'экспедиционный': 'expedition',
                'компактный': 'compact',
                'увеличенный': 'extended',
                'военный': 'military'
            }
            
            for type_ru, type_en in backpack_types.items():
                if type_ru in name_lower:
                    backpack_data['backpack_specific']['backpack_type'] = type_en
                    backpack_data['backpack_specific']['backpack_type_ru'] = type_ru
                    print(f"[{self.CATEGORY_NAME}-PARSER] Тип рюкзака: {type_ru}")
                    break

            if 'Стойкость' in backpack_data['characteristics']:
                backpack_data['backpack_specific']['durability'] = backpack_data['characteristics']['Стойкость']
            if 'Уровень' in backpack_data['characteristics']:
                backpack_data['backpack_specific']['level'] = backpack_data['characteristics']['Уровень']
            if 'Размер' in backpack_data['characteristics']:
                backpack_data['backpack_specific']['size'] = backpack_data['characteristics']['Размер']

            page_text = soup.get_text()
            additional_chars = [
                ('Вместимость', r'Вместимость[:\s]+([\d.,]+\s*слотов?)'),
                ('Вес', r'Вес[:\s]+([\d.,]+\s*кг)'),
                ('Защита', r'Защита[:\s]+([\d.,]+\s*%)'),
                ('Слоты', r'Слоты[:\s]+(\d+)'),
            ]
            
            for char_name, pattern in additional_chars:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match and char_name not in backpack_data['characteristics']:
                    backpack_data['characteristics'][char_name] = match.group(1).strip()
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {backpack_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Характеристик: {len(backpack_data['characteristics'])}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 🎒 Специфических данных: {len(backpack_data.get('backpack_specific', {}))}")
            
            return backpack_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {backpack_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def get_backpack_details(self, backpack_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали рюкзака из кэша или парсит заново"""
        with self._backpack_details_lock:
            if not force_refresh and backpack_name in self._backpack_details_cache:
                cache_entry = self._backpack_details_cache[backpack_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._backpack_details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {backpack_name}")
                    return cache_entry['data']
        
        if backpack_name not in self.backpacks_data['backpacks']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Рюкзак {backpack_name} не найден в списке")
            return None
        
        idx = self.backpacks_data['backpacks'].index(backpack_name)
        backpack_url = self.backpacks_data['links'][idx]
        
        if not backpack_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {backpack_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {backpack_name}...")
        details = self._parse_backpack_details_internal(backpack_name, backpack_url)
        
        if details:
            with self._backpack_details_lock:
                self._backpack_details_cache[backpack_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._backpack_details_lock:
                cache_to_save = {}
                for backpack_name, cache_entry in self._backpack_details_cache.items():
                    cache_to_save[backpack_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} рюкзаков)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._backpack_details_lock:
                    self._backpack_details_cache.clear()
                    self._backpack_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} рюкзаков)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_backpack_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали рюкзаков"""
        with self._backpack_details_lock:
            result = {}
            current_time = time.time()
            
            for backpack_name, cache_entry in self._backpack_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._backpack_details_ttl:
                    result[backpack_name] = cache_entry['data']
            
            return result
    
    def refresh_all_backpack_details(self):
        """Принудительно обновляет все детали рюкзаков"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._backpack_details_lock:
            self._backpack_details_cache.clear()
        
        self._parse_all_backpacks_background()
        
        return True
    
    
    def get_data(self):
        """Возвращает данные о рюкзаках"""
        # Если список рюкзаков пуст, парсим его
        if not self.backpacks_data['backpacks']:
            self.parse_backpacks_list()
        
        # Для обратной совместимости с cache_manager
        return {
            'backpacks': self.backpacks_data['backpacks'],
            'img': self.backpacks_data['images'],
            'links': self.backpacks_data['links'],
            'quantity': self.backpacks_data['quantity']
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._backpack_details_lock:
            total_backpacks = len(self.backpacks_data['backpacks'])
            cached_backpacks = len(self._backpack_details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._backpack_details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_backpacks': total_backpacks,
                'cached_backpacks': cached_backpacks,
                'coverage_percentage': (cached_backpacks / total_backpacks * 100) if total_backpacks > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._backpack_details_ttl / 3600
            }



backpack_parser = BackpackParser()

def Backpack():
    """Основная функция для парсинга рюкзаков"""
    return backpack_parser.parse_backpacks_list()

def get_cached_backpack():
    """Возвращает данные о рюкзаках"""
    return backpack_parser.get_data()

def get_backpack_details(backpack_name: str, force_refresh: bool = False):
    """Получает детали рюкзака"""
    return backpack_parser.get_backpack_details(backpack_name, force_refresh)

def get_all_backpack_details():
    """Получает все детали рюкзаков"""
    return backpack_parser.get_all_backpack_details()

def refresh_all_backpack_details():
    """Обновляет все детали рюкзаков"""
    return backpack_parser.refresh_all_backpack_details()