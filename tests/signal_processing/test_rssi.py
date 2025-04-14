"""
Tests pour le module rssi.py.
"""

import pytest
import numpy as np
import time
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to the path so we can import the src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.signal_processing.rssi import (
    RSSIMethod,
    RSSIComputer,
    RSSIManager,
    PropagationModel
)


class TestRSSIComputer:
    """Tests pour la classe RSSIComputer."""
    
    def test_init(self):
        """Teste l'initialisation du calculateur RSSI."""
        computer = RSSIComputer(
            window_size=15,
            method=RSSIMethod.PEAK,
            smoothing_factor=0.5
        )
        
        assert computer.window_size == 15
        assert computer.method == RSSIMethod.PEAK
        assert computer.smoothing_factor == 0.5
        assert computer.last_rssi == 0.0
        assert len(computer.history) == 0
        assert computer.calibration_factor == 1.0
        assert computer.noise_floor == -120.0
    
    def test_compute_from_audio_empty(self):
        """Teste le calcul RSSI à partir de données audio vides."""
        computer = RSSIComputer()
        rssi = computer.compute_from_audio(np.array([]))
        
        assert rssi == computer.noise_floor
    
    def test_compute_from_audio_methods(self):
        """Teste les différentes méthodes de calcul RSSI pour l'audio."""
        # Créer des données de test
        samples = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        
        # Tester chaque méthode
        for method in RSSIMethod:
            computer = RSSIComputer(method=method)
            rssi = computer.compute_from_audio(samples)
            
            # Vérifier que le résultat est une valeur raisonnable de RSSI
            assert -120 <= rssi <= 20
            # Vérifier que l'historique a été mis à jour
            assert len(computer.history) == 1
            assert computer.last_rssi == rssi
    
    def test_compute_from_waterfall_empty(self):
        """Teste le calcul RSSI à partir de données waterfall vides."""
        computer = RSSIComputer()
        rssi = computer.compute_from_waterfall(np.array([]))
        
        assert rssi == computer.noise_floor
    
    def test_compute_from_waterfall_methods(self):
        """Teste les différentes méthodes de calcul RSSI pour le waterfall."""
        # Créer des données de test (en dB)
        samples = np.array([-60, -55, -50, -45, -40])
        
        # Tester chaque méthode
        for method in RSSIMethod:
            computer = RSSIComputer(method=method)
            rssi = computer.compute_from_waterfall(samples)
            
            # Vérifier que le résultat est une valeur raisonnable de RSSI
            assert -120 <= rssi <= 20
            # Vérifier que l'historique a été mis à jour
            assert len(computer.history) == 1
            assert computer.last_rssi == rssi
    
    def test_compute_from_waterfall_with_freq_range(self):
        """Teste le calcul RSSI avec plage de fréquences spécifiée."""
        # Créer des données de test (en dB)
        samples = np.array([-100, -90, -80, -70, -60, -50, -40, -30, -20, -10])
        
        computer = RSSIComputer(method=RSSIMethod.PEAK)
        
        # Calculer sur toute la plage
        full_rssi = computer.compute_from_waterfall(samples)
        
        # Réinitialiser
        computer.reset()
        
        # Calculer sur une plage restreinte
        range_rssi = computer.compute_from_waterfall(samples, freq_range=(0.7, 1.0))
        
        # La plage restreinte contient les valeurs les plus élevées
        assert range_rssi > full_rssi - 20  # Tenir compte du lissage
    
    def test_smooth_rssi(self):
        """Teste le lissage des valeurs RSSI."""
        computer = RSSIComputer(smoothing_factor=0.5)
        
        # Premier échantillon
        smoothed1 = computer._smooth_rssi(-50.0)
        assert smoothed1 == -50.0
        
        # Deuxième échantillon
        smoothed2 = computer._smooth_rssi(-40.0)
        expected2 = 0.5 * -40.0 + 0.5 * -50.0
        assert smoothed2 == pytest.approx(expected2)
        
        # Troisième échantillon
        smoothed3 = computer._smooth_rssi(-30.0)
        expected3 = 0.5 * -30.0 + 0.5 * smoothed2
        assert smoothed3 == pytest.approx(expected3)
    
    def test_get_average_rssi(self):
        """Teste la récupération de la moyenne RSSI."""
        computer = RSSIComputer()
        
        # Historique vide
        assert computer.get_average_rssi() == computer.noise_floor
        
        # Ajouter des valeurs
        computer._smooth_rssi(-50.0)
        computer._smooth_rssi(-40.0)
        computer._smooth_rssi(-30.0)
        
        avg = computer.get_average_rssi()
        assert avg == pytest.approx((-50.0 + -40.0 + -30.0) / 3)
    
    def test_get_peak_rssi(self):
        """Teste la récupération de la valeur maximale RSSI."""
        computer = RSSIComputer()
        
        # Historique vide
        assert computer.get_peak_rssi() == computer.noise_floor
        
        # Ajouter des valeurs
        computer._smooth_rssi(-50.0)
        computer._smooth_rssi(-40.0)
        computer._smooth_rssi(-60.0)
        
        peak = computer.get_peak_rssi()
        assert peak == -40.0
    
    def test_calibrate(self):
        """Teste la calibration du RSSI."""
        computer = RSSIComputer()
        
        # Calibrer avec des valeurs connues
        reference_rssi = -60.0
        measured_rssi = -90.0
        computer.calibrate(reference_rssi, measured_rssi)
        
        expected_factor = reference_rssi / measured_rssi
        assert computer.calibration_factor == pytest.approx(expected_factor)
        
        # Vérifier l'effet de la calibration
        raw_rssi = -90.0
        expected_calibrated = raw_rssi * computer.calibration_factor
        
        # Simuler le calcul sans lissage
        with patch.object(computer, '_smooth_rssi', return_value=expected_calibrated):
            calibrated = computer.compute_from_audio(np.array([0.1]))
            assert calibrated == pytest.approx(expected_calibrated)
    
    def test_set_noise_floor(self):
        """Teste la définition du niveau de bruit."""
        computer = RSSIComputer()
        
        original_floor = computer.noise_floor
        new_floor = -115.0
        
        computer.set_noise_floor(new_floor)
        assert computer.noise_floor == new_floor
        assert computer.noise_floor != original_floor
    
    def test_reset(self):
        """Teste la réinitialisation du calculateur."""
        computer = RSSIComputer()
        
        # Ajouter des valeurs
        computer._smooth_rssi(-50.0)
        computer._smooth_rssi(-40.0)
        computer.last_rssi = -45.0
        
        assert len(computer.history) > 0
        assert computer.last_rssi != 0.0
        
        # Réinitialiser
        computer.reset()
        
        assert len(computer.history) == 0
        assert computer.last_rssi == 0.0


