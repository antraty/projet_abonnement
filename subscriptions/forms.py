from django import forms
from .models import Client, Subscription

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['nom', 'email', 'telephone', 'type_client', 'nom_entreprise', 'adresse']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom complet'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+33 1 23 45 67 89'
            }),
            'type_client': forms.Select(attrs={
                'class': 'form-control',
                'id': 'type-client'
            }),
            'nom_entreprise': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de l\'entreprise (si applicable)'
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse complète',
                'rows': 3
            }),
        }
        labels = {
            'nom': 'Nom complet',
            'email': 'Adresse email',
            'telephone': 'Numéro de téléphone',
            'type_client': 'Type de client',
            'nom_entreprise': 'Nom de l\'entreprise',
            'adresse': 'Adresse',
        }

class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['client', 'nom_abonnement', 'description', 'date_debut', 'duree_mois']
        widgets = {
            'client': forms.Select(attrs={
                'class': 'form-control'
            }),
            'nom_abonnement': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Description de l\'abonnement',
                'rows': 3
            }),
            'date_debut': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'duree_mois': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '1'
            }),
        }
        labels = {
            'client': 'Client',
            'nom_abonnement': 'Nom de l\'abonnement',
            'description': 'Description',
            'prix': 'Prix (Ar)',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
            'duree_mois': 'Durée (mois)',
            'statut': 'Statut',
        }