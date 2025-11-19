from django.core.management.base import BaseCommand
from subscriptions import notifications

class Command(BaseCommand):
    help = "Envoie le rapport quotidien et les alertes d'abonnement expirant."

    def add_arguments(self, parser):
        parser.add_argument('--jours', type=int, default=3, help='Jours avant expiration pour les alertes')

    def handle(self, *args, **options):
        jours = options['jours']
        self.stdout.write("Envoi du rapport quotidien...")
        try:
            notifications.send_daily_report()
            self.stdout.write(self.style.SUCCESS("Rapport quotidien envoyé."))
        except Exception as e:
            self.stderr.write(f"Erreur en envoyant le rapport quotidien: {e}")

        self.stdout.write(f"Envoi des alertes d'expiration (dans {jours} jours)...")
        try:
            notifications.send_upcoming_expiration_alerts(jours_avant_expiration=jours)
            self.stdout.write(self.style.SUCCESS("Alertes d'expiration envoyées."))
        except Exception as e:
            self.stderr.write(f"Erreur en envoyant les alertes d'expiration: {e}")