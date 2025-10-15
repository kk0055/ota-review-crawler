from rest_framework.generics import ListAPIView
from ..models import CrawlTarget, Hotel,Ota
from .serializers import OtaSerializer, HotelSerializer, CrawlTargetStatusSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.management import call_command
import threading
from reviews.services import get_reviews_as_dataframe, generate_excel_in_memory
from django.http import HttpResponse
import io
import re
from datetime import datetime
from urllib.parse import quote
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


# -----------------------------------------------------------------------------
# API Views
# -----------------------------------------------------------------------------
class OtaListView(ListAPIView):
    """
    有効なOTAサイトを、表示順で一覧表示するためのAPIビュー
    is_active=True のもののみを返します。
    """
    # is_active=True でフィルターし、display_orderで並び替え
    queryset = Ota.objects.filter(is_active=True).order_by("display_order")
    serializer_class = OtaSerializer


class HotelListAPIView(ListAPIView):
    """
    ホテルの一覧を返すAPIビュー
    /api/hotels/ でアクセスできるようにする
    """

    queryset = Hotel.objects.all().order_by("name")
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
            hotel_master = Hotel.objects.get(pk=selected_hotel_id)
            hotel_name = hotel_master.name

            # コマンドに渡す引数を準備
            command_kwargs = {
                "ota_ids": options.get("otas"),
                "start_date": options.get("startDate"),
                "end_date": options.get("endDate"),
            }

            # コマンドをバックグラウンドで実行
            # hotel_name は位置引数、他はキーワード引数として渡す
            run_command_in_thread("start_crawl", hotel_name, **command_kwargs)

            action_name = "ファイル出力" if self.export_only else "クロール処理"
            message = (
                f"「{hotel_name}」 の {action_name} をバックグラウンドで開始しました。"
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

    def get(self, request, hotel_id):
        try:
            hotel_master = Hotel.objects.get(pk=hotel_id)
            targets = CrawlTarget.objects.filter(hotel=hotel_master)
            serializer = CrawlTargetStatusSerializer(targets, many=True)
            return Response(serializer.data)
        except Hotel.DoesNotExist:
            return Response(
                {"error": f"ホテル '{hotel_id}' が見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )


class ExportExcelAPIView(APIView):
    """
    リクエストされたホテルのレビューデータをExcelファイルとして生成し、
    直接ダウンロードさせるAPIビュー。
    """

    def post(self, request, *args, **kwargs):

        hotel_data = request.data.get("hotel", {})
        hotel_name = hotel_data.get("name") 
        selected_hotel_id = hotel_data.get("id")
        options_data = request.data.get("options", {})
        otas_ids = options_data.get("otas")
        start_date = options_data.get("startDate")
        end_date = options_data.get("endDate")

        if not hotel_name:
            return Response(
                {"error": "hotel_nameは必須です。"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if not Hotel.objects.filter(name=hotel_name).exists():
                return Response(
                    {"error": f"ホテル '{hotel_name}' が見つかりません。"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # --- サービス関数を呼び出す (hotel_name を渡す) ---
            df = get_reviews_as_dataframe(
                hotel_name=hotel_name,
                hotel_id=selected_hotel_id, 
                ota_ids=otas_ids,
                start_date=start_date,
                end_date=end_date,
            )
            if df.empty:
                return Response(
                    {"message": "エクスポート対象のデータがありませんでした。"},
                    status=status.HTTP_204_NO_CONTENT,
                )

            # --- ファイル名生成とレスポンス作成 (ここは前回の回答と同じ) ---
            safe_hotel_name = re.sub(r'[\\/*?:"<>|]', "_", hotel_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_filename = f"{safe_hotel_name}_{timestamp}.xlsx"

            excel_data_buffer = generate_excel_in_memory(df)

            response = HttpResponse(
                excel_data_buffer,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f"attachment; filename*=UTF-8''{quote(final_filename)}"
            )

            return response

        except CrawlTarget.DoesNotExist:
            return Response(
                {"error": f" {hotel_name} のホテルが見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"サーバー内部でエラーが発生しました: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
