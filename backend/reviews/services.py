import pandas as pd
import io
import re
from datetime import date
import re
import hashlib
import pandas as pd
from .models import Review, CrawlTarget, ReviewScore, Hotel
from .crawlers.expedia_crawler import scrape_expedia_reviews
from .crawlers.rakuten_travel_crawler import scrape_rakuten_travel_reviews
# from .crawlers.google_travel_crawler import scrape_google_travel_reviews
from .crawlers.jalan_crawler import scrape_jalan_reviews
import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


EXCEL_HEADER_MAP = {
    "review_date": "投稿月日",
    "ota_name": "OTA",
    "reviewer_name": "ユーザー名",
    # "nationality_region": "国籍_大分類",
    # "nationality_country": "国籍_小分類",
    "review_language": "言語",
    "room_type": "部屋",
    "purpose_of_visit": "目的",
    "traveler_type": "旅行形態",
    "gender": "性別",
    "age_group": "年代",
    "overall_score": "総合評価",
    # ReviewScoreからピボットして生成されるフィールド (enumのキーと一致させる)
    "LOCATION": "立地",
    "SERVICE": "サービス",
    "CLEANLINESS": "清潔感",
    "FACILITIES": "施設/設備/アメニティ",
    "ROOM": "客室/部屋",
    "BATH": "風呂/温泉",
    "FOOD": "食事",
    "BREAKFAST": "料理（朝食）",
    "DINNER": "料理（夕食）",
    "review_comment": "口コミ本文",
    "translated_review_comment": "口コミ(翻訳済)",
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
        elif target.ota.name == "じゃらん":
            print(f"OTA: じゃらん を検出。じゃらん用クローラーを開始します。")
            reviews_list = scrape_jalan_reviews(
                url=target.crawl_url,
                hotel_id=hotel_slug,
                start_date_str=start_date,
                end_date_str=end_date,
            )
        # elif target.ota.name == "Googleトラベル":
        #     print(
        #         f"OTA: Googleトラベル を検出。Googleトラベル用クローラーを開始します。"
        #     )
        #     reviews_list = scrape_google_travel_reviews(
        #         url=target.crawl_url,
        #         hotel_id=hotel_slug,
        #         start_date_str=start_date,
        #         end_date_str=end_date,
        #     )
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
    hotel_id: int,
    hotel_name: str,
    ota_ids: list = None,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """
    指定された条件でDBからレビューを取得し、pandas DataFrameとして返す。
    """
    print(f"--- [Service] Function started. Searching for hotel: '{hotel_name}' ---")
    try:
        hotel_master = Hotel.objects.get(name=hotel_name)
    except Hotel.DoesNotExist:
        return pd.DataFrame()

    targets = CrawlTarget.objects.filter(hotel=hotel_master)
    if ota_ids:
        targets = targets.filter(ota__id__in=ota_ids)

    reviews_query = Review.objects.filter(crawl_target__in=targets)
    # 日付範囲の指定があれば、それでさらにフィルタリング
    if start_date:
        reviews_query = reviews_query.filter(review_date__gte=start_date)
    if end_date:
        reviews_query = reviews_query.filter(review_date__lte=end_date)

    reviews_query = reviews_query.select_related("crawl_target__ota")

    review_values = list(
        reviews_query.values(
            "id",
            "review_date",
            "crawl_target__ota__name", 
            "reviewer_name",
            "review_language",
            "room_type",
            "purpose_of_visit",
            "traveler_type",
            "gender",
            "age_group",
            "review_comment",
            "translated_review_comment",
            "overall_score",
        )
    )

    if not review_values:
        print("--- [Service] No reviews found. Returning empty DataFrame. ---")
        return pd.DataFrame()

    df_reviews = pd.DataFrame(review_values)
    # 分かりやすいようにカラム名を変更
    df_reviews.rename(columns={"crawl_target__ota__name": "ota_name"}, inplace=True)

    review_ids = df_reviews['id'].tolist()
    score_values = list(ReviewScore.objects.filter(review_id__in=review_ids).values(
        'review_id', 'category', 'score'
    ))

    if score_values:
        df_scores = pd.DataFrame(score_values)
        df_scores_pivot = df_scores.pivot_table(
            index='review_id', columns='category', values='score'
        ).reset_index()

        df = pd.merge(df_reviews, df_scores_pivot, left_on='id', right_on='review_id', how='left')
        df.drop(columns=['id', 'review_id'], inplace=True)
    else:
        df = df_reviews.drop(columns=['id'])

    # カラム名を日本語ヘッダーにリネーム
    df.rename(columns=EXCEL_HEADER_MAP, inplace=True)
    
    expected_columns_jp = list(EXCEL_HEADER_MAP.values())
    
    final_columns_order = [
        jp_name for jp_name in expected_columns_jp if jp_name in df.columns
    ]

    df = df[final_columns_order]

    print(f"--- [Service] Data found. Returning DataFrame with {len(df)} rows. ---")
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

    SCORE_MAPPING = {
        "location": ReviewScore.ScoreCategory.LOCATION,
        "service": ReviewScore.ScoreCategory.SERVICE,
        "cleanliness": ReviewScore.ScoreCategory.CLEANLINESS,
        "facilities": ReviewScore.ScoreCategory.FACILITIES,
        "room": ReviewScore.ScoreCategory.ROOM,
        "bath": ReviewScore.ScoreCategory.BATH,
        "food": ReviewScore.ScoreCategory.FOOD,
    }
    review_model_fields = {f.name for f in Review._meta.get_fields()}

    for review_data in reviews_list:
        try:

            with transaction.atomic():
                reviewer_name = str(review_data.get('reviewer_name', '')).strip()
                raw_date = review_data.get('review_date')
                if isinstance(raw_date, date):
                    normalized_date = raw_date.isoformat()
                elif isinstance(raw_date, str):
                    normalized_date = raw_date.strip() 
                else:
                    normalized_date = ''
                score_original = str(
                    review_data.get("overall_score_original", "")
                ).strip()
                comment = str(review_data.get("review_comment", "")).strip()
                
                # 【ハッシュ生成】
                # 欠損したり変更されたりする可能性が低い、安定したコア情報のみでハッシュを構成する。
                # これにより、2回目にクロールした際に一部情報が欠損しても、同じレビューとして特定できる。
                source_string = (
                    f"{crawl_target.id}-"
                    f"{reviewer_name}-"
                    f"{normalized_date}-"
                    f"{score_original}-"
                    f"{comment}"
                )
                review_hash = hashlib.sha256(source_string.encode("utf-8")).hexdigest()

                review_defaults = {}
                score_data = {}

                for key, value in review_data.items():
                    if value is None:
                        continue # 値がNoneのデータは無視

                    # スコア関連のキーかどうかを判定
                    is_score_field = False
                    for prefix in SCORE_MAPPING.keys():
                        if key.startswith(prefix + "_score"):
                            score_data[key] = value
                            is_score_field = True
                            break

                    # スコア関連でなければ、Reviewモデルのフィールドかチェック
                    if not is_score_field and key in review_model_fields:
                        review_defaults[key] = value

                review_defaults["crawl_target"] = crawl_target
                # ※正規化済みの総合評価(overall_score)はreview_defaultsに含まれる

                # ---  Reviewオブジェクトの保存/更新 ---
                review_obj, created = Review.objects.update_or_create(
                    review_hash=review_hash,
                    defaults=review_defaults,
                )

                # --- ReviewScoreオブジェクトの保存/更新 ---
                # 存在する場合のみ、カテゴリ別にスコアを保存
                for prefix, category_enum in SCORE_MAPPING.items():
                    score_key = f"{prefix}_score"
                    original_key = f"{prefix}_score_original"

                    # 正規化済みスコアが存在する場合のみ処理
                    if score_key in score_data:
                        try:
                            normalized_score = Decimal(str(score_data[score_key]))
                            original_score = score_data.get(original_key, '')

                            ReviewScore.objects.update_or_create(
                                review=review_obj,
                                category=category_enum,
                                defaults={
                                    'score': normalized_score,
                                    'score_original': original_score
                                }
                            )
                        except InvalidOperation:
                            logging.warning(
                                f"  '{score_key}' の値 '{score_data[score_key]}' をDecimalに変換できませんでした。スキップします。"
                            )

                # --- カウント処理 ---
                if created:
                    saved_count += 1
                else:
                    updated_count += 1

        except Exception as e:
            logging.error(f"    DB保存中に致命的なエラー: {e}。このレビューの処理をスキップします. データ: {review_data}")
            skipped_count += 1

    logging.info(
        f"  [DB保存結果] 新規: {saved_count}件, 更新: {updated_count}件, スキップ: {skipped_count}件"
    )
