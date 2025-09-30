from rest_framework.generics import ListAPIView
from ..models import CrawlTarget
from .serializers import HotelSerializer, CrawlTargetStatusSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.management import call_command
import threading

# -----------------------------------------------------------------------------
# API Views
# -----------------------------------------------------------------------------
class HotelListAPIView(ListAPIView):
    """
    ホテルの一覧を返すAPIビュー
    /api/hotels/ でアクセスできるようにする
    """

    queryset = CrawlTarget.objects.select_related("ota").all()
    serializer_class = HotelSerializer


def run_command_in_thread(command_name, *args, **kwargs):
    """
    Djangoのコマンドを別スレッドで実行するためのヘルパー関数
    位置引数とキーワード引数を適切に処理する
    """
    cmd_args = list(args)
    for key, value in kwargs.items():
        if value is not None:
            if isinstance(value, bool) and value:
                cmd_args.append(f'--{key.replace("_", "-")}')
            elif isinstance(value, list):
                cmd_args.append(f'--{key.replace("_", "-")}')
                cmd_args.extend(value)
            elif not isinstance(value, bool):
                cmd_args.append(f'--{key.replace("_", "-")}')
                cmd_args.append(str(value))

    thread = threading.Thread(target=call_command, args=(command_name, *cmd_args))
    thread.start()


class BaseCrawlerActionView(APIView):
    """クロール/エクスポート処理の共通ロジックを持つ基底クラス"""

    export_only = False

    def post(self, request, *args, **kwargs):
        selected_hotel_id = request.data.get("hotel", {}).get("id")
        options = request.data.get("options", {})

        if not selected_hotel_id:
            return Response(
                {"error": "Hotel IDは必須です。"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # フロントからはIDでホテルが来るので、そこから名前を取得する
            base_hotel = CrawlTarget.objects.get(pk=selected_hotel_id)
            hotel_name = base_hotel.hotel_name

            # コマンドに渡す引数を準備
            command_kwargs = {
                "otas": options.get("otas"),
                "start_date": options.get("startDate"),
                "end_date": options.get("endDate"),
                "export_only": self.export_only,
            }

            # コマンドをバックグラウンドで実行
            # hotel_name は位置引数、他はキーワード引数として渡す
            run_command_in_thread("start_crawl", hotel_name, **command_kwargs)

            action_name = "ファイル出力" if self.export_only else "クロール処理"
            message = (
                f"'{hotel_name}' の {action_name} をバックグラウンドで開始しました。"
            )

            return Response({"message": message}, status=status.HTTP_202_ACCEPTED)

        except CrawlTarget.DoesNotExist:
            return Response(
                {"error": "指定されたホテルが見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            # ログ出力などを推奨
            return Response(
                {"error": "サーバー内部でエラーが発生しました。"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StartCrawlerAPIView(BaseCrawlerActionView):
    export_only = False


class ExportFileAPIView(BaseCrawlerActionView):
    export_only = True


class CrawlStatusAPIView(APIView):
    def get(self, request, hotel_name):
        targets = CrawlTarget.objects.filter(hotel_name=hotel_name)
        serializer = CrawlTargetStatusSerializer(targets, many=True)
        return Response(serializer.data)
