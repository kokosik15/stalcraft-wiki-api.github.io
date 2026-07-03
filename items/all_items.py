import time
import json
import os
import sys
from typing import Dict, Any, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from Weapon import Weapons as WeaponsData, get_weapon_details, get_all_weapon_details
    from Bron import Brons as ArmorData, parse_armor_details
    from Art import Arts as ArtifactsData, parse_artifact_details
    from Backpacks import Backpacks as BackpacksData, parse_backpack_details
    from Containers import Containers as ContainersData, parse_container_details
    from Devices import Devices as DevicesData, parse_device_details
    from Mod import Attachments as AttachmentsData, _parse_attachment_details

    from Weapon import Weapon as WeaponParser
    from Bron import Bron as ArmorParser
    from Art import Art as ArtifactsParser
    from Backpacks import Backpack as BackpacksParser
    from Containers import Container as ContainersParser
    from Devices import Device as DevicesParser
    from Mod import Attachment as AttachmentsParser

    from cache_manager import (
        get_cached_weapon,
        get_cached_armor,
        get_cached_artifacts,
        get_cached_backpacks,
        get_cached_containers,
        get_cached_devices,
        get_cached_attachments,
        get_all_category_details,
        save_item_details
    )
    
except ImportError as e:
    print(f"[ALL-ITEMS] Ошибка импорта: {e}")
    print(f"[ALL-ITEMS] Текущая директория: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"[ALL-ITEMS] Содержимое директории: {os.listdir(os.path.dirname(os.path.abspath(__file__)))}")

    def get_cached_weapon(): return {"quantity": [0], "weapon": [], "links": [], "img": []}
    def get_cached_armor(): return {"quantity": [0], "Bron": [], "links": [], "img": []}
    def get_cached_artifacts(): return {"quantity": [0], "Art": [], "links": [], "img": []}
    def get_cached_backpacks(): return {"quantity": [0], "backpack": [], "links": [], "img": []}
    def get_cached_containers(): return {"quantity": [0], "container": [], "links": [], "img": []}
    def get_cached_devices(): return {"quantity": [0], "device": [], "links": [], "img": []}
    def get_cached_attachments(): return {"quantity": [0], "attachment": [], "links": [], "img": []}
    def get_all_category_details(category): return {}
    def save_item_details(category, name, details): pass

_ALL_ITEMS_CACHE_FILE = "all_items_cache.json"
_ALL_ITEMS_TTL = 1800  

def get_all_items_data(refresh: bool = False) -> Dict[str, Any]:
    """
    Получает все предметы из всех категорий
    """
    if not refresh:
        cached_data = _load_all_items_cache()
        if cached_data:
            cache_age = time.time() - cached_data.get('timestamp', 0)
            if cache_age < _ALL_ITEMS_TTL:
                print(f"[ALL-ITEMS] Использую кэш всех предметов (возраст: {cache_age:.0f} сек)")
                return cached_data['data']
    
    print(f"[ALL-ITEMS] Начинаю сбор данных со всех категорий...")
    start_time = time.time()
    
    all_items = {}

    categories = [
        ('weapons', get_cached_weapon, 'weapon'),
        ('armor', get_cached_armor, 'Bron'),
        ('artifacts', get_cached_artifacts, 'Art'),
        ('backpacks', get_cached_backpacks, 'backpack'),
        ('containers', get_cached_containers, 'container'),
        ('devices', get_cached_devices, 'device'),
        ('attachments', get_cached_attachments, 'attachment')
    ]
    
    for category_name, get_func, items_key in categories:
        print(f"[ALL-ITEMS] Собираю {category_name}...")
        try:
            category_data = get_func()
            category_details = get_all_category_details(category_name.rstrip('s'))

            quantity = 0
            if 'quantity' in category_data and category_data['quantity']:
                if isinstance(category_data['quantity'], list) and category_data['quantity']:
                    quantity = category_data['quantity'][0]
                elif isinstance(category_data['quantity'], int):
                    quantity = category_data['quantity']
            
            all_items[category_name] = {
                'quantity': quantity,
                'items': category_data.get(items_key, []),
                'links': category_data.get('links', []),
                'images': category_data.get('img', []),
                'categories': category_data.get('categories', []),
                'details_count': len(category_details),
                'timestamp': time.time()
            }
        except Exception as e:
            print(f"[ALL-ITEMS] Ошибка при сборе {category_name}: {e}")
            all_items[category_name] = {
                'quantity': 0,
                'items': [],
                'links': [],
                'images': [],
                'categories': [],
                'details_count': 0,
                'error': str(e)
            }

    total_items = 0
    total_details = 0
    category_stats = {}
    
    for category, data in all_items.items():
        if category != '_metadata':
            items_count = data.get('quantity', 0)
            details_count = data.get('details_count', 0)
            
            category_stats[category] = {
                'items_count': items_count,
                'details_count': details_count,
                'coverage': f"{(details_count / items_count * 100):.1f}%" if items_count > 0 else "0%"
            }
            total_items += items_count
            total_details += details_count

    all_items['_metadata'] = {
        'total_items': total_items,
        'total_details': total_details,
        'coverage': f"{(total_details / total_items * 100):.1f}%" if total_items > 0 else "0%",
        'categories': category_stats,
        'timestamp': time.time(),
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'version': '3.0'
    }
    
    elapsed = time.time() - start_time
    print(f"[ALL-ITEMS] Данные собраны за {elapsed:.2f} секунд")
    print(f"[ALL-ITEMS] Всего предметов: {total_items}, деталей: {total_details}")

    _save_all_items_cache(all_items)
    
    return all_items

def _save_all_items_cache(data: Dict[str, Any]):
    """Сохраняет кэш всех предметов на диск"""
    try:
        cache_data = {
            'data': data,
            'timestamp': time.time(),
            'version': '3.0'
        }
        
        with open(_ALL_ITEMS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"[ALL-ITEMS] Кэш всех предметов сохранен")
    except Exception as e:
        print(f"[ALL-ITEMS] Ошибка сохранения кэша: {e}")

def _load_all_items_cache() -> Optional[Dict[str, Any]]:
    """Загружает кэш всех предметов с диска"""
    try:
        if not os.path.exists(_ALL_ITEMS_CACHE_FILE):
            print(f"[ALL-ITEMS] Файл кэша всех предметов не найден")
            return None
        
        with open(_ALL_ITEMS_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        print(f"[ALL-ITEMS] Кэш всех предметов загружен")
        return cache_data
            
    except Exception as e:
        print(f"[ALL-ITEMS] Ошибка загрузки кэша: {e}")
        return None

def get_items_by_category(category: str) -> Dict[str, Any]:
    """
    Получает предметы по категории
    """
    category_map = {
        'weapons': get_cached_weapon,
        'armor': get_cached_armor,
        'artifacts': get_cached_artifacts,
        'backpacks': get_cached_backpacks,
        'containers': get_cached_containers,
        'devices': get_cached_devices,
        'attachments': get_cached_attachments
    }
    
    if category not in category_map:
        return {'error': f'Неизвестная категория: {category}'}
    
    try:
        data = category_map[category]()
        details = get_all_category_details(category.rstrip('s'))

        key_map = {
            'weapons': 'weapon',
            'armor': 'Bron',
            'artifacts': 'Art',
            'backpacks': 'backpack',
            'containers': 'container',
            'devices': 'device',
            'attachments': 'attachment'
        }
        items_key = key_map.get(category, 'items')
        
        return {
            'category': category,
            'quantity': data.get('quantity', [0])[0] if data.get('quantity') else 0,
            'items': data.get(items_key, []),
            'links': data.get('links', []),
            'images': data.get('img', []),
            'categories': data.get('categories', []),
            'details_count': len(details),
            'details_available': list(details.keys())[:10]
        }
    except Exception as e:
        return {'error': str(e)}

def get_items_statistics() -> Dict[str, Any]:
    """
    Получает статистику по всем предметам
    """
    all_data = get_all_items_data()
    
    if '_metadata' in all_data:
        return all_data['_metadata']
    
    return {'error': 'Не удалось получить статистику'}

def search_items(query: str, category: str = 'all') -> Dict[str, Any]:
    """
    Поиск предметов по названию
    """
    if not query or len(query.strip()) < 2:
        return {'error': 'Слишком короткий поисковый запрос (минимум 2 символа)'}
    
    query_lower = query.lower().strip()
    results = {}

    if category == 'all':
        categories_to_search = ['weapons', 'armor', 'artifacts', 'backpacks', 'containers', 'devices', 'attachments']
    else:
        categories_to_search = [category] if category in ['weapons', 'armor', 'artifacts', 'backpacks', 'containers', 'devices', 'attachments'] else []
    
    for cat in categories_to_search:
        try:
            data = get_items_by_category(cat)
            if 'error' not in data and 'items' in data:
                items = data['items']
                matches = [item for item in items if query_lower in item.lower()]
                
                if matches:
                    results[cat] = {
                        'count': len(matches),
                        'items': matches[:50],
                        'total_in_category': data['quantity']
                    }
        except Exception as e:
            results[cat] = {'error': str(e)}
    
    total_matches = sum(len(r.get('items', [])) if isinstance(r, dict) and 'items' in r else 0 for r in results.values())
    
    return {
        'query': query,
        'category': category,
        'total_matches': total_matches,
        'results': results,
        'timestamp': time.time()
    }

def refresh_all_items_cache():
    """Принудительно обновляет кэш всех предметов"""
    print(f"[ALL-ITEMS] Принудительное обновление кэша всех предметов...")
    return get_all_items_data(refresh=True)

def export_all_items(format: str = 'json') -> Dict[str, Any]:
    """
    Экспортирует все предметы в указанном формате
    """
    all_data = get_all_items_data()
    
    if format == 'minimal':
        minimal_data = {}
        for category, data in all_data.items():
            if category != '_metadata':
                minimal_data[category] = {
                    'count': data.get('quantity', 0),
                    'items': data.get('items', [])
                }
        return minimal_data
    
    elif format == 'detailed':
        detailed_data = {}
        for category, data in all_data.items():
            if category != '_metadata':
                items = data.get('items', [])
                details = get_all_category_details(category.rstrip('s'))
                
                detailed_items = []
                for item in items:
                    if item in details:
                        detailed_items.append({
                            'name': item,
                            'details': details[item]
                        })
                    else:
                        detailed_items.append({'name': item, 'details': None})
                
                detailed_data[category] = {
                    'count': data.get('quantity', 0),
                    'items': detailed_items
                }
        return detailed_data
    
    else:
        return all_data

def test_all_items():
    """Тестовая функция для проверки работы модуля"""
    print("="*60)
    print("ТЕСТ МОДУЛЯ ALL_ITEMS")
    print("="*60)
    
    try:
        print("\n1. Получаем статистику...")
        stats = get_items_statistics()
        if 'error' not in stats:
            print(f"Всего предметов: {stats.get('total_items', 0)}")
            print(f"Деталей собрано: {stats.get('total_details', 0)}")
            print(f"Покрытие: {stats.get('coverage', '0%')}")

            if 'categories' in stats:
                print("\nСтатистика по категориям:")
                for cat, cat_stats in stats['categories'].items():
                    print(f"  {cat}: {cat_stats['items_count']} предметов, {cat_stats['coverage']} покрытия")
        else:
            print(f"Ошибка: {stats['error']}")
        
        print("\n2. Тестируем поиск...")
        search_results = search_items("ПНВ")
        print(f"Найдено результатов: {search_results.get('total_matches', 0)}")
        
        print("\n3. Получаем предметы по категории...")
        weapons = get_items_by_category('weapons')
        print(f"Оружия: {weapons.get('quantity', 0)} шт.")
        
    except Exception as e:
        print(f"Ошибка при тестировании: {e}")
    
    print("\n" + "="*60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("="*60)

if __name__ == "__main__":
    test_all_items()