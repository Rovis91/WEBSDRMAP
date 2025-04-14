"""
Tests unitaires pour le module waterfall_stream.py.

Ce module teste les classes:
- WaterfallBuffer
- WaterfallProcessor
- WaterfallStream
- WaterfallStreamManager
"""

import asyncio
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.sdr_client.waterfall_stream import (
    WaterfallBuffer,
    WaterfallProcessor,
    WaterfallStream,
    WaterfallStreamManager,
    WaterfallStreamError
)


class TestWaterfallBuffer:
    """Tests pour la classe WaterfallBuffer."""

    def test_init(self):
        """Teste l'initialisation du buffer."""
        buffer = WaterfallBuffer(max_lines=500, line_width=800)
        
        assert buffer.max_lines == 500
        assert buffer.line_width == 800
        assert buffer.lines_count == 0
        assert buffer.dropped_lines == 0
        assert len(buffer.buffer) == 0
    
    def test_add_line(self):
        """Teste l'ajout de lignes au buffer."""
        buffer = WaterfallBuffer(max_lines=3, line_width=4)
        
        # Créer des lignes de test
        line1 = np.array([10, 20, 30, 40], dtype=np.uint8)
        line2 = np.array([50, 60, 70, 80], dtype=np.uint8)
        line3 = np.array([90, 100, 110, 120], dtype=np.uint8)
        line4 = np.array([130, 140, 150, 160], dtype=np.uint8)
        
        # Ajouter les lignes
        assert buffer.add_line(line1) is True
        assert buffer.add_line(line2) is True
        assert buffer.add_line(line3) is True
        
        # Vérifier le comptage
        assert buffer.lines_count == 3
        assert buffer.dropped_lines == 0
        assert len(buffer.buffer) == 3
        
        # Ajouter une ligne supplémentaire (dépassement)
        assert buffer.add_line(line4) is True
        
        # Vérifier que la première ligne a été supprimée
        assert buffer.lines_count == 4
        assert buffer.dropped_lines == 1
        assert len(buffer.buffer) == 3
        
        # Vérifier que les données sont correctes
        data = buffer.get_waterfall_data()
        assert np.array_equal(data[0], line2)
        assert np.array_equal(data[1], line3)
        assert np.array_equal(data[2], line4)
    
    def test_add_line_wrong_size(self):
        """Teste l'ajout d'une ligne de taille incorrecte."""
        buffer = WaterfallBuffer(max_lines=3, line_width=4)
        
        # Ligne avec une taille incorrecte
        wrong_line = np.array([10, 20, 30], dtype=np.uint8)  # Taille 3 au lieu de 4
        
        # L'ajout devrait échouer
        assert buffer.add_line(wrong_line) is False
        
        # Vérifier que rien n'a été ajouté
        assert buffer.lines_count == 0
        assert len(buffer.buffer) == 0
    
    def test_get_waterfall_data(self):
        """Teste la récupération des données waterfall."""
        buffer = WaterfallBuffer(max_lines=3, line_width=4)
        
        # Buffer vide
        data = buffer.get_waterfall_data()
        assert data.shape == (0, 4)
        
        # Ajouter des lignes
        line1 = np.array([10, 20, 30, 40], dtype=np.uint8)
        line2 = np.array([50, 60, 70, 80], dtype=np.uint8)
        
        buffer.add_line(line1)
        buffer.add_line(line2)
        
        # Vérifier les données
        data = buffer.get_waterfall_data()
        assert data.shape == (2, 4)
        assert np.array_equal(data[0], line1)
        assert np.array_equal(data[1], line2)
    
    def test_get_latest_line(self):
        """Teste la récupération de la dernière ligne."""
        buffer = WaterfallBuffer(max_lines=3, line_width=4)
        
        # Buffer vide
        line = buffer.get_latest_line()
        assert np.array_equal(line, np.zeros(4, dtype=np.uint8))
        
        # Ajouter des lignes
        line1 = np.array([10, 20, 30, 40], dtype=np.uint8)
        line2 = np.array([50, 60, 70, 80], dtype=np.uint8)
        
        buffer.add_line(line1)
        buffer.add_line(line2)
        
        # Vérifier la dernière ligne
        line = buffer.get_latest_line()
        assert np.array_equal(line, line2)
    
    def test_clear(self):
        """Teste le vidage du buffer."""
        buffer = WaterfallBuffer(max_lines=3, line_width=4)
        
        # Ajouter des lignes
        line1 = np.array([10, 20, 30, 40], dtype=np.uint8)
        line2 = np.array([50, 60, 70, 80], dtype=np.uint8)
        
        buffer.add_line(line1)
        buffer.add_line(line2)
        
        # Vider le buffer
        buffer.clear()
        
        # Vérifier que le buffer est vide
        assert buffer.lines_count == 0
        assert buffer.dropped_lines == 0
        assert len(buffer.buffer) == 0
        
        # Vérifier les données
        data = buffer.get_waterfall_data()
        assert data.shape == (0, 4)
    
    def test_get_info(self):
        """Teste la récupération des informations du buffer."""
        buffer = WaterfallBuffer(max_lines=100, line_width=200)
        
        # Ajouter des lignes
        line = np.zeros(200, dtype=np.uint8)
        for _ in range(10):
            buffer.add_line(line)
        
        # Vérifier les informations
        info = buffer.get_info()
        assert info["max_lines"] == 100
        assert info["line_width"] == 200
        assert info["current_lines"] == 10
        assert info["total_lines_received"] == 10
        assert info["dropped_lines"] == 0


