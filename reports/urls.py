from django.urls import path
from .import views

urlpatterns = [
    path('upload/', views.ReportWasteView.as_view(), name='report_waste'),
    path('mark-picked/<int:pk>/', views.mark_as_picked, name='mark_as_picked'),
    path('my-dashboard/', views.ResidentDashboardView.as_view(), name='reports_resident_dashboard'),
    
]