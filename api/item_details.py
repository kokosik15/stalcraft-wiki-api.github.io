from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from ..items.cache_manager import cache_manager
from ..items.Weapon import get_weapon_details
from ..items.Bron import parse_armor_details
from ..items.Art import parse_artifact_details
# ... импорты для других категорий ...

router = APIRouter(prefix="/item-details", tags=["Item Details"])

@router.get("/{category}/{item_name}")
async def get_item_detail(
    category: str, 
    item_name: str, 
    refresh: bool = Query(False, description="Принудительное обновление данных")
):
    """
    Получить детальную информацию о предмете
    """
    # Валидация категории
    valid_categories = ['weapon', 'armor', 'artifact', 'attachment', 'device', 'container', 'backpack']
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Некорректная категория. Допустимые: {', '.join(valid_categories)}")
    
    # Получаем детали в зависимости от категории
    details = None
    
    if category == 'weapon':
        details = get_weapon_details(item_name, force_refresh=refresh)
    elif category == 'armor':
        details = parse_armor_details(item_name, get_armor_url(item_name))
    elif category == 'artifact':
        details = parse_artifact_details(item_name, get_artifact_url(item_name))
    # ... остальные категории ...
    
    if not details:
        raise HTTPException(status_code=404, detail=f"Предмет '{item_name}' не найден в категории '{category}'")
    
    return {
        "success": True,
        "category": category,
        "item_name": item_name,
        "data": details
    }

@router.get("/cache/statistics")
async def get_cache_statistics():
    """
    Получить статистику по кэшам
    """
    stats = cache_manager.get_cache_statistics()
    
    total_items = 0
    fresh_items = 0
    
    for category_stat in stats.values():
        total_items += category_stat['total_items']
        fresh_items += category_stat['fresh_items']
    
    return {
        "success": True,
        "overall": {
            "total_items": total_items,
            "fresh_items": fresh_items,
            "stale_items": total_items - fresh_items,
            "fresh_percentage": (fresh_items / total_items * 100) if total_items > 0 else 0
        },
        "categories": stats
    }

@router.post("/cache/clear/{category}")
async def clear_category_cache(category: str):
    """
    Очистить кэш категории
    """
    cache_manager.clear_category_cache(category)
    return {"success": True, "message": f"Кэш категории '{category}' очищен"}

@router.post("/cache/clear-all")
async def clear_all_caches():
    """
    Очистить все кэши
    """
    cache_manager.clear_all_caches()
    return {"success": True, "message": "Все кэши очищены"}