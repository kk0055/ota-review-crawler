import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from datetime import datetime
import re
import pprint
from ..normalizer import DataNormalizer 
from reviews.utils import (
    normalize_score,
    detect_language,
    get_language_name_ja
)

def scrape_rakuten_travel_reviews(
    url: str,
    hotel_id: str, 
    start_date_str: str = None,
    end_date_str: str = None,
):
    """
    指定された楽天トラベルのホテルレビューページから口コミをスクレイピングする関数

    Args:
        url (str): クロールする楽天トラベルのレビューページのURL。
        start_date_str (str, optional): 収集開始日 (YYYY-MM-DD形式)。この日付より古い口コミが見つかると収集を停止します。
        end_date_str (str, optional): 収集終了日 (YYYY-MM-DD形式)。この日付より新しい口コミはスキップ。

    Returns:
        list: 収集した口コミデータのリスト。各要素は辞書型。
    """
    # === WebDriverのセットアップ===
    options = uc.ChromeOptions()
    options.add_argument("--lang=ja-JP")
    # サイトによってはヘッドレスモードがブロックされるため、必要に応じて有効化
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = uc.Chrome(options=options)
    driver.set_window_size(500, 500)
    wait = WebDriverWait(driver, 10) 

    ota_name = 'rakuten'
    normalizer = DataNormalizer()

    start_date_obj = None
    if start_date_str:
        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            print(f"収集開始日を設定: {start_date_obj}")
        except ValueError:
            print(f"エラー: 開始日の形式が不正です ('{start_date_str}')。")
            return []

    end_date_obj = None
    if end_date_str:
        try:
            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            print(f"収集終了日を設定: {end_date_obj}")
        except ValueError:
            print(f"エラー: 終了日の形式が不正です ('{end_date_str}')。")
            return []

    all_reviews_data = []
    page_count = 1
    stop_scraping = False

    try:
        print(f"アクセス中: {url}")
        driver.get(url)
        try:
            print("「最新の投稿順」に並び替えます...")
            
            # 1. 「最新の投稿順」のリンクが見つかるまで待機し、取得する
            sort_button = wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "最新の投稿順"))
            )
            
            # 2. リンクをクリックする
            sort_button.click()
            
            # 3. クリックによるページの再読み込みが完了し、口コミが表示されるまで待機
            print("ページの再読み込みを待機しています...")
            wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "commentBox"))
            )
            print("並び替えが完了しました。")

        except TimeoutException:
            print("「最新の投稿順」ボタンが見つからないか、並び替え後のページ読み込みに失敗しました。")
            # 並び替えに失敗した場合は、処理を中断するか、そのまま続行するかを決定
            # ここでは処理を中断する
            driver.quit()
            return []
        
        # === 口コミ収集のメインループ (ページが続く限り実行) ===
        while not stop_scraping:
            print(f"\n--- {page_count}ページ目の口コミを収集中 ---")

            # 口コミのコンテナ要素が読み込まれるまで待機
            try:
                wait.until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "commentBox"))
                )
            except TimeoutException:
                print("口コミが見つかりませんでした。")
                break

            review_elements = driver.find_elements(By.CLASS_NAME, "commentBox")
            print(f"{len(review_elements)}件の口コミを発見。")

            if not review_elements:
                print("このページに口コミはありません。収集を終了します。")
                break

            last_review_date_on_page = None
            # === 1ページ内の各口コミを処理 ===
            for review_element in review_elements:
                data = extract_review_data(
                    review_element, normalizer, hotel_id, ota_name
                )
                if not data:
                    print("[失敗] この口コミからはデータを抽出できませんでした。")
                    continue

                review_date_obj = data["posted_datetime_obj"].date()
                last_review_date_on_page = review_date_obj

                if end_date_obj and review_date_obj > end_date_obj:
                    print(f"スキップ: 投稿日({review_date_obj})が終了日({end_date_obj})より新しいため。")
                    continue

                # 【停止判定】開始日より古い口コミが見つかったら停止
                if start_date_obj and review_date_obj < start_date_obj:
                    print(f"停止: 投稿日({review_date_obj})が開始日({start_date_obj})より古いため、収集を終了します。")
                    driver.quit()   
                    return all_reviews_data         

                print(f" 投稿日: {data['review_date']} (処理対象)")
                del data["posted_datetime_obj"]
                all_reviews_data.append(data)
                pprint.pprint(data)

            if (
                end_date_obj
                and last_review_date_on_page
                and last_review_date_on_page > end_date_obj
            ):
                print(
                    f"\nページの最後のレビュー日({last_review_date_on_page})が終了日({end_date_obj})より新しいため、これ以上ページを遡る必要はありません。"
                )
                break
            # === ページネーション処理 ===
            try:
                # 「次の20件」ボタンを探してクリック
                next_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "li.pagingNext > a"))
                )
                driver.execute_script("arguments[0].click();", next_button)
                page_count += 1
                time.sleep(2)  # ページ遷移のための待機
            except (TimeoutException, NoSuchElementException):
                print("「次の15件」ボタンが見つかりません。最終ページに到達しました。")
                break  # ループを終了

    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        if 'driver' in locals() and driver.service.is_connectable():
            driver.quit()
        return all_reviews_data 

    print("\nブラウザを終了します。")
    driver.quit()
    return all_reviews_data


