from django.urls import reverse, reverse_lazy
from .forms import ResidentRegistrationForm, AdminRegistrationForm
from .models import Message
from django.views.generic import CreateView, TemplateView, ListView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import render
from django.db.models import Count, Q
from django.views import View
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from .utils import send_custom_email
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import WasteReport
from .forms import WasteReportForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponseRedirect



User = get_user_model()



# PDF Generation Imports
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

# Internal Imports
from .forms import ResidentRegistrationForm
from .models import User

# 1. SHARED HIERARCHY DATA
# Centralized to ensure all divisions (Central, Southern, Northern) work across all views
KABALE_HIERARCHY = {
    "Central Division": {
        "Nyabikoni": ["Kanyakiriro", "Rutoma", "Rutooma Upper", "Rutooma Lower", "Nyabikoni Central"],
        "Kigongi": ["Kigongi A", "Kigongi B", "Nyakahita"],
        "Central": ["Makanga", "Garage Street", "Rwakaraba", "Main Street", "Town Centre"],
        "Butobere": ["Butobere", "Kijurera", "Kashaki", "Rugarama Rd"]
    },
    "Southern Division": {
        "Karubanda Ward": ["Rwagaana", "Rwehuye"],
        "Kirigime Ward": ["Bataka", "Central", "Kabale N.T.C", "Kamukira", "Kekuubo", "Rushambya"],
        "Mwanjari Ward": ["Igabiro", "Kikungiri", "Ndorwa", "Nyakabungo", "Nyakiharo", "Nyangande", "Rwagaana/Kamatojo", "Rwamukundi"],
        "Rushaki Ward": ["Nyamabare", "Nyarukokoromi", "Omwibare", "Rugyendeira", "Ruhita", "Rushaki"]
    },
    "Northern Division": {
        "Kikungiri Ward": ["Kikungiri Upper", "Kikungiri Lower", "Rwakaraba", "Kabaraga", "Karubanda"],
        "Kijuguta Ward": ["Kijuguta Central", "Nyakihanga", "Kijuguta Upper", "Kijuguta Lower"],
        "Kirigime Ward": ["Kirigime A", "Kirigime B", "Nyakabungo", "Butobere"],
        "Kyanamira Ward": ["Kyanamira Central", "Nyabikoni", "Hamurwa Road Cell", "Nyamwegabira"]
    }
}

class RegisterView(SuccessMessageMixin, CreateView):
    template_name = 'users/register.html'
    form_class = ResidentRegistrationForm
    success_url = reverse_lazy('login')
    success_message = "Your account was created successfully! You can now login."

class UserLoginView(LoginView):
    template_name = 'users/login.html'
    def get_success_url(self):
        if self.request.user.is_staff:
            return reverse('admin_dashboard')
        return reverse('resident_dashboard')

class UserLogoutView(LogoutView):
    next_page = 'home'

class AdminDashboardView(UserPassesTestMixin, TemplateView):
    template_name = 'users/admin_dashboard.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        div_data = {}
        
        for div, wards_dict in KABALE_HIERARCHY.items():
            div_data[div] = {
                'user_count': User.objects.filter(division=div, is_staff=False).count(),
                'total_reports': WasteReport.objects.filter(user__division=div).count(),
                'picked': WasteReport.objects.filter(user__division=div, status='collected').count(),  # FIXED: was 'picked'
                'pending': WasteReport.objects.filter(user__division=div, status='pending').count(),
                'all_wards': sorted(wards_dict.keys())
            }
        
        context['division_stats'] = div_data
        context['total_users'] = User.objects.filter(is_staff=False).count()

        # Unread message badge for the nav and dashboard
        context['total_unread_messages'] = Message.objects.filter(
            recipient=self.request.user, is_read=False
        ).count()

        return context


