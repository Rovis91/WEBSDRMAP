# Cahier des Charges - SDR Viewer Simplifié

## 1. Objectif du Projet

Développer une application web Python simple permettant de:

- Visualiser sur une carte les récepteurs SDR configurés
- Afficher un spectrogramme waterfall pour chaque SDR
- Écouter le signal audio des SDR sélectionnés
- Se concentrer sur la simplicité et la fonctionnalité de base plutôt que sur des fonctionnalités avancées

## 2. Fonctionnalités Essentielles

### 2.1 Connexion aux SDR

- Connexion à des récepteurs KiwiSDR publics via WebSocket
- Configuration simple dans un fichier YAML ou JSON
- Gestion des connexions/déconnexions de base

### 2.2 Visualisation

- Carte Leaflet montrant l'emplacement des SDR configurés
- Spectrogramme waterfall simple pour le SDR sélectionné
- Indication visuelle de l'état de connexion

### 2.3 Audio

- Lecture du flux audio du SDR sélectionné
- Contrôle de volume basique
- Possibilité de changer de fréquence et de mode (AM, FM, SSB)

### 2.4 Interface Utilisateur

- Interface web unique et simple
- Panneau de contrôle pour la sélection de fréquence/mode
- Disposition claire avec carte et spectrogramme visibles simultanément

## 3. Architecture Simplifiée

### 3.1 Backend (Python/Flask)

- Serveur web léger avec Flask
- Gestion des connexions aux KiwiSDR
- Traitement minimal des signaux (juste assez pour visualisation)
- API WebSocket pour transférer les données en temps réel

### 3.2 Frontend

- Interface HTML/CSS/JS simple
- Bibliothèque Leaflet pour la carte
- Canvas ou bibliothèque légère pour le spectrogramme
- Contrôles d'interface utilisateur standard

## 4. Non-Objectifs (à éviter)

- Triangulation et traitement de signal complexe
- Système de détection automatique
- Exportation de données
- Fonctionnalités non essentielles qui compliquent le code
- Docker ou configurations complexes

## 5. Technologies à Utiliser

### 5.1 Backend

- Python 3.9+
- Flask pour le serveur web
- Flask-SocketIO pour les communications en temps réel
- websocket-client pour la connexion aux KiwiSDR
- NumPy pour le traitement minimal des données

### 5.2 Frontend

- HTML5/CSS3/JavaScript
- Leaflet.js pour la cartographie
- Bootstrap pour l'interface utilisateur simple
- Canvas natif ou bibliothèque légère pour le spectrogramme

## 6. Critères de Réussite

- L'application se lance facilement avec Python
- La carte affiche correctement les SDR configurés
- Le spectrogramme waterfall fonctionne en temps réel
- L'audio peut être écouté avec un délai minimal
- L'interface est intuitive et réactive
- Le code est simple, lisible et bien documenté
