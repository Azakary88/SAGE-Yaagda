from django.contrib import admin

from accounts.models import User
from accounts.scopes import filter_activities_for_user, filter_evaluations_for_user, filter_recommendations_for_user

from .models import Activity, ActivityMedia, Evaluation, Innovation, Recommendation, Report


@admin.register(Innovation)
class InnovationAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'school', 'innovation', 'reporting_date', 'participating_students')
    list_filter = ('innovation', 'reporting_date', 'has_internet')
    search_fields = ('title', 'school__name', 'innovation__name')
    autocomplete_fields = ('school', 'innovation', 'created_by')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_activities_for_user(request.user, queryset)

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.ADMINISTRATOR,
            User.Role.SCHOOL_DIRECTOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_activity(obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_activity(obj)


@admin.register(ActivityMedia)
class ActivityMediaAdmin(admin.ModelAdmin):
    list_display = ('activity', 'uploaded_by', 'created_at')
    search_fields = ('activity__title', 'comment')
    autocomplete_fields = ('activity', 'uploaded_by')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(activity__in=filter_activities_for_user(request.user, Activity.objects.all()))

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) in {
            User.Role.ADMINISTRATOR,
            User.Role.SCHOOL_DIRECTOR,
        }

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        return request.user.can_manage_activity(obj.activity)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return request.user.can_manage_activity(obj.activity)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('school', 'innovation', 'evaluation_date', 'implementation_level', 'performance_score')
    list_filter = ('innovation', 'evaluation_date')
    search_fields = ('school__name', 'innovation__name')
    autocomplete_fields = ('school', 'innovation', 'activity', 'evaluator')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_evaluations_for_user(request.user, queryset)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('school', 'innovation', 'priority', 'status', 'generated_by_system', 'created_at')
    list_filter = ('priority', 'status', 'generated_by_system')
    search_fields = ('school__name', 'recommendation_text', 'innovation__name')
    autocomplete_fields = ('school', 'innovation', 'based_on_evaluation')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return filter_recommendations_for_user(request.user, queryset)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'scope', 'school', 'province', 'created_at')
    list_filter = ('scope',)
    search_fields = ('title', 'school__name', 'province__name')
    autocomplete_fields = ('school', 'province', 'generated_by')
