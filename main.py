import os
import json
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, List, Any
import uvicorn
import sys

def _extract_image_from_cache(cache_item):
    """Извлекает URL изображения из кэшированных данных"""
    if isinstance(cache_item, dict):
        if 'data' in cache_item and isinstance(cache_item['data'], dict):
            return cache_item['data'].get('image')
        return cache_item.get('image')
    return None

def read_cache_file(category: str):
    """Читает файл кэша для категории из корневой папки"""
    cache_files = {
        "weapons": "weapon_details_cache.json",
        "armor": "armor_details_cache.json", 
        "artifacts": "artifact_details_cache.json",
        "backpacks": "backpack_details_cache.json",
        "containers": "container_details_cache.json",
        "devices": "device_details_cache.json",
        "attachments": "attachment_details_cache.json"
    }
    
    if category not in cache_files:
        return None
    
    cache_file = cache_files[category]
    
    if not os.path.exists(cache_file):
        print(f"⚠️ Файл кэша не найден: {cache_file}")
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"[CACHE] Загружен {cache_file}: {len(data)} предметов")
            return data
    except Exception as e:
        print(f"❌ Ошибка чтения кэша {cache_file}: {e}")
        return None

def get_item_full_from_cache(category: str, item_name: str):
    """Получить полную структуру предмета из файла кэша"""
    cache_data = read_cache_file(category)
    
    if not cache_data:
        return None
    
    if item_name not in cache_data:
        return None
    
    cached_item = cache_data[item_name]

    if isinstance(cached_item, dict) and 'data' in cached_item:
        return cached_item
    else:
        return {
            "data": cached_item,
            "timestamp": time.time()
        }

def get_item_full_from_cache(category: str, item_name: str):
    """Получить полную структуру предмета из файла кэша"""
    cache_data = read_cache_file(category)
    
    if not cache_data:
        print(f"[CACHE] Нет данных для категории {category}")
        return None

    if item_name not in cache_data:
        print(f"[CACHE] Предмет не найден: {item_name}")
        return None
    
    cached_item = cache_data[item_name]
    print(f"[CACHE DEBUG] Найден предмет: {item_name}")
    print(f"[CACHE DEBUG] Тип данных: {type(cached_item)}")

    if isinstance(cached_item, dict):
        if 'data' in cached_item:
            print(f"[CACHE DEBUG] Формат Weapon.py (с 'data')")
            return cached_item
        
        elif 'name' in cached_item and 'category' in cached_item:
            print(f"[CACHE DEBUG] Формат Bron.py (прямые данные)")
            return {
                "data": cached_item,  # Обернем в "data" для единого формата
                "timestamp": cached_item.get('timestamp', time.time())
            }
        
        else:
            print(f"[CACHE DEBUG] Неизвестный формат словаря, оборачиваем в 'data'")
            return {
                "data": cached_item,
                "timestamp": time.time()
            }
    
    else:
        print(f"[CACHE DEBUG] Не словарь, оборачиваем в 'data'")
        return {
            "data": cached_item,
            "timestamp": time.time()
        }
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

PORT = 5000

try:
    from items.cache_manager import (
        get_cached_weapon, get_cached_armor, get_cached_artifacts,
        get_cached_backpacks, get_cached_containers, get_cached_devices,
        get_cached_attachments
    )
    
    try:
        from items.cache_manager import get_item_details, get_all_category_details
        DETAILS_AVAILABLE = True
    except ImportError:
        DETAILS_AVAILABLE = False
        print("⚠️  Функции деталей не найдены в cache_manager")
    
    try:
        from items.cache_manager import start_auto_parsing, get_auto_parse_status
        AUTO_PARSE_AVAILABLE = True
    except ImportError:
        AUTO_PARSE_AVAILABLE = False
        print("⚠️  Функции авто-парсинга не найдены в cache_manager")
    
    CACHE_MANAGER_LOADED = True
    print("✅ Cache manager загружен")
    
except ImportError as e:
    print(f"❌ Ошибка загрузки cache_manager: {e}")
    CACHE_MANAGER_LOADED = False
    DETAILS_AVAILABLE = False
    AUTO_PARSE_AVAILABLE = False

