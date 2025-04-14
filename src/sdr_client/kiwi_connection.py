"""
Module de connexion aux récepteurs KiwiSDR.

Ce module permet de:
- Se connecter aux récepteurs KiwiSDR via WebSocket
- Gérer les commandes de configuration des récepteurs
- Récupérer les données brutes (audio, I/Q, waterfall)
- Gérer les déconnexions et reconnexions automatiques
- Surveiller l'état de santé des connexions
"""

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Dict, Any, Optional, Union, List, Callable, Tuple

import websocket
from websocket import WebSocketApp

from src.utils.logger import get_logger

# Configuration du logger
logger = get_logger(__name__)


class KiwiSDRMode(Enum):
    """Modes de modulation supportés par KiwiSDR."""
    AM = "am"
    FM = "fm"
    NFM = "nfm"  # Narrow FM
    USB = "usb"  # Upper Sideband
    LSB = "lsb"  # Lower Sideband
    CW = "cw"   # Continuous Wave
    IQ = "iq"   # I/Q data


class KiwiMessageType(Enum):
    """Types de messages échangés avec le KiwiSDR."""
    SOUND = "SND"
    WATERFALL = "W"
    STATUS = "MSG"
    CONFIGURATION = "SET"
    ERROR = "ERR"
    AUTH = "AUTH"


class KiwiConnectionState(Enum):
    """États possibles d'une connexion KiwiSDR."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"
    ERROR = "error"


class KiwiConnectionError(Exception):
    """Exception levée lors d'erreurs de connexion au KiwiSDR."""
    pass


