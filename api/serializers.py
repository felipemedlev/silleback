from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from rest_framework import serializers
from .models import ( # Add Cart, CartItem, PredefinedBox, SubscriptionTier, UserSubscription, Order, OrderItem, Rating, Favorite, Note, Coupon
    Brand, Occasion, Accord, Perfume, SurveyResponse, UserPerfumeMatch,
    Cart, CartItem, PredefinedBox, SubscriptionTier, UserSubscription,
    Order, OrderItem, Rating, Favorite, Note, Coupon
)
from django.contrib.auth import get_user_model

User = get_user_model() # Get the custom User model defined in settings.AUTH_USER_MODEL

class UserCreateSerializer(BaseUserCreateSerializer):
    """
    Serializer for creating users with optional username.
    """
    username = serializers.CharField(required=False)  # Make username optional

    def create(self, validated_data):
        # If username is not provided, use the first part of email as username
        if 'username' not in validated_data:
            email = validated_data.get('email')
            username = email.split('@')[0]
            validated_data['username'] = username
        return super().create(validated_data)

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'username', 'password', 'phone', 'address')

class UserSerializer(BaseUserSerializer):
    """
    Serializer for retrieving and updating user details (excluding sensitive info like password).
    """
    class Meta(BaseUserSerializer.Meta):
        model = User
        # Specify fields available when viewing/updating user profile
        fields = ('id', 'email', 'username', 'phone', 'address', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')
        # Prevent changing email via this serializer easily after creation
        read_only_fields = ('email', 'date_joined', 'is_active', 'is_staff')

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class OccasionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Occasion
        fields = '__all__'

class AccordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accord
        fields = '__all__'

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = '__all__'

class PerfumeSerializer(serializers.ModelSerializer):
    # Use StringRelatedField for readable representation of related objects
    brand = serializers.StringRelatedField()
    occasions = serializers.StringRelatedField(many=True)
    accords = serializers.StringRelatedField(many=True)
    # Add notes as string representations
    top_notes = serializers.StringRelatedField(many=True)
    middle_notes = serializers.StringRelatedField(many=True)
    base_notes = serializers.StringRelatedField(many=True)
    # Add personalized match percentage field
    match_percentage = serializers.SerializerMethodField()
    best_for = serializers.SerializerMethodField() # Add SerializerMethodField for best_for

    class Meta:
        model = Perfume
        # Include all relevant fields for the perfume catalog, plus the new match field and other added fields
        fields = (
            'id', 'external_id', 'name', 'brand', 'description',
            'top_notes', 'middle_notes', 'base_notes',
            'accords', 'occasions',
            'gender', 'season', 'best_for', 'year_released', 'country_origin', # Keep original best_for in fields for now, will be handled by get_best_for
            'price_per_ml', 'thumbnail_url', 'full_size_url',
            'overall_rating', 'rating_count', 'longevity_rating', 'sillage_rating', 'price_value_rating',
            'popularity',
            'similar_perfume_ids', 'recommended_perfume_ids', # Note: These expose external IDs
            'match_percentage'
        )

    def get_match_percentage(self, obj):
        """
        Calculates the match percentage for the current user and perfume.
        Returns the percentage (Decimal) or None if user is not authenticated
        or no match exists.
        """
        user = self.context['request'].user
        if user.is_authenticated:
            try:
                match = UserPerfumeMatch.objects.get(user=user, perfume=obj)
                return match.match_percentage # Returns Decimal or None
            except UserPerfumeMatch.DoesNotExist:
                return None
        return None

    def get_best_for(self, obj):
        """
        Returns 'both' if best_for is null or empty, otherwise returns the original value.
        """
        if obj.best_for is None or obj.best_for == '':
            return 'both'
        return obj.best_for


class SurveyResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for submitting and viewing survey responses.
    The 'user' field is automatically set to the authenticated user during creation.
    """
    # Make user read-only in the serializer context, it will be set in the view
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    # Allow response_data to be written
    response_data = serializers.JSONField()
    # completed_at is read-only as it's set automatically on creation
    completed_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SurveyResponse
        fields = ('user', 'response_data', 'completed_at')
        # Explicitly state read_only fields for clarity, though PrimaryKeyRelatedField(read_only=True) handles 'user'
        read_only_fields = ('user', 'completed_at')





class CartItemAddSerializer(serializers.Serializer):
    """Serializer specifically for adding items to the cart."""
    perfume_id = serializers.PrimaryKeyRelatedField(queryset=Perfume.objects.all(), required=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    decant_size = serializers.IntegerField(required=False, allow_null=True)
    # product_type and box_configuration could be added here if needed for adding boxes

# --- Cart Serializers ---

class PerfumeSummarySerializer(serializers.ModelSerializer):
    """ Minimal serializer for representing perfumes within cart items. """
    brand = serializers.StringRelatedField()
    class Meta:
        model = Perfume
        fields = ('id', 'name', 'brand', 'thumbnail_url', 'price_per_ml', 'external_id') # Added external_id for consistency

class CartItemSerializer(serializers.ModelSerializer):
    """ Serializer for displaying items within a cart. """
    # Use nested serializer for perfume details on read
    perfume = PerfumeSummarySerializer(read_only=True)
    # Add a write-only field to accept perfume ID on creation/update (handled in view/specific serializer)
    perfume_id = serializers.PrimaryKeyRelatedField(
        queryset=Perfume.objects.all(), source='perfume', write_only=True, required=False, allow_null=True
    )
    # Calculate item total price (consider adding this if needed)
    # item_total = serializers.SerializerMethodField()

    class Meta:
        model = 'api.CartItem' # Use string import
        fields = (
            'id', 'product_type', 'perfume', 'perfume_id', 'quantity',
            'decant_size', 'price_at_addition', 'box_configuration', 'added_at'
            # 'item_total'
        )
        read_only_fields = ('id', 'price_at_addition', 'added_at') # Price is set on addition

    # def get_item_total(self, obj):
    #     # Basic calculation, might need refinement based on decant_size, box config etc.
    #     if obj.perfume and obj.price_at_addition:
    #         return obj.quantity * obj.price_at_addition # Or calculate based on price_per_ml * decant_size?
    #     # Add logic for box pricing if applicable
    #     return None

    def validate(self, data):
        """
        Validate based on product_type.
        """
        product_type = data.get('product_type', self.instance.product_type if self.instance else 'perfume')
        perfume = data.get('perfume', None) # Note: source='perfume' maps perfume_id here
        box_configuration = data.get('box_configuration', None)

        if product_type == 'perfume' and not perfume:
            raise serializers.ValidationError({"perfume_id": "Perfume must be selected for product_type 'perfume'."})
        if product_type == 'box' and not box_configuration:
            # Decide if box_configuration is mandatory on creation/update
            # raise serializers.ValidationError({"box_configuration": "Box configuration must be provided for product_type 'box'."})
            pass
        if product_type == 'box' and perfume:
            raise serializers.ValidationError({"perfume_id": "Perfume should not be set for product_type 'box'."})

        return data


class CartSerializer(serializers.ModelSerializer):
    """ Serializer for the user's shopping cart. """
    user = UserSerializer(read_only=True) # Display user details
    items = CartItemSerializer(many=True, read_only=True) # Nested list of cart items
    # Add calculated total field if needed
    # cart_total = serializers.SerializerMethodField()

    class Meta:
        model = 'api.Cart' # Use string import
        fields = ('id', 'user', 'items', 'created_at', 'updated_at') # Add 'cart_total' if implemented
        read_only_fields = ('id', 'user', 'created_at', 'updated_at', 'items')

    # def get_cart_total(self, obj):
    #     # Sum up item totals - requires item_total on CartItemSerializer
    #     total = sum(item.quantity * item.price_at_addition for item in obj.items.all() if item.price_at_addition is not None)
    #     # Add logic for box pricing if needed
    #     return total

# --- Box Serializers ---

class PredefinedBoxSerializer(serializers.ModelSerializer):
    """ Serializer for predefined boxes. """
    # Use the summary serializer for nested perfume representation
    perfumes = PerfumeSummarySerializer(many=True, read_only=True)

    class Meta:
        model = PredefinedBox
        fields = ('id', 'title', 'description', 'icon', 'gender', 'perfumes') # Added icon, gender, corrected name->title
        # Add other fields like price, image_url if they are added to the model

# --- End Box Serializers ---


# --- Subscription Serializers ---

class SubscriptionTierSerializer(serializers.ModelSerializer):
    """ Serializer for displaying subscription tiers. """
    class Meta:
        model = SubscriptionTier
        fields = ('id', 'name', 'price', 'decant_size', 'perfume_criteria', 'description')
        # Typically read-only for listing tiers
        read_only_fields = fields

class UserSubscriptionSerializer(serializers.ModelSerializer):
    """ Serializer for displaying the user's current subscription status. """
    # Use nested serializer for tier details
    tier = SubscriptionTierSerializer(read_only=True)
    # User is implicitly the request user, not shown directly unless needed
    # user = UserSerializer(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ('id', 'tier', 'start_date', 'is_active')
        read_only_fields = ('id', 'tier', 'start_date', 'is_active') # Status is read-only

class SubscribeSerializer(serializers.Serializer):
    """ Serializer for the subscribe action. """
    tier_id = serializers.PrimaryKeyRelatedField(queryset=SubscriptionTier.objects.all(), required=True)
    # Add fields for payment details later (e.g., payment_method_id)

# --- End Subscription Serializers ---


# --- Order Serializers ---

class OrderItemSerializer(serializers.ModelSerializer):
    """ Serializer for displaying items within an order. """
    # Use the summary serializer for perfume details if available
    perfume = PerfumeSummarySerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            'id', 'perfume', 'product_type', 'quantity', 'decant_size',
            'price_at_purchase', 'box_configuration', 'item_name', 'item_description'
        )
        read_only_fields = fields # Order items are read-only representations

