"""
Tests d'intégration pour l'outil de triangulation SDR.

Ces tests valident le bon fonctionnement des différents composants
lorsqu'ils interagissent ensemble dans des conditions réelles.
"""

import os
import asyncio
import time
import pytest
import unittest
import logging
from unittest.mock import patch, MagicMock, AsyncMock

from src.main import SDRTriangulationApp
from src.utils.config_loader import load_config
from src.utils.logger import get_logger, configure_logger, set_log_level
from src.sdr_client.kiwi_connection import KiwiConnection, KiwiSDRMode

# Désactiver les logs pour les tests
configure_logger({"app": {"log_level": "ERROR"}})
set_log_level("ERROR")
logger = get_logger(__name__)

# URL de KiwiSDR publics pour les tests
TEST_KIWISDR_URLS = [
    "wss://kiwisdr.northlandradio.nz:8073/",  # Nouvelle-Zélande
    "wss://kiwisdr.vanuatubox.net:8073/",     # Vanuatu
    "wss://sdr.ct2jsg.com:8073/"              # Portugal
]


class TestKiwiSDRConnectivity(unittest.TestCase):
    """Tests d'intégration pour la connectivité aux KiwiSDR."""

    def setUp(self):
        """Configuration avant chaque test."""
        # Configuration de test
        self.test_config = {
            "receivers": [
                {
                    "name": "test_receiver_1",
                    "url": TEST_KIWISDR_URLS[0],
                    "location": {"latitude": -35.7, "longitude": 174.3}
                }
            ],
            "signal_processing": {
                "fft_size": 1024,
                "sample_rate": 12000,
                "initial_frequency": 7100000,
                "modulation_mode": "am"
            }
        }

    @pytest.mark.asyncio
    async def test_kiwi_connection_basic(self):
        """Test de connexion basique à un KiwiSDR."""
        kiwi = KiwiConnection(
            url=TEST_KIWISDR_URLS[0],
            name="test_receiver",
            location={"latitude": -35.7, "longitude": 174.3}
        )
        
        try:
            # Connexion
            connect_result = await kiwi.connect()
            self.assertTrue(connect_result, "La connexion au KiwiSDR a échoué")
            
            # Authentification
            auth_result = await kiwi.authenticate()
            self.assertTrue(auth_result, "L'authentification au KiwiSDR a échoué")
            
            # Configuration de la fréquence
            freq_result = await kiwi.set_frequency(7100000)  # 7.1 MHz
            self.assertTrue(freq_result, "La configuration de la fréquence a échoué")
            
            # Configuration du mode
            mode_result = await kiwi.set_mode(KiwiSDRMode.AM)
            self.assertTrue(mode_result, "La configuration du mode a échoué")
            
            # Vérifier l'état
            self.assertTrue(kiwi.is_healthy(), "Le KiwiSDR n'est pas en bon état après configuration")
            
            # Se déconnecter
            await kiwi.disconnect()
            
        except Exception as e:
            self.fail(f"Exception lors du test de connexion: {e}")

    @pytest.mark.asyncio
    async def test_app_integration_with_kiwisdr(self):
        """Test d'intégration avec l'application complète."""
        # Patcher le chargement de config pour utiliser notre config de test
        with patch('src.main.load_config') as mock_load_config:
            mock_load_config.return_value = self.test_config
            
            # Créer l'application
            app = SDRTriangulationApp()
            
            try:
                # Initialiser l'application
                init_result = await app.initialize()
                self.assertTrue(init_result, "L'initialisation de l'application a échoué")
                
                # Connecter les récepteurs
                connect_results = await app.connect_receivers()
                self.assertTrue(any(connect_results.values()), "Aucun récepteur n'a pu être connecté")
                
                # Démarrer les flux
                stream_results = await app.start_streams()
                self.assertTrue(
                    any(stream_results['audio'].values()) or any(stream_results['waterfall'].values()),
                    "Aucun flux audio ou waterfall n'a pu être démarré"
                )
                
                # Laisser tourner l'application un court instant
                await asyncio.sleep(2)
                
                # Arrêter l'application
                await app.stop()
                
            except Exception as e:
                self.fail(f"Exception lors du test d'intégration: {e}")


