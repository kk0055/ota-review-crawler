# google_travel_crawler.py

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from datetime import datetime, timedelta
import re
import pprint
from ..normalizer import DataNormalizer
from reviews.utils import normalize_score, detect_language, get_language_name_ja
import html
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def parse_google_relative_date(relative_date_str: str) -> datetime:
    """
    Googleの相対的な日付文字列("a week ago", "3ヶ月前"など)をdatetimeオブジェクトに変換する。
    """
    now = datetime.now()
    relative_date_str = relative_date_str.lower().strip()

    # 日本語と英語のパターンを正規表現で処理
    # 例: "3 weeks ago", "a month ago", "5日前", "1年前"
    match = re.search(
        r"(an?|a|\d+)\s+(year|month|week|day|hour|minute)s?", relative_date_str
    )
    if not match:
        match = re.search(r"(\d+)\s*日前", relative_date_str)
        if match:
            unit = "day"
        else:
            match = re.search(r"(\d+)\s*週間前", relative_date_str)
            if match:
                unit = "week"
            else:
                match = re.search(r"(\d+)\s*か月前", relative_date_str)
                if match:
                    unit = "month"
                else:
                    match = re.search(r"(\d+)\s*年前", relative_date_str)
                    if match:
                        unit = "year"

    if match:
        try:
            quantity_str = match.group(1)
            quantity = 1 if quantity_str in ["a", "an"] else int(quantity_str)

            unit_str = match.group(2) if len(match.groups()) > 1 else unit

            if "year" in unit_str:
                return now - timedelta(days=365 * quantity)
            if "month" in unit_str:
                return now - timedelta(days=30 * quantity)  # 簡略化
            if "week" in unit_str:
                return now - timedelta(weeks=quantity)
            if "day" in unit_str:
                return now - timedelta(days=quantity)
            if "hour" in unit_str:
                return now - timedelta(hours=quantity)
            if "minute" in unit_str:
                return now - timedelta(minutes=quantity)
        except (ValueError, IndexError):
            pass  # パース失敗時はそのまま

    # パターンに一致しない場合やパース失敗時は現在時刻を返す
    print(
        f"[警告] 相対日付のパースに失敗しました: '{relative_date_str}'。現在時刻を使用します。"
    )
    return now


