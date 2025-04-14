"""
Tests pour le module sdr_client.py.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.sdr_client.sdr_client import (
    SDRClient,
    SDRClientPriority,
    SDRResource
)
from src.sdr_client.kiwi_connection import KiwiConnection, KiwiSDRMode


class TestSDRResource:
    """Tests pour la classe SDRResource."""
    
    def test_init(self):
        """Teste l'initialisation d'une ressource SDR."""
        resource = SDRResource("test", SDRClientPriority.HIGH)
        
        assert resource.name == "test"
        assert resource.priority == SDRClientPriority.HIGH
        assert resource.last_access > 0
    
    def test_lt_comparison(self):
        """Teste la comparaison de priorité entre ressources."""
        # Priorité plus élevée
        resource1 = SDRResource("high", SDRClientPriority.HIGH)
        resource2 = SDRResource("normal", SDRClientPriority.NORMAL)
        
        assert resource1 < resource2  # HIGH (1) < NORMAL (2)
        
        # Même priorité, différent timestamp
        resource3 = SDRResource("old", SDRClientPriority.NORMAL)
        resource3.last_access = 100  # plus ancien
        resource4 = SDRResource("new", SDRClientPriority.NORMAL)
        resource4.last_access = 200  # plus récent
        
        assert resource3 < resource4  # Même priorité, mais accès plus ancien
    
    def test_update_access_time(self):
        """Teste la mise à jour du temps d'accès."""
        resource = SDRResource("test")
        old_time = resource.last_access
        
        # Petite pause pour assurer un changement de timestamp
        import time
        time.sleep(0.01)
        
        resource.update_access_time()
        assert resource.last_access > old_time


@pytest.fixture
def mock_kiwi_connection():
    """Fixture pour créer un mock de KiwiConnection."""
    with patch('src.sdr_client.sdr_client.KiwiConnection') as mock:
        # Configure le mock pour qu'il retourne une instance avec les méthodes requises
        instance = mock.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.disconnect = AsyncMock(return_value=True)
        instance.authenticate = AsyncMock(return_value=True)
        instance.set_frequency = AsyncMock(return_value=True)
        instance.set_mode = AsyncMock(return_value=True)
        instance.get_status = MagicMock(return_value={"state": "connected"})
        
        yield mock


@pytest.fixture
def mock_audio_manager():
    """Fixture pour créer un mock d'AudioStreamManager."""
    with patch('src.sdr_client.sdr_client.AudioStreamManager') as mock:
        instance = mock.return_value
        instance.add_stream = AsyncMock(return_value=True)
        instance.remove_stream = AsyncMock(return_value=True)
        
        yield mock


@pytest.fixture
def mock_waterfall_manager():
    """Fixture pour créer un mock de WaterfallStreamManager."""
    with patch('src.sdr_client.sdr_client.WaterfallStreamManager') as mock:
        instance = mock.return_value
        instance.add_stream = AsyncMock(return_value=True)
        instance.remove_stream = AsyncMock(return_value=True)
        
        yield mock


