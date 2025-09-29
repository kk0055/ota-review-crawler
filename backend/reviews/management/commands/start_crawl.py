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
}

class Command(BaseCommand):
    help = "指定されたホテルの口コミ情報をクロールしてDBに保存します。"
    # python manage.py start_crawl "ノボテル奈良"
    # python manage.py start_crawl "ノボテル奈良" --start-date 2025-04-01 --end-date 2024-07-30

    def add_arguments(self, parser):
        parser.add_argument(
            "hotel_name",
            type=str,
            help="クロール対象のホテルの名前 (例: 'ノボテル奈良')",
        )
        parser.add_argument(
            "--otas",
            nargs='+', # 1つ以上のOTA名をリストで受け取る
            default=None, # 指定がない場合はNone
            help="クロール対象のOTA名のリスト (例: Expedia agoda)。指定がない場合は登録されている全OTAが対象。"
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
        otas = options["otas"]
        start_date = options["start_date"]
        end_date = options["end_date"]
        should_export_excel = options["export_excel"]
        export_only = options["export_only"]

        # DBから対象ホテル情報を取得
        hotels_to_process = Hotel.objects.filter(
            hotel_name=hotel_name
        ).select_related("ota")
        
        if otas:
            hotels_to_process = hotels_to_process.filter(ota__name__in=otas)

        if not hotels_to_process.exists():
            ota_filter_msg = f" (OTA: {', '.join(otas)})" if otas else ""
            raise CommandError(f"ホテル '{hotel_name}'{ota_filter_msg} はDBに登録されていません。")


        self.stdout.write(self.style.SUCCESS(f"--- 処理開始: {hotel_name} ({hotels_to_process.count()}件のOTAが対象) ---"))


        # --- 3. OTAごとのループ処理 ---
        for hotel in hotels_to_process:
            self.stdout.write(f"\n▶ 処理中: {hotel.ota.name} (Hotel ID: {hotel.id})")

            if not hotel.crawl_url and not export_only:
                self.stdout.write(self.style.WARNING("  クロールURLが未設定のため、クロール処理をスキップします。"))
                continue

            # --- 4. クロール & DB保存処理 ---
            if not export_only:
                reviews_list = []
                if not hotel.crawl_url:
                    self.stdout.write(self.style.WARNING("  クロールURLが未設定のため、クロール処理をスキップします。"))
                    # Excel出力処理に進むため、continueはしない
                else:
                    try:
                        # OTAによって担当クローラーを切り替える
                        if hotel.ota.name == "Expedia":
                            reviews_list = scrape_expedia_reviews(hotel.crawl_url, start_date_str=start_date, end_date_str=end_date)
                        elif hotel.ota.name == "agoda":
                            # reviews_list = fetch_agoda_reviews(hotel.crawl_url, start_date_str=start_date, end_date_str=end_date)
                            print('Skip')
                        else:
                            self.stdout.write(self.style.WARNING(f"  '{hotel.ota.name}' に対応するクローラーがありません。"))

                    except Exception as e:
                        # 例外をキャッチし、エラーメッセージを表示して処理を続行する
                        self.stderr.write(self.style.ERROR(f"  [エラー] {hotel.ota.name}のクロール中にエラーが発生しました: {e}"))
                        self.stderr.write(self.style.ERROR(f"  {hotel.ota.name}の処理を中断し、次のOTAに進みます。"))
                

                # DB保存ロジック
                if reviews_list:
                    self.save_reviews_to_db(reviews_list, hotel)
                else:
                    self.stdout.write("  口コミは取得されませんでした。")
            else:
                self.stdout.write("  クローリングはスキップされました (--export-only)。")

            # --- 5. Excel出力処理 ---
            if should_export_excel:
                self.export_reviews_to_excel(hotel)
            else:
                self.stdout.write("  Excel出力はスキップされました (--no-excel-export)。")

        self.stdout.write(self.style.SUCCESS(f"\n--- '{hotel_name}' に関する全ての処理が完了しました ---"))



    def save_reviews_to_db(self, reviews_list, hotel):
        """取得したレビューのリストをデータベースに保存/更新します。"""
        self.stdout.write(f"  取得した {len(reviews_list)} 件の口コミをDBに保存します...")
        saved_count, updated_count, skipped_count = 0, 0, 0

        for review_data in reviews_list:
            try:
                # 重複判定のためのハッシュを生成
                source_string = f"{hotel.id}-{review_data.get('reviewer_name','')}-{review_data.get('review_date','')}-{review_data.get('review_comment','')}"
                review_hash = hashlib.sha256(source_string.encode("utf-8")).hexdigest()

                # update_or_createでDBに保存/更新
                _obj, created = Review.objects.update_or_create(
                    review_hash=review_hash,
                    defaults={
                        "hotel": hotel,
                        "overall_score": int(review_data["overall_score"]) if review_data.get("overall_score", "").isdigit() else None,
                        "reviewer_name": review_data.get("reviewer_name"),
                        "review_date": review_data.get("review_date"),
                        "traveler_type": review_data.get("traveler_type"),
                        "review_comment": review_data.get("review_comment"),
                        "translated_review_comment": review_data.get("translated_review_comment"),
                    },
                )
                if created: saved_count += 1
                else: updated_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"    DB保存エラー: {e} スキップします. データ: {review_data}"))
                skipped_count += 1
        
        self.stdout.write(f"  [DB保存結果] 新規: {saved_count}件, 更新: {updated_count}件, スキップ: {skipped_count}件")



    def export_reviews_to_excel(self, hotel):
        """指定されたホテルのレビューをDBから取得し、Excelファイルに出力します。"""
        self.stdout.write(f"  DBから口コミデータを取得してExcelファイルを作成します...")

        fields_to_get = list(EXCEL_HEADER_MAP.values())
        all_reviews = Review.objects.filter(hotel=hotel).values(*fields_to_get)

        if not all_reviews:
            self.stdout.write(
                self.style.WARNING(
                    "  DBに口コミ情報がないため、Excel出力はスキップします。"
                )
            )
            return

        df = pd.DataFrame(list(all_reviews))
        rename_map = {v: k for k, v in EXCEL_HEADER_MAP.items()}
        df.rename(columns=rename_map, inplace=True)
        df = df[list(EXCEL_HEADER_MAP.keys())]  # 列の並び替え

        safe_hotel_name = re.sub(r"[^\w\-]", "_", hotel.hotel_name)
        safe_ota_name = re.sub(r"[^\w\-]", "_", hotel.ota.name)
        base_filename = f"{safe_ota_name}_{safe_hotel_name}"

        export_dataframe_to_excel(
            df=df, base_filename=base_filename, stdout_writer=self
        )
