from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import DeletePageMixin, FormPageMixin, ObjectPermissionMixin, RoleRequiredMixin
from accounts.models import User
from accounts.scopes import filter_activities_for_user, filter_recommendations_for_user, filter_schools_for_user
from schools.models import School

from .forms import ActivityForm, ActivityMediaForm, ActivityReportForm
from .models import Activity, ActivityMedia, Innovation, Recommendation
from .reporting import build_activity_report_context, build_activity_report_pdf_response


class ActivityListView(LoginRequiredMixin, ListView):
    model = Activity
    context_object_name = 'activities'
    template_name = 'innovations/activity_list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = filter_activities_for_user(
            self.request.user,
            Activity.objects.select_related(
                'school',
                'school__province',
                'school__province__region',
                'school__ceb',
                'innovation',
                'created_by',
            ),
        )
        innovation_id = self.request.GET.get('innovation')
        school_id = self.request.GET.get('school')

        if innovation_id:
            queryset = queryset.filter(innovation_id=innovation_id)
        if school_id:
            queryset = queryset.filter(school_id=school_id)

        return queryset.annotate(media_total=Count('media_items', distinct=True)).order_by(
            '-reporting_date',
            '-created_at',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['innovations'] = Innovation.objects.filter(is_active=True)
        context['schools'] = filter_schools_for_user(
            self.request.user,
            School.objects.order_by('name'),
        )
        context['selected_innovation'] = self.request.GET.get('innovation', '')
        context['selected_school'] = self.request.GET.get('school', '')
        return context


class RecommendationListView(LoginRequiredMixin, ListView):
    model = Recommendation
    context_object_name = 'recommendations'
    template_name = 'innovations/recommendation_list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = filter_recommendations_for_user(
            self.request.user,
            Recommendation.objects.select_related('school', 'school__province', 'innovation'),
        )
        priority = self.request.GET.get('priority')
        status = self.request.GET.get('status')

        if priority:
            queryset = queryset.filter(priority=priority)
        if status:
            queryset = queryset.filter(status=status)

        return queryset


