"""
Module app.py pour la configuration du serveur Flask.

Ce module:
- Configure le serveur Flask
- Initialise Flask-SocketIO pour la communication temps réel
- Définit les routes principales de l'application
- Gère les connexions WebSocket avec les clients
"""

import os
import logging
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

# Get the logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Initialisation de l'application Flask
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Configuration de l'application
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sdr_triangulation_secret')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

# Initialisation de Flask-SocketIO
socketio = SocketIO(app, 
                    cors_allowed_origins="*",  # Permissif pour le développement
                    async_mode='eventlet')     # Mode asynchrone efficace

# Stockage des données de l'application
app_data = {
    'receivers': {},        # Informations sur les récepteurs connectés
    'signals': [],          # Signaux détectés
    'triangulations': [],   # Résultats de triangulation
    'status': 'idle'        # État de l'application
}


@app.route('/')
def index():
    """
    Route principale de l'application.
    
    Returns:
        La page d'accueil de l'application
    """
    return render_template('index.html')


@app.route('/status')
def status():
    """
    Route pour obtenir l'état actuel de l'application.
    
    Returns:
        État de l'application au format JSON
    """
    return jsonify({
        'status': app_data['status'],
        'receivers': {
            name: {
                'connected': info.get('connected', False),
                'location': info.get('location', {'latitude': 0, 'longitude': 0}),
                'frequency': info.get('frequency', 0),
                'mode': info.get('mode', 'AM')
            } for name, info in app_data['receivers'].items()
        },
        'signals_count': len(app_data['signals']),
        'triangulations_count': len(app_data['triangulations'])
    })


@app.route('/config', methods=['GET', 'POST'])
def config():
    """
    Route pour obtenir ou mettre à jour la configuration.
    
    Returns:
        Configuration au format JSON ou statut de la mise à jour
    """
    if request.method == 'GET':
        return jsonify({
            'receivers': app_data['receivers'],
            'frequency_range': [0, 30000000],  # 0-30 MHz
            'modes': ['AM', 'FM', 'USB', 'LSB', 'CW']
        })
    elif request.method == 'POST':
        # Mise à jour de la configuration
        try:
            config_data = request.json
            # TODO: Implémenter la mise à jour de la configuration
            return jsonify({'success': True, 'message': 'Configuration mise à jour'})
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la configuration: {e}")
            return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/signals')
def signals():
    """
    Route pour obtenir les signaux détectés.
    
    Returns:
        Liste des signaux au format JSON
    """
    return jsonify(app_data['signals'])


@app.route('/triangulations')
def triangulations():
    """
    Route pour obtenir les résultats de triangulation.
    
    Returns:
        Liste des triangulations au format JSON
    """
    return jsonify(app_data['triangulations'])


