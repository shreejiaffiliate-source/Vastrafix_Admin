from django.core.management.base import BaseCommand
from services.models import Category, SubCategory, Item
from django.db import transaction


class Command(BaseCommand):
    help = "Clone subcategories and items from one category to others"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        source_category_name = "Steam Iron"

        target_category_names = [
            "Wash & Iron",
            "Wash & Fold",
            "Dry Cleaning",
            "Saree Rolling",
        ]

        try:
            source_category = Category.objects.get(name=source_category_name)
        except Category.DoesNotExist:
            self.stdout.write(self.style.ERROR("Source category not found"))
            return

        source_subcats = SubCategory.objects.filter(type=source_category)

        for target_name in target_category_names:
            try:
                target_category = Category.objects.get(name=target_name)
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"{target_name} not found"))
                continue

            self.stdout.write(self.style.SUCCESS(f"\nProcessing: {target_name}"))

            for subcat in source_subcats:
                # ✅ check if subcategory already exists
                new_subcat, created = SubCategory.objects.get_or_create(
                    type=target_category,
                    name=subcat.name,
                    defaults={"is_active": subcat.is_active},
                )

                source_items = Item.objects.filter(subcategory=subcat)

                for item in source_items:
                    Item.objects.get_or_create(
                        type=target_category,
                        subcategory=new_subcat,
                        name=item.name,
                        defaults={
                            "price": item.price,
                            "is_active": item.is_active,
                        },
                    )

        self.stdout.write(self.style.SUCCESS("\n✅ Cloning completed!"))