from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    User, Brand, Occasion, Accord, Perfume, Note,
    PredefinedBox, SubscriptionTier, UserSubscription,
    Cart, CartItem, Order, OrderItem,
    Rating, Favorite, SurveyResponse, UserPerfumeMatch, SurveyQuestion,
    PerfumeAccordOrder, Coupon, # Added import Coupon
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

class CartItemInlineForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make perfume and box_configuration not required at the form widget level.
        # The clean method will enforce conditional requirement.
        if 'perfume' in self.fields:
            self.fields['perfume'].required = False
            self.fields['perfume'].help_text = "Only required for individual perfume purchases"

        if 'box_configuration' in self.fields:
            self.fields['box_configuration'].required = False
            self.fields['box_configuration'].help_text = (
                "Required for box products. JSON format with perfume details. "
                "Example: {\"perfumes\": [{\"id\": 1, \"name\": \"Chanel No. 5\", \"brand\": \"Chanel\"}], "
                "\"decantCount\": 4, \"decantSize\": 5}"
            )

        if 'name' in self.fields:
            self.fields['name'].help_text = (
                "Display name for the item (e.g., 'AI Discovery Box (4x5ml)', 'Custom Box', or perfume name)"
            )

    def clean(self):
        cleaned_data = super().clean()
        product_type = cleaned_data.get('product_type')
        perfume = cleaned_data.get('perfume')
        box_configuration = cleaned_data.get('box_configuration')
        name = cleaned_data.get('name')

        if product_type == 'perfume':
            if not perfume:
                self.add_error('perfume', 'Perfume is required when product type is "perfume".')
            if box_configuration:
                self.add_error('box_configuration', 'Box configuration must be empty when product type is "perfume".')

        elif product_type == 'box':
            if not box_configuration:
                self.add_error('box_configuration', 'Box configuration is required when product type is "box".')
            if perfume:
                self.add_error('perfume', 'Perfume must be empty when product type is "box".')
            if not name:
                self.add_error('name', 'Name is required for box products (e.g., "AI Discovery Box (4x5ml)").')

            # Validate box_configuration structure if present
            if box_configuration:
                try:
                    if isinstance(box_configuration, str):
                        import json
                        box_config = json.loads(box_configuration)
                    else:
                        box_config = box_configuration

                    # Check for required fields in box configuration
                    if 'perfumes' not in box_config:
                        self.add_error('box_configuration', 'Box configuration must include "perfumes" array.')
                    elif not isinstance(box_config['perfumes'], list) or len(box_config['perfumes']) == 0:
                        self.add_error('box_configuration', 'Box configuration must include at least one perfume.')

                except (json.JSONDecodeError, TypeError):
                    self.add_error('box_configuration', 'Box configuration must be valid JSON.')

        return cleaned_data

class CartItemInline(admin.TabularInline):
    model = CartItem
    form = CartItemInlineForm # Use the custom form
    extra = 0
    readonly_fields = ('price_at_addition',)

    def get_fields(self, request, obj=None):
        """
        Dynamically show fields based on product_type.
        For box business model, focus on box configuration rather than individual perfumes.
        """
        base_fields = ['name', 'product_type', 'quantity', 'decant_size', 'price_at_addition']

        # Only show perfume field for perfume product types
        # For boxes, show box_configuration instead
        if obj and hasattr(obj, 'product_type'):
            if obj.product_type == 'perfume':
                return base_fields[:2] + ['perfume'] + base_fields[2:]
            else:  # box type
                return base_fields[:2] + ['box_configuration'] + base_fields[2:]

        # Default: show both but box_configuration is more relevant for your business
        return base_fields[:2] + ['box_configuration', 'perfume'] + base_fields[2:]

    def get_readonly_fields(self, request, obj=None):
        """Make price_at_addition always readonly"""
        return ('price_at_addition',)

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    inlines = [CartItemInline]

import json # Import json for pretty printing

