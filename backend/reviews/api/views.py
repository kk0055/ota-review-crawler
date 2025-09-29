
from rest_framework.generics import ListAPIView
from ..models import Hotel
from .serializers import HotelSerializer


# -----------------------------------------------------------------------------
# API Views
# -----------------------------------------------------------------------------
class HotelListAPIView(ListAPIView):
    """
    ホテルの一覧を返すAPIビュー
    /api/hotels/ でアクセスできるようにする
    """

    queryset = Hotel.objects.select_related("ota").all()
    serializer_class = HotelSerializer
