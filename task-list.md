# Task List - SDR Viewer Simplifié

## 1. Configuration et Setup Initial

- [x] 1.1. Créer une structure de projet simplifiée
- [x] 1.2. Configurer l'environnement virtuel Python
- [x] 1.3. Créer un fichier de configuration YAML pour les SDR
- [x] 1.4. Créer un fichier `requirements.txt` minimaliste
- [x] 1.5. Préparer un script simple de lancement

## 2. Implémentation du Module KiwiSDR Client

- [x] 2.1. Développer une classe KiwiSDR de base
  - [x] 2.1.1. Implémenter la connexion WebSocket
  - [x] 2.1.2. Implémenter l'authentification simple
  - [x] 2.1.3. Implémenter le changement de fréquence/mode
- [x] 2.2. Développer la gestion du flux audio
  - [x] 2.2.1. Récupérer le flux audio brut
  - [x] 2.2.2. Traiter et formater pour la lecture web
- [x] 2.3. Développer la récupération des données waterfall
  - [x] 2.3.1. Obtenir les données du spectrogramme
  - [x] 2.3.2. Traiter pour la visualisation

## 3. Développement du Serveur Web Flask

- [x] 3.1. Configurer l'application Flask de base
  - [x] 3.1.1. Créer la structure de routes
  - [x] 3.1.2. Configurer Flask-SocketIO
- [x] 3.2. Implémenter les API REST essentielles
  - [x] 3.2.1. API pour obtenir la liste des SDR configurés
  - [x] 3.2.2. API pour obtenir/modifier les paramètres
- [x] 3.3. Implémenter les événements WebSocket
  - [x] 3.3.1. Événements pour transmettre les données waterfall
  - [x] 3.3.2. Événements pour contrôler l'audio

## 4. Développement du Frontend

- [x] 4.1. Créer la structure HTML de base
  - [x] 4.1.1. Layout principal de l'interface
  - [x] 4.1.2. Emplacement pour la carte et le spectrogramme
- [x] 4.2. Implémenter la carte avec Leaflet
  - [x] 4.2.1. Afficher la carte de base
  - [x] 4.2.2. Ajouter les marqueurs pour les SDR
  - [x] 4.2.3. Implémenter la sélection de SDR par clic
- [x] 4.3. Implémenter l'affichage waterfall
  - [x] 4.3.1. Créer le canvas pour le spectrogramme
  - [x] 4.3.2. Développer le code pour dessiner le waterfall
  - [x] 4.3.3. Ajouter les échelles et légendes
- [x] 4.4. Implémenter les contrôles audio
  - [x] 4.4.1. Créer l'élément audio HTML5
  - [x] 4.4.2. Ajouter les contrôles de volume
  - [x] 4.4.3. Implémenter la sélection de mode (AM/FM/SSB)
- [x] 4.5. Développer les contrôles de fréquence
  - [x] 4.5.1. Créer l'interface de sélection de fréquence
  - [x] 4.5.2. Implémenter le changement de fréquence via WebSocket

## 5. Intégration et Communication

- [x] 5.1. Intégrer la communication backend-frontend
  - [x] 5.1.1. Établir la connexion WebSocket pour les données en temps réel
  - [x] 5.1.2. Synchroniser les paramètres entre UI et serveur
- [x] 5.2. Gérer le flux audio en temps réel
  - [x] 5.2.1. Transmettre l'audio du backend au frontend
  - [x] 5.2.2. Assurer une lecture fluide

## 6. Test et Optimisation

- [ ] 6.1. Tester avec différents KiwiSDR publics
  - [ ] 6.1.1. Vérifier la connexion à plusieurs sources
  - [ ] 6.1.2. Tester la stabilité des connexions
- [ ] 6.2. Optimiser les performances
  - [x] 6.2.1. Réduire la consommation de ressources
  - [ ] 6.2.2. Améliorer la réactivité de l'interface

## 7. Documentation et Finalisation

- [x] 7.1. Rédiger un README clair
  - [x] 7.1.1. Instructions d'installation
  - [x] 7.1.2. Guide d'utilisation simple
- [x] 7.2. Documenter le code
  - [x] 7.2.1. Ajouter des commentaires dans les sections clés
  - [x] 7.2.2. Expliquer l'architecture simplifiée
- [x] 7.3. Créer un script de lancement unique
  - [x] 7.3.1. Script Python pour démarrer l'application
  - [x] 7.3.2. Validation des dépendances avant lancement
