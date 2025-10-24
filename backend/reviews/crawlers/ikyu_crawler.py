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
from reviews.utils import normalize_score, detect_language, get_language_name_ja


def scrape_ikyu_reviews(
    url: str, hotel_id: str, start_date_str: str = None, end_date_str: str = None
):
    """
    指定された一休.comのホテルページで「口コミ」タブをクリックし、
    表示されるモーダル内の口コミをスクレイピングする関数。
    """
    # === WebDriverのセットアップ ===
    options = uc.ChromeOptions()
    options.add_argument("--lang=ja-JP")
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-popup-blocking")

    driver = uc.Chrome(options=options)
    driver.set_window_size(1280, 800)
    wait = WebDriverWait(driver, 10)

    ota_name = "ikyu"
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

        # === レビューページへの移動と並び替え ===
        print("レビュータブをクリックします...")
        # gaclickid属性が変更されにくいと判断し、セレクタとして使用
        review_tab_selector = 'a[gaclickid="PcGuidePage/Review"]'
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, review_tab_selector))
        ).click()
        print("レビューページに移動しました。")

        # ページの読み込みを待機
        time.sleep(5)

        print("「新しい順」で並び替えます...")
        # aria-label属性で並び替えボタンを特定
        sort_button_selector = 'button[aria-label="新しい順"]'
        sort_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, sort_button_selector))
        )

        # すでに選択されているか確認 (data-selected="true"ならクリックしない)
        if sort_button.get_attribute("data-selected") != "true":
            sort_button.click()
            print("並び替えを実行しました。")
            time.sleep(2)  # 並び替え後の読み込み待機
        else:
            print("すでに「新しい順」にソートされています。")

        # === 口コミ収集のメインループ ===
        while not stop_scraping:
            print(f"\n--- {page_count}ページ目の口コミを収集中 ---")

            # 動的クラス名に対応するため前方一致セレクタを使用
            review_container_selector = 'section[itemprop="reviewRating"]'

            try:
                wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, review_container_selector)
                    )
                )
            except TimeoutException:
                print("このページに口コミが見つかりませんでした。収集を終了します。")
                break

            review_elements = driver.find_elements(
                By.CSS_SELECTOR, review_container_selector
            )
            print(f"{len(review_elements)}件の口コミを発見。")

            if not review_elements:
                print("このページに口コミはありません。収集を終了します。")
                break

            # --- 1ページ内の各口コミを処理 ---
            for review_element in review_elements:

                try:
                    more_button = review_element.find_element(
                        By.XPATH, ".//button[contains(text(), 'すべてみる')]"
                    )
                    driver.execute_script("arguments[0].click();", more_button)
                    time.sleep(0.5)  # テキストが展開されるのを待つ
                except NoSuchElementException:
                    pass

                data = extract_review_data(
                    review_element, normalizer, hotel_id, ota_name
                )
                if not data:
                    print("[失敗] この口コミからはデータを抽出できませんでした。")
                    continue

                review_date_obj = data["posted_datetime_obj"].date()

                if end_date_obj and review_date_obj > end_date_obj:
                    print(
                        f"スキップ: 投稿日({review_date_obj})が終了日({end_date_obj})より新しいため。"
                    )
                    continue

                if start_date_obj and review_date_obj < start_date_obj:
                    print(
                        f"停止: 投稿日({review_date_obj})が開始日({start_date_obj})より古いため、収集を終了します。"
                    )
                    stop_scraping = True
                    break

                print(f" 投稿日: {data['review_date']} (処理対象)")
                del data["posted_datetime_obj"]
                # all_reviews_data.append(data)
                pprint.pprint(data)

            if stop_scraping:
                break

            # === ページネーション処理 ===
            try:
                load_more_button_xpath = "//button[contains(., '続きをみる')]"
                load_more_button = driver.find_element(By.XPATH, load_more_button_xpath)

                # ボタンをクリックする前に画面内にスクロールする
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", load_more_button
                )
                time.sleep(0.5)  # スクロール後の安定待機

                load_more_button.click()

                print(
                    "「続きをみる」をクリックしました。新しい口コミの読み込みを待機します..."
                )
                page_count += 1
                time.sleep(
                    3
                )  # 新しいコンテンツが読み込まれるのを待つ (必要に応じて調整)

            except NoSuchElementException:
                # ボタンが見つからなければ、全ての口コミを読み込んだと判断
                print(
                    "「続きをみる」ボタンが見つかりません。すべての口コミを読み込みました。"
                )
                break  # ループを終了

              
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
    finally:
        print("\nブラウザを終了します。")
        if "driver" in locals() and driver.service.is_connectable():
            driver.quit()

    return all_reviews_data


