from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import WasteReport
from .models import WasteReport

# Resident View: Upload Waste Photo and Location
class ReportWasteView(LoginRequiredMixin, CreateView):
    model = WasteReport
    template_name = 'reports/report_waste.html'
    fields = ['image', 'latitude', 'longitude', 'location_address']
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

# Admin Action: Mark waste as collected
def mark_as_picked(request, pk):
    if request.user.is_staff:
        report = get_object_or_404(WasteReport, pk=pk)
        report.status = 'picked'
        report.save()
    return redirect('admin_dashboard')


class ResidentDashboardView(LoginRequiredMixin, ListView):
    model = WasteReport
    template_name = 'reports/resident_dashboard.html'
    context_object_name = 'my_reports'

    def get_queryset(self):
        # Only show reports created by the logged-in user
        return WasteReport.objects.filter(user=self.request.user).order_by('-created_at')