class TestSignalProcessingIntegration(unittest.TestCase):
    """Tests d'intégration pour le traitement du signal en temps réel."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        # Configuration de test
        self.test_config = {
            "receivers": [
                {
                    "name": "test_receiver_1",
                    "url": TEST_KIWISDR_URLS[0],
                    "location": {"latitude": -35.7, "longitude": 174.3}
                }
            ],
            "signal_processing": {
                "fft_size": 1024,
                "sample_rate": 12000,
                "initial_frequency": 7100000,
                "modulation_mode": "am"
            }
        }
    
    @pytest.mark.asyncio
    async def test_real_time_signal_processing(self):
        """Test du traitement du signal en temps réel."""
        # Patcher le chargement de config pour utiliser notre config de test
        with patch('src.main.load_config') as mock_load_config:
            mock_load_config.return_value = self.test_config
            
            # Créer l'application
            app = SDRTriangulationApp()
            
            try:
                # Initialiser l'application
                await app.initialize()
                
                # Connecter les récepteurs
                connect_results = await app.connect_receivers()
                if not any(connect_results.values()):
                    self.skipTest("Aucun récepteur n'a pu être connecté pour le test")
                
                # Démarrer les flux
                stream_results = await app.start_streams()
                if not any(stream_results['waterfall'].values()):
                    self.skipTest("Aucun flux waterfall n'a pu être démarré pour le test")
                
                # Traiter manuellement les données waterfall
                await app._process_waterfall_data()
                
                # Vérifier que le traitement ne génère pas d'exception
                # Si nous arrivons ici, c'est déjà une réussite
                
                # On peut vérifier si des signaux ont été détectés,
                # mais c'est dépendant de la présence réelle de signaux
                # donc on ne le fait pas dans un test automatisé
                
                # Arrêter l'application
                await app.stop()
                
            except Exception as e:
                self.fail(f"Exception lors du test de traitement du signal: {e}")


class TestTriangulationIntegration(unittest.TestCase):
    """Tests d'intégration pour la triangulation avec des émetteurs connus."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        # Configuration avec 3 récepteurs pour permettre la triangulation
        self.test_config = {
            "receivers": [
                {
                    "name": "receiver_1",
                    "url": TEST_KIWISDR_URLS[0],
                    "location": {"latitude": -35.7, "longitude": 174.3}
                },
                {
                    "name": "receiver_2",
                    "url": TEST_KIWISDR_URLS[1],
                    "location": {"latitude": -17.7, "longitude": 168.3}
                },
                {
                    "name": "receiver_3",
                    "url": TEST_KIWISDR_URLS[2],
                    "location": {"latitude": 40.2, "longitude": -8.4}
                }
            ],
            "signal_processing": {
                "fft_size": 1024,
                "sample_rate": 12000,
                "initial_frequency": 7100000,  # 7.1 MHz (bande radio amateur)
                "modulation_mode": "am"
            },
            "triangulation": {
                "min_receivers": 2,  # Pour les tests, on accepte seulement 2 récepteurs
                "max_distance_km": 20000,  # Pour couvrir le monde entier
                "confidence_threshold": 0.3  # Seuil bas pour les tests
            }
        }
    
    @pytest.mark.asyncio
    async def test_triangulation_with_known_transmitters(self):
        """Test de triangulation avec des émetteurs connus (stations de radio)."""
        # Ce test utilise des émetteurs connus (stations de radiodiffusion internationale)
        # qui ont une forte probabilité d'être détectés
        
        # Pour ce test, on utilise un mock partiel - on se connecte réellement aux KiwiSDR
        # mais on simule la réception de données RSSI fortes pour forcer une triangulation
        
        with patch('src.main.load_config') as mock_load_config, \
             patch('src.signal_processing.rssi.RSSIComputer.compute_rssi') as mock_compute_rssi:
            
            mock_load_config.return_value = self.test_config
            
            # Simuler des valeurs RSSI fortes
            mock_compute_rssi.return_value = -50.0  # Signal fort
            
            # Créer l'application
            app = SDRTriangulationApp()
            
            try:
                # Initialiser l'application
                await app.initialize()
                
                # Connecter les récepteurs (tenter de se connecter à des KiwiSDR réels)
                connect_results = await app.connect_receivers()
                connected_count = sum(1 for result in connect_results.values() if result)
                
                if connected_count < 2:
                    self.skipTest(f"Insuffisamment de récepteurs connectés pour la triangulation ({connected_count}/2)")
                
                # Démarrer les flux
                stream_results = await app.start_streams()
                
                # Simuler des données RSSI pour forcer une triangulation
                # On crée un dictionnaire avec des données RSSI simulées
                rssi_by_freq = {
                    7100000: {}  # Fréquence 7.1 MHz
                }
                
                # Ajouter des valeurs RSSI pour chaque récepteur connecté
                for name, result in connect_results.items():
                    if result:
                        rssi_by_freq[7100000][name] = -50.0  # Signal fort
                
                # Effectuer la triangulation avec les données simulées
                app._perform_triangulation(rssi_by_freq, time.time())
                
                # Vérifier qu'un résultat de triangulation a été généré
                self.assertTrue(len(app.triangulation_results) > 0, 
                             "Aucun résultat de triangulation n'a été généré")
                
                # Vérifier que le résultat à la fréquence 7.1 MHz existe
                self.assertIn(7100000, app.triangulation_results, 
                           "Pas de résultat de triangulation pour 7.1 MHz")
                
                # Vérifier la validité du résultat
                result = app.triangulation_results[7100000]
                self.assertIsNotNone(result.latitude, "Latitude manquante dans le résultat")
                self.assertIsNotNone(result.longitude, "Longitude manquante dans le résultat")
                self.assertIsNotNone(result.radius_km, "Rayon manquant dans le résultat")
                self.assertIsNotNone(result.confidence, "Indice de confiance manquant dans le résultat")
                
                # Arrêter l'application
                await app.stop()
                
            except Exception as e:
                self.fail(f"Exception lors du test de triangulation: {e}")


