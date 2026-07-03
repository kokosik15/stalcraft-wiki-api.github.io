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

class ArtifactParser:
    """Парсер для артефактов"""
    
    def __init__(self):
        self.BASE_URL = "https://stalcraft.wiki"
        self.CATEGORY_NAME = "Артефакты"
        self.CATEGORY_URL = "https://stalcraft.wiki/items/artefacts"  
        self.user = fake_useragent.UserAgent().random

        self.artifacts_data = {
            'artifacts': [],     
            'images': [],        
            'links': [],         
            'quantity': []        
        }

        self._artifact_details_cache = {}
        self._artifact_details_lock = threading.Lock()
        self._artifact_details_ttl = 86400  # 24 часа
        self._CACHE_FILE = "artifact_details_cache.json"

        self.headers = {
            'user-agent': self.user,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://stalcraft.wiki/',
        }

        self._load_details_cache()
    
    
    def parse_artifacts_list(self):
        """Парсит список артефактов"""
        try:
            print(f"[{self.CATEGORY_NAME}] Начинаю парсинг списка...")
            start_time = time.time()
            
            response = requests.get(self.CATEGORY_URL, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            self.artifacts_data = {
                'artifacts': [],
                'images': [],
                'links': [],
                'quantity': []
            }

            print(f"[{self.CATEGORY_NAME}] Первые 500 символов ответа:")
            print(response.text[:500])
            
            grid_div = None

            grid_div = soup.find('div', class_=lambda x: x and 'grid' in x and 'gap-3' in x)

            if not grid_div:
                grid_div = soup.find('div', class_='grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3')

            if not grid_div:
                all_divs = soup.find_all('div')
                for div in all_divs:
                    if div.find('a') and 'Морозец' in str(div):  
                        grid_div = div
                        break
            
            if grid_div:
                print(f"[{self.CATEGORY_NAME}] Grid блок найден!")

                artifact_cards = []

                artifact_cards = grid_div.find_all('a')

                if not artifact_cards:
                    artifact_cards = grid_div.find_all('a', class_=lambda x: x and 'group' in x and 'relative' in x)
                
                print(f"[{self.CATEGORY_NAME}] Найдено карточек (всего <a>): {len(artifact_cards)}")
                
                processed_count = 0
                
                for card in artifact_cards:
                    try:
                        if not card.get('href'):
                            continue

                        name_tag = card.find('p', class_=lambda x: x and 'truncate' in x and 'font-medium' in x)
                        if not name_tag:
                            name_tag = card.find('p')
                        
                        if name_tag:
                            artifact_name = name_tag.text.strip()

                            if not artifact_name or len(artifact_name) < 2:
                                continue
                            
                            self.artifacts_data['artifacts'].append(artifact_name)

                            artifact_link = ''
                            href = card.get('href', '')
                            
                            if href:
                                if href.startswith('artefacts/'):
                                    artifact_link = f"items/{href}"
                                elif href.startswith('/artefacts/'):
                                    artifact_link = f"items{href}"
                                elif 'artefacts/' in href and not href.startswith('items/'):
                                    artifact_link = f"items/{href}"
                                elif href.startswith('items/artefacts/'):
                                    artifact_link = href
                                
                                if artifact_link and not artifact_link.startswith('http'):
                                    artifact_link = urljoin(self.BASE_URL, artifact_link)
                            
                            self.artifacts_data['links'].append(artifact_link)

                            img_src = ''
                            img_tag = card.find('img')
                            if img_tag and img_tag.get('src'):
                                img_src = img_tag['src']
                            
                            if img_src:
                                if img_src.startswith('http'):
                                    final_img_src = img_src
                                elif img_src.startswith('/'):
                                    final_img_src = urljoin(self.BASE_URL, img_src)
                                elif not img_src.startswith(('http', '/')):
                                    final_img_src = urljoin(self.BASE_URL, '/' + img_src.lstrip('/'))
                                else:
                                    final_img_src = img_src
                                
                                self.artifacts_data['images'].append(final_img_src)
                            else:
                                self.artifacts_data['images'].append('')
                            
                            processed_count += 1
                            print(f"[{self.CATEGORY_NAME}] Добавлен: {artifact_name} (ссылка: {href})")
                        
                    except Exception as e:
                        print(f"[{self.CATEGORY_NAME}] Ошибка при обработке карточки: {e}")
                        continue
                
                print(f"[{self.CATEGORY_NAME}] Обработано карточек: {processed_count}")
                
                self.artifacts_data['quantity'].append(len(self.artifacts_data['artifacts']))
                
                elapsed = time.time() - start_time
                print(f"[{self.CATEGORY_NAME}] Парсинг завершен за {elapsed:.2f} секунд")
                print(f"[{self.CATEGORY_NAME}] Получено артефактов: {len(self.artifacts_data['artifacts'])}")

                for i in range(min(5, len(self.artifacts_data['artifacts']))):
                    print(f"  {i+1}. {self.artifacts_data['artifacts'][i]}")
                
                if self.artifacts_data['artifacts']:
                    self._start_background_parsing()
                else:
                    print(f"[{self.CATEGORY_NAME}] ⚠️ Не найдено ни одного артефакта!")
                    print(f"[{self.CATEGORY_NAME}] Весь HTML grid блока:")
                    print(grid_div.prettify()[:1000])  
                
                return self.artifacts_data
                
            else:
                print(f"[{self.CATEGORY_NAME}] Grid блок не найден")
                print(f"[{self.CATEGORY_NAME}] Ищем все элементы с классом 'grid':")
                grid_elements = soup.find_all(class_=lambda x: x and 'grid' in str(x))
                print(f"[{self.CATEGORY_NAME}] Найдено grid элементов: {len(grid_elements)}")
                
                for i, element in enumerate(grid_elements[:5]):
                    classes = element.get('class', [])
                    print(f"[{self.CATEGORY_NAME}] Grid {i}: классы={classes}, текст={element.text[:100]}...")
                
                return self.artifacts_data
                
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}] Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return self.artifacts_data
    
    def _start_background_parsing(self):
        """Запускает фоновый парсинг деталей артефактов"""
        thread = threading.Thread(target=self._parse_all_artifacts_background, daemon=True)
        thread.start()
        print(f"[{self.CATEGORY_NAME}] Фоновый парсинг деталей запущен")
    
    def _parse_all_artifacts_background(self):
        """Фоновая функция парсинга всех артефактов"""
        try:
            if not self.artifacts_data['artifacts']:
                print(f"[{self.CATEGORY_NAME}-BACKGROUND] Список артефактов пуст")
                return
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Начинаю фоновый парсинг {len(self.artifacts_data['artifacts'])} артефактов...")
            
            successful_parses = 0
            failed_parses = 0
            
            for i, (artifact_name, artifact_url) in enumerate(zip(self.artifacts_data['artifacts'], self.artifacts_data['links']), 1):
                if not artifact_url:
                    failed_parses += 1
                    continue
                
                with self._artifact_details_lock:
                    if artifact_name in self._artifact_details_cache:
                        successful_parses += 1
                        continue
                
                try:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                    
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] [{i}/{len(self.artifacts_data['artifacts'])}] Парсим {artifact_name}...")
                    details = self._parse_artifact_details_internal(artifact_name, artifact_url)
                    
                    if details:
                        with self._artifact_details_lock:
                            self._artifact_details_cache[artifact_name] = {
                                'data': details,
                                'timestamp': time.time()
                            }
                        successful_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {artifact_name}")
                    else:
                        failed_parses += 1
                        print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✗ Не удалось: {artifact_name}")

                    if i % 10 == 0:
                        self._save_details_cache()
                    
                except Exception as e:
                    failed_parses += 1
                    print(f"[{self.CATEGORY_NAME}-BACKGROUND] Ошибка при парсинге {artifact_name}: {e}")
            
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Фоновый парсинг завершен.")
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] ✓ Успешно: {successful_parses}, ✗ Не удалось: {failed_parses}")
            
            self._save_details_cache()
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-BACKGROUND] Критическая ошибка фонового парсинга: {e}")
    
    def _parse_artifact_details_internal(self, artifact_name: str, artifact_url: str) -> Optional[Dict[str, Any]]:
        """Внутренняя функция парсинга деталей артефактов"""
        try:
            print(f"[{self.CATEGORY_NAME}-PARSER] Загружаю страницу: {artifact_url}")
            
            response = requests.get(artifact_url, headers=self.headers, timeout=15)
            print(f"[{self.CATEGORY_NAME}-PARSER] Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[{self.CATEGORY_NAME}-PARSER] ❌ Ошибка загрузки: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            artifact_data = {
                'name': artifact_name,
                'url': artifact_url,
                'category': self.CATEGORY_NAME,
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            title_tag = soup.find('h1', class_='text-2xl font-semibold text-foreground')
            if title_tag:
                artifact_data['name'] = title_tag.text.strip()
                print(f"[{self.CATEGORY_NAME}-PARSER] Название: {artifact_data['name']}")

            info_block = soup.find('div', class_='flex-1 space-y-2')
            if info_block:
                info_items = info_block.find_all('div', class_='text-sm')
                for item in info_items:
                    text = item.text.strip()
                    if 'Класс:' in text:
                        artifact_data['class'] = text.replace('Класс:', '').strip()
                        print(f"[{self.CATEGORY_NAME}-PARSER] Класс: {artifact_data['class']}")

            region_div = soup.find('div', class_='flex items-center gap-2 pt-2 text-sm')
            if region_div:
                region_text = region_div.text.strip()
                if 'Доступен на регионе:' in region_text:
                    artifact_data['region'] = region_text.replace('Доступен на регионе:', '').strip()
                    print(f"[{self.CATEGORY_NAME}-PARSER] Регион: {artifact_data['region']}")

            image_found = False
            img_div = soup.find('div', class_='flex h-40 w-40 items-center justify-center')
            if img_div:
                img_tag = img_div.find('img')
                if img_tag and img_tag.get('src'):
                    img_src = img_tag['src']
                    if not img_src.startswith('http'):
                        img_src = urljoin(self.BASE_URL, img_src)
                    artifact_data['image'] = img_src
                    artifact_data['image_alt'] = img_tag.get('alt', '')
                    image_found = True
                    print(f"[{self.CATEGORY_NAME}-PARSER] Изображение найдено")
            
            if not image_found:
                if artifact_name in self.artifacts_data['artifacts']:
                    idx = self.artifacts_data['artifacts'].index(artifact_name)
                    if idx < len(self.artifacts_data.get('images', [])):
                        list_image = self.artifacts_data['images'][idx]
                        if list_image:
                            artifact_data['image'] = list_image
                            image_found = True
            
            if not image_found:
                artifact_data['image'] = None

            description_div = soup.find('div', class_='mt-6 border-t border-foreground/10 pt-6')
            if description_div:
                p_tag = description_div.find('p')
                if p_tag:
                    description = p_tag.text.strip()
                    description = re.sub(r'\s+', ' ', description)
                    artifact_data['description'] = description
                    print(f"[{self.CATEGORY_NAME}-PARSER] Описание: {len(description)} символов")

            artifact_data['characteristics'] = {}
            artifact_data['additional_characteristics'] = {}

            char_sections = soup.find_all('div', class_='rounded-lg border border-foreground/10 bg-secondary/50 p-4 backdrop-blur-sm')
            
            for char_section in char_sections:
                header = char_section.find('h2', class_='text-xl font-semibold text-foreground')
                if header and 'Характеристики' in header.text:

                    main_char_list = char_section.find('ul', class_='space-y-2')
                    if main_char_list:
                        items = main_char_list.find_all('li')
                        for item in items:
                            spans = item.find_all('span')
                            if len(spans) >= 2:
                                char_name = spans[0].text.strip()
                                char_value = spans[1].text.strip()
                                artifact_data['characteristics'][char_name] = char_value
                                print(f"[{self.CATEGORY_NAME}-PARSER] Характеристика: {char_name} = {char_value}")

                    additional_header = char_section.find('p', class_='mb-3 text-sm font-medium text-foreground/80')
                    if additional_header and 'Дополнительные характеристики' in additional_header.text:
                        next_sibling = additional_header.find_next_sibling('ul')
                        if next_sibling and 'space-y-2' in next_sibling.get('class', []):
                            items = next_sibling.find_all('li')
                            for item in items:
                                spans = item.find_all('span')
                                if len(spans) >= 2:
                                    char_name = spans[0].text.strip()
                                    char_value = spans[1].text.strip()
                                    artifact_data['additional_characteristics'][char_name] = char_value
                                    print(f"[{self.CATEGORY_NAME}-PARSER] Доп. характеристика: {char_name} = {char_value}")

            page_text = soup.get_text()

            if 'Эффект' in page_text:
                effect_start = page_text.find('Эффект')
                if effect_start != -1:
                    effect_end = page_text.find('\n\n', effect_start)
                    if effect_end == -1:
                        effect_end = len(page_text)
                    
                    effect_text = page_text[effect_start:effect_end].strip()
                    artifact_data['effect'] = effect_text
                    print(f"[{self.CATEGORY_NAME}-PARSER] Эффект: {effect_text[:100]}...")

            if 'Аномалия' in page_text:
                anomaly_match = page_text.find('Аномалия')
                if anomaly_match != -1:
                    lines = page_text[anomaly_match:].split('\n')
                    for line in lines[:3]:
                        if line.strip() and 'Аномалия' not in line:
                            artifact_data['anomaly'] = line.strip()
                            print(f"[{self.CATEGORY_NAME}-PARSER] Аномалия: {artifact_data['anomaly']}")
                            break

            if 'characteristics' in artifact_data and 'Вес' in artifact_data['characteristics']:
                weight = artifact_data['characteristics']['Вес']
                try:
                    if 'кг' in weight:
                        kg = float(weight.replace('кг', '').strip())
                        artifact_data['weight_grams'] = kg * 1000
                    elif 'г' in weight:
                        artifact_data['weight_grams'] = float(weight.replace('г', '').strip())
                    print(f"[{self.CATEGORY_NAME}-PARSER] Вес в граммах: {artifact_data.get('weight_grams')}")
                except:
                    pass

            artifact_data['positive_effects'] = []
            artifact_data['negative_effects'] = []

            if 'characteristics' in artifact_data:
                for char_name, char_value in artifact_data['characteristics'].items():
                    if char_value.startswith('-'):
                        artifact_data['negative_effects'].append({
                            'name': char_name,
                            'value': char_value
                        })
                    else:
                        artifact_data['positive_effects'].append({
                            'name': char_name,
                            'value': char_value
                        })
            
            print(f"[{self.CATEGORY_NAME}-PARSER] ✓ Успешно спарсено: {artifact_name}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Основных характеристик: {len(artifact_data.get('characteristics', {}))}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📊 Доп. характеристик: {len(artifact_data.get('additional_characteristics', {}))}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📈 Позитивных эффектов: {len(artifact_data.get('positive_effects', []))}")
            print(f"[{self.CATEGORY_NAME}-PARSER] 📉 Негативных эффектов: {len(artifact_data.get('negative_effects', []))}")
            
            return artifact_data
            
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-PARSER] Ошибка при парсинге {artifact_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def get_artifact_details(self, artifact_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Получает детали артефакта из кэша или парсит заново"""
        with self._artifact_details_lock:
            if not force_refresh and artifact_name in self._artifact_details_cache:
                cache_entry = self._artifact_details_cache[artifact_name]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self._artifact_details_ttl:
                    print(f"[{self.CATEGORY_NAME}-DETAILS] Использую кэш для {artifact_name}")
                    return cache_entry['data']
        
        if artifact_name not in self.artifacts_data['artifacts']:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Артефакт {artifact_name} не найден в списке")
            return None
        
        idx = self.artifacts_data['artifacts'].index(artifact_name)
        artifact_url = self.artifacts_data['links'][idx]
        
        if not artifact_url:
            print(f"[{self.CATEGORY_NAME}-DETAILS] Нет URL для {artifact_name}")
            return None
        
        print(f"[{self.CATEGORY_NAME}-DETAILS] Парсим {artifact_name}...")
        details = self._parse_artifact_details_internal(artifact_name, artifact_url)
        
        if details:
            with self._artifact_details_lock:
                self._artifact_details_cache[artifact_name] = {
                    'data': details,
                    'timestamp': time.time()
                }
            
            self._save_details_cache()
        
        return details
    
    def _save_details_cache(self):
        """Сохраняет кэш деталей в файл"""
        try:
            with self._artifact_details_lock:
                cache_to_save = {}
                for artifact_name, cache_entry in self._artifact_details_cache.items():
                    cache_to_save[artifact_name] = {
                        'data': cache_entry['data'],
                        'timestamp': cache_entry['timestamp']
                    }
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
            
            print(f"[{self.CATEGORY_NAME}-CACHE] Кэш сохранен ({len(cache_to_save)} артефактов)")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка сохранения кэша: {e}")
    
    def _load_details_cache(self):
        """Загружает кэш деталей из файла"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                with self._artifact_details_lock:
                    self._artifact_details_cache.clear()
                    self._artifact_details_cache.update(loaded_cache)
                
                print(f"[{self.CATEGORY_NAME}-CACHE] Кэш загружен ({len(loaded_cache)} артефактов)")
            else:
                print(f"[{self.CATEGORY_NAME}-CACHE] Файл кэша не найден")
        except Exception as e:
            print(f"[{self.CATEGORY_NAME}-CACHE] Ошибка загрузки кэша: {e}")
    
    def get_all_artifact_details(self) -> Dict[str, Dict[str, Any]]:
        """Получает все доступные детали артефактов"""
        with self._artifact_details_lock:
            result = {}
            current_time = time.time()
            
            for artifact_name, cache_entry in self._artifact_details_cache.items():
                cache_age = current_time - cache_entry['timestamp']
                if cache_age < self._artifact_details_ttl:
                    result[artifact_name] = cache_entry['data']
            
            return result
    
    def refresh_all_artifact_details(self):
        """Принудительно обновляет все детали артефактов"""
        print(f"[{self.CATEGORY_NAME}] Начинаю принудительное обновление всех деталей...")
        
        with self._artifact_details_lock:
            self._artifact_details_cache.clear()
        
        self._parse_all_artifacts_background()
        
        return True

    
    def get_data(self):
        """Возвращает данные об артефактах"""
        if not self.artifacts_data['artifacts']:
            self.parse_artifacts_list()

        return {
            'artifacts': self.artifacts_data['artifacts'],
            'img': self.artifacts_data['images'],
            'links': self.artifacts_data['links'],
            'quantity': self.artifacts_data['quantity']
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по парсингу"""
        with self._artifact_details_lock:
            total_artifacts = len(self.artifacts_data['artifacts'])
            cached_artifacts = len(self._artifact_details_cache)
            
            current_time = time.time()
            cache_ages = []
            for cache_entry in self._artifact_details_cache.values():
                cache_ages.append(current_time - cache_entry['timestamp'])
            
            avg_age = sum(cache_ages) / len(cache_ages) if cache_ages else 0
            
            return {
                'category': self.CATEGORY_NAME,
                'total_artifacts': total_artifacts,
                'cached_artifacts': cached_artifacts,
                'coverage_percentage': (cached_artifacts / total_artifacts * 100) if total_artifacts > 0 else 0,
                'avg_cache_age_hours': avg_age / 3600,
                'cache_expires_in_hours': self._artifact_details_ttl / 3600
            }


artifact_parser = ArtifactParser()

def Art():
    """Основная функция для парсинга артефактов"""
    return artifact_parser.parse_artifacts_list()

def get_cached_artifact():
    """Возвращает данные об артефактах"""
    return artifact_parser.get_data()

def get_artifact_details(artifact_name: str, force_refresh: bool = False):
    """Получает детали артефакта"""
    return artifact_parser.get_artifact_details(artifact_name, force_refresh)

def get_all_artifact_details():
    """Получает все детали артефактов"""
    return artifact_parser.get_all_artifact_details()

def refresh_all_artifact_details():
    """Обновляет все детали артефактов"""
    return artifact_parser.refresh_all_artifact_details()