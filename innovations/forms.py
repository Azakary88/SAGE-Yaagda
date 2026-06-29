from django import forms
from django.db import models

from accounts.forms import BootstrapFormMixin
from accounts.models import User
from accounts.scopes import filter_activities_for_user, filter_schools_for_user
from schools.models import School

from .models import Activity, ActivityMedia, Innovation


class ActivityForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            'school',
            'innovation',
            'title',
            'reporting_date',
            'classes_concerned',
            'description',
            'participating_students',
            'trained_teachers',
            'taught_hours',
            'computers_count',
            'has_internet',
            'quantity_produced',
            'available_resources',
            'challenges',
        ]
        labels = {
            'school': 'École',
            'innovation': 'Innovation',
            'title': "Titre de l'activité",
            'reporting_date': 'Date de rapportage',
            'classes_concerned': 'Classes concernées',
            'description': 'Description',
            'participating_students': 'Effectif des élèves participants',
            'trained_teachers': "Nombre d'enseignants formés",
            'taught_hours': "Volume horaire dispensé",
            'computers_count': "Nombre d'ordinateurs mobilisés",
            'has_internet': 'Accès à Internet',
            'quantity_produced': 'Quantité produite',
            'available_resources': 'Ressources disponibles',
            'challenges': 'Contraintes observées',
        }
        widgets = {
            'reporting_date': forms.DateInput(attrs={'type': 'date'}),
            'participating_students': forms.NumberInput(attrs={'min': 0}),
            'trained_teachers': forms.NumberInput(attrs={'min': 0}),
            'taught_hours': forms.NumberInput(attrs={'min': 0}),
            'computers_count': forms.NumberInput(attrs={'min': 0}),
            'quantity_produced': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['innovation'].queryset = Innovation.objects.filter(is_active=True).order_by('name')
        self.fields['school'].queryset = filter_schools_for_user(
            user,
            School.objects.select_related('province', 'ceb').order_by('name'),
        )

    def clean_school(self):
        school = self.cleaned_data['school']
        user = self.user

        if (
            user
            and not user.is_superuser
            and user.role == User.Role.SCHOOL_DIRECTOR
            and school.director_id != user.id
        ):
            raise forms.ValidationError(
                "Vous pouvez uniquement enregistrer une activité pour votre école."
            )

        return school


class ActivityMediaForm(BootstrapFormMixin, forms.ModelForm):
    MAX_FILE_SIZE = 2 * 1024 * 1024
    ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}

    class Meta:
        model = ActivityMedia
        fields = ['file', 'comment']
        labels = {
            'file': "Image de l'activité",
            'comment': 'Commentaire',
        }
        help_texts = {
            'file': "Les grandes images sont compressées automatiquement avant l'envoi.",
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs['accept'] = 'image/*'

    def clean_file(self):
        file = self.cleaned_data['file']
        content_type = getattr(file, 'content_type', '')

        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            raise forms.ValidationError(
                "Le fichier doit être une image au format JPG, PNG, GIF ou WebP."
            )

        if file.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError(
                "L'image est trop volumineuse. Veuillez choisir une image de 2 Mo maximum."
            )

        return file


class ActivityReportForm(BootstrapFormMixin, forms.Form):
    class ReportKind(models.TextChoices):
        ACTIVITY = 'ACTIVITY', "Synthèse détaillée d'une activité"
        GENERAL = 'GENERAL', "Rapport consolidé de la zone d'action"

    report_kind = forms.ChoiceField(
        label='Type de rapport',
        choices=ReportKind.choices,
        initial=ReportKind.GENERAL,
    )
    activity = forms.ModelChoiceField(
        label='Activité concernée',
        queryset=Activity.objects.none(),
        required=False,
        empty_label='Choisir une activité',
        help_text="Sélectionnez une activité pour afficher sa fiche de synthèse détaillée.",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['activity'].queryset = filter_activities_for_user(
            user,
            Activity.objects.select_related(
                'school',
                'school__province',
                'school__ceb',
                'innovation',
            ).order_by('-reporting_date', 'school__name', 'title'),
        )

    def clean(self):
        cleaned_data = super().clean()
        report_kind = cleaned_data.get('report_kind')
        activity = cleaned_data.get('activity')

        if report_kind == self.ReportKind.ACTIVITY and not activity:
            raise forms.ValidationError(
                "Veuillez sélectionner une activité pour afficher sa synthèse détaillée."
            )

        return cleaned_data
