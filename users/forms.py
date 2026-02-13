from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, WasteReport

class ResidentRegistrationForm(UserCreationForm):
    full_name = forms.CharField(label="Full Name", max_length=100)
    email = forms.EmailField(label="Email address")
    
    DIVISION_CHOICES = [
        ('', '---------'),
        ('Central Division', 'Central Division'),
        ('Southern Division', 'Southern Division'),
        ('Northern Division', 'Northern Division'),
    ]
    
    division = forms.ChoiceField(choices=DIVISION_CHOICES)
    
    ward = forms.CharField(
        widget=forms.Select(choices=[('', '---------')]),
        required=True
    )
    cell = forms.CharField(
        widget=forms.Select(choices=[('', '---------')]),
        required=True
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('full_name', 'email', 'division', 'ward', 'cell')

# Updated WasteReportForm with location_address
class WasteReportForm(forms.ModelForm):
    class Meta:
        model = WasteReport
        fields = ['image', 'latitude', 'longitude', 'location_address']
        widgets = {
            # We use TextInput or NumberInput with a hidden style to ensure 
            # 'step="any"' is respected by the browser's form validation.
            'latitude': forms.TextInput(attrs={
                'id': 'id_latitude', 
                'step': 'any', 
                'style': 'display:none;'
            }),
            'longitude': forms.TextInput(attrs={
                'id': 'id_longitude', 
                'step': 'any', 
                'style': 'display:none;'
            }),
            'location_address': forms.TextInput(attrs={
                'id': 'id_location_address', 
                'style': 'display:none;'
            }),
        }