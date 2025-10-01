import pandas as pd
import io
import re
from datetime import datetime
import re
import hashlib
import pandas as pd
from .models import Review, CrawlTarget, Ota
from .crawlers.expedia_crawler import scrape_expedia_reviews
import logging

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


def run_crawl_and_save(target: CrawlTarget, start_date: str, end_date: str):
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
        # ... 他のOTAの処理 ...
        else:
            return True, f"'{target.ota.name}' に対応するクローラーがありません。"

        if not reviews_list:
            return True, "口コミは取得されませんでした。"

        save_reviews_to_db(reviews_list, target)

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

    target_hotels = CrawlTarget.objects.filter(hotel_name=hotel_name)

    if ota_names:
        target_hotels = target_hotels.filter(ota__name__in=ota_names)

    # この時点で絞り込み対象のホテルが存在しないなら、早期にリターン
    if not target_hotels.exists():
        print("--- [Service] No target hotels found. Returning empty DataFrame. ---")
        return pd.DataFrame()

    reviews = Review.objects.filter(hotel__in=target_hotels)

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


def save_reviews_to_db(reviews_list, hotel):
    """取得したレビューのリストをデータベースに保存/更新します。"""
    logging.info(f"  取得した {len(reviews_list)} 件の口コミをDBに保存します...")
    saved_count, updated_count, skipped_count = 0, 0, 0

    for review_data in reviews_list:
        try:

            # 【ハッシュ生成】
            # 欠損したり変更されたりする可能性が低い、安定したコア情報のみでハッシュを構成する。
            # これにより、2回目にクロールした際に一部情報が欠損しても、同じレビューとして特定できる。
            source_string = (
                f"{hotel.id}-"
                f"{review_data.get('reviewer_name', '')}-"
                f"{review_data.get('review_date', '')}-"
                f"{review_data.get('overall_score', '')}-"
                f"{review_data.get('review_comment', '')}"
            )
            review_hash = hashlib.sha256(source_string.encode("utf-8")).hexdigest()

            defaults_to_update = {
                "hotel": hotel,
            }

            # 各項目をチェックし、有効なデータだけを defaults に追加していく
            if review_data.get("overall_score", "").isdigit():
                defaults_to_update["overall_score"] = int(review_data["overall_score"])

            # 文字列系のフィールドは、Noneや空文字列でないことを確認
            string_fields = [
                "reviewer_name",
                "review_date",
                "traveler_type",
                "review_comment",
                "translated_review_comment",
            ]
            for field in string_fields:
                value = review_data.get(field)
                if value:  # valueがNoneや空文字列でない場合にTrueとなる
                    defaults_to_update[field] = value

            # update_or_createでDBに保存/更新
            _obj, created = Review.objects.update_or_create(
                review_hash=review_hash,
                defaults=defaults_to_update,
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
