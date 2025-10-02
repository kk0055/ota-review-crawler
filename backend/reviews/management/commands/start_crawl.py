from django.core.management.base import BaseCommand, CommandError
from reviews.models import CrawlTarget,Hotel

from django.utils import timezone
from reviews.services import run_crawl_and_save
from reviews.utils.excel_exporter import export_dataframe_to_excel

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
            nargs="+",  # 1つ以上のOTA名をリストで受け取る
            default=None,  # 指定がない場合はNone
            help="クロール対象のOTA名のリスト (例: Expedia agoda)。指定がない場合は登録されている全OTAが対象。",
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

    def handle(self, *args, **options):
        hotel_name = options["hotel_name"]
        otas = options["otas"]
        start_date = options["start_date"]
        end_date = options["end_date"]

        try:
          
            hotel_master = Hotel.objects.get(name=hotel_name)
            
        except Hotel.DoesNotExist:
            raise CommandError(
                f"ホテルマスター '{hotel_name}' がDBに登録されていません。"
                f'先に `register_hotel "{hotel_name}"` コマンドで登録してください。'
            )
            
        crawl_targets = CrawlTarget.objects.filter(
            hotel=hotel_master
        ).select_related("ota")

        if otas:
            crawl_targets = crawl_targets.filter(ota__name__in=otas)

        if not crawl_targets.exists():
            ota_filter_msg = f" (OTA: {', '.join(otas)})" if otas else ""
            raise CommandError(
                f"ホテル '{hotel_name}' はマスターに存在しますが、クロール対象{ota_filter_msg}が設定されていません。"
                f"`add_crawl_target` コマンドで対象を追加してください。"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"--- 処理開始: {hotel_name} ({crawl_targets.count()}件のOTAが対象) ---"
            )
        )

        # --- 3. OTAごとのループ処理 ---
        for target in crawl_targets:
            self.stdout.write(f"\n▶ 処理中: {target.ota.name} (Hotel ID: {target.id})")
            target.last_crawl_status = CrawlTarget.CrawlStatus.PENDING
            target.save()

            success, message = run_crawl_and_save(target, start_date, end_date)

            target.last_crawl_status = CrawlTarget.CrawlStatus.SUCCESS if success else CrawlTarget.CrawlStatus.FAILURE
            target.last_crawl_message = message
            target.last_crawled_at = timezone.now()
            target.save()
            self.stdout.write(f"  結果: {message}")


        # if should_export_excel:
        #     self.stdout.write("\n▶ Excelファイルを作成します...")

        #     df = get_reviews_as_dataframe(hotel_name, otas)

        #     if df.empty:
        #         self.stdout.write(
        #             self.style.WARNING("  Excel出力対象のデータがありません。")
        #         )
        #     else:
        #         # コマンド実行時はディスクにファイルを保存
        #         export_dataframe_to_excel(
        #             df=df, base_filename=hotel_name, stdout_writer=self
        #         )

        # self.stdout.write(self.style.SUCCESS("\n--- 全ての処理が完了しました ---"))