def extract_review_data(review_element, normalizer, hotel_id, ota_name):
    """
    一休.comの単一レビュー要素からデータを抽出する関数
    """
    original_score_scale = 5
    # --- 変数の初期化 ---
    normalized_overall_score, overall_score_original = None, None
    normalized_room_score, room_score_original = None, None
    normalized_service_score, service_score_original = None, None
    normalized_bath_score, bath_score_original = None, None
    normalized_food_score, food_score_original = None, None
    normalized_facilities_score, facilities_score_original = (
        None,
        None,
    )
    (normalized_satisfaction_score, satisfaction_score_original) = (
        None,
        None,
    )

    reviewer_name = None, 
    review_datetime, review_date,  review_comment = None, None, None
    stay_date_for_db = None
    normalized_room_type, original_room_type = None, None
    language_code, language_name = None, None
    try:
        ### 投稿者名 ###
        reviewer_name = review_element.find_element(
            By.CSS_SELECTOR, "span.text-st-link"
        ).text.strip()

        ### 投稿日 ###
        date_str_raw = review_element.find_element(
            By.CSS_SELECTOR, 'span[itemprop="datePublished"]'
        ).text.strip()
        date_str = re.sub(r"投稿日[:：]\s*", "", date_str_raw)
        review_datetime = datetime.strptime(date_str, "%Y/%m/%d")
        review_date = review_datetime.strftime("%Y-%m-%d")

        ### 総合評価 ###
        score_element = review_element.find_element(
            By.CSS_SELECTOR, 'span[itemprop="ratingValue"]'
        )
        overall_score_original = score_element.text.strip()
        normalized_overall_score = normalize_score(
            overall_score_original, original_score_scale
        )

        ### サブ評価項目 ###
        sub_score_elements = review_element.find_elements(
            By.XPATH, './/ul[li/span[contains(text(), "客室・アメニティ")]]/li'
        )
        for item in sub_score_elements:
            try:
                category = item.find_element(
                    By.CSS_SELECTOR, "span:first-child"
                ).text.strip()
                score_text = item.find_element(
                    By.CSS_SELECTOR, "span:last-child"
                ).text.strip()
                if "客室・アメニティ" in category:
                    room_score_original = score_text
                elif "接客・サービス" in category:
                    service_score_original = score_text
                elif "温泉・お風呂" in category:
                    bath_score_original = score_text
                elif "お食事" in category:
                    food_score_original = score_text
                elif "施設・設備" in category:
                    facilities_score_original = score_text
                elif "満足度" in category: 
                    satisfaction_score_original = score_text
            except NoSuchElementException:
                continue

        stay_info_items = review_element.find_elements(
            By.XPATH, './/ul[li/svg/path[contains(@d, "M9 44q")]]/li'
        )
        for item in stay_info_items:
            item_text = item.text.strip()
            if "～" in item_text:
                match = re.search(r"(\d{4}/\d{1,2}/\d{1,2})", item_text)
                if match:
                    stay_date_for_db = datetime.strptime(
                        match.group(1), "%Y/%m/%d"
                    ).strftime("%Y-%m-%d")
            # 宿泊日でも人数でも食事プランでもないものを部屋タイプと見なす
            elif not re.search(r"(\d+名|朝食付|夕食付)", item_text):
                original_room_type = item_text

        try:
            stay_info_container = review_element.find_element(
                By.CSS_SELECTOR, 'ul.bg-gray-100'
            )
            # コンテナ内のすべての<li>要素を取得
            stay_info_items = stay_info_container.find_elements(By.TAG_NAME, "li")

            for item in stay_info_items:
                item_text = item.text.strip()

                # パターン1: 宿泊日を特定する ("～"が含まれるか、日付形式に一致するか)
                if "～" in item_text:
                    # 正規表現で "YYYY/M/D" の形式の日付部分だけを安全に抽出
                    match = re.search(r"(\d{4}/\d{1,2}/\d{1,2})", item_text)
                    if match:
                        # 抽出した日付文字列をdatetimeオブジェクトに変換し、DB保存用の形式にする
                        stay_date_obj = datetime.strptime(
                            match.group(1), "%Y/%m/%d"
                        ).date()
                        stay_date_for_db = stay_date_obj.strftime("%Y-%m-%d")

                # パターン2: 人数や食事プランなど、部屋タイプではない情報を除外する
                elif "名" in item_text or "室" in item_text or "食付" in item_text:
                    continue  # 人数情報や食事プランはスキップ

                # パターン3: 上記のいずれでもない場合、部屋タイプと判断する
                else:
                    original_room_type = item_text

        except NoSuchElementException:
            # 宿泊情報ブロック自体が存在しないレビューもあるため、エラーは握りつぶす
            print("宿泊関連情報ブロックが見つかりませんでした。")
            pass

        ### コメント本文 ###
        review_comment = review_element.find_element(
            By.CSS_SELECTOR, 'p[itemprop="reviewBody"]'
        ).text.strip()

        language_code = detect_language(review_comment)
        language_name = get_language_name_ja(language_code)

        # --- データ処理・正規化 ---

        normalized_room_type = normalizer.normalize_room_type(
            original_room_type, hotel_id, ota_name
        )
        normalized_overall_score = normalize_score(
            overall_score_original, original_score_scale
        )
        normalized_room_score = normalize_score(
            room_score_original, original_score_scale
        )
        normalized_service_score = normalize_score(
            service_score_original, original_score_scale
        )
        normalized_bath_score = normalize_score(
            bath_score_original, original_score_scale
        )
        normalized_food_score = normalize_score(
            food_score_original, original_score_scale
        )
        normalized_facilities_score = normalize_score(
            facilities_score_original, original_score_scale
        )
        normalized_satisfaction_score = normalize_score(satisfaction_score_original, original_score_scale) 

        review_data = {
            "posted_datetime_obj": review_datetime,
            "overall_score": normalized_overall_score,
            "overall_score_original": overall_score_original,
            "room_score": normalized_room_score,
            "room_score_original": room_score_original,
            "facilities_score": normalized_facilities_score,
            "facilities_score_original": facilities_score_original,
            "service_score": normalized_service_score,
            "service_score_original": service_score_original,
            "food_score": normalized_food_score,
            "food_score_original": food_score_original,
            "bath_score": normalized_bath_score,
            "bath_score_original": bath_score_original,
            "satisfaction_score": normalized_satisfaction_score,
            "satisfaction_score_original": satisfaction_score_original,
            "original_score_scale": original_score_scale,
            "reviewer_name": reviewer_name,
            "review_date": review_date,
            "review_comment": review_comment,
            "stay_date": stay_date_for_db,
            "room_type": normalized_room_type,
            "room_type_original": original_room_type,
            "language_code": language_code,
            "review_language": language_name,
        }
        return review_data

    except Exception as e:
        print(f"口コミの解析中に予期せぬエラーが発生しました: {e}")
        return None
