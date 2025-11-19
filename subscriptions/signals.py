from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Subscription
from . import notifications

@receiver(post_save, sender=Subscription)
def on_subscription_created(sender, instance, created, **kwargs):
    """
    Quand un abonnement est créé, envoyer un email de bienvenue/confirmation au client.
    """
    if created:
        try:
            notifications.send_new_subscription_email(instance)
        except Exception:
            # Ne pas planter le save si l'envoi échoue. On peut logger ici si nécessaire.
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Erreur lors de l'envoi d'email de nouvel abonnement pour id=%s", instance.id)