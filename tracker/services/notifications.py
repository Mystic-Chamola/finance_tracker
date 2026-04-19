from ..models import Notification


class NotificationService:
    def __init__(self, user):
        self.user = user

    def mark_read(self, notification_id):
        notification = Notification.objects.filter(pk=notification_id, user=self.user).first()
        if notification:
            notification.is_read = True
            notification.save()
            return notification.link if notification.link else '/notifications/'
        return '/notifications/'

    def mark_all_read(self):
        Notification.objects.filter(user=self.user, is_read=False).update(is_read=True)

    def get_queryset(self):
        return Notification.objects.filter(user=self.user).order_by('-created_at')

    def get_unread_count(self):
        return Notification.objects.filter(user=self.user, is_read=False).count()

    def get_recent(self, limit=5):
        return Notification.objects.filter(user=self.user, is_read=False)[:limit]