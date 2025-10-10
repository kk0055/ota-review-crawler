import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "mapping_config.yaml"


class DataNormalizer:
    def __init__(self, config_path=CONFIG_PATH):
        config = self._load_config(config_path)
        self.traveler_type_maps = self._build_generic_maps(config, "traveler_type")
        self.purpose_maps = self._build_generic_maps(config, "purpose_of_visit")
        self.room_type_maps = self._build_room_type_maps(config)

    def _load_config(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _create_reverse_map(self, mapping_dict):
        reverse_map = {}
        if not mapping_dict:
            return reverse_map
        for normalized, originals in mapping_dict.items():
            if originals:
                for original in originals:
                    reverse_map[original] = normalized
        return reverse_map

    def _build_generic_maps(self, config, field_name):
        maps = {"common": {}, "ota_specific": {}}
        field_config = config.get(field_name, {})
        maps["common"] = self._create_reverse_map(field_config.get("common", {}))
        ota_specific_config = field_config.get("ota_specific", {})
        for ota, mapping in ota_specific_config.items():
            maps["ota_specific"][ota] = self._create_reverse_map(mapping)
        return maps

    def _build_room_type_maps(self, config):
        maps = {}
        room_type_config = config.get("room_type", {})
        for hotel_id, hotel_mappings in room_type_config.items():
            maps[hotel_id] = {}
            for ota_name, ota_mappings in hotel_mappings.items():
                maps[hotel_id][ota_name] = self._create_reverse_map(ota_mappings)
        return maps

    def normalize_traveler_type(self, original_value, ota_name):
        maps_dict = self.traveler_type_maps
        if not original_value:
            return None
        ota_map = maps_dict["ota_specific"].get(ota_name, {})
        normalized = ota_map.get(original_value)
        if normalized:
            return normalized
        common_map = maps_dict["common"]
        return common_map.get(original_value, "その他")

    def normalize_purpose(self, original_value, ota_name):
        maps_dict = self.purpose_maps
        if not original_value:
            return None
        # 目的は共通ルールのみで判断
        common_map = maps_dict["common"]
        return common_map.get(original_value, "その他")

    def normalize_room_type(self, original_value, ota_name, hotel_id):
        if not original_value:
            return None
        hotel_map = self.room_type_maps.get(str(hotel_id), {})  # hotel_idを文字列に変換
        ota_map = hotel_map.get(ota_name, {})
        return ota_map.get(original_value, original_value)