@method_decorator(never_cache, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class ActivityDetailView(LoginRequiredMixin, DetailView):
    model = Activity
    context_object_name = 'activity'
    template_name = 'innovations/activity_detail.html'

    def get_queryset(self):
        return filter_activities_for_user(
            self.request.user,
            Activity.objects.select_related('school', 'school__province', 'school__ceb', 'innovation', 'created_by'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.object
        can_manage_activity = self.request.user.can_manage_activity(activity)
        context['media_items'] = activity.media_items.select_related('uploaded_by').order_by('-created_at')
        context['can_manage_activity_here'] = can_manage_activity
        context['media_form'] = kwargs.get('media_form') or ActivityMediaForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.user.can_manage_activity(self.object):
            raise PermissionDenied(
                "Seuls l'administrateur et le directeur de l'école concernée peuvent ajouter des pièces justificatives."
            )

        media_form = ActivityMediaForm(request.POST, request.FILES)
        if media_form.is_valid():
            media_item = media_form.save(commit=False)
            media_item.activity = self.object
            media_item.uploaded_by = request.user
            media_item.save()
            messages.success(
                request,
                "Le média de l'activité a été ajouté avec succès et reste visible pour tous les utilisateurs autorisés.",
            )
            return HttpResponseRedirect(self.request.path)

        context = self.get_context_data(media_form=media_form)
        return self.render_to_response(context)


class ActivityCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = Activity
    form_class = ActivityForm
    allowed_roles = (User.Role.ADMINISTRATOR, User.Role.SCHOOL_DIRECTOR)
    permission_denied_message = (
        "Seuls l'administrateur et le directeur d'école sont habilités à enregistrer une activité."
    )
    success_url = reverse_lazy('innovations:activity_list')
    cancel_url = reverse_lazy('innovations:activity_list')
    page_title = 'Enregistrer une activité'
    page_intro = (
        "Renseignez les informations relatives à l'activité à déclarer dans votre zone d'action."
    )
    success_message = "L'activité a été enregistrée avec succès."

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
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ActivityUpdateView(RoleRequiredMixin, ObjectPermissionMixin, FormPageMixin, UpdateView):
    model = Activity
    form_class = ActivityForm
    allowed_roles = (User.Role.ADMINISTRATOR, User.Role.SCHOOL_DIRECTOR)
    permission_denied_message = (
        "Seuls l'administrateur et le directeur de l'école concernée peuvent modifier cette activité."
    )
    success_url = reverse_lazy('innovations:activity_list')
    cancel_url = reverse_lazy('innovations:activity_list')
    page_title = "Mettre à jour une activité"
    page_intro = "Actualisez les informations relatives à cette activité."
    success_message = "L'activité a été mise à jour avec succès."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_activity(obj)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class ActivityDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = Activity
    allowed_roles = (User.Role.ADMINISTRATOR, User.Role.SCHOOL_DIRECTOR)
    permission_denied_message = (
        "Seuls l'administrateur et le directeur de l'école concernée peuvent supprimer cette activité."
    )
    success_url = reverse_lazy('innovations:activity_list')
    cancel_url = reverse_lazy('innovations:activity_list')
    page_title = "Supprimer une activité"
    page_intro = "Cette opération retire définitivement l'activité sélectionnée."
    delete_message = "L'activité a été supprimée avec succès."

    def has_object_permission(self, obj):
        return self.request.user.can_manage_activity(obj)


class ActivityMediaCreateView(RoleRequiredMixin, FormPageMixin, CreateView):
    model = ActivityMedia
    form_class = ActivityMediaForm
    allowed_roles = (User.Role.ADMINISTRATOR, User.Role.SCHOOL_DIRECTOR)
    success_url = reverse_lazy('innovations:activity_list')
    cancel_url = reverse_lazy('innovations:activity_list')
    page_title = "Ajouter un média d'activité"
    page_intro = "Ajoutez une pièce justificative et son commentaire associé."
    success_message = "Le média de l'activité a été ajouté avec succès."
    permission_denied_message = (
        "Seuls l'administrateur et le directeur de l'école concernée peuvent ajouter des pièces justificatives."
    )

    def dispatch(self, request, *args, **kwargs):
        self.activity = get_object_or_404(
            Activity.objects.select_related('school', 'school__province', 'school__ceb'),
            pk=kwargs['activity_pk'],
        )
        if not request.user.can_manage_activity(self.activity):
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        self.cancel_url = reverse_lazy('innovations:activity_detail', kwargs={'pk': self.activity.pk})
        context = super().get_context_data(**kwargs)
        context['activity'] = self.activity
        return context

    def form_valid(self, form):
        form.instance.activity = self.activity
        form.instance.uploaded_by = self.request.user
        self.success_url = reverse_lazy('innovations:activity_detail', kwargs={'pk': self.activity.pk})
        return super().form_valid(form)


class ActivityMediaDeleteView(RoleRequiredMixin, ObjectPermissionMixin, DeletePageMixin, DeleteView):
    model = ActivityMedia
    allowed_roles = (User.Role.ADMINISTRATOR, User.Role.SCHOOL_DIRECTOR)
    page_title = "Supprimer un média d'activité"
    page_intro = "Cette opération retire définitivement le média sélectionné."
    delete_message = "Le média de l'activité a été supprimé avec succès."
    permission_denied_message = (
        "Seuls l'administrateur et le directeur de l'école concernée peuvent supprimer ce média."
    )

    def has_object_permission(self, obj):
        return self.request.user.can_manage_activity(obj.activity)

    def get_success_url(self):
        return reverse_lazy('innovations:activity_detail', kwargs={'pk': self.object.activity_id})

    def get_context_data(self, **kwargs):
        self.cancel_url = reverse_lazy('innovations:activity_detail', kwargs={'pk': self.object.activity_id})
        return super().get_context_data(**kwargs)


@login_required
def activity_report_center(request):
    has_query = 'report_kind' in request.GET or 'activity' in request.GET
    form = ActivityReportForm(request.GET or None, user=request.user)
    report_preview = None
    pdf_url = ''

    if has_query and form.is_valid():
        report_preview = build_activity_report_context(request.user, form.cleaned_data)
        pdf_url = f"{reverse_lazy('innovations:activity_report_pdf')}?{request.GET.urlencode()}"

    context = {
        'page_title': "Centre de rapports d'activités",
        'page_intro': (
            "Préparez une synthèse détaillée par activité ou un rapport consolidé sur l'ensemble de votre zone d'action."
        ),
        'report_scope': build_activity_report_context(
            request.user,
            {'report_kind': ActivityReportForm.ReportKind.GENERAL},
        )['metadata'],
        'form': form,
        'report_preview': report_preview,
        'pdf_url': pdf_url,
        'has_query': has_query,
    }
    return render(request, 'innovations/activity_report.html', context)


@login_required
def activity_report_pdf(request):
    form = ActivityReportForm(request.GET or None, user=request.user)
    if not form.is_valid():
        return HttpResponseBadRequest("Les paramètres de génération du rapport sont invalides.")

    report_context = build_activity_report_context(request.user, form.cleaned_data)
    return build_activity_report_pdf_response(report_context)
