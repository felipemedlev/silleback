from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    User, Brand, Occasion, Accord, Perfume, Note,
    PredefinedBox, SubscriptionTier, UserSubscription,
    Cart, CartItem, Order, OrderItem,
    Rating, Favorite, SurveyResponse, UserPerfumeMatch, SurveyQuestion,
    PerfumeAccordOrder, # Added import
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'phone', 'address', 'is_active', 'is_staff', 'date_joined', 'view_matches_link') # Added link

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone', 'address'),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('phone', 'address'),
        }),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)

    def view_matches_link(self, obj):
        """
        Generates a link to the filtered UserPerfumeMatch admin page for this user.
        """
        count = UserPerfumeMatch.objects.filter(user=obj).count()
        if count == 0:
            return "No matches"

        url = (
            reverse("admin:api_userperfumematch_changelist")
            + f"?user__id__exact={obj.pk}"
        )
        return format_html('<a href="{}">View {} Matches</a>', url, count)

    view_matches_link.short_description = "Perfume Matches"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Occasion)
class OccasionAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Accord)
class AccordAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'gender', 'price_per_ml')
    search_fields = ('name', 'brand__name')
    list_filter = ('gender', 'brand')
    filter_horizontal = ('occasions', 'top_notes', 'middle_notes', 'base_notes')

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


@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question_type', 'accord', 'order', 'is_active')
    list_filter = ('question_type', 'is_active')
    search_fields = ('text', 'accord__name')
    list_editable = ('order', 'is_active')
    ordering = ('order',)

    fieldsets = (
        (None, {
            'fields': ('text', 'question_type', 'order', 'is_active')
        }),
        ('Type Specific', {
            'fields': ('accord', 'options'),
            'description': "Fill 'accord' if type is 'accord'. Fill 'options' (as JSON) if type is 'gender'."
        }),
    )

    # Optional: Add validation or custom logic if needed
    # def clean(self): ...


# Added registration
@admin.register(PerfumeAccordOrder)
class PerfumeAccordOrderAdmin(admin.ModelAdmin):
    list_display = ('perfume', 'accord', 'order')
    list_filter = ('perfume', 'accord')
    search_fields = ('perfume__name', 'accord__name')
    ordering = ('perfume', 'order')