def scrape_google_travel_reviews(
    url: str,
    hotel_id: str,
    start_date_str: str = None,
    end_date_str: str = None,
):
    """
    指定されたGoogle Travelのホテルレビューページから口コミをスクレイピングする関数

    Args:
        url (str): クロールするGoogle TravelのレビューページのURL。
        start_date_str (str, optional): 収集開始日 (YYYY-MM-DD形式)。この日付より古い口コミが見つかると収集を停止します。
        end_date_str (str, optional): 収集終了日 (YYYY-MM-DD形式)。この日付より新しい口コミはスキップ。

    Returns:
        list: 収集した口コミデータのリスト。各要素は辞書型。
    """
    # === WebDriverのセットアップ===
    options = uc.ChromeOptions()
    # options.add_argument("--lang=en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7")
    options.add_argument("--lang=ja-JP")
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # options.add_argument("--disable-blink-features=AutomationControlled")
    prefs = {
        'intl.accept_languages': 'ja,en'
    }

    options.add_experimental_option('prefs', prefs)

    driver = uc.Chrome(options=options)
    driver.set_window_size(1200, 800)
    # driver.maximize_window()
    wait = WebDriverWait(driver, 10)

    ota_name = "google"
    normalizer = DataNormalizer()

    start_date_obj, end_date_obj = None, None
    if start_date_str:
        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return []
    if end_date_str:
        try:
            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return []

    # 近似計算のズレを吸収するためのバッファ（ここでは90日）
    date_buffer = timedelta(days=90)

    all_reviews_data = []
    stop_scraping = False
    processed_review_ids = set()

    try:
        print(f"アクセス中: {url}")
        driver.get(url)
        time.sleep(3)  # ページの初期読み込み待機

        if "/search" in driver.current_url:
            print("検索ページを検出しました。レビューセクションに直接移動します...")
            try:
                # クラス名に依存せず、レビュー数(例: "(497)")のテキスト形式を元にリンクを特定するXPath
                review_count_link_xpath = (
                    "//a[.//span[contains(text(),'(') and contains(text(),')')]]"
                )
                review_count_link = wait.until(
                    EC.element_to_be_clickable((By.XPATH, review_count_link_xpath))
                )
                print("レビュー数リンクをクリックして、クチコミページに移動します...")
                driver.execute_script("arguments[0].click();", review_count_link)
                time.sleep(4)

            except TimeoutException:
                print(
                    "レビューページへのリンクが見つかりませんでした。ページ構成が変更された可能性があります。"
                )
                driver.quit()
                return []
        try:
            print("「新しい順」での並び替えを試みます...")
            sort_button_xpath = "//div[@role='option' and (contains(., 'Most helpful')or contains(., '参考度の高い順'))]"
            sort_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, sort_button_xpath))
            )
            time.sleep(1)

            sort_button.click()
            time.sleep(1)
            newest_option = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//div[@aria-label='新しい順'][@data-value='2'][@role='option']",
                    )
                )
            )
            newest_option.click()
            print("並び替え後のクチコミ読み込みを待機しています...")
            time.sleep(3)
        except TimeoutException:
            print("並び替えボタンまたは「新しい順」オプションが見つかりませんでした。デフォルトの順序で続行します。")

        # try:
        #     print("「Google」のみの表示に切り替えます...")
        #     ota_button_xpath = "//div[@role='option' and (contains(., 'All')or contains(., 'すべてのレビュー'))]"
        #     ota_button = wait.until(
        #         EC.element_to_be_clickable((By.XPATH, ota_button_xpath))
        #     )
        #     time.sleep(1)

        #     ota_button.click()
        #     time.sleep(1)
        #     google_btn = wait.until(
        #         EC.element_to_be_clickable(
        #             (
        #                 By.XPATH,
        #                 "//div[@aria-label='Google'][@data-value='-1'][@role='option']",
        #             )
        #         )
        #     )
        #     google_btn.click()

        #     time.sleep(3)
        # except TimeoutException:
        #     print("「Google」のみの表示に切り替え失敗")

        scrollable_div = None
        try:

            print("スクロールコンテナの表示を待機します...")
            scrollable_container_xpath = "//div[@jsname='UcPrk']"
            scrollable_div = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, scrollable_container_xpath))
            )
            print("コンテナを特定しました。スクレイピングを開始します。")

        except TimeoutException:
            print(
                "[致命的エラー] 「すべてのレビュー」ボタン、またはレビューコンテナの特定に失敗しました。"
            )
            return

        while not stop_scraping:

            review_elements_xpath = (
                ".//img[contains(@src, 'googleg')]/ancestor::div[@data-ved][1]"
            )
            review_elements = driver.find_elements(By.XPATH, review_elements_xpath)
            print(f"ページ上で{len(review_elements)}件の口コミを検出しました。")

            # if not review_elements or len(review_elements) == len(processed_review_ids):
            #     print("新しい口コミが見つかりませんでした。収集を終了します。")
            #     break

            current_review_count = len(review_elements)
            # last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)

            last_processed_date = None
            # まだ処理していないレビューだけを対象にする
            new_reviews_to_process = [
                el for el in review_elements if el.text not in processed_review_ids
            ]

            print(f"未処理の口コミ {len(new_reviews_to_process)}件を処理します。")

            for review_element in new_reviews_to_process:
                review_text_content = review_element.text
                # ここでも念のため二重チェック
                if review_text_content in processed_review_ids:
                    continue
                processed_review_ids.add(review_text_content)

                try:
                    # レビュー要素内に、Googleロゴ画像が含まれているかを確認
                    google_logo_xpath = ".//img[contains(@src, 'googleg')]"
                    review_element.find_element(By.XPATH, google_logo_xpath)
                    # 上の行で要素が見つかれば、Googleレビューと判断。見つからなければ例外が発生する。
                except NoSuchElementException:
                    # Googleロゴが見つからなかった場合、このレビューはスキップする
                    print(
                        "  [情報] Google以外のレビュー(TripAdvisor等)のためスキップします。"
                    )
                    continue  # 次のレビューに進む

                data = extract_google_review_data(
                    review_element, normalizer, hotel_id, ota_name, driver
                )
                if not data:
                    continue

                last_processed_date = data["posted_datetime_obj"].date()
                all_reviews_data.append(data)

            if start_date_obj and last_processed_date:
                if last_processed_date < (start_date_obj - date_buffer):
                    print(
                        f"収集バッファを超えました。収集ループを停止します。(最終処理日: {last_processed_date})"
                    )
                    stop_scraping = True


        last_review_count = len(review_elements)
        print("\n次の口コミチャンクの読み込みを試行します...")
        actions = ActionChains(driver)
        actions.move_to_element(scrollable_div).click()
        for _ in range(3):
            actions.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.3)
        actions.perform()
        print("  新しいコンテンツの読み込みを待機します...")
        time.sleep(3.5)
        current_review_count = len(
            driver.find_elements(
                By.XPATH,
                ".//img[contains(@src, 'googleg')]/ancestor::div[@data-ved][1]",
            )
        )
        if current_review_count > last_review_count:
            print(
                f"  成功！新しい口コミを読み込みました。(総数: {current_review_count}件)"
            )
        else:
            print(
                "  件数が変わりませんでした。ページの最下部と判断し、収集を終了します。"
            )
            stop_scraping = True
            

    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
    finally:
        print(
            f"\nスクレイピングが完了しました。収集した口コミの総数: {len(all_reviews_data)}"
        )
        if "driver" in locals() and driver.service.is_connectable():
            driver.quit()

    if not all_reviews_data:
        print("\n収集したレビューはありません。")
        return []

    print(
        f"\n収集が完了しました。全{len(all_reviews_data)}件のレビューを日付で絞り込みます..."
    )

    filtered_reviews = []
    for review in all_reviews_data:
        review_date = review["posted_datetime_obj"].date()

        # end_dateのチェック
        if end_date_obj and review_date > end_date_obj:
            continue  # 終了日より新しいのでスキップ

        # start_dateのチェック
        if start_date_obj and review_date < start_date_obj:
            continue  # 開始日より古いのでスキップ

        # 絞り込み条件を通過したものだけを追加
        del review["posted_datetime_obj"]  # 最終データからは不要
        filtered_reviews.append(review)

    print(f"絞り込みの結果、{len(filtered_reviews)}件のレビューが対象となりました。")
    return filtered_reviews


