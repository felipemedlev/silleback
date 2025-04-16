from django_filters import FilterSet, NumberFilter, CharFilter, BaseInFilter, Filter
from .models import Perfume

class PerfumeFilter(FilterSet): # Use imported FilterSet
    # Define filters for fields not handled by default or needing specific lookups
    # pricePerML = django_filters.RangeFilter() # Replaced with explicit min/max filters below
    price_min = NumberFilter(field_name='pricePerML', lookup_expr='gte') # Use imported NumberFilter
    price_max = NumberFilter(field_name='pricePerML', lookup_expr='lte') # Use imported NumberFilter
    season = CharFilter(field_name='season', lookup_expr='iexact') # Use imported CharFilter
    best_for = CharFilter(field_name='best_for', lookup_expr='iexact') # Use imported CharFilter

    # Add filters for existing fields if needed for consistency or specific lookups
    # gender = CharFilter(field_name='gender', lookup_expr='iexact') # Example if needed explicitly
    brand = Filter(method='filter_brand', label='Brand IDs (comma-separated)') # Use base Filter
    occasions = CharFilter(method='filter_occasions', label='Occasion IDs (comma-separated)')

    def filter_brand(self, queryset, name, value):
        """ Custom filter for comma-separated brand IDs """
        try:
            brand_ids = [int(bid.strip()) for bid in value.split(',') if bid.strip()]
            if brand_ids:
                # Use distinct() to avoid duplicates if a perfume matches multiple occasions but only one brand
                return queryset.filter(brand__id__in=brand_ids).distinct()
        except ValueError:
            # Handle cases where value is not a valid list of integers
            pass # Or return queryset.none() or raise ValidationError
        return queryset # Return original queryset if value is empty or invalid

    def filter_occasions(self, queryset, name, value):
        """ Custom filter for comma-separated occasion IDs """
        try:
            occasion_ids = [int(oid.strip()) for oid in value.split(',') if oid.strip()]
            if occasion_ids:
                # Use distinct() to avoid duplicates if a perfume matches multiple occasions
                return queryset.filter(occasions__id__in=occasion_ids).distinct()
        except ValueError:
            pass
        return queryset

    class Meta:
        model = Perfume
        fields = [
            'gender',       # Keep existing filter
# Removed 'brand' and 'occasions' as they are now explicitly defined above
            'accords',      # Keep existing filter (will filter by ID)
            'season',       # Add season filter
            'best_for',     # Add best_for filter
            # 'pricePerML', # Removed, using price_min and price_max instead
            'price_min',
            'price_max',
        ]