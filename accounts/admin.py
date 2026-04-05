from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import Address

User = get_user_model()
admin.site.unregister(Group)


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    model = User

    list_display = (
        'id',
        'username',
        'email',
        'phone',
        'role',
        'is_active',
    )

    list_filter = (
        'role',
        'is_active',
        'city',
    )

    search_fields = (
        'username',
        'email',
        'phone',
        'city',
    )

    ordering = ('-date_joined',)

    # 🔹 Edit Page Layout
    fieldsets = (
        ('Account Info', {
            'fields': ('username', 'email', 'phone', 'password', 'fcm_token')
        }),

        ('Address Info', {
            'fields': ('address', 'city', 'state', 'pincode', 'latitude', 'longitude')
        }),

        ('Role Info', {
            'fields': ('role', 'is_active')
        }),

    
    )

    # 🔹 Add User Page Layout (IMPORTANT FIX 🔥)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'phone',
                'password1',
                'password2',
                'fcm_token',
                'role',
                'address',
                'city',
                'state',
                'pincode',
                'latitude',
                'longitude',
                'is_active',
            ),
        }),
    )



# ================= ADDRESS ADMIN =================
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "house_no",
        "area",
        "city",
        "state",
        "pincode",
    
        
    )

    list_filter = (
        "city",
        "state",
        "user__role",   # 🔥 filter by customer/partner
    )

    search_fields = (
        "user__username",
        "user__phone",
        "city",
        "area",
    )

    def get_role(self, obj):
        return obj.user.role

    get_role.short_description = "Role"


admin.site.register(Address, AddressAdmin)