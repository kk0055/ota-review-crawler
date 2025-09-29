

from rest_framework import serializers
from ..models import Hotel


class HotelSerializer(serializers.ModelSerializer):
    """HotelモデルをJSONに変換するためのシリアライザー"""

    # ForeignKey先のOtaモデルの名前を直接取得する
    ota_name = serializers.CharField(source="ota.name", read_only=True)

    class Meta:
        model = Hotel
        # APIで返したいフィールドを指定
        fields = ["id", "hotel_name", "ota_name", "crawl_url"]
