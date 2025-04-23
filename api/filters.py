import django_filters # Use import django_filters instead of specific imports for clarity
from .models import Perfume, UserPerfumeMatch # Import UserPerfumeMatch

class PerfumeFilter(django_filters.FilterSet):
    # Define filters for fields not handled by default or needing specific lookups
    price_min = django_filters.NumberFilter(field_name='pricePerML', lookup_expr='gte') # Corrected field name
    price_max = django_filters.NumberFilter(field_name='pricePerML', lookup_expr='lte') # Corrected field name
    season = django_filters.CharFilter(field_name='season', lookup_expr='iexact')
    best_for = django_filters.CharFilter(field_name='best_for', lookup_expr='iexact')

    # Add filters for existing fields if needed for consistency or specific lookups
    gender = django_filters.CharFilter(field_name='gender', lookup_expr='iexact')
    brand = django_filters.CharFilter(method='filter_brand', label='Brand IDs (comma-separated)') # Use CharFilter for comma-separated values
    occasions = django_filters.CharFilter(method='filter_occasions', label='Occasion IDs (comma-separated)')
    # Add filter for external_id (comma-separated)
    external_ids = django_filters.CharFilter(method='filter_external_ids', label='External IDs (comma-separated)')

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

        return queryset

    def filter_external_ids(self, queryset, name, value):
        """ Custom filter for comma-separated external IDs """
        try:
            ext_ids = [eid.strip() for eid in value.split(',') if eid.strip()]
            if ext_ids:
                return queryset.filter(external_id__in=ext_ids).distinct()
        except ValueError: # Should not happen with string IDs, but good practice
            pass
        return queryset

    class Meta:
        model = Perfume
        fields = { # Use dictionary format for more control if needed later
            'gender': ['exact', 'iexact'],
            'accords': ['exact'], # Assumes filtering by single accord ID
            'season': ['iexact'],
            'best_for': ['iexact'],
            # price_min, price_max, brand, occasions, external_ids handled by custom filters/methods
        }

# --- New FilterSet for Recommendations ---

class UserPerfumeMatchFilter(django_filters.FilterSet):
    """
    FilterSet for UserPerfumeMatch model, allowing filtering based on
    related Perfume attributes.
    """
    # Filter by related Perfume's price
    price_min = django_filters.NumberFilter(field_name='perfume__pricePerML', lookup_expr='gte') # Correct field name
    price_max = django_filters.NumberFilter(field_name='perfume__pricePerML', lookup_expr='lte') # Correct field name

    # Filter by related Perfume's occasions (comma-separated IDs)
    occasions = django_filters.CharFilter(method='filter_perfume_occasions', label='Occasion IDs (comma-separated)')

    # Filter by related Perfume's external ID (comma-separated)
    external_ids = django_filters.CharFilter(method='filter_perfume_external_ids', label='External IDs (comma-separated)')

    def filter_perfume_occasions(self, queryset, name, value):
        """ Custom filter for comma-separated occasion IDs on the related perfume """
        try:
            occasion_ids = [int(oid.strip()) for oid in value.split(',') if oid.strip()]
            if occasion_ids:
                # Filter UserPerfumeMatch where the related perfume has any of the specified occasions
                return queryset.filter(perfume__occasions__id__in=occasion_ids).distinct()
        except ValueError:
            pass # Handle potential non-integer values gracefully
        return queryset # Return original queryset if value is empty or invalid

    def filter_perfume_external_ids(self, queryset, name, value):
        """ Custom filter for comma-separated external IDs on the related perfume """
        try:
            ext_ids = [eid.strip() for eid in value.split(',') if eid.strip()]
            if ext_ids:
                 # Filter UserPerfumeMatch where the related perfume has any of the specified external IDs
                return queryset.filter(perfume__external_id__in=ext_ids).distinct()
        except ValueError: # Should not happen with string IDs
            pass
        return queryset

    class Meta:
        model = UserPerfumeMatch
        fields = [
            # 'price_min', # Handled by explicit filter definition above
            # 'price_max', # Handled by explicit filter definition above
            'occasions',
            'external_ids',
            # Add other fields from UserPerfumeMatch if direct filtering is needed
            # e.g., 'score': ['gte', 'lte']
        ]