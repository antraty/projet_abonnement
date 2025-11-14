from django.core.management.base import BaseCommand
from subscriptions.notifications import send_subscription_expiry_notifications, send_daily_report

class Command(BaseCommand):
    help = 'Envoyer les notifications par email'
    
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
        
        if notification_type in ['expiry', 'all']:
            self.stdout.write('Envoi des notifications d\'expiration...')
            count = send_subscription_expiry_notifications()
            self.stdout.write(
                self.style.SUCCESS(f'{count} notifications d\'expiration envoyées')
            )
        
        if notification_type in ['daily', 'all']:
            self.stdout.write('Envoi du rapport quotidien...')
            success = send_daily_report()
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Rapport quotidien envoyé avec succès')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Erreur lors de l\'envoi du rapport quotidien')
                )