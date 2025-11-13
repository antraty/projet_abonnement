```markdown
# Suivi des Abonnements Clients — Résumé pour exposé

Résumé
------
Application de bureau (Tkinter + SQLite) pour gérer clients, abonnements, paiements et relances email. Conçue pour suivre la vie d’un abonnement : création, paiement, relance, archivage et statistiques.

Technologies
------------
- Python 3.8+
- Tkinter (interface graphique)
- SQLite (sqlite3)
- smtplib / email (envoi d'e-mails)
- Modules standard : json, csv, threading, datetime, os

Installation
------------
1. Installer Python 3.8+.
2. S’assurer que Tkinter est disponible (ex. `sudo apt install python3-tk` sur Debian/Ubuntu).
3. Lancer :
   python main.py

Configuration
-------------
- Fichier config.json (ou onglet Relances → Configuration SMTP):
  - smtp_host, smtp_port, smtp_user, smtp_password
  - retention_days (jours avant archivage automatique)
  - auto_archive (True/False)
- Pour Gmail : utiliser un mot de passe d’application si 2FA activé.

Fonctionnalités (aperçu)
------------------------
- Gestion clients : ajouter, lister.
- Gestion abonnements : créer, calcul automatique de date de fin, renouvellement automatique.
- Paiements : ajouter, importer CSV, statut (payé / en attente / échec).
- Relances : templates, envoi automatique selon règles, historique des envois.
- Archivage automatique des abonnements expirés (politique de rétention).
- Exports : CSV (clients, abonnements, paiements) et ICS (échéances).
- Audit : logs des actions (logs_audit).
- Dashboard rapide avec quelques KPI et évolution mensuelle.

Fonctionnalités détaillées (pour l’exposé)
------------------------------------------
- Création de clients
  - Formulaire simple (nom, prénom, email, téléphone).
  - Stockage avec date de création et statut.

- Abonnements
  - Types prédéfinis : Mensuel, Trimestriel, Semestriel, Annuel, Personnalisé.
  - Calcul automatique de la date de fin selon le type.
  - Statut dynamique : "Actif" ou "Expiré" (mis à jour automatiquement).
  - Renouvellement automatique : si activé, prolonge la date de fin au moment de l’expiration.
  - Archivage : les abonnements expirés sont automatiquement archivés après N jours (retention_days).

- Paiements
  - Saisie manuelle avec méthode, date, statut et référence.
  - Import CSV pour charger plusieurs paiements (colonnes minimales requises).
  - Statistiques : total payés, ce mois, en attente, échecs.
  - Couleurs dans la liste pour repérer rapidement les statuts.

- Relances par email
  - Templates paramétrables (sujet + corps avec placeholders : {prenom}, {nom}, {type}, {date_fin}, {prix}).
  - Règles basées sur "jours_avant" (ex : J-7, J-1) et relances post-expiration (ex : J+3).
  - Envois automatiques en tâche de fond ; historique conservé.
  - Envoi ignoré si SMTP non configuré pour éviter erreurs.

- Archivage & rétention
  - Politique configurable : après X jours post-expiration, l’abonnement est copié dans archive_abonnements et marqué archivé.
  - Les archives sont consultables et exportables.

- Exports & calendrier
  - CSV : abonnements, clients, paiements.
  - ICS : événements d’échéance (format calendrier exportable vers Google Calendar / Outlook).

- Audit et logs
  - Table logs_audit : enregistre actions importantes (ajout/maj/suppression, renouvellements automatiques, imports).

Aspects techniques importants (résumé)
-------------------------------------
- Concurrence SQLite : chaque thread de fond utilise sa propre connexion DB pour éviter l’erreur "Recursive use of cursors not allowed".
- Tâches de fond :
  - Archivage automatique : vérification toutes les heures.
  - Vérification/envoi de relances : toutes les 30 minutes.
- Simplicité : aucune dépendance externe, tout en stdlib pour faciliter déploiement.

Points à mentionner à l’oral (suggestions pour l’exposé)
-------------------------------------------------------
- Décrire le parcours d’un abonnement (création → paiement → expiration → relance → archivage).
- Expliquer la logique de renouvellement automatique et la politique de rétention.
- Souligner la gestion des emails : templates + historique + configuration SMTP.
- Aborder rapidement la contrainte SQLite multithreading et la solution (connexion par thread).
- Montrer 2-3 écrans clés : liste clients, fiche abonnement, historique relances, exports.

---

Fin : ce README est volontairement synthétique pour un exposé — si tu veux, je peux générer une version encore plus courte (1 page) ou créer des slides de présentation à partir de ces points.
```