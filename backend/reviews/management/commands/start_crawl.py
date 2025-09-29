from django.core.management.base import BaseCommand, CommandError
from reviews.models import Hotel, Review, Ota
from reviews.crawlers.expedia_crawler import (
    scrape_expedia_reviews,
)
from reviews.utils.excel_exporter import export_dataframe_to_excel
from datetime import datetime
import re
import hashlib
import pandas as pd

EXCEL_HEADER_MAP = {
    "ホテルID": "hotel_id",
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
    # '立地/地図（10）', 'サービス（10）' などのスコア項目は、Reviewモデルにフィールドがあれば追加してください。
}

class Command(BaseCommand):
    help = "指定されたホテルの口コミ情報をクロールしてDBに保存します。"
    # python manage.py start_crawl "ノボテル奈良"
    # python manage.py start_crawl "ノボテル奈良" --start-date 2025-04-01 --end-date 2024-07-30

    def add_arguments(self, parser):
        parser.add_argument("hotel_name", type=str, help="対象のホテル名")
        parser.add_argument(
            "--ota",
            type=str,
            default="Expedia",
            help="対象のOTA名 (デフォルト: Expedia)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            default=None,  # 指定がない場合はNone
            help="収集開始日 (YYYY-MM-DD形式)。この日付以降の口コミを収集します。",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default=None,  # 指定がない場合はNone
            help="収集終了日 (YYYY-MM-DD形式)。この日付以前の口コミを収集します。",
        )
        parser.add_argument(
            "--no-excel-export",
            action="store_false", 
            dest="export_excel", 
            default=True,  # デフォルトでは True (Excel出力を行う)
            help="処理後のExcelファイルへの口コミ出力を行わないようにします (デフォルトは出力する)。",
        )
        parser.add_argument(
            "--export-only",
            action="store_true",
            help="クローリングを実行せず、既存のDBデータのみをExcelに出力します。",
        )

    def handle(self, *args, **options):
        hotel_name = options["hotel_name"]
        ota_name = options["ota"]
        start_date = options["start_date"]
        end_date = options["end_date"]
        should_export_excel = options["export_excel"]
        export_only = options["export_only"]

        # DBから対象ホテル情報を取得
        try:
            hotel = Hotel.objects.get(hotel_name=hotel_name, ota__name=ota_name)
        except Hotel.DoesNotExist:
            raise CommandError(
                f'"{hotel_name}" ({ota_name}) はDBに登録されていません。先にregister_hotelコマンドで登録してください。'
            )

        if not hotel.crawl_url:
            raise CommandError(
                f'"{hotel.hotel_name}" のクロール対象URLが設定されていません。'
            )

        # --- クロールとDB保存のメイン処理 ---
        if not export_only:
            self.stdout.write(
                f"クロールを開始します: {hotel.hotel_name} ({hotel.ota.name})"
            )
            self.stdout.write(f"  URL: {hotel.crawl_url}")
            if start_date or end_date:
                self.stdout.write(
                    f"  対象期間: {start_date or '指定なし'} 〜 {end_date or '指定なし'}"
                )

            # クローラーを実行
            reviews_list = scrape_expedia_reviews(
                hotel.crawl_url, start_date_str=start_date, end_date_str=end_date
            )

            if not reviews_list:
                self.stdout.write(self.style.WARNING("口コミが取得できませんでした。"))
                # Excel出力のために実行を続ける
            else:
                self.stdout.write(
                    f"取得した {len(reviews_list)} 件の口コミをデータベースに保存します..."
                )

                saved_count = 0
                skipped_count = 0
                updated_count = 0

                for review_data in reviews_list:
                    # --- DB保存ロジック ---
                    source_string = (
                        f"{hotel.id}-"
                        f"{review_data['reviewer_name']}-"
                        f"{review_data['review_date']}-"
                        f"{review_data['review_comment']}"
                    )
                    review_hash = hashlib.sha256(
                        source_string.encode("utf-8")
                    ).hexdigest()

                    try:
                        # データの整形（クリーニング）
                        score_str = review_data.get("overall_score")
                        overall_score = (
                            int(score_str)
                            if score_str and score_str.isdigit()
                            else None
                        )
                        reviewer_name = review_data["reviewer_name"]
                        review_date = review_data["review_date"]
                        traveler_type = review_data["traveler_type"]
                        review_comment = review_data["review_comment"]
                        translated_review_comment = review_data[
                            "translated_review_comment"
                        ]

                        # update_or_createでDBに保存/更新
                        obj, created = Review.objects.update_or_create(
                            review_hash=review_hash,
                            defaults={
                                "hotel": hotel,
                                "overall_score": overall_score,
                                "reviewer_name": reviewer_name,
                                "review_date": review_date,
                                "traveler_type": traveler_type,
                                "review_comment": review_comment,
                                "translated_review_comment": translated_review_comment,
                            },
                        )

                        if created:
                            saved_count += 1
                        else:
                            updated_count += 1

                    except (ValueError, KeyError) as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  データ整形エラー: {e}。スキップします. データ: {review_data}"
                            )
                        )
                        skipped_count += 1
                        continue
                # --- DB保存ロジック終了 ---

                self.stdout.write(self.style.SUCCESS("-" * 50))
                self.stdout.write(self.style.SUCCESS("DB保存処理が完了しました。"))
                self.stdout.write(f"  - 新規保存: {saved_count} 件")
                self.stdout.write(f"  - 更新: {updated_count} 件")
                self.stdout.write(f"  - スキップ: {skipped_count} 件")
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"クローリングはスキップされました (--export-only)。Excel出力のみ実行します。"
                )
            )

        # --- ここからExcel出力処理 ---
        if should_export_excel:
            self.stdout.write(
                f"Excel出力フラグが有効です。データベースから全口コミ情報を取得し、Excelファイルを作成します..."
            )

            # DBから、Excelに出力したいフィールドのみを効率的に取得
            fields_to_get = list(EXCEL_HEADER_MAP.values())

            # .values()にフィールド名を指定
            # export-onlyモードでは、DBから既存データを取得することが目的となる
            all_reviews = Review.objects.filter(hotel=hotel).values(*fields_to_get)

            if not all_reviews:
                self.stdout.write(
                    self.style.WARNING(
                        "データベースに口コミ情報がありませんでした。Excel出力はスキップします。"
                    )
                )
            else:
                # 取得したデータをpandasのDataFrameに変換
                df = pd.DataFrame(all_reviews)

                # 列名を日本語のヘッダーにリネームする
                rename_map = {v: k for k, v in EXCEL_HEADER_MAP.items()}
                df.rename(columns=rename_map, inplace=True)

                # Excelで表示したい順番に列を並べ替える
                df = df[list(EXCEL_HEADER_MAP.keys())]

                # ファイル名に使用できない文字（スペースなど）をアンダースコアに置換
                safe_ota_name = re.sub(r"[^\w\-]", "_", hotel.ota.name)
                safe_hotel_name = re.sub(r"[^\w\-]", "_", hotel.hotel_name)

                new_base_filename = f"{safe_ota_name}_{safe_hotel_name}"

                # ヘルパー関数を呼び出してExcelに出力
                export_dataframe_to_excel(
                    df=df, base_filename=new_base_filename, stdout_writer=self
                )
        else:
            self.stdout.write(
                "Excel出力フラグが無効です。Excel出力はスキップしました。"
            )
        # --- Excel出力処理ここまで ---
