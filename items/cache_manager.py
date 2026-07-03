import os
import time
import json
import threading
from datetime import datetime, timedelta
import schedule
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

print(f"[CACHE-MANAGER] Запуск из: {current_dir}")

_CACHE_DIR = os.path.join(os.path.dirname(current_dir), "cache_data")
_DETAILS_CACHE_DIR = os.path.join(_CACHE_DIR, "details")

_category_cache = {}
_item_details_cache = {}

class SimpleAutoParser:
    def __init__(self):
        self.categories = {
            "weapon": {
                "name": "Оружие",
                "module": "Weapon",
                "parser_func": "Weapon",
                "data_obj": "Weapons",    
                "items_key": "weapon",
                "cache_file": "weapon_details_cache.json"
            },
            "armor": {
                "name": "Броня",
                "module": "Bron",
                "parser_func": "Bron",
                "data_obj": "Brons",
                "items_key": "Bron",
                "cache_file": "armor_details_cache.json"
            },
            "artifacts": {
                "name": "Артефакты",
                "module": "Art",
                "parser_func": "Art",
                "data_obj": "Arts",
                "items_key": "Art",
                "cache_file": "artifact_details_cache.json"
            },
            "backpacks": {
                "name": "Рюкзаки",
                "module": "Backpacks",
                "parser_func": "Backpack",  
                "data_obj": "Backpacks",   
                "items_key": "backpack",
                "cache_file": "backpack_details_cache.json"
            },
            "containers": {
                "name": "Контейнеры",
                "module": "Containers",
                "parser_func": "Container",
                "data_obj": "Containers",
                "items_key": "container",
                "cache_file": "container_details_cache.json"
            },
            "devices": {
                "name": "Устройства",
                "module": "Devices",
                "parser_func": "Device",
                "data_obj": "Devices",
                "items_key": "device",
                "cache_file": "device_details_cache.json"
            },
            "attachments": {
                "name": "Модификации",
                "module": "Mod",
                "parser_func": "Attachment",
                "data_obj": "Attachments",
                "items_key": "attachment",
                "cache_file": "attachment_details_cache.json"
            }
        }
        
        self.is_parsing = False
        
    def check_cache(self, category_id):
        """Проверяет, есть ли кэш для категории"""
        config = self.categories[category_id]
        cache_file = config["cache_file"]
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    return True, len(data)
            except:
                pass
        return False, 0
    
    def load_module_direct(self, module_name):
        """Прямая загрузка модуля"""
        try:
            module = __import__(f"items.{module_name}", fromlist=[module_name])
            return module
        except Exception as e:
            print(f"[PARSER] Ошибка загрузки модуля {module_name}: {e}")
            return None
    
    def parse_category_direct(self, category_id):
        """Прямой парсинг категории - улучшенная версия"""
        if category_id not in self.categories:
            print(f"[PARSER] Неизвестная категория: {category_id}")
            return None
        
        config = self.categories[category_id]
        print(f"\n🔧 ПАРСИНГ: {config['name']}")
        
        try:
            module = self.load_module_direct(config["module"])
            if not module:
                return None
            
            print(f"✅ Модуль загружен: {config['module']}")
            
            parser_func = None
            possible_func_names = [
                config["parser_func"],
                config["parser_func"].lower(),
                config["parser_func"].capitalize(),
                f"parse_{config['module'].lower()}",
                f"get_{config['module'].lower()}",
                config["module"]
            ]
            
            for func_name in possible_func_names:
                if hasattr(module, func_name):
                    func = getattr(module, func_name)
                    if callable(func):
                        parser_func = func
                        print(f"✅ Найдена функция парсера: {func_name}")
                        break
            
            data_obj = None

            if parser_func:
                print(f"🔄 Запускаю парсер...")
                try:
                    result = parser_func()
                    print(f"✅ Парсер выполнен")
                    
                    if result and isinstance(result, dict):
                        data_obj = result
                        print(f"📦 Данные получены от парсера")
                except Exception as e:
                    print(f"⚠️  Ошибка парсера: {e}")
            else:
                print(f"ℹ️  Парсер не найден, ищу готовые данные")
            
            if not data_obj:
                possible_data_names = [
                    config["data_obj"],
                    config["data_obj"].lower(),
                    config["data_obj"].capitalize(),
                    config["module"],
                    config["module"].lower(),
                    config["module"].capitalize()
                ]
                
                for data_name in possible_data_names:
                    if hasattr(module, data_name):
                        data_obj = getattr(module, data_name)
                        print(f"📦 Данные найдены: {data_name}")
                        break
            
            if not data_obj:
                print(f"❌ Данные не найдены!")
                attrs = [a for a in dir(module) if not a.startswith('_')]
                print(f"   Доступные атрибуты: {attrs}")
                return None
            
            print(f"📦 Тип данных: {type(data_obj).__name__}")
            
            if isinstance(data_obj, dict):
                print(f"📊 Ключи в данных: {list(data_obj.keys())}")
                for key, value in data_obj.items():
                    if isinstance(value, list):
                        print(f"   '{key}': список [{len(value)}]")
                    else:
                        print(f"   '{key}': {type(value).__name__}")
            elif hasattr(data_obj, '__dict__'):
                print(f"📊 Атрибуты объекта: {list(data_obj.__dict__.keys())}")

            items_list = []
            found_key = None

            possible_keys = [
                config["items_key"],
                config["items_key"].lower(),
                config["items_key"].capitalize(),
                config["module"].lower(),
                "items",
                "list",
                "names"
            ]
            
            if isinstance(data_obj, dict):
                for key in possible_keys:
                    if key in data_obj and isinstance(data_obj[key], list) and data_obj[key]:
                        items_list = data_obj[key]
                        found_key = key
                        print(f"✅ Найден список в ключе '{key}': {len(items_list)} элементов")
                        break

                if not items_list:
                    for key, value in data_obj.items():
                        if isinstance(value, list) and value and len(value) > 0:
                            if isinstance(value[0], str):
                                items_list = value
                                found_key = key
                                print(f"✅ Найден список в ключе '{key}' (автоопределение): {len(items_list)} элементов")
                                break
            
            elif hasattr(data_obj, '__dict__'):
                for attr_name in data_obj.__dict__.keys():
                    attr = getattr(data_obj, attr_name)
                    if isinstance(attr, list) and attr and len(attr) > 0:
                        if isinstance(attr[0], str):
                            items_list = attr
                            found_key = attr_name
                            print(f"✅ Найден список в атрибуте '{attr_name}': {len(items_list)} элементов")
                            break
            
            if not items_list:
                print(f"❌ Не удалось найти список предметов!")
                return None
            
            print(f"\n🎉 УСПЕХ: {config['name']} - {len(items_list)} предметов")
            if items_list:
                print(f"📝 Примеры: {items_list[:5]}")
            
            _category_cache[category_id] = {
                "data": data_obj,
                "timestamp": time.time()
            }
            
            self.save_to_json(category_id, items_list, data_obj)
            
            return data_obj
            
        except Exception as e:
            print(f"💥 Ошибка парсинга {config['name']}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_to_json(self, category_id, items_list, data_obj):
        """Сохраняет данные в JSON файл"""
        config = self.categories[category_id]
        cache_file = config["cache_file"]
        
        try:
            items_data = {}
            
            for item_name in items_list[:20]:
                items_data[item_name] = {
                    "name": item_name,
                    "category": category_id,
                    "timestamp": time.time(),
                    "parsed_at": datetime.now().isoformat()
                }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(items_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Сохранено в {cache_file}: {len(items_data)} предметов")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения в JSON: {e}")
            
        def debug_data_structure(data_obj):
            """Показывает структуру данных для отладки"""
            if isinstance(data_obj, dict):
                print(f"[DEBUG] Словарь с ключами: {list(data_obj.keys())}")
                for key, value in list(data_obj.items())[:5]:
                    if isinstance(value, list):
                        print(f"[DEBUG]   {key}: список [{len(value)}] - пример: {value[:3]}")
                    else:
                        print(f"[DEBUG]   {key}: {type(value).__name__} = {str(value)[:50]}...")
            elif hasattr(data_obj, '__dict__'):
                print(f"[DEBUG] Объект с атрибутами: {list(data_obj.__dict__.keys())}")

    def start_auto_parsing(self, categories=None):
        """Запускает авто-парсинг"""
        if self.is_parsing:
            print("[AUTO-PARSER] Парсинг уже запущен")
            return False
        
        if categories is None:
            categories = []
            for cat_id in self.categories:
                has_cache, count = self.check_cache(cat_id)
                if not has_cache or count < 3:
                    categories.append(cat_id)
        
        if not categories:
            print("[AUTO-PARSER] Все категории имеют данные")
            return True
        
        print(f"\n🤖 ЗАПУСК АВТО-ПАРСИНГА")
        print(f"📋 Категории: {len(categories)}")
        for cat_id in categories:
            print(f"  • {self.categories[cat_id]['name']}")
        
        self.is_parsing = True

        def parse_thread():
            try:
                for i, cat_id in enumerate(categories):
                    print(f"\n[{i+1}/{len(categories)}] 📦 {self.categories[cat_id]['name']}")
                    print("-" * 40)
                    
                    self.parse_category_direct(cat_id)

                    if i < len(categories) - 1:
                        time.sleep(3)
                
                print(f"\n✅ АВТО-ПАРСИНГ ЗАВЕРШЕН")
                
            except Exception as e:
                print(f"💥 Ошибка авто-парсинга: {e}")
            finally:
                self.is_parsing = False
        
        thread = threading.Thread(target=parse_thread, daemon=True)
        thread.start()
        
        return True
    
    def get_status(self):
        """Возвращает статус парсинга"""
        categories_status = {}
        for cat_id, config in self.categories.items():
            has_cache, count = self.check_cache(cat_id)
            categories_status[cat_id] = {
                "name": config["name"],
                "has_cache": has_cache,
                "items_count": count,
                "cache_file": config["cache_file"]
            }
        
        return {
            "is_parsing": self.is_parsing,
            "categories": categories_status,
            "timestamp": datetime.now().isoformat()
        }

auto_parser = SimpleAutoParser()

def get_cached_weapon(refresh=False):
    """Получить оружие"""
    category = "weapon"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_cached_armor(refresh=False):
    """Получить броню"""
    category = "armor"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_cached_artifacts(refresh=False):
    """Получить артефакты"""
    category = "artifacts"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_cached_backpacks(refresh=False):
    """Получить рюкзаки"""
    category = "backpacks"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_cached_containers(refresh=False):
    """Получить контейнеры"""
    category = "containers"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_cached_devices(refresh=False):
    """Получить устройства"""
    category = "devices"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_cached_attachments(refresh=False):
    """Получить модификации"""
    category = "attachments"
    
    if refresh or category not in _category_cache:
        print(f"[CACHE] Загружаю {category}...")
        data = auto_parser.parse_category_direct(category)
        if data:
            _category_cache[category] = {
                "data": data,
                "timestamp": time.time()
            }
    
    if category in _category_cache:
        return _category_cache[category]["data"]
    return {}

def get_item_details(category, item_name, force_refresh=False):
    """Заглушка для деталей"""
    return {"name": item_name, "category": category}

def get_all_category_details(category):
    """Заглушка для всех деталей"""
    return {}

def start_auto_parsing(categories=None):
    """Запустить авто-парсинг"""
    return auto_parser.start_auto_parsing(categories)

def get_auto_parse_status():
    """Получить статус авто-парсинга"""
    return auto_parser.get_status()

def get_cached_data():
    """Получить все данные"""
    weapons = get_cached_weapon()
    armor = get_cached_armor()
    artifacts = get_cached_artifacts()
    backpacks = get_cached_backpacks()
    containers = get_cached_containers()
    devices = get_cached_devices()
    attachments = get_cached_attachments()
    
    return {
        "weapons": weapons,
        "armor": armor,
        "artifacts": artifacts,
        "backpacks": backpacks,
        "containers": containers,
        "devices": devices,
        "attachments": attachments,
        "_metadata": {
            "timestamp": time.time(),
            "generated_at": datetime.now().isoformat()
        }
    }

print("[CACHE-MANAGER] Инициализация...")

print("[CACHE-MANAGER] Проверка кэшей...")
for cat_id in auto_parser.categories:
    has_cache, count = auto_parser.check_cache(cat_id)
    status = "✅" if has_cache else "❌"
    print(f"  {status} {auto_parser.categories[cat_id]['name']}: {count} предметов")

need_parsing = []
for cat_id in auto_parser.categories:
    has_cache, count = auto_parser.check_cache(cat_id)
    if not has_cache or count < 3:
        need_parsing.append(cat_id)

if need_parsing:
    print(f"[CACHE-MANAGER] Запуск авто-парсинга для {len(need_parsing)} категорий...")
    threading.Timer(5, lambda: start_auto_parsing(need_parsing)).start()
else:
    print("[CACHE-MANAGER] Все категории имеют данные")

print("[CACHE-MANAGER] Инициализация завершена ✅")