class TestWaterfallProcessor:
    """Tests pour la classe WaterfallProcessor."""

    def test_init(self):
        """Teste l'initialisation du processeur."""
        processor = WaterfallProcessor(min_db=-110, max_db=-20)
        
        assert processor.min_db == -110
        assert processor.max_db == -20
        assert processor.db_range == 90
    
    def test_process_waterfall_data(self):
        """Teste le traitement des données waterfall brutes."""
        processor = WaterfallProcessor()
        
        # Créer des données de test
        raw_data = bytes([10, 20, 30, 40, 50])
        
        # Traiter les données
        result = processor.process_waterfall_data(raw_data)
        
        # Vérifier le résultat
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.uint8
        assert np.array_equal(result, np.array([10, 20, 30, 40, 50], dtype=np.uint8))
    
    def test_process_waterfall_data_error(self):
        """Teste le traitement des données waterfall avec erreur."""
        processor = WaterfallProcessor()
        
        # Utiliser None devrait lever une exception mais être gérée
        result = processor.process_waterfall_data(None)
        
        # Vérifier que le résultat est un tableau vide
        assert isinstance(result, np.ndarray)
        assert len(result) == 0
    
    def test_db_to_pixel(self):
        """Teste la conversion de dB en valeurs de pixels."""
        processor = WaterfallProcessor(min_db=-100, max_db=0)
        
        # Créer des données de test
        db_values = np.array([-100, -75, -50, -25, 0])
        
        # Convertir en pixels
        pixels = processor.db_to_pixel(db_values)
        
        # Vérifier le résultat
        expected = np.array([0, 63.75, 127.5, 191.25, 255], dtype=np.uint8)
        np.testing.assert_almost_equal(pixels, expected, decimal=0)
    
    def test_pixel_to_db(self):
        """Teste la conversion de valeurs de pixels en dB."""
        processor = WaterfallProcessor(min_db=-100, max_db=0)
        
        # Créer des données de test
        pixel_values = np.array([0, 64, 128, 192, 255])
        
        # Convertir en dB
        db_values = processor.pixel_to_db(pixel_values)
        
        # Vérifier le résultat
        expected = np.array([-100, -74.9, -49.8, -24.7, 0])
        np.testing.assert_almost_equal(db_values, expected, decimal=1)
    
    def test_detect_peaks(self):
        """Teste la détection des pics dans une ligne de données."""
        processor = WaterfallProcessor(min_db=-100, max_db=0)
        
        # Créer une ligne avec des pics
        # Convertir d'abord des valeurs dB en valeurs de pixels
        db_values = np.array([-90, -80, -40, -85, -95, -35, -90, -75])
        pixel_values = processor.db_to_pixel(db_values)
        
        # Détecter les pics
        peaks = processor.detect_peaks(pixel_values, threshold=0.6, min_distance=2)
        
        # Vérifier les résultats
        # Les pics devraient être autour des indices 2 et 5
        assert 2 in peaks
        assert 5 in peaks
        assert len(peaks) == 2


