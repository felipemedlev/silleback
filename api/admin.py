from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Brand, Occasion, Accord, Perfume,
    PredefinedBox, SubscriptionTier, UserSubscription,
    Cart, CartItem, Order, OrderItem,
    Rating, Favorite, SurveyResponse, UserPerfumeMatch
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'username')
    ordering = ('email',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Occasion)
class OccasionAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Accord)
class AccordAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'gender', 'pricePerML')
    search_fields = ('name', 'brand__name')
    list_filter = ('gender', 'brand')
    filter_horizontal = ('accords', 'occasions')

@admin.register(PredefinedBox)
class PredefinedBoxAdmin(admin.ModelAdmin):
    list_display = ('title', 'gender')
    search_fields = ('title', 'description')
    filter_horizontal = ('perfumes',)

@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'decant_size')
    search_fields = ('name',)

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'tier', 'is_active', 'start_date')
    search_fields = ('user__email', 'tier__name')

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    inlines = [CartItemInline]

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product_type', 'perfume', 'quantity', 'decant_size', 'price_at_addition')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'order_date', 'total_price', 'status')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'perfume', 'product_type', 'quantity', 'decant_size', 'price_at_purchase')

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'perfume', 'rating', 'timestamp')
    search_fields = ('user__email', 'perfume__name')

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'perfume', 'added_at')
    search_fields = ('user__email', 'perfume__name')

@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'completed_at')

@admin.register(UserPerfumeMatch)
class UserPerfumeMatchAdmin(admin.ModelAdmin):
    list_display = ('user', 'perfume', 'match_percentage', 'last_updated')
    search_fields = ('user__email', 'perfume__name')
