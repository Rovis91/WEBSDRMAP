"""
Tests unitaires pour le module principal (main.py).
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pytest

from src.main import SDRTriangulationApp
from src.signal_processing.detection import SignalDetection, SignalType
from src.signal_processing.triangulation import TriangulationResult


class TestSDRTriangulationApp(unittest.TestCase):
    """Tests pour la classe SDRTriangulationApp."""

    def setUp(self):
        """Configuration avant chaque test."""
        # Créer une configuration minimale pour les tests
        self.test_config = {
            "receivers": [
                {
                    "name": "test_receiver_1",
                    "url": "wss://test1.kiwisdr.com/",
                    "location": {"latitude": 48.8566, "longitude": 2.3522}
                },
                {
                    "name": "test_receiver_2",
                    "url": "wss://test2.kiwisdr.com/",
                    "location": {"latitude": 51.5074, "longitude": -0.1278}
                }
            ],
            "signal_processing": {
                "fft_size": 1024,
                "sample_rate": 12000,
                "initial_frequency": 7100000,
                "modulation_mode": "am"
            },
            "detection": {
                "threshold_db": -70.0,
                "min_snr_db": 10.0
            },
            "data_export": {
                "output_dir": "test_exports",
                "enable_audio_export": True
            }
        }

        # Patcher les fonctions pour éviter de charger un vrai fichier de configuration
        self.config_patcher = patch('src.main.load_config')
        self.mock_load_config = self.config_patcher.start()
        self.mock_load_config.return_value = self.test_config

        # Créer l'application avec notre configuration mockée
        self.app = SDRTriangulationApp()

    def tearDown(self):
        """Nettoyage après chaque test."""
        self.config_patcher.stop()

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Tester l'initialisation de l'application."""
        # Patcher les classes et méthodes utilisées lors de l'initialisation
        with patch('src.main.process_pool') as mock_process_pool, \
             patch('src.main.thread_pool') as mock_thread_pool, \
             patch('src.main.performance_monitor') as mock_performance_monitor, \
             patch('src.main.KiwiConnection') as mock_kiwi_connection, \
             patch('src.main.OptimizedSignalProcessor') as mock_signal_processor, \
             patch('src.main.SignalDetector') as mock_signal_detector, \
             patch('src.main.RSSIComputer') as mock_rssi_computer, \
             patch('src.main.Triangulator') as mock_triangulator, \
             patch('src.main.DataExporter') as mock_data_exporter:
            
            # Configurer les mocks
            mock_kiwi_connection.return_value = AsyncMock()
            
            # Appeler la méthode à tester
            result = await self.app.initialize()
            
            # Vérifier que l'initialisation a réussi
            self.assertTrue(result)
            
            # Vérifier que tous les composants ont été initialisés
            mock_process_pool.start.assert_called_once()
            mock_thread_pool.start.assert_called_once()
            mock_performance_monitor.reset.assert_called_once()
            mock_performance_monitor.start.assert_called_once()
            
            # Vérifier que les KiwiConnection ont été créés
            self.assertEqual(mock_kiwi_connection.call_count, 2)  # 2 récepteurs dans la config
            
            # Vérifier que les composants principaux ont été initialisés
            mock_signal_processor.assert_called_once()
            mock_signal_detector.assert_called_once()
            mock_rssi_computer.assert_called_once()
            mock_triangulator.assert_called_once()
            mock_data_exporter().configure.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_receivers(self):
        """Tester la connexion aux récepteurs."""
        # Configurer les mocks pour les connexions KiwiSDR
        mock_kiwi1 = AsyncMock()
        mock_kiwi1.connect = AsyncMock(return_value=True)
        mock_kiwi1.authenticate = AsyncMock(return_value=True)
        mock_kiwi1.set_frequency = AsyncMock(return_value=True)
        mock_kiwi1.set_mode = AsyncMock(return_value=True)
        
        mock_kiwi2 = AsyncMock()
        mock_kiwi2.connect = AsyncMock(return_value=True)
        mock_kiwi2.authenticate = AsyncMock(return_value=True)
        mock_kiwi2.set_frequency = AsyncMock(return_value=True)
        mock_kiwi2.set_mode = AsyncMock(return_value=True)
        
        # Ajouter les mocks à l'application
        self.app.kiwi_connections = {
            "test_receiver_1": mock_kiwi1,
            "test_receiver_2": mock_kiwi2
        }
        
        # Appeler la méthode à tester
        results = await self.app.connect_receivers()
        
        # Vérifier que les connexions ont réussi
        self.assertEqual(len(results), 2)
        self.assertTrue(results["test_receiver_1"])
        self.assertTrue(results["test_receiver_2"])
        
        # Vérifier que les méthodes ont été appelées
        mock_kiwi1.connect.assert_called_once()
        mock_kiwi1.authenticate.assert_called_once()
        mock_kiwi1.set_frequency.assert_called_once()
        mock_kiwi1.set_mode.assert_called_once()
        
        mock_kiwi2.connect.assert_called_once()
        mock_kiwi2.authenticate.assert_called_once()
        mock_kiwi2.set_frequency.assert_called_once()
        mock_kiwi2.set_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_waterfall_data(self):
        """Tester le traitement des données waterfall."""
        # Créer des mocks pour les composants
        mock_waterfall_manager = MagicMock()
        mock_stream1 = MagicMock()
        mock_stream2 = MagicMock()
        
        # Configurer les données de test
        test_spectrum = np.random.normal(-90, 5, 1024)
        test_frequencies = np.linspace(7.0e6, 7.2e6, 1024)
        
        # Ajouter quelques pics pour simuler des signaux
        test_spectrum[300] = -60  # Signal fort
        test_spectrum[600] = -65  # Signal moyen
        
        # Configurer les streams
        mock_stream1.get_latest_spectrum.return_value = test_spectrum
        mock_stream1.get_frequency_range.return_value = test_frequencies
        
        mock_stream2.get_latest_spectrum.return_value = test_spectrum
        mock_stream2.get_frequency_range.return_value = test_frequencies
        
        # Configurer le manager
        mock_waterfall_manager.get_all_streams.return_value = {
            "test_receiver_1": mock_stream1,
            "test_receiver_2": mock_stream2
        }
        
        # Remplacer les composants de l'application
        self.app.waterfall_manager = mock_waterfall_manager
        self.app.signal_processor = MagicMock()
        self.app.signal_processor.process_spectrum.return_value = test_spectrum
        
        self.app.signal_detector = MagicMock()
        test_signals = [
            SignalDetection(
                frequency=7.06e6,
                bandwidth=2800.0,
                power=-60.0,
                snr=30.0,
                signal_type=SignalType.AM,
                confidence=0.9,
                timestamp=1234567890.0
            ),
            SignalDetection(
                frequency=7.12e6,
                bandwidth=500.0,
                power=-65.0,
                snr=25.0,
                signal_type=SignalType.CW,
                confidence=0.8,
                timestamp=1234567890.0
            )
        ]
        self.app.signal_detector.detect_from_spectrum.return_value = test_signals
        
        self.app.rssi_computer = MagicMock()
        self.app.rssi_computer.compute_rssi.return_value = -60.0
        
        self.app.alert_manager = MagicMock()
        self.app.alert_manager.check_signals.return_value = []
        
        self.app.triangulator = MagicMock()
        self.app.triangulator.min_receivers = 2
        self.app.triangulator.triangulate.return_value = TriangulationResult(
            latitude=50.0,
            longitude=5.0,
            radius_km=10.0,
            confidence=0.8,
            signal_frequency=7.06e6,
            timestamp=1234567890.0
        )
        
        self.app.data_exporter = MagicMock()
        
        # Configurer les récepteurs pour la triangulation
        self.app.kiwi_connections = {
            "test_receiver_1": MagicMock(location={"latitude": 48.8566, "longitude": 2.3522}),
            "test_receiver_2": MagicMock(location={"latitude": 51.5074, "longitude": -0.1278})
        }
        
        # Appeler la méthode à tester
        await self.app.initialize()  # Initialiser les composants
        await self.app._process_waterfall_data()
        
        # Vérifier que les méthodes ont été appelées
        mock_waterfall_manager.get_all_streams.assert_called_once()
        mock_stream1.get_latest_spectrum.assert_called_once()
        mock_stream1.get_frequency_range.assert_called_once()
        mock_stream2.get_latest_spectrum.assert_called_once()
        mock_stream2.get_frequency_range.assert_called_once()
        
        self.app.signal_processor.process_spectrum.assert_called()
        self.app.signal_detector.detect_from_spectrum.assert_called()
        self.app.rssi_computer.compute_rssi.assert_called()
        self.app.alert_manager.check_signals.assert_called()
        self.app.triangulator.triangulate.assert_called()

    @pytest.mark.asyncio
    async def test_export_data(self):
        """Tester l'exportation des données."""
        # Configurer les mocks
        mock_audio_manager = MagicMock()
        mock_audio_stream = MagicMock()
        mock_audio_stream.get_recent_audio.return_value = np.zeros(12000 * 5)  # 5 secondes d'audio
        mock_audio_stream.sample_rate = 12000
        mock_audio_manager.streams = {"test_receiver_1": mock_audio_stream}
        
        mock_data_exporter = MagicMock()
        mock_data_exporter.export_audio.return_value = "/path/to/exported/audio.wav"
        mock_data_exporter.export_spectrum_data.return_value = "/path/to/exported/spectrum.png"
        mock_data_exporter.export_triangulation.return_value = "/path/to/exported/triangulation.json"
        
        # Configurer l'application
        self.app.audio_manager = mock_audio_manager
        self.app.data_exporter = mock_data_exporter
        self.app.kiwi_connections = {"test_receiver_1": MagicMock()}
        
        # Ajouter des données simulées
        test_signal = SignalDetection(
            frequency=7.06e6,
            bandwidth=2800.0,
            power=-60.0,
            snr=30.0,
            signal_type=SignalType.AM,
            confidence=0.9,
            timestamp=1234567890.0
        )
        self.app.active_signals = {1: test_signal}
        
        test_triangulation = TriangulationResult(
            latitude=50.0,
            longitude=5.0,
            radius_km=10.0,
            confidence=0.8,
            signal_frequency=7.06e6,
            timestamp=1234567890.0
        )
        self.app.triangulation_results = {7.06e6: test_triangulation}
        
        # Tester l'exportation audio
        result = self.app.export_data('audio', frequency=7.06e6, duration=5.0)
        self.assertEqual(result, ["/path/to/exported/audio.wav"])
        mock_audio_stream.get_recent_audio.assert_called_with(seconds=5.0)
        mock_data_exporter.export_audio.assert_called()
        
        # Tester l'exportation du spectre
        result = self.app.export_data('spectrum', frequency=7.06e6)
        self.assertEqual(result, "/path/to/exported/spectrum.png")
        mock_data_exporter.export_spectrum_data.assert_called_with(test_signal)
        
        # Tester l'exportation de la triangulation
        result = self.app.export_data('triangulation', frequency=7.06e6)
        self.assertEqual(result, "/path/to/exported/triangulation.json")
        mock_data_exporter.export_triangulation.assert_called_with(test_triangulation)
        
        # Tester l'exportation de tous les résultats de triangulation
        mock_data_exporter.export_triangulation.reset_mock()
        result = self.app.export_data('triangulation')
        self.assertEqual(result, ["/path/to/exported/triangulation.json"])
        mock_data_exporter.export_triangulation.assert_called_with(test_triangulation)


if __name__ == '__main__':
    unittest.main() 