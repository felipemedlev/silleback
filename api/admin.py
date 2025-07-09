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
    PerfumeAccordOrder, Coupon,
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'phone', 'address', 'is_active', 'is_staff', 'date_joined', 'view_matches_link')

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

        instance = kwargs.get('instance')

        if 'product_type' in self.fields:
            self.fields['product_type'].initial = 'box'
            self.fields['product_type'].disabled = True

        if 'perfume' in self.fields:
            self.fields['perfume'].required = False
            self.fields['perfume'].widget = forms.HiddenInput()
            self.fields['perfume'].help_text = ""

        if 'box_configuration' in self.fields:
            self.fields['box_configuration'].required = True
            self.fields['box_configuration'].help_text = (
                "Required. JSON format with perfume details. "
                "Example: {\"perfumes\": [{\"perfume_id_backend\": 1, \"name\": \"Chanel No. 5\"}], "
                "\"decant_count\": 4, \"decant_size\": 5}"
            )

        if 'decant_size' in self.fields:
            self.fields['decant_size'].required = False
            self.fields['decant_size'].widget = forms.HiddenInput()
            self.fields['decant_size'].help_text = "Decant size is specified within the Box Configuration."

        if 'name' in self.fields:
            self.fields['name'].required = True
            self.fields['name'].help_text = (
                "Required. Display name for the box (e.g., 'AI Discovery Box (4x5ml)')"
            )

        if 'quantity' in self.fields:
            self.fields['quantity'].initial = 1
            self.fields['quantity'].disabled = True
            self.fields['quantity'].help_text = "Quantity is always 1 for each unique box."


    def clean(self):
        cleaned_data = super().clean()
        product_type = cleaned_data.get('product_type')
        perfume = cleaned_data.get('perfume')
        box_configuration = cleaned_data.get('box_configuration')
        name = cleaned_data.get('name')

        if product_type != 'box':
            self.add_error('product_type', 'Product type must be "box".')
            cleaned_data['product_type'] = 'box'


        if not box_configuration:
            self.add_error('box_configuration', 'Box configuration is required.')
        if perfume:
            self.add_error('perfume', 'Perfume (direct link) must be empty for box items. Perfumes are in box_configuration.')
            cleaned_data['perfume'] = None
        if not name:
            self.add_error('name', 'Name is required for box products (e.g., "AI Discovery Box (4x5ml)").')

        if box_configuration:
            try:
                if isinstance(box_configuration, str):
                    import json
                    box_config = json.loads(box_configuration)
                else:
                    box_config = box_configuration

                if not isinstance(box_config, dict):
                    raise TypeError("Box configuration is not a dictionary.")

                if 'perfumes' not in box_config or not isinstance(box_config['perfumes'], list) or not box_config['perfumes']:
                    self.add_error('box_configuration', 'Box configuration must include a non-empty "perfumes" array.')
                else:
                    for p_entry in box_config['perfumes']:
                        if not isinstance(p_entry, dict) or ('perfume_id_backend' not in p_entry and 'external_id' not in p_entry):
                             self.add_error('box_configuration', "Each perfume in box_configuration must be an object with 'perfume_id_backend' or 'external_id'.")
                if 'decant_size' not in box_config or not isinstance(box_config['decant_size'], (int, float)):
                    self.add_error('box_configuration', 'Box configuration must include a numeric "decant_size".')
                if 'decant_count' not in box_config or not isinstance(box_config['decant_count'], int):
                     self.add_error('box_configuration', 'Box configuration must include an integer "decant_count".')


            except (json.JSONDecodeError, TypeError) as e:
                self.add_error('box_configuration', f'Box configuration must be valid JSON and structured correctly. Error: {e}')

        if cleaned_data.get('decant_size') is not None:
            cleaned_data['decant_size'] = None


        return cleaned_data

class CartItemInline(admin.TabularInline):
    model = CartItem
    form = CartItemInlineForm
    extra = 0
    readonly_fields = ('price_at_addition',)

    fields = (
        'name',
        'box_configuration',
        'price_at_addition'
    )

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    inlines = [CartItemInline]

import json

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'name', 'product_type', 'display_box_summary', 'display_decant_size_from_config', 'display_box_price', 'display_perfumes_in_box')
    search_fields = ('name', 'cart__user__email', 'box_configuration')
    list_filter = ('cart__user', 'product_type')

    def display_box_price(self, obj):
        """
        Displays 'Box Price' for box items.
        """
        if obj.product_type == 'box' and obj.price_at_addition is not None:
            price_str = "{:.2f}".format(obj.price_at_addition)
            return format_html("<strong>Box Price:</strong> ${}", price_str)
        return "N/A"
    display_box_price.short_description = "Box Price"

    def display_box_summary(self, obj):
        """
        Display summary of the box configuration.
        """
        if obj.product_type == 'box':
            if obj.box_configuration:
                perfume_count = len(obj.box_configuration.get('perfumes', []))
                decant_count_conf = obj.box_configuration.get('decant_count', 'N/A')
                decant_size_conf = obj.box_configuration.get('decant_size', 'N/A')
                return f"Box: {perfume_count} perfumes ({decant_count_conf} x {decant_size_conf}ml)"
            return "Box (No configuration)"
        return "N/A (Not a Box)"
    display_box_summary.short_description = "Box Summary"

    def display_decant_size_from_config(self, obj):
        """
        Displays the decant_size from the box_configuration.
        """
        if obj.product_type == 'box' and obj.box_configuration:
            decant_size = obj.box_configuration.get('decant_size')
            if decant_size is not None:
                return f"{decant_size}ml"
            return "N/A in config"
        return "N/A"
    display_decant_size_from_config.short_description = "Decant Size (Box)"

    def display_perfumes_in_box(self, obj):
        """
        Show the perfumes included in a box configuration.
        """
        if obj.product_type == 'box' and obj.box_configuration:
            perfumes = obj.box_configuration.get('perfumes', [])
            if perfumes:
                perfume_list = []
                for p in perfumes[:3]:
                    name = p.get('name', p.get('perfume_name', 'Unknown Perfume'))
                    perfume_list.append(f"{name}")


                result = ", ".join(perfume_list)
                if len(perfumes) > 3:
                    result += f" + {len(perfumes) - 3} more"
                return result
            return "No perfumes in configuration"
        return "N/A (Not a Box)"
    display_perfumes_in_box.short_description = "Perfumes in Box"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not obj:
            form.base_fields['product_type'].initial = 'box'
            form.base_fields['product_type'].widget.attrs['disabled'] = True
        elif obj and obj.product_type != 'box':
             obj.product_type = 'box'
        return form


    def get_fields(self, request, obj=None):
        """
        Always show fields relevant for a 'box' type item.
        """
        return ('cart', 'product_type', 'name', 'box_configuration', 'price_at_addition')


        def get_readonly_fields(self, request, obj=None):
            """Make certain fields readonly."""
            ro_fields = ['added_at', 'price_at_addition', 'quantity']

            if obj:
                ro_fields.append('product_type')

            return tuple(ro_fields)

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
            'fields': ('uses_count',),
        }),
    )
    readonly_fields = ('uses_count', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('created_at', 'updated_at')
        return self.readonly_fields
