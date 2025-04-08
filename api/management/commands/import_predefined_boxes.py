import json
from django.core.management.base import BaseCommand, CommandError
from api.models import PredefinedBox, Perfume
from django.db import transaction

class Command(BaseCommand):
    help = 'Import predefined boxes from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file_path', type=str, help='Path to predefined_boxes.json')

    def handle(self, *args, **options):
        json_file_path = options['json_file_path']
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                boxes_data = json.load(f)
        except Exception as e:
            raise CommandError(f"Error reading JSON file: {e}")

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for box in boxes_data:
                title = box.get('title')
                description = box.get('description', '')
                icon = box.get('icon', '')
                gender_raw = box.get('gender', '').lower()
                # Map 'male'/'female' to model choices
                gender = 'masculino' if gender_raw == 'male' else 'femenino' if gender_raw == 'female' else None
                perfume_ids = box.get('perfumes', [])

                if not title:
                    self.stdout.write(self.style.WARNING('Skipping box with missing title'))
                    continue

                predefined_box, created = PredefinedBox.objects.get_or_create(
                    title=title,
                    defaults={
                        'description': description,
                        'icon': icon,
                        'gender': gender,
                    }
                )
                if not created:
                    # Update existing
                    predefined_box.description = description
                    predefined_box.icon = icon
                    predefined_box.gender = gender
                    predefined_box.save()
                    updated_count += 1
                else:
                    created_count += 1

                # Clear existing perfumes
                predefined_box.perfumes.clear()

                # Add perfumes by ID
                perfumes_found = 0
                for pid in perfume_ids:
                    try:
                        perfume = Perfume.objects.get(external_id=str(pid))
                        predefined_box.perfumes.add(perfume)
                        perfumes_found += 1
                    except Perfume.DoesNotExist:
                        try:
                            perfume = Perfume.objects.get(id=pid)
                            predefined_box.perfumes.add(perfume)
                            perfumes_found += 1
                        except Perfume.DoesNotExist:
                            self.stdout.write(self.style.WARNING(f"Perfume ID {pid} not found for box '{title}'"))

                self.stdout.write(f"Box '{title}': {perfumes_found}/{len(perfume_ids)} perfumes linked.")

        self.stdout.write(self.style.SUCCESS(f"Import complete. Created: {created_count}, Updated: {updated_count}"))