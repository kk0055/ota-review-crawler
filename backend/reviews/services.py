import pandas as pd
import io
import re
from datetime import datetime
import re
import hashlib
import pandas as pd
from .models import Review, CrawlTarget, Ota, Hotel
from .crawlers.expedia_crawler import scrape_expedia_reviews
from .crawlers.rakuten_travel_crawler import scrape_rakuten_travel_reviews
import logging
from decimal import Decimal, InvalidOperation

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


EXCEL_HEADER_MAP = {
    # "ホテルID": "hotel_id",
    "投稿月日": "review_date",
    "ユーザー名": "reviewer_name",
    "国籍_大分類": "nationality_region",
    "国籍_小分類": "nationality_country",
    "言語": "review_language",
    "部屋": "room_type",
    "目的": "purpose_of_visit",
    "形態": "traveler_type",
    "性別": "gender",
    "年代": "age_group",
    "総合スコア": "overall_score",
    "口コミ": "review_comment",
    "口コミ(翻訳済)": "translated_review_comment",
}


def run_crawl_and_save(
    target: CrawlTarget, start_date: str, end_date: str, hotel_slug: str
):
    """
    指定されたCrawlTargetに対してクロールを実行し、結果をDBに保存する。
    :return: (成功フラグ, メッセージ) のタプル
    """
    try:
        reviews_list = []
        if not target.crawl_url:
            return True, "クロールURLが未設定のため、スキップしました。"

        # OTAによってクローラーを切り替え
        if target.ota.name == "Expedia":
            reviews_list = scrape_expedia_reviews(
                target.crawl_url, start_date, end_date
            )
        elif target.ota.name == "楽天トラベル":
            print(f"OTA: 楽天トラベル を検出。楽天トラベル用クローラーを開始します。")
            reviews_list = scrape_rakuten_travel_reviews(
                url=target.crawl_url,
                hotel_id=hotel_slug,
                start_date_str=start_date,
                end_date_str=end_date,
            )
        else:
            return True, f"'{target.ota.name}' に対応するクローラーがありません。"

        if not reviews_list:
            return True, "口コミは取得されませんでした。"

        # save_reviews_to_db(reviews_list, target)

        message = f"正常に処理完了。取得件数: {len(reviews_list)}"
        return True, message

    except Exception as e:
        error_message = f"クロール中にエラーが発生しました: {e}"
        # logging.error(error_message)
        return False, error_message


def get_reviews_as_dataframe(
    hotel_name: str,
    ota_names: list = None,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """
    指定された条件でDBからレビューを取得し、pandas DataFrameとして返す。
    """
    print(f"--- [Service] Function started. Searching for hotel: '{hotel_name}' ---")
    try:
        # 1. まずホテル名で Hotel マスターモデルを取得する
        hotel_master = Hotel.objects.get(name=hotel_name)
    except Hotel.DoesNotExist:
        # マスターが存在しない場合は、空のDataFrameを返す
        return pd.DataFrame()

    targets = CrawlTarget.objects.filter(hotel=hotel_master)

    if ota_names:
        targets = targets.filter(ota__name__in=ota_names)

    if not targets.exists():
        print("--- [Service] No target hotels found. Returning empty DataFrame. ---")
        return pd.DataFrame()

    reviews = Review.objects.filter(crawl_target__in=targets)

    # 日付範囲の指定があれば、それでさらにフィルタリング
    if start_date:
        reviews = reviews.filter(review_date__gte=start_date)
    if end_date:
        reviews = reviews.filter(review_date__lte=end_date)

    if not reviews.exists():
        return pd.DataFrame()

    fields_to_get = list(EXCEL_HEADER_MAP.values())
    review_list = list(reviews.values(*fields_to_get))
    df = pd.DataFrame(review_list)
    rename_map = {v: k for k, v in EXCEL_HEADER_MAP.items()}
    df.rename(columns=rename_map, inplace=True)
    print(f"--- [Service] Data found. Returning DataFrame with {len(df)} rows. ---")
    df = df[list(EXCEL_HEADER_MAP.keys())]
    return df


def generate_excel_in_memory(df: pd.DataFrame) -> io.BytesIO:
    """
    DataFrameをメモリ上のExcelファイルデータ (BytesIO) として返す。
    """
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_buffer.seek(0)  # ポインタを先頭に戻す
    return excel_buffer


def save_reviews_to_db(reviews_list, crawl_target: CrawlTarget):
    """取得したレビューのリストをデータベースに保存/更新します。"""
    logging.info(f"  取得した {len(reviews_list)} 件の口コミをDBに保存します...")
    saved_count, updated_count, skipped_count = 0, 0, 0
    model_field_names = {f.name for f in Review._meta.get_fields()}

    for review_data in reviews_list:
        try:

            # 【ハッシュ生成】
            # 欠損したり変更されたりする可能性が低い、安定したコア情報のみでハッシュを構成する。
            # これにより、2回目にクロールした際に一部情報が欠損しても、同じレビューとして特定できる。
            source_string = (
                f"{crawl_target.id}-"
                f"{review_data.get('reviewer_name', '')}-"
                f"{review_data.get('review_date', '')}-"
                f"{review_data.get('overall_score_original', '')}-"
                f"{review_data.get('review_comment', '')}"
            )
            review_hash = hashlib.sha256(source_string.encode("utf-8")).hexdigest()

            # review_dataからモデルに存在するフィールドを抽出し、
            # さらに「値がNoneでない」ものだけをdefaults辞書に含める
            defaults = {
                key: value
                for key, value in review_data.items()
                if key in model_field_names and value is not None
            }

            defaults["crawl_target"] = crawl_target

            for key, value in defaults.items():
                if "_normalized" in key:  
                    try:
                        defaults[key] = Decimal(str(value))
                    except InvalidOperation:
                        logging.warning(
                            f"  '{key}' の値 '{value}' をDecimalに変換できません。Noneに設定します。"
                        )
                        defaults[key] = (
                            None  
                        )

            # review_hashをキーに、DBに保存/更新
            _obj, created = Review.objects.update_or_create(
                review_hash=review_hash,
                defaults=defaults,
            )

            if created:
                saved_count += 1
            else:
                updated_count += 1

        except Exception as e:
            logging.warning(
                f"    DB保存エラー: {e} スキップします. データ: {review_data}"
            )
            skipped_count += 1

    logging.info(
        f"  [DB保存結果] 新規: {saved_count}件, 更新: {updated_count}件, スキップ: {skipped_count}件"
    )
