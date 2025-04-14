"""
Tests pour le module audio_stream.
"""

import asyncio
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from src.sdr_client.audio_stream import (
    AudioBuffer,
    AudioProcessor,
    AudioStream,
    AudioStreamManager,
    AudioStreamError
)
from src.sdr_client.kiwi_connection import KiwiSDRMode, KiwiConnection, KiwiConnectionState


class TestAudioBuffer:
    """Tests pour la classe AudioBuffer."""
    
    def test_init(self):
        """Teste l'initialisation du buffer."""
        buffer = AudioBuffer(buffer_size=1000)
        assert buffer.buffer_size == 1000
        assert len(buffer.buffer) == 0
        assert buffer.overflow_count == 0
        assert buffer.underflow_count == 0
    
    def test_add_samples(self):
        """Teste l'ajout d'échantillons au buffer."""
        buffer = AudioBuffer(buffer_size=10)
        samples = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        
        buffer.add_samples(samples)
        
        assert len(buffer.buffer) == 5
        assert list(buffer.buffer) == [1.0, 2.0, 3.0, 4.0, 5.0]
    
    def test_add_samples_overflow(self):
        """Teste l'ajout d'échantillons au-delà de la capacité du buffer."""
        buffer = AudioBuffer(buffer_size=5)
        samples1 = np.array([1.0, 2.0, 3.0])
        samples2 = np.array([4.0, 5.0, 6.0])
        
        buffer.add_samples(samples1)
        buffer.add_samples(samples2)
        
        # Buffer circulaire: les plus anciens échantillons sont supprimés
        assert len(buffer.buffer) == 5
        assert list(buffer.buffer) == [2.0, 3.0, 4.0, 5.0, 6.0]
        assert buffer.overflow_count == 1
    
    def test_get_samples(self):
        """Teste la récupération d'échantillons du buffer."""
        buffer = AudioBuffer(buffer_size=10)
        samples = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        
        buffer.add_samples(samples)
        result = buffer.get_samples(3)
        
        assert len(result) == 3
        assert list(result) == [1.0, 2.0, 3.0]
        assert len(buffer.buffer) == 2
        assert list(buffer.buffer) == [4.0, 5.0]
    
    def test_get_samples_underflow(self):
        """Teste la récupération d'échantillons au-delà de la capacité du buffer."""
        buffer = AudioBuffer(buffer_size=10)
        samples = np.array([1.0, 2.0, 3.0])
        
        buffer.add_samples(samples)
        result = buffer.get_samples(5)
        
        # En cas d'underflow, renvoie des zéros
        assert len(result) == 5
        assert list(result) == [0.0, 0.0, 0.0, 0.0, 0.0]
        assert buffer.underflow_count == 1
    
    def test_clear(self):
        """Teste le vidage du buffer."""
        buffer = AudioBuffer(buffer_size=10)
        samples = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        
        buffer.add_samples(samples)
        buffer.clear()
        
        assert len(buffer.buffer) == 0
        assert buffer.overflow_count == 0
        assert buffer.underflow_count == 0


