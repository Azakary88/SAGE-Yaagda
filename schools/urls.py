from django.urls import path

from .views import (
    CEBCreateView,
    CEBDeleteView,
    CEBEvaluationCreateView,
    CEBListView,
    CEBUpdateView,
    ProvinceCreateView,
    ProvinceDeleteView,
    ProvinceEvaluationCreateView,
    ProvinceListView,
    ProvinceUpdateView,
    SchoolAdministrativeEvaluationCreateView,
    SchoolCreateView,
    SchoolDeleteView,
    SchoolDetailView,
    SchoolListView,
    SchoolUpdateView,
)

app_name = 'schools'

urlpatterns = [
    path('provinces/', ProvinceListView.as_view(), name='province_list'),
    path('provinces/nouvelle/', ProvinceCreateView.as_view(), name='province_create'),
    path('provinces/evaluer/', ProvinceEvaluationCreateView.as_view(), name='province_evaluation_create'),
    path('provinces/<int:pk>/modifier/', ProvinceUpdateView.as_view(), name='province_update'),
    path('provinces/<int:pk>/supprimer/', ProvinceDeleteView.as_view(), name='province_delete'),
    path('cebs/', CEBListView.as_view(), name='ceb_list'),
    path('cebs/nouvelle/', CEBCreateView.as_view(), name='ceb_create'),
    path('cebs/evaluer/', CEBEvaluationCreateView.as_view(), name='ceb_evaluation_create'),
    path('cebs/<int:pk>/modifier/', CEBUpdateView.as_view(), name='ceb_update'),
    path('cebs/<int:pk>/supprimer/', CEBDeleteView.as_view(), name='ceb_delete'),
    path('', SchoolListView.as_view(), name='list'),
    path('nouvelle/', SchoolCreateView.as_view(), name='create'),
    path('evaluer/', SchoolAdministrativeEvaluationCreateView.as_view(), name='school_evaluation_create'),
    path('<int:pk>/modifier/', SchoolUpdateView.as_view(), name='update'),
    path('<int:pk>/supprimer/', SchoolDeleteView.as_view(), name='delete'),
    path('<int:pk>/', SchoolDetailView.as_view(), name='detail'),
]