class WardDetailView(UserPassesTestMixin, TemplateView):
    template_name = 'users/ward_detail.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        div_name = self.kwargs.get('div_name')
        ward_name = self.kwargs.get('ward_name') 

        # 1. Fetch all reports for this ward once to calculate summary stats
        ward_reports = WasteReport.objects.filter(
            user__division=div_name, 
            user__ward=ward_name
        )

        # 2. Calculate Top-Level Ward Stats
        ward_total = ward_reports.count()
        ward_pending = ward_reports.filter(status='pending').count()
        ward_collected = ward_reports.filter(status='picked').count()

        # 3. Cell-by-Cell Breakdown
        cells = KABALE_HIERARCHY.get(div_name, {}).get(ward_name, [])
        cell_analytics = [] 
        
        for cell in cells:
            # Filter reports specific to this cell
            reports = ward_reports.filter(user__cell=cell).order_by('-created_at')

            # Add navigation links for the Admin to each report
            for report in reports:
                report.google_map_url = f"https://www.google.com/maps?q={report.latitude},{report.longitude}"

            cell_analytics.append({
                'name': cell,
                'total': reports.count(),
                'pending': reports.filter(status='pending').count(),
                'collected': reports.filter(status='picked').count(),
                'reports': reports 
            })

        # 4. Update Context
        context.update({
            'division': div_name,
            'ward': ward_name, 
            'cell_analytics': cell_analytics,
            'ward_total': ward_total,
            'ward_pending': ward_pending,
            'ward_collected': ward_collected,
        })
        return context        

    
class DivisionUserListView(UserPassesTestMixin, TemplateView):
    template_name = 'users/division_users.html'
    def test_func(self):
        return self.request.user.is_staff
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Capture the raw string from URL (e.g., "Central Division")
        division_name = self.kwargs.get('division') 
        context['division'] = division_name
        context['users'] = User.objects.filter(division=division_name, is_staff=False)
        return context
    


class DivisionUploadListView(UserPassesTestMixin, ListView):
    model = WasteReport
    template_name = 'users/division_uploads.html'
    context_object_name = 'reports'
    def test_func(self):
        return self.request.user.is_staff
    def get_queryset(self):
        division_name = self.kwargs.get('division')
        return WasteReport.objects.filter(user__division=division_name).order_by('-created_at')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['division'] = self.kwargs.get('division')
        return context

class ExportDivisionPDFView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff
    def get(self, request, division):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph(f"Waste Collection Manifest: {division}", styles['Title']))
        elements.append(Paragraph("Kabale Municipality - Clean Kabale Initiative", styles['Normal']))
        elements.append(Paragraph("<br/><br/>", styles['Normal']))

        reports = WasteReport.objects.filter(user__division=division, status='pending')
        data = [['Resident', 'Ward', 'Cell', 'Status', 'Signature']]
        
        for r in reports:
            data.append([
                r.user.full_name or r.user.username,
                r.user.ward,
                r.user.cell,
                r.status.upper(),
                "________________"
            ])

        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f'{division}_manifest.pdf')
    



class UpdateWasteStatusView(View):
    """
    Handles toggling waste collection status between Pending and Picked.
    """
    def post(self, request, report_id):
        # Ensure only admins can perform this action
        if not request.user.is_staff:
            return redirect('home')
            
        report = get_object_or_404(WasteReport, id=report_id)
        action = request.POST.get('action')
        
        if action == 'confirm':
            report.status = 'picked'
            messages.success(request, f"Collection for {report.user.username} confirmed!")
        elif action == 'undo':
            report.status = 'pending'
            messages.info(request, f"Collection for {report.user.username} reverted to pending.")
            
        report.save()
        # Returns the admin to the specific ward/cell they were viewing
        return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))    
    


# class CellMembersView(ListView):
#     model = User
#     template_name = 'cell_members.html'
#     context_object_name = 'members'

