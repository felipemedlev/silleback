from django.core.management.base import BaseCommand
from api.models import OrderItem, Perfume


class Command(BaseCommand):
    help = 'Fix order item box configurations to use actual external_ids instead of database IDs'

    def handle(self, *args, **options):
        # Find all order items with box configurations
        order_items = OrderItem.objects.filter(
            product_type='box',
            box_configuration__isnull=False
        )

        fixed_count = 0
        for order_item in order_items:
            if 'perfumes' in order_item.box_configuration:
                fixed_perfumes = []
                needs_fix = False

                for perfume_data in order_item.box_configuration['perfumes']:
                    if 'external_id' in perfume_data:
                        try:
                            # Try to get perfume by the external_id value (which might be a database ID)
                            db_id = perfume_data['external_id']
                            # Check if this looks like a database ID (numeric)
                            if str(db_id).isdigit():
                                perfume_obj = Perfume.objects.get(id=int(db_id))
                                # Update with the correct external_id
                                fixed_perfume_data = perfume_data.copy()
                                fixed_perfume_data['external_id'] = perfume_obj.external_id
                                fixed_perfumes.append(fixed_perfume_data)
                                needs_fix = True
                                self.stdout.write(
                                    f"Fixed perfume in order item {order_item.id}: "
                                    f"DB ID {db_id} -> external_id {perfume_obj.external_id}"
                                )
                            else:
                                # Already has correct external_id format
                                fixed_perfumes.append(perfume_data)
                        except (Perfume.DoesNotExist, ValueError):
                            # Keep original data if perfume doesn't exist or invalid ID
                            fixed_perfumes.append(perfume_data)
                    else:
                        # Keep perfume data as is if no external_id field
                        fixed_perfumes.append(perfume_data)

                if needs_fix:
                    # Update the box configuration
                    order_item.box_configuration['perfumes'] = fixed_perfumes
                    order_item.save()
                    fixed_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Successfully fixed {fixed_count} order items')
        )