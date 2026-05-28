from django.urls import path

from .views import (
    PedagogicalSupervisorCreateView,
    PedagogicalSupervisorDeleteView,
    PedagogicalSupervisorListView,
    PedagogicalSupervisorUpdateView,
    PhonePasswordResetView,
    ProvincialUserCreateView,
    ProvincialUserDeleteView,
    ProvincialUserListView,
    ProvincialUserUpdateView,
    SchoolDirectorCreateView,
    SchoolDirectorDeleteView,
    SchoolDirectorListView,
    SchoolDirectorUpdateView,
)

app_name = 'accounts'

urlpatterns = [
    path('mot-de-passe-oublie/', PhonePasswordResetView.as_view(), name='phone_password_reset'),
    path('provinciaux/', ProvincialUserListView.as_view(), name='provincial_list'),
    path('provinciaux/nouveau/', ProvincialUserCreateView.as_view(), name='provincial_create'),
    path('provinciaux/<int:pk>/modifier/', ProvincialUserUpdateView.as_view(), name='provincial_update'),
    path('provinciaux/<int:pk>/supprimer/', ProvincialUserDeleteView.as_view(), name='provincial_delete'),
    path('encadreurs/', PedagogicalSupervisorListView.as_view(), name='supervisor_list'),
    path('encadreurs/nouveau/', PedagogicalSupervisorCreateView.as_view(), name='supervisor_create'),
    path('encadreurs/<int:pk>/modifier/', PedagogicalSupervisorUpdateView.as_view(), name='supervisor_update'),
    path('encadreurs/<int:pk>/supprimer/', PedagogicalSupervisorDeleteView.as_view(), name='supervisor_delete'),
    path('directeurs/', SchoolDirectorListView.as_view(), name='director_list'),
    path('directeurs/nouveau/', SchoolDirectorCreateView.as_view(), name='director_create'),
    path('directeurs/<int:pk>/modifier/', SchoolDirectorUpdateView.as_view(), name='director_update'),
    path('directeurs/<int:pk>/supprimer/', SchoolDirectorDeleteView.as_view(), name='director_delete'),
]