app = FastAPI(
    title="Stalcraft Wiki API",
    description="API для данных Stalcraft Wiki с авто-парсингом",
    version="4.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CATEGORIES = {
    "weapons": {
        "name": "Оружие",
        "cache_key": "weapon",
        "items_key": "weapon"
    },
    "armor": {
        "name": "Броня", 
        "cache_key": "armor",
        "items_key": "Bron"
    },
    "artifacts": {
        "name": "Артефакты",
        "cache_key": "artifacts",
        "items_key": "Art"
    },
    "backpacks": {
        "name": "Рюкзаки",
        "cache_key": "backpacks",
        "items_key": "backpack"
    },
    "containers": {
        "name": "Контейнеры",
        "cache_key": "containers",
        "items_key": "container"
    },
    "devices": {
        "name": "Устройства",
        "cache_key": "devices",
        "items_key": "device"
    },
    "attachments": {
        "name": "Модификации",
        "cache_key": "attachments",
        "items_key": "attachment"
    }
}

if CACHE_MANAGER_LOADED:
    CATEGORY_FUNCTIONS = {
        "weapons": get_cached_weapon,
        "armor": get_cached_armor,
        "artifacts": get_cached_artifacts,
        "backpacks": get_cached_backpacks,
        "containers": get_cached_containers,
        "devices": get_cached_devices,
        "attachments": get_cached_attachments
    }
else:
    CATEGORY_FUNCTIONS = {}


