from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from reviews.models import Ota


class Command(BaseCommand):
    help = "定義済みリストに基づき、既存のOTAサイトの表示順と表示状態を一括更新します。"
    # python manage.py bulk_update_otas
    # --- 更新したいOTAのデータリスト ---
    # name: データベース上のOTA名と完全に一致させる必要があります。
    # display_order: 設定したい表示順の数値。
    # is_active: Trueなら表示、Falseなら非表示。
    OTA_UPDATE_DATA = [
        {"name": "Expedia", "display_order": 1, "is_active": True},
        {"name": "楽天トラベル", "display_order": 2, "is_active": True},
        {"name": "Booking.com", "display_order": 3, "is_active": True},
        {"name": "Agoda", "display_order": 4, "is_active": False},
        {"name": "じゃらんnet", "display_order": 5, "is_active": False},
        {"name": "一休.com", "display_order": 6, "is_active": False},
        {"name": "Googleトラベル", "display_order": 999, "is_active": False},
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際にデータベースを更新せず、実行される内容のプレビューのみを表示します。",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        is_dry_run = options["dry_run"]

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "=== ドライランモードで実行します (データベースへの変更は行われません) ==="
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("=== OTA情報の一括更新を開始します ===")
            )

        updated_count = 0
        skipped_count = 0
        not_found_count = 0

        for ota_data in self.OTA_UPDATE_DATA:
            target_name = ota_data["name"]

            try:
                # 更新対象のOTAを名前で検索
                ota_object = Ota.objects.get(name=target_name)

                # 更新が必要かどうかをチェック
                needs_update = (
                    ota_object.display_order != ota_data["display_order"]
                    or ota_object.is_active != ota_data["is_active"]
                )

                if needs_update:
                    old_order = ota_object.display_order
                    old_active = ota_object.is_active

                    # 新しい値をセット
                    ota_object.display_order = ota_data["display_order"]
                    ota_object.is_active = ota_data["is_active"]

                    # ドライランでなければ保存
                    if not is_dry_run:
                        # 更新するフィールドを明示することで効率化
                        ota_object.save(update_fields=["display_order", "is_active"])

                    msg = (
                        f"[更新] {ota_object.name}: "
                        f"表示順({old_order} -> {ota_object.display_order}), "
                        f"状態({old_active} -> {ota_object.is_active})"
                    )
                    self.stdout.write(self.style.SUCCESS(msg))
                    updated_count += 1
                else:
                    msg = f"[スキップ] {target_name} は既に最新の状態です。"
                    self.stdout.write(
                        self.style.NOTICE(msg)
                    ) 
                    skipped_count += 1

            except Ota.DoesNotExist:
                # データベースに存在しないOTAはスキップして警告
                msg = f"[警告] {target_name} はデータベースに存在しません。スキップします。"
                self.stdout.write(self.style.ERROR(msg))
                not_found_count += 1

        self.stdout.write("-" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"処理完了。更新: {updated_count}件, スキップ(変更なし): {skipped_count}件, "
                f"対象なし: {not_found_count}件"
            )
        )
        if is_dry_run:
            self.stdout.write(
                self.style.WARNING("=== ドライランモードが終了しました ===")
            )
