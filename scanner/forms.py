from django import forms
from .models import ScanRequest


class ScanRequestForm(forms.ModelForm):
    class Meta:
        model = ScanRequest
        fields = ["repository_url", "scan_depth", "include_history", "scan_type"]
        widgets = {
            "repository_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://github.com/username/repository",
                }
            ),
            "scan_depth": forms.Select(attrs={"class": "form-control"}),
            "scan_type": forms.Select(attrs={"class": "form-control"}),
            "include_history": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "repository_url": "URL репозитория",
            "scan_depth": "Глубина сканирования",
            "include_history": "Включить историю коммитов",
            "scan_type": "Тип сканирования",
        }
