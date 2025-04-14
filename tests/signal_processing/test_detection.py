"""
Tests unitaires pour le module de détection de signaux.
"""

import unittest
import numpy as np
import time
from unittest.mock import patch, MagicMock
import logging

from src.signal_processing.detection import (
    SignalType, 
    SignalDetection, 
    SignalDetector, 
    AlertManager
)

# Désactiver les logs pendant les tests
logging.disable(logging.CRITICAL)


class TestSignalType(unittest.TestCase):
    """Tests pour l'enum SignalType."""
    
    def test_signal_types(self):
        """Vérifier les valeurs de l'enum."""
        self.assertEqual(SignalType.UNKNOWN.value, "unknown")
        self.assertEqual(SignalType.AM.value, "am")
        self.assertEqual(SignalType.FM.value, "fm")
        self.assertEqual(SignalType.SSB.value, "ssb")
        self.assertEqual(SignalType.CW.value, "cw")
        self.assertEqual(SignalType.DIGITAL.value, "digital")


class TestSignalDetection(unittest.TestCase):
    """Tests pour la classe SignalDetection."""
    
    def test_initialization(self):
        """Vérifier l'initialisation d'un objet SignalDetection."""
        signal = SignalDetection(
            frequency=14.200e6,
            bandwidth=2800.0,
            power=-65.0,
            snr=20.0,
            signal_type=SignalType.SSB,
            confidence=0.8,
            timestamp=1234567890.0
        )
        
        self.assertEqual(signal.frequency, 14.200e6)
        self.assertEqual(signal.bandwidth, 2800.0)
        self.assertEqual(signal.power, -65.0)
        self.assertEqual(signal.snr, 20.0)
        self.assertEqual(signal.signal_type, SignalType.SSB)
        self.assertEqual(signal.confidence, 0.8)
        self.assertEqual(signal.timestamp, 1234567890.0)
        self.assertEqual(signal.duration, 0.0)  # Valeur par défaut
        self.assertTrue(signal.is_active)  # Valeur par défaut


