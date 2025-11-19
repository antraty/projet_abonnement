from django.urls import path
from . import views

app_name = 'facturation'

urlpatterns = [
    path('api/facture/abonnement/generer/', views.GenererFactureAbonnementAPI.as_view(), name='generer_facture_abonnement'),
    path('facture/<int:facture_id>/', views.FactureView.as_view(), name='afficher_facture'),
]