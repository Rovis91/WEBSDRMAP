"""
Module de gestion des flux audio pour les récepteurs KiwiSDR.

Ce module permet de:
- Extraire et traiter les données audio provenant des KiwiSDR
- Extraire les données I/Q pour le traitement du signal
- Gérer différents modes de modulation (AM, FM, SSB)
- Mettre en buffer les données pour gérer la latence
"""

import asyncio
import collections
import numpy as np
import struct
import time
from typing import Dict, Any, Optional, Union, List, Callable, Tuple, Deque

from src.utils.logger import get_logger
from src.sdr_client.kiwi_connection import KiwiSDRMode, KiwiConnection

# Configuration du logger
logger = get_logger(__name__)


class AudioStreamError(Exception):
    """Exception levée lors d'erreurs de traitement du flux audio."""
    pass


class AudioBuffer:
    """
    Classe de buffer circulaire pour les données audio.
    
    Cette classe gère un buffer circulaire pour stocker les échantillons audio
    et permet de les récupérer de façon fluide pour éviter les discontinuités.
    """
    
    def __init__(self, buffer_size: int = 44100*5):
        """
        Initialise un buffer audio.
        
        Args:
            buffer_size: Taille du buffer en nombre d'échantillons (par défaut 5 secondes à 44.1kHz)
        """
        self.buffer_size = buffer_size
        self.buffer = collections.deque(maxlen=buffer_size)
        self.last_add_time = 0
        self.overflow_count = 0
        self.underflow_count = 0
    
    def add_samples(self, samples: np.ndarray) -> None:
        """
        Ajoute des échantillons au buffer.
        
        Args:
            samples: Tableau NumPy d'échantillons audio
        """
        # Vérifier si le buffer est plein
        if len(self.buffer) + len(samples) > self.buffer_size:
            self.overflow_count += 1
            if self.overflow_count % 10 == 0:
                logger.warning(f"Dépassement de capacité du buffer audio ({self.overflow_count} fois)")
        
        # Ajouter les échantillons au buffer
        for sample in samples:
            self.buffer.append(sample)
        
        self.last_add_time = time.time()
    
    def get_samples(self, num_samples: int) -> np.ndarray:
        """
        Récupère des échantillons du buffer.
        
        Args:
            num_samples: Nombre d'échantillons à récupérer
            
        Returns:
            Tableau NumPy d'échantillons audio
            
        Raises:
            AudioStreamError: Si le buffer ne contient pas assez d'échantillons
        """
        if len(self.buffer) < num_samples:
            self.underflow_count += 1
            if self.underflow_count % 10 == 0:
                logger.warning(f"Buffer audio insuffisant ({self.underflow_count} fois)")
            
            # Retourner des zéros si le buffer est vide
            return np.zeros(num_samples)
        
        # Récupérer les échantillons
        samples = []
        for _ in range(num_samples):
            samples.append(self.buffer.popleft())
        
        return np.array(samples)
    
    def get_available_samples(self) -> int:
        """
        Retourne le nombre d'échantillons disponibles dans le buffer.
        
        Returns:
            Nombre d'échantillons disponibles
        """
        return len(self.buffer)
    
    def clear(self) -> None:
        """Vide le buffer."""
        self.buffer.clear()
        self.overflow_count = 0
        self.underflow_count = 0


