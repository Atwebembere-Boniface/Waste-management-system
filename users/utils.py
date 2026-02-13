# your_app/utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_custom_email(subject, recipient_email, message_body):
    """Utility to handle email dispatch with error catching."""
    try:
        send_mail(
            subject=subject,
            message=message_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Email Dispatch Error: {e}")