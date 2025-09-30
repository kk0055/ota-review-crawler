import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from datetime import datetime, date


def scrape_expedia_reviews(url, start_date_str: str = None, end_date_str: str = None):
    """
    指定されたExpediaのホテルページから全ての口コミをスクレイピングする関数

    url: CrawlするURL。
    start_date_str: 収集開始日 (YYYY-MM-DD形式の文字列)。この日付より古い口コミが見つかると停止。
    end_date_str: 収集終了日 (YYYY-MM-DD形式の文字列)。この日付より新しい口コミはスキップ。
    """
    # Chromeオプションの設定
    chrome_options = Options()
    chrome_options.add_argument("--lang=ja-JP")
    chrome_options.add_argument('--headless=new')

    # WebDriver Managerを使って、Chromeのバージョンに合ったWebDriverを自動設定
    # service = Service(ChromeDriverManager().install())
    # driver = webdriver.Chrome(service=service, options=chrome_options)
    # ブラウザドライバーのセットアップ
    driver = uc.Chrome(options=chrome_options)

    # 処理が完了するまで最大で待機する時間（秒）
    wait = WebDriverWait(driver, 10)

    start_date_obj = None
    if start_date_str:
        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            print(f"収集開始日を設定: {start_date_obj}")
        except ValueError:
            print(
                f"エラー: 開始日の形式が不正です ('{start_date_str}')。処理を中断します。"
            )
            return []

    end_date_obj = None
    if end_date_str:
        try:
            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            print(f"収集終了日を設定: {end_date_obj}")
        except ValueError:
            print(
                f"エラー: 終了日の形式が不正です ('{end_date_str}')。処理を中断します。"
            )
            return []

    all_reviews_data = []
    try:
        print(f"アクセス中: {url}")
        driver.get(url)

        try:
            # "すべて承諾" ボタン (ID: onetrust-accept-btn-handler) が表示されるまで待つ
            accept_cookies_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            print("Cookie同意ポップアップを検知しました。承諾しています...")
            driver.execute_script("arguments[0].click();", accept_cookies_button)
            time.sleep(1)  # クリック後の画面遷移を待つ
        except TimeoutException:
            # 5秒待っても表示されなければ、ポップアップは無いか、すでに同意済みと判断
            print("Cookie同意ポップアップは表示されませんでした。")

        # --- 日付選択のポップアップが表示された場合、閉じる ---
        try:
            # "選択完了"ボタンが表示されるまで少し待つ (最大5秒)
            close_date_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[data-stid='apply-date-selector']")
                )
            )
            print("日付選択ポップアップを検知しました。閉じています...")
            close_date_button.click()
            time.sleep(1)  # 閉じるアニメーションのための待機
        except TimeoutException:
            # 5秒待っても表示されなければ、ポップアップは無いと判断して次に進む
            print("日付選択ポップアップは表示されませんでした。")

        # 2. "口コミをすべて表示" をクリックしてレビュー表示
        print("「口コミをすべて表示」ボタンを探しています...")
        show_reviews_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[data-stid='reviews-link']")
            )
        )
        print("ボタンをクリックして口コミを表示します。")
        show_reviews_button.click()

        # 口コミモーダルが表示され、最初の口コミが読み込まれるまで待機
        print("口コミの読み込みを待っています...")
        wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "div[data-stid^='product-reviews-list-item']")
            )
        )
        time.sleep(5)  # レンダリングの安定化のため少し待機

        # ループで「さらに表示」を押し続け、全口コミを取得
        processed_reviews_count = 0
        stop_crawling = False

        while not stop_crawling:
            # 現在表示されている口コミの親要素を全て取得
            review_elements = driver.find_elements(
                By.CSS_SELECTOR, "div[data-stid^='product-reviews-list-item']"
            )
            # 新しく読み込まれた口コミだけを処理対象にする
            new_reviews = review_elements[processed_reviews_count:]
            if not new_reviews:
                print("新しい口コミが見つかりませんでした。5秒後に再試行します...")
                time.sleep(5)  # 念のための待機
                review_elements = driver.find_elements(
                    By.CSS_SELECTOR, "div[data-stid^='product-reviews-list-item']"
                )
                new_reviews = review_elements[processed_reviews_count:]
                if not new_reviews:
                    print("再試行しても新しい口コミがありません。処理を終了します。")
                    break

            print(
                f"新たに {len(new_reviews)} 件の口コミを処理します... (合計: {len(review_elements)}件)"
            )

            for review in new_reviews:
                try:
                    # 評価 (例: "8/10 良い" -> "8")
                    rating_text = review.find_element(
                        By.CSS_SELECTOR, "h3.uitk-heading"
                    ).text
                    overall_score = rating_text.split("/")[0]

                    # 投稿者と投稿日
                    author_info = review.find_element(
                        By.XPATH, ".//h4/.."
                    )  # h4タグの親要素を取得
                    reviewer_name = author_info.find_element(By.TAG_NAME, "h4").text
                    # 旅行者タイプ
                    traveler_type = "" 
                    try:
                        traveler_type_element = author_info.find_element(By.CSS_SELECTOR, "h4 + div")
                        # 日付と区別するため、テキストに「年」が含まれていないことを確認
                        if "年" not in traveler_type_element.text:
                            traveler_type = traveler_type_element.text
                    except NoSuchElementException:
                        print("  -> 旅行者タイプの項目は見つかりませんでした。")

                    review_date_str = author_info.find_element(
                        By.XPATH, ".//div[contains(text(), '年')]"
                    ).text
                    review_datetime_obj = datetime.strptime(
                        review_date_str, "%Y 年 %m 月 %d 日"
                    )
                    review_date_obj = review_datetime_obj.date()
                    review_date_for_db = review_date_obj.strftime("%Y-%m-%d")
                    # --- 日付比較ロジック ---
                    # 【スキップ判定】終了日より新しい口コミはスキップ
                    if end_date_obj and review_date_obj > end_date_obj:
                        print(
                            f"  -> スキップ: 投稿日({review_date_obj})が終了日({end_date_obj})より新しいため。"
                        )
                        continue

                    # 【停止判定】開始日より古い口コミが見つかったら停止
                    if start_date_obj and review_date_obj < start_date_obj:
                        print(
                            f"  -> 停止: 投稿日({review_date_obj})が開始日({start_date_obj})より古いため。"
                        )
                        stop_crawling = True
                        break
                    print(f"  投稿日: {review_date_for_db} (処理対象)")

                    # 口コミ本文
                    review_comment = ""
                    translated_review_comment = ""
                    try:
                        # オリジナル文の要素を特定
                        original_text_element = review.find_element(
                            By.CSS_SELECTOR,
                            "div.uitk-expando-peek-inner > div.uitk-text",
                        )
                        review_comment = original_text_element.text

                        # 翻訳
                        translate_buttons = review.find_elements(
                            By.XPATH, ".//button[text()='Google で翻訳']"
                        )
                        if translate_buttons:
                            translate_buttons[0].click()

                            try:
                                wait = WebDriverWait(review, 5)
                                wait.until(
                                    lambda d: d.find_element(
                                        By.CSS_SELECTOR,
                                        "div.uitk-expando-peek-inner > div.uitk-text",
                                    ).text
                                    != review_comment
                                )

                                translated_review_comment = review.find_element(
                                    By.CSS_SELECTOR,
                                    "div.uitk-expando-peek-inner > div.uitk-text",
                                ).text

                            except TimeoutException:
                                print("翻訳文の読み込みがタイムアウトしました。")

                    except NoSuchElementException:
                        review_comment = ""
                        translated_review_comment = ""

                    review_data = {
                        "overall_score": overall_score,
                        "reviewer_name": reviewer_name,
                        "review_date": review_date_for_db,
                        "traveler_type": traveler_type,
                        "review_comment": review_comment.strip(),
                        "translated_review_comment": translated_review_comment.strip(),
                    }

                    all_reviews_data.append(review_data)

                    print("  --- 取得した口コミ情報 ---")
                    print(f"  評価: {review_data['overall_score']}")
                    print(f"  投稿者: {review_data['reviewer_name']}")
                    print(f"  旅行タイプ: {review_data['traveler_type']}")
                    print(f"  投稿日: {review_data['review_date']}")
                    # 口コミ本文は長くなる可能性があるので、先頭50文字だけ表示するなどの工夫をすると見やすい
                    print(f"  本文: {review_data['review_comment'][:50]}...")
                    if review_data['translated_review_comment']: # 翻訳文がある場合のみ表示
                        print(f"  翻訳文: {review_data['translated_review_comment'][:50]}...")
                    print("-" * 30)

                except Exception as e:
                    print(f"口コミの解析中にエラーが発生しました: {e}")

            processed_reviews_count = len(review_elements)

            # 「口コミをさらに表示する」ボタンを探してクリック
            try:
                load_more_button = driver.find_element(By.ID, "load-more-reviews")
                # ボタンが画面内にないとクリックできないことがあるのでスクロール
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", load_more_button
                )
                time.sleep(1)

                if load_more_button.is_enabled():
                    print("「口コミをさらに表示する」をクリックします。")
                    load_more_button.click()
                    # 新しい口コミが読み込まれるのを待つ
                    time.sleep(3)  # AJAXの読み込み時間として3秒待機
                else:
                    print("「さらに表示」ボタンが無効化されました。")
                    break
            except NoSuchElementException:
                # ボタンが見つからなければ、それが最後のページ
                print(
                    "「さらに表示」ボタンが見つかりません。全ての口コミを取得しました。"
                )
                break

    finally:
        print("処理を終了し、ブラウザを閉じます。")
        driver.quit()

    return all_reviews_data