class OrderSerializer(serializers.ModelSerializer):
    """ Serializer for displaying order details. """
    # Nested items using OrderItemSerializer
    items = OrderItemSerializer(many=True, read_only=True)
    # Optionally display user email or use a nested UserSerializer
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True) # Allow null if user is deleted

    class Meta:
        model = Order
        fields = (
            'id', 'user_email', 'order_date', 'total_price', 'status',
            'shipping_address', 'items', 'updated_at'
            # Add payment_details later if needed
        )
        read_only_fields = fields # Orders are typically read-only once created via API

class OrderCreateSerializer(serializers.Serializer):
    """ Serializer for creating an order from the cart. """
    # Expects shipping address, other details derived from cart/user
    shipping_address = serializers.CharField(required=True, allow_blank=False)
    # Add payment details field later (e.g., payment_method_id)

# --- End Order Serializers ---


# --- Rating & Favorite Serializers ---

class RatingSerializer(serializers.ModelSerializer):
    """ Serializer for creating/updating/viewing a perfume rating. """
    # User and Perfume are set implicitly or via URL, make read-only here
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    perfume = serializers.PrimaryKeyRelatedField(read_only=True)
    # Allow rating field to be written
    rating = serializers.IntegerField(min_value=1, max_value=5, required=True)

    class Meta:
        model = Rating
        fields = ('id', 'user', 'perfume', 'rating', 'timestamp')
        read_only_fields = ('id', 'user', 'perfume', 'timestamp') # User/Perfume set in view

    def validate_rating(self, value):
        """ Ensure rating is within the allowed range (1-5). """
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

