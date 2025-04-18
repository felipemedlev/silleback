from django.core.management.base import BaseCommand
from api.models import Perfume, Note
from django.db import transaction


class Command(BaseCommand):
    help = 'Migrates perfume notes from JSON fields to ManyToMany relationships'

    def handle(self, *args, **options):
        # First, ensure the directory exists
        self.stdout.write(self.style.NOTICE('Starting notes migration...'))

        # Get counts for reporting
        perfume_count = Perfume.objects.count()
        self.stdout.write(f'Found {perfume_count} perfumes to process')

        # Use a transaction to ensure data integrity
        with transaction.atomic():
            # Process each note type
            note_mappings = {
                'top_notes': 'top_notes_m2m',
                'middle_notes': 'middle_notes_m2m',
                'base_notes': 'base_notes_m2m'
            }

            # Create a dictionary to cache note instances
            note_cache = {}

            # Process each perfume
            for perfume in Perfume.objects.all():
                for json_field, m2m_field in note_mappings.items():
                    # Get the notes from the JSON field
                    note_list = getattr(perfume, json_field)

                    # Skip if no notes
                    if not note_list:
                        continue

                    # Process each note
                    for note_name in note_list:
                        # Skip empty notes
                        if not note_name or note_name.strip() == '':
                            continue

                        # Clean up note name
                        note_name = note_name.strip()

                        # Get or create the note object (use cache for efficiency)
                        if note_name not in note_cache:
                            note_obj, created = Note.objects.get_or_create(name=note_name)
                            note_cache[note_name] = note_obj
                            if created:
                                self.stdout.write(f'Created new note: {note_name}')
                        else:
                            note_obj = note_cache[note_name]

                        # Add the note to the appropriate M2M relation
                        getattr(perfume, m2m_field).add(note_obj)

            self.stdout.write(self.style.SUCCESS(f'Migrated all notes for all perfumes'))

        self.stdout.write(self.style.SUCCESS('Notes migration completed successfully!'))