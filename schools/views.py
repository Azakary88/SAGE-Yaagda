from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import DeletePageMixin, FormPageMixin, ObjectPermissionMixin, RoleRequiredMixin
from accounts.models import User
from accounts.scopes import filter_cebs_for_user, filter_provinces_for_user, filter_schools_for_user
from innovations.models import Activity, Evaluation, Recommendation

from .forms import (
    CEBEvaluationForm,
    CEBForm,
    ProvinceEvaluationForm,
    ProvinceForm,
    SchoolAdministrativeEvaluationForm,
    SchoolForm,
)
from .models import CEB, CEBEvaluation, Province, ProvinceEvaluation, School, SchoolAdministrativeEvaluation


class ProvinceListView(LoginRequiredMixin, ListView):
    model = Province
    context_object_name = 'provinces'
    template_name = 'schools/province_list.html'

    def get_queryset(self):
        queryset = filter_provinces_for_user(
            self.request.user,
            Province.objects.select_related('region').order_by('name'),
        )
        return queryset.annotate(
            total_cebs=Count('cebs', distinct=True),
            total_schools=Count('schools', distinct=True),
            total_activities=Count('schools__activities', distinct=True),
            avg_score=Avg('administrative_evaluations__performance_score'),
        )


class CEBListView(LoginRequiredMixin, ListView):
    model = CEB
    context_object_name = 'cebs'
    template_name = 'schools/ceb_list.html'

    def get_queryset(self):
        queryset = filter_cebs_for_user(
            self.request.user,
            CEB.objects.select_related('province', 'province__region').order_by('name'),
        )
        province_id = self.request.GET.get('province')
        if province_id:
            queryset = queryset.filter(province_id=province_id)

        return queryset.annotate(
            total_schools=Count('schools', distinct=True),
            total_activities=Count('schools__activities', distinct=True),
            avg_score=Avg('administrative_evaluations__performance_score'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = filter_provinces_for_user(
            self.request.user,
            Province.objects.select_related('region').order_by('name'),
        )
        context['selected_province'] = self.request.GET.get('province', '')
        return context


class SchoolListView(LoginRequiredMixin, ListView):
    model = School
    context_object_name = 'schools'
    template_name = 'schools/school_list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = filter_schools_for_user(
            self.request.user,
            School.objects.select_related('province', 'province__region', 'ceb', 'director'),
        )
        search_term = self.request.GET.get('q', '').strip()
        province_id = self.request.GET.get('province')
        ceb_id = self.request.GET.get('ceb')

        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term)
                | Q(code__icontains=search_term)
                | Q(locality__icontains=search_term)
            )
        if province_id:
            queryset = queryset.filter(province_id=province_id)
        if ceb_id:
            queryset = queryset.filter(ceb_id=ceb_id)

        return queryset.annotate(
            total_activities=Count('activities', distinct=True),
            avg_score=Avg('administrative_evaluations__performance_score'),
            innovation_score=Avg('evaluations__performance_score'),
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = filter_provinces_for_user(
            self.request.user,
            Province.objects.select_related('region').order_by('name'),
        )
        context['cebs'] = filter_cebs_for_user(
            self.request.user,
            CEB.objects.select_related('province').order_by('name'),
        )
        context['search_term'] = self.request.GET.get('q', '').strip()
        context['selected_province'] = self.request.GET.get('province', '')
        context['selected_ceb'] = self.request.GET.get('ceb', '')
        return context


class SchoolDetailView(LoginRequiredMixin, DetailView):
    model = School
    context_object_name = 'school'
    template_name = 'schools/school_detail.html'

    def get_queryset(self):
        return filter_schools_for_user(
            self.request.user,
            School.objects.select_related('province', 'province__region', 'ceb', 'director'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = self.object
        user = self.request.user
        context['activities'] = (
            Activity.objects.filter(school=school).select_related('innovation').order_by('-reporting_date')[:10]
        )
        context['evaluations'] = Evaluation.objects.filter(school=school).select_related(
            'innovation',
            'evaluator',
        )[:10]
        context['recommendations'] = Recommendation.objects.filter(school=school).select_related(
            'innovation',
        )[:10]
        context['administrative_evaluations'] = SchoolAdministrativeEvaluation.objects.filter(
            school=school,
        ).select_related('evaluator')[:10]
        context['can_add_activity_here'] = user.can_add_activity and (
            user.is_superuser
            or user.role == User.Role.ADMINISTRATOR
            or school.director_id == user.id
        )
        context['can_manage_school_here'] = user.can_manage_school(school)
        context['can_evaluate_school_here'] = user.can_manage_school(school)
        return context


class ProvinceCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = Province
    form_class = ProvinceForm
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    permission_denied_message = "Seuls les agents regionaux sont habilites a enregistrer une province."
    success_url = reverse_lazy('schools:province_list')
    cancel_url = reverse_lazy('schools:province_list')
    page_title = 'Enregistrer une province'
    page_intro = "Renseignez les informations administratives de la province a integrer dans votre region."
    success_message = 'La province a ete enregistree avec succes.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class ProvinceUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = Province
    form_class = ProvinceForm
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    permission_denied_message = "Vous pouvez uniquement modifier les provinces rattachees a votre region."
    success_url = reverse_lazy('schools:province_list')
    cancel_url = reverse_lazy('schools:province_list')
    page_title = 'Mettre a jour une province'
    page_intro = "Actualisez les informations administratives de cette province."
    success_message = 'La province a ete mise a jour avec succes.'

    def has_object_permission(self, obj):
        return self.request.user.can_manage_province(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class ProvinceDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = Province
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    permission_denied_message = "Vous pouvez uniquement supprimer les provinces rattachees a votre region."
    success_url = reverse_lazy('schools:province_list')
    cancel_url = reverse_lazy('schools:province_list')
    page_title = 'Supprimer une province'
    page_intro = "Cette operation retire definitivement la province selectionnee de votre espace de gestion."
    delete_message = 'La province a ete supprimee avec succes.'

    def has_object_permission(self, obj):
        return self.request.user.can_manage_province(obj)


class CEBCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = CEB
    form_class = CEBForm
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    permission_denied_message = "Seuls les agents provinciaux sont habilites a enregistrer une CEB."
    success_url = reverse_lazy('schools:ceb_list')
    cancel_url = reverse_lazy('schools:ceb_list')
    page_title = 'Enregistrer une CEB'
    page_intro = "Renseignez les informations administratives de la CEB a rattacher a votre province."
    success_message = 'La CEB a ete enregistree avec succes.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class CEBUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = CEB
    form_class = CEBForm
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    permission_denied_message = "Vous pouvez uniquement modifier les CEB rattachees a votre province."
    success_url = reverse_lazy('schools:ceb_list')
    cancel_url = reverse_lazy('schools:ceb_list')
    page_title = 'Mettre a jour une CEB'
    page_intro = "Actualisez les informations administratives de cette CEB."
    success_message = 'La CEB a ete mise a jour avec succes.'

    def has_object_permission(self, obj):
        return self.request.user.can_manage_ceb(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class CEBDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = CEB
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    permission_denied_message = "Vous pouvez uniquement supprimer les CEB rattachees a votre province."
    success_url = reverse_lazy('schools:ceb_list')
    cancel_url = reverse_lazy('schools:ceb_list')
    page_title = 'Supprimer une CEB'
    page_intro = "Cette operation retire definitivement la CEB selectionnee de votre espace de gestion."
    delete_message = 'La CEB a ete supprimee avec succes.'

    def has_object_permission(self, obj):
        return self.request.user.can_manage_ceb(obj)


class SchoolCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = School
    form_class = SchoolForm
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    permission_denied_message = "Seuls les encadreurs pedagogiques sont habilites a enregistrer une ecole."
    cancel_url = reverse_lazy('schools:list')
    page_title = 'Enregistrer une ecole'
    page_intro = (
        "Renseignez les informations administratives de l'ecole. "
        "Le directeur pourra etre associe ulterieurement depuis le module de gestion des directeurs."
    )
    success_message = "L'ecole a ete enregistree avec succes."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('schools:detail', args=[self.object.pk])


class SchoolUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = School
    form_class = SchoolForm
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    permission_denied_message = "Vous pouvez uniquement modifier les ecoles rattachees a votre CEB."
    page_title = "Mettre a jour une ecole"
    page_intro = (
        "Actualisez les informations administratives de cette ecole. "
        "L'association avec un directeur se gere depuis le module de gestion des directeurs."
    )
    success_message = "L'ecole a ete mise a jour avec succes."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_school(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('schools:detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        self.cancel_url = reverse('schools:detail', args=[self.object.pk])
        return super().get_context_data(**kwargs)


class SchoolDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = School
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    permission_denied_message = "Vous pouvez uniquement supprimer les ecoles rattachees a votre CEB."
    success_url = reverse_lazy('schools:list')
    cancel_url = reverse_lazy('schools:list')
    page_title = "Supprimer l'ecole"
    page_intro = "Cette operation retire definitivement l'ecole selectionnee de votre espace de gestion."
    delete_message = "L'ecole a ete supprimee avec succes."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_school(obj)


class ProvinceEvaluationCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = ProvinceEvaluation
    form_class = ProvinceEvaluationForm
    allowed_roles = (User.Role.REGIONAL_AGENT, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('schools:province_list')
    cancel_url = reverse_lazy('schools:province_list')
    page_title = 'Enregistrer une evaluation de province'
    page_intro = "Saisissez l'evaluation administrative de la province selectionnee."
    success_message = "L'evaluation de la province a ete enregistree avec succes."

    def get_initial(self):
        initial = super().get_initial()
        province_id = self.request.GET.get('province')
        if province_id:
            initial['province'] = province_id
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.evaluator = self.request.user
        return super().form_valid(form)


class CEBEvaluationCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = CEBEvaluation
    form_class = CEBEvaluationForm
    allowed_roles = (User.Role.PROVINCIAL_USER, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('schools:ceb_list')
    cancel_url = reverse_lazy('schools:ceb_list')
    page_title = 'Enregistrer une evaluation de CEB'
    page_intro = "Saisissez l'evaluation administrative de la CEB selectionnee."
    success_message = "L'evaluation de la CEB a ete enregistree avec succes."

    def get_initial(self):
        initial = super().get_initial()
        ceb_id = self.request.GET.get('ceb')
        if ceb_id:
            initial['ceb'] = ceb_id
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.evaluator = self.request.user
        return super().form_valid(form)


class SchoolAdministrativeEvaluationCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = SchoolAdministrativeEvaluation
    form_class = SchoolAdministrativeEvaluationForm
    allowed_roles = (User.Role.PEDAGOGICAL_SUPERVISOR, User.Role.ADMINISTRATOR)
    success_url = reverse_lazy('schools:list')
    cancel_url = reverse_lazy('schools:list')
    page_title = "Enregistrer une evaluation d'ecole"
    page_intro = "Saisissez l'evaluation administrative de l'ecole selectionnee."
    success_message = "L'evaluation de l'ecole a ete enregistree avec succes."

    def get_initial(self):
        initial = super().get_initial()
        school_id = self.request.GET.get('school')
        if school_id:
            initial['school'] = school_id
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.evaluator = self.request.user
        return super().form_valid(form)