class TestSignalDetector(unittest.TestCase):
    """Tests pour la classe SignalDetector."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.detector = SignalDetector(
            threshold_db=-80.0,
            min_snr_db=10.0,
            min_duration_sec=1.0,
            max_inactive_sec=3.0,
            frequency_tolerance_hz=50.0
        )
    
    def test_initialization(self):
        """Vérifier l'initialisation du détecteur."""
        self.assertEqual(self.detector.threshold_db, -80.0)
        self.assertEqual(self.detector.min_snr_db, 10.0)
        self.assertEqual(self.detector.min_duration_sec, 1.0)
        self.assertEqual(self.detector.max_inactive_sec, 3.0)
        self.assertEqual(self.detector.frequency_tolerance_hz, 50.0)
        self.assertEqual(len(self.detector.signals), 0)
        self.assertEqual(len(self.detector.detection_history), 0)
    
    def _create_test_spectrum(self):
        """Créer un spectre de test avec quelques signaux simulés."""
        freq_range = np.linspace(14.0e6, 14.5e6, 1000)
        
        # Spectre de base (bruit)
        spectrum = np.random.normal(-100.0, 1.0, 1000)
        
        # Ajouter un signal AM
        center_idx = 250
        width = 30
        for i in range(center_idx - width, center_idx + width):
            if 0 <= i < 1000:
                spectrum[i] = -60 + np.random.normal(0, 0.5)
        
        # Ajouter un signal CW
        center_idx = 600
        for i in range(center_idx - 2, center_idx + 3):
            if 0 <= i < 1000:
                spectrum[i] = -55 + np.random.normal(0, 0.3)
        
        # Ajouter un signal FM
        center_idx = 800
        width = 50
        for i in range(center_idx - width, center_idx + width):
            if 0 <= i < 1000:
                spectrum[i] = -65 + np.random.normal(0, 1.0)
        
        return spectrum, freq_range
    
    @patch('src.signal_processing.optimized_processing.detect_peaks')
    def test_detect_from_spectrum(self, mock_detect_peaks):
        """Tester la détection à partir d'un spectre."""
        # Configurer le mock pour detect_peaks
        mock_detect_peaks.return_value = [
            (250, -60.0),  # Signal AM
            (600, -55.0),  # Signal CW
            (800, -65.0)   # Signal FM
        ]
        
        # Créer un spectre de test
        spectrum, frequencies = self._create_test_spectrum()
        
        # Appeler la fonction à tester
        timestamp = time.time()
        detected_signals = self.detector.detect_from_spectrum(spectrum, frequencies, timestamp)
        
        # Les 3 signaux ne seront pas tous immédiatement détectés à cause du filtrage des faux positifs
        # mais ils seront enregistrés dans l'historique de détection
        self.assertTrue(len(self.detector.detection_history) > 0)
        
        # Simuler plusieurs détections successives pour valider les signaux
        for _ in range(5):
            timestamp += 0.1
            detected_signals = self.detector.detect_from_spectrum(spectrum, frequencies, timestamp)
        
        # Maintenant au moins un signal devrait être validé
        self.assertTrue(len(detected_signals) > 0)
        
        # Vérifier que les signaux détectés ont les bonnes propriétés
        for signal in detected_signals:
            self.assertIsInstance(signal, SignalDetection)
            self.assertTrue(signal.power > -90.0)  # Signal assez fort
            self.assertTrue(signal.snr > self.detector.min_snr_db)
            self.assertTrue(signal.confidence > 0.0)
            self.assertEqual(signal.is_active, True)
    
    def test_detect_from_rssi(self):
        """Tester la détection à partir de valeurs RSSI."""
        # Dictionnaire de valeurs RSSI simulées pour plusieurs récepteurs
        rssi_values = {
            "receiver1": -65.0,
            "receiver2": -67.0,
            "receiver3": -70.0
        }
        
        # Paramètres du signal
        frequency = 14.200e6
        bandwidth = 2800.0
        
        # Premier appel - devrait être ajouté à l'historique mais pas encore validé
        timestamp = time.time()
        signal = self.detector.detect_from_rssi(rssi_values, frequency, bandwidth, timestamp)
        
        # Le signal ne devrait pas être validé immédiatement
        self.assertIsNone(signal)
        
        # Plusieurs détections successives pour valider le signal
        for _ in range(5):
            timestamp += 0.1
            signal = self.detector.detect_from_rssi(rssi_values, frequency, bandwidth, timestamp)
        
        # Maintenant le signal devrait être validé
        self.assertIsNotNone(signal)
        self.assertIsInstance(signal, SignalDetection)
        self.assertEqual(signal.frequency, frequency)
        self.assertEqual(signal.bandwidth, bandwidth)
        self.assertTrue(signal.power > self.detector.threshold_db)
        self.assertEqual(signal.signal_type, SignalType.UNKNOWN)  # Sans spectre, type inconnu
    
    def test_find_existing_signal(self):
        """Tester la recherche d'un signal existant."""
        # Ajouter manuellement un signal
        signal = SignalDetection(
            frequency=14.200e6,
            bandwidth=2800.0,
            power=-65.0,
            snr=20.0,
            signal_type=SignalType.SSB,
            confidence=0.8,
            timestamp=time.time()
        )
        
        self.detector.signals[1] = signal
        self.detector.next_signal_id = 2
        
        # Tester avec une fréquence proche
        found_id = self.detector._find_existing_signal(14.200e6 + 30.0)  # +30Hz, dans la tolérance
        self.assertEqual(found_id, 1)
        
        # Tester avec une fréquence trop éloignée
        found_id = self.detector._find_existing_signal(14.200e6 + 100.0)  # +100Hz, hors tolérance
        self.assertIsNone(found_id)
    
    def test_estimate_bandwidth(self):
        """Tester l'estimation de la largeur de bande."""
        # Créer un spectre simulé avec un signal
        spectrum = np.ones(100) * -100.0  # Niveau de bruit
        
        # Signal avec -3dB à 5 points de chaque côté du pic
        peak_idx = 50
        spectrum[peak_idx] = -60.0  # Pic
        
        for i in range(1, 6):
            spectrum[peak_idx - i] = -60.0 - i * 0.5  # Décroissance à gauche
            spectrum[peak_idx + i] = -60.0 - i * 0.5  # Décroissance à droite
        
        # -3dB à 5 points du pic
        spectrum[peak_idx - 5] = -63.0
        spectrum[peak_idx + 5] = -63.0
        
        # Fréquences: 100Hz de résolution
        frequencies = np.linspace(14.200e6, 14.210e6, 100)
        
        # Tester la fonction
        bandwidth = self.detector._estimate_bandwidth(spectrum, peak_idx, frequencies)
        
        # La largeur attendue est de 10 points, soit 1000Hz
        expected_bandwidth = 1000.0
        self.assertAlmostEqual(bandwidth, expected_bandwidth, delta=100.0)
    
    def test_classify_signal(self):
        """Tester la classification du type de signal."""
        # Créer un spectre pour chaque type de signal
        spectrum_size = 100
        frequencies = np.linspace(14.200e6, 14.210e6, spectrum_size)
        
        # Tester pour chaque type de signal
        test_cases = [
            # (bandwidth, signal_type)
            (30.0, SignalType.CW),
            (300.0, SignalType.SSB),
            (4000.0, SignalType.AM),
            (15000.0, SignalType.FM)
        ]
        
        for bandwidth, expected_type in test_cases:
            # Créer un spectre adapté à ce type
            spectrum = np.ones(spectrum_size) * -100.0
            peak_idx = spectrum_size // 2
            
            # Configurer le pic et la largeur
            width = int(bandwidth / (frequencies[1] - frequencies[0]))
            for i in range(max(0, peak_idx - width // 2), min(spectrum_size, peak_idx + width // 2)):
                spectrum[i] = -60.0
            
            # Pour SSB, ajouter de l'asymétrie
            if expected_type == SignalType.SSB:
                for i in range(peak_idx, min(spectrum_size, peak_idx + width // 2)):
                    spectrum[i] = -70.0  # Plus faible d'un côté
            
            # Tester la classification
            signal_type, confidence = self.detector._classify_signal(
                spectrum, peak_idx, bandwidth, frequencies
            )
            
            # Vérifier le résultat
            self.assertEqual(signal_type, expected_type, 
                          f"Signal avec largeur {bandwidth}Hz classifié comme {signal_type} au lieu de {expected_type}")
            self.assertTrue(0.0 <= confidence <= 1.0)
    
    def test_update_signals_state(self):
        """Tester la mise à jour de l'état des signaux."""
        # Ajouter des signaux
        now = time.time()
        
        # Signal actif récent
        signal1 = SignalDetection(
            frequency=14.200e6,
            bandwidth=2800.0,
            power=-65.0,
            snr=20.0,
            signal_type=SignalType.SSB,
            confidence=0.8,
            timestamp=now - 1.0,
            is_active=True
        )
        
        # Signal inactif ancien
        signal2 = SignalDetection(
            frequency=14.300e6,
            bandwidth=3000.0,
            power=-70.0,
            snr=15.0,
            signal_type=SignalType.AM,
            confidence=0.7,
            timestamp=now - 10.0,
            duration=5.0,
            is_active=False
        )
        
        self.detector.signals = {1: signal1, 2: signal2}
        self.detector.active_signals = 1
        
        # Mise à jour de l'état des signaux
        self.detector.last_detection_time = now - 2.0  # Plus de 1s d'écart
        self.detector._update_signals_state(now)
        
        # Signal1 devrait être marqué inactif
        self.assertFalse(self.detector.signals[1].is_active)
        self.assertEqual(self.detector.active_signals, 0)
        
        # Signal2 devrait être supprimé (inactif depuis plus de max_inactive_sec)
        self.assertNotIn(2, self.detector.signals)
    
    def test_get_active_signals(self):
        """Tester la récupération des signaux actifs."""
        # Créer des signaux actifs et inactifs
        signal1 = SignalDetection(
            frequency=14.200e6,
            bandwidth=2800.0,
            power=-65.0,
            snr=20.0,
            signal_type=SignalType.SSB,
            confidence=0.8,
            timestamp=time.time(),
            is_active=True
        )
        
        signal2 = SignalDetection(
            frequency=14.300e6,
            bandwidth=3000.0,
            power=-70.0,
            snr=15.0,
            signal_type=SignalType.AM,
            confidence=0.7,
            timestamp=time.time(),
            is_active=False
        )
        
        self.detector.signals = {1: signal1, 2: signal2}
        
        # Tester get_active_signals
        active_signals = self.detector.get_active_signals()
        self.assertEqual(len(active_signals), 1)
        self.assertEqual(active_signals[0], signal1)
        
        # Tester get_all_signals
        all_signals = self.detector.get_all_signals()
        self.assertEqual(len(all_signals), 2)
        self.assertIn(signal1, all_signals)
        self.assertIn(signal2, all_signals)
    
    def test_set_threshold(self):
        """Tester la modification du seuil de détection."""
        initial_threshold = self.detector.threshold_db
        new_threshold = -75.0
        
        self.detector.set_threshold(new_threshold)
        self.assertEqual(self.detector.threshold_db, new_threshold)
        self.assertNotEqual(self.detector.threshold_db, initial_threshold)
    
    def test_reset(self):
        """Tester la réinitialisation du détecteur."""
        # Ajouter des signaux et des données d'historique
        self.detector.signals = {
            1: SignalDetection(
                frequency=14.200e6,
                bandwidth=2800.0,
                power=-65.0,
                snr=20.0,
                signal_type=SignalType.SSB,
                confidence=0.8,
                timestamp=time.time()
            )
        }
        self.detector.detection_history = {14.200e6: [time.time()]}
        self.detector.active_signals = 1
        
        # Réinitialiser
        self.detector.reset()
        
        # Vérifier que tout est vide
        self.assertEqual(len(self.detector.signals), 0)
        self.assertEqual(len(self.detector.detection_history), 0)
        self.assertEqual(self.detector.active_signals, 0)
        self.assertEqual(self.detector.next_signal_id, 1)


class TestAlertManager(unittest.TestCase):
    """Tests pour la classe AlertManager."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.alert_manager = AlertManager()
    
    def test_add_rule(self):
        """Tester l'ajout d'une règle d'alerte."""
        rule_id = self.alert_manager.add_rule(
            name="Test Rule",
            min_frequency=14.0e6,
            max_frequency=14.5e6,
            min_power=-80.0,
            signal_type=SignalType.AM,
            min_duration=5.0
        )
        
        self.assertEqual(rule_id, 1)
        self.assertEqual(len(self.alert_manager.alert_rules), 1)
        
        rule = self.alert_manager.alert_rules[0]
        self.assertEqual(rule["name"], "Test Rule")
        self.assertEqual(rule["min_frequency"], 14.0e6)
        self.assertEqual(rule["max_frequency"], 14.5e6)
        self.assertEqual(rule["min_power"], -80.0)
        self.assertEqual(rule["signal_type"], SignalType.AM)
        self.assertEqual(rule["min_duration"], 5.0)
        self.assertTrue(rule["active"])
    
    def test_remove_rule(self):
        """Tester la suppression d'une règle d'alerte."""
        # Ajouter deux règles
        rule1_id = self.alert_manager.add_rule(name="Rule 1")
        rule2_id = self.alert_manager.add_rule(name="Rule 2")
        
        # Vérifier avant suppression
        self.assertEqual(len(self.alert_manager.alert_rules), 2)
        
        # Supprimer une règle
        result = self.alert_manager.remove_rule(rule1_id)
        self.assertTrue(result)
        
        # Vérifier après suppression
        self.assertEqual(len(self.alert_manager.alert_rules), 1)
        self.assertEqual(self.alert_manager.alert_rules[0]["name"], "Rule 2")
        
        # Tenter de supprimer une règle inexistante
        result = self.alert_manager.remove_rule(999)
        self.assertFalse(result)
    
    def test_check_signals(self):
        """Tester la vérification des signaux par rapport aux règles d'alerte."""
        # Ajouter une règle
        self.alert_manager.add_rule(
            name="VHF Rule",
            min_frequency=144.0e6,
            max_frequency=146.0e6,
            min_power=-90.0
        )
        
        # Signal correspondant à la règle
        matching_signal = SignalDetection(
            frequency=145.0e6,
            bandwidth=10000.0,
            power=-75.0,
            snr=15.0,
            signal_type=SignalType.FM,
            confidence=0.9,
            timestamp=time.time()
        )
        
        # Signal ne correspondant pas à la règle
        non_matching_signal = SignalDetection(
            frequency=7.1e6,
            bandwidth=3000.0,
            power=-85.0,
            snr=10.0,
            signal_type=SignalType.SSB,
            confidence=0.8,
            timestamp=time.time()
        )
        
        # Tester avec un signal correspondant
        new_alerts = self.alert_manager.check_signals([matching_signal])
        self.assertEqual(len(new_alerts), 1)
        self.assertEqual(new_alerts[0]["rule_name"], "VHF Rule")
        self.assertEqual(new_alerts[0]["frequency"], 145.0e6)
        self.assertEqual(new_alerts[0]["signal_type"], "fm")
        
        # Tester avec un signal ne correspondant pas
        new_alerts = self.alert_manager.check_signals([non_matching_signal])
        self.assertEqual(len(new_alerts), 0)
        
        # Vérifier que l'alerte précédente est toujours active
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
    
    def test_callback(self):
        """Tester le mécanisme de callback lors d'une alerte."""
        # Créer un mock pour le callback
        callback_mock = MagicMock()
        self.alert_manager.add_callback(callback_mock)
        
        # Ajouter une règle
        self.alert_manager.add_rule(
            name="Test Rule",
            min_frequency=14.0e6,
            max_frequency=14.5e6
        )
        
        # Créer un signal correspondant
        signal = SignalDetection(
            frequency=14.2e6,
            bandwidth=3000.0,
            power=-75.0,
            snr=15.0,
            signal_type=SignalType.SSB,
            confidence=0.8,
            timestamp=time.time()
        )
        
        # Déclencher une alerte
        self.alert_manager.check_signals([signal])
        
        # Vérifier que le callback a été appelé
        callback_mock.assert_called_once()
        
        # Vérifier les arguments du callback
        alert = callback_mock.call_args[0][0]
        self.assertEqual(alert["rule_name"], "Test Rule")
        self.assertEqual(alert["frequency"], 14.2e6)
    
    def test_clean_inactive_alerts(self):
        """Tester le nettoyage des alertes inactives."""
        # Ajouter une règle
        self.alert_manager.add_rule(name="Test Rule")
        
        # Créer une alerte active
        self.alert_manager.active_alerts[1] = {
            "id": 1,
            "rule_id": 1,
            "rule_name": "Test Rule",
            "frequency": 14.2e6,
            "power": -75.0,
            "signal_type": "ssb",
            "timestamp": time.time(),
            "last_update": time.time()
        }
        
        # Créer une alerte inactive (vieille)
        self.alert_manager.active_alerts[2] = {
            "id": 2,
            "rule_id": 1,
            "rule_name": "Test Rule",
            "frequency": 14.3e6,
            "power": -80.0,
            "signal_type": "am",
            "timestamp": time.time() - 100.0,
            "last_update": time.time() - 100.0
        }
        
        # Nettoyer les alertes inactives
        self.alert_manager._clean_inactive_alerts(max_age_sec=30.0)
        
        # Vérifier que seule l'alerte active reste
        self.assertEqual(len(self.alert_manager.active_alerts), 1)
        self.assertIn(1, self.alert_manager.active_alerts)
        self.assertNotIn(2, self.alert_manager.active_alerts)
    
    def test_get_active_alerts(self):
        """Tester la récupération des alertes actives."""
        # Ajouter des alertes
        self.alert_manager.active_alerts = {
            1: {"id": 1, "rule_name": "Rule 1"},
            2: {"id": 2, "rule_name": "Rule 2"}
        }
        
        # Récupérer les alertes actives
        active_alerts = self.alert_manager.get_active_alerts()
        
        # Vérifier le résultat
        self.assertEqual(len(active_alerts), 2)
        self.assertTrue(any(alert["rule_name"] == "Rule 1" for alert in active_alerts))
        self.assertTrue(any(alert["rule_name"] == "Rule 2" for alert in active_alerts))


# Exécuter les tests
if __name__ == "__main__":
    unittest.main() 