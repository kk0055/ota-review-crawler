from django.urls import path
from .views import (
    OtaListView,
    HotelListAPIView,
    StartCrawlerAPIView,
    ExportExcelAPIView,
    CrawlStatusAPIView,
)

urlpatterns = [
    path("otas/", OtaListView.as_view(), name="ota-list"),
    path("hotels/", HotelListAPIView.as_view(), name="hotel-list"),
    path("crawlers/start/", StartCrawlerAPIView.as_view(), name="start-crawler"),
    path("export/", ExportExcelAPIView.as_view(), name="export-file"),
    path(
        "crawl-status/<int:hotel_id>/",
        CrawlStatusAPIView.as_view(),
        name="crawl-status",
    ),
]
