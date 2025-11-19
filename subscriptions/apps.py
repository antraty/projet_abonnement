from django.apps import AppConfig

class SubscriptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'subscriptions'

    def ready(self):
        # Importer les signals pour les enregistrer
        try:
            import subscriptions.signals  # noqa: F401
        except Exception:

            pass