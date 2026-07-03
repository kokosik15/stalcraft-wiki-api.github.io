"""
Пакет парсеров для Stalcraft Wiki
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from .Weapon import Weapon, get_cached_weapon, get_weapon_details, get_all_weapon_details, refresh_all_weapon_details
    from .Bron import Bron, get_cached_bron, get_armor_details, get_all_armor_details, refresh_all_armor_details
    from .Art import Art, get_cached_artifact, get_artifact_details, get_all_artifact_details, refresh_all_artifact_details
    from .Backpacks import Backpack, get_cached_backpack, get_backpack_details, get_all_backpack_details, refresh_all_backpack_details
    from .Containers import Container, get_cached_container, get_container_details, get_all_container_details, refresh_all_container_details
    from .Devices import Device, get_cached_device, get_device_details, get_all_device_details, refresh_all_device_details
    from .Mod import Attachment, get_cached_attachment, get_attachment_details, get_all_attachment_details, refresh_all_attachment_details
    
    print("[ITEMS] Все парсеры загружены успешно")
    
except ImportError as e:
    print(f"[ITEMS] Ошибка импорта парсеров: {e}")

    class StubParser:
        def __init__(self, name="Заглушка"):
            self.name = name
        
        def __call__(self, *args, **kwargs):
            print(f"[STUB] Вызвана заглушка для {self.name}")
            return {'items': [], 'images': [], 'links': [], 'quantity': [0]}
        
        def get_data(self):
            return {'items': [], 'images': [], 'links': [], 'quantity': [0]}

    stub = StubParser()
    Weapon = stub
    Bron = stub
    Art = stub
    Backpack = stub
    Container = stub
    Device = stub
    Attachment = stub

    def create_stub_func(name):
        def stub_func(*args, **kwargs):
            print(f"[STUB] Вызвана заглушка: {name}")
            return {}
        return stub_func
    
    get_cached_weapon = create_stub_func("get_cached_weapon")
    get_cached_bron = create_stub_func("get_cached_bron")
    get_cached_artifact = create_stub_func("get_cached_artifact")
    get_cached_backpack = create_stub_func("get_cached_backpack")
    get_cached_container = create_stub_func("get_cached_container")
    get_cached_device = create_stub_func("get_cached_device")
    get_cached_attachment = create_stub_func("get_cached_attachment")

__all__ = [
    'Weapon', 'get_cached_weapon', 'get_weapon_details', 'get_all_weapon_details', 'refresh_all_weapon_details',
    'Bron', 'get_cached_bron', 'get_armor_details', 'get_all_armor_details', 'refresh_all_armor_details',
    'Art', 'get_cached_artifact', 'get_artifact_details', 'get_all_artifact_details', 'refresh_all_artifact_details',
    'Backpack', 'get_cached_backpack', 'get_backpack_details', 'get_all_backpack_details', 'refresh_all_backpack_details',
    'Container', 'get_cached_container', 'get_container_details', 'get_all_container_details', 'refresh_all_container_details',
    'Device', 'get_cached_device', 'get_device_details', 'get_all_device_details', 'refresh_all_device_details',
    'Attachment', 'get_cached_attachment', 'get_attachment_details', 'get_all_attachment_details', 'refresh_all_attachment_details',
]

print("[ITEMS] Пакет инициализирован")