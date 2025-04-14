from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError # Moved import to top
from django.core.validators import MinValueValidator, MaxValueValidator


# Create your models here.

class User(AbstractUser):
    # Fields from AbstractUser: username, first_name, last_name, email, password,
    # groups, user_permissions, is_staff, is_active, is_superuser, last_login, date_joined

    # Use email as the primary identifier instead of username
    USERNAME_FIELD = 'email'
    # 'username' is still required by default for createsuperuser command
    # if it's part of the model. We keep it here but make it optional for regular use.
    REQUIRED_FIELDS = []

    # Ensure email is unique and stored
    email = models.EmailField(unique=True, blank=False, null=False) # Make email explicitly required

    # Make username optional and not unique for regular users
    username = models.CharField(
        max_length=150,
        unique=False, # Allow multiple users to potentially have no username or same placeholder
        blank=True,
        null=True
    )

    # Add custom fields
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
    ]

    # Core Info
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='perfumes')
    external_id = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True, help_text="ID from the source CSV")
    year_released = models.IntegerField(null=True, blank=True)
    country_origin = models.CharField(max_length=100, blank=True, null=True)

    # Description & Composition
    description = models.TextField(blank=True, null=True)
    top_notes = models.JSONField(default=list, blank=True, help_text='List of top note names')
    middle_notes = models.JSONField(default=list, blank=True, help_text='List of middle note names')
    base_notes = models.JSONField(default=list, blank=True, help_text='List of base note names')
    accords = models.ManyToManyField(Accord, blank=True, related_name='perfumes')

    # Categorization & Usage
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True) # Allow blank/null if data missing
    occasions = models.ManyToManyField(Occasion, blank=True, related_name='perfumes')
    season = models.CharField(max_length=10, choices=SEASON_CHOICES, blank=True, null=True)
    best_for = models.CharField(max_length=5, choices=BEST_FOR_CHOICES, blank=True, null=True)

    # Pricing & URLs
    pricePerML = models.DecimalField(max_digits=6, decimal_places=2, help_text='Price per milliliter', null=True, blank=True) # Allow null
    thumbnailUrl = models.URLField(max_length=500, blank=True, null=True)
    fullSizeUrl = models.URLField(max_length=500, blank=True, null=True)

    # Ratings & Performance (from CSV)
    overall_rating = models.FloatField(null=True, blank=True, help_text="Overall rating from source")
    rating_count = models.IntegerField(default=0, help_text="Number of ratings from source")
    longevity_rating = models.FloatField(null=True, blank=True, help_text="Longevity rating (0-1) from source")
    sillage_rating = models.FloatField(null=True, blank=True, help_text="Sillage rating (0-1) from source")
    price_value_rating = models.FloatField(null=True, blank=True, help_text="Price/Value rating (0-1) from source")
    popularity = models.IntegerField(default=0, help_text="Popularity score based on recent magnitude")

    # Relationships (from CSV, stored as IDs)
    similar_perfume_ids = models.JSONField(default=list, blank=True, help_text="List of external_ids of similar perfumes")
    recommended_perfume_ids = models.JSONField(default=list, blank=True, help_text="List of external_ids of recommended perfumes")

    # Internal fields (Consider adding fields for ML later, e.g., embeddings)

    def __str__(self):
        return f"{self.name} by {self.brand.name}"



class SurveyResponse(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='survey_response')
    response_data = models.JSONField(default=dict, blank=True) # Stores survey answers as JSON
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Survey Response for {self.user.email}"

