from django.core.management.base import BaseCommand, CommandError
from reviews.models import Hotel 

class Command(BaseCommand):
    help = "新しいホテルマスター情報を登録します。すでに存在する場合は何もしません。"

    # python manage.py register_hotel "ノボテル奈良"
    def add_arguments(self, parser):
        parser.add_argument(
            "hotel_name",
            type=str,
            help="登録するホテルの正式名称 (例: 帝国ホテル東京)"
        )

    def handle(self, *args, **options):
        hotel_name = options["hotel_name"].strip()

        if not hotel_name:
            raise CommandError("ホテル名は空にできません。")

        hotel, created = Hotel.objects.get_or_create(name=hotel_name)

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'ホテル "{hotel.name}" をマスターに正常に登録しました。'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'ホテル "{hotel.name}" は既にマスターに登録されています。'
                )
            )
