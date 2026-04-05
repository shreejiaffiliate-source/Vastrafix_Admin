from django.contrib import admin
from .models import Banner, SubCategory, Category, Item
from django.utils.html import format_html





class ItemInline(admin.TabularInline):
    model = Item
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id','name','icon', 'slug')
    

    fieldsets = (
    (None, {
        'fields': ('name', 'is_active', 'icon', 'slug')
    }),
)

    
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = [ItemInline]
    
    
@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'type','is_active')
    list_filter = ('type',)
    
    


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id','name','price', 'subcategory','is_active')
    list_filter = ('type','subcategory', 'is_active')
    search_fields = ('name',)

#support and services admin

from .models import Complaint

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    # Admin panel ki list mein ye columns dikhenge
    list_display = ('id', 'order','user','status', 'created_at')
    
    # Right side mein filter lagane ke liye (Status aur Date ke hisab se)
    list_filter = ('status', 'created_at')
    
    # Search bar (User ka naam ya complaint text search karne ke liye)
    search_fields = ('user__username', 'issue','order__id','message')
    
    # Status ko list view se hi change karne ke liye
    list_editable = ('status',)
    
    # Sorting order (Nayi complaints pehle dikhengi)
    ordering = ('-created_at',)

    
    


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'preview_image', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title',)
    readonly_fields = ('preview_image',)

    def preview_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="E:\Vastrafix\Django\media\banners\banner.png" style="height:60px;border-radius:8px;" />',
                obj.image.url
            )
        return "-"
    
    preview_image.short_description = "Preview"    
    