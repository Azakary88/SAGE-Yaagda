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
            'region': 'Region',
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
            'code': "Code de l'ecole",
            'name': "Nom de l'ecole",
            'province': 'Province',
            'ceb': 'CEB',
            'school_type': "Type d'ecole",
            'status': 'Statut',
            'locality': 'Localite',
            'student_capacity': "Capacite d'accueil",
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
            self.add_error('ceb', 'La CEB selectionnee ne correspond pas a la province renseignee.')
        if (
            self.user
            and self.user.role == User.Role.PEDAGOGICAL_SUPERVISOR
            and self.user.ceb_id
            and ceb
            and ceb.id != self.user.ceb_id
        ):
            self.add_error('ceb', "Vous pouvez uniquement gerer les ecoles rattachees a votre CEB.")

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
            'evaluation_date': "Date d'evaluation",
            'planning_score': 'Score de planification',
            'execution_score': "Score d'execution",
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
            'school': 'Ecole',
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
