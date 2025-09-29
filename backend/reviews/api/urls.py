from django.urls import path
from .views import (
    HotelListAPIView,
    StartCrawlerAPIView,
    ExportFileAPIView,
)  

urlpatterns = [
    path("hotels/", HotelListAPIView.as_view(), name="hotel-list"),
    path("crawlers/start/", StartCrawlerAPIView.as_view(), name="start-crawler"),
    path("export/", ExportFileAPIView.as_view(), name="export-file"),  
]
