import yaml
from pathlib import Path
import re
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "mapping_config.yaml"


# 旅行形態の優先順位（リストの先頭ほど優先度が高い）
TRAVELER_TYPE_PRIORITY = ["家族", "カップル・夫婦", "友達", "一人"]
# レジャー目的を推定するための旅行形態リスト
LEISURE_DERIVED_TRAVELER_TYPES = ["家族", "カップル・夫婦", "友達", "一人"]


class DataNormalizer:

    def __init__(self, config_path=None):
        """
        初期化時に、指定されたYAMLファイルから設定を読み込み、
        効率的な逆引きマップを自動生成します。
        """

        if config_path is None:
            # ★ config_pathが指定されなかった場合、
            # このファイル(normalizer.py)と同じディレクトリにある
            # 'mapping_config.yaml' を自動的に探す。
            base_dir = Path(__file__).resolve().parent
            config_path = base_dir / "mapping_config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

        # 各種マッピングを構築
        self.traveler_type_maps = self._build_maps(self.config.get("traveler_type", {}))
        self.purpose_maps = self._build_maps(self.config.get("purpose_of_visit", {}))

    def _build_maps(self, config_section):
        """設定から逆引きマップ {'元文字列': '正規化後'} を構築するヘルパー関数"""
        maps = {"common": {}, "ota_specific": {}}

        # 共通マップの構築
        for normalized_value, original_list in config_section["common"].items():
            for original_value in original_list:
                maps["common"][original_value] = normalized_value

        # OTA固有マップの構築
        if "ota_specific" in config_section:
            for ota, ota_config in config_section["ota_specific"].items():
                ota_map = {}
                for normalized_value, original_list in ota_config.items():
                    for original_value in original_list:
                        ota_map[original_value] = normalized_value
                maps["ota_specific"][ota] = ota_map
        return maps

    # def _build_room_type_maps(self, config):
    #     maps = {}
    #     room_type_config = config.get("room_type", {})
    #     for hotel_id, hotel_mappings in room_type_config.items():
    #         maps[hotel_id] = {}
    #         for ota_name, ota_mappings in hotel_mappings.items():
    #             maps[hotel_id][ota_name] = self._create_reverse_map(ota_mappings)
    #     return maps

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
        common_map = maps_dict["common"]
        return common_map.get(original_value, "その他")

    @lru_cache(maxsize=32)
    def _get_normalization_patterns(self, map_key, ota_name=None):
        """
        【新しいヘルパー関数】
        YAMLマップから(パターン, 正規化後の値)のタプルリストを生成し、
        パターン長で降順ソートして返す。
        """
        maps = getattr(self, map_key)  # self.traveler_type_mapsなどを動的に取得

        pattern_list = []

        # 1. 共通のパターンを追加
        for norm_value, raw_tags in maps.get("common", {}).items():
            for raw_tag in raw_tags:
                pattern_list.append((raw_tag, norm_value))

        # 2. OTA固有のパターンを追加
        if ota_name:
            ota_map = maps.get("ota_specific", {}).get(ota_name, {})
            for norm_value, raw_tags in ota_map.items():
                for raw_tag in raw_tags:
                    pattern_list.append((raw_tag, norm_value))

        # 3. パターンの文字数が長い順（より具体的）にソート
        pattern_list.sort(key=lambda x: len(x[0]), reverse=True)
        return pattern_list

    def normalize_from_tags(self, tags_input, ota_name=None):
        """
        【修正版】タグのリストまたは文字列から、旅行タイプと目的を正規化する。
        部分一致検索ロジックに変更。
        """
        if not tags_input:
            return {"traveler_type": None, "purpose": None}

        # 入力がリストでも文字列でも、最終的に1つの検索対象文字列に統一する
        search_text = ""
        if isinstance(tags_input, str):
            search_text = tags_input
        elif isinstance(tags_input, list):
            search_text = ", ".join(map(str, tags_input))

        if not search_text.strip():
            return {"traveler_type": None, "purpose": None}

        # ソート済みのパターンリストを取得
        traveler_patterns = self._get_normalization_patterns(
            "traveler_type_maps", ota_name
        )
        purpose_patterns = self._get_normalization_patterns("purpose_maps", ota_name)

        # 部分一致でマッチするものをすべて発見する
        found_traveler_types = set()
        for pattern, norm_value in traveler_patterns:
            if pattern in search_text:
                found_traveler_types.add(norm_value)

        found_purposes = set()
        for pattern, norm_value in purpose_patterns:
            if pattern in search_text:
                found_purposes.add(norm_value)

        # --- ここから下の優先度決定ロジックは変更なし ---
        result_traveler_type = None
        for priority_type in TRAVELER_TYPE_PRIORITY:
            if priority_type in found_traveler_types:
                result_traveler_type = priority_type
                break

        result_purpose = (
            "ビジネス"
            if "ビジネス" in found_purposes
            else next(iter(found_purposes), None)
        )

        if (
            not result_purpose
            and result_traveler_type in LEISURE_DERIVED_TRAVELER_TYPES
        ):
            result_purpose = "レジャー"

        return {"traveler_type": result_traveler_type, "purpose": result_purpose}

    @lru_cache(maxsize=128)
    def _get_sorted_pattern_list(self, hotel_slug, ota_name):
        """
        【内部ヘルパー/修正版】
        正規化のための「(パターン, 正規化名)」のタプルリストを生成し、
        パターンの文字数が長い順（より具体的なルールが先）にソートしてキャッシュする。
        """
        try:
            hotel_ota_map = self.config["room_type"][hotel_slug][ota_name]

            # (パターン, 正規化名) のリストを作成
            pattern_list = [
                (pattern, norm_name)
                for norm_name, patterns in hotel_ota_map.items()
                for pattern in patterns
            ]

            # パターンの文字数が長い順（降順）でソートする。これが非常に重要！
            # これにより "エグゼクティブツイン" が "ツイン" より先に評価される。
            pattern_list.sort(key=lambda x: len(x[0]), reverse=True)

            return pattern_list

        except KeyError:
            return []

    def normalize_room_type(self, original_room_name, hotel_slug, ota_name):
        """
        元の部屋名を、ホテルとOTAに合わせて正規化する（部分一致）。
        """
        if not all([original_room_name, hotel_slug, ota_name]):
            return original_room_name

        # ソート済みのパターンリストを取得
        sorted_patterns = self._get_sorted_pattern_list(hotel_slug, ota_name)

        # パターンが元の部屋名に含まれているかをチェック
        for pattern, normalized_name in sorted_patterns:
            if pattern in original_room_name:
                # 最初に見つかったマッチを返す（具体的なものが先に評価される）
                return normalized_name

        # どのパターンにもマッチしなかった場合は、元の名前をそのまま返す
        return original_room_name
