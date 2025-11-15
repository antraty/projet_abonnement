from django.core.management.base import BaseCommand
from django.utils import timezone
from subscriptions.notifications import send_subscription_expiry_notifications, send_daily_report
from subscriptions.models import Subscription

class Command(BaseCommand):
    help = 'Envoyer les notifications par email (et synchroniser les statuts expirés)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['expiry', 'daily', 'all'],
            default='all',
            help='Type de notifications à envoyer'
        )

    def handle(self, *args, **options):
        notification_type = options['type']

        # 1) Mise à jour en masse : tous les abonnements dont date_fin < today
        today = timezone.now().date()
        # Mettre à 'suspendu' tous ceux qui ne sont pas déjà 'suspendu' (y compris ceux marqués 'expire')
        to_update_qs = Subscription.objects.filter(date_fin__lt=today).exclude(statut='suspendu')
        updated_count = to_update_qs.update(statut='suspendu')
        if updated_count:
            self.stdout.write(self.style.SUCCESS(
                f'{updated_count} abonnement(s) mis à jour en "suspendu" (date de fin dépassée).'
            ))
        else:
            self.stdout.write('Aucun abonnement à mettre à jour en "suspendu".')

        # 2) Envoi des notifications (comme avant)
        if notification_type in ['expiry', 'all']:
            self.stdout.write('Envoi des notifications d\'expiration...')
            try:
                count = send_subscription_expiry_notifications()
                self.stdout.write(self.style.SUCCESS(f'{count} notifications d\'expiration envoyées'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erreur lors de l\'envoi des notifications d\'expiration: {e}'))

        if notification_type in ['daily', 'all']:
            self.stdout.write('Envoi du rapport quotidien...')
            try:
                success = send_daily_report()
                if success:
                    self.stdout.write(self.style.SUCCESS('Rapport quotidien envoyé avec succès'))
                else:
                    self.stdout.write(self.style.ERROR('Erreur lors de l\'envoi du rapport quotidien'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erreur lors de l\'envoi du rapport quotidien: {e}'))