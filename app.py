#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import threading
import time
import yaml
from flask import Flask, render_template, request, jsonify, g, Response
from collections import defaultdict

# Configurer le logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('sdr_app')

# Déterminer le meilleur mode asynchrone disponible
async_mode = None
try:
    import eventlet
    eventlet.monkey_patch()
    async_mode = 'eventlet'
    logger.info("Utilisation du mode asynchrone: eventlet")
except ImportError:
    try:
        import gevent
        import gevent.monkey
        gevent.monkey.patch_all()
        async_mode = 'gevent'
        logger.info("Utilisation du mode asynchrone: gevent")
    except ImportError:
        async_mode = 'threading'
        logger.info("Utilisation du mode asynchrone: threading")

# Importer Flask-SocketIO après les monkey patches
from flask_socketio import SocketIO, emit

# Importer le client KiwiSDR
from kiwi_client import KiwiSDR

# Créer l'application Flask et la configuration SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sdr_production_secret'
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

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
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            },
            'receivers': []
        }

# Charger la configuration
config = load_config()

# Configuration du serveur
SERVER_CONFIG = config.get('server', {})
HOST = SERVER_CONFIG.get('host', '0.0.0.0')
PORT = SERVER_CONFIG.get('port', 5000)
DEBUG = SERVER_CONFIG.get('debug', False)

# Liste des récepteurs
receivers = {}
connected_clients = set()
client_receivers = defaultdict(set)  # Pour suivre quels clients sont connectés à quels récepteurs

# Fréquence d'envoi des données (ms) - adaptive selon le nombre de clients
BASE_WATERFALL_INTERVAL = 500  # Intervalle de base pour le waterfall (ms)
BASE_AUDIO_INTERVAL = 100      # Intervalle de base pour l'audio (ms)
MAX_CLIENTS_FULL_SPEED = 3     # Nombre de clients pour la vitesse maximale

# Verrous pour l'accès aux ressources partagées
clients_lock = threading.Lock()
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

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    logger.info(f"Client {client_id} connected")
    with clients_lock:
        connected_clients.add(client_id)
    # Adapter la fréquence d'envoi des données en fonction du nombre de clients
    _adjust_stream_intervals()

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    logger.info(f"Client {client_id} disconnected")
    
    # Libérer les ressources associées à ce client
    with clients_lock:
        if client_id in connected_clients:
            connected_clients.remove(client_id)
        
        # Déconnecter les récepteurs utilisés uniquement par ce client
        receivers_to_disconnect = []
        with receivers_lock:
            if client_id in client_receivers:
                for receiver_id in client_receivers[client_id]:
                    # Vérifier si d'autres clients utilisent ce récepteur
                    other_users = False
                    for other_client, other_receivers in client_receivers.items():
                        if other_client != client_id and receiver_id in other_receivers:
                            other_users = True
                            break
                    
                    if not other_users and receiver_id in receivers:
                        receivers_to_disconnect.append(receiver_id)
                
                # Nettoyer les associations client-récepteurs
                client_receivers.pop(client_id, None)
        
        # Déconnecter les récepteurs non utilisés
        for receiver_id in receivers_to_disconnect:
            if receiver_id in receivers:
                logger.info(f"Déconnexion du récepteur {receiver_id} (plus aucun client)")
                try:
                    receivers[receiver_id].disconnect()
                except Exception as e:
                    logger.error(f"Erreur lors de la déconnexion du récepteur {receiver_id}: {e}")
    
    # Adapter la fréquence d'envoi des données
    _adjust_stream_intervals()

@socketio.on('tune')
def handle_tune(data):
    """Gère les requêtes de changement de fréquence et de mode."""
    client_id = request.sid
    receiver_id = data.get('id')
    freq = data.get('freq')
    mode = data.get('mode')
    
    if not receiver_id or receiver_id not in receivers:
        emit('error', {'message': 'Récepteur non valide'})
        return
    
    with receivers_lock:
        receiver = receivers.get(receiver_id)
        if not receiver or not receiver.connected:
            emit('error', {'message': 'Récepteur non connecté'})
            return
        
        # Enregistrer l'association client-récepteur
        with clients_lock:
            client_receivers[client_id].add(receiver_id)
        
        # Changer la fréquence si spécifiée
        if freq is not None:
            try:
                freq = int(freq)
                receiver.set_frequency(freq)
            except (ValueError, TypeError):
                emit('error', {'message': 'Fréquence invalide'})
        
        # Changer le mode si spécifié
        if mode is not None:
            receiver.set_mode(mode)
        
        # Envoyer le statut du récepteur au client
        emit('status', {
            'id': receiver_id,
            'freq': receiver.current_freq,
            'mode': receiver.current_mode
        })

