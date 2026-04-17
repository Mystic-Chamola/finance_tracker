from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

class PaginatedListView(LoginRequiredMixin, ListView):
    """Base list view with pagination (20 items per page) and user filtering."""
    paginate_by = 20
    context_object_name = 'page_obj'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_obj'] = context.get('page_obj') or context.get('object_list')
        return context