class TestDataExportIntegration(unittest.TestCase):
    """Tests d'intégration pour l'exportation des données."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.test_dir = "test_exports"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Configuration de test
        self.test_config = {
            "receivers": [
                {
                    "name": "test_receiver",
                    "url": TEST_KIWISDR_URLS[0],
                    "location": {"latitude": -35.7, "longitude": 174.3}
                }
            ],
            "data_export": {
                "output_dir": self.test_dir,
                "enable_audio_export": True,
                "enable_spectrum_export": True,
                "enable_triangulation_export": True,
                "auto_export_detected": True,
                "auto_export_triangulation": True
            }
        }
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        # Option pour nettoyer le répertoire de test
        # import shutil
        # shutil.rmtree(self.test_dir, ignore_errors=True)
        pass
    
    @pytest.mark.asyncio
    async def test_data_export_functionality(self):
        """Test de la fonctionnalité d'exportation des données."""
        with patch('src.main.load_config') as mock_load_config:
            mock_load_config.return_value = self.test_config
            
            # Créer l'application
            app = SDRTriangulationApp()
            
            try:
                # Initialiser l'application
                await app.initialize()
                
                # Exporter manuellement des données
                # 1. Audio
                import numpy as np
                audio_data = np.random.normal(0, 0.1, 12000 * 3)  # 3 secondes d'audio
                audio_result = app.export_data('audio', frequency=7100000, duration=3.0)
                
                # Vérifier que l'exportation audio a fonctionné
                self.assertIsNotNone(audio_result, "L'exportation audio a échoué")
                if audio_result:
                    for path in audio_result:
                        self.assertTrue(os.path.exists(path), f"Le fichier exporté {path} n'existe pas")
                
                # 2. Triangulation
                from src.signal_processing.triangulation import TriangulationResult
                test_result = TriangulationResult(
                    latitude=45.0,
                    longitude=5.0,
                    radius_km=100.0,
                    confidence=0.8,
                    signal_frequency=7100000,
                    timestamp=time.time()
                )
                
                # Ajouter le résultat à l'application
                app.triangulation_results[7100000] = test_result
                
                # Exporter
                tri_result = app.export_data('triangulation', frequency=7100000)
                
                # Vérifier que l'exportation a fonctionné
                self.assertIsNotNone(tri_result, "L'exportation de triangulation a échoué")
                self.assertTrue(os.path.exists(tri_result), f"Le fichier exporté {tri_result} n'existe pas")
                
                # Nettoyer
                await app.stop()
                
            except Exception as e:
                self.fail(f"Exception lors du test d'exportation: {e}")


class TestAlertAnnotationIntegration(unittest.TestCase):
    """Tests d'intégration pour les alertes et annotations."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        # Configuration avec des règles d'alerte
        self.test_config = {
            "receivers": [
                {
                    "name": "test_receiver",
                    "url": TEST_KIWISDR_URLS[0],
                    "location": {"latitude": -35.7, "longitude": 174.3}
                }
            ],
            "signal_processing": {
                "fft_size": 1024,
                "sample_rate": 12000,
                "initial_frequency": 7100000,
                "modulation_mode": "am"
            },
            "alert_rules": [
                {
                    "name": "Signal fort",
                    "min_power": -60.0,
                    "signal_type": "am"
                },
                {
                    "name": "Signal CW",
                    "signal_type": "cw",
                    "min_frequency": 7000000,
                    "max_frequency": 7200000
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_alert_system(self):
        """Test du système d'alerte."""
        with patch('src.main.load_config') as mock_load_config:
            mock_load_config.return_value = self.test_config
            
            # Créer l'application
            app = SDRTriangulationApp()
            
            try:
                # Initialiser l'application
                await app.initialize()
                
                # Créer un signal qui déclenche une alerte
                from src.signal_processing.detection import SignalDetection, SignalType
                test_signal = SignalDetection(
                    frequency=7100000,
                    bandwidth=2800.0,
                    power=-50.0,  # Signal fort
                    snr=30.0,
                    signal_type=SignalType.AM,
                    confidence=0.9,
                    timestamp=time.time()
                )
                
                # Simuler la vérification d'alerte
                alerts = app.alert_manager.check_signals([test_signal])
                
                # Vérifier qu'une alerte a été déclenchée
                self.assertTrue(len(alerts) > 0, "Aucune alerte n'a été déclenchée")
                self.assertEqual(alerts[0]['rule_name'], "Signal fort", 
                               "Mauvaise règle d'alerte déclenchée")
                
                # Nettoyer
                await app.stop()
                
            except Exception as e:
                self.fail(f"Exception lors du test d'alerte: {e}")


if __name__ == '__main__':
    unittest.main() 