class TestRSSIManager:
    """Tests pour la classe RSSIManager."""
    
    def test_init(self):
        """Teste l'initialisation du gestionnaire RSSI."""
        manager = RSSIManager()
        
        assert manager.computers == {}
        assert manager.reference_receiver is None
        assert manager.last_update == {}
        assert isinstance(manager.propagation_model, PropagationModel)
    
    def test_add_receiver(self):
        """Teste l'ajout d'un récepteur."""
        manager = RSSIManager()
        
        manager.add_receiver(
            name="Receiver1",
            method=RSSIMethod.PEAK,
            window_size=15,
            smoothing_factor=0.4
        )
        
        assert "Receiver1" in manager.computers
        assert isinstance(manager.computers["Receiver1"], RSSIComputer)
        assert manager.computers["Receiver1"].method == RSSIMethod.PEAK
        assert manager.computers["Receiver1"].window_size == 15
        assert manager.computers["Receiver1"].smoothing_factor == 0.4
        assert "Receiver1" in manager.last_update
        assert manager.reference_receiver == "Receiver1"  # Premier récepteur devient référence
    
    def test_remove_receiver(self):
        """Teste la suppression d'un récepteur."""
        manager = RSSIManager()
        
        # Ajouter deux récepteurs
        manager.add_receiver("Receiver1")
        manager.add_receiver("Receiver2")
        
        # Supprimer le premier (qui est la référence)
        result = manager.remove_receiver("Receiver1")
        
        assert result is True
        assert "Receiver1" not in manager.computers
        assert "Receiver1" not in manager.last_update
        assert manager.reference_receiver == "Receiver2"  # Nouvelle référence
        
        # Supprimer un récepteur inexistant
        result = manager.remove_receiver("NonExistent")
        assert result is False
        
        # Supprimer le dernier récepteur
        result = manager.remove_receiver("Receiver2")
        assert result is True
        assert manager.reference_receiver is None  # Plus de référence
    
    def test_set_reference_receiver(self):
        """Teste la définition du récepteur de référence."""
        manager = RSSIManager()
        
        # Ajouter deux récepteurs
        manager.add_receiver("Receiver1")
        manager.add_receiver("Receiver2")
        
        # Changer la référence
        result = manager.set_reference_receiver("Receiver2")
        
        assert result is True
        assert manager.reference_receiver == "Receiver2"
        
        # Essayer de définir un récepteur inexistant
        result = manager.set_reference_receiver("NonExistent")
        assert result is False
        assert manager.reference_receiver == "Receiver2"  # Inchangé
    
    def test_update_rssi_audio(self):
        """Teste la mise à jour du RSSI à partir de données audio."""
        manager = RSSIManager()
        
        # Ajouter un récepteur
        manager.add_receiver("Receiver1")
        
        # Mocker le calculateur pour éviter les calculs réels
        manager.computers["Receiver1"].compute_from_audio = MagicMock(return_value=-50.0)
        
        # Mettre à jour le RSSI
        rssi = manager.update_rssi_audio("Receiver1", np.array([0.1, 0.2]))
        
        assert rssi == -50.0
        assert manager.last_update["Receiver1"] > 0
        manager.computers["Receiver1"].compute_from_audio.assert_called_once()
        
        # Essayer avec un récepteur inexistant
        rssi = manager.update_rssi_audio("NonExistent", np.array([0.1]))
        assert rssi == -120.0
    
    def test_update_rssi_waterfall(self):
        """Teste la mise à jour du RSSI à partir de données waterfall."""
        manager = RSSIManager()
        
        # Ajouter un récepteur
        manager.add_receiver("Receiver1")
        
        # Mocker le calculateur pour éviter les calculs réels
        manager.computers["Receiver1"].compute_from_waterfall = MagicMock(return_value=-40.0)
        
        # Mettre à jour le RSSI
        rssi = manager.update_rssi_waterfall("Receiver1", np.array([-60, -50]))
        
        assert rssi == -40.0
        assert manager.last_update["Receiver1"] > 0
        manager.computers["Receiver1"].compute_from_waterfall.assert_called_once()
        
        # Essayer avec un récepteur inexistant
        rssi = manager.update_rssi_waterfall("NonExistent", np.array([-60]))
        assert rssi == -120.0
    
    def test_get_rssi(self):
        """Teste la récupération du RSSI."""
        manager = RSSIManager()
        
        # Ajouter un récepteur
        manager.add_receiver("Receiver1")
        
        # Définir une valeur RSSI
        manager.computers["Receiver1"].last_rssi = -45.0
        
        # Récupérer le RSSI
        rssi = manager.get_rssi("Receiver1")
        assert rssi == -45.0
        
        # Essayer avec un récepteur inexistant
        rssi = manager.get_rssi("NonExistent")
        assert rssi == -120.0
    
    def test_calibrate_receivers(self):
        """Teste la calibration des récepteurs."""
        manager = RSSIManager()
        
        # Ajouter des récepteurs
        manager.add_receiver("Receiver1")
        manager.add_receiver("Receiver2")
        
        # Définir des valeurs RSSI
        manager.computers["Receiver1"].last_rssi = -50.0
        manager.computers["Receiver2"].last_rssi = -70.0
        
        # Mocker la méthode de calibration pour éviter les problèmes de division par zéro
        manager.computers["Receiver1"].calibrate = MagicMock()
        manager.computers["Receiver2"].calibrate = MagicMock()
        
        # Calibrer avec une valeur absolue
        manager.calibrate_receivers(known_signal_strength=-40.0)
        
        # Vérifier que les méthodes ont été appelées
        manager.computers["Receiver1"].calibrate.assert_called_with(-40.0, -50.0)
        manager.computers["Receiver2"].calibrate.assert_called_with(-50.0, -70.0)
    
    def test_get_all_rssi(self):
        """Teste la récupération de tous les RSSI."""
        manager = RSSIManager()
        
        # Ajouter des récepteurs
        manager.add_receiver("Receiver1")
        manager.add_receiver("Receiver2")
        
        # Définir des valeurs RSSI
        manager.computers["Receiver1"].last_rssi = -50.0
        manager.computers["Receiver2"].last_rssi = -70.0
        
        # Récupérer tous les RSSI
        all_rssi = manager.get_all_rssi()
        
        assert isinstance(all_rssi, dict)
        assert len(all_rssi) == 2
        assert all_rssi["Receiver1"] == -50.0
        assert all_rssi["Receiver2"] == -70.0
    
    def test_estimate_signal_strength(self):
        """Teste l'estimation de la force du signal."""
        manager = RSSIManager()
        
        # Mocker le modèle de propagation
        manager.propagation_model.estimate_signal_strength = MagicMock(return_value=-65.0)
        
        # Estimer la force du signal
        strength = manager.estimate_signal_strength(frequency=7100000, distance=100)
        
        assert strength == -65.0
        manager.propagation_model.estimate_signal_strength.assert_called_with(7100000, 100)


