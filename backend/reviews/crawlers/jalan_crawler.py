import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from datetime import datetime
import re
import pprint
from decimal import Decimal, InvalidOperation

from ..normalizer import DataNormalizer 
from reviews.utils import (
    normalize_score,
    detect_language,
    get_language_name_ja
)


def scrape_jalan_reviews(url: str, hotel_id: str, start_date_str: str = None, end_date_str: str = None):
    """
    指定されたじゃらんnetのホテルレビューページから口コミをスクレイピングする関数

    Args:
        url (str): クロールするじゃらんnetのレビューページのURL。
        hotel_id (str): ホテルID。
        start_date_str (str, optional): 収集開始日 (YYYY-MM-DD形式)。この日付より古い口コミが見つかると収集を停止します。
        end_date_str (str, optional): 収集終了日 (YYYY-MM-DD形式)。この日付より新しい口コミはスキップ。

    Returns:
        list: 収集した口コミデータのリスト。各要素は辞書型。
    """
    # === WebDriverのセットアップ ===
    options = uc.ChromeOptions()
    options.add_argument("--lang=ja-JP")
    # サイトによってはヘッドレスモードがブロックされるため、必要に応じて有効化
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-popup-blocking")

    driver = uc.Chrome(options=options)
    driver.set_window_size(1280, 800)
    wait = WebDriverWait(driver, 10) 

    ota_name = 'jalan'
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

        # クッキー同意バナーを閉じる
        try:
            cookie_close_button = wait.until(
                EC.element_to_be_clickable((By.ID, "jln-kv__cookie-policy-close"))
            )
            print("クッキー同意バナーを検知しました。閉じています...")
            cookie_close_button.click()
            time.sleep(1)
        except TimeoutException:
            print("クッキー同意バナーは表示されませんでした。")

        # 「投稿日の新しい順」に並び替え
        # try:
        #     print("「投稿日の新しい順」に並び替えます...")
        #     sort_button = wait.until(
        #         EC.element_to_be_clickable((By.LINK_TEXT, "投稿日の新しい順"))
        #     )
        #     sort_button.click()
        #     print("ページの再読み込みを待機しています...")
        #     wait.until(
        #         EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.kuchikomi-cassette-wrapper"))
        #     )
        #     print("並び替えが完了しました。")
        # except TimeoutException:
        #     print("「投稿日の新しい順」ボタンが見つかりませんでした。処理を続行します。")

        # === 口コミ収集のメインループ (ページが続く限り実行) ===
        while not stop_scraping:
            print(f"\n--- {page_count}ページ目の口コミを収集中 ---")

            review_container_selector = "div.jlnpc-kuchikomiCassette__contWrap"

            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, review_container_selector)))
            except TimeoutException:
                print("口コミが見つかりませんでした。")
                break

            review_elements = driver.find_elements(By.CSS_SELECTOR, review_container_selector)

            print(f"{len(review_elements)}件の口コミを発見。")

            if not review_elements:
                print("このページに口コミはありません。収集を終了します。")
                break

            # === 1ページ内の各口コミを処理 ===
            for review_element in review_elements:
                data = extract_review_data(review_element, normalizer, hotel_id, ota_name)
                if not data:
                    print("[失敗] この口コミからはデータを抽出できませんでした。")
                    continue

                review_date_obj = data["posted_datetime_obj"].date()

                if end_date_obj and review_date_obj > end_date_obj:
                    print(f"スキップ: 投稿日({review_date_obj})が終了日({end_date_obj})より新しいため。")
                    continue

                if start_date_obj and review_date_obj < start_date_obj:
                    print(f"停止: 投稿日({review_date_obj})が開始日({start_date_obj})より古いため、収集を終了します。")
                    stop_scraping = True
                    break # このページのループを抜ける

                print(f" 投稿日: {data['review_date']} (処理対象)")
                del data["posted_datetime_obj"] # DB保存に不要な一時オブジェクトを削除
                all_reviews_data.append(data)
                pprint.pprint(data)

            if stop_scraping:
                break # メインループを抜ける

            # === ページネーション処理 ===
            try:
                next_button_selector = "a.jlnpc-pager-next, a.next"
                next_button = driver.find_element(By.CSS_SELECTOR, next_button_selector)

                # ボタンがクリック可能であることを確認
                wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector))
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", next_button
                )
                time.sleep(0.5)

                next_button.click()
                page_count += 1
                time.sleep(2)  # ページ遷移が完了するのを待つ
            except (NoSuchElementException, TimeoutException):
                print(
                    "「次へ」ボタンが見つからないかクリックできません。最終ページに到達しました。"
                )
                break

    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")

    finally:
        print("\nブラウザを終了します。")
        if 'driver' in locals() and driver.service.is_connectable():
            driver.quit()

    return all_reviews_data


