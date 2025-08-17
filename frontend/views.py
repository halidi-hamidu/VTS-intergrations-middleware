from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Count
from django.db import IntegrityError
from django_select2 import forms as s2forms
import json
from vehicles.forms import VehicleForm, CustomerForm,EditCustomerForm
from vehicles.models import Vehicle, DeviceImei,Customer
from data_reported.models import ReportedData


from django.urls import reverse_lazy
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import *
from .forms import *


def login_view(request):
    """Login page view"""
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('frontend:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'frontend/login.html')


def logout_view(request):
    """Logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('frontend:login')


@login_required
def dashboard_view(request):
    """Dashboard view with cards and data table"""
    # Get dashboard statistics
    total_devices = DeviceImei.objects.count()
    assigned_devices = Vehicle.objects.count()
    unassigned_devices = total_devices - assigned_devices
    total_vehicles = Vehicle.objects.count()
    
    # Get reported data statistics
    total_reported_data = ReportedData.objects.count()
    success_count = ReportedData.objects.filter(is_success=True).count()
    failed_count = ReportedData.objects.filter(is_success=False).count()
    
    # Get all reported data without pagination
    reported_data = ReportedData.objects.select_related('vehicle__imei').order_by('-created_at')
    
    context = {
        'total_devices': total_devices,
        'assigned_devices': assigned_devices,
        'unassigned_devices': unassigned_devices,
        'total_vehicles': total_vehicles,
        'total_reported_data': total_reported_data,
        'success_count': success_count,
        'failed_count': failed_count,
        'reported_data': reported_data,
    }
    
    return render(request, 'frontend/dashboard.html', context)

@login_required
@csrf_exempt
def device_view(request):
    """Add new device IMEI"""
    if request.method == 'POST' and "add_device_btn" in request.POST:
        try:
            imei_number = request.POST.get('deviceImei', '').strip()
            
            if not imei_number:
                messages.error(request, f"Device IMEI number is required")
                print(f"Device IMEI number is required")
                return redirect("frontend:device")
            
            if len(imei_number) != 15:
                messages.error(request, f"Device IMEI must be 15 digits")
                print(f"Device IMEI must be 15 digits")
                return redirect("frontend:device")
            
            if not imei_number.isdigit():
                messages.error(request, f"Device IMEI must contain only digits")
                print(f"Device IMEI must contain only digits")
                return redirect("frontend:device")
            
            # Check if IMEI already exists
            if DeviceImei.objects.filter(imei_number=imei_number).exists():
                messages.info(request, f"Device IMEI: {device.imei_number} already exists")
                print(f"Device IMEI: {device.imei_number} already exists")
                return redirect("frontend:device")
            
            # Create new device
            device = DeviceImei.objects.create(imei_number=imei_number)
            messages.success(request, f"Device {device.imei_number} added successfully")
            print(f"Device {device.imei_number} added successfully")
            return redirect("frontend:device")
            
        except json.JSONDecodeError:
            messages.error(request, f"Invalid device data")
            print(f"Invalid device data")
            return redirect("frontend:device")
        except Exception as e:
            messages.error(request, f"Invalid device data")
            print(f"{str(e)}")
            return redirect("frontend:device")

    if request.method == 'POST' and 'edit_device_btn' in request.POST:
        device_id = request.POST.get('device_id')
        new_imei = request.POST.get('deviceImei')

        # Validate input
        if not new_imei or len(new_imei) != 15 or not new_imei.isdigit():
            messages.error(request, "IMEI must be exactly 15 digits.")
            return redirect('frontend:device')

        # Check for duplicate IMEI
        if DeviceImei.objects.filter(imei_number=new_imei).exclude(id=device_id).exists():
            messages.error(request, "This IMEI number already exists.")
            return redirect('frontend:device')

        # Update the device
        device = get_object_or_404(DeviceImei, id=device_id)
        device.imei_number = new_imei
        device.save()

        messages.success(request, f"Device #{device.imei_number} updated successfully.")
        return redirect('frontend:device')

    if request.method == "POST" and 'delete_device_btn' in request.POST:
        device_id = request.POST.get('device_id')
        device = get_object_or_404(DeviceImei, id=device_id)
        device.delete()
        messages.success(request, f"Device deleted successfully.")
        return redirect('frontend:device')  # or wherever you want to redirect after deletion

    devices =  DeviceImei.objects.all().order_by("-created_at")
    templates = "frontend/device.html"
    context = {
        "devices":devices
    }
    return render(request, templates, context)

@login_required
def customer_view(request):
    # Handle POST requests
    if request.method == 'POST':
        # Add Customer
        if "add_customer_btn" in request.POST:
            form = CustomerForm(request.POST)
            if form.is_valid():
                try:
                    form.save()
                    messages.success(request, 'Customer added successfully!')
                    return redirect('frontend:customer')
                except Exception as e:
                    messages.error(request, f'Error saving customer: {str(e)}')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field.title()}: {error}")

        # Edit Customer
        elif 'edit_customer_btn' in request.POST:
            customer_id = request.POST.get('customer_id')
            try:
                customer = Customer.objects.get(pk=customer_id)
                form = EditCustomerForm(request.POST, instance=customer)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Customer updated successfully!')
                    return redirect('frontend:customer')
            except Customer.DoesNotExist:
                messages.error(request, 'Customer not found!')
                return redirect('frontend:customer')

        # Delete Customer
        elif "delete_cutomer_btn" in request.POST:
            customer_id = request.POST.get('customer_id')
            try:
                customer = Customer.objects.get(pk=customer_id)
                customer.delete()
                messages.success(request, 'Customer deleted successfully!')
                return redirect('frontend:customer')
            except Customer.DoesNotExist:
                messages.error(request, 'Customer not found!')
                return redirect('frontend:customer')
        
        # Add Project (AJAX)
        elif "add_project_btn" in request.POST:
            try:
                customer_id = request.POST.get('customer_id')
                imei_number = request.POST.get('imei_number')
                registration_number = request.POST.get('registration_number')

                # Validate required fields
                if not all([customer_id, imei_number, registration_number]):
                    messages.error(request, 'All fields are required')
                    return redirect('frontend:customer')

                # Get related objects
                customer = Customer.objects.get(id=customer_id)
                device = DeviceImei.objects.get(imei_number=imei_number)

                # Check for duplicates
                if Vehicle.objects.filter(registration_number=registration_number).exists():
                    messages.error(request, 'A project with this registration number already exists')
                    return redirect('frontend:customer')

                if Vehicle.objects.filter(imei=device).exists():
                    messages.error(request, 'This device is already assigned to another project')
                    return redirect('frontend:customer')

                # Create the project
                Vehicle.objects.create(
                    customer=customer,
                    imei=device,
                    registration_number=registration_number,
                )

                messages.success(request, 'Project created successfully')
                return redirect('frontend:customer')

            except Customer.DoesNotExist:
                messages.error(request, 'Customer not found')
                return redirect('frontend:customer')
            except DeviceImei.DoesNotExist:
                messages.error(request, 'Device not found')
                return redirect('frontend:customer')
            except IntegrityError:
                messages.error(request, 'Database error occurred')
                return redirect('frontend:customer')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
                return redirect('frontend:customer')
            
        # Handle Edit Project
        elif 'edit_project_btn' in request.POST:
            try:
                vehicle_id = request.POST.get('vehicle_id')
                customer_id = request.POST.get('customer_id')
                imei_number = request.POST.get('imei_number')
                registration_number = request.POST.get('registration_number')

                if not all([vehicle_id, customer_id, imei_number, registration_number]):
                    messages.error(request, 'All fields are required')
                    return redirect('frontend:customer')

                vehicle = Vehicle.objects.get(id=vehicle_id)
                customer = Customer.objects.get(id=customer_id)
                device = DeviceImei.objects.get(imei_number=imei_number)

                # Check for duplicate registration number (excluding current vehicle)
                if Vehicle.objects.filter(registration_number=registration_number).exclude(id=vehicle_id).exists():
                    messages.error(request, 'This registration number already exists')
                    return redirect('frontend:customer')

                # Check for duplicate device (excluding current vehicle)
                if Vehicle.objects.filter(imei=device).exclude(id=vehicle_id).exists():
                    messages.error(request, 'This device is already assigned to another project')
                    return redirect('frontend:customer')

                # Update the vehicle
                vehicle.registration_number = registration_number
                vehicle.imei = device
                vehicle.save()
                messages.success(request, f'Project {vehicle.registration_number} updated successfully')
                return redirect('frontend:customer')

            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
                return redirect('frontend:customer')
            
        elif 'delete_project_btn' in request.POST:
            try:
                vehicle_id = request.POST.get('vehicle_id')
                vehicle = Vehicle.objects.get(id=vehicle_id)
                
                vehicle.delete()
                messages.success(request, 'Project deleted successfully')
                return redirect('frontend:customer')
                
            except Vehicle.DoesNotExist:
                messages.error(request, 'Project not found')
                return redirect('frontend:customer')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
                return redirect('frontend:customer')
            
    # GET request handling
    devices = DeviceImei.objects.all().order_by("-created_at")
    customers = Customer.objects.all().order_by("-created_at")           
    customer_form = CustomerForm()
    vehicle_form = VehicleForm()
    vehicles = Vehicle.objects.all().order_by("-created_at")
    
    return render(request, 'frontend/customer.html', {
        "customer_form": customer_form,
        "customers": customers,
        "vehicle_form": vehicle_form,
        "devices": devices,
        "vehicles": vehicles
    })

@login_required
def skipping_list(request):
    # Get all skipping data with related vehicle info
    # skipping_data = ReportedData.objects.select_related('vehicle').all().order_by('-created_at')
    
    skipping_data = ReportedData.objects.filter(is_success = False).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(skipping_data, 25)  # Show 25 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Skipping Data',
        'page_obj': page_obj,
    }
    return render(request, 'frontend/skipping_list.html', context)

class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = CustomUser
    template_name = 'frontend/user_list.html'
    context_object_name = 'users'
    permission_required = 'auth.view_user'
    paginate_by = 10

    def get_queryset(self):
        return CustomUser.objects.all().order_by('-created_at')
    
class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'frontend/user_form.html'
    success_url = reverse_lazy('frontend:user_list')
    permission_required = 'auth.add_user'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"User {self.object.email} created successfully")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below")
        return super().form_invalid(form)

class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'frontend/user_form.html'
    success_url = reverse_lazy('frontend:user_list')
    permission_required = 'auth.change_user'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"User {self.object.email} updated successfully")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below")
        return super().form_invalid(form)

# class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
#     model = CustomUser
#     form_class = CustomUserCreationForm
#     template_name = 'frontend/user_form.html'
#     success_url = reverse_lazy('frontend:user_list')
#     permission_required = 'auth.add_user'

#     def form_valid(self, form):
#         response = super().form_valid(form)
#         # You can add additional logic here if needed
#         return response

# class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
#     model = CustomUser
#     form_class = CustomUserChangeForm
#     template_name = 'frontend/user_form.html'
#     success_url = reverse_lazy('frontend:user_list')
#     permission_required = 'auth.change_user'

class UserDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'frontend/user_confirm_delete.html'
    success_url = reverse_lazy('frontend:user_list')
    permission_required = 'auth.delete_user'


@login_required
def get_unassigned_devices(request):
    """Get list of unassigned IMEI devices"""
    unassigned_devices = DeviceImei.objects.filter(vehicle__isnull=True)
    devices_list = [
        {'id': device.id, 'imei_number': device.imei_number}
        for device in unassigned_devices
    ]
    return JsonResponse({'devices': devices_list})


@login_required
@csrf_exempt
def delete_vehicle_view(request, vehicle_id):
    """Delete a vehicle and unassign its IMEI device"""
    if request.method == 'DELETE':
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            vehicle_reg = vehicle.registration_number
            vehicle.delete()
            
            return JsonResponse({
                'success': True, 
                'message': f'Vehicle {vehicle_reg} deleted successfully'
            })
            
        except Vehicle.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Vehicle not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})
