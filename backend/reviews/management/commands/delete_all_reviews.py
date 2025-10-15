import sys
from django.core.management.base import BaseCommand
from django.db import transaction

from reviews.models import Review, ReviewScore 


class Command(BaseCommand):
    help = (
        "【危険】すべてのレビュー関連データ（Review, ReviewScore）を削除します。"
        "実行には確認プロンプトが必要です。"
        # python manage.py delete_all_reviews
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="確認プロンプトを表示せずに実行します。（自動化スクリプト用・使用注意）",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # 関連するモデルをリストアップ
        models_to_delete = [Review, ReviewScore]

        # まず、削除対象の件数をユーザーに提示する
        counts = {}
        total_count = 0
        for model in models_to_delete:
            count = model.objects.count()
            counts[model.__name__] = count
            total_count += count

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("削除対象のレビューデータはありませんでした。")
            )
            return

        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(
            self.style.WARNING("           警告：この操作は元に戻せません！")
        )
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write("以下のモデルからすべてのデータが削除されます：")
        for model_name, count in counts.items():
            self.stdout.write(f"  - {model_name}: {count} 件")
        self.stdout.write("-" * 60)

        # --no-input フラグがなければ、確認プロンプトを表示
        if not options["no_input"]:
            confirm = input(
                "本当にすべてのレビューデータを削除しますか？ 'yes' と入力してください: "
            )
            if confirm != "yes":
                self.stdout.write(self.style.ERROR("操作がキャンセルされました。"))
                sys.exit(1)  # 0以外のステータスコードで終了

        # 確認が取れた場合のみ、削除処理を実行
        self.stdout.write("削除処理を開始します...")

        deleted_counts_total = {}
        for model in models_to_delete:
            # .delete()は (削除された件数, {モデルごとの件数}) のタプルを返す
            deleted_count, _ = model.objects.all().delete()
            deleted_counts_total[model.__name__] = deleted_count
            self.stdout.write(
                f"  {model.__name__} の全 {deleted_count} 件のデータを削除しました。"
            )

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(
            self.style.SUCCESS("すべてのレビュー関連データの削除が完了しました。")
        )