class AudioProcessor:
    """
    Classe de traitement des données audio.
    
    Cette classe traite les données brutes reçues du KiwiSDR pour les convertir
    en échantillons audio utilisables ou en données I/Q pour le traitement du signal.
    """
    
    def __init__(self, sample_rate: int = 12000):
        """
        Initialise un processeur audio.
        
        Args:
            sample_rate: Taux d'échantillonnage en Hz (12 kHz par défaut pour KiwiSDR)
        """
        self.sample_rate = sample_rate
        self.channel_count = 2  # Stéréo pour I/Q, mono pour audio
    
    def process_sound_data(self, data: bytes, mode: KiwiSDRMode) -> np.ndarray:
        """
        Traite les données audio brutes du KiwiSDR.
        
        Args:
            data: Données audio brutes reçues du KiwiSDR
            mode: Mode de modulation actuel
            
        Returns:
            Tableau NumPy d'échantillons audio traités
            
        Raises:
            AudioStreamError: En cas d'erreur de traitement des données
        """
        try:
            # Déterminer le format des données selon le mode
            if mode == KiwiSDRMode.IQ:
                # Format I/Q: 2 canaux (I et Q), échantillons 16 bits signés
                # Les données sont organisées en [I, Q, I, Q, ...]
                samples = np.frombuffer(data, dtype=np.int16)
                samples = samples.astype(np.float32) / 32768.0  # Normalisation à [-1, 1]
                
                # Réorganiser en tableaux I et Q séparés
                i_samples = samples[0::2]
                q_samples = samples[1::2]
                
                # Retourner sous forme de tableau complexe pour le traitement I/Q
                return i_samples + 1j * q_samples
            else:
                # Format audio normal: 1 canal, échantillons 16 bits signés
                samples = np.frombuffer(data, dtype=np.int16)
                return samples.astype(np.float32) / 32768.0  # Normalisation à [-1, 1]
        
        except Exception as e:
            raise AudioStreamError(f"Erreur lors du traitement des données audio: {str(e)}")
    
    def process_waterfall_data(self, data: bytes) -> np.ndarray:
        """
        Traite les données waterfall brutes du KiwiSDR.
        
        Args:
            data: Données waterfall brutes reçues du KiwiSDR
            
        Returns:
            Tableau NumPy de données de spectrogramme
            
        Raises:
            AudioStreamError: En cas d'erreur de traitement des données
        """
        try:
            # Données waterfall: 1024 valeurs FFT sur 8 bits (0-255)
            samples = np.frombuffer(data, dtype=np.uint8)
            return samples
        
        except Exception as e:
            raise AudioStreamError(f"Erreur lors du traitement des données waterfall: {str(e)}")


