from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from rest_framework import serializers
from .models import ( # Add Cart, CartItem, PredefinedBox
    Brand, Occasion, Accord, Perfume, SurveyResponse, UserPerfumeMatch,
    Cart, CartItem, PredefinedBox
)
from django.contrib.auth import get_user_model

User = get_user_model() # Get the custom User model defined in settings.AUTH_USER_MODEL

class UserCreateSerializer(BaseUserCreateSerializer):
    """
    Serializer for creating users. Includes custom fields.
    """
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        # Specify fields available during registration
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

class PerfumeSerializer(serializers.ModelSerializer):
    # Use StringRelatedField for readable representation of related objects
    brand = serializers.StringRelatedField()
    occasions = serializers.StringRelatedField(many=True)
    accords = serializers.StringRelatedField(many=True)
    # Add personalized match percentage field
    match_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Perfume
        # Include all relevant fields for the perfume catalog, plus the new match field and other added fields
        fields = (
            'id', 'external_id', 'name', 'brand', 'description',
            'top_notes', 'middle_notes', 'base_notes',
            'accords', 'occasions',
            'gender', 'season', 'best_for', 'year_released', 'country_origin',
            'pricePerML', 'thumbnailUrl', 'fullSizeUrl',
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
        fields = ('id', 'name', 'brand', 'thumbnailUrl', 'pricePerML') # Key info for cart display

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
    #         return obj.quantity * obj.price_at_addition # Or calculate based on pricePerML * decant_size?
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
        fields = ('id', 'name', 'description', 'perfumes')
        # Add other fields like price, image_url if they are added to the model

# --- End Box Serializers ---


# Add other serializers here later (OrderSerializer, etc.)


# --- End Cart Serializers ---


# Add other serializers here later (OrderSerializer, etc.)

# Add other serializers here later (PerfumeSerializer, CartSerializer, etc.)