from decimal import Decimal, ROUND_HALF_UP
import pycld2 as cld2
import pycountry

LANG_MAP_JA = {
    "ja": "日本語",
    "en": "英語",
    "ko": "韓国語",
    'zh': '中国語',
    # "zh-cn": "中国語 (簡体)",
    # "zh-tw": "中国語 (繁体)",
    "fr": "フランス語",
    "de": "ドイツ語",
    "es": "スペイン語",
    "it": "イタリア語",
    "ru": "ロシア語",
    "th": "タイ語",
    "vi": "ベトナム語",
    "unknown": "不明",
}

def normalize_score(original_score, original_scale, target_scale=10):
    """スコアを正規化する関数"""
    if original_score is None or original_scale is None:
        return None
    try:
        # 元のスコアをDecimal型に変換
        original_score_dec = Decimal(str(original_score))
        original_scale_dec = Decimal(str(original_scale))
        target_scale_dec = Decimal(str(target_scale))

        # 正規化計算: (元のスコア / 元の満点) * 新しい満点
        normalized = (original_score_dec / original_scale_dec) * target_scale_dec

        # 小数点第2位を四捨五入して、小数点第1位までの値にする
        return normalized.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError):
        # 数値に変換できないデータの場合はNoneを返す
        return None


def detect_language(text: str) -> str:
    """
    与えられたテキストの言語を判定する。
    Args:
        text (str): 言語を判定したいテキスト。
    Returns:
        str: 判定された言語のISO 639-1コード ('ja', 'en'など)。
             テキストが短すぎる、または判定不能な場合は None を返す。
    """
    # テキストが空、または空白文字のみの場合は判定不能とする
    if not text or not text.strip():
        return None

    try:

        # details: (('言語名1', '言語コード1', 信頼度%, スコア), ('言語名2', ...))
        is_reliable, text_bytes_found, details = cld2.detect(text)

        # detailsが空、または最初の判定結果が 'un' (unknown) の場合は判定不能とみなす
        if not details or details[0][1] == 'un':
            return None

        lang_code = details[0][1]

        if "-" in lang_code:
            lang_code = lang_code.split("-")[0]
            
        return lang_code
    except cld2.error:
        return None


def get_language_name_ja(lang_code: str) -> str:
    """
    言語コードを日本語の表示名に変換する。
    """
    if not lang_code:
        return None
    ja_name = LANG_MAP_JA.get(lang_code)
    if ja_name:
        return ja_name

    try:

        lang_obj = pycountry.languages.get(alpha_2=lang_code)
        if lang_obj:
            name = getattr(lang_obj, 'name', lang_code)
            return f"{name} ({lang_code})"
    except (KeyError, AttributeError):
        # pycountryに存在しない、または無効なコードの場合
        pass

    return f"不明な言語 ({lang_code})"

# 言語コードから国籍カテゴリへのマッピング辞書
# 提供されたリストに基づき、言語から推定される国籍をマッピング
# NATIONALITY_MAP_FROM_LANG = {
#     # 言語コード: {'major': '国籍_大分類', 'minor': '国籍_小分類'}
#     # === アジア ===
#     "ja": {"major": "国内", "minor": "日本"},
#     "ko": {"major": "アジア", "minor": "韓国"},
#     "zh-cn": {"major": "アジア", "minor": "中国"},
#     "zh-tw": {"major": "アジア", "minor": "台湾/香港/マカオ"},  # 繁体字
#     # === 東南アジア ===
#     "id": {"major": "東南アジア", "minor": "インドネシア"},
#     "ms": {"major": "東南アジア", "minor": "シンガポール"},
#     "th": {"major": "東南アジア", "minor": "タイ"},
#     "tl": {"major": "東南アジア", "minor": "フィリピン"},  # タガログ語
#     "vi": {"major": "東南アジア", "minor": "ベトナム"},
#     # === 欧米・オセアニア ===
#     # 英語は国を特定できないため、大分類を「欧米・オセアニア」とし、小分類を「英語圏」とします
#     "en": {"major": "欧米・オセアニア", "minor": "英語圏"},
#     # --- 欧州 ---
#     "de": {"major": "欧米", "minor": "ドイツ語圏 (ドイツ/オーストリア/スイスなど)"},
#     "es": {"major": "欧米", "minor": "スペイン語圏 (スペイン/中南米など)"},
#     "fi": {"major": "欧米", "minor": "フィンランド"},
#     "fr": {"major": "欧米", "minor": "フランス語圏 (フランス/カナダ/ベルギーなど)"},
#     "it": {"major": "欧米", "minor": "イタリア"},
#     "nl": {"major": "欧米", "minor": "オランダ語圏 (オランダ/ベルギーなど)"},
#     "pl": {"major": "欧米", "minor": "ポーランド"},
#     "pt": {"major": "欧米", "minor": "ポルトガル語圏 (ポルトガル/ブラジルなど)"},
#     "ro": {"major": "欧米", "minor": "ルーマニア"},
#     "ru": {"major": "欧米", "minor": "ロシア"},
#     "sv": {"major": "欧米", "minor": "スウェーデン"},
#     # === 海外その他 ===
#     "ar": {"major": "海外その他", "minor": "アラブ圏"},  # アラビア語
#     "hi": {"major": "海外その他", "minor": "インド"},  # ヒンディー語
#     "tr": {"major": "海外その他", "minor": "トルコ"},
# }


# def infer_nationality_from_language(lang_code: str) -> dict:
#     """
#     言語コードから推定される国籍カテゴリ情報を返す。
#     """
#     if not lang_code:
#         return {"major": None, "minor": None}
#     # マッピングに存在しない場合のデフォルト値
#     default_info = {"major": "海外その他", "minor": "不明"}

#     return NATIONALITY_MAP_FROM_LANG.get(lang_code, default_info)