# Événements WebSocket
@socketio.on('connect')
def handle_connect():
    """Gère la connexion d'un client WebSocket."""
    logger.info(f"Client connecté: {request.sid}")
    # Envoyer l'état initial
    socketio.emit('status_update', {
        'status': app_data['status'],
        'receivers_count': len(app_data['receivers']),
        'signals_count': len(app_data['signals']),
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Gère la déconnexion d'un client WebSocket."""
    logger.info(f"Client déconnecté: {request.sid}")


@socketio.on('set_frequency')
def handle_set_frequency(data):
    """
    Handle frequency change request from the client
    """
    try:
        frequency = data.get('frequency')
        receivers = data.get('receivers', [])
        
        if not frequency:
            return {'status': 'error', 'message': 'No frequency specified'}
        
        logger.info(f"Setting frequency to {frequency} Hz for receivers {receivers}")
        
        # Update frequency for each requested receiver
        for receiver_name in receivers:
            if receiver_name in app_data['receivers']:
                # Update frequency in receiver object
                app_data['receivers'][receiver_name]['frequency'] = frequency
                
                # Update status info
                status = app_data['receivers'][receiver_name]
                
                # Notify frontend of the change
                update_receiver_status(receiver_name, status)
                
                # If we have a real connection, we would change the actual receiver frequency here
                # For now, we simulate the response
                simulate_waterfall_updates(receiver_name, frequency)
        
        # Respond with success
        return {'status': 'success', 'frequency': frequency, 'receivers': receivers}
    except Exception as e:
        logger.error(f"Error setting frequency: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def simulate_waterfall_updates(receiver_name, frequency, duration_seconds=10):
    """
    Simulate waterfall data updates for testing the UI
    
    Args:
        receiver_name: The name of the receiver
        frequency: The center frequency in Hz
        duration_seconds: How long to send simulated data
    """
    try:
        import threading
        import time
        import numpy as np
        import random
        
        def send_simulated_data():
            start_time = time.time()
            sample_rate = 12000  # 12 kHz
            fft_size = 1024
            
            # Send updates every 100ms
            update_interval = 0.1
            
            while time.time() - start_time < duration_seconds:
                # Create simulated FFT data (512 bins)
                fft_data = []
                
                # Base noise level between -100 and -90 dBm
                base_level = np.random.uniform(-100, -90, fft_size // 2)
                
                # Add some peaks for simulated signals
                for i in range(3):
                    # Random position within the FFT
                    pos = random.randint(0, (fft_size // 2) - 1)
                    # Random signal strength between -60 and -40 dBm
                    strength = random.uniform(-60, -40)
                    # Random width between 5 and 15 bins
                    width = random.randint(5, 15)
                    
                    # Create a peak
                    for j in range(max(0, pos - width), min(fft_size // 2, pos + width)):
                        # Gaussian falloff from center
                        distance = abs(j - pos)
                        falloff = np.exp(-(distance ** 2) / (2 * (width / 3) ** 2))
                        base_level[j] = strength * falloff + base_level[j] * (1 - falloff)
                
                # Convert to list for JSON serialization
                fft_data = base_level.tolist()
                
                # Send the data
                socketio.emit('waterfall_data', {
                    'receiver': receiver_name,
                    'timestamp': time.time(),
                    'frequency': frequency,
                    'sampleRate': sample_rate,
                    'fftSize': fft_size,
                    'fftData': fft_data
                })
                
                # Also emit some audio data frames for visualization
                simulate_audio_data(receiver_name)
                
                # Sleep for the update interval
                time.sleep(update_interval)
                
            logger.debug(f"Finished sending simulated data for {receiver_name}")
        
        # Start the simulation in a background thread
        threading.Thread(target=send_simulated_data, daemon=True).start()
        logger.info(f"Started simulated waterfall data for {receiver_name} at {frequency} Hz")
        
    except Exception as e:
        logger.error(f"Error simulating waterfall data: {str(e)}")


def simulate_audio_data(receiver_name, num_samples=1024):
    """
    Simulate audio data for the audio visualizer
    
    Args:
        receiver_name: The name of the receiver
        num_samples: Number of audio samples to generate
    """
    try:
        import numpy as np
        
        # Generate random audio samples (-1 to 1)
        audio_data = np.random.uniform(-0.5, 0.5, num_samples).tolist()
        
        # Send the audio data
        socketio.emit('audio_data', {
            'receiver': receiver_name,
            'timestamp': time.time(),
            'samples': audio_data
        })
        
    except Exception as e:
        logger.error(f"Error simulating audio data: {str(e)}")


@socketio.on('start_listening')
def handle_start_listening(data):
    """
    Start streaming data from selected receivers
    """
    try:
        receivers = data.get('receivers', [])
        frequency = data.get('frequency')
        mode = data.get('mode', 'AM')
        
        if not receivers:
            return {'status': 'error', 'message': 'No receivers specified'}
        
        logger.info(f"Starting listening on receivers {receivers} at {frequency} Hz ({mode})")
        
        # Update application status
        update_status('listening')
        
        # Simulate starting the receivers
        for receiver_name in receivers:
            if receiver_name in app_data['receivers']:
                # Update receiver status
                app_data['receivers'][receiver_name]['status'] = 'active'
                app_data['receivers'][receiver_name]['frequency'] = frequency
                app_data['receivers'][receiver_name]['mode'] = mode
                
                # Notify frontend
                update_receiver_status(receiver_name, app_data['receivers'][receiver_name])
                
                # Start simulated data
                simulate_waterfall_updates(receiver_name, frequency)
        
        return {'status': 'success', 'message': 'Listening started'}
    except Exception as e:
        logger.error(f"Error starting listening: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('set_mode')
def handle_set_mode(data):
    """
    Handle mode change request from the client
    """
    try:
        mode = data.get('mode')
        receivers = data.get('receivers', [])
        
        if not mode:
            return {'status': 'error', 'message': 'No mode specified'}
        
        logger.info(f"Setting mode to {mode} for receivers {receivers}")
        
        # Update mode for each requested receiver
        for receiver_name in receivers:
            if receiver_name in app_data['receivers']:
                # Update mode in receiver object
                app_data['receivers'][receiver_name]['mode'] = mode
                
                # Update status info
                status = app_data['receivers'][receiver_name]
                
                # Notify frontend of the change
                update_receiver_status(receiver_name, status)
        
        # Respond with success
        return {'status': 'success', 'mode': mode, 'receivers': receivers}
    except Exception as e:
        logger.error(f"Error setting mode: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('save_annotation')
def handle_save_annotation(data):
    """
    Handle saving an annotation to the database
    """
    try:
        annotation_id = data.get('id')
        title = data.get('title')
        notes = data.get('notes')
        frequency = data.get('frequency')
        mode = data.get('mode')
        tags = data.get('tags', [])
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        if not title:
            return {'status': 'error', 'message': 'Annotation title is required'}
        
        # Initialize annotations collection if not exists
        if 'annotations' not in app_data:
            app_data['annotations'] = {}
        
        # Create new ID if not provided
        if not annotation_id:
            annotation_id = str(uuid.uuid4())
        
        # Create or update annotation
        app_data['annotations'][annotation_id] = {
            'id': annotation_id,
            'title': title,
            'notes': notes,
            'frequency': frequency,
            'mode': mode,
            'tags': tags,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp
        }
        
        logger.info(f"Saved annotation: {title}")
        
        # Broadcast annotation update to all clients
        socketio.emit('annotation_updated', app_data['annotations'][annotation_id])
        
        return {
            'status': 'success', 
            'message': 'Annotation saved successfully',
            'annotation': app_data['annotations'][annotation_id]
        }
    except Exception as e:
        logger.error(f"Error saving annotation: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('get_annotations')
def handle_get_annotations():
    """
    Return all saved annotations
    """
    try:
        # Initialize annotations collection if not exists
        if 'annotations' not in app_data:
            app_data['annotations'] = {}
        
        # Convert dictionary to list
        annotations_list = list(app_data['annotations'].values())
        
        response = {
            'status': 'success',
            'annotations': annotations_list
        }
        
        # Emit response to the requester
        socketio.emit('get_annotations', response)
        
        return response
    except Exception as e:
        logger.error(f"Error retrieving annotations: {str(e)}")
        error_response = {'status': 'error', 'message': str(e)}
        socketio.emit('get_annotations', error_response)
        return error_response


@socketio.on('delete_annotation')
def handle_delete_annotation(data):
    """
    Delete an annotation by ID
    """
    try:
        annotation_id = data.get('id')
        
        if not annotation_id:
            return {'status': 'error', 'message': 'Annotation ID is required'}
        
        # Check if annotations collection exists
        if 'annotations' not in app_data:
            return {'status': 'error', 'message': 'No annotations found'}
        
        # Remove annotation if exists
        if annotation_id in app_data['annotations']:
            deleted = app_data['annotations'].pop(annotation_id)
            logger.info(f"Deleted annotation: {deleted['title']}")
            
            # Broadcast deletion to all clients
            socketio.emit('annotation_deleted', {'id': annotation_id})
            
            return {
                'status': 'success',
                'message': 'Annotation deleted successfully'
            }
        else:
            return {'status': 'error', 'message': 'Annotation not found'}
    except Exception as e:
        logger.error(f"Error deleting annotation: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('map_click')
def handle_map_click(data):
    """
    Handle a map click event from the client
    """
    try:
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not latitude or not longitude:
            return {'status': 'error', 'message': 'Invalid coordinates'}
        
        logger.info(f"Map clicked at {latitude}, {longitude}")
        
        # Store the click location
        app_data['last_map_click'] = {
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check if we should create a marker
        if data.get('create_marker', False):
            marker_id = str(uuid.uuid4())
            marker_type = data.get('marker_type', 'manual')
            
            # Create a new marker
            if 'markers' not in app_data:
                app_data['markers'] = {}
                
            app_data['markers'][marker_id] = {
                'id': marker_id,
                'latitude': latitude,
                'longitude': longitude,
                'type': marker_type,
                'label': data.get('label', 'Manual marker'),
                'description': data.get('description', ''),
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast the new marker to all clients
            socketio.emit('new_marker', app_data['markers'][marker_id])
            
            return {
                'status': 'success',
                'message': 'Marker created',
                'marker': app_data['markers'][marker_id]
            }
            
        return {'status': 'success', 'coordinates': {'latitude': latitude, 'longitude': longitude}}
    except Exception as e:
        logger.error(f"Error handling map click: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('signal_select')
def handle_signal_select(data):
    """
    Handle a signal selection event from the client
    """
    try:
        signal_id = data.get('signal_id')
        selected = data.get('selected', True)
        
        if not signal_id:
            return {'status': 'error', 'message': 'No signal ID provided'}
        
        logger.info(f"Signal {signal_id} {'selected' if selected else 'deselected'}")
        
        # Find the signal in the signals list
        signal = None
        for s in app_data['signals']:
            if s.get('id') == signal_id:
                signal = s
                break
                
        if not signal:
            return {'status': 'error', 'message': 'Signal not found'}
            
        # Update the selection status
        signal['selected'] = selected
        
        # Broadcast the selection change to all clients
        socketio.emit('signal_selection_changed', {
            'signal_id': signal_id,
            'selected': selected
        })
        
        return {'status': 'success', 'signal': signal}
    except Exception as e:
        logger.error(f"Error handling signal selection: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('frequency_select')
def handle_frequency_select(data):
    """
    Handle a frequency selection event from the spectrogram
    """
    try:
        frequency = data.get('frequency')
        
        if not frequency:
            return {'status': 'error', 'message': 'No frequency provided'}
        
        logger.info(f"Frequency selected: {frequency} Hz")
        
        # Store the last selected frequency
        app_data['last_selected_frequency'] = frequency
        
        # Check if there are any signals near this frequency
        nearby_signals = []
        for signal in app_data['signals']:
            signal_freq = signal.get('frequency', 0)
            # Check if within 5 kHz
            if abs(signal_freq - frequency) <= 5000:
                nearby_signals.append(signal)
        
        # If we found any, broadcast them
        if nearby_signals:
            socketio.emit('nearby_signals', {
                'frequency': frequency,
                'signals': nearby_signals
            })
        
        return {
            'status': 'success',
            'frequency': frequency,
            'nearby_signals_count': len(nearby_signals)
        }
    except Exception as e:
        logger.error(f"Error handling frequency selection: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@socketio.on('receiver_select')
def handle_receiver_select(data):
    """
    Handle a receiver selection event from the client
    """
    try:
        receiver_name = data.get('receiver')
        selected = data.get('selected', True)
        
        if not receiver_name:
            return {'status': 'error', 'message': 'No receiver specified'}
            
        if receiver_name not in app_data['receivers']:
            return {'status': 'error', 'message': 'Receiver not found'}
        
        logger.info(f"Receiver {receiver_name} {'selected' if selected else 'deselected'}")
        
        # Update the selection status
        app_data['receivers'][receiver_name]['selected'] = selected
        
        # Broadcast the change
        socketio.emit('receiver_selection_changed', {
            'receiver': receiver_name,
            'selected': selected
        })
        
        return {'status': 'success', 'receiver': receiver_name, 'selected': selected}
    except Exception as e:
        logger.error(f"Error handling receiver selection: {str(e)}")
        return {'status': 'error', 'message': str(e)}


# Fonctions pour mettre à jour les données de l'application
def update_receiver_status(name: str, status: Dict[str, Any]):
    """
    Met à jour le statut d'un récepteur.
    
    Args:
        name: Nom du récepteur
        status: Nouvelles informations de statut
    """
    if name in app_data['receivers']:
        app_data['receivers'][name].update(status)
    else:
        app_data['receivers'][name] = status
    
    # Notifier les clients
    socketio.emit('receiver_update', {
        'name': name,
        'status': app_data['receivers'][name]
    })


def add_signal(signal_data: Dict[str, Any]):
    """
    Ajoute un signal détecté.
    
    Args:
        signal_data: Données du signal
    """
    app_data['signals'].append(signal_data)
    
    # Limiter la liste à un nombre raisonnable
    max_signals = 100
    if len(app_data['signals']) > max_signals:
        app_data['signals'] = app_data['signals'][-max_signals:]
    
    # Notifier les clients
    socketio.emit('new_signal', signal_data)


def add_triangulation(triangulation_data: Dict[str, Any]):
    """
    Ajoute un résultat de triangulation.
    
    Args:
        triangulation_data: Données de triangulation
    """
    app_data['triangulations'].append(triangulation_data)
    
    # Limiter la liste à un nombre raisonnable
    max_triangulations = 50
    if len(app_data['triangulations']) > max_triangulations:
        app_data['triangulations'] = app_data['triangulations'][-max_triangulations:]
    
    # Notifier les clients
    socketio.emit('new_triangulation', triangulation_data)


def update_status(new_status: str):
    """
    Met à jour l'état global de l'application.
    
    Args:
        new_status: Nouvel état
    """
    app_data['status'] = new_status
    
    # Notifier les clients
    socketio.emit('status_update', {
        'status': new_status
    })


def add_waterfall_data(data: Dict[str, Any]):
    """
    Ajoute des données de spectrogramme waterfall.
    
    Args:
        data: Données du spectrogramme (FFT)
    """
    # Notifier les clients
    socketio.emit('waterfall_data', data)


# Fonctions pour envoyer des données simulées (pour le développement et les tests)
def send_test_data():
    """
    Envoie des données de test pour la démonstration de l'interface.
    Cette fonction est utilisée uniquement pour le développement.
    """
    import numpy as np
    import time
    import threading
    
    def generate_test_data():
        # Génération de données pour simuler un spectrogramme waterfall
        while True:
            try:
                # Générer des données FFT simulées
                fft_size = 1024
                fft_data = np.random.normal(-100, 20, fft_size)
                
                # Créer quelques signaux simulés
                for i in range(3):
                    center = np.random.randint(100, fft_size-100)
                    width = np.random.randint(5, 20)
                    strength = np.random.randint(30, 60)
                    
                    # Ajouter un pic à une position aléatoire
                    fft_data[center-width:center+width] += np.hamming(width*2) * strength
                
                # Simuler un signal mobile
                t = time.time()
                center = int(fft_size/2 + fft_size/4 * np.sin(t/5))
                width = 10
                fft_data[center-width:center+width] += np.hamming(width*2) * 50
                
                # Envoyer les données waterfall
                add_waterfall_data({
                    'fftData': fft_data.tolist(),
                    'centerFreq': 7100000,
                    'sampleRate': 12000,
                    'timestamp': time.time()
                })
                
                # Simuler de nouveaux signaux détectés
                if np.random.random() < 0.05:  # 5% de chance
                    add_signal({
                        'id': f'sig_{int(time.time())}',
                        'frequency': 7100000 + np.random.randint(-6000, 6000),
                        'mode': np.random.choice(['AM', 'FM', 'USB', 'LSB', 'CW']),
                        'snr': np.random.randint(10, 40),
                        'timestamp': time.time(),
                        'receivers': [f'rx_{i}' for i in range(np.random.randint(1, 4))]
                    })
                
                # Simuler une triangulation occasionnelle
                if np.random.random() < 0.02:  # 2% de chance
                    receivers = [f'rx_{i}' for i in range(np.random.randint(2, 5))]
                    center_lat = 46.2276  # France
                    center_lon = 2.2137
                    
                    add_triangulation({
                        'id': f'tr_{int(time.time())}',
                        'frequency': 7100000 + np.random.randint(-6000, 6000),
                        'timestamp': time.time(),
                        'mode': np.random.choice(['AM', 'FM', 'USB', 'LSB', 'CW']),
                        'lat': center_lat + np.random.normal(0, 0.5),
                        'lon': center_lon + np.random.normal(0, 0.5),
                        'radius': np.random.randint(20, 100),
                        'confidence': np.random.random(),
                        'receivers': receivers,
                        'rssi_values': {rx: np.random.randint(-100, -60) for rx in receivers}
                    })
                
                # Pause entre les mises à jour
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Erreur lors de la génération des données de test: {e}")
                time.sleep(1)
    
    # Démarrer la génération de données dans un thread séparé
    thread = threading.Thread(target=generate_test_data, daemon=True)
    thread.start()
    logger.info("Générateur de données de test démarré")


# Point d'entrée pour le démarrage du serveur (utilisé par main.py)
def run_server(host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
    """
    Point d'entrée pour le démarrage du serveur Flask.
    
    Args:
        host: Adresse d'écoute
        port: Port d'écoute
        debug: Mode debug
        
    Returns:
        None
    """
    app.config['DEBUG'] = debug
    
    # En mode debug, générer des données de test
    if debug:
        send_test_data()
    
    logger.info(f"Démarrage du serveur Flask sur {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    # Ce bloc est exécuté si le script est lancé directement
    run_server(debug=True) 