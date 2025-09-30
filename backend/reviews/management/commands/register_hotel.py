from django.core.management.base import BaseCommand, CommandError
from reviews.models import Ota, CrawlTarget


class Command(BaseCommand):
    help = "指定されたOTAサイトに新しいホテルを登録します。"

    # 例： "h103382146" がExpedia内のIDだと仮定
    # python manage.py register_hotel "Expedia" "h103382146" "ノボテル奈良" --url "https://www.expedia.co.jp/Nara-Hotels-Novotel-Nara.h103382146.Hotel-Information"

    def add_arguments(self, parser):
        parser.add_argument(
            "ota_name", type=str, help="関連付けるOTAサイトの名前 (例: Booking.com)"
        )
        parser.add_argument("hotel_id", type=str, help="OTA内でのユニークなホテルID")
        parser.add_argument("hotel_name", type=str, help="登録するホテルの名前")
        parser.add_argument("--url", type=str, help="クロール対象のURL", default=None)

    def handle(self, *args, **options):
        ota_name = options["ota_name"]
        hotel_id = options["hotel_id"]
        hotel_name = options["hotel_name"]
        crawl_url = options["url"]

        # まず、指定されたOTAが存在するか確認する
        try:
            ota = Ota.objects.get(name=ota_name)
        except Ota.DoesNotExist:
            # CommandErrorを発生させると、コマンドがエラーとして終了する
            raise CommandError(
                f'OTAサイト "{ota_name}" が見つかりません。先に register_ota コマンドで登録してください。'
            )

        # OTAとホテルIDの組み合わせでホテルを検索または作成
        hotel, created = CrawlTarget.objects.get_or_create(
            ota=ota,
            hotel_id_in_ota=hotel_id,
            defaults={
                "hotel_name": hotel_name,
                "crawl_url": crawl_url,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'"{hotel.hotel_name}" ({ota.name}) を正常に登録しました。'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'"{hotel.hotel_name}" (ID: {hotel_id}) は {ota.name} に既に存在します。'
                )
            )
