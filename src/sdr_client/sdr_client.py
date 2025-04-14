"""
Module d'intégration du client SDR complet.

Ce module permet de:
- Intégrer les fonctionnalités de kiwi_connection.py et audio_stream.py
- Gérer simultanément plusieurs connexions SDR via asyncio
- Implémenter un système de prioritisation des ressources
- Fournir une interface unifiée pour les KiwiSDR
"""

import asyncio
import time
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Tuple, Set
import heapq

from src.utils.logger import get_logger
from src.utils.performance import timeit
from src.sdr_client.kiwi_connection import KiwiConnection, KiwiSDRMode, KiwiConnectionState
from src.sdr_client.audio_stream import AudioStream, AudioStreamManager
from src.sdr_client.waterfall_stream import WaterfallStream, WaterfallStreamManager

# Configuration du logger
logger = get_logger(__name__)


class SDRClientPriority(Enum):
    """Niveaux de priorité pour les connexions aux KiwiSDR."""
    CRITICAL = 0  # Priorité maximale (ex: surveillance d'urgence)
    HIGH = 1      # Haute priorité (ex: détection de signaux)
    NORMAL = 2    # Priorité normale (ex: écoute régulière)
    LOW = 3       # Basse priorité (ex: recherche de fond)
    BACKGROUND = 4  # Priorité minimale (ex: cartographie)


class SDRResource:
    """Classe représentant une ressource SDR avec sa priorité."""
    
    def __init__(self, name: str, priority: SDRClientPriority = SDRClientPriority.NORMAL):
        """
        Initialise une ressource SDR.
        
        Args:
            name: Nom identifiant la ressource
            priority: Niveau de priorité de la ressource
        """
        self.name = name
        self.priority = priority
        self.last_access = time.time()
    
    def __lt__(self, other):
        """Surcharge de l'opérateur < pour permettre le tri par priorité."""
        if not isinstance(other, SDRResource):
            return NotImplemented
        # Tri par priorité d'abord, puis par dernier accès (le plus ancien d'abord)
        return (self.priority.value, self.last_access) < (other.priority.value, other.last_access)
    
    def update_access_time(self):
        """Met à jour le timestamp du dernier accès."""
        self.last_access = time.time()


