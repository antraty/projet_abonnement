from django.core.management.base import BaseCommand
from subscriptions.notifications import send_upcoming_expiration_alerts

class Command(BaseCommand):
    help = "Envoie automatiquement les alertes pour les abonnements expirant bientôt"

    def handle(self, *args, **kwargs):
        send_upcoming_expiration_alerts()
        self.stdout.write(self.style.SUCCESS("Alertes envoyées avec succès !"))