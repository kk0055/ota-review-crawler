import os
import shutil


home_dir = os.path.expanduser("~")

# 削除対象のキャッシュディレクトリのフルパスを構築
cache_dir = os.path.join(home_dir, ".wdm")

print(f"削除対象のキャッシュディレクトリ: {cache_dir}")

# ディレクトリが実際に存在するかどうかを確認
if os.path.exists(cache_dir):
    try:
        # フォルダを中身ごと完全に削除
        shutil.rmtree(cache_dir)
        print("キャッシュディレクトリを正常に削除しました。")
    except Exception as e:
        print(f"キャッシュの削除中にエラーが発生しました: {e}")
else:
    print("キャッシュディレクトリが見つかりませんでした。")
