from django.db import migrations
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Hotel = apps.get_model("reviews", "Hotel")
    for hotel in Hotel.objects.all():
        if not hotel.slug:
            # ユニーク制約を考慮し、重複した場合は末尾にIDなどをつける
            base_slug = slugify(hotel.name, allow_unicode=True)
            slug = base_slug
            counter = 1
            while Hotel.objects.filter(slug=slug).exclude(pk=hotel.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            hotel.slug = slug
            hotel.save(update_fields=["slug"])  # slugフィールドのみを更新


class Migration(migrations.Migration):

    dependencies = [
        (
            "reviews",
            "0003_auto_20251010_1234",
        ),  # 依存する前のマイグレーションファイル名
    ]

    operations = [
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
    ]
