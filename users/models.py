from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save # For automated emails
from django.dispatch import receiver          # For automated emails
from django.core.mail import send_mail        # For automated emails
from django.conf import settings

class User(AbstractUser):
    full_name = models.CharField(max_length=255, null=True, blank=True)

    DIVISION_CHOICES = [
        ('Central Division', 'Central Division'),
        ('Northern Division', 'Northern Division'),
        ('Southern Division', 'Southern Division'),
    ]
    
    division = models.CharField(
        max_length=50, 
        choices=DIVISION_CHOICES, 
        null=True, 
        blank=True
    )
    
    ward = models.CharField(max_length=100, null=True, blank=True)
    cell = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.username} - {self.ward or 'No Ward'}"

class WasteReport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('collected', 'Collected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    image = models.ImageField(upload_to='waste_images/')
    
    # These fields are correctly set for high-precision GPS
    latitude = models.DecimalField(max_digits=22, decimal_places=16)
    longitude = models.DecimalField(max_digits=22, decimal_places=16)
    
    location_address = models.CharField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report by {self.user.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# --- AUTO-EMAIL SIGNAL ---
@receiver(post_save, sender=WasteReport)
def notify_admin_on_new_report(sender, instance, created, **kwargs):
    """Sends an email to the Ward Administrator when a new report is saved."""
    if created: 
        subject = f"🚨 New Waste Report: {instance.user.ward or 'General'}"
        message = (
            f"Hello Ward Administrator,\n\n"
            f"A new report has been submitted by {instance.user.full_name or instance.user.username}.\n\n"
            f"📍 Address: {instance.location_address}\n"
            f"🛰️ Coordinates: {instance.latitude}, {instance.longitude}\n"
            f"⏰ Reported at: {instance.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Please log in to the dashboard to assign a pickup team."
        )
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.WARD_ADMIN_EMAIL], # Ensure this is in settings.py
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email failed: {e}")


class Message(models.Model):
    report = models.ForeignKey(
        WasteReport, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received_messages'
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"From {self.sender.username} → {self.recipient.username} | Report #{self.report.id}"            