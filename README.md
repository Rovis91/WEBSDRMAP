# SDR Web Viewer

Application web pour visualiser les signaux provenant de récepteurs KiwiSDR.

## Fonctionnalités

- Connexion à plusieurs récepteurs KiwiSDR
- Visualisation du waterfall (spectrogramme)
- Écoute en temps réel
- Sélection de la fréquence et du mode de réception

## Installation

### Prérequis

- Python 3.9+ 
- pip

### Installation des dépendances

```bash
pip install -r requirements.txt
```

## Utilisation

### Méthode simple (recommandée)

Pour démarrer l'application, il suffit d'exécuter le script de démarrage :

```bash
python start_sdr.py
```

Cela démarre le serveur et ouvre automatiquement votre navigateur web à l'adresse http://127.0.0.1:8000.

### Méthode alternative

Si la méthode simple ne fonctionne pas, vous pouvez démarrer le serveur directement :

```bash
python basic_app.py
```

Puis ouvrir manuellement votre navigateur à l'adresse http://127.0.0.1:8000.

### Configuration

La configuration se fait via le fichier `config.yaml`. Vous pouvez définir les récepteurs KiwiSDR auxquels vous souhaitez vous connecter ainsi que d'autres paramètres.

Exemple de configuration:

```yaml
# Configuration du serveur web
server:
  host: "127.0.0.1"
  port: 5000
  secret_key: "change_this_in_production"

# Configuration des récepteurs KiwiSDR
receivers:
  - name: "Récepteur 1"
    url: "wss://example.com:8073/kiwi"
    location:
      latitude: 48.8566
      longitude: 2.3522
```

## Résolution des problèmes

Si l'application ne démarre pas correctement :

1. Vérifiez que toutes les dépendances sont installées : `pip install -r requirements.txt`
2. Assurez-vous qu'aucun autre service n'utilise le port 8000
3. Consultez les logs pour identifier d'éventuelles erreurs

## Licence

Ce projet est sous licence MIT.
