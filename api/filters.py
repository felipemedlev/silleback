import django_filters
from .models import Perfume

class PerfumeFilter(django_filters.FilterSet):
    # Define filters for fields not handled by default or needing specific lookups
    # pricePerML = django_filters.RangeFilter() # Replaced with explicit min/max filters below
    price_min = django_filters.NumberFilter(field_name='pricePerML', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='pricePerML', lookup_expr='lte')
    season = django_filters.CharFilter(field_name='season', lookup_expr='iexact') # Case-insensitive exact match
    best_for = django_filters.CharFilter(field_name='best_for', lookup_expr='iexact') # Case-insensitive exact match

    # Add filters for existing fields if needed for consistency or specific lookups
    # gender = django_filters.CharFilter(field_name='gender', lookup_expr='iexact')
    # brand = django_filters.NumberFilter(field_name='brand_id') # Filter by brand ID
    # occasions = django_filters.NumberFilter(field_name='occasions__id') # Filter by occasion ID

    class Meta:
        model = Perfume
        fields = [
            'gender',       # Keep existing filter
            'brand',        # Keep existing filter (will filter by ID)
            'occasions',    # Keep existing filter (will filter by ID)
            'accords',      # Keep existing filter (will filter by ID)
            'season',       # Add season filter
            'best_for',     # Add best_for filter
            # 'pricePerML', # Removed, using price_min and price_max instead
            'price_min',
            'price_max',
        ]