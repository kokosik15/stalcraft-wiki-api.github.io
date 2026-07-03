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

class WeaponParser:
    """Специализированный парсер для оружия"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Оружие"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/weapon"
        self.user = fake_useragent.UserAgent().random

        self.weapons_data = {
            'weapon': [],      
            'images': [],     
            'links': [],      
            'quantity': []   
        }

        self._weapon_details_cache = {}
        self._weapon_details_lock = threading.Lock()
        self._weapon_details_ttl = 86400  # 24 часа
        self._CACHE_FILE = "weapon_details_cache.json"

        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }
        
        self._load_details_cache()
    
    
    def parse_weapons_list(self):
        """Парсит список оружия"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            self.weapons_data = {
                'weapon': [],
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
                        self.weapons_data['weapon'].append(item_text)

                        weapon_link = ''
                        parent_a = item.find_parent('a')
                        
                        if parent_a and parent_a.get('href'):
                            weapon_link = parent_a['href']
                            
                            if weapon_link.startswith('weapon/'):
                                weapon_link = f"items/{weapon_link}"
                            elif weapon_link.startswith('/weapon/'):
                                weapon_link = f"items{weapon_link}"
                            elif 'weapon/' in weapon_link and not weapon_link.startswith('items/'):
                                weapon_link = f"items/{weapon_link}"
                            
                            if not weapon_link.startswith('http'):
                                weapon_link = urljoin(self.BASE_URL, weapon_link)
                        
                        self.weapons_data['links'].append(weapon_link)
                        
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
                            
                            self.weapons_data['images'].append(final_img_src)
                            
                            if i < 5:
                                print(f"[{self.CATEGORY_NAME}] Изображение {i+1}: {item_text}")
                                print(f"    URL: {final_img_src}")
                        else:
                            self.weapons_data['images'].append('')
                            if i < 10:  
                                print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено изображение для: {item_text}")
                
                self.weapons_data['quantity'].append(len(self.weapons_data['weapon']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено оружия: {len(self.weapons_data['weapon'])}")

                self._start_background_parsing()
                
                return self.weapons_data
                
            else:
                print(f"[{self.CATEGORY_NAME}] Основной блок не найден")
                return self.weapons_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.weapons_data
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей оружия"""
        thread = threading.Thread(target=self._parse_all_weapons_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_weapons_background(self):
        """Фоновая функция парсинга всего оружия"""
        try:
            if not self.weapons_data['weapon']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список оружия пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.weapons_data['weapon'])} оружия...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (weapon_name, weapon_url) in enumerate(zip(self.weapons_data['weapon'], self.weapons_data['links']), 1):
                if not weapon_url:
                    failed_parses += 1
                    continue
                
                with self._weapon_details_lock:
                    if weapon_name in self._weapon_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.weapons_data['weapon'])}] Парсим {weapon_name}...")
                    details = self._parse_weapon_details_internal(weapon_name, weapon_url)
                    
                    if details:
                        with self._weapon_details_lock:
                            self._weapon_details_cache[weapon_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {weapon_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {weapon_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {weapon_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_weapon_details_internal(self, weapon_name: str, weapon_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей оружия"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {weapon_url}")

            if not weapon_url.startswith('https://stalcraft.wiki/items/weapon/'):
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠ Неправильный URL: {weapon_url}")
                print(f"[{self.CATEGORY_NAME}-PARSER] Ожидается: https://stalcraft.wiki/items/weapon/[id]")
                return None
            
            response = requests.get(weapon_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            weapon_data = {
                'name': weapon_name,
                'url': weapon_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                weapon_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {weapon_data['name']}")

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Ранг:' in text:
                        weapon_data['rank'] = text.replace('Ранг:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Ранг: {weapon_data['rank']}")
                    elif 'Класс:' in text:
                        weapon_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {weapon_data['class']}")
                    elif 'Тип:' in text:
                        weapon_data['type'] = text.replace('Тип:', '').strip()

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    weapon_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {weapon_data['region']}")

            image_found = False

            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    weapon_data['image'] = img_src
                    weapon_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 1)")

            if not image_found:
                all_images = soup.find_all('img')
                for img_tag in all_images:
                    img_src = img_tag.get('src', '')
                    if img_src and 'exbo_item_parser' in img_src:
                        if not img_src.startswith('http'):
                            img_src = urljoin(self.BASE_URL, img_src)
                        weapon_data['image'] = img_src
                        weapon_data['image_alt'] = img_tag.get('alt', '')
                        image_found = True
                        print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено (метод 2)")
                        break

            if not image_found and hasattr(self, 'weapons_data') and 'weapon' in self.weapons_data:
                try:
                    if weapon_name in self.weapons_data['weapon']:
                        idx = self.weapons_data['weapon'].index(weapon_name)
                        if idx < len(self.weapons_data.get('images', [])):
                            list_image = self.weapons_data['images'][idx]
                            if list_image:
                                weapon_data['image'] = list_image
                                image_found = True
                                print(f"[{self.CATEGORY_NAME}-PARSER] Изображение взято из списка (метод 3)")
                except Exception as e:
                    print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при поиске изображения в списке: {e}")
            
            if image_found:
                print(f"[{self.CATEGORY_NAME}-PARSER] 🖼️ Изображение для {weapon_name}: {weapon_data.get('image', '')[:80]}...")
            else:
                print(f"[{self.CATEGORY_NAME}-PARSER] ⚠️ Изображение не найдено для {weapon_name}")
                weapon_data['image'] = None

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    weapon_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")

            weapon_data['characteristics'] = {}
            weapon_data['damage_multipliers'] = {}
            weapon_data['overheat_info'] = None
            weapon_data['damage_falloff'] = {}
            
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
                            weapon_data['characteristics'][char_name] = char_value
                            print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value}")

                damage_multiplier_div = char_block.find('p', string='Множитель урона')
                if damage_multiplier_div:
                    parent_div = damage_multiplier_div.find_parent('div')
                    if parent_div:
                        multipliers_list = parent_div.find('ul', class_='space-y-2')
                        if multipliers_list:
                            items = multipliers_list.find_all('li')
                            for item in items:
                                text = item.text.strip()
                                if ':' in text:
                                    parts = text.split(':', 1)
                                    if len(parts) == 2:
                                        multiplier_type = parts[0].strip()
                                        multiplier_value = parts[1].strip()
                                        weapon_data['damage_multipliers'][multiplier_type] = multiplier_value
                                        print(f"[{self.CATEGORY_NAME}-PARSER] Множитель: {multiplier_type} = {multiplier_value}")

                overheat_text = char_block.get_text()
                if 'перегрев' in overheat_text.lower() or 'непрерывной стрельбы' in overheat_text:
                    weapon_data['overheat_info'] = overheat_text.strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Перегрев: {weapon_data['overheat_info']}")

                if 'Падение урона на расстоянии' in char_block.get_text():
                    falloff_divs = char_block.find_all('p', class_='mt-1')
                    for falloff_div in falloff_divs:
                        text = falloff_div.text.strip()
                        if ':' in text:
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                distance = parts[0].strip()
                                damage = parts[1].strip()
                                weapon_data['damage_falloff'][distance] = damage
                                print(f"[{self.CATEGORY_NAME}-PARSER] Падение урона: {distance} = {damage}")
            
            if 'Урон' in weapon_data['characteristics']:
                damage_str = weapon_data['characteristics']['Урон']
                try:
                    weapon_data['damage_value'] = float(damage_str.replace(',', '.'))
                except:
                    pass
            
            if 'Скорострельность' in weapon_data['characteristics']:
                fire_rate = weapon_data['characteristics']['Скорострельность']
                if 'выстр/мин' in fire_rate:
                    try:
                        weapon_data['fire_rate_rpm'] = int(fire_rate.replace('выстр/мин', '').strip())
                    except:
                        pass
            
            if 'Объем магазина' in weapon_data['characteristics']:
                magazine = weapon_data['characteristics']['Объем магазина']
                if '/' in magazine:
                    parts = magazine.split('/')
                    if len(parts) == 2:
                        weapon_data['current_magazine'] = parts[0]
                        weapon_data['max_magazine'] = parts[1]
            
            if 'Перезарядка' in weapon_data['characteristics']:
                reload = weapon_data['characteristics']['Перезарядка']
                if 'с' in reload:
                    try:
                        weapon_data['reload_time_sec'] = float(reload.replace('с', '').strip())
                    except:
                        pass

            page_text = soup.get_text()
            additional_chars = [
                ('Урон', r'Урон[:\s]+([\d.,]+)'),
                ('Скорострельность', r'Скорострельность[:\s]+([\d.,]+\s*выстр/мин)'),
                ('Обойма', r'Обойма[:\s]+(\d+)'),
                ('Точность', r'Точность[:\s]+([\d.,]+)'),
            ]
            
            for char_name, pattern in additional_chars:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match and char_name not in weapon_data['characteristics']:
                    weapon_data['characteristics'][char_name] = match.group(1).strip()
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {weapon_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Характеристик: {len(weapon_data['characteristics'])}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 🎯 Множителей урона: {len(weapon_data['damage_multipliers'])}")
            
            return weapon_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {weapon_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def get_weapon_details(self, weapon_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали оружия из кэша или парсит заново"""
        with self._weapon_details_lock:
            if not force_refresh and weapon_name in self._weapon_details_cache:
                cache_entry = self._weapon_details_cache[weapon_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._weapon_details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {weapon_name}")
                    return cache_entry['data']
        
        if weapon_name not in self.weapons_data['weapon']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Оружие {weapon_name} не найдено в списке")
            return None
        
        idx = self.weapons_data['weapon'].index(weapon_name)
        weapon_url = self.weapons_data['links'][idx]
        
        if not weapon_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {weapon_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {weapon_name}...")
        details = self._parse_weapon_details_internal(weapon_name, weapon_url)
        
        if details:
            with self._weapon_details_lock:
                self._weapon_details_cache[weapon_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._weapon_details_lock:
                cache_to_save = {}
                for weapon_name, cache_entry in self._weapon_details_cache.items():
                    cache_to_save[weapon_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} оружий)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._weapon_details_lock:
                    self._weapon_details_cache.clear()
                    self._weapon_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} оружий)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_weapon_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали оружия"""
        with self._weapon_details_lock:
            result = {}
            current_time = time.time()
            
            for weapon_name, cache_entry in self._weapon_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._weapon_details_ttl:
                    result[weapon_name] = cache_entry['data']
            
            return result
    
    def refresh_all_weapon_details(self):
        """Принудительно обновляет все детали оружия"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._weapon_details_lock:
            self._weapon_details_cache.clear()
        
        self._parse_all_weapons_background()
        
        return True
    
    
    def get_data(self):
        """Возвращает данные об оружии"""
        if not self.weapons_data['weapon']:
            self.parse_weapons_list()
        
        return {
            'weapon': self.weapons_data['weapon'],
            'img': self.weapons_data['images'],
            'links': self.weapons_data['links'],
            'quantity': self.weapons_data['quantity']
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._weapon_details_lock:
            total_weapons = len(self.weapons_data['weapon'])
            cached_weapons = len(self._weapon_details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._weapon_details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_weapons': total_weapons,
                'cached_weapons': cached_weapons,
                'coverage_percentage': (cached_weapons / total_weapons * 100) if total_weapons > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._weapon_details_ttl / 3600
            }

weapon_parser = WeaponParser()

def Weapon():
    """Основная функция для парсинга оружия"""
    return weapon_parser.parse_weapons_list()

def get_cached_weapon():
    """Возвращает данные об оружии"""
    return weapon_parser.get_data()

def get_weapon_details(weapon_name: str, force_refresh: bool = False):
    """Получает детали оружия"""
    return weapon_parser.get_weapon_details(weapon_name, force_refresh)

def get_all_weapon_details():
    """Получает все детали оружия"""
    return weapon_parser.get_all_weapon_details()

def refresh_all_weapon_details():
    """Обновляет все детали оружия"""
    return weapon_parser.refresh_all_weapon_details()