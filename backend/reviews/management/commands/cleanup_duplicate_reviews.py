from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction

from reviews.models import Review 

class Command(BaseCommand):
    help = (
        "重複したレビューを特定し、クリーンアップします。"
        "デフォルトではドライランモードで実行されます。"
    )
    #  python manage.py cleanup_duplicate_reviews
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="実際に重複レコードの削除を実行します。このオプションがない場合はドライラン（報告のみ）です。",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        is_dry_run = not options["execute"]

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "=== ドライランモードで実行します (データベースの変更は行われません) ==="
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("=== 重複レビューの削除処理を開始します ===")
            )

        # 重複を判定するためのキーとなるフィールドを指定
        duplicate_check_keys = [
            "crawl_target",
            "reviewer_name",
            "review_date",
            "overall_score_original",
        ]

        # 上記キーの組み合わせが完全に一致するレコードをグループ化し、
        # 2件以上存在するグループ（＝重複）を抽出
        duplicates = (
            Review.objects.values(*duplicate_check_keys)
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .order_by("-count")
        )

        if not duplicates:
            self.stdout.write(
                self.style.SUCCESS("重複したレビューは見つかりませんでした。")
            )
            return

        self.stdout.write(f"{len(duplicates)} 件の重複グループが見つかりました。")

        total_deleted_count = 0

        for i, group in enumerate(duplicates):
            count = group.pop("count")
            self.stdout.write("-" * 40)
            self.stdout.write(
                f"グループ {i+1}/{len(duplicates)}: {count}件の重複があります"
            )
            # self.stdout.write(f"  キー: {group}") # デバッグ用にキー情報を表示

            # このグループに属する全てのレビューオブジェクトを取得
            # idの降順でソートすることで、通常は新しいレコード（IDが大きい）が先頭に来る
            reviews_in_group = Review.objects.filter(**group).order_by("-id")

            # --- 削除ロジック ---
            # 保持するレコードを1つ選ぶ。
            # ここでは「最も新しく作られた（IDが最大の）レコード」を保持する戦略をとる。
            review_to_keep = reviews_in_group.first()
            reviews_to_delete = reviews_in_group.exclude(pk=review_to_keep.pk)

            self.stdout.write(
                self.style.SUCCESS(
                    f"  [保持]: Review ID {review_to_keep.id} (作成日時: {review_to_keep.created_at})"
                )
            )

            for review in reviews_to_delete:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [削除対象]: Review ID {review.id} (作成日時: {review.created_at})"
                    )
                )
                if not is_dry_run:
                    review.delete()
                total_deleted_count += 1

        self.stdout.write("=" * 40)
        self.stdout.write(self.style.SUCCESS("処理が完了しました。"))
        if is_dry_run:
            self.stdout.write(
                f"削除対象となるレコードは合計 {total_deleted_count} 件です。"
            )
            self.stdout.write(
                "実際に削除するには --execute オプションを付けて再実行してください。"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"合計 {total_deleted_count} 件の重複レコードを削除しました。"
                )
            )
