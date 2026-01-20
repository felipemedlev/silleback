"""
Django management command to reclassify all perfumes' occasions based on their accords.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Perfume, Occasion
from api.utils.occasion_classifier import AccordOccasionClassifier
from collections import Counter


class Command(BaseCommand):
    help = 'Reclassify all perfumes occasions based on their accords'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making any database modifications',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of perfumes to process (useful for testing)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each perfume',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        verbose = options['verbose']

        classifier = AccordOccasionClassifier(
            min_occasions=1,
            max_occasions=3,
            score_threshold=4.0
        )

        # Get all perfumes with their accords
        perfumes = Perfume.objects.prefetch_related('accords', 'occasions').all()

        if limit:
            perfumes = perfumes[:limit]
            self.stdout.write(self.style.WARNING(f'Processing only {limit} perfumes (limit applied)'))

        total_perfumes = perfumes.count()
        self.stdout.write(f'Processing {total_perfumes} perfumes...\n')

        # Statistics tracking
        before_stats = Counter()
        after_stats = Counter()
        occasions_per_perfume_before = []
        occasions_per_perfume_after = []

        changes = []  # List of (perfume, old_occasions, new_occasions)

        for perfume in perfumes:
            # Get current occasions
            current_occasions = list(perfume.occasions.values_list('name', flat=True))
            occasions_per_perfume_before.append(len(current_occasions))
            for occ in current_occasions:
                before_stats[occ] += 1

            # Get ordered accords for this perfume
            ordered_accords = perfume.get_ordered_accords()
            accords_with_positions = [
                (accord.name, idx)
                for idx, accord in enumerate(ordered_accords[:5])  # Use top 5 accords
            ]

            # Classify based on accords
            new_occasion_names = classifier.classify_perfume(accords_with_positions)
            occasions_per_perfume_after.append(len(new_occasion_names))
            for occ in new_occasion_names:
                after_stats[occ] += 1

            # Track changes
            if set(current_occasions) != set(new_occasion_names):
                changes.append((perfume, current_occasions, new_occasion_names))

            if verbose:
                accord_names = [acc.name for acc in ordered_accords[:3]]
                self.stdout.write(
                    f'{perfume.name[:40]:40} | '
                    f'Accords: {", ".join(accord_names):30} | '
                    f'Before: {len(current_occasions)} | '
                    f'After: {len(new_occasion_names)}'
                )

        # Display statistics
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('\nSTATISTICS SUMMARY'))
        self.stdout.write('='*80 + '\n')

        avg_before = sum(occasions_per_perfume_before) / len(occasions_per_perfume_before) if occasions_per_perfume_before else 0
        avg_after = sum(occasions_per_perfume_after) / len(occasions_per_perfume_after) if occasions_per_perfume_after else 0

        self.stdout.write(f'Total perfumes processed: {total_perfumes}')
        self.stdout.write(f'Perfumes with changes: {len(changes)} ({len(changes)/total_perfumes*100:.1f}%)')
        self.stdout.write(f'\nAverage occasions per perfume:')
        self.stdout.write(f'  Before: {avg_before:.2f}')
        self.stdout.write(f'  After:  {avg_after:.2f}')
        self.stdout.write(f'  Change: {avg_after - avg_before:+.2f}')

        self.stdout.write('\n' + '-'*80)
        self.stdout.write('OCCASION DISTRIBUTION')
        self.stdout.write('-'*80)
        self.stdout.write(f'{"Occasion":<15} {"Before":<20} {"After":<20} {"Change"}')
        self.stdout.write('-'*80)

        all_occasions = set(before_stats.keys()) | set(after_stats.keys())
        for occasion in sorted(all_occasions):
            before_count = before_stats.get(occasion, 0)
            after_count = after_stats.get(occasion, 0)
            before_pct = before_count / total_perfumes * 100 if total_perfumes > 0 else 0
            after_pct = after_count / total_perfumes * 100 if total_perfumes > 0 else 0
            change = after_count - before_count

            self.stdout.write(
                f'{occasion:<15} '
                f'{before_count:>5} ({before_pct:>5.1f}%)    '
                f'{after_count:>5} ({after_pct:>5.1f}%)    '
                f'{change:+>5}'
            )

        # Show sample changes
        if changes and not verbose:
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('SAMPLE CHANGES (first 10)')
            self.stdout.write('-'*80)
            for perfume, old_occs, new_occs in changes[:10]:
                accord_names = [acc.name for acc in perfume.get_ordered_accords()[:3]]
                self.stdout.write(f'\n{perfume.name}')
                self.stdout.write(f'  Accords: {", ".join(accord_names)}')
                self.stdout.write(f'  Before:  {", ".join(old_occs) if old_occs else "None"}')
                self.stdout.write(f'  After:   {", ".join(new_occs)}')

        # Apply changes if not dry run
        if not dry_run:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.WARNING('APPLYING CHANGES TO DATABASE...'))

            with transaction.atomic():
                # Get or create all occasion objects
                occasion_objects = {}
                for occasion_name in all_occasions:
                    occasion_objects[occasion_name], _ = Occasion.objects.get_or_create(name=occasion_name)

                # Update each perfume
                update_count = 0
                for perfume, old_occasions, new_occasions in changes:
                    # Clear existing occasions
                    perfume.occasions.clear()

                    # Add new occasions
                    for occasion_name in new_occasions:
                        perfume.occasions.add(occasion_objects[occasion_name])

                    update_count += 1

                    if update_count % 100 == 0:
                        self.stdout.write(f'  Updated {update_count}/{len(changes)} perfumes...')

                self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully updated {update_count} perfumes!'))
        else:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made to the database'))
            self.stdout.write('Run without --dry-run to apply these changes')
            self.stdout.write('='*80)
