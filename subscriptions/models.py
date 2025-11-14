from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Client(models.Model):
    # Types de clients possibles
    TYPE_CHOICES = [
        ('personnel', 'Personnel'),
        ('entreprise', 'Entreprise'),
    ]
    
    # Informations de base
    nom = models.CharField(max_length=100)
    email = models.EmailField()
    telephone = models.CharField(max_length=20, blank=True)
    type_client = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Informations supplémentaires pour les entreprises
    nom_entreprise = models.CharField(max_length=100, blank=True)
    adresse = models.TextField(blank=True)
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.type_client == 'entreprise' and self.nom_entreprise:
            return f"{self.nom_entreprise} ({self.nom})"
        return self.nom

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"

class Subscription(models.Model):
    # Statuts possibles
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('suspendu', 'Suspendu'),
        ('expire', 'Expiré'),
    ]
    
    # Relations
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    
    # Informations de l'abonnement
    nom_abonnement = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Période
    date_debut = models.DateField()
    date_fin = models.DateField()
    duree_mois = models.IntegerField(help_text="Durée en mois")
    
    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.nom_abonnement} - {self.client.nom}"
    
    def est_expire(self):
        return self.date_fin < timezone.now().date()
    
    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"

class Renewal(models.Model):
    # L'abonnement renouvelé
    abonnement = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    
    # Informations du renouvellement
    date_renouvellement = models.DateTimeField(auto_now_add=True)
    nouveau_prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duree_extension_mois = models.IntegerField(default=1)
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Renouvellement {self.abonnement.nom_abonnement} - {self.date_renouvellement.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Renouvellement"
        verbose_name_plural = "Renouvellements"