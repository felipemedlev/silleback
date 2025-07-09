from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    email = models.EmailField(unique=True, blank=False, null=False)
    username = models.CharField(
        max_length=150,
        unique=False,
        blank=True,
        null=True
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    def __str__(self):
        return self.email

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Occasion(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Accord(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Note(models.Model):
    """
    Represents a perfume note (ingredient) that can be used in top, middle, or base notes.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Perfume(models.Model):
    # Choices definitions
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('unisex', 'Unisex'),
    ]
    SEASON_CHOICES = [
        ('winter', 'Winter'),
        ('summer', 'Summer'),
        ('autumn', 'Autumn'),
        ('spring', 'Spring'),
    ]
    BEST_FOR_CHOICES = [
        ('day', 'Day'),
        ('night', 'Night'),
        ('both', 'Day and Night'),
    ]

    # Core Info
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='perfumes')
    external_id = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True, help_text="ID from the source CSV")
    year_released = models.IntegerField(null=True, blank=True)
    country_origin = models.CharField(max_length=100, blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    top_notes = models.ManyToManyField(Note, blank=True, related_name='perfumes_as_top')
    middle_notes = models.ManyToManyField(Note, blank=True, related_name='perfumes_as_middle')
    base_notes = models.ManyToManyField(Note, blank=True, related_name='perfumes_as_base')

    accords = models.ManyToManyField(
        Accord,
        through='PerfumeAccordOrder',
        blank=True,
        related_name='perfumes'
    )

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    occasions = models.ManyToManyField(Occasion, blank=True, related_name='perfumes')
    season = models.CharField(max_length=10, choices=SEASON_CHOICES, blank=True, null=True)
    best_for = models.CharField(max_length=5, choices=BEST_FOR_CHOICES, blank=True, null=True)

    price_per_ml = models.DecimalField(max_digits=6, decimal_places=2, help_text='Price per milliliter', null=True, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True, null=True)
    full_size_url = models.URLField(max_length=500, blank=True, null=True)

    overall_rating = models.FloatField(null=True, blank=True, help_text="Overall rating from source")
    rating_count = models.IntegerField(default=0, help_text="Number of ratings from source")
    longevity_rating = models.FloatField(null=True, blank=True, help_text="Longevity rating (0-1) from source")
    sillage_rating = models.FloatField(null=True, blank=True, help_text="Sillage rating (0-1) from source")
    price_value_rating = models.FloatField(null=True, blank=True, help_text="Price/Value rating (0-1) from source")
    popularity = models.IntegerField(default=0, help_text="Popularity score based on recent magnitude")

    similar_perfume_ids = models.JSONField(default=list, blank=True, help_text="List of external_ids of similar perfumes")
    recommended_perfume_ids = models.JSONField(default=list, blank=True, help_text="List of external_ids of recommended perfumes")


    def __str__(self):
        return f"{self.name} by {self.brand.name}"

    def get_ordered_accords(self):
        return self.accords.order_by('perfumeaccordorder__order')


class PerfumeAccordOrder(models.Model):
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE)
    accord = models.ForeignKey(Accord, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['order']
        unique_together = ('perfume', 'accord')


class SurveyResponse(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='survey_response')
    response_data = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Survey Response for {self.user.email}"

class UserPerfumeMatch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfume_matches')
    perfume = models.ForeignKey('Perfume', on_delete=models.CASCADE, related_name='user_matches')
    match_percentage = models.DecimalField(
        max_digits=4,       # Allows for 1.000
        decimal_places=3,   # Three decimal places
        null=True,
        blank=True
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'perfume')
        indexes = [
            models.Index(fields=['user', 'perfume']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.perfume.name}: {self.match_percentage}"



class SurveyQuestion(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('gender', 'Gender Selection'),
        ('accord', 'Accord Preference'),
    ]

    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    text = models.CharField(max_length=255, help_text="The question text presented to the user.")
    options = models.JSONField(null=True, blank=True, help_text="JSON defining options (e.g., for gender: [{'id': 'male', 'label': 'Masculinas', 'emoji': '👨'}])")
    accord = models.ForeignKey(Accord, on_delete=models.SET_NULL, null=True, blank=True, related_name='survey_questions', help_text="Associated accord, if question_type is 'accord'.")
    order = models.PositiveIntegerField(default=0, help_text="Order in which the question appears in the survey.")
    is_active = models.BooleanField(default=True, help_text="Whether this question is currently used in the survey.")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"({self.order}) {self.text[:50]}..."

    def clean(self):
        if self.question_type == 'accord' and not self.accord:
            raise ValidationError("An Accord must be linked for question_type 'accord'.")
        if self.question_type != 'accord' and self.accord:
            raise ValidationError("Accord should only be linked for question_type 'accord'.")
        if self.question_type == 'gender' and not self.options:
             raise ValidationError("Options must be defined for question_type 'gender'.")
        if self.question_type != 'gender' and self.options:
             raise ValidationError("Options should only be defined for question_type 'gender'.")

class Cart(models.Model):
    """
    Represents a user's shopping cart.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.email}"

class CartItem(models.Model):
    """
    Represents an item within a shopping cart.
    Can be a single perfume or a configured box.
    """
    PRODUCT_TYPE_CHOICES = [
        ('perfume', 'Perfume'),
        ('box', 'Box'),
    ]

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE_CHOICES, default='perfume')
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Name of the item (e.g., perfume name or box name like 'AI Box (4 x 5ml)')")
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, null=True, blank=True, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    decant_size = models.IntegerField(null=True, blank=True, help_text="Size of decant in ML (for individual perfumes or items in a box)")
    price_at_addition = models.DecimalField(max_digits=10, decimal_places=2)
    box_configuration = models.JSONField(null=True, blank=True, help_text="JSON configuration for boxes (e.g., list of perfumes, specific decant size for the box)")
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        display_name = self.name
        if not display_name and self.product_type == 'perfume' and self.perfume:
            display_name = self.perfume.name
        elif not display_name:
            display_name = f"Unnamed {self.product_type} item"
        return f"{self.quantity} x {display_name} in cart {self.cart.id}"

    def clean(self):
        if self.product_type == 'perfume' and not self.perfume:
            raise ValidationError("Perfume must be selected for product_type 'perfume'.")
        if self.product_type == 'box' and not self.box_configuration:
             pass
        if self.product_type == 'box' and self.perfume:
            raise ValidationError("Perfume should not be set for product_type 'box'.")

class PredefinedBox(models.Model):
    """
    Represents a curated box with a fixed set of perfumes.
    """
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Feather icon name")
    gender = models.CharField(
        max_length=10,
        choices=[('masculino', 'Masculino'), ('femenino', 'Femenino')],
        blank=True,
        null=True,
        help_text="Target gender for the box"
    )
    perfumes = models.ManyToManyField(Perfume, related_name='predefined_boxes', blank=True)

    def __str__(self):
        return self.title


# --- Subscription Models ---
class SubscriptionTier(models.Model):
    """
    Represents different subscription levels offered.
    """
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Monthly price")
    decant_size = models.IntegerField(help_text="Size of decant in ML included in this tier")
    perfume_criteria = models.JSONField(default=dict, blank=True, help_text="JSON defining criteria for perfume selection in this tier")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} (${self.price}/month)"

class UserSubscription(models.Model):
    """
    Links a user to a specific subscription tier they are subscribed to.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription') # Assuming one active subscription per user
    tier = models.ForeignKey(SubscriptionTier, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscribers') # SET_NULL keeps user record if tier deleted
    start_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        tier_name = self.tier.name if self.tier else "No Tier"
        status = "Active" if self.is_active else "Inactive"
        return f"{self.user.email} - {tier_name} ({status})"

# --- Order Models ---
class Order(models.Model):
    """
    Represents a customer order.
    """
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_date = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    shipping_address = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"Order {self.id} by {self.user.email if self.user else 'Guest'} on {self.order_date.strftime('%Y-%m-%d')}"

class OrderItem(models.Model):
    """
    Represents an item within an order, mirroring CartItem structure at the time of purchase.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    perfume = models.ForeignKey(Perfume, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    product_type = models.CharField(max_length=10, default='perfume')
    quantity = models.PositiveIntegerField(default=1)
    decant_size = models.IntegerField(null=True, blank=True, help_text="Size of decant in ML, if applicable")
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    box_configuration = models.JSONField(null=True, blank=True, help_text="JSON configuration for custom boxes if applicable")
    item_name = models.CharField(max_length=255, blank=True, null=True)
    item_description = models.TextField(blank=True, null=True)

    def __str__(self):
        item_desc = self.item_name if self.item_name else f"Item {self.id}"
        return f"{self.quantity} x {item_desc} in Order {self.order.id}"

class Rating(models.Model):
    """
    Represents a user's rating for a specific perfume.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings')
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='ratings')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User rating (1-5)"
    )
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'perfume')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'perfume']),
        ]

    def __str__(self):
        return f"{self.user.email} rated {self.perfume.name}: {self.rating} stars"

class Favorite(models.Model):
    """
    Represents a perfume marked as a favorite by a user.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='favorited_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'perfume')
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['user', 'perfume']),
        ]

    def __str__(self):
        return f"{self.user.email} favorited {self.perfume.name}"


class Coupon(models.Model):
    """
    Represents a discount coupon.
    """
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]

    code = models.CharField(max_length=50, unique=True, help_text="User-facing code (e.g., SUMMER10). Should be stored in uppercase.")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Discount value (e.g., 10 for 10% or 5000 for $5000 CLP)")
    description = models.TextField(blank=True, null=True)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Minimum cart total required to apply")
    expiry_date = models.DateTimeField(null=True, blank=True, help_text="Optional expiry date and time")
    is_active = models.BooleanField(default=True, help_text="Whether the coupon is currently active")
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of times this coupon can be used in total")
    uses_count = models.PositiveIntegerField(default=0, help_text="How many times this coupon has been used")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    def clean(self):
        if self.code:
            self.code = self.code.upper()
        if self.discount_type == 'percentage' and (self.value <= 0 or self.value > 100):
            raise ValidationError({'value': 'Percentage value must be between 0 and 100.'})
        if self.discount_type == 'fixed' and self.value <= 0:
            raise ValidationError({'value': 'Fixed discount value must be positive.'})

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"