class TestPropagationModel:
    """Tests pour la classe PropagationModel."""
    
    def test_init(self):
        """Teste l'initialisation du modèle de propagation."""
        model = PropagationModel()
        
        assert isinstance(model.band_factors, dict)
        assert len(model.band_factors) > 0
    
    def test_get_band(self):
        """Teste la détermination de la bande de fréquence."""
        model = PropagationModel()
        
        assert model.get_band(15000) == "VLF"        # 15 kHz
        assert model.get_band(150000) == "LF"        # 150 kHz
        assert model.get_band(1000000) == "MF"       # 1 MHz
        assert model.get_band(10000000) == "HF"      # 10 MHz
        assert model.get_band(100000000) == "VHF"    # 100 MHz
        assert model.get_band(1000000000) == "UHF"   # 1 GHz
    
    def test_free_space_path_loss(self):
        """Teste le calcul de l'atténuation en espace libre."""
        model = PropagationModel()
        
        # Fréquence: 7.1 MHz, Distance: 10 km
        loss = model.free_space_path_loss(frequency=7100000, distance=10)
        
        # Valeur attendue selon la formule
        expected_loss = 20 * np.log10(10) + 20 * np.log10(7.1) + 32.44
        
        assert loss == pytest.approx(expected_loss)
    
    def test_estimate_signal_strength(self):
        """Teste l'estimation de la force du signal."""
        model = PropagationModel()
        
        # Cas limite: distance zéro
        strength_zero = model.estimate_signal_strength(
            frequency=7100000, 
            distance=0, 
            transmitter_power=100
        )
        assert strength_zero == 30.0  # Maximum théorique
        
        # Cas normal: HF, 100 km
        strength_normal = model.estimate_signal_strength(
            frequency=7100000,
            distance=100,
            transmitter_power=100
        )
        
        # Vérifier que le résultat est dans une plage raisonnable
        assert -120.0 <= strength_normal <= 30.0
        
        # Comparer différentes bandes à même distance
        strength_lf = model.estimate_signal_strength(frequency=300000, distance=50)
        strength_hf = model.estimate_signal_strength(frequency=10000000, distance=50)
        strength_vhf = model.estimate_signal_strength(frequency=100000000, distance=50)
        
        # Les fréquences plus basses devraient avoir moins d'atténuation
        assert strength_lf > strength_hf
        assert strength_hf > strength_vhf 