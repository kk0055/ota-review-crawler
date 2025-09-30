from django.urls import path
from .views import (
    HotelListAPIView,
    StartCrawlerAPIView,
    ExportExcelAPIView,
    CrawlStatusAPIView,
)

urlpatterns = [
    path("hotels/", HotelListAPIView.as_view(), name="hotel-list"),
    path("crawlers/start/", StartCrawlerAPIView.as_view(), name="start-crawler"),
    path("export/", ExportExcelAPIView.as_view(), name="export-file"),
    path(
        "crawl-status/<str:hotel_name>/",
        CrawlStatusAPIView.as_view(),
        name="crawl-status-api",
    ),
]