#     def get_queryset(self):
#         # Captures ward and cell from the URL parameters
#         ward = self.kwargs.get('ward_name')
#         cell = self.kwargs.get('cell_name')
#         # Filters users who match both the ward and cell exactly
#         return User.objects.filter(ward=ward, cell=cell).order_by('username')

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['ward'] = self.kwargs.get('ward_name')
#         context['cell'] = self.kwargs.get('cell_name')
#         return context    
    


class WardMembersListView(ListView):
    model = User
    template_name = 'ward_members.html'
    context_object_name = 'members'

    def get_queryset(self):
        div_name = self.kwargs.get('div_name')
        ward_name = self.kwargs.get('ward_name')
        
        # Log these to your console to see what is actually being passed
        print(f"DEBUG: Division: {div_name}, Ward: {ward_name}")
        
        if not div_name or not ward_name:
            return User.objects.none()

        return User.objects.filter(
            division=div_name, 
            ward=ward_name,
            is_staff=False # Usually you don't want to list admins here
        ).order_by('username')


class WardUploadsListView(UserPassesTestMixin, ListView):
    model = WasteReport
    template_name = 'users/ward_uploads.html'
    context_object_name = 'reports'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        div_name = self.kwargs.get('div_name')
        ward_name = self.kwargs.get('ward_name')
        # Ensure we filter by division AND ward to isolate data
        return WasteReport.objects.filter(
            user__division=div_name,
            user__ward=ward_name
        ).select_related('user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['division'] = self.kwargs.get('div_name')
        context['ward'] = self.kwargs.get('ward_name')
        return context



class ReportWasteView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = WasteReport
    form_class = WasteReportForm
    template_name = 'reports/report_waste.html'
    success_url = reverse_lazy('resident_dashboard')
    success_message = "Waste report submitted successfully! Our team has been notified."

    def form_valid(self, form):
        # 1. Attach user and default status
        form.instance.user = self.request.user
        form.instance.status = 'pending'
        
        # 2. Save to DB (this triggers the SuccessMessageMixin)
        response = super().form_valid(form)
        
        # 3. Notify Admin after successful save
        self.notify_admin(form.instance)
        
        return response

    def notify_admin(self, report):
        """Builds the context and sends the email via utils."""
        # Use ward from user profile if it exists
        ward_name = getattr(report.user, 'ward', 'Unspecified')
        subject = f"🚨 New Waste Report: {ward_name} Ward"
        
        # Determine the best location string to send to admin
        location = report.location_address if report.location_address else f"GPS: {report.latitude}, {report.longitude}"
        
        message = (
            f"Hello Admin,\n\n"
            f"A new waste report has been uploaded and is pending collection.\n\n"
            f"REPORT DETAILS:\n"
            f"--------------------------\n"
            f"Resident: {report.user.get_full_name() or report.user.username}\n"
            f"Ward: {ward_name}\n"
            f"Location: {location}\n"
            f"Time: {report.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"--------------------------\n\n"
            f"View full details on the Admin Dashboard: {self.request.build_absolute_uri('/')}"
        )
        
        send_custom_email(
            subject=subject,
            recipient_email=settings.ADMIN_EMAIL,
            message_body=message
        )

        
class ReportSuccessView(TemplateView):
    template_name = 'reports/report_success.html'    



class ResidentDashboardView(LoginRequiredMixin, ListView):
    model = WasteReport
    template_name = 'reports/resident_dashboard.html'
    context_object_name = 'my_reports'

    def get_queryset(self):
        # Only show reports belonging to the logged-in resident
        return WasteReport.objects.filter(user=self.request.user).order_by('-created_at')
    

class ToggleWasteStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        report = get_object_or_404(WasteReport, pk=pk)
        action = request.POST.get('action')

        if action == "confirm":
            report.status = 'collected'
            report.save()
            
            # Notify Resident using the utility function
            res_subject = "♻️ Waste Collection Confirmed"
            res_message = (
                f"Hello {report.user.first_name or report.user.username},\n\n"
                f"We have confirmed the collection of waste at {report.location_address}.\n"
                f"Thank you for keeping Kabale clean!"
            )
            send_custom_email(res_subject, report.user.email, res_message)
            messages.success(request, f"Report marked as collected and {report.user.username} notified.")
            
        elif action == "undo":
            report.status = 'pending'
            report.save()
            messages.info(request, "Status reverted to pending.")

        # FIX: Redirect back to the page the admin was just on (Ward Detail page)
        # This prevents the NoReverseMatch error by not requiring explicit URL arguments
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin_dashboard')))


class SendMessageView(LoginRequiredMixin, View):
    """Resident sends a message about a specific report."""
    def post(self, request, report_id):
        report = get_object_or_404(WasteReport, id=report_id, user=request.user)
        body = request.POST.get('body', '').strip()

        if not body:
            messages.error(request, "Message cannot be empty.")
            return redirect(request.META.get('HTTP_REFERER', 'resident_dashboard'))

        # Find the first admin user to receive the message
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            messages.error(request, "No admin available. Please try again later.")
            return redirect('resident_dashboard')

        Message.objects.create(
            report=report,
            sender=request.user,
            recipient=admin_user,
            body=body
        )

        # Notify admin by email
        send_custom_email(
            subject=f"💬 New message from {request.user.username} | Report #{report.id}",
            recipient_email=admin_user.email,
            message_body=(
                f"Hello Admin,\n\n"
                f"{request.user.get_full_name() or request.user.username} has sent you a message "
                f"regarding their waste report (ID: {report.id}).\n\n"
                f"Message:\n\"{body}\"\n\n"
                f"Location: {report.location_address or f'{report.latitude}, {report.longitude}'}\n\n"
                f"Log in to the admin dashboard to reply."
            )
        )

        messages.success(request, "Your message was sent to the admin.")
        return redirect('resident_dashboard')


class AdminReplyMessageView(UserPassesTestMixin, View):
    """Admin replies to a resident's message from any admin page."""
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, report_id):
        report = get_object_or_404(WasteReport, id=report_id)
        body = request.POST.get('body', '').strip()

        if not body:
            messages.error(request, "Reply cannot be empty.")
            return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))

        Message.objects.create(
            report=report,
            sender=request.user,
            recipient=report.user,
            body=body
        )

        # Mark all resident messages on this report as read
        Message.objects.filter(report=report, recipient=request.user, is_read=False).update(is_read=True)

        # Notify resident by email
        send_custom_email(
            subject=f"📩 Admin replied to your waste report #{report.id}",
            recipient_email=report.user.email,
            message_body=(
                f"Hello {report.user.first_name or report.user.username},\n\n"
                f"The Kabale Municipality admin has replied to your waste report.\n\n"
                f"Message:\n\"{body}\"\n\n"
                f"Log in to your dashboard to view the full conversation."
            )
        )

        messages.success(request, f"Reply sent to {report.user.username}.")
        return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))


class AdminInboxView(UserPassesTestMixin, TemplateView):
    """Admin sees all open conversations grouped by report."""
    template_name = 'users/admin_inbox.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all reports that have at least one message
        reports_with_messages = (
            WasteReport.objects
            .filter(messages__isnull=False)
            .distinct()
            .select_related('user')
            .prefetch_related('messages__sender')
            .order_by('-messages__created_at')
        )

        # Annotate unread count per report
        inbox = []
        for report in reports_with_messages:
            unread = report.messages.filter(recipient=self.request.user, is_read=False).count()
            inbox.append({'report': report, 'unread': unread})

        context['inbox'] = inbox
        context['total_unread'] = sum(i['unread'] for i in inbox)
        return context


class AdminRegisterView(SuccessMessageMixin, CreateView):
    template_name = 'users/admin_register.html'
    form_class = AdminRegistrationForm
    success_url = reverse_lazy('login')
    success_message = "Admin account created successfully! You can now log in."        