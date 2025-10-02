from rest_framework import serializers

from ..models import CrawlTarget, Ota, Hotel


class HotelSerializer(serializers.ModelSerializer):
    """ホテルマスターの一覧を返すためのシリアライザー"""

    class Meta:
        model = Hotel
        fields = ["id", "name"]


class CrawlTargetStatusSerializer(serializers.ModelSerializer):
    """特定のクロール対象の実行ステータスを返すためのシリアライザー"""


    ota_name = serializers.CharField(source="ota.name", read_only=True)
    hotel_name = serializers.CharField(source="hotel.name", read_only=True)

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