class KiwiConnection:
    """
    Classe gérant une connexion à un récepteur KiwiSDR.
    
    Cette classe gère:
    - L'établissement d'une connexion WebSocket
    - L'authentification et la configuration du récepteur
    - La gestion des déconnexions et reconnexions
    - La récupération des données audio, I/Q ou waterfall
    - La surveillance de l'état de santé de la connexion
    """
    
    def __init__(self, 
                 url: str, 
                 name: str = None,
                 location: Dict[str, float] = None,
                 connection_timeout: int = 30,
                 reconnect_attempts: int = 3,
                 reconnect_delay: int = 5):
        """
        Initialise une connexion KiwiSDR.
        
        Args:
            url: URL du WebSocket KiwiSDR (ex: wss://kiwisdr.example.com/kiwi)
            name: Nom descriptif du récepteur
            location: Dictionnaire contenant la latitude et longitude du récepteur
            connection_timeout: Timeout de connexion en secondes
            reconnect_attempts: Nombre de tentatives de reconnexion
            reconnect_delay: Délai entre les tentatives de reconnexion en secondes
        """
        # Paramètres de connexion
        self.url = url
        self.name = name or url
        self.location = location or {"latitude": 0.0, "longitude": 0.0}
        self.connection_timeout = connection_timeout
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        
        # État de la connexion
        self.state = KiwiConnectionState.DISCONNECTED
        self.ws = None
        self.last_error = None
        self.last_activity = 0
        self.reconnect_count = 0
        
        # Configuration actuelle
        self.current_freq = 0       # Hz
        self.current_mode = None    # KiwiSDRMode
        self.current_bandwidth = 0  # Hz
        
        # Callbacks pour les données reçues
        self.sound_callback = None
        self.waterfall_callback = None
        self.status_callback = None
        
        # Statistiques
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.connected_since = None
        self.connection_drops = 0
        
        # Indicateurs
        self.stop_requested = False
        self.is_authenticated = False
    
    async def connect(self) -> bool:
        """
        Établit une connexion WebSocket au récepteur KiwiSDR.
        
        Returns:
            True si la connexion a réussi, False sinon
        """
        if self.state in [KiwiConnectionState.CONNECTED, KiwiConnectionState.READY]:
            logger.warning(f"Tentative de connexion alors que déjà connecté à {self.name}")
            return True
        
        logger.info(f"Connexion au récepteur KiwiSDR: {self.name} ({self.url})")
        self.state = KiwiConnectionState.CONNECTING
        self.stop_requested = False
        
        try:
            # Création de la connexion WebSocket
            self.ws = WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Lancement de la connexion dans un thread séparé
            import threading
            def run_websocket():
                self.ws.run_forever()
            
            ws_thread = threading.Thread(target=run_websocket)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Attente de la connexion
            timeout = time.time() + self.connection_timeout
            while self.state == KiwiConnectionState.CONNECTING and time.time() < timeout:
                await asyncio.sleep(0.1)
            
            # Vérification de l'état de la connexion
            if self.state not in [KiwiConnectionState.CONNECTED, KiwiConnectionState.READY]:
                error_msg = f"Échec de la connexion à {self.name}: {self.last_error or 'timeout'}"
                logger.error(error_msg)
                self.state = KiwiConnectionState.ERROR
                return False
            
            logger.info(f"Connexion établie au récepteur {self.name}")
            self.connected_since = time.time()
            return True
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Erreur lors de la connexion à {self.name}: {e}")
            self.state = KiwiConnectionState.ERROR
            return False
    
    async def disconnect(self) -> None:
        """Ferme la connexion au récepteur KiwiSDR."""
        if self.state in [KiwiConnectionState.DISCONNECTED, KiwiConnectionState.ERROR]:
            return
        
        logger.info(f"Déconnexion du récepteur {self.name}")
        self.stop_requested = True
        
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logger.warning(f"Erreur lors de la fermeture de la connexion à {self.name}: {e}")
        
        self.state = KiwiConnectionState.DISCONNECTED
        self.is_authenticated = False
    
    async def reconnect(self) -> bool:
        """
        Tente de reconnecter au récepteur KiwiSDR.
        
        Returns:
            True si la reconnexion a réussi, False sinon
        """
        if self.stop_requested:
            return False
        
        if self.reconnect_count >= self.reconnect_attempts:
            logger.error(f"Nombre maximal de tentatives de reconnexion atteint pour {self.name}")
            return False
        
        logger.info(f"Tentative de reconnexion à {self.name} ({self.reconnect_count + 1}/{self.reconnect_attempts})")
        self.reconnect_count += 1
        self.connection_drops += 1
        
        # Attente avant la tentative de reconnexion
        await asyncio.sleep(self.reconnect_delay)
        
        # Fermeture de la connexion existante si nécessaire
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        
        # Tentative de reconnexion
        result = await self.connect()
        
        if result:
            # Si la reconnexion a réussi, reconfigurer le récepteur
            if self.current_freq > 0 and self.current_mode:
                await self.set_frequency(self.current_freq)
                await self.set_mode(self.current_mode, self.current_bandwidth)
            
            self.reconnect_count = 0
            return True
        
        return False
    
    async def authenticate(self) -> bool:
        """
        Authentifie la connexion au récepteur KiwiSDR.
        
        Returns:
            True si l'authentification a réussi, False sinon
        """
        if self.state != KiwiConnectionState.CONNECTED:
            logger.error(f"Impossible de s'authentifier: non connecté à {self.name}")
            return False
        
        if self.is_authenticated:
            return True
        
        logger.info(f"Authentification auprès du récepteur {self.name}")
        
        try:
            # Message d'authentification pour le KiwiSDR
            auth_msg = {
                "name": "SDR Triangulation Tool",
                "type": "EXT_CLIENT",
                "ext_name": "Triangulation"
            }
            
            # Envoi du message d'authentification
            self._send_message("SET auth", json.dumps(auth_msg))
            
            # Attente de l'authentification
            timeout = time.time() + 5  # 5 secondes max
            while not self.is_authenticated and time.time() < timeout:
                await asyncio.sleep(0.1)
            
            if not self.is_authenticated:
                logger.error(f"Échec de l'authentification auprès de {self.name}")
                return False
            
            logger.info(f"Authentification réussie auprès de {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification auprès de {self.name}: {e}")
            return False
    
    async def set_frequency(self, frequency: int) -> bool:
        """
        Définit la fréquence d'écoute du récepteur.
        
        Args:
            frequency: Fréquence en Hz
            
        Returns:
            True si la configuration a réussi, False sinon
        """
        if self.state != KiwiConnectionState.READY:
            logger.error(f"Impossible de configurer la fréquence: non prêt ({self.name})")
            return False
        
        logger.info(f"Configuration de la fréquence du récepteur {self.name}: {frequency} Hz")
        
        try:
            # Formatage de la commande de fréquence pour le KiwiSDR
            self._send_message(f"SET freq={frequency}")
            self.current_freq = frequency
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de la fréquence de {self.name}: {e}")
            return False
    
    async def set_mode(self, mode: KiwiSDRMode, bandwidth: int = 0) -> bool:
        """
        Définit le mode de modulation et la bande passante du récepteur.
        
        Args:
            mode: Mode de modulation
            bandwidth: Bande passante en Hz (0 pour la valeur par défaut du mode)
            
        Returns:
            True si la configuration a réussi, False sinon
        """
        if self.state != KiwiConnectionState.READY:
            logger.error(f"Impossible de configurer le mode: non prêt ({self.name})")
            return False
        
        logger.info(f"Configuration du mode du récepteur {self.name}: {mode.value}, BW={bandwidth} Hz")
        
        try:
            # Si mode est une énumération, obtenir la valeur
            mode_value = mode.value if isinstance(mode, KiwiSDRMode) else mode
            
            # Formatage de la commande de mode pour le KiwiSDR
            self._send_message(f"SET mod={mode_value}")
            
            # Configuration de la bande passante si spécifiée
            if bandwidth > 0:
                self._send_message(f"SET compression=0 bandwidth={bandwidth}")
            
            self.current_mode = mode
            self.current_bandwidth = bandwidth
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la configuration du mode de {self.name}: {e}")
            return False
    
    async def start_audio_stream(self, callback: Callable[[bytes], None]) -> bool:
        """
        Démarre le flux audio depuis le récepteur.
        
        Args:
            callback: Fonction appelée avec les données audio reçues
            
        Returns:
            True si le démarrage a réussi, False sinon
        """
        if self.state != KiwiConnectionState.READY:
            logger.error(f"Impossible de démarrer le flux audio: non prêt ({self.name})")
            return False
        
        logger.info(f"Démarrage du flux audio depuis le récepteur {self.name}")
        
        try:
            # Enregistrement du callback
            self.sound_callback = callback
            
            # Formatage de la commande de démarrage audio pour le KiwiSDR
            self._send_message("SET SND")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du flux audio de {self.name}: {e}")
            return False
    
    async def start_waterfall_stream(self, callback: Callable[[bytes], None]) -> bool:
        """
        Démarre le flux de données waterfall depuis le récepteur.
        
        Args:
            callback: Fonction appelée avec les données waterfall reçues
            
        Returns:
            True si le démarrage a réussi, False sinon
        """
        if self.state != KiwiConnectionState.READY:
            logger.error(f"Impossible de démarrer le flux waterfall: non prêt ({self.name})")
            return False
        
        logger.info(f"Démarrage du flux waterfall depuis le récepteur {self.name}")
        
        try:
            # Enregistrement du callback
            self.waterfall_callback = callback
            
            # Formatage de la commande de démarrage waterfall pour le KiwiSDR
            self._send_message("SET waterfall=1")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du flux waterfall de {self.name}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère l'état actuel de la connexion.
        
        Returns:
            Dictionnaire contenant les informations d'état
        """
        return {
            "name": self.name,
            "url": self.url,
            "location": self.location,
            "state": self.state.value,
            "connected_since": self.connected_since,
            "last_activity": self.last_activity,
            "current_freq": self.current_freq,
            "current_mode": self.current_mode.value if self.current_mode else None,
            "current_bandwidth": self.current_bandwidth,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
            "connection_drops": self.connection_drops,
            "last_error": self.last_error
        }
    
    def is_healthy(self) -> bool:
        """
        Vérifie si la connexion est saine.
        
        Returns:
            True si la connexion est active et fonctionne normalement, False sinon
        """
        if self.state != KiwiConnectionState.READY:
            return False
        
        # Vérifier si l'activité est récente (moins de 5 secondes)
        if time.time() - self.last_activity > 5:
            return False
        
        return True
    
    def _send_message(self, message: str, data: str = None) -> None:
        """
        Envoie un message au récepteur KiwiSDR.
        
        Args:
            message: Message à envoyer
            data: Données JSON optionnelles
            
        Raises:
            KiwiConnectionError: Si l'envoi échoue
        """
        if not self.ws:
            raise KiwiConnectionError(f"Aucune connexion WebSocket active pour {self.name}")
        
        try:
            if data:
                full_message = f"{message} {data}"
            else:
                full_message = message
            
            self.ws.send(full_message)
            self.tx_bytes += len(full_message)
            self.last_activity = time.time()
            
        except Exception as e:
            self.last_error = str(e)
            raise KiwiConnectionError(f"Erreur lors de l'envoi d'un message à {self.name}: {e}")
    
    def _on_open(self, ws) -> None:
        """Callback appelé lorsque la connexion WebSocket est ouverte."""
        logger.info(f"Connexion WebSocket ouverte pour {self.name}")
        self.state = KiwiConnectionState.CONNECTED
        self.last_activity = time.time()
    
    def _on_message(self, ws, message: str) -> None:
        """
        Callback appelé lorsqu'un message est reçu.
        
        Args:
            ws: WebSocket
            message: Message reçu
        """
        # Mise à jour des statistiques
        self.rx_bytes += len(message)
        self.last_activity = time.time()
        
        try:
            # Analyser le type de message
            if message.startswith("MSG"):
                self._handle_msg_message(message[4:])
            elif message.startswith("SND"):
                self._handle_sound_message(message[4:])
            elif message.startswith("W"):
                self._handle_waterfall_message(message[2:])
            elif message.startswith("ERR"):
                self._handle_error_message(message[4:])
            else:
                logger.debug(f"Message non traité de {self.name}: {message[:20]}...")
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement d'un message de {self.name}: {e}")
    
    def _on_error(self, ws, error) -> None:
        """
        Callback appelé en cas d'erreur WebSocket.
        
        Args:
            ws: WebSocket
            error: Erreur survenue
        """
        self.last_error = str(error)
        logger.error(f"Erreur WebSocket pour {self.name}: {error}")
        self.state = KiwiConnectionState.ERROR
    
    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """
        Callback appelé lors de la fermeture de la connexion WebSocket.
        
        Args:
            ws: WebSocket
            close_status_code: Code de statut de fermeture
            close_msg: Message de fermeture
        """
        if self.stop_requested:
            logger.info(f"Connexion WebSocket fermée pour {self.name}")
            self.state = KiwiConnectionState.DISCONNECTED
        else:
            logger.warning(f"Connexion WebSocket fermée inopinément pour {self.name}")
            self.state = KiwiConnectionState.ERROR
            
            # Lancer une tentative de reconnexion asynchrone
            async def try_reconnect():
                await self.reconnect()
            
            asyncio.create_task(try_reconnect())
    
    def _handle_msg_message(self, msg_data: str) -> None:
        """
        Traite un message de type MSG (statut).
        
        Args:
            msg_data: Données du message
        """
        try:
            # Les messages MSG sont généralement du JSON
            data = json.loads(msg_data)
            
            # Traitement des différents types de messages
            if "auth" in data:
                # Réponse d'authentification
                if data["auth"] == "ok":
                    self.is_authenticated = True
                    self.state = KiwiConnectionState.READY
                    logger.info(f"Authentification réussie pour {self.name}")
                else:
                    logger.error(f"Authentification refusée pour {self.name}: {data}")
            
            # Appel du callback si défini
            if self.status_callback:
                self.status_callback(data)
                
        except json.JSONDecodeError:
            logger.warning(f"Message MSG invalide de {self.name}: {msg_data[:50]}...")
        except Exception as e:
            logger.error(f"Erreur lors du traitement d'un message MSG de {self.name}: {e}")
    
    def _handle_sound_message(self, sound_data: str) -> None:
        """
        Traite un message de type SND (audio).
        
        Args:
            sound_data: Données audio
        """
        if self.sound_callback:
            # Les données sont en binaire, conversion nécessaire
            try:
                # Conversion en bytes
                binary_data = sound_data.encode('latin-1')  # Préserve les bytes tels quels
                self.sound_callback(binary_data)
            except Exception as e:
                logger.error(f"Erreur lors du traitement des données audio de {self.name}: {e}")
    
    def _handle_waterfall_message(self, waterfall_data: str) -> None:
        """
        Traite un message de type W (waterfall).
        
        Args:
            waterfall_data: Données waterfall
        """
        if self.waterfall_callback:
            # Les données sont en binaire, conversion nécessaire
            try:
                # Conversion en bytes
                binary_data = waterfall_data.encode('latin-1')  # Préserve les bytes tels quels
                self.waterfall_callback(binary_data)
            except Exception as e:
                logger.error(f"Erreur lors du traitement des données waterfall de {self.name}: {e}")
    
    def _handle_error_message(self, error_data: str) -> None:
        """
        Traite un message de type ERR (erreur).
        
        Args:
            error_data: Données d'erreur
        """
        self.last_error = error_data
        logger.error(f"Erreur reçue du récepteur {self.name}: {error_data}") 