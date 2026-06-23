from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User
from accounts.scopes import filter_cebs_for_user, filter_provinces_for_user, filter_regions_for_user

from .models import CEB, CEBEvaluation, Province, ProvinceEvaluation, School, SchoolAdministrativeEvaluation


class ProvinceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Province
        fields = ['region', 'code', 'name']
        labels = {
            'region': 'Région',
            'code': 'Code de la province',
            'name': 'Nom de la province',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['region'].queryset = filter_regions_for_user(user, self.fields['region'].queryset)


class CEBForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CEB
        fields = ['province', 'code', 'name']
        labels = {
            'province': 'Province',
            'code': 'Code de la CEB',
            'name': 'Nom de la CEB',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['province'].queryset = filter_provinces_for_user(user, self.fields['province'].queryset)


class SchoolForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = School
        fields = [
            'code',
            'name',
            'province',
            'ceb',
            'school_type',
            'status',
            'locality',
            'student_capacity',
        ]
        labels = {
            'code': "Code de l'école",
            'name': "Nom de l'école",
            'province': 'Province',
            'ceb': 'CEB',
            'school_type': "Type d'école",
            'status': 'Statut',
            'locality': 'Localité',
            'student_capacity': "Capacité d'accueil",
        }
        widgets = {
            'student_capacity': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['province'].queryset = filter_provinces_for_user(
            user,
            Province.objects.select_related('region').order_by('name'),
        )
        self.fields['ceb'].queryset = filter_cebs_for_user(
            user,
            CEB.objects.select_related('province').order_by('name'),
        )

    def clean(self):
        cleaned_data = super().clean()
        province = cleaned_data.get('province')
        ceb = cleaned_data.get('ceb')

        if province and ceb and ceb.province_id != province.id:
            self.add_error('ceb', 'La CEB sélectionnée ne correspond pas à la province renseignée.')
        if (
            self.user
            and self.user.role == User.Role.PEDAGOGICAL_SUPERVISOR
            and self.user.ceb_id
            and ceb
            and ceb.id != self.user.ceb_id
        ):
            self.add_error('ceb', "Vous pouvez uniquement gérer les écoles rattachées à votre CEB.")

        return cleaned_data


class BaseAdministrativeEvaluationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        fields = [
            'evaluation_date',
            'planning_score',
            'execution_score',
            'reporting_score',
            'strengths',
            'constraints',
            'recommendations',
        ]
        labels = {
            'evaluation_date': "Date d'évaluation",
            'planning_score': 'Score de planification',
            'execution_score': "Score d'exécution",
            'reporting_score': 'Score de rapportage',
            'strengths': 'Points forts',
            'constraints': 'Contraintes',
            'recommendations': 'Recommandations',
        }
        widgets = {
            'evaluation_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ProvinceEvaluationForm(BaseAdministrativeEvaluationForm):
    class Meta(BaseAdministrativeEvaluationForm.Meta):
        model = ProvinceEvaluation
        fields = ['province'] + BaseAdministrativeEvaluationForm.Meta.fields
        labels = {
            **BaseAdministrativeEvaluationForm.Meta.labels,
            'province': 'Province',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['province'].queryset = filter_provinces_for_user(
            user,
            Province.objects.select_related('region').order_by('name'),
        )


class CEBEvaluationForm(BaseAdministrativeEvaluationForm):
    class Meta(BaseAdministrativeEvaluationForm.Meta):
        model = CEBEvaluation
        fields = ['ceb'] + BaseAdministrativeEvaluationForm.Meta.fields
        labels = {
            **BaseAdministrativeEvaluationForm.Meta.labels,
            'ceb': 'CEB',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['ceb'].queryset = filter_cebs_for_user(
            user,
            CEB.objects.select_related('province', 'province__region').order_by('name'),
        )


class SchoolAdministrativeEvaluationForm(BaseAdministrativeEvaluationForm):
    class Meta(BaseAdministrativeEvaluationForm.Meta):
        model = SchoolAdministrativeEvaluation
        fields = ['school'] + BaseAdministrativeEvaluationForm.Meta.fields
        labels = {
            **BaseAdministrativeEvaluationForm.Meta.labels,
            'school': 'École',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['school'].queryset = School.objects.select_related('province', 'ceb').order_by('name')
        if user and not user.is_superuser:
            if user.role == User.Role.PEDAGOGICAL_SUPERVISOR:
                self.fields['school'].queryset = self.fields['school'].queryset.filter(ceb_id=user.ceb_id)
            elif user.role == User.Role.ADMINISTRATOR:
                pass
            else:
                self.fields['school'].queryset = self.fields['school'].queryset.none()