def get_category_data(category: str) -> Dict[str, Any]:
    """Получить данные категории"""
    if category not in CATEGORIES:
        raise HTTPException(404, f"Категория {category} не найдена")
    
    if not CACHE_MANAGER_LOADED:
        raise HTTPException(500, "Cache manager не загружен")
    
    if category not in CATEGORY_FUNCTIONS:
        raise HTTPException(500, f"Функция для категории {category} не найдена")
    
    config = CATEGORIES[category]
    
    try:
        data_func = CATEGORY_FUNCTIONS[category]
        data = data_func()
        
        if not isinstance(data, dict):
            raise HTTPException(500, "Некорректный формат данных")
        
        return {
            "config": config,
            "data": data,
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка получения данных: {e}")


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    status = {
        "api": "Stalcraft Wiki API",
        "version": "4.0",
        "status": "active" if CACHE_MANAGER_LOADED else "degraded",
        "cache_manager": "loaded" if CACHE_MANAGER_LOADED else "not_loaded",
        "auto_parsing": "available" if AUTO_PARSE_AVAILABLE else "not_available",
        "features": [
            "categories" if CACHE_MANAGER_LOADED else "categories (disabled)",
            "auto-parsing-30-days" if AUTO_PARSE_AVAILABLE else "auto-parsing (disabled)",
            "detailed-cache-files" if DETAILS_AVAILABLE else "details (disabled)"
        ]
    }
    
    endpoints = {
        "categories": "/categories",
        "category_items": "/items/{category}",
        "category_with_images": "/items/{category}/images",
        "category_count": "/count/{category}",
        "all_counts": "/counts",
        "full_item": "/item/{category}/{item_name}",
        "cache_raw": "/cache/{category}/{item_name}/raw",  
        "cache_all": "/cache/{category}/all",  
        "search": "/search?q={query}",
        "health": "/health",
        "stats": "/stats"
    }
    
    if AUTO_PARSE_AVAILABLE:
        endpoints.update({
            "parsing_status": "/parsing/status",
            "parsing_start": "/parsing/start"
        })
    
    if DETAILS_AVAILABLE:
        endpoints.update({
            "category_details": "/items/{category}/details",
            "item_detail": "/items/{category}/{item_name}"
        })
    
    status["endpoints"] = endpoints
    return status

@app.get("/categories")
async def get_categories():
    """Получить список всех категорий"""
    if not CACHE_MANAGER_LOADED:
        raise HTTPException(500, "Cache manager не загружен")
    
    categories_list = []
    for cat_id, config in CATEGORIES.items():
        if cat_id not in CATEGORY_FUNCTIONS:
            categories_list.append({
                "id": cat_id,
                "name": config["name"],
                "items_count": 0,
                "error": "Функция не найдена"
            })
            continue
        
        try:
            data_func = CATEGORY_FUNCTIONS[cat_id]
            data = data_func()
            items_key = config["items_key"]
            items = data.get(items_key, []) if isinstance(data, dict) else []
            
            categories_list.append({
                "id": cat_id,
                "name": config["name"],
                "items_count": len(items),
                "endpoint": f"/items/{cat_id}"
            })
        except Exception as e:
            categories_list.append({
                "id": cat_id,
                "name": config["name"],
                "items_count": 0,
                "error": f"Ошибка: {str(e)[:50]}"
            })
    
    return {
        "success": True,
        "categories": categories_list,
        "total_categories": len(categories_list),
        "timestamp": time.time()
    }

@app.get("/items/{category}")
async def get_category_items_simple(category: str, limit: int = 400):
    """
    Возвращает список предметов категории с полями name, rank, image.
    Данные читаются из соответствующего JSON-файла.
    """
    cache_data = read_cache_file(category)
    if not cache_data:
        raise HTTPException(404, f"Кэш для категории '{category}' не найден")

    items = []
    # Предполагается, что cache_data — это словарь { "Название": { ... }, ... }
    for item_name, item_data in list(cache_data.items())[:limit]:
        data = item_data.get("data", {})
        rank = data.get("rank", "Неизвестно")
        class_name = data.get("class", "") 
        image = _extract_image_from_cache(item_data)
        items.append({
            "name": item_name,
            "rank": rank,
            "class": class_name,
            "image": image
        })

    return {
        "items": items,
        "total": len(cache_data),
        "category": category
    }

@app.get("/items/{category}/images-only")
async def get_category_items_images_only(category: str, limit: int = 400):
    """Только предметы с изображениями и рангом из кэша"""
    cache_data = read_cache_file(category)
    
    if not cache_data:
        raise HTTPException(404, f"Кэш для категории {category} не найден")
    
    items_with_images = []
    
    for item_name, item_data in cache_data.items():
        image_url = None
        rank = None
        damage = None
        
        if isinstance(item_data, dict):
            if 'data' in item_data:
                actual_data = item_data['data']
                if isinstance(actual_data, dict):
                    image_url = actual_data.get('image')
                    rank = actual_data.get('rank')
                    damage = actual_data.get('damage_value')
                    
                    if not damage and 'characteristics' in actual_data:
                        characteristics = actual_data.get('characteristics', {})
                        damage = characteristics.get('Урон')
                        
            elif 'image' in item_data:
                image_url = item_data.get('image')
                rank = item_data.get('rank')
        
        if image_url:
            item_info = {
                "name": item_name,
                "image": image_url
            }
            
            if rank:
                item_info["rank"] = rank
            if damage:
                item_info["damage"] = damage
            
            items_with_images.append(item_info)
            
            if len(items_with_images) >= limit:
                break
    
    return {
        "category": category,
        "items": items_with_images,
        "total_with_images": len(items_with_images),
        "total_in_cache": len(cache_data)
    }

@app.get("/item/{category}/{item_name}/raw")
async def get_item_raw(category: str, item_name: str):
    cache_data = read_cache_file(category)
    if not cache_data:
        raise HTTPException(404, f"Cache for {category} not found")
    
    # Логирование
    print(f"Looking for item: '{item_name}'")
    print(f"Available keys: {list(cache_data.keys())[:5]}...")  # первые 5 для проверки
    
    if item_name not in cache_data:
        raise HTTPException(404, f"Item '{item_name}' not found in {category}")
    
    return cache_data[item_name]

@app.get("/routes")
async def list_routes():
    return [{"path": route.path, "name": route.name} for route in app.routes]

@app.get("/count/{category}")
async def get_category_count(category: str):
    """Получить количество предметов в категории"""
    result = get_category_data(category)
    config = result["config"]
    data = result["data"]
    
    items_key = config["items_key"]
    items = data.get(items_key, [])
    
    images = data.get('img', []) if 'img' in data else []
    images_count = sum(1 for img in images if img)
    
    details_count = 0
    if DETAILS_AVAILABLE:
        try:
            cache_category = config["cache_key"]
            details = get_all_category_details(cache_category)
            if details:
                details_count = len(details)
        except:
            pass
    
    return {
        "success": True,
        "category": category,
        "name": config["name"],
        "total_items": len(items),
        "with_images": images_count,
        "with_details": details_count,
        "coverage_images": f"{(images_count/len(items)*100):.1f}%" if len(items) > 0 else "0%",
        "coverage_details": f"{(details_count/len(items)*100):.1f}%" if len(items) > 0 else "0%",
        "timestamp": time.time()
    }

@app.get("/counts")
async def get_counts_simple():
    """Простая статистика - только количество предметов"""
    counts = {}
    
    for cat_id, config in CATEGORIES.items():
        cache_data = read_cache_file(cat_id)
        if cache_data:
            counts[cat_id] = {
                "name": config["name"],
                "count": len(cache_data)
            }
        else:
            counts[cat_id] = {
                "name": config["name"], 
                "count": 0,
                "status": "no_cache"
            }
    
    return {
        "categories": counts,
        "total": sum(item["count"] for item in counts.values())
    }

@app.get("/items/{category}/details")
async def get_category_all_details(category: str, limit: int = 50):
    """Получить ВСЕ детали предметов категории"""
    if not DETAILS_AVAILABLE:
        raise HTTPException(501, "Функция деталей не доступна")
    
    if category not in CATEGORIES:
        raise HTTPException(404, f"Категория {category} не найдена")
    
    config = CATEGORIES[category]
    cache_category = config["cache_key"]
    
    try:
        details = get_all_category_details(cache_category)
        
        if not details:
            raise HTTPException(404, f"Детали для категории {category} не найдены")
        
        items_list = []
        for item_name, item_details in list(details.items())[:limit]:
            items_list.append({
                "name": item_name,
                "details": item_details
            })
        
        return {
            "success": True,
            "category": category,
            "name": config["name"],
            "total_items": len(details),
            "returned_items": len(items_list),
            "has_more": len(details) > limit,
            "items": items_list,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ошибка получения деталей: {e}")


@app.post("/parsing/start")
async def start_parsing(background_tasks: BackgroundTasks, categories: Optional[str] = None):
    """Запустить авто-парсинг"""
    if not AUTO_PARSE_AVAILABLE:
        raise HTTPException(501, "Авто-парсинг не доступен")
    
    categories_list = None
    if categories:
        categories_list = [cat.strip() for cat in categories.split(',')]
        categories_list = [cat.rstrip('s') for cat in categories_list]
    
    def start_parse():
        try:
            start_auto_parsing(categories_list)
        except Exception as e:
            print(f"Ошибка запуска авто-парсинга: {e}")
    
    background_tasks.add_task(start_parse)
    
    return {
        "success": True,
        "message": "Авто-парсинг запущен в фоне",
        "categories": categories_list if categories_list else "all",
        "check_status": "/parsing/status",
        "timestamp": time.time()
    }

@app.get("/parsing/status")
async def get_parsing_status():
    """Получить статус авто-парсинга"""
    if not AUTO_PARSE_AVAILABLE:
        raise HTTPException(501, "Авто-парсинг не доступен")
    
    try:
        status = get_auto_parse_status()
        return {
            "success": True,
            "auto_parsing": status,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(500, f"Ошибка получения статуса: {e}")


@app.get("/search")
async def search_items(
    q: str,
    category: Optional[str] = None,
    limit: int = 20
):
    """Поиск предметов по всем категориям"""
    if len(q) < 2:
        raise HTTPException(400, "Поисковый запрос должен содержать минимум 2 символа")
    
    if not CACHE_MANAGER_LOADED:
        raise HTTPException(500, "Cache manager не загружен")
    
    query = q.lower()
    results = []
    
    categories_to_search = []
    if category:
        if category in CATEGORIES:
            categories_to_search = [category]
        else:
            raise HTTPException(400, f"Неизвестная категория: {category}")
    else:
        categories_to_search = list(CATEGORIES.keys())
    
    for cat in categories_to_search:
        if cat not in CATEGORY_FUNCTIONS:
            continue
        
        config = CATEGORIES[cat]
        
        try:
            data_func = CATEGORY_FUNCTIONS[cat]
            data = data_func()
            
            if not isinstance(data, dict):
                continue
            
            items_key = config["items_key"]
            items = data.get(items_key, [])
            
            if not isinstance(items, list):
                continue
            
            images = data.get('img', []) if 'img' in data else []
            
            for i, item_name in enumerate(items):
                if query in item_name.lower():
                    result_item = {
                        "name": item_name,
                        "category": cat,
                        "category_name": config["name"]
                    }
                    
                    if i < len(images):
                        result_item["image"] = images[i]
                    
                    if DETAILS_AVAILABLE:
                        try:
                            cache_category = config["cache_key"]
                            details = get_item_details(cache_category, item_name)
                            if details:
                                result_item["details"] = details
                        except:
                            pass
                    
                    results.append(result_item)
                    
                    if len(results) >= limit:
                        break
            
            if len(results) >= limit:
                break
                
        except:
            continue
    
    return {
        "success": True,
        "query": q,
        "found": len(results),
        "results": results,
        "timestamp": time.time()
    }


@app.get("/stats")
async def get_stats():
    """Полная статистика"""
    if not CACHE_MANAGER_LOADED:
        raise HTTPException(500, "Cache manager не загружен")
    
    try:
        total_items = 0
        category_stats = {}
        
        for cat_id, config in CATEGORIES.items():
            if cat_id not in CATEGORY_FUNCTIONS:
                category_stats[cat_id] = {
                    "name": config["name"],
                    "items_count": 0,
                    "has_data": False,
                    "error": "Функция не найдена"
                }
                continue
            
            try:
                data_func = CATEGORY_FUNCTIONS[cat_id]
                data = data_func()
                items_key = config["items_key"]
                items = data.get(items_key, []) if isinstance(data, dict) else []
                item_count = len(items)
                
                stats = {
                    "name": config["name"],
                    "items_count": item_count,
                    "has_data": item_count > 0
                }
                
                if DETAILS_AVAILABLE:
                    cache_category = config["cache_key"]
                    details = get_all_category_details(cache_category)
                    if details:
                        stats["detailed_items"] = len(details)
                
                category_stats[cat_id] = stats
                
                total_items += item_count
            except Exception as e:
                category_stats[cat_id] = {
                    "name": config["name"],
                    "items_count": 0,
                    "has_data": False,
                    "error": str(e)[:50]
                }
        
        auto_parse_info = {}
        if AUTO_PARSE_AVAILABLE:
            try:
                parse_status = get_auto_parse_status()
                auto_parse_info = {
                    "is_running": parse_status.get("is_running", False),
                    "last_full_parse": parse_status.get("last_full_parse"),
                    "next_scheduled_parse": parse_status.get("next_scheduled_parse")
                }
            except:
                auto_parse_info = {"error": "Не удалось получить статус"}
        
        return {
            "success": True,
            "timestamp": time.time(),
            "total_categories": len(category_stats),
            "total_items": total_items,
            "categories": category_stats,
            "auto_parsing": auto_parse_info,
            "features": {
                "cache_manager": CACHE_MANAGER_LOADED,
                "details": DETAILS_AVAILABLE,
                "auto_parsing": AUTO_PARSE_AVAILABLE
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка получения статистики: {e}")

@app.get("/health")
async def health_check():
    """Проверка здоровья"""
    return {
        "status": "healthy" if CACHE_MANAGER_LOADED else "degraded",
        "cache_manager": "loaded" if CACHE_MANAGER_LOADED else "not_loaded",
        "details": "available" if DETAILS_AVAILABLE else "not_available",
        "auto_parsing": "available" if AUTO_PARSE_AVAILABLE else "not_available",
        "timestamp": time.time(),
        "categories_available": len(CATEGORIES)
    }


if __name__ == "__main__":
    print("="*60)
    print("🚀 STALCRAFT WIKI API v4.0")
    print("="*60)
    print(f"📡 Порт: {PORT}")
    print(f"🌐 URL: http://127.0.0.1:{PORT}")
    print(f"📚 Документация: http://127.0.0.1:{PORT}/docs")
    print("="*60)
    
    if CACHE_MANAGER_LOADED:
        print("✅ Cache manager загружен")
        if AUTO_PARSE_AVAILABLE:
            print("🤖 Авто-парсинг активен (30 дней)")
        if DETAILS_AVAILABLE:
            print("🔍 Детали предметов доступны")
    else:
        print("❌ Cache manager не загружен - API будет работать в ограниченном режиме")
    
    print("\n📊 НОВЫЕ ЭНДПОИНТЫ:")
    print("   GET  /items/{category}/images     - предметы с изображениями")
    print("   GET  /item/{category}/{item}      - ВСЕ данные о предмете")
    print("   GET  /count/{category}            - количество в категории")
    print("   GET  /counts                      - количество во ВСЕХ категориях")
    
    print("\n📊 ОСНОВНЫЕ ЭНДПОИНТЫ:")
    print("   GET  /categories                  - список категорий")
    print("   GET  /items/{category}            - предметы категории")
    print("   GET  /search?q={query}            - поиск по всем категориям")
    
    if DETAILS_AVAILABLE:
        print("   GET  /items/{category}/details  - все детали категории")
        print("   GET  /items/{category}/{item}   - детали конкретного предмета")
    
    if AUTO_PARSE_AVAILABLE:
        print("   POST /parsing/start             - запустить авто-парсинг")
        print("   GET  /parsing/status            - статус парсинга")
    
    print("   GET  /stats                      - статистика")
    print("   GET  /health                     - проверка здоровья")
    print("="*60)
    
    uvicorn.run(app, host="127.0.0.1", port=PORT)
    
    
    
        