def _adjust_stream_intervals():
    """Ajuste les intervalles de streaming en fonction du nombre de clients."""
    with clients_lock:
        client_count = len(connected_clients)
    
    # Calcul du facteur d'ajustement (1.0 pour MAX_CLIENTS_FULL_SPEED clients ou moins)
    factor = 1.0 if client_count <= MAX_CLIENTS_FULL_SPEED else (MAX_CLIENTS_FULL_SPEED / client_count)
    factor = max(0.2, factor)  # Limiter la réduction à 20% minimum
    
    # Ajuster les intervalles
    waterfall_interval = int(BASE_WATERFALL_INTERVAL / factor)
    audio_interval = int(BASE_AUDIO_INTERVAL / factor)
    
    logger.info(f"Ajustement des intervalles pour {client_count} clients: waterfall={waterfall_interval}ms, audio={audio_interval}ms")
    
    # Mise à jour des intervalles dans les threads actifs
    # Les nouveaux threads utiliseront automatiquement ces valeurs
    global WATERFALL_INTERVAL, AUDIO_INTERVAL
    WATERFALL_INTERVAL = waterfall_interval
    AUDIO_INTERVAL = audio_interval

# Intervalles initiaux
WATERFALL_INTERVAL = BASE_WATERFALL_INTERVAL
AUDIO_INTERVAL = BASE_AUDIO_INTERVAL

def waterfall_stream_thread(receiver_id):
    """Thread de streaming des données waterfall pour un récepteur."""
    if receiver_id not in receivers:
        return
    
    receiver = receivers[receiver_id]
    thread_id = threading.get_ident()
    logger.info(f"Démarrage du thread waterfall pour {receiver_id} (id={thread_id})")
    
    while receiver.connected and receiver_id in receivers:
        try:
            # Vérifier si des clients sont connectés à ce récepteur
            with clients_lock:
                has_clients = any(receiver_id in client_recv for client_recv in client_receivers.values())
            
            if not has_clients:
                # Pas de clients connectés, pause pour économiser les ressources
                time.sleep(0.5)
                continue
            
            # Récupérer les données waterfall
            waterfall_data = receiver.get_waterfall_data()
            
            if waterfall_data:
                # Émettre les données vers tous les clients connectés à ce récepteur
                socketio.emit('waterfall', {
                    'id': receiver_id,
                    'data': waterfall_data
                }, namespace='/')
            
            # Attendre avant la prochaine émission
            time.sleep(WATERFALL_INTERVAL / 1000.0)
        except Exception as e:
            logger.error(f"Erreur dans le thread waterfall pour {receiver_id}: {str(e)}")
            time.sleep(1.0)  # Pause en cas d'erreur pour éviter les boucles rapides
    
    logger.info(f"Arrêt du thread waterfall pour {receiver_id}")

def audio_stream_thread(receiver_id):
    """Thread de streaming des données audio pour un récepteur."""
    if receiver_id not in receivers:
        return
    
    receiver = receivers[receiver_id]
    thread_id = threading.get_ident()
    logger.info(f"Démarrage du thread audio pour {receiver_id} (id={thread_id})")
    
    while receiver.connected and receiver_id in receivers:
        try:
            # Vérifier si des clients sont connectés à ce récepteur
            with clients_lock:
                has_clients = any(receiver_id in client_recv for client_recv in client_receivers.values())
            
            if not has_clients:
                # Pas de clients connectés, pause pour économiser les ressources
                time.sleep(0.5)
                continue
            
            # Récupérer les données audio
            audio_data = receiver.get_audio_packet()
            
            if audio_data:
                # Émettre les données vers tous les clients connectés à ce récepteur
                socketio.emit('audio', {
                    'id': receiver_id,
                    'data': audio_data
                }, namespace='/')
            
            # Attendre avant la prochaine émission
            time.sleep(AUDIO_INTERVAL / 1000.0)
        except Exception as e:
            logger.error(f"Erreur dans le thread audio pour {receiver_id}: {str(e)}")
            time.sleep(1.0)  # Pause en cas d'erreur pour éviter les boucles rapides
    
    logger.info(f"Arrêt du thread audio pour {receiver_id}")

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
    """Connecte un récepteur et démarre les threads de streaming."""
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
            
            # Démarrer les threads de streaming
            waterfall_thread = threading.Thread(
                target=waterfall_stream_thread,
                args=(receiver_id,),
                daemon=True
            )
            audio_thread = threading.Thread(
                target=audio_stream_thread,
                args=(receiver_id,),
                daemon=True
            )
            
            # Conserver les références aux threads pour permettre leur arrêt
            receiver.stream_threads = [waterfall_thread, audio_thread]
            
            # Démarrer les threads
            waterfall_thread.start()
            audio_thread.start()
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
    
    # Ajuster les intervalles initiaux
    _adjust_stream_intervals()

def run_app():
    """Fonction pour démarrer l'application."""
    init_app()
    # Try different methods of running the app
    try:
        # Method 1: Use socketio with allow_unsafe_werkzeug
        try:
            logger.info("Tentative de démarrage avec socketio (méthode 1)")
            socketio.run(app, host=HOST, port=PORT, debug=DEBUG, allow_unsafe_werkzeug=True)
            return
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"Méthode 1 échouée: {str(e)}")
        
        # Method 2: Use socketio without allow_unsafe_werkzeug
        try:
            logger.info("Tentative de démarrage avec socketio (méthode 2)")
            socketio.run(app, host=HOST, port=PORT, debug=DEBUG)
            return
        except Exception as e:
            logger.warning(f"Méthode 2 échouée: {str(e)}")
        
        # Method 3: Use Flask's built-in server
        logger.info("Tentative de démarrage avec Flask standard")
        app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de l'application: {str(e)}")

if __name__ == '__main__':
    run_app() 