def extract_review_data(review_element, normalizer, hotel_id, ota_name):
    """
    単一のレビュー要素(div.revRvwUserEntry)から必要なデータを抽出する関数
    Args:
        review_element: 口コミ1件分のコンテナ要素 (WebElement)
    Returns:
        dict: 抽出した口コミデータ。抽出失敗時はNoneを返す。
    """
    original_score_scale = 5
    try:
        # --- 基本情報の抽出 ---
        # 評価点 (例: "5")
        # <span class="rate rate50">5</span>
        overall_score_original_text = review_element.find_element(
            By.CSS_SELECTOR, "span.rate"
        ).text.strip()

        normalized_overall_score = normalize_score(
            original_score=overall_score_original_text,
            original_scale=original_score_scale,
        )
        # 投稿者名
        # <span class="user">投稿者さん</span>
        user_full_text = review_element.find_element(By.CSS_SELECTOR, "span.user").text.strip()

        reviewer_name = user_full_text
        age_group = None
        gender = None

        # 角括弧が含まれているかチェックして情報を分割
        if '[' in user_full_text and ']' in user_full_text:
            try:
                match = re.search(r"^(.*?)\s*\[(.*?)\]$", user_full_text)
                if match:
                    reviewer_name = match.group(1).strip()
                    details = match.group(2).strip()

                    # 詳細情報を'/'で分割
                    detail_parts = details.split('/')
                    if len(detail_parts) == 2:
                        age_group = detail_parts[0].strip()
                        gender = detail_parts[1].strip()
                    elif len(detail_parts) == 1:
                        # [30代] のように片方しかない場合も考慮
                        # ここでは年代として扱う
                        age_group = detail_parts[0].strip()

            except Exception as e:
                # パースに失敗してもエラーとせず、元のテキストを名前として扱う
                print(f"    [情報] 投稿者情報のパースに失敗しました: {e}")
                reviewer_name = user_full_text

        # 投稿日時
        # <span class="time">2025年10月05日 11:30:44</span>
        time_str = review_element.find_element(
            By.CSS_SELECTOR, "span.time"
        ).text.strip()
        # 日付と時間をパース
        review_datetime = datetime.strptime(time_str, "%Y年%m月%d日 %H:%M:%S")
        review_date = review_datetime.strftime("%Y-%m-%d")

        # コメント本文
        # <p class="commentSentence">...</p>
        # <br>は改行に変換されるので、そのままtextで取得
        comment_text = review_element.find_element(
            By.CSS_SELECTOR, "p.commentSentence"
        ).text.strip()

        language_code = detect_language(comment_text)
        language_name = get_language_name_ja(language_code)
        # nationality_info = infer_nationality_from_language(language_code)
        # --- 旅行目的、同伴者、宿泊年月の抽出 ---
        purpose_items = review_element.find_elements(
            By.CSS_SELECTOR, "dl.commentPurpose dt, dl.commentPurpose dd"
        )
        purpose_data = {}
        # dtとddがペアになっていることを前提に2つずつ処理
        for i in range(0, len(purpose_items), 2):
            key = purpose_items[i].text.strip()
            value = purpose_items[i + 1].text.strip()
            purpose_data[key] = value

        # --- 部屋タイプの抽出と整形 ---
        original_room_type = None
        try:
            room_type_element = review_element.find_element(
                By.XPATH, ".//dt[text()='ご利用のお部屋']/following-sibling::dd[1]"
            )
            original_room_type = room_type_element.text.strip().strip("【】")
            # original_room_type = room_type_element.text.strip()
        except NoSuchElementException:
            print("    [情報] この口コミには「ご利用のお部屋」情報がありませんでした。")
            pass

        stay_month_str = purpose_data.get("宿泊年月")  # 例: "2024年08月"
        stay_date_for_db = None
        if stay_month_str:
            try:
                # "YYYY年MM月" 形式の文字列をdatetimeオブジェクトに変換し、date部分だけを取り出す
                # 日付は自動的にその月の1日になる
                stay_date_obj = datetime.strptime(stay_month_str, "%Y年%m月").date()
                stay_date_for_db = stay_date_obj.strftime(
                    "%Y-%m-%d"
                )  # "YYYY-MM-DD"形式の文字列
            except ValueError:
                print(
                    f"[警告] 宿泊年月のフォーマットが不正です: '{stay_month_str}'"
                )
        original_traveler_type = purpose_data.get("同伴者")
        original_purpose = purpose_data.get("旅行の目的")

        normalized_traveler_type = normalizer.normalize_traveler_type(
            original_traveler_type, ota_name
        )
        normalized_purpose = normalizer.normalize_purpose(
            original_purpose or original_traveler_type, ota_name
        )
        print("-" * 20)

        normalized_room_type = normalizer.normalize_room_type(
            original_room_type, hotel_id, ota_name
        )

        # 抽出したデータを辞書にまとめる
        review_data = {
            "posted_datetime_obj": review_datetime,
            "overall_score": normalized_overall_score,  # 正規化後のスコア
            "overall_score_original": overall_score_original_text,  # 元のスコア
            "original_score_scale": original_score_scale,  # 元の評価尺度
            "reviewer_name": reviewer_name,
            "age_group": age_group,
            "gender": gender,
            "review_date": review_date,
            "review_comment": comment_text,
            "stay_date": stay_date_for_db,
            "traveler_type": normalized_traveler_type,
            "traveler_type_original": original_traveler_type,
            "purpose_of_visit": normalized_purpose,
            "purpose_of_visit_original": original_purpose,
            "room_type": normalized_room_type,
            "room_type_original": original_room_type,
            "language_code": language_code,
            "review_language": language_name,
        }
        return review_data

    except NoSuchElementException as e:
        print(f"必須要素が見つかりませんでした: {e}")
        return None
    except (ValueError, IndexError) as e:
        print(f"データの変換または解析に失敗しました: {e}")
        return None