@pytest.fixture
def mock_kiwi():
    """Fixture pour créer un objet KiwiConnection simulé."""
    mock = MagicMock()
    mock.name = "test_kiwi"
    mock.set_waterfall_callback = MagicMock()
    mock.set_frequency = AsyncMock(return_value=True)
    mock.start_waterfall_stream = AsyncMock(return_value=True)
    mock.stop_waterfall_stream = AsyncMock(return_value=True)
    return mock


# Helper pour les méthodes asynchrones
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class TestWaterfallStream:
    """Tests pour la classe WaterfallStream."""

    def test_init(self, mock_kiwi):
        """Teste l'initialisation du flux waterfall."""
        stream = WaterfallStream(mock_kiwi, buffer_lines=400, line_width=800)
        
        assert stream.kiwi == mock_kiwi
        assert isinstance(stream.processor, WaterfallProcessor)
        assert isinstance(stream.buffer, WaterfallBuffer)
        assert stream.buffer.max_lines == 400
        assert stream.buffer.line_width == 800
        assert stream.is_running is False
        assert stream.center_frequency == 0
        assert stream.span == 0
        
        # Vérifier que le callback a été enregistré
        mock_kiwi.set_waterfall_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start(self, mock_kiwi):
        """Teste le démarrage du flux waterfall."""
        stream = WaterfallStream(mock_kiwi)
        
        # Démarrer le flux
        result = await stream.start(center_freq=7100000, span=20000)
        
        # Vérifier le résultat
        assert result is True
        assert stream.is_running is True
        assert stream.center_frequency == 7100000
        assert stream.span == 20000
        
        # Vérifier les appels
        mock_kiwi.set_frequency.assert_called_once_with(7100000)
        mock_kiwi.start_waterfall_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_failure(self, mock_kiwi):
        """Teste le démarrage du flux waterfall avec échec."""
        mock_kiwi.start_waterfall_stream = AsyncMock(return_value=False)
        stream = WaterfallStream(mock_kiwi)
        
        # Démarrer le flux
        result = await stream.start()
        
        # Vérifier le résultat
        assert result is False
        assert stream.is_running is False
        assert stream.last_error is not None
    
    @pytest.mark.asyncio
    async def test_stop(self, mock_kiwi):
        """Teste l'arrêt du flux waterfall."""
        stream = WaterfallStream(mock_kiwi)
        
        # Démarrer puis arrêter le flux
        await stream.start()
        result = await stream.stop()
        
        # Vérifier le résultat
        assert result is True
        assert stream.is_running is False
        
        # Vérifier les appels
        mock_kiwi.stop_waterfall_stream.assert_called_once()
    
    def test_register_update_callback(self, mock_kiwi):
        """Teste l'enregistrement d'un callback pour les mises à jour."""
        stream = WaterfallStream(mock_kiwi)
        
        # Enregistrer un callback
        callback = MagicMock()
        stream.register_update_callback(callback)
        
        # Vérifier l'enregistrement
        assert stream.update_callback == callback
    
    def test_get_waterfall_image(self, mock_kiwi):
        """Teste la récupération de l'image waterfall."""
        stream = WaterfallStream(mock_kiwi)
        
        # Simuler des données dans le buffer
        mock_data = np.zeros((10, 1024), dtype=np.uint8)
        stream.buffer.get_waterfall_data = MagicMock(return_value=mock_data)
        
        # Récupérer l'image
        image = stream.get_waterfall_image()
        
        # Vérifier le résultat
        assert np.array_equal(image, mock_data)
        stream.buffer.get_waterfall_data.assert_called_once()
    
    def test_get_latest_spectrum(self, mock_kiwi):
        """Teste la récupération du dernier spectre."""
        stream = WaterfallStream(mock_kiwi)
        
        # Simuler un spectre dans le buffer
        mock_spectrum = np.zeros(1024, dtype=np.uint8)
        stream.buffer.get_latest_line = MagicMock(return_value=mock_spectrum)
        
        # Récupérer le spectre
        spectrum = stream.get_latest_spectrum()
        
        # Vérifier le résultat
        assert np.array_equal(spectrum, mock_spectrum)
        stream.buffer.get_latest_line.assert_called_once()
    
    def test_get_status(self, mock_kiwi):
        """Teste la récupération de l'état du flux."""
        stream = WaterfallStream(mock_kiwi)
        stream.is_running = True
        stream.center_frequency = 7100000
        stream.span = 20000
        stream.last_error = "Test error"
        
        # Simuler des infos de buffer
        mock_buffer_info = {"test": "info"}
        stream.buffer.get_info = MagicMock(return_value=mock_buffer_info)
        
        # Récupérer l'état
        status = stream.get_status()
        
        # Vérifier les résultats
        assert status["is_running"] is True
        assert status["center_frequency"] == 7100000
        assert status["span"] == 20000
        assert status["last_error"] == "Test error"
        assert status["buffer"] == mock_buffer_info
    
    def test_on_waterfall_data(self, mock_kiwi):
        """Teste le callback de données waterfall."""
        stream = WaterfallStream(mock_kiwi)
        stream.is_running = True
        
        # Simuler des données
        mock_data = bytes([10, 20, 30, 40, 50])
        processed_data = np.array([10, 20, 30, 40, 50], dtype=np.uint8)
        
        # Mocker le traitement
        stream.processor.process_waterfall_data = MagicMock(return_value=processed_data)
        stream.buffer.add_line = MagicMock(return_value=True)
        
        # Simuler un callback
        callback = MagicMock()
        stream.register_update_callback(callback)
        
        # Appeler le callback
        callback_method = mock_kiwi.set_waterfall_callback.call_args[0][0]
        callback_method(mock_data)
        
        # Vérifier le traitement
        stream.processor.process_waterfall_data.assert_called_once_with(mock_data)
        stream.buffer.add_line.assert_called_once_with(processed_data)
        callback.assert_called_once_with(processed_data)
    
    def test_on_waterfall_data_not_running(self, mock_kiwi):
        """Teste le callback de données waterfall quand le flux n'est pas actif."""
        stream = WaterfallStream(mock_kiwi)
        stream.is_running = False
        
        # Simuler le traitement
        stream.processor.process_waterfall_data = MagicMock()
        stream.buffer.add_line = MagicMock()
        
        # Appeler le callback
        callback_method = mock_kiwi.set_waterfall_callback.call_args[0][0]
        callback_method(bytes([10, 20, 30]))
        
        # Vérifier qu'aucun traitement n'a lieu
        stream.processor.process_waterfall_data.assert_not_called()
        stream.buffer.add_line.assert_not_called()
    
    def test_on_waterfall_data_error(self, mock_kiwi):
        """Teste le callback de données waterfall avec une erreur."""
        stream = WaterfallStream(mock_kiwi)
        stream.is_running = True
        
        # Simuler une erreur dans le traitement
        stream.processor.process_waterfall_data = MagicMock(side_effect=Exception("Test error"))
        
        # Appeler le callback
        callback_method = mock_kiwi.set_waterfall_callback.call_args[0][0]
        callback_method(bytes([10, 20, 30]))
        
        # Vérifier que l'erreur a été capturée
        assert stream.last_error == "Test error"


