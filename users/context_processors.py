from .models import Message

def unread_message_count(request):
    if request.user.is_authenticated and request.user.is_staff:
        count = Message.objects.filter(recipient=request.user, is_read=False).count()
        return {'total_unread_messages': count}
    return {'total_unread_messages': 0}