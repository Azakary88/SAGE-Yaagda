from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Profil', {'fields': ('role', 'phone_number', 'job_title', 'region', 'province', 'ceb')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Profil', {'fields': ('role', 'phone_number', 'job_title', 'region', 'province', 'ceb')}),
    )
    list_display = (
        'username',
        'first_name',
        'last_name',
        'role',
        'region',
        'province',
        'ceb',
        'is_staff',
        'is_active',
    )
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
