from django.core.management.base import BaseCommand, CommandError
from reviews.models import Hotel, Review, Ota
from reviews.crawlers.expedia_crawler import (
    scrape_expedia_reviews,
)
from datetime import datetime
import re
import hashlib

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

    def handle(self, *args, **options):
        hotel_name = options["hotel_name"]
        ota_name = options["ota"]
        start_date = options["start_date"]
        end_date = options["end_date"]

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

        self.stdout.write(
            f"クロールを開始します: {hotel.hotel_name} ({hotel.ota.name})"
        )
        self.stdout.write(f"  URL: {hotel.crawl_url}")
        if start_date or end_date:
            self.stdout.write(
                f"  対象期間: {start_date or '指定なし'} 〜 {end_date or '指定なし'}"
            )
        # クローラーを実行
        # if hotel.ota.name == "Expedia":
        reviews_list = scrape_expedia_reviews(
            hotel.crawl_url, start_date_str=start_date, end_date_str=end_date
        )

        # elif hotel.ota.name == "Booking.com":
        #     print("Booking.comのを呼び出します...")
        #     reviews_list = scrape_booking_reviews(hotel.crawl_url)

        if not reviews_list:
            self.stdout.write(self.style.WARNING("口コミが取得できませんでした。"))
            return

        self.stdout.write(
            f"取得した {len(reviews_list)} 件の口コミをデータベースに保存します..."
        )

        saved_count = 0
        skipped_count = 0
        updated_count = 0

        for review_data in reviews_list:

            source_string = (
                f"{hotel.id}-"
                f"{review_data['reviewer_name']}-"
                f"{review_data['review_date']}-"
                f"{review_data['review_comment']}"
            )

            review_hash = hashlib.sha256(source_string.encode('utf-8')).hexdigest()

            try:
                # --- データの整形（クリーニング） ---
                score_str = review_data.get("overall_score")
                overall_score = int(score_str) if score_str and score_str.isdigit() else None
                reviewer_name = review_data["reviewer_name"]
                review_date = review_data["review_date"]
                traveler_type = review_data["traveler_type"]
                review_comment = review_data["review_comment"]
                translated_review_comment = review_data["translated_review_comment"]

                # --- update_or_createでDBに保存/更新 ---
                obj, created = Review.objects.update_or_create(
                    review_hash=review_hash,  # このキーでDBからレビューを探す
                    defaults={  # 見つかったらこの内容で更新、見つからなければこの内容で新規作成
                        "hotel": hotel,
                        "ota": hotel.ota_id,
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
                        f"  データ整形エラー: {e}。スキップします. データ: {review_data}"
                    )
                )
                skipped_count += 1
                continue

        # 最終結果を報告する
        self.stdout.write(self.style.SUCCESS("-" * 50))
        self.stdout.write(self.style.SUCCESS("処理が完了しました。"))
        self.stdout.write(f"  - 新規保存: {saved_count} 件")
        self.stdout.write(f"  - 更新: {updated_count} 件")
        self.stdout.write(f"  - スキップ: {skipped_count} 件")
