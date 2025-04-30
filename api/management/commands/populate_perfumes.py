# api/management/commands/populate_perfumes.py

import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from api.models import Perfume, Brand, Accord, Occasion, Note, PerfumeAccordOrder # Import Note and PerfumeAccordOrder models
import json # For parsing list-like strings if needed
from decimal import Decimal, InvalidOperation # For helper method

class Command(BaseCommand):
    help = 'Populates the database with perfume data from a specified CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file_path', type=str, help='The path to the CSV file containing perfume data.')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file_path']
        self.stdout.write(self.style.SUCCESS(f'Starting perfume data population from: {csv_file_path}'))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        try:
            # Ensure the parent directories exist (needed for write_to_file)
            import os
            os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

            with open(csv_file_path, mode='r', encoding='utf-8') as csvfile: # Specify encoding
                reader = csv.DictReader(csvfile)
                # Check required headers (adjust based on final CSV)
                # Assuming these are the exact headers in your CSV
                required_headers = [
                    'Name', 'Perfume ID', 'Brand Name', 'Gender', 'overall rating',
                    'rating count', 'main accords', 'top notes', 'middle notes',
                    'base notes', 'description', 'Occasions', 'price_per_ml',
                    'thumbnail_url', 'full_size_url', 'season', 'best_for',
                    'country_origin', 'year_released', 'similar perfumes',
                    'recommended perfumes', 'longevity', 'sillage', 'price for value',
                    'Recent Magnitude' # Added popularity source header
                ]
                # Check if all required headers are present in the CSV file
                csv_headers = set(reader.fieldnames)
                missing_headers = [h for h in required_headers if h not in csv_headers]
                if missing_headers:
                    raise CommandError(f"CSV file is missing required headers: {', '.join(missing_headers)}")

                with transaction.atomic(): # Wrap in a transaction for efficiency and safety
                    for row_num, row in enumerate(reader, start=1):
                        try:
                            # --- Data Cleaning and Preparation ---
                            external_id = row.get('Perfume ID', '').strip()
                            if not external_id:
                                self.stdout.write(self.style.WARNING(f'Skipping row {row_num}: Missing Perfume ID.'))
                                skipped_count += 1
                                continue

                            brand_name = row.get('Brand Name', '').strip()
                            if not brand_name:
                                self.stdout.write(self.style.WARNING(f'Skipping row {row_num} (ID: {external_id}): Missing Brand Name.'))
                                skipped_count += 1
                                continue

                            # Get or create Brand
                            brand, _ = Brand.objects.get_or_create(name=brand_name)

                            # Prepare notes lists
                            top_notes_list = self.parse_list_string(row.get('top notes', ''))
                            middle_notes_list = self.parse_list_string(row.get('middle notes', ''))
                            base_notes_list = self.parse_list_string(row.get('base notes', ''))

                            # Prepare relationship IDs JSON
                            similar_ids = self.parse_list_string(row.get('similar perfumes', ''))
                            recommended_ids = self.parse_list_string(row.get('recommended perfumes', ''))

                            # Prepare nullable fields
                            year_released = self.to_int_or_none(row.get('year_released'))
                            overall_rating = self.to_float_or_none(row.get('overall rating'))
                            rating_count = self.to_int_or_none(row.get('rating count'), default=0)
                            price_per_ml = self.to_decimal_or_none(row.get('price_per_ml'))
                            longevity = self.to_float_or_none(row.get('longevity'))
                            sillage = self.to_float_or_none(row.get('sillage'))
                            price_value = self.to_float_or_none(row.get('price for value'))
                            popularity = self.to_int_or_none(row.get('Recent Magnitude'), default=0) # Parse popularity
                            gender_raw = row.get('Gender', '').lower().strip() or None
                            season_raw = row.get('season', '').lower().strip() or None
                            best_for_raw = row.get('best_for', '').lower().strip() or None

                            # --- Create or Update Perfume ---
                            perfume_data = {
                                'name': row.get('Name', '').strip(),
                                'brand': brand,
                                'description': row.get('description', '').strip() or None,
                                # 'top_notes': top_notes_list, # Removed - Handled via M2M below
                                # 'middle_notes': middle_notes_list, # Removed - Handled via M2M below
                                # 'base_notes': base_notes_list, # Removed - Handled via M2M below
                                'price_per_ml': price_per_ml,
                                'thumbnail_url': row.get('thumbnail_url', '').strip() or None,
                                'full_size_url': row.get('full_size_url', '').strip() or None,
                                'gender': gender_raw if gender_raw in ['male', 'female', 'unisex'] else None,
                                'season': season_raw if season_raw in ['winter', 'summer', 'autumn', 'spring'] else None,
                                'best_for': best_for_raw if best_for_raw in ['day', 'night'] else None,
                                'country_origin': row.get('country_origin', '').strip() or None,
                                'year_released': year_released,
                                'overall_rating': overall_rating,
                                'rating_count': rating_count,
                                'longevity_rating': longevity,
                                'sillage_rating': sillage,
                                'price_value_rating': price_value,
                                'popularity': popularity, # Add popularity field
                                'similar_perfume_ids': similar_ids,
                                'recommended_perfume_ids': recommended_ids,
                            }
                            # Remove None values for fields that shouldn't be explicitly set to None if blank in CSV,
                            # except for JSON fields which default to list
                            perfume_data = {k: v for k, v in perfume_data.items() if v is not None or k in ['similar_perfume_ids', 'recommended_perfume_ids']} # Removed note fields


                            perfume, created = Perfume.objects.update_or_create(
                                external_id=external_id,
                                defaults=perfume_data
                            )

                            # --- Handle ManyToMany Relationships ---
                            # Accords - Use through model to preserve order
                            accord_names = self.parse_list_string(row.get('main accords', ''))
                            # Clear existing ordered relationships for this perfume first
                            PerfumeAccordOrder.objects.filter(perfume=perfume).delete()
                            for index, name in enumerate(accord_names):
                                if name:
                                    accord, _ = Accord.objects.get_or_create(name=name.strip())
                                    # Create the through model instance with the order
                                    PerfumeAccordOrder.objects.create(perfume=perfume, accord=accord, order=index)

                            # Occasions
                            occasion_names = self.parse_list_string(row.get('Occasions', ''))
                            perfume.occasions.clear() # Clear existing before adding new ones
                            for name in occasion_names:
                                if name:
                                    occasion, _ = Occasion.objects.get_or_create(name=name.strip())
                                    perfume.occasions.add(occasion)

                            if created:
                                created_count += 1
                            else:
                                updated_count += 1

                            if (created_count + updated_count) % 100 == 0: # Log progress
                                self.stdout.write(f'Processed {created_count + updated_count} perfumes...')

                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'Error processing row {row_num} (ID: {external_id}): {e}'))
                            skipped_count += 1
                            # Optionally re-raise if you want the whole transaction to fail on one error
                            # raise e

        except FileNotFoundError:
            raise CommandError(f'Error: CSV file not found at "{csv_file_path}"')
        except Exception as e:
            raise CommandError(f'An unexpected error occurred: {e}')

        self.stdout.write(self.style.SUCCESS(f'Finished population.'))
        self.stdout.write(f'Created: {created_count}')
        self.stdout.write(f'Updated: {updated_count}')
        self.stdout.write(f'Skipped: {skipped_count}')

    # --- Helper Methods ---
    def parse_list_string(self, list_str):
        """ Parses a string representation of a list (e.g., "['a', 'b', 'c']" or "a, b, c") into a Python list. """
        if not list_str or not isinstance(list_str, str):
            return []
        list_str = list_str.strip()
        # Handle potential 'nan' strings or similar non-list values
        if list_str.lower() in ['nan', 'none', 'null', '']:
             return []
        try:
            # Try parsing as a literal Python list representation
            # Be careful with eval, but necessary for ['a','b'] format. Ensure input is trusted.
            # Using json.loads is safer if format is guaranteed JSON-like "[\"a\", \"b\"]"
            # Let's try json first, then fallback or split
            try:
                # Assume JSON standard double quotes or handle single quotes
                parsed_list = json.loads(list_str.replace("'", '"'))
                if isinstance(parsed_list, list):
                    return [str(item).strip() for item in parsed_list if item]
            except json.JSONDecodeError:
                 # If not JSON, assume comma-separated or potentially list literal
                 if list_str.startswith('[') and list_str.endswith(']'):
                     # Attempt to parse list literal carefully
                     content = list_str[1:-1].strip()
                     if not content: return []
                     # Split by comma, handling potential quotes around items
                     items = []
                     in_quotes = False
                     current_item = ''
                     for char in content:
                         if char == "'" or char == '"':
                             in_quotes = not in_quotes
                         elif char == ',' and not in_quotes:
                             items.append(current_item.strip().strip("'\""))
                             current_item = ''
                         else:
                             current_item += char
                     items.append(current_item.strip().strip("'\"")) # Add last item
                     return [item for item in items if item]

                 else: # Fallback: Try splitting by comma
                    return [item.strip() for item in list_str.split(',') if item.strip()]

        except Exception: # Catch broad exceptions during parsing
            # Log or handle specific parsing errors if needed
            return [] # Return empty list if parsing fails
        return [] # Default empty list

    def to_int_or_none(self, value, default=None):
        """ Converts a value to int, returning None if conversion fails. """
        if value is None or value == '' or str(value).lower() == 'nan':
            return default
        try:
            return int(float(value)) # Use float first to handle "1.0" etc.
        except (ValueError, TypeError):
            return default

    def to_float_or_none(self, value, default=None):
        """ Converts a value to float, returning None if conversion fails. """
        if value is None or value == '' or str(value).lower() == 'nan':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def to_decimal_or_none(self, value, default=None):
        """ Converts a value to Decimal, returning None if conversion fails. """
        if value is None or value == '' or str(value).lower() == 'nan':
            return default
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            return default