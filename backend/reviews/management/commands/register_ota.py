from django.core.management.base import BaseCommand, CommandError
from reviews.models import Ota  


class Command(BaseCommand):
    help = (
        "OTAサイトを登録します。個別登録と、--initフラグによる一括初期登録が可能です。"
    )
    # ---【一括で初期登録する場合】
    # python manage.py register_ota --init

    # ---【個別に追加登録する場合】
    # 例：じゃらんnetを追加
    # python manage.py register_ota "じゃらんnet" --base_url "https://www.jalan.net/"

    # --- 一括登録用のデータリスト ---
    OTA_INITIAL_DATA = [
        {"name": "Expedia", "url": "https://www.expedia.co.jp/"},
        {"name": "楽天トラベル", "url": "https://travel.rakuten.co.jp/"},
        {"name": "Google", "url": "https://www.google.com/travel"},
        # {"name": "Booking.com", "url": "https://www.booking.com/"},
        # {"name": "Agoda", "url": "https://www.agoda.com/ja-jp/"},
        # {"name": "一休.com", "url": "https://www.ikyu.com/"},
    ]

    def add_arguments(self, parser):
        # 個別登録用の引数 (nargs='?' でオプショナルにする)
        parser.add_argument(
            "name",
            nargs="?",
            type=str,
            default=None,
            help="登録するOTAサイトの名前 (例: Booking.com)",
        )
        parser.add_argument(
            "--base_url",
            type=str,
            help="OTAサイトのベースURL (個別登録時のみ有効)",
            default=None,
        )
        # 一括登録を実行するためのフラグ
        parser.add_argument(
            "--init",
            action="store_true",
            help="定義済みの主要なOTAサイトを一括で初期登録します。",
        )

    def handle(self, *args, **options):
        # --init フラグが指定されていれば、一括登録処理を実行
        if options["init"]:
            self.handle_initial_registration()
            return

        # --init フラグがない場合は、個別登録処理
        ota_name = options["name"]
        if not ota_name:
            raise CommandError(
                "エラー: 登録するOTA名が指定されていません。\n"
                '個別登録: python manage.py register_ota "サイト名"\n'
                "一括登録: python manage.py register_ota --init"
            )

        self.handle_single_registration(ota_name, options["base_url"])

    def handle_initial_registration(self):
        """定義済みリストからOTAサイトを一括登録する処理"""
        self.stdout.write("主要OTAサイトの一括登録を開始します...")
        created_count = 0
        skipped_count = 0

        for ota_data in self.OTA_INITIAL_DATA:
            ota, created = Ota.objects.get_or_create(
                name=ota_data["name"], defaults={"base_url": ota_data["url"]}
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"  [新規作成] {ota.name} を登録しました。")
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f"  [スキップ] {ota.name} は既に存在します。")
                )
                skipped_count += 1

        self.stdout.write("-" * 40)
        self.stdout.write(
            self.style.SUCCESS(
                f"処理完了。新規登録: {created_count}件, スキップ: {skipped_count}件"
            )
        )

    def handle_single_registration(self, name, base_url):
        """単一のOTAサイトを登録する処理"""
        ota, created = Ota.objects.update_or_create(
            name=name, defaults={"base_url": base_url}
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'OTAサイト "{ota.name}" を正常に登録しました。')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'OTAサイト "{ota.name}" は既に存在します。')
            )