class TestAudioProcessor:
    """Tests pour la classe AudioProcessor."""
    
    def test_init(self):
        """Teste l'initialisation du processeur audio."""
        processor = AudioProcessor(sample_rate=16000)
        assert processor.sample_rate == 16000
        assert processor.channel_count == 2
    
    def test_process_sound_data_mono(self):
        """Teste le traitement des données audio en mode mono."""
        processor = AudioProcessor()
        
        # Créer des données audio de test (16 bits signés)
        data = np.array([100, 200, 300, 400], dtype=np.int16).tobytes()
        
        # Traiter les données
        result = processor.process_sound_data(data, KiwiSDRMode.AM)
        
        # Vérifier le résultat
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 4
        assert result[0] == 100 / 32768.0
        assert result[1] == 200 / 32768.0
        assert result[2] == 300 / 32768.0
        assert result[3] == 400 / 32768.0
    
    def test_process_sound_data_iq(self):
        """Teste le traitement des données audio en mode I/Q."""
        processor = AudioProcessor()
        
        # Créer des données I/Q de test (16 bits signés)
        data = np.array([100, 200, 300, 400], dtype=np.int16).tobytes()
        
        # Traiter les données
        result = processor.process_sound_data(data, KiwiSDRMode.IQ)
        
        # Vérifier le résultat
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.complex64  # Résultat complexe
        assert len(result) == 2
        assert np.isclose(result[0], complex(100 / 32768.0, 200 / 32768.0))
        assert np.isclose(result[1], complex(300 / 32768.0, 400 / 32768.0))
    
    def test_process_waterfall_data(self):
        """Teste le traitement des données waterfall."""
        processor = AudioProcessor()
        
        # Créer des données waterfall de test (8 bits non signés)
        data = np.array([10, 20, 30, 40], dtype=np.uint8).tobytes()
        
        # Traiter les données
        result = processor.process_waterfall_data(data)
        
        # Vérifier le résultat
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.uint8
        assert len(result) == 4
        assert result[0] == 10
        assert result[1] == 20
        assert result[2] == 30
        assert result[3] == 40


