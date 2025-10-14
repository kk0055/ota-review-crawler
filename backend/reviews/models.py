from django.db import models
from django.utils import timezone
import hashlib
import uuid
from django.utils.text import slugify

# -----------------------------------------------------------------------------
# 1. OTAモデル: OTAサイトのマスター情報を管理
# -----------------------------------------------------------------------------
class Ota(models.Model):
    """OTAサイト (例: Booking.com, Agoda) の情報を格納するモデル"""

    name = models.CharField(
        "OTA名",
        max_length=50,
        unique=True,
        help_text="OTAサイトの名前 (例: Booking.com)",
    )
    base_url = models.URLField(
        "ベースURL",
        max_length=255,
        help_text="OTAサイトのトップページのURL",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "OTAサイト"
        verbose_name_plural = "OTAサイト"

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
# 1. Hotelモデル: ホテルのマスター情報を管理
# -----------------------------------------------------------------------------
class Hotel(models.Model):
    """物理的なホテルそのもののマスター情報を管理するモデル"""

    name = models.CharField(
        "ホテル正式名称",
        max_length=200,
        unique=True,  # ホテル名はユニークとする
        help_text="ホテルの正式名称（例: 帝国ホテル東京）",
    )
    slug = models.SlugField(
        "スラッグ",
        max_length=100,
        unique=True,
        blank=True, 
        help_text="URLや設定ファイルで使われる、ユニークな識別子。",
    )
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "ホテルマスター"
        verbose_name_plural = "ホテルマスター"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        # slugが空の場合、nameから自動生成する
        if not self.slug and self.name:
            # slugifyを使って、"ノボテル奈良" -> "ノボテル奈良" (日本語許可)
            # or "novotel-nara" (ASCIIのみ) のように変換
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
#  CrawlTargetモデル: クロール対象となるOTAとホテルの情報を管理
# -----------------------------------------------------------------------------
class CrawlTarget(models.Model):
    """
    OTAサイト上の、クロール対象となる個別のホテル掲載情報を管理するモデル。
    """

    class CrawlStatus(models.TextChoices):
        PENDING = "PENDING", "処理中"
        SUCCESS = "SUCCESS", "成功"
        FAILURE = "FAILURE", "失敗"
        NEVER_RUN = "NEVER_RUN", "未実行"

    last_crawl_status = models.CharField(
        "最終クロールステータス",
        max_length=10,
        choices=CrawlStatus.choices,
        default=CrawlStatus.NEVER_RUN,  # デフォルト値を設定
        help_text="このOTAのホテルの最終クロール結果",
    )
    last_crawled_at = models.DateTimeField(
        "最終クロール日時",
        null=True,
        blank=True,
        help_text="最後にクロール処理が実行された日時",
    )
    last_crawl_message = models.TextField(
        "最終クロール結果メッセージ",
        blank=True,
        null=True,
        help_text="成功メッセージやエラー詳細を格納",
    )
    ota = models.ForeignKey(
        Ota,
        verbose_name="OTAサイト",
        on_delete=models.CASCADE,
        related_name="crawl_targets",
    )
    hotel = models.ForeignKey(
        Hotel,
        verbose_name="ホテル",
        on_delete=models.CASCADE,
        related_name="crawl_targets",
    )
    hotel_id_in_ota = models.CharField(
        "OTA内のホテルID",
        max_length=50,
        null=True,
        blank=True,
        help_text="各OTAサイト内でホテルを一位に識別するID",
    )
    # hotel_name = models.CharField("ホテル名", max_length=200)
    crawl_url = models.URLField(
        "クロール対象URL",
        max_length=512,  # URLは長くなる可能性があるので余裕を持たせる
        null=True,
        blank=True,
        help_text="このホテルの口コミ一覧ページのURL",
    )

    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "クロール対象（ホテル掲載情報）"
        verbose_name_plural = "クロール対象（ホテル掲載情報）"
        ordering = ["hotel", "ota"]
        constraints = [
            # otaとhotelの組み合わせでユニークにする
            models.UniqueConstraint(
                fields=["ota", "hotel"], name="unique_ota_hotel_listing"
            )
        ]

    def __str__(self):
        return f"{self.hotel.name} ({self.ota.name})"


# -----------------------------------------------------------------------------
# 3. Reviewモデル: 口コミ情報を詳細に管理
# -----------------------------------------------------------------------------
class Review(models.Model):
    """各OTAサイトから収集した詳細な口コミ情報を格納するモデル"""

    # --- 関連情報 ---
    crawl_target = models.ForeignKey(
        CrawlTarget,
        verbose_name="クロール対象",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    review_id_in_ota = models.CharField(
        "OTA内の口コミID",
        max_length=50,
        null=True,
        blank=True,
        help_text="取得できる場合のみ格納",
    )
    review_hash = models.CharField(
        "レビューハッシュ",
        max_length=64,  # SHA256のハッシュ値（64文字）を想定
        unique=True,  # このフィールドでユニーク性を担保する
        db_index=True,  # 検索パフォーマンス向上のためインデックスを付与
        editable=False,  # 管理画面などでは編集不可にする
        help_text="レビュー内容から生成された一意のハッシュ値。重複登録の防止に利用。",
    )
    # --- レビュアー情報 ---
    reviewer_name = models.CharField(
        "投稿者の表示名", max_length=255, null=True, blank=True
    )

    nationality_region = models.CharField(
        "国籍（大分類）", max_length=100, null=True, blank=True
    )
    nationality_country = models.CharField(
        "国籍（小分類）", max_length=100, null=True, blank=True
    )
    traveler_type = models.CharField(
        "旅行形態（正規化済）", max_length=50, null=True, blank=True, db_index=True
    )
    traveler_type_original = models.CharField(
        "旅行形態（取得元オリジナル）", max_length=100, null=True, blank=True
    )
    purpose_of_visit = models.CharField(
        "旅行の目的（正規化済）", max_length=50, null=True, blank=True, db_index=True
    )
    purpose_of_visit_original = models.CharField(
        "旅行の目的（取得元オリジナル）", max_length=100, null=True, blank=True
    )
    gender = models.CharField("性別", max_length=20, null=True, blank=True)
    age_group = models.CharField("年代", max_length=20, null=True, blank=True)

    # --- 評価スコア ---
    original_score_scale = models.PositiveIntegerField(
        "元の評価尺度",
        null=True,
        blank=True,
        help_text="評価点の満点（例: 5, 10）",
    )

    # 各スコアフィールドを「正規化済み」と「オリジナル」に分ける
    # 総合評価点 (10点満点に正規化)
    overall_score = models.DecimalField(
        "総合評価点（10点満点に正規化）",
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        db_index=True,
    )
    overall_score_original = models.CharField(
        "総合評価点（取得元オリジナル）", max_length=10, null=True, blank=True
    )  # 元のデータが数値以外の場合も考慮しCharFieldも選択肢

    # 立地スコア
    location_score = models.DecimalField(
        "立地スコア（正規化済）", max_digits=3, decimal_places=1, null=True, blank=True
    )
    location_score_original = models.CharField(
        "立地スコア（オリジナル）", max_length=10, null=True, blank=True
    )

    # サービススコア
    service_score = models.DecimalField(
        "サービススコア（正規化済）",
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )
    service_score_original = models.CharField(
        "サービススコア（オリジナル）", max_length=10, null=True, blank=True
    )

    # 清潔感スコア
    cleanliness_score = models.DecimalField(
        "清潔感スコア（正規化済）",
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )
    cleanliness_score_original = models.CharField(
        "清潔感スコア（オリジナル）", max_length=10, null=True, blank=True
    )

    # 施設スコア
    facilities_score = models.DecimalField(
        "施設スコア（正規化済）", max_digits=3, decimal_places=1, null=True, blank=True
    )
    facilities_score_original = models.CharField(
        "施設スコア（オリジナル）", max_length=10, null=True, blank=True
    )

    # 食事スコア
    food_score = models.DecimalField(
        "食事スコア（正規化済）", max_digits=3, decimal_places=1, null=True, blank=True
    )
    food_score_original = models.CharField(
        "食事スコア（オリジナル）", max_length=10, null=True, blank=True
    )

    # コスパスコア
    price_performance_score = models.DecimalField(
        "コスパスコア（正規化済）",
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )
    price_performance_score_original = models.CharField(
        "コスパスコア（オリジナル）", max_length=10, null=True, blank=True
    )

    # --- 口コミ本文 ---
    review_title = models.CharField(
        "口コミタイトル", max_length=255, null=True, blank=True
    )
    language_code = models.CharField(
        "言語コード",
        max_length=10,
        null=True,
        blank=True,
    )
    review_language = models.CharField("言語", max_length=50, null=True, blank=True)
    review_comment = models.TextField("オリジナルの口コミ本文", null=True, blank=True)
    translated_review_comment = models.TextField(
        "翻訳した口コミ本文", null=True, blank=True
    )
    location_comment = models.TextField("立地に関するコメント", null=True, blank=True)
    service_comment = models.TextField(
        "サービスに関するコメント", null=True, blank=True
    )
    cleanliness_comment = models.TextField(
        "清潔感に関するコメント", null=True, blank=True
    )
    facilities_comment = models.TextField("施設に関するコメント", null=True, blank=True)
    room_comment = models.TextField("客室に関するコメント", null=True, blank=True)
    bath_comment = models.TextField("風呂に関するコメント", null=True, blank=True)
    food_comment = models.TextField("食事全般に関するコメント", null=True, blank=True)
    breakfast_comment = models.TextField("朝食に関するコメント", null=True, blank=True)
    dinner_comment = models.TextField("夕食に関するコメント", null=True, blank=True)

    # --- 予約情報 (取得できない場合を考慮し、nullを許可) ---
    room_type = models.CharField(
        "部屋タイプ（正規化済）", max_length=255, null=True, blank=True, db_index=True
    )
    room_type_original = models.CharField(
        "部屋タイプ（取得元オリジナル）", max_length=255, null=True, blank=True
    )
    price = models.DecimalField(
        "価格",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="予約時の価格。通貨はcurrencyフィールドで指定。",
    )
    currency = models.CharField(
        "通貨",
        max_length=3,
        null=True,
        blank=True,
        help_text="価格の通貨コード (例: JPY, USD)",
    )
    # --- 日時情報 ---
    stay_date = models.DateField(
        "宿泊年月",
        null=True,
        blank=True,
        help_text="口コミ対象の宿泊年月。",
    )
    review_date = models.DateField("口コミ投稿日", null=True, blank=True)
    crawled_at = models.DateTimeField("データ取得日時", default=timezone.now)
    created_at = models.DateTimeField("DB登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("データ更新日時", auto_now=True)

    class Meta:
        verbose_name = "口コミ情報"
        verbose_name_plural = "口コミ情報"
        ordering = ["-review_date"]

    def __str__(self):

        display_id = self.review_id_in_ota or f"hash:{self.review_hash[:7]}"
        return f"Review ({display_id}) for {self.crawl_target.hotel.name} on {self.crawl_target.ota.name}"
