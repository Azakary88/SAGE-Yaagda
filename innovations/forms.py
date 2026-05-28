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
            'school': 'Ecole',
            'innovation': 'Innovation',
            'title': "Titre de l'activite",
            'reporting_date': 'Date de rapportage',
            'classes_concerned': 'Classes concernees',
            'description': 'Description',
            'participating_students': 'Effectif des eleves participants',
            'trained_teachers': "Nombre d'enseignants formes",
            'taught_hours': "Volume horaire dispense",
            'computers_count': "Nombre d'ordinateurs mobilises",
            'has_internet': 'Acces a Internet',
            'quantity_produced': 'Quantite produite',
            'available_resources': 'Ressources disponibles',
            'challenges': 'Contraintes observees',
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
                "Vous pouvez uniquement enregistrer une activite pour votre ecole."
            )

        return school


class ActivityMediaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ActivityMedia
        fields = ['file', 'comment']
        labels = {
            'file': "Image de l'activite",
            'comment': 'Commentaire',
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs['accept'] = 'image/*'


class ActivityReportForm(BootstrapFormMixin, forms.Form):
    class ReportKind(models.TextChoices):
        ACTIVITY = 'ACTIVITY', "Synthese detaillee d'une activite"
        GENERAL = 'GENERAL', 'Rapport consolide du perimetre'

    report_kind = forms.ChoiceField(
        label='Type de rapport',
        choices=ReportKind.choices,
        initial=ReportKind.GENERAL,
    )
    activity = forms.ModelChoiceField(
        label='Activite concernee',
        queryset=Activity.objects.none(),
        required=False,
        empty_label='Choisir une activite',
        help_text="Selectionnez une activite pour afficher sa fiche de synthese detaillee.",
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
                "Veuillez selectionner une activite pour afficher sa synthese detaillee."
            )

        return cleaned_data