@pytest.mark.asyncio
class TestAudioStream:
    """Tests pour la classe AudioStream."""
    
    async def test_init(self):
        """Teste l'initialisation du flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le flux audio
        stream = AudioStream(kiwi, buffer_size=1000)
        
        # Vérifier l'initialisation
        assert stream.kiwi == kiwi
        assert isinstance(stream.processor, AudioProcessor)
        assert isinstance(stream.audio_buffer, AudioBuffer)
        assert isinstance(stream.iq_buffer, AudioBuffer)
        assert stream.is_running is False
        assert stream.last_error is None
        assert stream.audio_callback is None
        assert stream.iq_callback is None
    
    async def test_start(self):
        """Teste le démarrage du flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = AsyncMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        kiwi.set_mode.return_value = True
        kiwi.start_audio_stream.return_value = True
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        
        # Démarrer le flux
        result = await stream.start(KiwiSDRMode.AM)
        
        # Vérifier le résultat
        assert result is True
        assert stream.is_running is True
        kiwi.set_mode.assert_called_once_with(KiwiSDRMode.AM)
        kiwi.start_audio_stream.assert_called_once()
    
    async def test_start_failure(self):
        """Teste l'échec du démarrage du flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = AsyncMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        kiwi.set_mode.return_value = False
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        
        # Démarrer le flux
        result = await stream.start(KiwiSDRMode.AM)
        
        # Vérifier le résultat
        assert result is False
        assert stream.is_running is False
        kiwi.set_mode.assert_called_once_with(KiwiSDRMode.AM)
        kiwi.start_audio_stream.assert_not_called()
    
    async def test_stop(self):
        """Teste l'arrêt du flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        stream.is_running = True
        
        # Arrêter le flux
        await stream.stop()
        
        # Vérifier le résultat
        assert stream.is_running is False
        assert len(stream.audio_buffer.buffer) == 0
        assert len(stream.iq_buffer.buffer) == 0
    
    def test_register_callbacks(self):
        """Teste l'enregistrement des callbacks."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        
        # Créer des callbacks de test
        def audio_callback(data):
            pass
        
        def iq_callback(data):
            pass
        
        # Enregistrer les callbacks
        stream.register_audio_callback(audio_callback)
        stream.register_iq_callback(iq_callback)
        
        # Vérifier l'enregistrement
        assert stream.audio_callback == audio_callback
        assert stream.iq_callback == iq_callback
    
    def test_get_samples(self):
        """Teste la récupération d'échantillons."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        
        # Ajouter des échantillons aux buffers
        audio_samples = np.array([1.0, 2.0, 3.0])
        iq_samples = np.array([1+1j, 2+2j, 3+3j])
        
        stream.audio_buffer.add_samples(audio_samples)
        stream.iq_buffer.add_samples(iq_samples)
        
        # Récupérer les échantillons
        audio_result = stream.get_audio_samples(2)
        iq_result = stream.get_iq_samples(2)
        
        # Vérifier le résultat
        assert len(audio_result) == 2
        assert list(audio_result) == [1.0, 2.0]
        
        assert len(iq_result) == 2
        assert list(iq_result) == [1+1j, 2+2j]
    
    def test_on_sound_data_audio(self):
        """Teste le traitement des données audio reçues."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        kiwi.current_mode = KiwiSDRMode.AM
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        stream.is_running = True
        
        # Créer un callback de test
        received_data = None
        def audio_callback(data):
            nonlocal received_data
            received_data = data
        
        stream.register_audio_callback(audio_callback)
        
        # Créer des données audio de test
        data = np.array([100, 200, 300, 400], dtype=np.int16).tobytes()
        
        # Appeler le callback
        stream._on_sound_data(data)
        
        # Vérifier le résultat
        assert received_data is not None
        assert len(received_data) == 4
        assert received_data[0] == 100 / 32768.0
        assert stream.audio_buffer.get_available_samples() == 4
    
    def test_on_sound_data_iq(self):
        """Teste le traitement des données I/Q reçues."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        kiwi.current_mode = KiwiSDRMode.IQ
        
        # Créer le flux audio
        stream = AudioStream(kiwi)
        stream.is_running = True
        
        # Créer un callback de test
        received_data = None
        def iq_callback(data):
            nonlocal received_data
            received_data = data
        
        stream.register_iq_callback(iq_callback)
        
        # Créer des données I/Q de test
        data = np.array([100, 200, 300, 400], dtype=np.int16).tobytes()
        
        # Appeler le callback
        stream._on_sound_data(data)
        
        # Vérifier le résultat
        assert received_data is not None
        assert len(received_data) == 2
        assert received_data[0] == complex(100 / 32768.0, 200 / 32768.0)
        assert stream.iq_buffer.get_available_samples() == 2
    
    def test_get_status(self):
        """Teste la récupération de l'état du flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le flux audio
        stream = AudioStream(kiwi, buffer_size=1000)
        stream.is_running = True
        stream.last_error = "Test error"
        
        # Ajouter des échantillons aux buffers
        audio_samples = np.array([1.0, 2.0, 3.0])
        iq_samples = np.array([1+1j, 2+2j, 3+3j])
        
        stream.audio_buffer.add_samples(audio_samples)
        stream.iq_buffer.add_samples(iq_samples)
        
        # Récupérer l'état
        status = stream.get_status()
        
        # Vérifier le résultat
        assert status["is_running"] is True
        assert status["last_error"] == "Test error"
        assert status["audio_buffer_level"] == 3
        assert status["iq_buffer_level"] == 3
        assert status["audio_buffer_size"] == 1000
        assert status["audio_overflows"] == 0
        assert status["audio_underflows"] == 0


@pytest.mark.asyncio
class TestAudioStreamManager:
    """Tests pour la classe AudioStreamManager."""
    
    async def test_init(self):
        """Teste l'initialisation du gestionnaire de flux audio."""
        manager = AudioStreamManager()
        assert manager.streams == {}
        assert manager.max_connections == 5
    
    async def test_add_stream(self):
        """Teste l'ajout d'un flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        
        # Ajouter le flux
        result = await manager.add_stream(kiwi)
        
        # Vérifier le résultat
        assert result is True
        assert "Test KiwiSDR" in manager.streams
        assert isinstance(manager.streams["Test KiwiSDR"], AudioStream)
    
    async def test_add_stream_duplicate(self):
        """Teste l'ajout d'un flux audio déjà existant."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        
        # Ajouter le flux une première fois
        await manager.add_stream(kiwi)
        
        # Tenter d'ajouter à nouveau
        result = await manager.add_stream(kiwi)
        
        # Vérifier le résultat
        assert result is False
    
    async def test_add_stream_max_connections(self):
        """Teste l'ajout d'un flux audio au-delà du nombre maximal de connexions."""
        # Créer le gestionnaire
        manager = AudioStreamManager()
        manager.max_connections = 2
        
        # Ajouter deux flux
        kiwi1 = MagicMock(spec=KiwiConnection)
        kiwi1.name = "Test KiwiSDR 1"
        
        kiwi2 = MagicMock(spec=KiwiConnection)
        kiwi2.name = "Test KiwiSDR 2"
        
        kiwi3 = MagicMock(spec=KiwiConnection)
        kiwi3.name = "Test KiwiSDR 3"
        
        await manager.add_stream(kiwi1)
        await manager.add_stream(kiwi2)
        
        # Tenter d'ajouter un troisième flux
        result = await manager.add_stream(kiwi3)
        
        # Vérifier le résultat
        assert result is False
        assert len(manager.streams) == 2
    
    async def test_remove_stream(self):
        """Teste la suppression d'un flux audio."""
        # Créer un mock pour KiwiConnection
        kiwi = MagicMock(spec=KiwiConnection)
        kiwi.name = "Test KiwiSDR"
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        
        # Ajouter puis supprimer le flux
        await manager.add_stream(kiwi)
        result = await manager.remove_stream("Test KiwiSDR")
        
        # Vérifier le résultat
        assert result is True
        assert "Test KiwiSDR" not in manager.streams
    
    async def test_remove_stream_nonexistent(self):
        """Teste la suppression d'un flux audio inexistant."""
        # Créer le gestionnaire
        manager = AudioStreamManager()
        
        # Tenter de supprimer un flux inexistant
        result = await manager.remove_stream("Nonexistent")
        
        # Vérifier le résultat
        assert result is False
    
    async def test_start_all(self):
        """Teste le démarrage de tous les flux audio."""
        # Créer des mocks pour les flux audio
        stream1 = AsyncMock(spec=AudioStream)
        stream1.start.return_value = True
        
        stream2 = AsyncMock(spec=AudioStream)
        stream2.start.return_value = False
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        manager.streams = {"Stream1": stream1, "Stream2": stream2}
        
        # Démarrer tous les flux
        results = await manager.start_all(KiwiSDRMode.AM)
        
        # Vérifier le résultat
        assert results == {"Stream1": True, "Stream2": False}
        stream1.start.assert_called_once_with(KiwiSDRMode.AM)
        stream2.start.assert_called_once_with(KiwiSDRMode.AM)
    
    async def test_stop_all(self):
        """Teste l'arrêt de tous les flux audio."""
        # Créer des mocks pour les flux audio
        stream1 = AsyncMock(spec=AudioStream)
        stream2 = AsyncMock(spec=AudioStream)
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        manager.streams = {"Stream1": stream1, "Stream2": stream2}
        
        # Arrêter tous les flux
        await manager.stop_all()
        
        # Vérifier le résultat
        stream1.stop.assert_called_once()
        stream2.stop.assert_called_once()
    
    def test_get_stream(self):
        """Teste la récupération d'un flux audio."""
        # Créer un mock pour le flux audio
        stream = MagicMock(spec=AudioStream)
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        manager.streams = {"Stream1": stream}
        
        # Récupérer le flux
        result = manager.get_stream("Stream1")
        
        # Vérifier le résultat
        assert result == stream
    
    def test_get_stream_nonexistent(self):
        """Teste la récupération d'un flux audio inexistant."""
        # Créer le gestionnaire
        manager = AudioStreamManager()
        
        # Récupérer un flux inexistant
        result = manager.get_stream("Nonexistent")
        
        # Vérifier le résultat
        assert result is None
    
    def test_get_all_streams(self):
        """Teste la récupération de tous les flux audio."""
        # Créer des mocks pour les flux audio
        stream1 = MagicMock(spec=AudioStream)
        stream2 = MagicMock(spec=AudioStream)
        
        # Créer le gestionnaire
        manager = AudioStreamManager()
        streams = {"Stream1": stream1, "Stream2": stream2}
        manager.streams = streams
        
        # Récupérer tous les flux
        result = manager.get_all_streams()
        
        # Vérifier le résultat
        assert result == streams
        assert result is not streams  # Copie, pas référence 