def extract_google_review_data(review_element, normalizer, hotel_id, ota_name, driver):

    def get_sub_score(keyword_en, keyword_ja):
        # (このヘルパー関数は変更なし)
        try:
            xpath = (
                f".//div[contains(., '{keyword_en}') or contains(., '{keyword_ja}')]"
            )
            element = review_element.find_element(By.XPATH, xpath)
            score_text = element.text.strip()
            match_slash = re.search(r"(\d+)/(\d+)", score_text)
            if match_slash:
                return float(match_slash.group(1))
            match_dot = re.search(r"(\d\.\d)", score_text)
            if match_dot:
                return float(match_dot.group(1))
            return None
        except NoSuchElementException:
            return None

    original_score_scale = 5
    try:

        overall_score_original_text = "0"  
        try:
            # "5/5" 形式のスコアを、位置関係を利用したXPathで取得
            score_div_xpath = (
                ".//div[.//a[contains(@href, '/contrib/')]]/following-sibling::div"
            )
            score_text = review_element.find_element(
                By.XPATH, score_div_xpath
            ).text  # "5/5" を取得

            # スラッシュの左側を取得
            if "/" in score_text:
                overall_score_original_text = score_text.split("/")[0].strip() 

        except NoSuchElementException:

            print(
                "  [情報] '5/5' 形式の総合評価が見つかりません。星のaria-labelから取得します。"
            )
            rating_element = review_element.find_element(
                By.XPATH, ".//span[@role='img']"
            )
            aria_label = rating_element.get_attribute("aria-label")
            score_match = re.search(r"(\d+)", aria_label)
            if score_match:
                overall_score_original_text = score_match.group(1)

        normalized_overall_score = normalize_score(
            original_score=overall_score_original_text,
            original_scale=original_score_scale,
        )

        # 投稿者名
        reviewer_name = review_element.find_element(
            By.XPATH, ".//a[contains(@href, '/contrib/') and text()]"
        ).text.strip()

        # 投稿日時
        time_str = ""
        try:
            # Googleアイコンを基点に、その前のテキストノードを取得
            date_xpath = ".//img[contains(@src, 'googleg')]/parent::span/preceding-sibling::text()"
            script = """
                var xpathResult = document.evaluate(arguments[1], arguments[0], null, XPathResult.STRING_TYPE, null);
                return xpathResult.stringValue;
                """
            time_str = driver.execute_script(script, review_element, date_xpath)

            # "最終編集:" や "、" などの余分な文字列を削除
            if time_str:
                time_str = time_str.replace("最終編集:", "").replace("、", "").strip()

        except NoSuchElementException:
            print("  [警告] 投稿日時の取得に失敗しました。")

        review_datetime = parse_google_relative_date(time_str)
        review_date = review_datetime.strftime("%Y-%m-%d")

        # 「続きを読む」ボタン
        try:
            more_button_xpath = ".//span[@role='button' and (contains(., 'Read more') or contains(., '続きを読む'))]"
            more_button = review_element.find_element(By.XPATH, more_button_xpath)
            driver.execute_script("arguments[0].click();", more_button)
            time.sleep(0.5)
        except NoSuchElementException:
            pass

        original_purpose = None
        original_traveler_type = None
        try:
            # "Holiday ❘ Couple" のようなテキストを取得
            travel_info_xpath = ".//img[contains(@src, 'googleg')]/ancestor::div[2]/following-sibling::div/div[1]/span"
            travel_info_text = review_element.find_element(By.XPATH, travel_info_xpath).text.strip()

            if '❘' in travel_info_text:
                parts = [part.strip() for part in travel_info_text.split('❘')]
                if len(parts) == 2:
                    original_purpose = parts[0]
                    original_traveler_type = parts[1]

                elif len(parts) == 1:
                    original_purpose = parts[0] # 片方だけの場合は目的に割り当てる
            else:
                original_purpose = travel_info_text 

        except NoSuchElementException:
            print("  [情報] 旅行タイプ/目的の情報は見つかりませんでした。")
            pass

        normalized_purpose = normalizer.normalize_purpose(
            original_purpose or original_traveler_type, ota_name
        )
        normalized_traveler_type = normalizer.normalize_traveler_type(
            original_traveler_type, ota_name
        )

        # コメント本文
        comment_full_html = ""
        try:
            # STEP 1: 【最優先】「続きを読む」で展開された後の「完全な本文」コンテナを探す
            # この 'NwoMSd' は完全な本文が格納される目印として非常に信頼性が高い。
            comment_span_xpath_full = ".//div[@jsname='NwoMSd']//span"
            comment_span_element = review_element.find_element(
                By.XPATH, comment_span_xpath_full
            )
            comment_full_html = comment_span_element.get_attribute("innerHTML")
            # print("  [成功] パターン1: 完全な本文を取得しました。")

        except NoSuchElementException:
            # STEP 2: 【フォールバック】完全な本文が見つからない場合、
            # 表示されている本文（短いレビュー or 省略版）を汎用XPathで探す。
            try:
                comment_span_xpath_generic = ".//span[not(.//*) and not(ancestor::a) and not(ancestor::*[@role='button']) and string-length(normalize-space()) > 15][1]"
                comment_span_element = review_element.find_element(
                    By.XPATH, comment_span_xpath_generic
                )
                # comment_full_html = comment_span_element.get_attribute("innerHTML")
                comment_full_html = comment_span_element.text
                # print("  [成功] パターン2: 表示されている本文を取得しました。")

            except NoSuchElementException:
                # どちらのパターンでも見つからなかった場合
                print("  [警告] いずれのパターンでも口コミ本文の取得に失敗しました。")

        # 2. HTMLをクリーニングして、扱いやすいプレーンテキストに変換する
        def clean_html_to_text(html_string):
            if not html_string:
                return ""
            # &nbsp; などのHTMLエンティティを通常の文字に変換 (例: &nbsp; -> ' ')
            text = html.unescape(html_string)
            # <br>タグを改行文字(\n)に置換
            text = re.sub(r"<br\s*/?>", "\n", text)
            # 残りのすべてのHTMLタグを除去
            text = re.sub(r"<.*?>", "", text)
            # 連続する空白や改行をまとめる
            text = re.sub(r"\s+", " ", text).strip()
            return text

        # クリーニングを実行
        comment_full_text = clean_html_to_text(comment_full_html)

        # 3. クリーニングされたテキストを元に、分離処理を行う
        original_marker = "（原文）"
        translation_marker = "（Google による翻訳）"

        review_comment = ""
        translated_review_comment = "" 

        # パターンA: 「原文」と「翻訳」の両方が存在する場合
        if original_marker in comment_full_text:
            parts = comment_full_text.split(original_marker, 1)
            translated_part = parts[0]
            review_comment = parts[1].strip()
            translated_review_comment = translated_part.replace(translation_marker, "").strip()

        # パターンB: 「翻訳」のみが存在する場合 (原文が英語のレビューなど)
        elif translation_marker in comment_full_text:
            # マーカー以降を翻訳文として取得
            translated_review_comment = comment_full_text.replace(translation_marker, "").strip()
            # この場合、原文はHTML上に存在しないため、
            # 利便性のために「原文」フィールドにも日本語訳を入れておく
            review_comment = translated_review_comment

        # パターンC: どちらのマーカーも存在しない場合 (日本語のレビューなど)
        else:
            review_comment = comment_full_text

        endings_to_remove = ["… 続きを読む", "… もっと見る", "… Read more"]
        # review_comment の末尾をチェックして削除
        for ending in endings_to_remove:
            if review_comment.endswith(ending):
                review_comment = review_comment[: -len(ending)].strip()
                break  # 1つ見つかったらループを抜ける

        # translated_review_comment の末尾をチェックして削除
        for ending in endings_to_remove:
            if translated_review_comment.endswith(ending):
                translated_review_comment = translated_review_comment[
                    : -len(ending)
                ].strip()
                break

        language_code = detect_language(review_comment)
        language_name = get_language_name_ja(language_code)

        # --- 部屋 (Rooms) ---
        rooms_score_original = get_sub_score("Rooms", "客室")
        rooms_score = None  # 正規化後のスコア (デフォルトはNone)
        if rooms_score_original is not None:
            rooms_score = normalize_score(
                original_score=rooms_score_original,
                original_scale=original_score_scale,
            )

        # --- サービス (Service) ---
        service_score_original = get_sub_score("Service", "サービス")
        service_score = None
        if service_score_original is not None:
            service_score = normalize_score(
                original_score=service_score_original,
                original_scale=original_score_scale,
            )

        # --- ロケーション (Location) ---
        location_score_original = get_sub_score("Location", "地図")
        location_score = None
        if location_score_original is not None:
            location_score = normalize_score(
                original_score=location_score_original,
                original_scale=original_score_scale,
            )

        review_data = {
            "posted_datetime_obj": review_datetime,
            "overall_score": normalized_overall_score,
            "overall_score_original": overall_score_original_text,
            "original_score_scale": original_score_scale,
            "reviewer_name": reviewer_name,
            "rooms_score": rooms_score,  # 正規化後の部屋スコア
            "rooms_score_original": rooms_score_original,  # 元の部屋スコア
            "service_score": service_score,  # 正規化後のサービススコア
            "service_score_original": service_score_original,  # 元のサービススコア
            "location_score": location_score,  # 正規化後のロケーションスコア
            "location_score_original": location_score_original, 
            "review_date": review_date,
            "review_comment": review_comment,
            "translated_review_comment": translated_review_comment,
            "traveler_type": normalized_traveler_type,
            "traveler_type_original": original_traveler_type,
            "purpose_of_visit": normalized_purpose,
            "purpose_of_visit_original": original_purpose,
            "language_code": language_code,
            "review_language": language_name,
        }

        print("\n--- Extracted Data ---")
        pprint.pprint(review_data)
        print("----------------------\n")

        # return review_data
    except NoSuchElementException as e:
        print(f"  [抽出エラー] 必須要素が見つかりませんでした: {e}")
        return None
    except (ValueError, IndexError, AttributeError) as e:
        print(f"  [抽出エラー] データの解析または変換に失敗しました: {e}")
        return None
