import pandas as pd
from datetime import datetime
import re
import os

def export_dataframe_to_excel(df: pd.DataFrame, base_filename: str, stdout_writer):
    """
    DataFrameをExcelファイルとして出力し、出力状況をコンソールに報告します。

    :param df: 出力対象のpandas DataFrame
    :param base_filename: 日付/時刻が付加される前のベースとなるファイル名
    :param stdout_writer: Django Commandのインスタンス (self)。
                          メッセージ出力のために stdout_writer.stdout と stdout_writer.style を使用します。
    """
    try:
        # ファイル名に使用できない文字をクリーニング
        safe_base_filename = re.sub(r"[^\w\-\.]", "_", base_filename)

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        # 実行日時をファイル名に追加
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_only = f"{safe_base_filename}_{timestamp}.xlsx"
        output_filepath = os.path.join(output_dir, filename_only)

        # Excelファイルとして保存
        df.to_excel(output_filepath, index=False, engine="openpyxl")

        # 成功メッセージの出力
        stdout_writer.stdout.write(
            stdout_writer.style.SUCCESS(
                f'Excelファイル "{output_filepath}" が正常に作成されました。'
            )
        )
        stdout_writer.stdout.write(f"  パス: {os.path.abspath(output_filepath)}")

    except Exception as e:
        # 失敗メッセージの出力
        stdout_writer.stdout.write(
            stdout_writer.style.ERROR(f"Excel出力中に致命的なエラーが発生しました: {e}")
        )
