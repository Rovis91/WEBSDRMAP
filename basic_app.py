#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import threading
import time
import yaml
from flask import Flask, render_template, request, jsonify, g, Response

# Configurer le logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('sdr_app_basic')

# Importer le client KiwiSDR
from kiwi_client import KiwiSDR

# Créer l'application Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sdr_production_secret'

# Charger la configuration depuis le fichier YAML
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    else:
        logger.warning(f"Fichier de configuration {config_path} non trouvé, utilisation des valeurs par défaut")
        return {
            'server': {
                'host': '127.0.0.1',
                'port': 5000,
                'debug': False
            },
            'receivers': []
        }

# Charger la configuration
config = load_config()

# Configuration du serveur
SERVER_CONFIG = config.get('server', {})
HOST = SERVER_CONFIG.get('host', '127.0.0.1')
PORT = 8000  # Use a different port
DEBUG = SERVER_CONFIG.get('debug', False)

# Liste des récepteurs
receivers = {}
receivers_lock = threading.Lock()

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    # Calculer le temps de traitement de la requête
    if hasattr(g, 'start_time'):
        diff = time.time() - g.start_time
        if diff > 0.5:  # Log seulement les requêtes lentes (>500ms)
            logger.info(f"Request {request.path} processed in {diff:.3f}s")
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/receivers')
def get_receivers():
    with receivers_lock:
        # Seulement les informations essentielles pour limiter le trafic réseau
        receivers_info = []
        for key, receiver in receivers.items():
            if receiver.connected:
                receivers_info.append({
                    'id': key,
                    'name': receiver.name,
                    'location': receiver.location
                })
    return jsonify(receivers_info)

@app.route('/health')
def health_check():
    # Endpoint pour vérifier la santé du serveur
    return Response(json.dumps({'status': 'ok'}), mimetype='application/json')

def init_receivers():
    """Initialise les récepteurs à partir de la configuration."""
    global receivers
    
    # Récupérer la liste des récepteurs depuis la configuration
    receivers_config = config.get('receivers', [])
    
    if not receivers_config:
        logger.warning("Aucun récepteur configuré")
        return
    
    # Créer les instances de récepteurs
    with receivers_lock:
        for i, receiver_config in enumerate(receivers_config):
            receiver_id = f"receiver_{i}"
            name = receiver_config.get('name', f"Récepteur {i}")
            url = receiver_config.get('url')
            location = receiver_config.get('location', {'latitude': 0, 'longitude': 0})
            
            if not url:
                logger.warning(f"URL manquante pour le récepteur {name}, ignoré")
                continue
            
            # Créer l'instance de récepteur
            receivers[receiver_id] = KiwiSDR(url=url, name=name, location=location)
            logger.info(f"Récepteur {name} créé avec l'ID {receiver_id}")

def connect_receiver(receiver_id):
    """Connecte un récepteur."""
    if receiver_id not in receivers:
        logger.error(f"Récepteur {receiver_id} non trouvé")
        return False
    
    with receivers_lock:
        receiver = receivers[receiver_id]
        
        if receiver.connected:
            return True
        
        # Tentative de connexion
        success = receiver.connect()
        
        if success:
            logger.info(f"Connexion réussie au récepteur {receiver_id}")
        else:
            logger.error(f"Échec de connexion au récepteur {receiver_id}")
        
        return success

def init_app():
    """Initialise l'application et les récepteurs."""
    # Initialiser les récepteurs depuis la configuration
    init_receivers()
    
    # Connecter tous les récepteurs au démarrage
    for receiver_id in receivers:
        threading.Thread(target=connect_receiver, args=(receiver_id,), daemon=True).start()
    
    # Définir la clé secrète
    app.config['SECRET_KEY'] = SERVER_CONFIG.get('secret_key', 'production_secret_key')

if __name__ == '__main__':
    init_app()
    logger.info(f"Démarrage du serveur basique sur http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True) 