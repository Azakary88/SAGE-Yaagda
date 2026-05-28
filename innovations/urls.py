from django.urls import path

from .views import (
    ActivityCreateView,
    ActivityDeleteView,
    ActivityDetailView,
    ActivityListView,
    ActivityMediaCreateView,
    ActivityMediaDeleteView,
    ActivityUpdateView,
    RecommendationListView,
    activity_report_center,
    activity_report_pdf,
)

app_name = 'innovations'

urlpatterns = [
    path('activites/', ActivityListView.as_view(), name='activity_list'),
    path('activites/rapports/', activity_report_center, name='activity_report'),
    path('activites/rapports/pdf/', activity_report_pdf, name='activity_report_pdf'),
    path('activites/nouvelle/', ActivityCreateView.as_view(), name='activity_create'),
    path('activites/<int:pk>/', ActivityDetailView.as_view(), name='activity_detail'),
    path('activites/<int:pk>/modifier/', ActivityUpdateView.as_view(), name='activity_update'),
    path('activites/<int:pk>/supprimer/', ActivityDeleteView.as_view(), name='activity_delete'),
    path('activites/<int:activity_pk>/images/nouvelle/', ActivityMediaCreateView.as_view(), name='media_create'),
    path('images/<int:pk>/supprimer/', ActivityMediaDeleteView.as_view(), name='media_delete'),
    path('recommandations/', RecommendationListView.as_view(), name='recommendation_list'),
]
