#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de lancement pour le SDR Viewer.
Exécutez ce script pour démarrer l'application en mode production.
"""

import os
import sys
import logging
import ssl

# Patch for SSL in older eventlet/newer Python versions
if not hasattr(ssl, 'wrap_socket') and hasattr(ssl, 'SSLContext'):
    ssl.wrap_socket = lambda sock, **kwargs: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).wrap_socket(sock, **kwargs)

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('sdr_launcher')

def main():
    """Fonction principale pour lancer l'application en mode production."""
    # Vérifier les dépendances statiques
    try:
        import yaml
        import flask
        import flask_socketio
        import numpy
        import websocket
    except ImportError as e:
        logger.error(f"Dépendance manquante: {str(e)}")
        logger.error("Installez les dépendances avec: pip install -r requirements.txt")
        return 1
    
    # Obtenir le chemin absolu du script
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # S'assurer que nous sommes dans le bon répertoire
    os.chdir(base_path)
    
    # Ajouter le répertoire courant au path pour les imports
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    try:
        # Importer l'application Flask
        from app import app, socketio, init_app
        
        # Initialiser l'application
        init_app()
        
        # Récupérer la configuration du serveur
        from app import config
        host = config.get('server', {}).get('host', '0.0.0.0')
        port = config.get('server', {}).get('port', 5000)
        debug = False  # Forcer le mode production
        
        # Démarrer le serveur avec gestion d'erreurs SSL
        logger.info(f"Démarrage du serveur en mode production sur http://{host}:{port}")
        
        # Try modern method first
        try:
            socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"Méthode de démarrage moderne échouée: {str(e)}, essai méthode alternative")
            # Fallback method for older versions
            try:
                socketio.run(app, host=host, port=port, debug=debug)
            except Exception as e2:
                logger.error(f"Erreur lors du démarrage avec la méthode alternative: {str(e2)}")
                # Last resort: use Flask's built-in server directly
                logger.warning("Utilisation du serveur intégré de Flask")
                app.run(host=host, port=port, debug=debug)
        
        return 0
    except ImportError as e:
        logger.error(f"Erreur d'importation: {str(e)}")
        logger.error("Assurez-vous que toutes les dépendances sont installées avec: pip install -r requirements.txt")
        return 1
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de l'application: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())