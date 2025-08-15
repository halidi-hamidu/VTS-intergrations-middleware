from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('add-device/', views.add_device_view, name='add_device'),
    path('add-vehicle/', views.add_vehicle_view, name='add_vehicle'),
    path('get-unassigned-devices/', views.get_unassigned_devices, name='get_unassigned_devices'),
    path('delete-device/<int:device_id>/', views.delete_device_view, name='delete_device'),
    path('delete-vehicle/<int:vehicle_id>/', views.delete_vehicle_view, name='delete_vehicle'),
]
