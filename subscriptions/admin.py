from django.contrib import admin
from .models import Client, Subscription, Renewal

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('nom', 'email', 'type_client', 'nom_entreprise', 'date_creation')
    list_filter = ('type_client', 'date_creation')
    search_fields = ('nom', 'email', 'nom_entreprise')
    list_per_page = 20

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('nom_abonnement', 'client', 'prix', 'date_debut', 'date_fin', 'statut')
    list_filter = ('statut', 'date_debut', 'date_fin')
    search_fields = ('nom_abonnement', 'client__nom', 'client__nom_entreprise')
    list_per_page = 20
    date_hierarchy = 'date_debut'

@admin.register(Renewal)
class RenewalAdmin(admin.ModelAdmin):
    list_display = ('abonnement', 'date_renouvellement', 'nouveau_prix', 'duree_extension_mois')
    list_filter = ('date_renouvellement',)
    search_fields = ('abonnement__nom_abonnement', 'abonnement__client__nom')
    list_per_page = 20
    date_hierarchy = 'date_renouvellement'