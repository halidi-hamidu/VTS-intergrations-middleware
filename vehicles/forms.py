from django import forms
from django.core.exceptions import ValidationError
import re
from .models import Customer, Vehicle, DeviceImei
from django_select2 import forms as s2forms
from django.db.models import Q

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter Fullname',
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'Enter Email',
                'class': 'form-control'
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': 'Enter Phonenumber',
                'class': 'form-control'
            }),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if not re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', phone):
                raise ValidationError("Invalid phone number format (e.g., +1234567890 or 123-456-7890)")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Customer.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

class EditCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter Fullname', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter Email', 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Enter Phonenumber', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Customer.objects.filter(email=email).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', phone):
            raise ValidationError("Invalid phone number format (e.g., +1234567890 or 123-456-7890)")
        return phone

class VehicleForm(forms.ModelForm):
    imei = forms.ModelChoiceField(
        queryset=DeviceImei.objects.none(),
        widget=s2forms.Select2Widget(attrs={
            'class': 'form-control select2-imei',
            'data-placeholder': 'Search or select IMEI...',
            'data-minimum-input-length': 1,
            'data-allow-clear': 'true',
            'data-theme': 'bootstrap-5',
            'data-width': '100%',
        }),
        label="IMEI Device",
        help_text="Search for an unassigned IMEI number",
        required=True
    )
    
    class Meta:
        model = Vehicle
        fields = ['registration_number', 'imei']
        widgets = {
            'registration_number': forms.TextInput(attrs={
                'placeholder': 'e.g. ABC-1234',
                'class': 'form-control',
                'autocomplete': 'off'
            }),
        }
        exclude = ['created_at', 'updated_at', 'customer']
        labels = {
            'registration_number': 'Registration Number'
        }
        help_texts = {
            'registration_number': 'Official vehicle registration'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self.fields['imei'].queryset = DeviceImei.objects.filter(
                Q(vehicle__isnull=True) | Q(vehicle=self.instance))
        else:
            self.fields['imei'].queryset = DeviceImei.objects.filter(vehicle__isnull=True)

        self.fields['registration_number'].widget.attrs.update({
            'pattern': '[A-Za-z0-9-]+',
            'title': 'Alphanumeric characters and hyphens only'
        })

    def clean_registration_number(self):
        reg_num = self.cleaned_data.get('registration_number')
        if reg_num:
            reg_num = reg_num.upper().strip()
            queryset = Vehicle.objects.filter(registration_number__iexact=reg_num)
            
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
                
            if queryset.exists():
                raise ValidationError(
                    "This registration number is already registered to another vehicle."
                )
        return reg_num

    def clean_imei(self):
        imei = self.cleaned_data.get('imei')
        if imei and imei.vehicle and imei.vehicle != self.instance:
            raise ValidationError(
                "This IMEI is already assigned to vehicle: %s" % imei.vehicle.registration_number
            )
        return imei

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
        return instance