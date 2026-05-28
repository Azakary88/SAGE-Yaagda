from django import forms
from django.contrib.auth.password_validation import validate_password

from schools.models import CEB, Province, School

from .models import User


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()

    def _apply_bootstrap_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get('class', '')

            if isinstance(widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css_class = 'form-select'
            else:
                css_class = 'form-control'

            widget.attrs['class'] = ' '.join(filter(None, [existing, css_class]))
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('rows', 4)


class BaseManagedUserForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput,
        required=False,
        help_text='Obligatoire a la creation. Laissez ce champ vide pour conserver le mot de passe actuel.',
    )
    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'job_title',
            'is_active',
        ]
        labels = {
            'username': "Nom d'utilisateur",
            'first_name': 'Prenom',
            'last_name': 'Nom',
            'email': 'Adresse e-mail',
            'phone_number': 'Numero de telephone',
            'job_title': 'Fonction',
            'is_active': 'Compte actif',
        }

    managed_role = None

    def __init__(self, *args, manager_user=None, **kwargs):
        self.manager_user = manager_user
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if not self.instance.pk and (not password1 or not password2):
            raise forms.ValidationError("Le mot de passe est obligatoire lors de la creation du compte.")
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Les deux mots de passe saisis doivent etre identiques.')

        return cleaned_data

    def apply_scope(self, user):
        return user

    def save_related_scope(self, user):
        return user

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.managed_role
        user.is_staff = False
        user.region = None
        user.province = None
        user.ceb = None
        user = self.apply_scope(user)

        password1 = self.cleaned_data.get('password1')
        if password1:
            user.set_password(password1)

        if commit:
            user.save()
            self.save_related_scope(user)
        return user


class ProvincialUserForm(BaseManagedUserForm):
    class Meta(BaseManagedUserForm.Meta):
        fields = BaseManagedUserForm.Meta.fields + ['province']
        labels = {
            **BaseManagedUserForm.Meta.labels,
            'province': 'Province',
        }

    managed_role = User.Role.PROVINCIAL_USER

    def __init__(self, *args, manager_user=None, **kwargs):
        super().__init__(*args, manager_user=manager_user, **kwargs)
        queryset = Province.objects.select_related('region').order_by('name')
        if manager_user and not manager_user.is_superuser and manager_user.role == User.Role.REGIONAL_AGENT:
            queryset = queryset.filter(region_id=manager_user.region_id)
        self.fields['province'].queryset = queryset

    def apply_scope(self, user):
        province = self.cleaned_data['province']
        user.province = province
        user.region = province.region
        return user


class PedagogicalSupervisorForm(BaseManagedUserForm):
    class Meta(BaseManagedUserForm.Meta):
        fields = BaseManagedUserForm.Meta.fields + ['ceb']
        labels = {
            **BaseManagedUserForm.Meta.labels,
            'ceb': 'CEB',
        }

    managed_role = User.Role.PEDAGOGICAL_SUPERVISOR

    def __init__(self, *args, manager_user=None, **kwargs):
        super().__init__(*args, manager_user=manager_user, **kwargs)
        queryset = CEB.objects.select_related('province', 'province__region').order_by('name')
        if manager_user and not manager_user.is_superuser and manager_user.role == User.Role.PROVINCIAL_USER:
            queryset = queryset.filter(province_id=manager_user.province_id)
        self.fields['ceb'].queryset = queryset

    def apply_scope(self, user):
        ceb = self.cleaned_data['ceb']
        user.ceb = ceb
        user.province = ceb.province
        user.region = ceb.province.region
        return user


class SchoolDirectorForm(BaseManagedUserForm):
    school = forms.ModelChoiceField(
        label='Ecole',
        queryset=School.objects.none(),
    )

    class Meta(BaseManagedUserForm.Meta):
        fields = BaseManagedUserForm.Meta.fields

    field_order = [
        'username',
        'first_name',
        'last_name',
        'email',
        'phone_number',
        'job_title',
        'school',
        'is_active',
        'password1',
        'password2',
    ]

    managed_role = User.Role.SCHOOL_DIRECTOR

    def __init__(self, *args, manager_user=None, **kwargs):
        super().__init__(*args, manager_user=manager_user, **kwargs)
        queryset = School.objects.select_related('province', 'ceb').order_by('name')
        if manager_user and not manager_user.is_superuser and manager_user.role == User.Role.PEDAGOGICAL_SUPERVISOR:
            queryset = queryset.filter(ceb_id=manager_user.ceb_id)
        self.fields['school'].queryset = queryset
        if self.instance.pk:
            assigned_school = School.objects.filter(director=self.instance).first()
            if assigned_school:
                self.fields['school'].initial = assigned_school

    def clean_school(self):
        school = self.cleaned_data['school']
        current_director = school.director
        if current_director and current_director != self.instance:
            raise forms.ValidationError("Cette ecole est deja rattachee a un autre directeur.")
        return school

    def apply_scope(self, user):
        school = self.cleaned_data['school']
        user.ceb = school.ceb
        user.province = school.province
        user.region = school.province.region
        return user

    def save_related_scope(self, user):
        school = self.cleaned_data['school']
        School.objects.filter(director=user).exclude(pk=school.pk).update(director=None)
        if school.director_id != user.id:
            school.director = user
            school.save(update_fields=['director'])
        return user


class PhonePasswordResetForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(label="Nom d'utilisateur", max_length=150)
    phone_number = forms.CharField(label='Numero de telephone', max_length=20)
    new_password1 = forms.CharField(
        label='Nouveau mot de passe',
        widget=forms.PasswordInput,
    )
    new_password2 = forms.CharField(
        label='Confirmer le nouveau mot de passe',
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username', '').strip()
        phone_number = cleaned_data.get('phone_number', '').strip()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Les deux mots de passe saisis doivent etre identiques.')

        try:
            self.user = User.objects.get(
                username=username,
                phone_number=phone_number,
                is_active=True,
            )
        except User.DoesNotExist as exc:
            raise forms.ValidationError(
                "Aucun compte actif ne correspond a l'identifiant et au numero de telephone renseignes."
            ) from exc

        if password1:
            validate_password(password1, self.user)

        return cleaned_data

    def save(self):
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save(update_fields=['password'])
        return self.user
