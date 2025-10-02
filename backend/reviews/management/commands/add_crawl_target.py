from django.core.management.base import BaseCommand, CommandError
from reviews.models import (
    Ota,
    Hotel,
    CrawlTarget,
)  


class Command(BaseCommand):
    help = "既存のホテルマスターを、指定したOTAサイトのクロール対象として登録します。"
    #  python manage.py add_crawl_target "Expedia" "ノボテル奈良" "h103382146" --url "https://www.expedia.co.jp/Nara-Hotels-Novotel-Nara.h103382146.Hotel-Information"
    def add_arguments(self, parser):
        parser.add_argument("ota_name", type=str, help="関連付けるOTAサイトの名前")
        parser.add_argument(
            "hotel_master_name",
            type=str,
            help="マスターに登録されているホテルの正式名称",
        )
        parser.add_argument(
            "hotel_id_in_ota", type=str, help="OTAサイト内でのユニークなホテルID"
        )
        parser.add_argument("--url", type=str, help="クロール対象のURL", required=True)

    def handle(self, *args, **options):
        ota_name = options["ota_name"]
        hotel_master_name = options["hotel_master_name"]
        hotel_id_in_ota = options["hotel_id_in_ota"]
        crawl_url = options["url"]

        # 1. 関連するOtaとHotelマスターを取得
        try:
            ota = Ota.objects.get(name=ota_name)
        except Ota.DoesNotExist:
            raise CommandError(
                f'OTAサイト "{ota_name}" が見つかりません。先に登録してください。'
            )

        try:
            hotel_master = Hotel.objects.get(name=hotel_master_name)
        except Hotel.DoesNotExist:
            raise CommandError(
                f'ホテルマスター "{hotel_master_name}" が見つかりません。'
                f'先に `register_hotel "{hotel_master_name}"` コマンドで登録してください。'
            )

        # 2. CrawlTarget を作成または取得
        target, created = CrawlTarget.objects.get_or_create(
            ota=ota,
            hotel=hotel_master,
            defaults={
                "hotel_id_in_ota": hotel_id_in_ota,
                "crawl_url": crawl_url,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'ホテル "{hotel_master.name}" を {ota.name} のクロール対象として正常に登録しました。'
                )
            )
        else:
            # 既に存在する場合、情報を更新するオプションも考えられる
            # target.crawl_url = crawl_url
            # target.save()
            self.stdout.write(
                self.style.WARNING(
                    f'ホテル "{hotel_master.name}" は既に {ota.name} のクロール対象として登録されています。'
                )
            )
