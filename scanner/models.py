from django.db import models
from django.contrib.auth.models import User

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class ScanRequest(BaseModel):
    SCAN_DEPTH_CHOICES = [
        ('STANDARD', 'Standard'),
        ('DEEP', 'Deep'),
    ]

    SCAN_TYPE_CHOICES = [
        ('SECRETS', 'Secrets'),
        ('DEPENDENCIES', 'Dependencies'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'В ожидании'),
        ('DOWNLOADING', 'Скачивание репозитория'),
        ('SCANNING', 'Сканирование'),
        ('COMPLETED', 'Завершено'),
        ('FAILED', 'Ошибка'),
    ]

    user = models.ForeignKey(User, related_name='scan_requests', on_delete=models.CASCADE)
    repository_url = models.URLField(max_length=2550, null=True, blank=True)
    scan_depth = models.CharField(choices=SCAN_DEPTH_CHOICES, max_length=20)
    include_history = models.BooleanField(default=False)
    scan_type = models.CharField(choices=SCAN_TYPE_CHOICES, max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')  # Это поле должно быть!
    local_path = models.CharField(max_length=2550, null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Scan {self.id} - {self.repository_url}"

class ScanResult(BaseModel):
    BUG_TYPE_CHOICES = [
        ('SECRETS', 'Secrets'),
        ('DEPENDENCIES', 'Dependencies'),
    ]

    CONFIDENCE_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    scan_request = models.ForeignKey(ScanRequest, on_delete=models.CASCADE, related_name='scan_results')
    status = models.BooleanField(default=False)
    file_path = models.CharField(max_length=2550)
    str_number = models.PositiveIntegerField(default=0)
    bug_type = models.CharField(choices=BUG_TYPE_CHOICES, max_length=20)
    secret_type = models.CharField(max_length=100, blank=True, null=True)
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, blank=True, null=True)
    raw_context = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Result for {self.scan_request.id} - {self.file_path}"