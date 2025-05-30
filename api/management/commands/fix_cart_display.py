from django.core.management.base import BaseCommand
from api.models import CartItem


class Command(BaseCommand):
    help = 'Fix cart item display for perfume box business model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes',
        )
        parser.add_argument(
            '--convert-perfumes',
            action='store_true',
            help='Convert individual perfume items to box format',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        convert_perfumes = options['convert_perfumes']

        self.stdout.write(
            self.style.SUCCESS('Analyzing cart items for perfume box business model...')
        )

        # Get all cart items
        all_items = CartItem.objects.all()
        perfume_items = all_items.filter(product_type='perfume')
        box_items = all_items.filter(product_type='box')

        self.stdout.write(f"Total cart items: {all_items.count()}")
        self.stdout.write(f"Individual perfume items: {perfume_items.count()}")
        self.stdout.write(f"Box items: {box_items.count()}")

        # Analyze box items without proper configuration
        box_items_without_config = box_items.filter(box_configuration__isnull=True)
        if box_items_without_config.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Found {box_items_without_config.count()} box items without configuration"
                )
            )

        # Analyze perfume items that might need conversion
        perfume_items_with_perfume = perfume_items.filter(perfume__isnull=False)
        if perfume_items_with_perfume.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Found {perfume_items_with_perfume.count()} individual perfume items"
                )
            )

        if convert_perfumes and perfume_items_with_perfume.exists():
            self.stdout.write("Converting individual perfume items to box format...")

            converted_count = 0
            for item in perfume_items_with_perfume:
                if dry_run:
                    self.stdout.write(
                        f"Would convert: {item.perfume.name} (Cart: {item.cart.id})"
                    )
                else:
                    # Convert to box format
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

                    # Clear the perfume field
                    item.perfume = None
                    item.save()

                    self.stdout.write(f"Converted: {item.name}")

                converted_count += 1

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Dry run complete. Would convert {converted_count} items."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully converted {converted_count} items to box format."
                    )
                )

        # Show recommendations
        self.stdout.write("\n" + "="*50)
        self.stdout.write("RECOMMENDATIONS FOR PERFUME BOX BUSINESS:")
        self.stdout.write("="*50)

        if perfume_items_with_perfume.exists():
            self.stdout.write(
                "• Consider converting individual perfume items to box format using --convert-perfumes"
            )

        self.stdout.write(
            "• Focus on box configurations in the admin panel"
        )
        self.stdout.write(
            "• Use the 'Box/Item Details' and 'Perfumes in Box' columns to manage your inventory"
        )
        self.stdout.write(
            "• The admin panel now hides irrelevant perfume fields for box items"
        )