class AudioStream:
    """
    Classe de gestion des flux audio des récepteurs KiwiSDR.
    
    Cette classe permet:
    - La récupération et le traitement des données audio
    - L'extraction des données I/Q
    - La gestion des buffers et de la latence
    - Le traitement selon le mode de modulation
    """
    
    def __init__(self, kiwi: KiwiConnection, buffer_size: int = 44100*5):
        """
        Initialise un flux audio pour un récepteur KiwiSDR.
        
        Args:
            kiwi: Connexion KiwiSDR
            buffer_size: Taille du buffer en nombre d'échantillons
        """
        self.kiwi = kiwi
        self.processor = AudioProcessor()
        self.audio_buffer = AudioBuffer(buffer_size)
        self.iq_buffer = AudioBuffer(buffer_size)
        self.is_running = False
        self.last_error = None
        
        # Callbacks pour les données traitées
        self.audio_callback = None
        self.iq_callback = None
    
    async def start(self, mode: KiwiSDRMode = KiwiSDRMode.AM) -> bool:
        """
        Démarre le flux audio depuis le récepteur KiwiSDR.
        
        Args:
            mode: Mode de modulation à utiliser
            
        Returns:
            True si le démarrage a réussi, False sinon
        """
        logger.info(f"Démarrage du flux audio pour {self.kiwi.name} en mode {mode.value}")
        
        try:
            # Définir le mode
            if not await self.kiwi.set_mode(mode):
                logger.error(f"Impossible de définir le mode {mode.value} pour {self.kiwi.name}")
                return False
            
            # Démarrer le flux audio
            if not await self.kiwi.start_audio_stream(self._on_sound_data):
                logger.error(f"Impossible de démarrer le flux audio pour {self.kiwi.name}")
                return False
            
            self.is_running = True
            return True
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Erreur lors du démarrage du flux audio pour {self.kiwi.name}: {e}")
            return False
    
    async def stop(self) -> None:
        """Arrête le flux audio."""
        logger.info(f"Arrêt du flux audio pour {self.kiwi.name}")
        self.is_running = False
        
        # Vider les buffers
        self.audio_buffer.clear()
        self.iq_buffer.clear()
    
    def register_audio_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Enregistre un callback pour les données audio traitées.
        
        Args:
            callback: Fonction à appeler avec les données audio
        """
        self.audio_callback = callback
    
    def register_iq_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Enregistre un callback pour les données I/Q traitées.
        
        Args:
            callback: Fonction à appeler avec les données I/Q
        """
        self.iq_callback = callback
    
    def get_audio_samples(self, num_samples: int) -> np.ndarray:
        """
        Récupère des échantillons audio du buffer.
        
        Args:
            num_samples: Nombre d'échantillons à récupérer
            
        Returns:
            Tableau NumPy d'échantillons audio
        """
        return self.audio_buffer.get_samples(num_samples)
    
    def get_iq_samples(self, num_samples: int) -> np.ndarray:
        """
        Récupère des échantillons I/Q du buffer.
        
        Args:
            num_samples: Nombre d'échantillons à récupérer
            
        Returns:
            Tableau NumPy d'échantillons I/Q complexes
        """
        return self.iq_buffer.get_samples(num_samples)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère l'état actuel du flux audio.
        
        Returns:
            Dictionnaire contenant les informations d'état
        """
        return {
            "is_running": self.is_running,
            "last_error": self.last_error,
            "audio_buffer_level": self.audio_buffer.get_available_samples(),
            "iq_buffer_level": self.iq_buffer.get_available_samples(),
            "audio_buffer_size": self.audio_buffer.buffer_size,
            "audio_overflows": self.audio_buffer.overflow_count,
            "audio_underflows": self.audio_buffer.underflow_count
        }
    
    def _on_sound_data(self, data: bytes) -> None:
        """
        Callback appelé lorsque des données audio sont reçues du KiwiSDR.
        
        Args:
            data: Données audio brutes
        """
        if not self.is_running:
            return
        
        try:
            # Obtenir le mode actuel du récepteur
            mode = self.kiwi.current_mode
            
            # Traiter les données selon le mode
            if mode == KiwiSDRMode.IQ:
                # Traitement I/Q
                samples = self.processor.process_sound_data(data, mode)
                self.iq_buffer.add_samples(samples)
                
                # Appel du callback I/Q si défini
                if self.iq_callback:
                    self.iq_callback(samples)
            else:
                # Traitement audio normal
                samples = self.processor.process_sound_data(data, mode)
                self.audio_buffer.add_samples(samples)
                
                # Appel du callback audio si défini
                if self.audio_callback:
                    self.audio_callback(samples)
                
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Erreur lors du traitement des données audio de {self.kiwi.name}: {e}")


class AudioStreamManager:
    """
    Gestionnaire de flux audio pour plusieurs récepteurs KiwiSDR.
    
    Cette classe permet:
    - La gestion de plusieurs flux audio simultanés
    - La synchronisation des flux pour le traitement multi-récepteurs
    - La gestion de la priorité des connexions
    """
    
    def __init__(self):
        """Initialise un gestionnaire de flux audio."""
        self.streams = {}  # {name: AudioStream}
        self.max_connections = 5
    
    async def add_stream(self, kiwi: KiwiConnection) -> bool:
        """
        Ajoute un flux audio pour un récepteur KiwiSDR.
        
        Args:
            kiwi: Connexion KiwiSDR
            
        Returns:
            True si l'ajout a réussi, False sinon
        """
        # Vérifier si le nombre maximal de connexions est atteint
        if len(self.streams) >= self.max_connections:
            logger.warning(f"Nombre maximal de connexions atteint ({self.max_connections})")
            return False
        
        # Vérifier si le récepteur est déjà dans la liste
        if kiwi.name in self.streams:
            logger.warning(f"Le récepteur {kiwi.name} est déjà dans la liste des flux")
            return False
        
        logger.info(f"Ajout du flux audio pour le récepteur {kiwi.name}")
        
        # Créer et ajouter le flux
        stream = AudioStream(kiwi)
        self.streams[kiwi.name] = stream
        
        return True
    
    async def remove_stream(self, name: str) -> bool:
        """
        Supprime un flux audio.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si la suppression a réussi, False sinon
        """
        if name not in self.streams:
            logger.warning(f"Le récepteur {name} n'est pas dans la liste des flux")
            return False
        
        logger.info(f"Suppression du flux audio pour le récepteur {name}")
        
        # Arrêter le flux
        await self.streams[name].stop()
        
        # Supprimer le flux
        del self.streams[name]
        
        return True
    
    async def start_all(self, mode: KiwiSDRMode = KiwiSDRMode.AM) -> Dict[str, bool]:
        """
        Démarre tous les flux audio.
        
        Args:
            mode: Mode de modulation à utiliser
            
        Returns:
            Dictionnaire {nom_récepteur: succès} indiquant le résultat pour chaque flux
        """
        logger.info(f"Démarrage de tous les flux audio en mode {mode.value}")
        
        results = {}
        for name, stream in self.streams.items():
            results[name] = await stream.start(mode)
        
        return results
    
    async def stop_all(self) -> None:
        """Arrête tous les flux audio."""
        logger.info("Arrêt de tous les flux audio")
        
        for stream in self.streams.values():
            await stream.stop()
    
    def get_stream(self, name: str) -> Optional[AudioStream]:
        """
        Récupère un flux audio par son nom.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            Flux audio ou None si non trouvé
        """
        return self.streams.get(name)
    
    def get_all_streams(self) -> Dict[str, AudioStream]:
        """
        Récupère tous les flux audio.
        
        Returns:
            Dictionnaire {nom_récepteur: flux_audio}
        """
        return self.streams.copy() 