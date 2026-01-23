from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from rest_framework import serializers
from .models import (
    Brand, Occasion, Accord, Perfume, SurveyResponse, UserPerfumeMatch,
    Cart, CartItem, PredefinedBox, SubscriptionTier, UserSubscription,
    Order, OrderItem, Rating, Favorite, Note, Coupon
)
from django.contrib.auth import get_user_model

User = get_user_model()

class UserCreateSerializer(BaseUserCreateSerializer):
    username = serializers.CharField(required=False)

    def create(self, validated_data):
        if 'username' not in validated_data:
            email = validated_data.get('email')
            username = email.split('@')[0]
            validated_data['username'] = username
        return super().create(validated_data)

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'username', 'password', 'phone', 'address')

class UserSerializer(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = User
        fields = ('id', 'email', 'username', 'phone', 'address', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')
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
    brand = serializers.StringRelatedField()
    occasions = serializers.StringRelatedField(many=True)
    accords = serializers.StringRelatedField(many=True)
    top_notes = serializers.StringRelatedField(many=True)
    middle_notes = serializers.StringRelatedField(many=True)
    base_notes = serializers.StringRelatedField(many=True)
    match_percentage = serializers.SerializerMethodField()
    best_for = serializers.SerializerMethodField()

    class Meta:
        model = Perfume
        fields = (
            'id', 'external_id', 'name', 'brand', 'description',
            'top_notes', 'middle_notes', 'base_notes',
            'accords', 'occasions',
            'gender', 'season', 'best_for', 'year_released', 'country_origin',
            'price_per_ml', 'thumbnail_url', 'full_size_url',
            'overall_rating', 'rating_count', 'longevity_rating', 'sillage_rating', 'price_value_rating',
            'popularity',
            'similar_perfume_ids', 'recommended_perfume_ids',
            'match_percentage'
        )

    def get_match_percentage(self, obj):
        # Optimization: use annotated value if available
        if hasattr(obj, 'match_percentage'):
             return obj.match_percentage

        user = self.context['request'].user
        if user.is_authenticated:
            try:
                match = UserPerfumeMatch.objects.get(user=user, perfume=obj)
                return match.match_percentage
            except UserPerfumeMatch.DoesNotExist:
                return None
        return None

    def get_best_for(self, obj):
        if obj.best_for is None or obj.best_for == '':
            return 'both'
        return obj.best_for


class SurveyResponseSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    response_data = serializers.JSONField()
    completed_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SurveyResponse
        fields = ('user', 'response_data', 'completed_at')
        read_only_fields = ('user', 'completed_at')





class CartItemAddSerializer(serializers.Serializer):
    product_type = serializers.ChoiceField(choices=[('box', 'Box')])
    quantity = serializers.HiddenField(default=1)
    box_configuration = serializers.JSONField(required=True)
    name = serializers.CharField(max_length=255, required=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    def validate_product_type(self, value):
        if value != 'box':
            raise serializers.ValidationError("Only 'box' product_type is allowed.")
        return value

    def validate_box_configuration(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("box_configuration must be a JSON object.")
        if 'perfumes' not in value or not isinstance(value['perfumes'], list):
            raise serializers.ValidationError("box_configuration must contain a 'perfumes' list.")
        if not value['perfumes']:
            raise serializers.ValidationError("'perfumes' list cannot be empty.")
        if 'decant_size' not in value or not isinstance(value['decant_size'], (int, float)):
            raise serializers.ValidationError("box_configuration must contain a numeric 'decant_size'.")
        if 'decant_count' not in value or not isinstance(value['decant_count'], int):
            raise serializers.ValidationError("box_configuration must contain an integer 'decant_count'.")

        for perfume_entry in value['perfumes']:
            if not isinstance(perfume_entry, dict):
                raise serializers.ValidationError("Each item in 'perfumes' list must be a JSON object.")
            if 'perfume_id_backend' not in perfume_entry and 'external_id' not in perfume_entry :
                 raise serializers.ValidationError("Each perfume in box_configuration must have 'perfume_id_backend' or 'external_id'.")
        return value

    def validate(self, data):

        if data.get('perfume_id'):
            raise serializers.ValidationError({"perfume_id": "perfume_id is not allowed at the top level for cart items. Specify perfumes within box_configuration."})
        if data.get('decant_size'):
            raise serializers.ValidationError({"decant_size": "decant_size is not allowed at the top level. Specify decant_size within box_configuration."})

        return data

# --- Cart Serializers ---

class PerfumeSummarySerializer(serializers.ModelSerializer):
    brand = serializers.StringRelatedField()
    class Meta:
        model = Perfume
        fields = ('id', 'name', 'brand', 'thumbnail_url', 'price_per_ml', 'external_id')

class CartItemSerializer(serializers.ModelSerializer):
    perfume = PerfumeSummarySerializer(read_only=True, allow_null=True)


    class Meta:
      model = CartItem
      fields = (
        'id', 'product_type',
        'perfume',
        'quantity',
        'price_at_addition',
        'box_configuration',
        'added_at',
        'name',
      )
      read_only_fields = ('id', 'price_at_addition', 'added_at', 'perfume')

    def validate(self, data):
        product_type = data.get('product_type', getattr(self.instance, 'product_type', 'box'))

        if product_type != 'box':
            raise serializers.ValidationError({"product_type": "Only 'box' product_type is allowed in the cart."})

        box_configuration = data.get('box_configuration')
        if not box_configuration:
            raise serializers.ValidationError({"box_configuration": "Box configuration must be provided for product_type 'box'."})

        if data.get('perfume') is not None:
             raise serializers.ValidationError({"perfume": "The direct 'perfume' field should not be set for 'box' type items. Perfumes are detailed in 'box_configuration'."})

        if not data.get('name'):
            raise serializers.ValidationError({"name": "A 'name' is required for box items."})

        return data


class CartSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
      model = Cart # Use direct model import
      fields = ('id', 'user', 'items', 'created_at', 'updated_at')
      read_only_fields = ('id', 'user', 'created_at', 'updated_at', 'items')


# --- Box Serializers ---

class PredefinedBoxSerializer(serializers.ModelSerializer):
    perfumes = PerfumeSummarySerializer(many=True, read_only=True)

    class Meta:
        model = PredefinedBox
        fields = ('id', 'title', 'description', 'icon', 'gender', 'perfumes')

# --- End Box Serializers ---


# --- Subscription Serializers ---

class SubscriptionTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionTier
        fields = ('id', 'name', 'price', 'decant_size', 'perfume_criteria', 'description')
        read_only_fields = fields

class UserSubscriptionSerializer(serializers.ModelSerializer):
    tier = SubscriptionTierSerializer(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ('id', 'tier', 'start_date', 'is_active')
        read_only_fields = ('id', 'tier', 'start_date', 'is_active')

class SubscribeSerializer(serializers.Serializer):
    tier_id = serializers.PrimaryKeyRelatedField(queryset=SubscriptionTier.objects.all(), required=True)

# --- End Subscription Serializers ---


# --- Order Serializers ---

class OrderItemSerializer(serializers.ModelSerializer):
    perfume = PerfumeSummarySerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            'id', 'perfume', 'product_type', 'quantity', 'decant_size',
            'price_at_purchase', 'box_configuration', 'item_name', 'item_description'
        )
        read_only_fields = fields

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = (
            'id', 'user_email', 'order_date', 'total_price', 'status',
            'shipping_address', 'items', 'updated_at'
        )
        read_only_fields = fields

class OrderCreateSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(required=True, allow_blank=False)

# --- End Order Serializers ---


# --- Rating & Favorite Serializers ---

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    perfume = serializers.PrimaryKeyRelatedField(read_only=True)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=True)

    class Meta:
        model = Rating
        fields = ('id', 'user', 'perfume', 'rating', 'timestamp')
        read_only_fields = ('id', 'user', 'perfume', 'timestamp')

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

class FavoriteSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    perfume_id = serializers.PrimaryKeyRelatedField(
        queryset=Perfume.objects.all(), source='perfume', write_only=True
    )

    class Meta:
        model = Favorite
        fields = ('id', 'user', 'perfume_id', 'added_at')
        read_only_fields = ('id', 'user', 'added_at')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        favorite, created = Favorite.objects.get_or_create(
            user=validated_data['user'],
            perfume=validated_data['perfume'],
            defaults={}
        )
        return favorite


class FavoriteListSerializer(serializers.ModelSerializer):
    perfume = PerfumeSummarySerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ('id', 'perfume', 'added_at')
        read_only_fields = fields

# --- End Rating & Favorite Serializers ---
# --- Recommendation Serializer ---

class UserPerfumeMatchSerializer(serializers.ModelSerializer):
    perfume = PerfumeSummarySerializer(read_only=True)
    score = serializers.DecimalField(source='match_percentage', max_digits=4, decimal_places=3, read_only=True)

    class Meta:
        model = UserPerfumeMatch
        fields = ('perfume', 'score', 'last_updated')
        read_only_fields = fields

# --- End Recommendation Serializer ---

# --- Coupon Serializer ---

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            'id', 'code', 'discount_type', 'value', 'description',
            'min_purchase_amount', 'expiry_date', 'is_active',
            'max_uses', 'uses_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'uses_count', 'created_at', 'updated_at')

    def validate_code(self, value):
        return value.upper()

    def validate(self, data):
        instance = getattr(self, 'instance', None)
        discount_type = data.get('discount_type', instance.discount_type if instance else None)
        value = data.get('value', instance.value if instance else None)

        if discount_type == 'percentage':
            if not (0 < value <= 100):
                raise serializers.ValidationError({'value': 'Percentage value must be between 0 (exclusive) and 100 (inclusive).'})
        elif discount_type == 'fixed':
            if value <= 0:
                raise serializers.ValidationError({'value': 'Fixed discount value must be positive.'})

        min_purchase_amount = data.get('min_purchase_amount')
        if min_purchase_amount is not None and min_purchase_amount < 0:
            raise serializers.ValidationError({'min_purchase_amount': 'Minimum purchase amount cannot be negative.'})

        return data

# --- End Coupon Serializer ---