@pytest.mark.asyncio
class TestSDRClient:
    """Tests pour la classe SDRClient."""
    
    async def test_init(self, mock_audio_manager, mock_waterfall_manager):
        """Teste l'initialisation du client SDR."""
        client = SDRClient(max_connections=3)
        
        assert client.max_connections == 3
        assert client.connections == {}
        assert client.connection_resources == {}
        assert client.active_connections == set()
        assert client.is_running == False
        assert client.connection_loop_task is None
    
    async def test_add_receiver(self, mock_kiwi_connection):
        """Teste l'ajout d'un récepteur."""
        client = SDRClient()
        
        # Ajouter un récepteur
        result = await client.add_receiver(
            url="wss://test.kiwisdr.com/kiwi",
            name="Test KiwiSDR",
            location={"latitude": 10.0, "longitude": 20.0},
            priority=SDRClientPriority.HIGH
        )
        
        assert result is True
        assert "Test KiwiSDR" in client.connections
        assert "Test KiwiSDR" in client.connection_resources
        assert client.connection_resources["Test KiwiSDR"].priority == SDRClientPriority.HIGH
        
        # Essayer d'ajouter un récepteur avec le même nom
        result = await client.add_receiver(
            url="wss://other.kiwisdr.com/kiwi",
            name="Test KiwiSDR"
        )
        
        assert result is False
    
    async def test_remove_receiver(self, mock_kiwi_connection):
        """Teste la suppression d'un récepteur."""
        client = SDRClient()
        
        # Ajouter puis supprimer un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR")
        result = await client.remove_receiver("Test KiwiSDR")
        
        assert result is True
        assert "Test KiwiSDR" not in client.connections
        assert "Test KiwiSDR" not in client.connection_resources
        
        # Essayer de supprimer un récepteur inexistant
        result = await client.remove_receiver("NonExistentSDR")
        
        assert result is False
    
    async def test_connect_receiver(self, mock_kiwi_connection):
        """Teste la connexion à un récepteur."""
        client = SDRClient()
        
        # Ajouter un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR")
        
        # Connecter
        result = await client.connect_receiver(
            "Test KiwiSDR", 
            frequency=7100000,
            mode=KiwiSDRMode.AM
        )
        
        assert result is True
        assert "Test KiwiSDR" in client.active_connections
        
        # Vérifier que les méthodes ont été appelées
        kiwi = client.connections["Test KiwiSDR"]
        kiwi.connect.assert_called_once()
        kiwi.authenticate.assert_called_once()
        kiwi.set_frequency.assert_called_once_with(7100000)
        kiwi.set_mode.assert_called_once()
    
    async def test_connect_receiver_errors(self, mock_kiwi_connection):
        """Teste les erreurs lors de la connexion."""
        client = SDRClient()
        
        # Essayer de connecter un récepteur inexistant
        result = await client.connect_receiver("NonExistentSDR")
        
        assert result is False
        
        # Ajouter un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR")
        
        # Simuler un échec de connexion
        kiwi = client.connections["Test KiwiSDR"]
        kiwi.connect.return_value = False
        
        result = await client.connect_receiver("Test KiwiSDR")
        
        assert result is False
        assert "Test KiwiSDR" not in client.active_connections
    
    async def test_disconnect_receiver(self, mock_kiwi_connection, mock_audio_manager, mock_waterfall_manager):
        """Teste la déconnexion d'un récepteur."""
        client = SDRClient()
        
        # Ajouter et connecter un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR")
        await client.connect_receiver("Test KiwiSDR")
        
        # Déconnecter
        result = await client.disconnect_receiver("Test KiwiSDR")
        
        assert result is True
        assert "Test KiwiSDR" not in client.active_connections
        
        # Vérifier que les méthodes ont été appelées
        kiwi = client.connections["Test KiwiSDR"]
        kiwi.disconnect.assert_called_once()
        
        # Essayer de déconnecter un récepteur inexistant
        result = await client.disconnect_receiver("NonExistentSDR")
        
        assert result is False
    
    async def test_audio_stream(self, mock_kiwi_connection, mock_audio_manager):
        """Teste le démarrage et l'arrêt du flux audio."""
        client = SDRClient()
        
        # Ajouter un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR")
        
        # Callback de test
        audio_callback = lambda data: None
        
        # Démarrer le flux audio
        result = await client.start_audio_stream("Test KiwiSDR", audio_callback)
        
        assert result is True
        assert "Test KiwiSDR" in client.active_connections  # La connexion auto doit avoir réussi
        
        # Vérifier que les méthodes ont été appelées
        client.audio_manager.add_stream.assert_called_once()
        
        # Arrêter le flux audio
        result = await client.stop_audio_stream("Test KiwiSDR")
        
        assert result is True
        client.audio_manager.remove_stream.assert_called_once_with("Test KiwiSDR")
    
    async def test_waterfall_stream(self, mock_kiwi_connection, mock_waterfall_manager):
        """Teste le démarrage et l'arrêt du flux waterfall."""
        client = SDRClient()
        
        # Ajouter un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR")
        
        # Callback de test
        waterfall_callback = lambda data: None
        
        # Démarrer le flux waterfall
        result = await client.start_waterfall_stream("Test KiwiSDR", waterfall_callback)
        
        assert result is True
        assert "Test KiwiSDR" in client.active_connections  # La connexion auto doit avoir réussi
        
        # Vérifier que les méthodes ont été appelées
        client.waterfall_manager.add_stream.assert_called_once()
        
        # Arrêter le flux waterfall
        result = await client.stop_waterfall_stream("Test KiwiSDR")
        
        assert result is True
        client.waterfall_manager.remove_stream.assert_called_once_with("Test KiwiSDR")
    
    async def test_start_stop(self, mock_kiwi_connection):
        """Teste le démarrage et l'arrêt du client SDR."""
        client = SDRClient()
        
        # Ajouter quelques récepteurs
        await client.add_receiver("wss://test1.kiwisdr.com/kiwi", "KiwiSDR1")
        await client.add_receiver("wss://test2.kiwisdr.com/kiwi", "KiwiSDR2")
        await client.connect_receiver("KiwiSDR1")
        
        # Démarrer le client
        await client.start()
        
        assert client.is_running is True
        assert client.connection_loop_task is not None
        
        # Arrêter le client
        await client.stop()
        
        assert client.is_running is False
        assert "KiwiSDR1" not in client.active_connections  # Doit être déconnecté
    
    async def test_get_connection_status(self, mock_kiwi_connection):
        """Teste la récupération du statut des connexions."""
        client = SDRClient()
        
        # Ajouter quelques récepteurs
        await client.add_receiver("wss://test1.kiwisdr.com/kiwi", "KiwiSDR1", priority=SDRClientPriority.HIGH)
        await client.add_receiver("wss://test2.kiwisdr.com/kiwi", "KiwiSDR2", priority=SDRClientPriority.LOW)
        await client.connect_receiver("KiwiSDR1")
        
        # Récupérer le statut
        status = client.get_connection_status()
        
        assert "KiwiSDR1" in status
        assert "KiwiSDR2" in status
        assert status["KiwiSDR1"]["active"] is True
        assert status["KiwiSDR2"]["active"] is False
        assert status["KiwiSDR1"]["priority"] == "HIGH"
        assert status["KiwiSDR2"]["priority"] == "LOW"
    
    async def test_set_priority(self, mock_kiwi_connection):
        """Teste la modification de priorité d'un récepteur."""
        client = SDRClient()
        
        # Ajouter un récepteur
        await client.add_receiver("wss://test.kiwisdr.com/kiwi", "Test KiwiSDR", priority=SDRClientPriority.NORMAL)
        
        # Modifier la priorité
        result = client.set_priority("Test KiwiSDR", SDRClientPriority.CRITICAL)
        
        assert result is True
        assert client.connection_resources["Test KiwiSDR"].priority == SDRClientPriority.CRITICAL
        
        # Essayer de modifier la priorité d'un récepteur inexistant
        result = client.set_priority("NonExistentSDR", SDRClientPriority.LOW)
        
        assert result is False
    
    async def test_prioritization(self, mock_kiwi_connection):
        """Teste le système de prioritisation des connexions."""
        client = SDRClient(max_connections=2)
        
        # Ajouter plusieurs récepteurs avec différentes priorités
        await client.add_receiver("wss://test1.kiwisdr.com/kiwi", "KiwiSDR1", priority=SDRClientPriority.LOW)
        await client.add_receiver("wss://test2.kiwisdr.com/kiwi", "KiwiSDR2", priority=SDRClientPriority.NORMAL)
        await client.add_receiver("wss://test3.kiwisdr.com/kiwi", "KiwiSDR3", priority=SDRClientPriority.HIGH)
        
        # Connecter les deux premiers
        await client.connect_receiver("KiwiSDR1")
        await client.connect_receiver("KiwiSDR2")
        
        assert "KiwiSDR1" in client.active_connections
        assert "KiwiSDR2" in client.active_connections
        assert "KiwiSDR3" not in client.active_connections
        
        # Essayer de connecter un récepteur de priorité supérieure
        await client.connect_receiver("KiwiSDR3")
        
        # La connexion de priorité la plus basse devrait être déconnectée
        assert "KiwiSDR1" not in client.active_connections
        assert "KiwiSDR2" in client.active_connections
        assert "KiwiSDR3" in client.active_connections
    
    async def test_connection_management_loop(self, mock_kiwi_connection):
        """Teste la boucle de gestion des connexions."""
        client = SDRClient(max_connections=2)
        
        # Ajouter plusieurs récepteurs avec différentes priorités
        await client.add_receiver("wss://test1.kiwisdr.com/kiwi", "KiwiSDR1", priority=SDRClientPriority.HIGH)
        await client.add_receiver("wss://test2.kiwisdr.com/kiwi", "KiwiSDR2", priority=SDRClientPriority.NORMAL)
        await client.add_receiver("wss://test3.kiwisdr.com/kiwi", "KiwiSDR3", priority=SDRClientPriority.LOW)
        
        # Initialiser manuellement la file de priorité
        await client._prioritize_connections()
        
        # Démarrer la boucle de gestion
        task = asyncio.create_task(client._connection_management_loop())
        client.is_running = True
        
        # Laisser la boucle s'exécuter un peu
        await asyncio.sleep(0.1)
        
        # Les connexions de priorité la plus élevée devraient être établies automatiquement
        assert "KiwiSDR1" in client.active_connections
        assert "KiwiSDR2" in client.active_connections
        
        # Arrêter la boucle
        client.is_running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass 