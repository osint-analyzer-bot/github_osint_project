from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_scan_request, name='create_scan_request'),
    path('', views.scan_requests_list, name='scan_requests_list'),
    path('<int:pk>/', views.scan_request_detail, name='scan_request_detail'),
]