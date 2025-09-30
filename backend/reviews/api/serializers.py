from rest_framework import serializers
from ..models import CrawlTarget, Ota

class HotelSerializer(serializers.ModelSerializer):
    """クロール対象のリストを返すためのシリアライザー"""

    # ForeignKey先のOtaモデルの名前を直接取得する
    ota_name = serializers.CharField(source="ota.name", read_only=True)

    class Meta:
        model = CrawlTarget
        # APIで返したいフィールドを指定
        fields = ["id", "hotel_name", "ota_name", "crawl_url"]


class CrawlTargetStatusSerializer(serializers.ModelSerializer):
    """特定のクロール対象の実行ステータスを返すためのシリアライザー"""

    ota_name = serializers.CharField(source="ota.name", read_only=True)

    class Meta:
        model = CrawlTarget
        fields = [
            "id",
            "hotel_name",
            "ota_name",
            "last_crawl_status",
            "last_crawled_at",
            "last_crawl_message",
        ]