class FavoriteSerializer(serializers.ModelSerializer):
    """ Serializer for creating a favorite relationship. """
    # User is set implicitly, Perfume via request data
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    perfume_id = serializers.PrimaryKeyRelatedField(
        queryset=Perfume.objects.all(), source='perfume', write_only=True
    )

    class Meta:
        model = Favorite
        fields = ('id', 'user', 'perfume_id', 'added_at')
        read_only_fields = ('id', 'user', 'added_at')

    def create(self, validated_data):
        # Ensure user is set correctly during creation
        validated_data['user'] = self.context['request'].user
        # Prevent duplicates using get_or_create
        favorite, created = Favorite.objects.get_or_create(
            user=validated_data['user'],
            perfume=validated_data['perfume'],
            defaults={} # No extra defaults needed here
        )
        return favorite


class FavoriteListSerializer(serializers.ModelSerializer):
    """ Serializer specifically for listing favorites, showing perfume details. """
    # Use nested serializer for perfume details
    perfume = PerfumeSummarySerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ('id', 'perfume', 'added_at') # Show perfume details and when it was added
        read_only_fields = fields

# --- End Rating & Favorite Serializers ---
# --- Recommendation Serializer ---

class UserPerfumeMatchSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying user-perfume match scores, including perfume details.
    Used for the /api/recommendations/ endpoint.
    """
    # Use the summary serializer for nested perfume representation
    perfume = PerfumeSummarySerializer(read_only=True)
    # Rename match_percentage for clarity in API response
    score = serializers.DecimalField(source='match_percentage', max_digits=4, decimal_places=3, read_only=True)

    class Meta:
        model = UserPerfumeMatch
        fields = ('perfume', 'score', 'last_updated')
        read_only_fields = fields # This data is read-only via the API

# --- End Recommendation Serializer ---

# --- Coupon Serializer ---

class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer for Coupon model.
    Handles creation, retrieval, and updates of coupons.
    """
    class Meta:
        model = Coupon
        fields = (
            'id', 'code', 'discount_type', 'value', 'description',
            'min_purchase_amount', 'expiry_date', 'is_active',
            'max_uses', 'uses_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'uses_count', 'created_at', 'updated_at')

    def validate_code(self, value):
        """
        Ensure code is uppercase.
        """
        return value.upper()

    def validate(self, data):
        """
        Validate discount_type and value.
        """
        # Access instance during updates
        instance = getattr(self, 'instance', None)
        discount_type = data.get('discount_type', instance.discount_type if instance else None)
        value = data.get('value', instance.value if instance else None)

        if discount_type == 'percentage':
            if not (0 < value <= 100):
                raise serializers.ValidationError({'value': 'Percentage value must be between 0 (exclusive) and 100 (inclusive).'})
        elif discount_type == 'fixed':
            if value <= 0:
                raise serializers.ValidationError({'value': 'Fixed discount value must be positive.'})

        # Ensure min_purchase_amount is not negative if provided
        min_purchase_amount = data.get('min_purchase_amount')
        if min_purchase_amount is not None and min_purchase_amount < 0:
            raise serializers.ValidationError({'min_purchase_amount': 'Minimum purchase amount cannot be negative.'})

        return data

# --- End Coupon Serializer ---