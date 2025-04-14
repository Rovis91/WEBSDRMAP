#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import time
import threading
import websocket
import numpy as np
from queue import Queue, Empty

# Configuration du logging avec niveau INFO par défaut
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kiwi_client')

# Désactiver les messages de debug de websocket-client
websocket.enableTrace(False)
logging.getLogger('websocket').setLevel(logging.WARNING)

class KiwiSDR:
    """
    Client simplifié pour se connecter aux récepteurs KiwiSDR via WebSocket.
    Gère la connexion, l'authentification, et la réception des données audio et waterfall.
    """
    
    # Limiter la taille des files d'attente pour éviter les fuites de mémoire
    MAX_QUEUE_SIZE = 100
    
    def __init__(self, url, name, location):
        """
        Initialise un client KiwiSDR.
        
        Args:
            url: URL du WebSocket du KiwiSDR (ex: wss://example.com:8073/kiwi)
            name: Nom du récepteur KiwiSDR
            location: Dictionnaire contenant la latitude et la longitude du récepteur
        """
        self.url = url
        self.name = name
        self.location = location
        self.connected = False
        self.ws = None
        self.audio_queue = Queue(maxsize=self.MAX_QUEUE_SIZE)  # Taille maximale de la file
        self.waterfall_queue = Queue(maxsize=self.MAX_QUEUE_SIZE)  # Taille maximale de la file
        self.last_waterfall_data = None
        self.current_freq = 7100  # Fréquence par défaut en kHz
        self.current_mode = 'am'  # Mode par défaut (am, usb, lsb, etc.)
        self.running = False
        self.auth_done = False
        self.ws_thread = None
        self.connection_timeout = 15  # Timeout de connexion en secondes
        self.auth_timeout = 5  # Timeout d'authentification en secondes
        self.stream_threads = []
        
    def connect(self):
        """Établit une connexion au KiwiSDR et authentifie."""
        if self.connected:
            return True
        
        logger.info(f"Connexion à {self.name} ({self.url})")
        
        try:
            # Connexion WebSocket avec timeout
            self.ws = websocket.create_connection(self.url, timeout=self.connection_timeout)
            self.connected = True
            
            # Authentification
            self._send_auth()
            
            # Démarrer le thread de traitement des messages
            self.running = True
            self.ws_thread = threading.Thread(target=self._ws_thread)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Attendre que l'authentification soit confirmée (avec timeout)
            start_time = time.time()
            while not self.auth_done and (time.time() - start_time) < self.auth_timeout:
                time.sleep(0.1)
            
            if not self.auth_done:
                logger.warning(f"Délai d'authentification dépassé pour {self.name}")
                self.disconnect()
                return False
            else:
                logger.info(f"Connecté à {self.name}")
                
                # Définir la fréquence et le mode initiaux
                self.set_frequency(self.current_freq)
                self.set_mode(self.current_mode)
            
            return self.auth_done
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à {self.name}: {str(e)}")
            self.disconnect()  # S'assurer que toutes les ressources sont libérées
            return False
    
    def disconnect(self):
        """Déconnecte du KiwiSDR."""
        if not self.connected and not self.ws and not self.running:
            return
        
        logger.info(f"Déconnexion de {self.name}")
        self.running = False
        
        try:
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
                self.ws = None
                
            # Arrêter et attendre le thread principal
            if self.ws_thread and self.ws_thread.is_alive():
                try:
                    self.ws_thread.join(2.0)  # Attente de 2 secondes max
                except:
                    pass
                
            # Arrêter les threads de stream (définis dans app.py)
            if hasattr(self, 'stream_threads'):
                for thread in self.stream_threads:
                    if thread and thread.is_alive():
                        try:
                            # On ne peut pas directement arrêter un thread, mais on arrête la boucle
                            pass
                        except:
                            pass
                self.stream_threads = []
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion de {self.name}: {str(e)}")
        
        # Vider les files d'attente pour libérer la mémoire
        self._clear_queues()
        
        self.connected = False
        self.auth_done = False
    
    def _clear_queues(self):
        """Vide les files d'attente pour libérer la mémoire."""
        try:
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except Empty:
                    break
            
            while not self.waterfall_queue.empty():
                try:
                    self.waterfall_queue.get_nowait()
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des files d'attente: {str(e)}")
    
    def _send_auth(self):
        """Envoie les messages d'authentification au KiwiSDR."""
        # Message initial de connexion
        self._send_message('SET auth t=kiwi p= need_status=1')
        
        # Message d'établissement de connexion
        setup_msg = {
            'name': 'sdr_client',
            'ver': '1.0',
        }
        self._send_message(f'SET ident_user m="{json.dumps(setup_msg)}"')
        
        # Message d'activation du flux audio
        self._send_message('SET SET_AUDIO_COMP compression=1')
        
        # Demande d'activation du waterfall - vitesse réduite pour économiser la bande passante
        self._send_message('SET maxdb=0 mindb=-100')
        self._send_message('SET wf_comp=1')
        self._send_message('SET wf_speed=3')  # Vitesse du waterfall réduite (1-4)
    
    def set_frequency(self, freq_khz):
        """
        Définit la fréquence de réception en kHz.
        
        Args:
            freq_khz: Fréquence en kHz
        """
        if not self.connected:
            logger.warning(f"Non connecté à {self.name}, impossible de changer la fréquence")
            return False
        
        self.current_freq = freq_khz
        self._send_message(f'SET freq={freq_khz}')
        logger.info(f"Fréquence définie à {freq_khz} kHz sur {self.name}")
        return True
    
    def set_mode(self, mode):
        """
        Définit le mode de réception (AM, USB, LSB, etc.).
        
        Args:
            mode: Mode de réception ('am', 'usb', 'lsb', 'cw', 'nbfm')
        """
        mode = mode.lower()
        valid_modes = {'am', 'usb', 'lsb', 'cw', 'nbfm'}
        
        if mode not in valid_modes:
            logger.warning(f"Mode {mode} non valide, utilisation de 'am'")
            mode = 'am'
        
        if not self.connected:
            logger.warning(f"Non connecté à {self.name}, impossible de changer le mode")
            return False
        
        self.current_mode = mode
        self._send_message(f'SET mod={mode}')
        logger.info(f"Mode défini à {mode} sur {self.name}")
        return True
    
    def _send_message(self, message):
        """Envoie un message au serveur WebSocket."""
        if not self.connected or not self.ws:
            return
        
        try:
            self.ws.send(message)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message: {str(e)}")
            self.connected = False  # Marquer comme déconnecté pour forcer une reconnexion
    
    def _ws_thread(self):
        """Thread principal pour traiter les messages du WebSocket."""
        while self.running and self.connected:
            try:
                # Attente de message avec timeout pour permettre l'arrêt propre du thread
                self.ws.settimeout(1.0)
                opcode, data = self.ws.recv_data()
                
                if opcode == websocket.ABNF.OPCODE_TEXT:
                    # Messages texte (JSON)
                    message = data.decode('utf-8')
                    self._process_text_message(message)
                elif opcode == websocket.ABNF.OPCODE_BINARY:
                    # Données binaires (audio ou waterfall)
                    if len(data) > 0:
                        if data[0] == 0:
                            # Données audio
                            self._process_audio_data(data)
                        elif data[0] == 1:
                            # Données waterfall
                            self._process_waterfall_data(data)
            except websocket.WebSocketTimeoutException:
                # Timeout normal, continue la boucle
                continue
            except websocket.WebSocketConnectionClosedException:
                logger.warning(f"Connexion WebSocket fermée pour {self.name}")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Erreur dans le thread WebSocket pour {self.name}: {str(e)}")
                self.connected = False
                break
        
        logger.info(f"Thread WebSocket terminé pour {self.name}")
    
    def _process_text_message(self, message):
        """Traite un message texte du serveur."""
        if message.startswith('MSG'):
            # Confirmation d'authentification
            self.auth_done = True
        elif message.startswith('ERR'):
            logger.error(f"Erreur KiwiSDR: {message}")
    
    def _process_audio_data(self, data):
        """
        Traite les données audio du serveur.
        
        Format:
        - Byte 0: Type (0 pour audio)
        - Byte 1-2: Séquence
        - Byte 3: Flags
        - Reste: Échantillons audio au format int16
        """
        try:
            # Extraire les échantillons (sauter l'en-tête de 4 octets)
            samples = np.frombuffer(data[4:], dtype=np.int16)
            
            # Convertir en flottants entre -1 et 1 pour le traitement ultérieur
            float_samples = samples.astype(np.float32) / 32768.0
            
            # Ajouter à la file d'attente, éviter le blocage si pleine
            if not self.audio_queue.full():
                self.audio_queue.put(float_samples.tolist(), block=False)
            else:
                # File pleine, on ignore ces échantillons
                pass
        except Exception as e:
            logger.error(f"Erreur lors du traitement des données audio: {str(e)}")
    
    def _process_waterfall_data(self, data):
        """
        Traite les données de waterfall du serveur.
        
        Format:
        - Byte 0: Type (1 pour waterfall)
        - Byte 1-2: Séquence
        - Byte 3: Compression
        - Reste: Données du waterfall (compressées ou non)
        """
        try:
            # Les données sont des valeurs de puissance en dBm, compressées
            # On se contente de les transférer telles quelles au client
            
            # Stocker les données brutes pour le waterfall
            if not self.waterfall_queue.full():
                # Convertir en liste de bytes pour JSON
                waterfall_bytes = [b for b in data[4:]]
                self.waterfall_queue.put(waterfall_bytes, block=False)
                self.last_waterfall_data = waterfall_bytes
            else:
                # File pleine, on ignore ces données
                pass
        except Exception as e:
            logger.error(f"Erreur lors du traitement des données waterfall: {str(e)}")
    
    def get_audio_packet(self, timeout=0.1):
        """
        Récupère un packet audio de la file d'attente.
        
        Args:
            timeout: Temps d'attente maximum en secondes
            
        Returns:
            Liste d'échantillons audio flottants ou None si aucune donnée disponible
        """
        try:
            return self.audio_queue.get(timeout=timeout, block=True)
        except Empty:
            return None
    
    def get_waterfall_data(self, timeout=0.1):
        """
        Récupère les données waterfall de la file d'attente.
        
        Args:
            timeout: Temps d'attente maximum en secondes
            
        Returns:
            Données waterfall brutes ou None si aucune donnée disponible
        """
        try:
            return self.waterfall_queue.get(timeout=timeout, block=True)
        except Empty:
            # Retourner les dernières données connues si aucune nouvelle n'est disponible
            return self.last_waterfall_data 