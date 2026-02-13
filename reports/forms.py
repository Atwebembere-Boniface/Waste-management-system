from django import forms
from users.models import WasteReport

class WasteReportForm(forms.ModelForm):
    class Meta:
        model = WasteReport
        fields = ['image', 'latitude', 'longitude', 'location_address']
        widgets = {
            # We hide these because JS will fill them automatically
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'location_address': forms.HiddenInput(),
        }
