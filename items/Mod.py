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

class AttachmentParser:
    """Специализированный парсер для модификаций/прицепов"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Модификации"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/attachments"
        self.user = fake_useragent.UserAgent().random

        self.attachments_data = {
            'attachments': [],  
            'images': [],        
            'links': [],         
            'quantity': []        
        }

        self._attachment_details_cache = {}
        self._attachment_details_lock = threading.Lock()
        self._attachment_details_ttl = 86400  # 24 часа
        self._CACHE_FILE = "attachment_details_cache.json"

        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }

        self._load_details_cache()
    
    
    def parse_attachments_list(self):
        """Парсит список модификаций"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            self.attachments_data = {
                'attachments': [],
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
                        self.attachments_data['attachments'].append(item_text)

                        attachment_link = ''
                        parent_a = item.find_parent('a')
                        
                        if parent_a and parent_a.get('href'):
                            attachment_link = parent_a['href']
                            
                            if attachment_link.startswith('attachments/'):
                                attachment_link = f"items/{attachment_link}"
                            elif attachment_link.startswith('/attachments/'):
                                attachment_link = f"items{attachment_link}"
                            elif 'attachments/' in attachment_link and not attachment_link.startswith('items/'):
                                attachment_link = f"items/{attachment_link}"
                            
                            if not attachment_link.startswith('http'):
                                attachment_link = urljoin(self.BASE_URL, attachment_link)
                        
                        self.attachments_data['links'].append(attachment_link)

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
                            
                            self.attachments_data['images'].append(final_img_src)

                            if i < 5:
                                print(f"[{self.CATEGORY_NAME}] Изображение {i+1}: {item_text}")
                                print(f"    URL: {final_img_src}")
                        else:
                            self.attachments_data['images'].append('')
                            if i < 10:  
                                print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено изображение для: {item_text}")
                
                self.attachments_data['quantity'].append(len(self.attachments_data['attachments']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено модификаций: {len(self.attachments_data['attachments'])}")

                self._start_background_parsing()
                
                return self.attachments_data
                
            else:
                print(f"[{self.CATEGORY_NAME}] Основной блок не найден")
                return self.attachments_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.attachments_data
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей модификаций"""
        thread = threading.Thread(target=self._parse_all_attachments_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_attachments_background(self):
        """Фоновая функция парсинга всех модификаций"""
        try:
            if not self.attachments_data['attachments']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список модификаций пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.attachments_data['attachments'])} модификаций...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (attachment_name, attachment_url) in enumerate(zip(self.attachments_data['attachments'], self.attachments_data['links']), 1):
                if not attachment_url:
                    failed_parses += 1
                    continue
                
                with self._attachment_details_lock:
                    if attachment_name in self._attachment_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.attachments_data['attachments'])}] Парсим {attachment_name}...")
                    details = self._parse_attachment_details_internal(attachment_name, attachment_url)
                    
                    if details:
                        with self._attachment_details_lock:
                            self._attachment_details_cache[attachment_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {attachment_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {attachment_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {attachment_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_attachment_details_internal(self, attachment_name: str, attachment_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей модификации"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {attachment_url}")
            
            if not attachment_url.startswith('https://stalcraft.wiki/items/attachments/'):
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠ Неправильный URL: {attachment_url}")
                print(f"[{self.CATEGORY_NAME}-PARSER] Ожидается: https://stalcraft.wiki/items/attachments/[id]")
                return None
            
            response = requests.get(attachment_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            attachment_data = {
                'name': attachment_name,
                'url': attachment_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                attachment_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {attachment_data['name']}")

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        attachment_data['rank'] = text.replace('Ранг:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Ранг: {attachment_data['rank']}")
                    elif 'Класс:' in text:
                        attachment_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {attachment_data['class']}")
                    elif 'Тип:' in text:
                        attachment_data['type'] = text.replace('Тип:', '').strip()

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    attachment_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {attachment_data['region']}")

            image_found = False

            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    attachment_data['image'] = img_src
                    attachment_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 1)")

            if not image_found:
                all_images = soup.find_all('img')
                for img_tag in all_images:
                    img_src = img_tag.get('src', '')
                    if img_src and 'exbo_item_parser' in img_src:
                        if not img_src.startswith('http'):
                            img_src = urljoin(self.BASE_URL, img_src)
                        attachment_data['image'] = img_src
                        attachment_data['image_alt'] = img_tag.get('alt', '')
                        image_found = True
                        print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 2)")
                        break

            if not image_found and hasattr(self, 'attachments_data') and 'attachments' in self.attachments_data:
                try:
                    if attachment_name in self.attachments_data['attachments']:
                        idx = self.attachments_data['attachments'].index(attachment_name)
                        if idx < len(self.attachments_data.get('images', [])):
                            list_image = self.attachments_data['images'][idx]
                            if list_image:
                                attachment_data['image'] = list_image
                                image_found = True
                                print(f"[{self.CATEGORY_NAME}-PARSER] Изображение взято из списка (метод 3)")
                except Exception as e:
                    print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при поиске изображения в списке: {e}")
            
            if image_found:
                print(f"[{self.CATEGORY_NAME}-PARSER] 🖼️ Изображение для {attachment_name}: {attachment_data.get('image', '')[:80]}...")
            else:
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠️ Изображение не найдено для {attachment_name}")
                attachment_data['image'] = None

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    attachment_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")
            
            attachment_data['characteristics'] = {}
            attachment_data['attachment_specific'] = {}
            
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
                            attachment_data['characteristics'][char_name] = char_value
                            print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value}")
            
            page_text = soup.get_text()
            
            mod_types = ['Прицел', 'Цевьё', 'Держатель', 'Ружейный', 'Тактический', 'Обвес', 
                        'Глушитель', 'Коллиматор', 'Оптический', 'Дальномер', 'Фонарь', 'Лазер']
            
            found_mod_type = None
            for mtype in mod_types:
                if mtype in page_text:
                    found_mod_type = mtype
                    attachment_data['attachment_specific']['mod_type'] = mtype
                    print(f"[{self.CATEGORY_NAME}-PARSER] Тип модификации: {mtype}")
                    break
            
            if not found_mod_type:
                name_lower = attachment_name.lower()
                if 'прицел' in name_lower or 'коллиматор' in name_lower:
                    attachment_data['attachment_specific']['mod_type'] = 'Прицел'
                elif 'цевьё' in name_lower or 'рукоятка' in name_lower:
                    attachment_data['attachment_specific']['mod_type'] = 'Цевьё'
                elif 'держатель' in name_lower or 'магазин' in name_lower:
                    attachment_data['attachment_specific']['mod_type'] = 'Держатель'
                elif 'глушитель' in name_lower:
                    attachment_data['attachment_specific']['mod_type'] = 'Глушитель'
                elif 'фонарь' in name_lower:
                    attachment_data['attachment_specific']['mod_type'] = 'Фонарь'
                elif 'лазер' in name_lower:
                    attachment_data['attachment_specific']['mod_type'] = 'Лазер'
            
            if 'description' in attachment_data:
                desc = attachment_data['description'].lower()
                if 'совместим' in desc:
                    compat_start = desc.find('совместим')
                    compat_text = desc[compat_start:compat_start+200]
                    attachment_data['attachment_specific']['compatibility_note'] = compat_text.strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Совместимость: найдено упоминание")

                compatibility_keywords = {
                    'пистолет': 'pistol',
                    'автомат': 'rifle',
                    'винтовка': 'sniper',
                    'дробовик': 'shotgun',
                    'пулемёт': 'machinegun'
                }
                
                for keyword, weapon_type in compatibility_keywords.items():
                    if keyword in desc:
                        attachment_data['attachment_specific'][f'compatible_{weapon_type}'] = True

            improvement_keys = ['Точность', 'Стабильность', 'Отдача', 'Скорость', 'Дальность', 
                              'Скрытность', 'Контроль', 'Скорострельность', 'Урон', 'Обойма']
            
            improvements = {}
            for key in improvement_keys:
                if key in attachment_data['characteristics']:
                    improvements[key] = attachment_data['characteristics'][key]
            
            if improvements:
                attachment_data['attachment_specific']['improvements'] = improvements
                print(f"[{self.CATEGORY_NAME}-PARSER] Улучшения: {len(improvements)} характеристик")

            slot_types = {
                'верхний': 'upper',
                'нижний': 'lower', 
                'боковой': 'side',
                'оптический': 'optic',
                'тактический': 'tactical',
                'дульный': 'muzzle',
                'ружейный': 'rail'
            }
            
            page_text_lower = page_text.lower()
            for slot_ru, slot_en in slot_types.items():
                if slot_ru in page_text_lower:
                    attachment_data['attachment_specific']['slot'] = slot_en
                    attachment_data['attachment_specific']['slot_ru'] = slot_ru
                    print(f"[{self.CATEGORY_NAME}-PARSER] Слот установки: {slot_ru}")
                    break

            page_text = soup.get_text()
            additional_chars = [
                ('Точность', r'Точность[:\s]+([+-]?[\d.,]+\s*%)'),
                ('Стабильность', r'Стабильность[:\s]+([+-]?[\d.,]+\s*%)'),
                ('Отдача', r'Отдача[:\s]+([+-]?[\d.,]+\s*%)'),
                ('Дальность', r'Дальность[:\s]+([+-]?[\d.,]+\s*м)'),
                ('Вес', r'Вес[:\s]+([\d.,]+\s*кг)'),
            ]
            
            for char_name, pattern in additional_chars:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match and char_name not in attachment_data['characteristics']:
                    attachment_data['characteristics'][char_name] = match.group(1).strip()
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {attachment_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Характеристик: {len(attachment_data['characteristics'])}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 🔧 Специфических данных: {len(attachment_data.get('attachment_specific', {}))}")
            
            return attachment_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {attachment_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_attachment_details(self, attachment_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали модификации из кэша или парсит заново"""
        with self._attachment_details_lock:
            if not force_refresh and attachment_name in self._attachment_details_cache:
                cache_entry = self._attachment_details_cache[attachment_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._attachment_details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {attachment_name}")
                    return cache_entry['data']
        
        if attachment_name not in self.attachments_data['attachments']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Модификация {attachment_name} не найдена в списке")
            return None
        
        idx = self.attachments_data['attachments'].index(attachment_name)
        attachment_url = self.attachments_data['links'][idx]
        
        if not attachment_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {attachment_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {attachment_name}...")
        details = self._parse_attachment_details_internal(attachment_name, attachment_url)
        
        if details:
            with self._attachment_details_lock:
                self._attachment_details_cache[attachment_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._attachment_details_lock:
                cache_to_save = {}
                for attachment_name, cache_entry in self._attachment_details_cache.items():
                    cache_to_save[attachment_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} модификаций)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._attachment_details_lock:
                    self._attachment_details_cache.clear()
                    self._attachment_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} модификаций)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_attachment_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали модификаций"""
        with self._attachment_details_lock:
            result = {}
            current_time = time.time()
            
            for attachment_name, cache_entry in self._attachment_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._attachment_details_ttl:
                    result[attachment_name] = cache_entry['data']
            
            return result
    
    def refresh_all_attachment_details(self):
        """Принудительно обновляет все детали модификаций"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._attachment_details_lock:
            self._attachment_details_cache.clear()
        
        self._parse_all_attachments_background()
        
        return True
    
    
    def get_data(self):
        """Возвращает данные о модификациях"""
        if not self.attachments_data['attachments']:
            self.parse_attachments_list()
        
        return {
            'attachments': self.attachments_data['attachments'],
            'img': self.attachments_data['images'],
            'links': self.attachments_data['links'],
            'quantity': self.attachments_data['quantity']
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._attachment_details_lock:
            total_attachments = len(self.attachments_data['attachments'])
            cached_attachments = len(self._attachment_details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._attachment_details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_attachments': total_attachments,
                'cached_attachments': cached_attachments,
                'coverage_percentage': (cached_attachments / total_attachments * 100) if total_attachments > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._attachment_details_ttl / 3600
            }


attachment_parser = AttachmentParser()

def Attachment():
    """Основная функция для парсинга модификаций"""
    return attachment_parser.parse_attachments_list()

def get_cached_attachment():
    """Возвращает данные о модификациях"""
    return attachment_parser.get_data()

def get_attachment_details(attachment_name: str, force_refresh: bool = False):
    """Получает детали модификации"""
    return attachment_parser.get_attachment_details(attachment_name, force_refresh)

def get_all_attachment_details():
    """Получает все детали модификаций"""
    return attachment_parser.get_all_attachment_details()

def refresh_all_attachment_details():
    """Обновляет все детали модификаций"""
    return attachment_parser.refresh_all_attachment_details()