class TestWaterfallStreamManager:
    """Tests pour la classe WaterfallStreamManager."""

    def test_init(self):
        """Teste l'initialisation du gestionnaire de flux."""
        manager = WaterfallStreamManager(max_connections=10)
        
        assert manager.max_connections == 10
        assert len(manager.streams) == 0
    
    @pytest.mark.asyncio
    async def test_add_stream(self, mock_kiwi):
        """Teste l'ajout d'un flux waterfall."""
        manager = WaterfallStreamManager()
        
        # Ajouter un flux
        result = await manager.add_stream(mock_kiwi, buffer_lines=300, line_width=500)
        
        # Vérifier le résultat
        assert result is True
        assert len(manager.streams) == 1
        assert mock_kiwi.name in manager.streams
        
        # Vérifier le flux créé
        stream = manager.streams[mock_kiwi.name]
        assert isinstance(stream, WaterfallStream)
        assert stream.buffer.max_lines == 300
        assert stream.buffer.line_width == 500
    
    @pytest.mark.asyncio
    async def test_add_stream_duplicate(self, mock_kiwi):
        """Teste l'ajout d'un flux déjà existant."""
        manager = WaterfallStreamManager()
        
        # Ajouter un flux
        await manager.add_stream(mock_kiwi)
        
        # Tenter d'ajouter à nouveau
        result = await manager.add_stream(mock_kiwi)
        
        # Vérifier que l'ajout a échoué
        assert result is False
        assert len(manager.streams) == 1
    
    @pytest.mark.asyncio
    async def test_add_stream_max_connections(self, mock_kiwi):
        """Teste l'ajout d'un flux lorsque le maximum est atteint."""
        manager = WaterfallStreamManager(max_connections=1)
        
        # Ajouter un premier flux
        await manager.add_stream(mock_kiwi)
        
        # Créer un second mock
        mock_kiwi2 = MagicMock()
        mock_kiwi2.name = "test_kiwi2"
        
        # Tenter d'ajouter un second flux
        result = await manager.add_stream(mock_kiwi2)
        
        # Vérifier que l'ajout a échoué
        assert result is False
        assert len(manager.streams) == 1
        assert mock_kiwi2.name not in manager.streams
    
    @pytest.mark.asyncio
    async def test_remove_stream(self, mock_kiwi):
        """Teste la suppression d'un flux waterfall."""
        manager = WaterfallStreamManager()
        
        # Ajouter puis supprimer un flux
        await manager.add_stream(mock_kiwi)
        result = await manager.remove_stream(mock_kiwi.name)
        
        # Vérifier le résultat
        assert result is True
        assert len(manager.streams) == 0
    
    @pytest.mark.asyncio
    async def test_remove_stream_running(self, mock_kiwi):
        """Teste la suppression d'un flux waterfall en cours d'exécution."""
        manager = WaterfallStreamManager()
        
        # Ajouter un flux et le démarrer
        await manager.add_stream(mock_kiwi)
        stream = manager.streams[mock_kiwi.name]
        stream.is_running = True
        
        # Mock stop method
        stream.stop = AsyncMock(return_value=True)
        
        # Supprimer le flux
        result = await manager.remove_stream(mock_kiwi.name)
        
        # Vérifier le résultat
        assert result is True
        assert len(manager.streams) == 0
        
        # Vérifier que le flux a été arrêté
        assert stream.stop.called
    
    @pytest.mark.asyncio
    async def test_remove_stream_nonexistent(self):
        """Teste la suppression d'un flux waterfall inexistant."""
        manager = WaterfallStreamManager()
        
        # Tenter de supprimer un flux inexistant
        result = await manager.remove_stream("nonexistent")
        
        # Vérifier le résultat
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_all(self, mock_kiwi):
        """Teste le démarrage de tous les flux waterfall."""
        manager = WaterfallStreamManager()
        
        # Ajouter deux flux
        await manager.add_stream(mock_kiwi)
        
        mock_kiwi2 = MagicMock()
        mock_kiwi2.name = "test_kiwi2"
        mock_kiwi2.set_waterfall_callback = MagicMock()
        mock_kiwi2.set_frequency = AsyncMock(return_value=True)
        mock_kiwi2.start_waterfall_stream = AsyncMock(return_value=True)
        await manager.add_stream(mock_kiwi2)
        
        # Mock start methods for both streams
        for name, stream in manager.streams.items():
            stream.start = AsyncMock(return_value=True)
        
        # Démarrer tous les flux
        results = await manager.start_all(center_freq=7100000, span=20000)
        
        # Vérifier les résultats
        assert len(results) == 2
        assert results[mock_kiwi.name] is True
        assert results[mock_kiwi2.name] is True
        
        # Vérifier les appels pour chaque flux
        for name, stream in manager.streams.items():
            assert stream.start.called
            # Check with the right parameters (passed as positional args, not kwargs)
            stream.start.assert_called_with(7100000, 20000)
    
    @pytest.mark.asyncio
    async def test_stop_all(self, mock_kiwi):
        """Teste l'arrêt de tous les flux waterfall."""
        manager = WaterfallStreamManager()
        
        # Ajouter deux flux
        await manager.add_stream(mock_kiwi)
        
        mock_kiwi2 = MagicMock()
        mock_kiwi2.name = "test_kiwi2"
        mock_kiwi2.set_waterfall_callback = MagicMock()
        mock_kiwi2.stop_waterfall_stream = AsyncMock(return_value=True)
        await manager.add_stream(mock_kiwi2)
        
        # Mock stop methods for both streams
        for name, stream in manager.streams.items():
            stream.kiwi.stop_waterfall_stream = AsyncMock(return_value=True)
            stream.stop = AsyncMock(return_value=True)
        
        # Arrêter tous les flux
        results = await manager.stop_all()
        
        # Vérifier les résultats
        assert len(results) == 2
        assert results[mock_kiwi.name] is True
        assert results[mock_kiwi2.name] is True
        
        # Vérifier les appels pour chaque flux
        for name, stream in manager.streams.items():
            assert stream.stop.called
    
    def test_get_stream(self, mock_kiwi):
        """Teste la récupération d'un flux waterfall."""
        manager = WaterfallStreamManager()
        
        # Avant l'ajout
        assert manager.get_stream(mock_kiwi.name) is None
        
        # Après l'ajout
        manager.streams[mock_kiwi.name] = "test_stream"
        assert manager.get_stream(mock_kiwi.name) == "test_stream"
    
    def test_get_all_streams(self, mock_kiwi):
        """Teste la récupération de tous les flux waterfall."""
        manager = WaterfallStreamManager()
        
        # Ajouter un flux manuellement
        manager.streams[mock_kiwi.name] = "test_stream"
        
        # Récupérer tous les flux
        streams = manager.get_all_streams()
        
        # Vérifier le résultat
        assert len(streams) == 1
        assert streams[mock_kiwi.name] == "test_stream"
        
        # Vérifier que c'est une copie
        streams[mock_kiwi.name] = "modified"
        assert manager.streams[mock_kiwi.name] == "test_stream"
    
    def test_get_combined_waterfall(self, mock_kiwi):
        """Teste la combinaison des données waterfall de tous les flux."""
        manager = WaterfallStreamManager()
        
        # Créer deux flux simulés
        stream1 = MagicMock()
        stream1.is_running = True
        stream1.center_frequency = 7100000
        stream1.span = 20000
        stream1.get_waterfall_image.return_value = np.zeros((10, 100))
        
        stream2 = MagicMock()
        stream2.is_running = True
        stream2.center_frequency = 14200000
        stream2.span = 30000
        stream2.get_waterfall_image.return_value = np.ones((20, 200))
        
        # Ajouter les flux au gestionnaire
        manager.streams = {
            "kiwi1": stream1,
            "kiwi2": stream2
        }
        
        # Récupérer les données combinées
        result = manager.get_combined_waterfall()
        
        # Vérifier le résultat
        assert result["streams_count"] == 2
        assert set(result["active_streams"]) == {"kiwi1", "kiwi2"}
        
        assert "kiwi1" in result["images"]
        assert "kiwi2" in result["images"]
        
        assert result["images"]["kiwi1"]["frequency"] == 7100000
        assert result["images"]["kiwi1"]["span"] == 20000
        assert np.array_equal(result["images"]["kiwi1"]["data"], np.zeros((10, 100)))
        
        assert result["images"]["kiwi2"]["frequency"] == 14200000
        assert result["images"]["kiwi2"]["span"] == 30000
        assert np.array_equal(result["images"]["kiwi2"]["data"], np.ones((20, 200))) 