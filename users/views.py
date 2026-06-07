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
from datetime import datetime

User = get_user_model()

# PDF Generation Imports
import io
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Internal Imports
from .forms import ResidentRegistrationForm
from .models import User

# 1. SHARED HIERARCHY DATA
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
                'user_count':    User.objects.filter(division=div, is_staff=False).count(),
                'total_reports': WasteReport.objects.filter(user__division=div).count(),
                'picked':        WasteReport.objects.filter(user__division=div, status='collected').count(),
                'pending':       WasteReport.objects.filter(user__division=div, status='pending').count(),
                'all_wards':     sorted(wards_dict.keys())
            }

        context['division_stats']        = div_data
        context['total_users']           = User.objects.filter(is_staff=False).count()
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
        div_name  = self.kwargs.get('div_name')
        ward_name = self.kwargs.get('ward_name')

        ward_reports   = WasteReport.objects.filter(user__division=div_name, user__ward=ward_name)
        ward_total     = ward_reports.count()
        ward_pending   = ward_reports.filter(status='pending').count()
        ward_collected = ward_reports.filter(status='picked').count()

        cells          = KABALE_HIERARCHY.get(div_name, {}).get(ward_name, [])
        cell_analytics = []

        for cell in cells:
            reports = ward_reports.filter(user__cell=cell).order_by('-created_at')
            for report in reports:
                report.google_map_url = f"https://www.google.com/maps?q={report.latitude},{report.longitude}"
            cell_analytics.append({
                'name':      cell,
                'total':     reports.count(),
                'pending':   reports.filter(status='pending').count(),
                'collected': reports.filter(status='picked').count(),
                'reports':   reports
            })

        context.update({
            'division':       div_name,
            'ward':           ward_name,
            'cell_analytics': cell_analytics,
            'ward_total':     ward_total,
            'ward_pending':   ward_pending,
            'ward_collected': ward_collected,
        })
        return context


class DivisionUserListView(UserPassesTestMixin, TemplateView):
    template_name = 'users/division_users.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        division_name      = self.kwargs.get('division')
        context['division'] = division_name
        context['users']    = User.objects.filter(division=division_name, is_staff=False)
        return context


class DivisionUploadListView(UserPassesTestMixin, ListView):
    model                = WasteReport
    template_name        = 'users/division_uploads.html'
    context_object_name  = 'reports'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        division_name = self.kwargs.get('division')
        return WasteReport.objects.filter(user__division=division_name).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['division'] = self.kwargs.get('division')
        return context