# Note: The duplicate "import json" and the django.urls/utils.html imports were consolidated at the top.
# If they were meant to be conditionally imported or had specific reasons for placement, that context is lost.
# For admin files, top-level imports are standard.

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'name', 'product_type', 'display_box_details', 'quantity', 'decant_size', 'price_at_addition', 'display_perfumes_in_box')
    search_fields = ('name', 'cart__user__email')
    list_filter = ('product_type', 'cart__user', 'decant_size')
    actions = ['convert_to_box_format']

    def display_box_details(self, obj):
        """
        Display relevant information based on product type.
        Focus on box configuration for the perfume box business model.
        """
        if obj.product_type == 'box':
            if obj.box_configuration:
                perfume_count = len(obj.box_configuration.get('perfumes', []))
                decant_count = obj.box_configuration.get('decantCount', 'N/A')
                return f"Box: {perfume_count} perfumes, {decant_count} decants"
            return "Box (No configuration)"
        elif obj.product_type == 'perfume' and obj.perfume:
            link = reverse("admin:api_perfume_change", args=[obj.perfume.pk])
            return format_html('<a href="{}">{}</a>', link, obj.perfume.name)
        return "N/A"
    display_box_details.short_description = "Box/Item Details"

    def display_perfumes_in_box(self, obj):
        """
        Show the perfumes included in a box configuration.
        This is the core information for your perfume box business.
        """
        if obj.product_type == 'box' and obj.box_configuration:
            perfumes = obj.box_configuration.get('perfumes', [])
            if perfumes:
                # Display perfume names and brands in a readable format
                perfume_list = []
                for p in perfumes[:3]:  # Show first 3 perfumes to avoid clutter
                    name = p.get('name', 'Unknown')
                    brand = p.get('brand', 'Unknown Brand')
                    perfume_list.append(f"{name} ({brand})")

                result = ", ".join(perfume_list)
                if len(perfumes) > 3:
                    result += f" + {len(perfumes) - 3} more"
                return result
            return "No perfumes in configuration"
        elif obj.product_type == 'perfume':
            return "Individual perfume (not a box)"
        return "N/A"
    display_perfumes_in_box.short_description = "Perfumes in Box"

    def get_fields(self, request, obj=None):
        """
        Show different fields based on product type to reduce confusion.
        """
        if obj and obj.product_type == 'box':
            return ('cart', 'product_type', 'name', 'box_configuration', 'quantity', 'decant_size', 'price_at_addition', 'added_at')
        elif obj and obj.product_type == 'perfume':
            return ('cart', 'product_type', 'name', 'perfume', 'quantity', 'decant_size', 'price_at_addition', 'added_at')
        else:
            # For new objects, show all fields
            return ('cart', 'product_type', 'name', 'perfume', 'box_configuration', 'quantity', 'decant_size', 'price_at_addition')

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly after creation"""
        if obj:  # Editing existing object
            return ('added_at', 'price_at_addition')
        return ('added_at',)

    def convert_to_box_format(self, request, queryset):
        """
        Admin action to help convert individual perfume items to box format.
        Useful for migrating data or fixing incorrectly categorized items.
        """
        updated_count = 0
        for item in queryset:
            if item.product_type == 'perfume' and item.perfume:
                # Convert perfume item to box format
                item.product_type = 'box'
                item.box_configuration = {
                    'perfumes': [{
                        'id': item.perfume.id,
                        'name': item.perfume.name,
                        'brand': str(item.perfume.brand),
                        'external_id': item.perfume.external_id
                    }],
                    'decantCount': 1,
                    'decantSize': item.decant_size or 5
                }
                if not item.name:
                    item.name = f"Single Perfume Box - {item.perfume.name}"
                # Clear the perfume field since it's now in box_configuration
                item.perfume = None
                item.save()
                updated_count += 1

        self.message_user(
            request,
            f"Successfully converted {updated_count} items to box format."
        )
    convert_to_box_format.short_description = "Convert selected perfume items to box format"

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

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'min_purchase_amount', 'expiry_date', 'is_active', 'uses_count', 'max_uses')
    list_filter = ('discount_type', 'is_active', 'expiry_date')
    search_fields = ('code', 'description')
    list_editable = ('is_active', 'value', 'min_purchase_amount', 'expiry_date', 'max_uses')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'value')
        }),
        ('Conditions & Limits', {
            'fields': ('min_purchase_amount', 'expiry_date', 'max_uses')
        }),
        ('Usage Tracking', {
            'fields': ('uses_count',), # uses_count is read-only usually
        }),
    )
    readonly_fields = ('uses_count', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        # Make uses_count always read-only
        # Add created_at and updated_at for existing objects
        if obj: # when editing an object
            return self.readonly_fields + ('created_at', 'updated_at')
        return self.readonly_fields
