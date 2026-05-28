from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, UpdateView

from .forms import (
    PedagogicalSupervisorForm,
    PhonePasswordResetForm,
    ProvincialUserForm,
    SchoolDirectorForm,
)
from .mixins import DeletePageMixin, FormPageMixin, ObjectPermissionMixin, RoleRequiredMixin
from .models import User
from .scopes import (
    filter_pedagogical_supervisors_for_user,
    filter_provincial_users_for_user,
    filter_school_directors_for_user,
)


class ManagedUserListView(ListView):
    context_object_name = 'users'
    template_name = 'accounts/user_list.html'
    page_title = ''
    page_intro = ''
    create_url_name = ''
    update_url_name = ''
    delete_url_name = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        context['page_intro'] = self.page_intro
        context['create_url_name'] = self.create_url_name
        context['update_url_name'] = self.update_url_name
        context['delete_url_name'] = self.delete_url_name
        return context


class ProvincialUserListView(RoleRequiredMixin, ManagedUserListView):
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    page_title = 'Agents provinciaux'
    page_intro = 'Administration des agents provinciaux relevant de votre region.'
    create_url_name = 'accounts:provincial_create'
    update_url_name = 'accounts:provincial_update'
    delete_url_name = 'accounts:provincial_delete'

    def get_queryset(self):
        return filter_provincial_users_for_user(self.request.user)


class ProvincialUserCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = User
    form_class = ProvincialUserForm
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:provincial_list')
    cancel_url = reverse_lazy('accounts:provincial_list')
    page_title = 'Enregistrer un agent provincial'
    page_intro = "Renseignez les informations du nouvel agent provincial rattache a votre region."
    success_message = "Le compte de l'agent provincial a ete cree avec succes."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['manager_user'] = self.request.user
        return kwargs


class ProvincialUserUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = User
    form_class = ProvincialUserForm
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:provincial_list')
    cancel_url = reverse_lazy('accounts:provincial_list')
    page_title = "Mettre a jour un agent provincial"
    page_intro = "Actualisez les informations administratives de cet agent provincial."
    success_message = "Le compte de l'agent provincial a ete mis a jour avec succes."
    permission_denied_message = "Vous pouvez uniquement modifier les agents provinciaux rattaches a votre region."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_provincial_user(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['manager_user'] = self.request.user
        return kwargs


class ProvincialUserDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = User
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:provincial_list')
    cancel_url = reverse_lazy('accounts:provincial_list')
    page_title = 'Supprimer un agent provincial'
    page_intro = "Cette operation retire definitivement le compte d'un agent provincial de votre region."
    delete_message = "Le compte de l'agent provincial a ete supprime avec succes."
    permission_denied_message = "Vous pouvez uniquement supprimer les agents provinciaux rattaches a votre region."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_provincial_user(obj)


class PedagogicalSupervisorListView(RoleRequiredMixin, ManagedUserListView):
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    page_title = 'Encadreurs pedagogiques'
    page_intro = 'Administration des encadreurs pedagogiques relevant de votre province.'
    create_url_name = 'accounts:supervisor_create'
    update_url_name = 'accounts:supervisor_update'
    delete_url_name = 'accounts:supervisor_delete'

    def get_queryset(self):
        return filter_pedagogical_supervisors_for_user(self.request.user)


class PedagogicalSupervisorCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = User
    form_class = PedagogicalSupervisorForm
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:supervisor_list')
    cancel_url = reverse_lazy('accounts:supervisor_list')
    page_title = 'Enregistrer un encadreur pedagogique'
    page_intro = "Renseignez les informations du nouvel encadreur pedagogique de votre province."
    success_message = "Le compte de l'encadreur pedagogique a ete cree avec succes."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['manager_user'] = self.request.user
        return kwargs


class PedagogicalSupervisorUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = User
    form_class = PedagogicalSupervisorForm
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:supervisor_list')
    cancel_url = reverse_lazy('accounts:supervisor_list')
    page_title = 'Mettre a jour un encadreur pedagogique'
    page_intro = "Actualisez les informations administratives de cet encadreur pedagogique."
    success_message = "Le compte de l'encadreur pedagogique a ete mis a jour avec succes."
    permission_denied_message = (
        "Vous pouvez uniquement modifier les encadreurs pedagogiques rattaches a votre province."
    )

    def has_object_permission(self, obj):
        return self.request.user.can_manage_pedagogical_supervisor(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['manager_user'] = self.request.user
        return kwargs


class PedagogicalSupervisorDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = User
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:supervisor_list')
    cancel_url = reverse_lazy('accounts:supervisor_list')
    page_title = 'Supprimer un encadreur pedagogique'
    page_intro = "Cette operation retire definitivement le compte d'un encadreur pedagogique de votre province."
    delete_message = "Le compte de l'encadreur pedagogique a ete supprime avec succes."
    permission_denied_message = (
        "Vous pouvez uniquement supprimer les encadreurs pedagogiques rattaches a votre province."
    )

    def has_object_permission(self, obj):
        return self.request.user.can_manage_pedagogical_supervisor(obj)


class SchoolDirectorListView(RoleRequiredMixin, ManagedUserListView):
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    page_title = "Directeurs d'ecole"
    page_intro = "Administration des directeurs d'ecole relevant de votre CEB."
    create_url_name = 'accounts:director_create'
    update_url_name = 'accounts:director_update'
    delete_url_name = 'accounts:director_delete'

    def get_queryset(self):
        return filter_school_directors_for_user(self.request.user)


class SchoolDirectorCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = User
    form_class = SchoolDirectorForm
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:director_list')
    cancel_url = reverse_lazy('accounts:director_list')
    page_title = "Enregistrer un directeur d'ecole"
    page_intro = "Renseignez les informations du nouveau directeur d'ecole de votre CEB."
    success_message = "Le compte du directeur d'ecole a ete cree avec succes."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['manager_user'] = self.request.user
        return kwargs


class SchoolDirectorUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = User
    form_class = SchoolDirectorForm
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:director_list')
    cancel_url = reverse_lazy('accounts:director_list')
    page_title = "Mettre a jour un directeur d'ecole"
    page_intro = "Actualisez les informations administratives de ce directeur d'ecole."
    success_message = "Le compte du directeur d'ecole a ete mis a jour avec succes."
    permission_denied_message = "Vous pouvez uniquement modifier les directeurs d'ecole rattaches a votre CEB."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_school_director(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['manager_user'] = self.request.user
        return kwargs


class SchoolDirectorDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = User
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('accounts:director_list')
    cancel_url = reverse_lazy('accounts:director_list')
    page_title = "Supprimer un directeur d'ecole"
    page_intro = "Cette operation retire definitivement le compte d'un directeur d'ecole de votre CEB."
    delete_message = "Le compte du directeur d'ecole a ete supprime avec succes."
    permission_denied_message = "Vous pouvez uniquement supprimer les directeurs d'ecole rattaches a votre CEB."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_school_director(obj)


class PhonePasswordResetView(FormPageMixin, FormView):
    form_class = PhonePasswordResetForm
    success_url = reverse_lazy('login')
    cancel_url = reverse_lazy('login')
    page_title = 'Reinitialisation du mot de passe'
    page_intro = (
        "Renseignez votre identifiant, votre numero de telephone et votre nouveau mot de passe pour recuperer l'acces a votre compte."
    )
    submit_label = 'Valider la reinitialisation'
    success_message = "Votre mot de passe a ete reinitialise avec succes. Vous pouvez a present vous connecter."

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