class UserPerfumeMatch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfume_matches')
    perfume = models.ForeignKey('Perfume', on_delete=models.CASCADE, related_name='user_matches')
    match_percentage = models.DecimalField(
        max_digits=4,       # Allows for 1.000
        decimal_places=3,   # Three decimal places
        null=True,          # Allow null if no prediction exists yet
        blank=True
    )
    last_updated = models.DateTimeField(auto_now=True) # Track when it was last calculated

    class Meta:
        unique_together = ('user', 'perfume') # Ensure only one match entry per user-perfume pair
        indexes = [
            models.Index(fields=['user', 'perfume']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.perfume.name}: {self.match_percentage}"


class SurveyQuestion(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('gender', 'Gender Selection'),
        ('accord', 'Accord Preference'),
        # Add other types if needed later
    ]

    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    text = models.CharField(max_length=255, help_text="The question text presented to the user.")
    # For 'gender' type, options are predefined. For 'accord', it links to an Accord.
    # We can store options as JSON for flexibility, especially for gender.
    options = models.JSONField(null=True, blank=True, help_text="JSON defining options (e.g., for gender: [{'id': 'male', 'label': 'Masculinas', 'emoji': '👨'}])")
    # Link to Accord model if question_type is 'accord'
    accord = models.ForeignKey(Accord, on_delete=models.SET_NULL, null=True, blank=True, related_name='survey_questions', help_text="Associated accord, if question_type is 'accord'.")
    order = models.PositiveIntegerField(default=0, help_text="Order in which the question appears in the survey.")
    is_active = models.BooleanField(default=True, help_text="Whether this question is currently used in the survey.")

    class Meta:
        ordering = ['order'] # Ensure questions are fetched in the correct order

    def __str__(self):
        return f"({self.order}) {self.text[:50]}..."

    def clean(self):
        # Validation: Ensure 'accord' is set if type is 'accord', and null otherwise.
        # Ensure 'options' is set if type is 'gender', and null otherwise.
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
        ('box', 'Box'), # For predefined or custom boxes
    ]

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE_CHOICES, default='perfume')
    # Link to Perfume, nullable if it's a box defined by box_configuration
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, null=True, blank=True, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    # Decant size in ML, relevant for perfume items or subscription box items
    decant_size = models.IntegerField(null=True, blank=True, help_text="Size of decant in ML, if applicable")
    # Store price at the time of addition to handle price fluctuations
    price_at_addition = models.DecimalField(max_digits=10, decimal_places=2)
    # For custom boxes (AI or Manual), store configuration details
    box_configuration = models.JSONField(null=True, blank=True, help_text="JSON configuration for custom boxes")
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.product_type == 'perfume' and self.perfume:
            item_name = self.perfume.name
        elif self.product_type == 'box':
            item_name = "Custom Box" # Or derive from box_configuration if possible
        else:
            item_name = "Unknown Item"
        return f"{self.quantity} x {item_name} in cart {self.cart.id}"

    def clean(self):
        # Ensure either perfume or box_configuration is set depending on product_type
        # from django.core.exceptions import ValidationError # Import moved to top
        if self.product_type == 'perfume' and not self.perfume:
            raise ValidationError("Perfume must be selected for product_type 'perfume'.")
        if self.product_type == 'box' and not self.box_configuration:
             # Allow box_configuration to be null initially, maybe set later? Or require it?
             # For now, let's allow it to be potentially set later.
             pass
             # raise ValidationError("Box configuration must be provided for product_type 'box'.")
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
    # Consider adding fields like price, image_url, etc. later if needed

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
    # Define criteria for perfume selection (e.g., JSONField for complex rules, or simpler fields)
    # Example: Allow perfumes up to a certain price point or from specific brands/categories
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
    # Add end_date or renewal_date if needed for billing cycles
    # end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Store payment details reference (e.g., Stripe customer/subscription ID) - Add later with payment integration
    # payment_provider_subscription_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        tier_name = self.tier.name if self.tier else "No Tier"
        status = "Active" if self.is_active else "Inactive"
        return f"{self.user.email} - {tier_name} ({status})"

# --- End Subscription Models ---


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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders') # Keep order if user deleted? Or CASCADE?
    order_date = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    # Store shipping address details directly or link to a saved address model?
    # For simplicity now, store directly. Consider Address model later.
    shipping_address = models.TextField(blank=True, null=True)
    # Payment details - store reference to payment transaction ID later
    # payment_details = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order_date'] # Show newest orders first

    def __str__(self):
        return f"Order {self.id} by {self.user.email if self.user else 'Guest'} on {self.order_date.strftime('%Y-%m-%d')}"

class OrderItem(models.Model):
    """
    Represents an item within an order, mirroring CartItem structure at the time of purchase.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # Link to the specific perfume purchased
    perfume = models.ForeignKey(Perfume, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items') # Keep item record if perfume deleted
    # Store details as they were at the time of purchase
    product_type = models.CharField(max_length=10, default='perfume') # 'perfume' or 'box'
    quantity = models.PositiveIntegerField(default=1)
    decant_size = models.IntegerField(null=True, blank=True, help_text="Size of decant in ML, if applicable")
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    # If it was a box, store its configuration/details
    box_configuration = models.JSONField(null=True, blank=True, help_text="JSON configuration for custom boxes if applicable")
    # Store the name/description as it was, in case the product changes later
    item_name = models.CharField(max_length=255, blank=True, null=True) # e.g., "Chanel No. 5" or "Discovery Box"
    item_description = models.TextField(blank=True, null=True)

    def __str__(self):
        item_desc = self.item_name if self.item_name else f"Item {self.id}"
        return f"{self.quantity} x {item_desc} in Order {self.order.id}"

# --- End Order Models ---


# --- Rating & Favorite Models ---

class Rating(models.Model):
    """
    Represents a user's rating for a specific perfume.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings')
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='ratings')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], # Assuming a 1-5 star rating
        help_text="User rating (1-5)"
    )
    timestamp = models.DateTimeField(auto_now=True) # Track when the rating was given/updated (use auto_now for updates)

    class Meta:
        unique_together = ('user', 'perfume') # User can only rate a perfume once
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
        unique_together = ('user', 'perfume') # User can only favorite a perfume once
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['user', 'perfume']),
        ]

    def __str__(self):
        return f"{self.user.email} favorited {self.perfume.name}"

# --- End Rating & Favorite Models ---
