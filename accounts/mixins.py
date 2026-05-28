from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()
    permission_denied_message = "Vous n'avez pas l'autorisation d'effectuer cette action."

    def test_func(self):
        return self.request.user.has_role(*self.allowed_roles)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(self.get_permission_denied_message())
        return super().handle_no_permission()


class FormPageMixin:
    template_name = 'shared/object_form.html'
    page_title = ''
    page_intro = ''
    submit_label = 'Enregistrer'
    cancel_url = None
    success_message = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = self.page_title
        context['form_intro'] = self.page_intro
        context['submit_label'] = self.submit_label
        context['cancel_url'] = self.cancel_url
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response


class DeletePageMixin:
    template_name = 'shared/object_confirm_delete.html'
    page_title = ''
    page_intro = ''
    delete_message = ''
    cancel_url = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = self.page_title
        context['form_intro'] = self.page_intro
        context['cancel_url'] = self.cancel_url
        return context

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        if self.delete_message:
            messages.success(request, self.delete_message)
        return response


class ObjectPermissionMixin:
    permission_denied_message = "Vous n'avez pas l'autorisation d'effectuer cette action."

    def has_object_permission(self, obj):
        return False

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not self.has_object_permission(obj):
            raise PermissionDenied(self.permission_denied_message)
        return obj
