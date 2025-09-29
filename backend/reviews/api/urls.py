from django.urls import path
from .views import HotelListAPIView

urlpatterns = [
    path("hotels/", HotelListAPIView.as_view(), name="hotel-list"),
]
