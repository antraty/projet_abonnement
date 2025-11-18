from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from django.core.validators import MinValueValidator

class Client(models.Model):
    TYPE_CHOICES = [
        ('personnel', 'Personnel'),
        ('entreprise', 'Entreprise'),
    ]
    nom = models.CharField(max_length=100)
    email = models.EmailField()
    telephone = models.CharField(max_length=20, blank=True)
    type_client = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Informations supplémentaires pour les entreprises
    nom_entreprise = models.CharField(max_length=100, blank=True)

    adresse = models.TextField(blank=True)
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
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('suspendu', 'Suspendu'),
        ('expire', 'Expiré'),
    ]
    ABONNEMENT_CHOICES = [
        ('classique', 'Classique'),
        ('premium', 'Premium'),
        ('vip', 'VIP'),
    ]
    TARIFS = {
        'classique': 10000.0,
        'premium': 20000.0,
        'vip': 50000.0,
    }
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    
    nom_abonnement = models.CharField(max_length=20, choices=ABONNEMENT_CHOICES, default='classique')
    description = models.TextField(blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(0)])
    date_debut = models.DateField()
    date_fin = models.DateField()
    duree_mois = models.IntegerField(help_text="Durée en mois")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Calcul automatique du prix
        if self.nom_abonnement in self.TARIFS and self.duree_mois:
            self.prix = self.TARIFS[self.nom_abonnement] * self.duree_mois

        if self.date_debut and self.duree_mois:
            year = self.date_debut.year + (self.date_debut.month + self.duree_mois - 1) // 12
            month = (self.date_debut.month + self.duree_mois - 1) % 12 + 1
            day = self.date_debut.day
            # Ajustement si le mois n'a pas ce jour (ex: février)
            try:
                self.date_fin = date(year, month, day)
            except ValueError:
                # Si le jour n’existe pas dans le mois, prendre le dernier jour du mois
                from calendar import monthrange
                last_day = monthrange(year, month)[1]
                self.date_fin = date(year, month, last_day)
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.nom_abonnement} - {self.client.nom}"
    
    def est_expire(self):
        """
        Retourne True si la date_fin est passée. Si l'abonnement est expiré,
        cette méthode met également à jour le champ `statut` en 'suspendu'
        (sauf si le statut est déjà 'suspendu') et sauvegarde l'objet.
        """
        today = timezone.now().date()
        is_expired = self.date_fin < today
        if is_expired and self.statut != 'suspendu':
            # Mettre à jour le statut en 'suspendu'
            self.statut = 'suspendu'
            # Sauvegarde ciblée pour éviter effets de bord
            self.save(update_fields=['statut'])
        return is_expired
    
    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"


class Renewal(models.Model):
    abonnement = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    
    date_renouvellement = models.DateTimeField(auto_now_add=True)
    nouveau_prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duree_extension_mois = models.IntegerField(default=1)
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Renouvellement {self.abonnement.nom_abonnement} - {self.date_renouvellement.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Renouvellement"
        verbose_name_plural = "Renouvellements"