from django.contrib import admin

from accounts.models import User
from accounts.scopes import (
    filter_ceb_evaluations_for_user,
    filter_cebs_for_user,
    filter_province_evaluations_for_user,
    filter_provinces_for_user,
    filter_regions_for_user,
    filter_school_admin_evaluations_for_user,
    filter_schools_for_user,
)

from .models import CEB, CEBEvaluation, Province, ProvinceEvaluation, Region, School, SchoolAdministrativeEvaluation


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_regions_for_user(request.user, queryset)


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'region')
    list_filter = ('region',)
    search_fields = ('code', 'name')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_provinces_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) == User.Role.REGIONAL_AGENT

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_province(obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_province(obj)


@admin.register(CEB)
class CEBAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'province')
    list_filter = ('province',)
    search_fields = ('code', 'name')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_cebs_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.PROVINCIAL_USER,
            User.Role.ADMINISTRATOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_ceb(obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_ceb(obj)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'province', 'ceb', 'school_type', 'status')
    list_filter = ('province', 'ceb', 'school_type', 'status')
    search_fields = ('code', 'name', 'locality')
    autocomplete_fields = ('director',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_schools_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.PEDAGOGICAL_SUPERVISOR,
            User.Role.ADMINISTRATOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_school(obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_school(obj)


@admin.register(ProvinceEvaluation)
class ProvinceEvaluationAdmin(admin.ModelAdmin):
    list_display = ('province', 'evaluation_date', 'performance_score', 'evaluator')
    list_filter = ('evaluation_date', 'province__region')
    search_fields = ('province__name',)
    autocomplete_fields = ('province', 'evaluator')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_province_evaluations_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.REGIONAL_AGENT,
            User.Role.ADMINISTRATOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_province(obj.province)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_province(obj.province)


@admin.register(CEBEvaluation)
class CEBEvaluationAdmin(admin.ModelAdmin):
    list_display = ('ceb', 'evaluation_date', 'performance_score', 'evaluator')
    list_filter = ('evaluation_date', 'ceb__province')
    search_fields = ('ceb__name',)
    autocomplete_fields = ('ceb', 'evaluator')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_ceb_evaluations_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.PROVINCIAL_USER,
            User.Role.ADMINISTRATOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_ceb(obj.ceb)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_ceb(obj.ceb)


@admin.register(SchoolAdministrativeEvaluation)
class SchoolAdministrativeEvaluationAdmin(admin.ModelAdmin):
    list_display = ('school', 'evaluation_date', 'performance_score', 'evaluator')
    list_filter = ('evaluation_date', 'school__ceb')
    search_fields = ('school__name',)
    autocomplete_fields = ('school', 'evaluator')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_school_admin_evaluations_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.PEDAGOGICAL_SUPERVISOR,
            User.Role.ADMINISTRATOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_school(obj.school)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_school(obj.school)
