"""
Tests pour le module kiwi_connection.
"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch
import pytest

from src.sdr_client.kiwi_connection import (
    KiwiConnection,
    KiwiSDRMode,
    KiwiMessageType,
    KiwiConnectionState,
    KiwiConnectionError
)


class MockWebSocketApp:
    """Mock pour WebSocketApp."""
    
    def __init__(self, url, on_open=None, on_message=None, on_error=None, on_close=None):
        self.url = url
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.connected = False
        self.messages = []
    
    def run_forever(self):
        """Simule le démarrage de la connexion."""
        self.connected = True
        if self.on_open:
            self.on_open(self)
    
    def send(self, message):
        """Simule l'envoi d'un message."""
        self.messages.append(message)
        
        # Simuler des réponses pour certains messages
        if message.startswith("SET auth"):
            # Simuler une réponse d'authentification réussie
            auth_response = '{"auth": "ok"}'
            if self.on_message:
                self.on_message(self, f"MSG {auth_response}")
        
        elif message.startswith("SET freq"):
            # Simuler une réponse de changement de fréquence
            freq_response = '{"freq": true}'
            if self.on_message:
                self.on_message(self, f"MSG {freq_response}")
        
        elif message.startswith("SET mod"):
            # Simuler une réponse de changement de mode
            mode_response = '{"mod": true}'
            if self.on_message:
                self.on_message(self, f"MSG {mode_response}")
        
        elif message == "SET SND":
            # Simuler des données audio
            if self.on_message:
                self.on_message(self, "SND TEST_AUDIO_DATA")
        
        elif message == "SET waterfall=1":
            # Simuler des données waterfall
            if self.on_message:
                self.on_message(self, "W TEST_WATERFALL_DATA")
    
    def close(self):
        """Simule la fermeture de la connexion."""
        self.connected = False
        if self.on_close:
            self.on_close(self, 1000, "Connection closed")


@pytest.fixture
def mock_websocket():
    """Fixture pour mocker le WebSocketApp."""
    with patch('src.sdr_client.kiwi_connection.WebSocketApp', new=MockWebSocketApp):
        yield


@pytest.mark.asyncio
class TestKiwiConnection:
    """Tests pour la classe KiwiConnection."""
    
    async def test_connect(self, mock_websocket):
        """Teste la connexion au récepteur KiwiSDR."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection(
            url="wss://test.kiwisdr.com/kiwi",
            name="Test KiwiSDR",
            location={"latitude": 10.0, "longitude": 20.0}
        )
        
        # Connecter au récepteur
        result = await kiwi.connect()
        
        # Vérifier que la connexion a réussi
        assert result is True
        assert kiwi.state == KiwiConnectionState.CONNECTED
        assert kiwi.ws is not None
        assert kiwi.ws.connected is True
    
    async def test_disconnect(self, mock_websocket):
        """Teste la déconnexion du récepteur KiwiSDR."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter puis déconnecter
        await kiwi.connect()
        await kiwi.disconnect()
        
        # Vérifier que la déconnexion a réussi
        assert kiwi.state == KiwiConnectionState.DISCONNECTED
        assert kiwi.ws.connected is False
    
    async def test_authenticate(self, mock_websocket):
        """Teste l'authentification auprès du récepteur KiwiSDR."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter
        await kiwi.connect()
        
        # Authentifier
        result = await kiwi.authenticate()
        
        # Vérifier que l'authentification a réussi
        assert result is True
        assert kiwi.is_authenticated is True
        assert kiwi.state == KiwiConnectionState.READY
        
        # Vérifier que le message d'authentification a été envoyé
        assert any("SET auth" in msg for msg in kiwi.ws.messages)
    
    async def test_set_frequency(self, mock_websocket):
        """Teste le changement de fréquence."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Définir la fréquence
        result = await kiwi.set_frequency(7100000)  # 7.1 MHz
        
        # Vérifier que la configuration a réussi
        assert result is True
        assert kiwi.current_freq == 7100000
        
        # Vérifier que le message de fréquence a été envoyé
        assert any("SET freq=7100000" in msg for msg in kiwi.ws.messages)
    
    async def test_set_mode(self, mock_websocket):
        """Teste le changement de mode."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Définir le mode
        result = await kiwi.set_mode(KiwiSDRMode.AM, 6000)  # AM, 6 kHz
        
        # Vérifier que la configuration a réussi
        assert result is True
        assert kiwi.current_mode == KiwiSDRMode.AM
        assert kiwi.current_bandwidth == 6000
        
        # Vérifier que les messages de mode et de bande passante ont été envoyés
        assert any("SET mod=am" in msg for msg in kiwi.ws.messages)
        assert any("bandwidth=6000" in msg for msg in kiwi.ws.messages)
    
    async def test_start_audio_stream(self, mock_websocket):
        """Teste le démarrage du flux audio."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Callback pour les données audio
        audio_data = None
        def audio_callback(data):
            nonlocal audio_data
            audio_data = data
        
        # Démarrer le flux audio
        result = await kiwi.start_audio_stream(audio_callback)
        
        # Envoyer manuellement un message audio pour déclencher le callback
        kiwi.ws.on_message(kiwi.ws, "SND TEST_AUDIO_DATA")
        
        # Vérifier que le flux a démarré et que le callback a été appelé
        assert result is True
        assert kiwi.sound_callback is not None
        assert audio_data is not None
        assert b"TEST_AUDIO_DATA" in audio_data
    
    async def test_start_waterfall_stream(self, mock_websocket):
        """Teste le démarrage du flux waterfall."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Callback pour les données waterfall
        waterfall_data = None
        def waterfall_callback(data):
            nonlocal waterfall_data
            waterfall_data = data
        
        # Démarrer le flux waterfall
        result = await kiwi.start_waterfall_stream(waterfall_callback)
        
        # Envoyer manuellement un message waterfall pour déclencher le callback
        kiwi.ws.on_message(kiwi.ws, "W TEST_WATERFALL_DATA")
        
        # Vérifier que le flux a démarré et que le callback a été appelé
        assert result is True
        assert kiwi.waterfall_callback is not None
        assert waterfall_data is not None
        assert b"TEST_WATERFALL_DATA" in waterfall_data
    
    async def test_get_status(self, mock_websocket):
        """Teste la récupération de l'état de la connexion."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection(
            url="wss://test.kiwisdr.com/kiwi",
            name="Test KiwiSDR",
            location={"latitude": 10.0, "longitude": 20.0}
        )
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Configurer la fréquence et le mode
        await kiwi.set_frequency(7100000)
        await kiwi.set_mode(KiwiSDRMode.AM, 6000)
        
        # Récupérer l'état
        status = kiwi.get_status()
        
        # Vérifier les informations d'état
        assert status["name"] == "Test KiwiSDR"
        assert status["url"] == "wss://test.kiwisdr.com/kiwi"
        assert status["location"] == {"latitude": 10.0, "longitude": 20.0}
        assert status["state"] == "ready"
        assert status["current_freq"] == 7100000
        assert status["current_mode"] == "am"
        assert status["current_bandwidth"] == 6000
    
    async def test_is_healthy(self, mock_websocket):
        """Teste la vérification de l'état de santé de la connexion."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Vérifier l'état de santé
        assert kiwi.is_healthy() is True
        
        # Modifier la dernière activité pour simuler une connexion inactive
        kiwi.last_activity = time.time() - 10  # 10 secondes dans le passé
        
        # Vérifier à nouveau l'état de santé
        assert kiwi.is_healthy() is False
    
    async def test_error_handling(self, mock_websocket):
        """Teste la gestion des erreurs."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Connecter
        await kiwi.connect()
        
        # Simuler une erreur
        kiwi.ws.on_error(kiwi.ws, Exception("Test error"))
        
        # Vérifier que l'erreur a été enregistrée
        assert kiwi.state == KiwiConnectionState.ERROR
        assert kiwi.last_error == "Test error"
    
    async def test_reconnect(self, mock_websocket):
        """Teste la reconnexion automatique."""
        # Créer une connexion KiwiSDR
        kiwi = KiwiConnection("wss://test.kiwisdr.com/kiwi")
        
        # Mémoriser la valeur initiale de connection_drops
        initial_drops = kiwi.connection_drops
        
        # Connecter et authentifier
        await kiwi.connect()
        await kiwi.authenticate()
        
        # Configurer la fréquence et le mode
        await kiwi.set_frequency(7100000)
        await kiwi.set_mode(KiwiSDRMode.AM, 6000)
        
        # Simuler une déconnexion inattendue
        kiwi.ws.on_close(kiwi.ws, 1006, "Connection lost")
        
        # Tenter une reconnexion manuelle
        result = await kiwi.reconnect()
        
        # Vérifier que la reconnexion a réussi
        assert result is True
        assert kiwi.state == KiwiConnectionState.CONNECTED
        # Vérifier que le compteur a été incrémenté
        assert kiwi.connection_drops > initial_drops
        
        # Vérifier que les paramètres ont été restaurés
        await kiwi.authenticate()
        assert kiwi.current_freq == 7100000
        assert kiwi.current_mode == KiwiSDRMode.AM
        assert kiwi.current_bandwidth == 6000 