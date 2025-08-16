from django.urls import path
from .views import (UserListView, UserCreateView, 
                    UserUpdateView, UserDeleteView)
from . import views

app_name = 'frontend'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # devices paths
    path('device/', views.device_view, name='device'),
    
    # customers path
    path('customer/', views.customer_view, name='customer'),

    # vehicles paths
    # path('add-vehicle/', views.add_vehicle_view, name='add_vehicle'),
    path('delete-vehicle/<int:vehicle_id>/', views.delete_vehicle_view, name='delete_vehicle'),
    path('get-unassigned-devices/', views.get_unassigned_devices, name='get_unassigned_devices'),

    # skiping path
    path('skipping/', views.skipping_list, name='skipping'),
]

user_management_urlpatterns = [
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),
]

urlpatterns += user_management_urlpatterns