def extract_review_data(review_element, normalizer, hotel_id, ota_name):
    """
    単一のレビュー要素からデータを抽出する関数 (現在の 'jlnpc-' レイアウト専用)
    """
    original_score_scale = 5
    # --- 変数の初期化 ---
    normalized_overall_score, overall_score_original = None, None
    normalized_room_score, room_score_original = None, None
    normalized_bath_score, bath_score_original = None, None
    normalized_food_score_breakfast, food_score_original_breakfast = None, None
    normalized_food_score_dinner, food_score_original_dinner = None, None
    normalized_cleanliness_score, cleanliness_score_original = None, None
    normalized_service_score, service_score_original = None, None
    reviewer_name, age_group, gender = None, None, None
    review_datetime, review_date, comment_text = None, None, None
    stay_date_for_db = None
    normalized_traveler_type, original_traveler_type = None, None
    normalized_purpose, original_purpose = None, None
    normalized_room_type, original_room_type = None, None
    language_code, language_name = None, None

    try:
        ### 総合評価 ###
        score_element = review_element.find_element(
            By.CSS_SELECTOR, "div.jlnpc-kuchikomiCassette__totalRate"
        )
        overall_score_original = score_element.text.strip()
        normalized_overall_score = normalize_score(
            overall_score_original, original_score_scale
        )

        ### サブ評価項目 ###
        sub_score_dts = review_element.find_elements(
            By.CSS_SELECTOR, "dl.jlnpc-kuchikomiCassette__rateList > dt"
        )
        for dt in sub_score_dts:
            try:
                category = dt.text.strip()
                # dtの直後にあるdd要素を取得
                score_text = dt.find_element(
                    By.XPATH, "following-sibling::dd[1]"
                ).text.strip()

                # スコアが '-' の場合はスキップ
                if score_text == "-":
                    continue

                if "部屋" == category:
                    room_score_original = score_text
                    normalized_room_score = normalize_score(
                        score_text, original_score_scale
                    )
                elif "風呂" == category:
                    bath_score_original = score_text
                    normalized_bath_score = normalize_score(
                        score_text, original_score_scale
                    )
                elif "料理(朝食)" == category:
                    food_score_original_breakfast = score_text
                    normalized_food_score_breakfast = normalize_score(
                        score_text, original_score_scale
                    )
                elif "料理(夕食)" == category:
                    food_score_original_dinner = score_text
                    normalized_food_score_dinner = normalize_score(
                        score_text, original_score_scale
                    )
                elif "接客・サービス" == category:
                    service_score_original = score_text
                    normalized_service_score = normalize_score(
                        score_text, original_score_scale
                    )
                elif "清潔感" == category:
                    cleanliness_score_original = score_text
                    normalized_cleanliness_score = normalize_score(
                        score_text, original_score_scale
                    )
            except (NoSuchElementException, InvalidOperation):
                continue
        ### 投稿者情報 ###
        try:
            # まず親のspan要素を取得
            user_span = review_element.find_element(
                By.CSS_SELECTOR, "span.jlnpc-kuchikomiCassette__userName"
            )
            try:
                # リンク(aタグ)があるか試す
                name_raw = user_span.find_element(By.TAG_NAME, "a").text.strip()
            except NoSuchElementException:
                # リンクがない場合はspan全体のテキストを取得
                name_raw = user_span.text.strip()

            if name_raw.endswith('さん'):
                reviewer_name = name_raw[:-2]  # 末尾から2文字をスライスして削除
            else:
                reviewer_name = name_raw
        except NoSuchElementException:
            reviewer_name = ""

        ### 同伴者形態・旅行目的 ###
        labels = review_element.find_elements(
            By.CSS_SELECTOR,
            "div.jlnpc-kuchikomiCassette__leftArea__contHead span.c-label",
        )
        for label in labels:
            text = label.text.strip()
            if "/" in text:
                parts = text.split("/")
                if len(parts) == 2:
                    gender, age_group = parts[0].strip(), parts[1].strip()
            else:
                original_traveler_type = text
                original_purpose = text

        ### 日付情報 ###
        try:
            date_str_raw = review_element.find_element(
                By.CSS_SELECTOR, "p.jlnpc-kuchikomiCassette__postDate"
            ).text.strip()

            date_str = date_str_raw.replace("投稿日：", "")
            review_datetime = datetime.strptime(date_str, "%Y/%m/%d")

            review_date = review_datetime.strftime("%Y-%m-%d")

        except (NoSuchElementException, ValueError) as e:
            print(f"  [警告] 日付の取得または解析に失敗しました: {e}")
            review_datetime = None
            review_date = None

        ### 旅行目的・部屋タイプなど(補助的) ###
        purpose_elements = review_element.find_elements(
            By.CSS_SELECTOR, "dl.jlnpc-kuchikomiCassette__purposeList > div"
        )
        for item in purpose_elements:
            try:
                key = item.find_element(By.TAG_NAME, "dt").text.strip()
                value = item.find_element(By.TAG_NAME, "dd").text.strip()
                if (
                    "誰と" in key and not original_traveler_type
                ):  # 既に取得済みの場合は上書きしない
                    original_traveler_type = value
                elif "目的" in key and not original_purpose:
                    original_purpose = value
                elif "部屋" in key:
                    original_room_type = value
            except NoSuchElementException:
                continue

        ### コメント本文 ###
        comment_text = review_element.find_element(
            By.CSS_SELECTOR, "p.jlnpc-kuchikomiCassette__postBody"
        ).text.strip()

        language_code = detect_language(comment_text)
        language_name = get_language_name_ja(language_code)

        # === 正規化と辞書への格納 ===
        normalized_traveler_type = normalizer.normalize_traveler_type(
            original_traveler_type, ota_name
        )
        normalized_purpose = normalizer.normalize_purpose(
            original_purpose or original_traveler_type, ota_name
        )
        normalized_room_type = normalizer.normalize_room_type(
            original_room_type, hotel_id, ota_name
        )

        review_data = {
            "posted_datetime_obj": review_datetime,
            "overall_score": normalized_overall_score,
            "overall_score_original": overall_score_original,
            "room_score": normalized_room_score,
            "room_score_original": room_score_original,
            "bath_score": normalized_bath_score,
            "bath_score_original": bath_score_original,
            "breakfast_score": normalized_food_score_breakfast,
            "breakfast_score_original": food_score_original_breakfast,
            "dinner_score": normalized_food_score_dinner,
            "dinner_score_original": food_score_original_dinner,
            "cleanliness_score": normalized_cleanliness_score,
            "cleanliness_score_original": cleanliness_score_original,
            "service_score": normalized_service_score,
            "service_score_original": service_score_original,
            "original_score_scale": original_score_scale,
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

    except Exception as e:
        print(f"口コミの解析中に予期せぬエラーが発生しました: {e}")
        return None
