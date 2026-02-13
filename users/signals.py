from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import WasteReport

@receiver(post_save, sender=WasteReport)
def send_admin_notification(sender, instance, created, **kwargs):
    if created:  # Only triggers on the FIRST time a report is saved
        subject = f"⚠️ NEW WASTE REPORT: {instance.location_address[:40]}"
        
        # Build the message body
        message = (
            f"A new waste report has been submitted.\n\n"
            f"📍 Address: {instance.location_address}\n"
            f"🗺️ Coordinates: {instance.latitude}, {instance.longitude}\n"
            f"📅 Date: {instance.created_at.strftime('%B %d, %Y at %H:%M')}\n\n"
            f"View details here: http://yourdomain.com/admin/yourapp/wastereport/{instance.id}/change/"
        )
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.WARD_ADMIN_EMAIL],
            fail_silently=False, # Set to False so you see errors during testing
        )