class SDRClient:
    """
    Client SDR complet intégrant les fonctionnalités de connexion et de flux audio.
    
    Cette classe:
    - Gère plusieurs connexions KiwiSDR simultanément
    - Coordonne les flux audio et waterfall
    - Implémente un système de prioritisation des ressources SDR
    - Fournit une interface unifiée pour l'accès aux KiwiSDR
    """
    
    def __init__(self, max_connections: int = 5):
        """
        Initialise le client SDR.
        
        Args:
            max_connections: Nombre maximal de connexions simultanées
        """
        self.max_connections = max_connections
        self.connections: Dict[str, KiwiConnection] = {}
        self.connection_resources: Dict[str, SDRResource] = {}
        self.audio_manager = AudioStreamManager()
        self.waterfall_manager = WaterfallStreamManager()
        self.active_connections: Set[str] = set()
        self.connection_queue = []  # File de priorité pour les connexions
        self.is_running = False
        self.connection_loop_task = None
    
    async def add_receiver(self, 
                          url: str, 
                          name: str = None,
                          location: Dict[str, float] = None,
                          priority: SDRClientPriority = SDRClientPriority.NORMAL) -> bool:
        """
        Ajoute un récepteur KiwiSDR au client.
        
        Args:
            url: URL du WebSocket KiwiSDR (ex: wss://kiwisdr.example.com/kiwi)
            name: Nom descriptif du récepteur (utilise l'URL si non spécifié)
            location: Dictionnaire contenant la latitude et longitude du récepteur
            priority: Niveau de priorité pour ce récepteur
        
        Returns:
            True si l'ajout a réussi, False sinon
        """
        if name is None:
            name = url
        
        if name in self.connections:
            logger.warning(f"Le récepteur {name} existe déjà")
            return False
        
        logger.info(f"Ajout du récepteur {name} avec priorité {priority.name}")
        
        # Créer la connexion
        kiwi = KiwiConnection(url, name, location)
        
        # Enregistrer la connexion et sa ressource associée
        self.connections[name] = kiwi
        self.connection_resources[name] = SDRResource(name, priority)
        
        # Ajouter à la file de priorité si nous gérons activement les connexions
        if self.is_running:
            await self._prioritize_connections()
        
        return True
    
    async def remove_receiver(self, name: str) -> bool:
        """
        Supprime un récepteur KiwiSDR du client.
        
        Args:
            name: Nom du récepteur à supprimer
            
        Returns:
            True si la suppression a réussi, False sinon
        """
        if name not in self.connections:
            logger.warning(f"Impossible de supprimer: le récepteur {name} n'existe pas")
            return False
        
        logger.info(f"Suppression du récepteur {name}")
        
        # Déconnecter si actif
        if name in self.active_connections:
            await self.disconnect_receiver(name)
        
        # Supprimer des structures de données
        del self.connections[name]
        del self.connection_resources[name]
        
        # Mettre à jour la file de priorité
        if self.is_running:
            await self._prioritize_connections()
        
        return True
    
    @timeit
    async def connect_receiver(self, name: str, 
                              frequency: int = None, 
                              mode: KiwiSDRMode = None) -> bool:
        """
        Connecte un récepteur spécifique.
        
        Args:
            name: Nom du récepteur
            frequency: Fréquence initiale en Hz (optionnel)
            mode: Mode de modulation initial (optionnel)
            
        Returns:
            True si la connexion a réussi, False sinon
        """
        if name not in self.connections:
            logger.error(f"Le récepteur {name} n'existe pas")
            return False
        
        kiwi = self.connections[name]
        
        # Si déjà connecté, mettre à jour la priorité et la dernière utilisation
        if name in self.active_connections:
            self.connection_resources[name].update_access_time()
            logger.info(f"Récepteur {name} déjà connecté, priorité mise à jour")
            
            # Si une fréquence ou un mode est spécifié, les configurer
            if frequency is not None:
                await kiwi.set_frequency(frequency)
            if mode is not None:
                await kiwi.set_mode(mode)
                
            return True
        
        # Vérifier si nous atteignons la limite de connexions
        if len(self.active_connections) >= self.max_connections:
            # Vérifier si cette connexion est prioritaire sur une connexion active
            should_connect, disconnect_target = self._should_prioritize(name)
            
            if should_connect and disconnect_target:
                # Déconnecter la connexion de priorité inférieure
                logger.info(f"Déconnexion de {disconnect_target} pour libérer des ressources pour {name}")
                await self.disconnect_receiver(disconnect_target)
            elif not should_connect:
                logger.warning(f"Limite de connexions atteinte, {name} mis en attente")
                return False
        
        logger.info(f"Connexion au récepteur {name}")
        
        try:
            # Connecter
            if not await kiwi.connect():
                logger.error(f"Échec de la connexion à {name}")
                return False
            
            # Authentifier
            if not await kiwi.authenticate():
                logger.error(f"Échec de l'authentification pour {name}")
                await kiwi.disconnect()
                return False
            
            # Configurer si spécifié
            if frequency is not None:
                if not await kiwi.set_frequency(frequency):
                    logger.error(f"Échec de la configuration de la fréquence pour {name}")
                    await kiwi.disconnect()
                    return False
            
            if mode is not None:
                if not await kiwi.set_mode(mode):
                    logger.error(f"Échec de la configuration du mode pour {name}")
                    await kiwi.disconnect()
                    return False
            
            # Ajouter aux connexions actives
            self.active_connections.add(name)
            self.connection_resources[name].update_access_time()
            
            logger.info(f"Connexion au récepteur {name} réussie")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à {name}: {e}")
            await kiwi.disconnect()
            return False
    
    async def disconnect_receiver(self, name: str) -> bool:
        """
        Déconnecte un récepteur spécifique.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si la déconnexion a réussi, False sinon
        """
        if name not in self.connections:
            logger.error(f"Le récepteur {name} n'existe pas")
            return False
        
        kiwi = self.connections[name]
        
        # Vérifier si la connexion est active
        if name not in self.active_connections:
            logger.warning(f"Le récepteur {name} n'est pas connecté")
            return True
        
        logger.info(f"Déconnexion du récepteur {name}")
        
        try:
            # Arrêter les flux associés
            await self.stop_audio_stream(name)
            await self.stop_waterfall_stream(name)
            
            # Déconnecter
            await kiwi.disconnect()
            
            # Retirer des connexions actives
            self.active_connections.remove(name)
            
            # Mettre à jour la file de priorité
            await self._prioritize_connections()
            
            logger.info(f"Déconnexion du récepteur {name} réussie")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion de {name}: {e}")
            return False
    
    async def start_audio_stream(self, name: str, callback: Callable[[Any], None]) -> bool:
        """
        Démarre le flux audio pour un récepteur spécifique.
        
        Args:
            name: Nom du récepteur
            callback: Fonction de rappel pour les données audio
            
        Returns:
            True si le démarrage a réussi, False sinon
        """
        if name not in self.connections:
            logger.error(f"Le récepteur {name} n'existe pas")
            return False
        
        # Assurer que le récepteur est connecté
        if name not in self.active_connections:
            logger.info(f"Connexion automatique au récepteur {name} pour le flux audio")
            if not await self.connect_receiver(name):
                return False
        
        # Mettre à jour la priorité
        self.connection_resources[name].update_access_time()
        
        # Démarrer le flux audio
        kiwi = self.connections[name]
        return await self.audio_manager.add_stream(kiwi)
    
    async def stop_audio_stream(self, name: str) -> bool:
        """
        Arrête le flux audio pour un récepteur spécifique.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si l'arrêt a réussi, False sinon
        """
        return await self.audio_manager.remove_stream(name)
    
    async def start_waterfall_stream(self, name: str, callback: Callable[[Any], None]) -> bool:
        """
        Démarre le flux waterfall pour un récepteur spécifique.
        
        Args:
            name: Nom du récepteur
            callback: Fonction de rappel pour les données waterfall
            
        Returns:
            True si le démarrage a réussi, False sinon
        """
        if name not in self.connections:
            logger.error(f"Le récepteur {name} n'existe pas")
            return False
        
        # Assurer que le récepteur est connecté
        if name not in self.active_connections:
            logger.info(f"Connexion automatique au récepteur {name} pour le flux waterfall")
            if not await self.connect_receiver(name):
                return False
        
        # Mettre à jour la priorité
        self.connection_resources[name].update_access_time()
        
        # Démarrer le flux waterfall
        kiwi = self.connections[name]
        return await self.waterfall_manager.add_stream(kiwi)
    
    async def stop_waterfall_stream(self, name: str) -> bool:
        """
        Arrête le flux waterfall pour un récepteur spécifique.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si l'arrêt a réussi, False sinon
        """
        return await self.waterfall_manager.remove_stream(name)
    
    async def start(self):
        """
        Démarre le client SDR et la gestion des connexions.
        """
        if self.is_running:
            logger.warning("Le client SDR est déjà en cours d'exécution")
            return
        
        logger.info("Démarrage du client SDR")
        self.is_running = True
        
        # Initialiser la file de priorité
        await self._prioritize_connections()
        
        # Démarrer la boucle de gestion des connexions
        self.connection_loop_task = asyncio.create_task(self._connection_management_loop())
    
    async def stop(self):
        """
        Arrête le client SDR et toutes les connexions.
        """
        if not self.is_running:
            logger.warning("Le client SDR n'est pas en cours d'exécution")
            return
        
        logger.info("Arrêt du client SDR")
        self.is_running = False
        
        # Arrêter la boucle de gestion
        if self.connection_loop_task:
            self.connection_loop_task.cancel()
            try:
                await self.connection_loop_task
            except asyncio.CancelledError:
                pass
        
        # Déconnecter tous les récepteurs
        disconnect_tasks = []
        for name in list(self.active_connections):
            disconnect_tasks.append(self.disconnect_receiver(name))
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks)
    
    def get_connection_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtient le statut de toutes les connexions.
        
        Returns:
            Dictionnaire avec le statut de chaque connexion
        """
        status = {}
        
        for name, kiwi in self.connections.items():
            resource = self.connection_resources[name]
            
            # Récupérer l'état de la connexion
            connection_state = kiwi.get_status()
            
            # Ajouter les informations de priorité
            status[name] = {
                **connection_state,
                "priority": resource.priority.name,
                "priority_value": resource.priority.value,
                "last_access": resource.last_access,
                "active": name in self.active_connections
            }
        
        return status
    
    def set_priority(self, name: str, priority: SDRClientPriority) -> bool:
        """
        Modifie la priorité d'un récepteur.
        
        Args:
            name: Nom du récepteur
            priority: Nouvelle priorité
            
        Returns:
            True si la modification a réussi, False sinon
        """
        if name not in self.connections:
            logger.error(f"Le récepteur {name} n'existe pas")
            return False
        
        logger.info(f"Modification de la priorité de {name}: {self.connection_resources[name].priority.name} -> {priority.name}")
        
        # Mettre à jour la priorité
        self.connection_resources[name].priority = priority
        
        # Mettre à jour la file de priorité
        asyncio.create_task(self._prioritize_connections())
        
        return True
    
    async def _prioritize_connections(self):
        """
        Met à jour la file de priorité des connexions.
        """
        # Vider la file actuelle
        self.connection_queue = []
        
        # Ajouter toutes les connexions non actives
        for name, resource in self.connection_resources.items():
            if name not in self.active_connections:
                heapq.heappush(self.connection_queue, (resource, name))
    
    def _should_prioritize(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Détermine si une connexion doit être prioritaire sur une connexion active.
        
        Args:
            name: Nom du récepteur à vérifier
            
        Returns:
            Tuple (doit_connecter, connexion_à_déconnecter)
        """
        if name not in self.connection_resources:
            return False, None
        
        # Obtenir la ressource du récepteur demandé
        resource = self.connection_resources[name]
        
        # Trouver la connexion active de priorité la plus basse
        lowest_priority_active = None
        lowest_priority_value = -1
        
        for active_name in self.active_connections:
            active_resource = self.connection_resources[active_name]
            
            # Si c'est la première connexion active ou si elle a une priorité plus basse
            if (lowest_priority_active is None or 
                active_resource.priority.value > lowest_priority_value):
                lowest_priority_active = active_name
                lowest_priority_value = active_resource.priority.value
        
        # Si la connexion demandée a une priorité plus élevée que la plus basse connexion active
        if lowest_priority_active and resource.priority.value < lowest_priority_value:
            return True, lowest_priority_active
        
        return False, None
    
    async def _connection_management_loop(self):
        """
        Boucle de gestion des connexions basée sur les priorités.
        """
        try:
            while self.is_running:
                # Vérifier s'il y a de la place pour de nouvelles connexions
                while (len(self.active_connections) < self.max_connections and 
                       self.connection_queue):
                    # Extraire la connexion de plus haute priorité
                    resource, name = heapq.heappop(self.connection_queue)
                    
                    # Vérifier si elle n'est pas déjà active
                    if name not in self.active_connections:
                        logger.info(f"Connexion automatique au récepteur prioritaire {name}")
                        await self.connect_receiver(name)
                
                # Pause avant la prochaine vérification
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Boucle de gestion des connexions arrêtée")
        except Exception as e:
            logger.error(f"Erreur dans la boucle de gestion des connexions: {e}") 