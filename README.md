# SAMEs : Système d'Alerte de Maintenance par l'Employé

Application mobile multiplateforme pour la gestion des alertes de maintenance en milieu industriel.

## Fonctionnalités

- Authentification sécurisée pour employés, techniciens et administrateurs
- Capture photo ou sélection d'image depuis la galerie pour signaler des anomalies
- Sélection du type d'anomalie avec interface visuelle
- Suivi et historique des alertes avec pagination
- Tableau de bord pour techniciens avec filtrage et tri
- Gestion des types d'anomalies (ajout, modification, suppression) pour administrateurs
- Profil utilisateur pour changer le mot de passe
- Déconnexion automatique après 2 minutes d'inactivité
- Support thème clair/sombre
- Notifications push pour nouvelles alertes
- Validation des entrées et feedback visuel (spinner de chargement)

## Types d'anomalies
- **Bruit** : Sons anormaux, bruits inhabituels
- **Vibration** : Secousses ou tremblements anormaux
- **Surchauffe** : Température élevée inhabituelle
- **Fuite** : Fuite de liquide ou de gaz

## Prérequis

- Python 3.11+
- pip (gestionnaire de paquets Python)

## Installation

1. Cloner le dépôt :
```bash
git clone [url-du-repo]
cd SAMEs_app