# ── PROFESSIONAL PDF REPORT ────────────────────────────────────────────────────
class ExportDivisionPDFView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, division):
        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=0.55 * inch,
            leftMargin=0.55 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.55 * inch,
        )

        # ── Colour palette ───────────────────────────────────────
        GREEN       = colors.HexColor('#1b5e20')
        LIGHT_GREEN = colors.HexColor('#e8f5e9')
        DARK_NAVY   = colors.HexColor('#0B132B')
        RED         = colors.HexColor('#b71c1c')
        LIGHT_RED   = colors.HexColor('#ffebee')
        GOLD        = colors.HexColor('#f5a623')
        GREY_HDR    = colors.HexColor('#37474f')
        WHITE       = colors.white
        LIGHT_GREY  = colors.HexColor('#f5f5f5')

        # ── Reusable paragraph styles ────────────────────────────
        def ps(name, **kw):
            """Shorthand ParagraphStyle factory."""
            return ParagraphStyle(name, **kw)

        title_style = ps('PDFTitle',
            fontSize=21, textColor=WHITE, alignment=TA_CENTER,
            fontName='Helvetica-Bold', leading=26)

        subtitle_style = ps('PDFSub',
            fontSize=11, textColor=GOLD, alignment=TA_CENTER,
            fontName='Helvetica', leading=16)

        meta_style = ps('PDFMeta',
            fontSize=8, textColor=colors.HexColor('#bbbbbb'),
            alignment=TA_CENTER, fontName='Helvetica', leading=12)

        section_style = ps('PDFSection',
            fontSize=13, textColor=WHITE, fontName='Helvetica-Bold',
            leading=18, leftIndent=6)

        note_style = ps('PDFNote',
            fontSize=8, textColor=colors.HexColor('#888888'),
            fontName='Helvetica-Oblique', alignment=TA_CENTER, leading=12)

        # ── Column config (shared by both tables) ────────────────
        col_headers = [
            '#', 'Resident Name', 'Username', 'Ward',
            'Cell', 'Location / Address', 'GPS Coordinates',
            'Date Reported', 'Status / Signature'
        ]
        col_widths = [
            0.30 * inch,   # #
            1.40 * inch,   # Resident Name
            0.90 * inch,   # Username
            1.05 * inch,   # Ward
            0.95 * inch,   # Cell
            2.05 * inch,   # Location
            1.45 * inch,   # GPS
            1.05 * inch,   # Date
            0.85 * inch,   # Status/Sig
        ]

        # Row-cell helper — keeps font size & line-height consistent
        def cell(text, bold=False, align=TA_LEFT, color=colors.black, size=7):
            return Paragraph(
                f"<b>{text}</b>" if bold else str(text),
                ps(f'rc_{id(text)}',
                   fontSize=size, fontName='Helvetica-Bold' if bold else 'Helvetica',
                   textColor=color, alignment=align, leading=size + 4)
            )

        def hdr_cell(text):
            return Paragraph(
                f"<b>{text}</b>",
                ps(f'hc_{text}',
                   fontSize=7, fontName='Helvetica-Bold',
                   textColor=WHITE, alignment=TA_CENTER, leading=11)
            )

        # ── Shared table style builder ────────────────────────────
        def data_table_style(header_color, alt_color):
            return TableStyle([
                # Header row
                ('BACKGROUND',    (0, 0), (-1, 0),  header_color),
                ('TEXTCOLOR',     (0, 0), (-1, 0),  WHITE),
                ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
                ('TOPPADDING',    (0, 0), (-1, 0),  10),
                ('BOTTOMPADDING', (0, 0), (-1, 0),  10),
                # Data rows
                ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, alt_color]),
                ('TOPPADDING',    (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING',   (0, 0), (-1, -1), 6),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
                ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#dddddd')),
                ('LINEBELOW',     (0, 0), (-1, 0),  1.2, header_color),
            ])

        # ── Section banner builder ───────────────────────────────
        def section_banner(text, bg_color):
            t = Table([[Paragraph(text, section_style)]], colWidths=[10 * inch])
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, -1), bg_color),
                ('TOPPADDING',    (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
                ('LEFTPADDING',   (0, 0), (-1, -1), 12),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
            ]))
            return t

        elements = []

        # ══════════════════════════════════════════════════════════
        # HEADER BANNER
        # ══════════════════════════════════════════════════════════
        header_data = [
            [Paragraph("Kabale Municipality — Clean Kabale Initiative", title_style)],
            [Paragraph(f"Waste Collection Manifest  ·  {division}", subtitle_style)],
            [Paragraph(
                f"Generated: {datetime.now().strftime('%A, %d %B %Y  at  %H:%M')}   |   "
                f"Printed by: {request.user.get_full_name() or request.user.username}",
                meta_style
            )],
        ]
        header_table = Table(header_data, colWidths=[10 * inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), DARK_NAVY),
            ('TOPPADDING',    (0, 0), (-1, 0),  18),
            ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
            ('TOPPADDING',    (0, 1), (-1, 1),  4),
            ('BOTTOMPADDING', (0, 1), (-1, 1),  6),
            ('TOPPADDING',    (0, 2), (-1, 2),  4),
            ('BOTTOMPADDING', (0, 2), (-1, 2),  16),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.30 * inch))

        # ══════════════════════════════════════════════════════════
        # SUMMARY STATISTICS
        # ══════════════════════════════════════════════════════════
        all_reports     = WasteReport.objects.filter(user__division=division)
        total           = all_reports.count()
        collected_qs    = all_reports.filter(status='collected')
        pending_qs      = all_reports.filter(status='pending')
        total_collected = collected_qs.count()
        total_pending   = pending_qs.count()
        pct_collected   = round((total_collected / total * 100), 1) if total else 0

        def stat_label(text, color=colors.black):
            return Paragraph(f"<b>{text}</b>",
                ps(f'sl_{text}', fontSize=8, alignment=TA_CENTER,
                   fontName='Helvetica-Bold', textColor=color, leading=12))

        def stat_value(text, color=colors.black):
            return Paragraph(f"<b>{text}</b>",
                ps(f'sv_{text}', fontSize=24, alignment=TA_CENTER,
                   fontName='Helvetica-Bold', textColor=color, leading=30))

        summary_data = [
            [stat_label("TOTAL REPORTS"),
             stat_label("COLLECTED", GREEN),
             stat_label("PENDING",   RED),
             stat_label("COMPLETION RATE")],
            [stat_value(str(total)),
             stat_value(str(total_collected), GREEN),
             stat_value(str(total_pending),   RED),
             stat_value(f"{pct_collected}%",  GOLD)],
        ]
        summary_table = Table(summary_data, colWidths=[2.5 * inch] * 4)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  GREY_HDR),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  WHITE),
            ('BACKGROUND',    (0, 1), (-1, 1),  LIGHT_GREY),
            ('GRID',          (0, 0), (-1, -1), 0.5, WHITE),
            ('TOPPADDING',    (0, 0), (-1, 0),  12),
            ('BOTTOMPADDING', (0, 0), (-1, 0),  12),
            ('TOPPADDING',    (0, 1), (-1, 1),  14),
            ('BOTTOMPADDING', (0, 1), (-1, 1),  14),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.40 * inch))

        # ══════════════════════════════════════════════════════════
        # SECTION 1 — COLLECTED
        # ══════════════════════════════════════════════════════════
        elements.append(section_banner("✅   COLLECTED WASTE REPORTS", GREEN))
        elements.append(Spacer(1, 0.14 * inch))

        if collected_qs.exists():
            c_data = [[hdr_cell(h) for h in col_headers]]
            for i, r in enumerate(
                collected_qs.select_related('user').order_by('user__ward', '-created_at'), 1
            ):
                location = r.location_address or f"{r.latitude}, {r.longitude}"
                gps = (
                    f"{round(float(r.latitude), 5)}, {round(float(r.longitude), 5)}"
                    if r.latitude and r.longitude else "N/A"
                )
                c_data.append([
                    cell(str(i),                                                   align=TA_CENTER),
                    cell(r.user.get_full_name() or r.user.username,                bold=True),
                    cell(r.user.username),
                    cell(r.user.ward  or '—'),
                    cell(r.user.cell  or '—'),
                    cell(location[:62] + ('…' if len(location) > 62 else '')),
                    cell(gps),
                    cell(r.created_at.strftime('%d/%m/%Y'),                        align=TA_CENTER),
                    cell("COLLECTED", bold=True, align=TA_CENTER, color=GREEN),
                ])
            c_table = Table(c_data, colWidths=col_widths, repeatRows=1)
            c_table.setStyle(data_table_style(GREEN, LIGHT_GREEN))
            elements.append(c_table)
        else:
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(Paragraph("No collected waste reports found for this division.", note_style))

        elements.append(Spacer(1, 0.45 * inch))

        # ══════════════════════════════════════════════════════════
        # SECTION 2 — PENDING
        # ══════════════════════════════════════════════════════════
        elements.append(section_banner("⏳   PENDING WASTE REPORTS", RED))
        elements.append(Spacer(1, 0.14 * inch))

        if pending_qs.exists():
            p_data = [[hdr_cell(h) for h in col_headers]]
            for i, r in enumerate(
                pending_qs.select_related('user').order_by('user__ward', '-created_at'), 1
            ):
                location = r.location_address or f"{r.latitude}, {r.longitude}"
                gps = (
                    f"{round(float(r.latitude), 5)}, {round(float(r.longitude), 5)}"
                    if r.latitude and r.longitude else "N/A"
                )
                p_data.append([
                    cell(str(i),                                                   align=TA_CENTER),
                    cell(r.user.get_full_name() or r.user.username,                bold=True),
                    cell(r.user.username),
                    cell(r.user.ward  or '—'),
                    cell(r.user.cell  or '—'),
                    cell(location[:62] + ('…' if len(location) > 62 else '')),
                    cell(gps),
                    cell(r.created_at.strftime('%d/%m/%Y'),                        align=TA_CENTER),
                    cell("________________",                                        align=TA_CENTER,
                         color=colors.HexColor('#999999')),
                ])
            p_table = Table(p_data, colWidths=col_widths, repeatRows=1)
            p_table.setStyle(data_table_style(RED, LIGHT_RED))
            elements.append(p_table)
        else:
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(Paragraph("No pending waste reports found for this division.", note_style))

        elements.append(Spacer(1, 0.45 * inch))

        # ══════════════════════════════════════════════════════════
        # FOOTER
        # ══════════════════════════════════════════════════════════
        elements.append(HRFlowable(width="100%", thickness=0.8, color=GREEN, spaceAfter=8))
        footer_data = [[
            Paragraph("Kabale Municipality Smart Waste Management System © 2026", note_style),
            Paragraph("Confidential — For Official Use Only", note_style),
        ]]
        footer_table = Table(footer_data, colWidths=[5 * inch, 5 * inch])
        footer_table.setStyle(TableStyle([
            ('ALIGN',         (0, 0), (0, 0), 'LEFT'),
            ('ALIGN',         (1, 0), (1, 0), 'RIGHT'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(footer_table)

        # ══════════════════════════════════════════════════════════
        # BUILD
        # ══════════════════════════════════════════════════════════
        doc.build(elements)
        buffer.seek(0)
        filename = (
            f"{division.replace(' ', '_')}_Manifest_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        return FileResponse(buffer, as_attachment=True, filename=filename)


class UpdateWasteStatusView(View):
    def post(self, request, report_id):
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
        return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))


class WardMembersListView(ListView):
    model               = User
    template_name       = 'ward_members.html'
    context_object_name = 'members'

    def get_queryset(self):
        div_name  = self.kwargs.get('div_name')
        ward_name = self.kwargs.get('ward_name')
        print(f"DEBUG: Division: {div_name}, Ward: {ward_name}")
        if not div_name or not ward_name:
            return User.objects.none()
        return User.objects.filter(
            division=div_name, ward=ward_name, is_staff=False
        ).order_by('username')


class WardUploadsListView(UserPassesTestMixin, ListView):
    model               = WasteReport
    template_name       = 'users/ward_uploads.html'
    context_object_name = 'reports'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        div_name  = self.kwargs.get('div_name')
        ward_name = self.kwargs.get('ward_name')
        return WasteReport.objects.filter(
            user__division=div_name, user__ward=ward_name
        ).select_related('user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['division'] = self.kwargs.get('div_name')
        context['ward']     = self.kwargs.get('ward_name')
        return context


class ReportWasteView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model         = WasteReport
    form_class    = WasteReportForm
    template_name = 'reports/report_waste.html'
    success_url   = reverse_lazy('resident_dashboard')
    success_message = "Waste report submitted successfully! Our team has been notified."

    def form_valid(self, form):
        form.instance.user   = self.request.user
        form.instance.status = 'pending'
        response = super().form_valid(form)
        self.notify_admin(form.instance)
        return response

    def notify_admin(self, report):
        ward_name = getattr(report.user, 'ward', 'Unspecified')
        subject   = f"🚨 New Waste Report: {ward_name} Ward"
        location  = report.location_address if report.location_address else f"GPS: {report.latitude}, {report.longitude}"
        message   = (
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
    model               = WasteReport
    template_name       = 'reports/resident_dashboard.html'
    context_object_name = 'my_reports'

    def get_queryset(self):
        return WasteReport.objects.filter(user=self.request.user).order_by('-created_at')


class ToggleWasteStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        report = get_object_or_404(WasteReport, pk=pk)
        action = request.POST.get('action')
        if action == "confirm":
            report.status = 'collected'
            report.save()
            send_custom_email(
                subject="♻️ Waste Collection Confirmed",
                recipient_email=report.user.email,
                message_body=(
                    f"Hello {report.user.first_name or report.user.username},\n\n"
                    f"We have confirmed the collection of waste at {report.location_address}.\n"
                    f"Thank you for keeping Kabale clean!"
                )
            )
            messages.success(request, f"Report marked as collected and {report.user.username} notified.")
        elif action == "undo":
            report.status = 'pending'
            report.save()
            messages.info(request, "Status reverted to pending.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin_dashboard')))


class SendMessageView(LoginRequiredMixin, View):
    def post(self, request, report_id):
        report = get_object_or_404(WasteReport, id=report_id, user=request.user)
        body   = request.POST.get('body', '').strip()
        if not body:
            messages.error(request, "Message cannot be empty.")
            return redirect(request.META.get('HTTP_REFERER', 'resident_dashboard'))
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            messages.error(request, "No admin available. Please try again later.")
            return redirect('resident_dashboard')
        Message.objects.create(report=report, sender=request.user, recipient=admin_user, body=body)
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
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, report_id):
        report = get_object_or_404(WasteReport, id=report_id)
        body   = request.POST.get('body', '').strip()
        if not body:
            messages.error(request, "Reply cannot be empty.")
            return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))
        Message.objects.create(report=report, sender=request.user, recipient=report.user, body=body)
        Message.objects.filter(report=report, recipient=request.user, is_read=False).update(is_read=True)
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
    template_name = 'users/admin_inbox.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reports_with_messages = (
            WasteReport.objects
            .filter(messages__isnull=False)
            .distinct()
            .select_related('user')
            .prefetch_related('messages__sender')
            .order_by('-messages__created_at')
        )
        inbox = []
        for report in reports_with_messages:
            unread = report.messages.filter(recipient=self.request.user, is_read=False).count()
            inbox.append({'report': report, 'unread': unread})
        context['inbox']        = inbox
        context['total_unread'] = sum(i['unread'] for i in inbox)
        return context


class AdminRegisterView(SuccessMessageMixin, CreateView):
    template_name   = 'users/admin_register.html'
    form_class      = AdminRegistrationForm
    success_url     = reverse_lazy('login')
    success_message = "Admin account created successfully! You can now log in."