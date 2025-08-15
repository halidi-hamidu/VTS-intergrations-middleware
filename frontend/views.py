from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Count
import json

from vehicles.models import Vehicle, DeviceImei
from data_reported.models import ReportedData


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
    
    # Get recent reported data with pagination
    reported_data = ReportedData.objects.select_related('vehicle__imei').order_by('-created_at')
    paginator = Paginator(reported_data, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'total_devices': total_devices,
        'assigned_devices': assigned_devices,
        'unassigned_devices': unassigned_devices,
        'total_vehicles': total_vehicles,
        'total_reported_data': total_reported_data,
        'success_count': success_count,
        'failed_count': failed_count,
        'reported_data': page_obj,
    }
    
    return render(request, 'frontend/dashboard.html', context)


@login_required
@csrf_exempt
def add_device_view(request):
    """Add new device IMEI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            imei_number = data.get('imei_number', '').strip()
            
            if not imei_number:
                return JsonResponse({'success': False, 'error': 'IMEI number is required'})
            
            if len(imei_number) != 15:
                return JsonResponse({'success': False, 'error': 'IMEI must be 15 digits'})
            
            if not imei_number.isdigit():
                return JsonResponse({'success': False, 'error': 'IMEI must contain only digits'})
            
            # Check if IMEI already exists
            if DeviceImei.objects.filter(imei_number=imei_number).exists():
                return JsonResponse({'success': False, 'error': 'IMEI already exists'})
            
            # Create new device
            device = DeviceImei.objects.create(imei_number=imei_number)
            
            return JsonResponse({
                'success': True, 
                'message': 'Device added successfully',
                'device_id': device.id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


@login_required
@csrf_exempt
def add_vehicle_view(request):
    """Add new vehicle with associated IMEI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            registration_number = data.get('registration_number', '').strip()
            imei_id = data.get('imei_id')
            
            if not registration_number:
                return JsonResponse({'success': False, 'error': 'Registration number is required'})
            
            if not imei_id:
                return JsonResponse({'success': False, 'error': 'IMEI device is required'})
            
            # Check if registration number already exists
            if Vehicle.objects.filter(registration_number=registration_number).exists():
                return JsonResponse({'success': False, 'error': 'Registration number already exists'})
            
            # Check if IMEI device exists and is not already assigned
            try:
                device = DeviceImei.objects.get(id=imei_id)
                if Vehicle.objects.filter(imei=device).exists():
                    return JsonResponse({'success': False, 'error': 'This IMEI is already assigned to another vehicle'})
            except DeviceImei.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'IMEI device not found'})
            
            # Create new vehicle
            vehicle = Vehicle.objects.create(
                registration_number=registration_number,
                imei=device
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'Vehicle added successfully',
                'vehicle_id': vehicle.id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


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
def delete_device_view(request, device_id):
    """Delete a device if not assigned to any vehicle"""
    if request.method == 'DELETE':
        try:
            device = DeviceImei.objects.get(id=device_id)
            
            # Check if device is assigned to a vehicle
            if hasattr(device, 'vehicle'):
                return JsonResponse({
                    'success': False, 
                    'error': 'Cannot delete device that is assigned to a vehicle'
                })
            
            device_imei = device.imei_number
            device.delete()
            
            return JsonResponse({
                'success': True, 
                'message': f'Device {device_imei} deleted successfully'
            })
            
        except DeviceImei.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Device not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


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
