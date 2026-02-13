from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # Division Views
    path('division/<str:division>/', views.DivisionUserListView.as_view(), name='division_users'),
    path('division/<str:division>/uploads/', views.DivisionUploadListView.as_view(), name='division_uploads'),
    path('division/<str:division>/export-pdf/', views.ExportDivisionPDFView.as_view(), name='export_division_pdf'),
    
    # Ward Analytics & Members (Parameters renamed for consistency)
    path('ward-detail/<str:div_name>/<str:ward_name>/', views.WardDetailView.as_view(), name='ward_detail'),
    path('ward/<str:div_name>/<str:ward_name>/members/', views.WardMembersListView.as_view(), name='ward_members'),
    path('ward/<str:div_name>/<str:ward_name>/uploads/', views.WardUploadsListView.as_view(), name='ward_uploads_list'),
    
    # Status Updates
    path('update-status/<int:report_id>/', views.UpdateWasteStatusView.as_view(), name='update_waste_status'),
    path('report/', views.ReportWasteView.as_view(), name='report_waste'),
    path('report/success/', views.ReportSuccessView.as_view(), name='report_success'),
    path('resident/dashboard/', views.ResidentDashboardView.as_view(), name='resident_dashboard'),
    path('reports/resident/dashboard/', views.ResidentDashboardView.as_view(), name='reports_resident_dashboard'),
    path('waste/update/<int:pk>/', views.ToggleWasteStatusView.as_view(), name='update_waste_status'),
    
]