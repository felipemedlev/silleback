# Plan to Fix Perfume Accord Ordering

**Goal:** Ensure that the `main accords` for each perfume are stored and retrieved in the same order as they appear in the `data/ccassions_perfumes_db.csv` file.

**Problem:** The current `Perfume.accords` relationship in `api/models.py` uses a standard `ManyToManyField`, which does not preserve the order of related items. The population script (`api/management/commands/populate_perfumes.py`) attempts to handle order but lacks the necessary database structure.

**Solution:** Modify the Django models to use a `through` model for the `Perfume`-`Accord` relationship, allowing an explicit `order` field to be stored.

**Steps:**

1.  **Modify `api/models.py`:**
    *   **Define `PerfumeAccordOrder` Model:** Create a new model to act as the intermediary table for the `Perfume` and `Accord` relationship. This model will store the foreign keys and the order.
        ```python
        class PerfumeAccordOrder(models.Model):
            perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE)
            accord = models.ForeignKey(Accord, on_delete=models.CASCADE)
            order = models.PositiveIntegerField(default=0, db_index=True) # Add index for ordering performance

            class Meta:
                ordering = ['order'] # Default ordering for queries
                unique_together = ('perfume', 'accord') # Prevent duplicates
        ```
    *   **Update `Perfume.accords` Field:** Modify the existing `ManyToManyField` in the `Perfume` model to use the new `through` model.
        ```python
        # Before:
        # accords = models.ManyToManyField(Accord, blank=True, related_name='perfumes')

        # After:
        accords = models.ManyToManyField(
            Accord,
            through='PerfumeAccordOrder', # Specify the intermediate model
            related_name='perfumes',
            blank=True
        )
        ```

2.  **Generate and Apply Database Migrations:**
    *   Run the command: `python manage.py makemigrations api`
    *   Carefully review the generated migration file in `api/migrations/` to ensure it correctly creates the `PerfumeAccordOrder` table and modifies the `Perfume.accords` relationship.
    *   Run the command: `python manage.py migrate`

3.  **Update Population Script (`api/management/commands/populate_perfumes.py`):**
    *   **Import Model:** Add `PerfumeAccordOrder` to the model imports at the top of the file:
        ```python
        from api.models import Perfume, Brand, Accord, Occasion, Note, PerfumeAccordOrder # Added PerfumeAccordOrder
        ```
    *   **Modify Accord Handling:** Update the loop that processes accords (around lines 125-131) to use the `PerfumeAccordOrder` model:
        ```python
        # --- Handle ManyToMany Relationships ---
        # Accords
        accord_names = self.parse_list_string(row.get('main accords', ''))
        # Clear existing through model entries for this perfume first
        PerfumeAccordOrder.objects.filter(perfume=perfume).delete() # Clear old relations
        for index, name in enumerate(accord_names): # Use enumerate for order
            if name:
                name_stripped = name.strip()
                if name_stripped: # Ensure name is not empty after stripping
                    accord, _ = Accord.objects.get_or_create(name=name_stripped)
                    # Create the through model instance with the order
                    PerfumeAccordOrder.objects.create(
                        perfume=perfume,
                        accord=accord,
                        order=index # Store the order
                    )
        ```

4.  **Repopulate Data:**
    *   *(Recommended for clean data)* Clear the relevant tables before repopulating. Access the Django shell (`python manage.py shell`) and run:
        ```python
        from api.models import Perfume, Accord, PerfumeAccordOrder
        PerfumeAccordOrder.objects.all().delete()
        # Optionally, if you want a completely fresh start (BE CAREFUL):
        # Perfume.objects.all().delete()
        # Accord.objects.all().delete()
        # Brand.objects.all().delete() # etc. for other related models if needed
        exit()
        ```
    *   Run the population command from your terminal:
        `python manage.py populate_perfumes data/ccassions_perfumes_db.csv`

5.  **Verification:**
    *   **(Admin Panel)** Register the `PerfumeAccordOrder` model in `api/admin.py` (e.g., `admin.site.register(PerfumeAccordOrder)`) to allow inspection of the ordered relationships directly in the admin interface.
    *   **(API)** Update any relevant serializers (e.g., `PerfumeSerializer`) and views if they were explicitly handling the `accords` field in a way that didn't rely on the default manager ordering. Test API endpoints that return perfume details to confirm the accords are now ordered correctly. Django's default manager for the `ManyToManyField` should now respect the `ordering` defined in the `PerfumeAccordOrder` model's `Meta` class.