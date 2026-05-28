from django.db.models import Count

from schools.models import CEB, CEBEvaluation, Province, ProvinceEvaluation, Region, School, SchoolAdministrativeEvaluation

from .models import User


def _none(queryset):
    return queryset.none()


def filter_regions_for_user(user, queryset=None):
    if queryset is None:
        queryset = Region.objects.all()

    if not user or not user.is_authenticated:
        return _none(queryset)
    if user.is_superuser or user.role == user.Role.ADMINISTRATOR:
        return queryset
    if user.role == user.Role.REGIONAL_AGENT:
        return queryset.filter(id=user.region_id) if user.region_id else _none(queryset)
    if user.role == user.Role.PROVINCIAL_USER:
        return queryset.filter(id=user.province.region_id) if user.province_id else _none(queryset)
    if user.role == user.Role.PEDAGOGICAL_SUPERVISOR:
        return queryset.filter(id=user.ceb.province.region_id) if user.ceb_id else _none(queryset)
    if user.role == user.Role.SCHOOL_DIRECTOR:
        return queryset.filter(provinces__cebs__schools__director=user).distinct()
    return _none(queryset)


def filter_provinces_for_user(user, queryset=None):
    if queryset is None:
        queryset = Province.objects.select_related('region')

    if not user or not user.is_authenticated:
        return _none(queryset)
    if user.is_superuser or user.role == user.Role.ADMINISTRATOR:
        return queryset
    if user.role == user.Role.REGIONAL_AGENT:
        return queryset.filter(region_id=user.region_id) if user.region_id else _none(queryset)
    if user.role == user.Role.PROVINCIAL_USER:
        return queryset.filter(id=user.province_id) if user.province_id else _none(queryset)
    if user.role == user.Role.PEDAGOGICAL_SUPERVISOR:
        return queryset.filter(id=user.ceb.province_id) if user.ceb_id else _none(queryset)
    if user.role == user.Role.SCHOOL_DIRECTOR:
        return queryset.filter(schools__director=user).distinct()
    return _none(queryset)


def filter_cebs_for_user(user, queryset=None):
    if queryset is None:
        queryset = CEB.objects.select_related('province', 'province__region')

    if not user or not user.is_authenticated:
        return _none(queryset)
    if user.is_superuser or user.role == user.Role.ADMINISTRATOR:
        return queryset
    if user.role == user.Role.REGIONAL_AGENT:
        return queryset.filter(province__region_id=user.region_id) if user.region_id else _none(queryset)
    if user.role == user.Role.PROVINCIAL_USER:
        return queryset.filter(province_id=user.province_id) if user.province_id else _none(queryset)
    if user.role == user.Role.PEDAGOGICAL_SUPERVISOR:
        return queryset.filter(id=user.ceb_id) if user.ceb_id else _none(queryset)
    if user.role == user.Role.SCHOOL_DIRECTOR:
        return queryset.filter(schools__director=user).distinct()
    return _none(queryset)


def filter_schools_for_user(user, queryset=None):
    if queryset is None:
        queryset = School.objects.select_related('province', 'province__region', 'ceb', 'director')

    if not user or not user.is_authenticated:
        return _none(queryset)
    if user.is_superuser or user.role == user.Role.ADMINISTRATOR:
        return queryset
    if user.role == user.Role.REGIONAL_AGENT:
        return queryset.filter(province__region_id=user.region_id) if user.region_id else _none(queryset)
    if user.role == user.Role.PROVINCIAL_USER:
        return queryset.filter(province_id=user.province_id) if user.province_id else _none(queryset)
    if user.role == user.Role.PEDAGOGICAL_SUPERVISOR:
        return queryset.filter(ceb_id=user.ceb_id) if user.ceb_id else _none(queryset)
    if user.role == user.Role.SCHOOL_DIRECTOR:
        return queryset.filter(director=user)
    return _none(queryset)


def filter_activities_for_user(user, queryset):
    return queryset.filter(school__in=filter_schools_for_user(user, School.objects.all()))


def filter_evaluations_for_user(user, queryset):
    return queryset.filter(school__in=filter_schools_for_user(user, School.objects.all()))


def filter_recommendations_for_user(user, queryset):
    return queryset.filter(school__in=filter_schools_for_user(user, School.objects.all()))


def filter_province_evaluations_for_user(user, queryset=None):
    if queryset is None:
        queryset = ProvinceEvaluation.objects.select_related('province', 'province__region', 'evaluator')
    return queryset.filter(province__in=filter_provinces_for_user(user, Province.objects.all()))


def filter_ceb_evaluations_for_user(user, queryset=None):
    if queryset is None:
        queryset = CEBEvaluation.objects.select_related('ceb', 'ceb__province', 'evaluator')
    return queryset.filter(ceb__in=filter_cebs_for_user(user, CEB.objects.all()))


def filter_school_admin_evaluations_for_user(user, queryset=None):
    if queryset is None:
        queryset = SchoolAdministrativeEvaluation.objects.select_related('school', 'school__ceb', 'evaluator')
    return queryset.filter(school__in=filter_schools_for_user(user, School.objects.all()))


def filter_users_for_user(user, queryset=None, role=None):
    if queryset is None:
        queryset = User.objects.select_related('region', 'province', 'ceb').order_by('username')

    if role:
        queryset = queryset.filter(role=role)

    if not user or not user.is_authenticated:
        return _none(queryset)
    if user.is_superuser or user.role == user.Role.ADMINISTRATOR:
        return queryset
    if user.role == user.Role.REGIONAL_AGENT:
        return queryset.filter(province__region_id=user.region_id) if user.region_id else _none(queryset)
    if user.role == user.Role.PROVINCIAL_USER:
        return queryset.filter(ceb__province_id=user.province_id) if user.province_id else _none(queryset)
    if user.role == user.Role.PEDAGOGICAL_SUPERVISOR:
        return queryset.filter(ceb_id=user.ceb_id) if user.ceb_id else _none(queryset)
    if user.role == user.Role.SCHOOL_DIRECTOR:
        return queryset.filter(id=user.id)
    return _none(queryset)


def filter_provincial_users_for_user(user, queryset=None):
    queryset = filter_users_for_user(user, queryset, role=User.Role.PROVINCIAL_USER)
    if not user.is_superuser and user.role == user.Role.REGIONAL_AGENT:
        return queryset.filter(region_id=user.region_id)
    return queryset


def filter_pedagogical_supervisors_for_user(user, queryset=None):
    queryset = filter_users_for_user(user, queryset, role=User.Role.PEDAGOGICAL_SUPERVISOR)
    if not user.is_superuser and user.role == user.Role.PROVINCIAL_USER:
        return queryset.filter(province_id=user.province_id)
    return queryset


def filter_school_directors_for_user(user, queryset=None):
    queryset = filter_users_for_user(user, queryset, role=User.Role.SCHOOL_DIRECTOR)
    if not user.is_superuser and user.role == user.Role.PEDAGOGICAL_SUPERVISOR:
        return queryset.filter(ceb_id=user.ceb_id)
    return queryset


def summarize_visible_scope(user):
    if not user or not user.is_authenticated:
        return {
            'regions': 0,
            'provinces': 0,
            'cebs': 0,
            'schools': 0,
            'schools_with_activity': 0,
        }
    return {
        'regions': filter_regions_for_user(user).count(),
        'provinces': filter_provinces_for_user(user).count(),
        'cebs': filter_cebs_for_user(user).count(),
        'schools': filter_schools_for_user(user).count(),
        'schools_with_activity': filter_schools_for_user(user).annotate(
            total_activities=Count('activities'),
        ).filter(total_activities__gt=0).count(),
    }