# if __name__ == "__main__":
#     # テストしたいExpediaのURL
#     target_url = "https://www.expedia.co.jp/Nara-Hotels-Novotel-Nara.h103382146.Hotel-Information"

#     # --- ここで期間を指定してテストできます ---
#     # 2023年の口コミのみ取得
#     # reviews = scrape_expedia_reviews(target_url, start_date_str="2023-01-01", end_date_str="2023-12-31")

#     # 指定なしで全件取得
#     reviews = scrape_expedia_reviews(target_url)

#     print("\n--- 取得結果 ---")
#     print(f"合計 {len(reviews)} 件の口コミを取得しました。")

#     if reviews:
#         print("\n--- 最初の3件の口コミ ---")
#         for i, review in enumerate(reviews[:3]):
#             print(f"--- 口コミ {i+1} ---")
#             print(f"  評価: {review['overall_score']}")
#             print(f"  投稿者: {review['reviewer_name']}")
#             print(f"  投稿日: {review['review_date']}")
#             print(
#                 f"  本文: {review['review_comment'][:50]}..."
#             )  # 長いので50文字だけ表示
#             print(f"  翻訳文: {review['translated_review_comment'][:50]}...")

#         # もし5件以上あれば最後の口コミも表示
#         if len(reviews) > 5:
#             print("\n--- 最後の3件の口コミ ---")
#             for i, review in enumerate(reviews[-3:]):
#                 print(f"--- 口コミ {len(reviews) - 3 + i + 1} ---")
#                 print(f"  評価: {review['overall_score']}")
#                 print(f"  投稿者: {review['reviewer_name']}")
#                 print(f"  投稿日: {review['review_date']}")
#                 print(f"  本文: {review['review_comment'][:50]}...")
#                 print(f"  翻訳文: {review['translated_review_comment'][:50]}...")
