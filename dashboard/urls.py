from django.urls import path

from .views import ai_analysis, ai_analysis_pdf, home

app_name = 'dashboard'

urlpatterns = [
    path('', home, name='home'),
    path('analyse-ia/', ai_analysis, name='ai_analysis'),
    path('analyse-ia/export-pdf/', ai_analysis_pdf, name='ai_analysis_pdf'),
]
