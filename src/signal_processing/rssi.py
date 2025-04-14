"""
Module de calcul de RSSI (Received Signal Strength Indicator).

Ce module permet de:
- Calculer l'indicateur de puissance du signal reçu (RSSI)
- Calibrer les mesures RSSI entre différents récepteurs
- Appliquer un lissage temporel des valeurs RSSI
- Estimer la puissance du signal en fonction de la bande de fréquence
"""

import numpy as np
import time
from typing import Dict, List, Any, Optional, Tuple, Deque
from collections import deque
import logging
from enum import Enum

from src.utils.logger import get_logger

# Configuration du logger
logger = get_logger(__name__)


class RSSIMethod(Enum):
    """Méthodes de calcul du RSSI."""
    PEAK = "peak"           # Valeur de crête
    MEAN = "mean"           # Moyenne
    RMS = "rms"             # Root Mean Square (valeur efficace)
    MEDIAN = "median"       # Médiane
    WEIGHTED = "weighted"   # Moyenne pondérée des méthodes précédentes


class RSSIComputer:
    """
    Classe de calcul du RSSI.
    
    Cette classe permet de calculer le RSSI à partir des données audio
    ou waterfall, avec différentes méthodes et calibrations.
    """
    
    def __init__(self, 
                window_size: int = 10, 
                method: RSSIMethod = RSSIMethod.RMS,
                smoothing_factor: float = 0.3):
        """
        Initialise le calculateur de RSSI.
        
        Args:
            window_size: Taille de la fenêtre de lissage
            method: Méthode de calcul du RSSI
            smoothing_factor: Facteur de lissage exponentiel (0-1)
        """
        self.window_size = window_size
        self.method = method
        self.smoothing_factor = smoothing_factor
        
        self.last_rssi = 0.0
        self.history: Deque[float] = deque(maxlen=window_size)
        self.calibration_factor = 1.0
        self.noise_floor = -120.0  # dBm, valeur typique pour le bruit de fond
    
    def compute_from_audio(self, audio_samples: np.ndarray) -> float:
        """
        Calcule le RSSI à partir d'échantillons audio.
        
        Args:
            audio_samples: Tableau NumPy d'échantillons audio
            
        Returns:
            Valeur RSSI en dBm
        """
        if len(audio_samples) == 0:
            return self.noise_floor
        
        # Conversion en valeur absolue pour traiter les amplitudes
        samples = np.abs(audio_samples)
        
        # Calcul selon la méthode choisie
        if self.method == RSSIMethod.PEAK:
            # Valeur de crête
            raw_rssi = np.max(samples)
        elif self.method == RSSIMethod.MEAN:
            # Moyenne
            raw_rssi = np.mean(samples)
        elif self.method == RSSIMethod.RMS:
            # Root Mean Square (valeur efficace)
            raw_rssi = np.sqrt(np.mean(np.square(samples)))
        elif self.method == RSSIMethod.MEDIAN:
            # Médiane
            raw_rssi = np.median(samples)
        elif self.method == RSSIMethod.WEIGHTED:
            # Moyenne pondérée
            peak = np.max(samples)
            rms = np.sqrt(np.mean(np.square(samples)))
            mean = np.mean(samples)
            # Pondération: 20% peak, 60% RMS, 20% mean
            raw_rssi = 0.2 * peak + 0.6 * rms + 0.2 * mean
        else:
            # Par défaut: RMS
            raw_rssi = np.sqrt(np.mean(np.square(samples)))
        
        # Conversion en dBm (en supposant que les échantillons sont normalisés entre -1 et 1)
        # Équation: 20 * log10(amplitude) + référence
        # Où référence est un niveau de référence calibré (généralement entre -30 et 0 dBm)
        reference = -30.0  # dBm, à calibrer selon le récepteur
        
        # Si le signal est trop faible, utiliser le niveau de bruit
        if raw_rssi < 1e-10:
            rssi_dbm = self.noise_floor
        else:
            rssi_dbm = 20 * np.log10(raw_rssi) + reference
            
            # Appliquer le facteur de calibration
            rssi_dbm = rssi_dbm * self.calibration_factor
            
            # Limiter à des valeurs raisonnables
            rssi_dbm = max(rssi_dbm, self.noise_floor)
            rssi_dbm = min(rssi_dbm, 20.0)  # dBm max typique pour un récepteur SDR
        
        # Appliquer le lissage et mettre à jour l'historique
        smoothed_rssi = self._smooth_rssi(rssi_dbm)
        
        return smoothed_rssi
    
    def compute_from_waterfall(self, waterfall_data: np.ndarray, 
                              freq_range: Optional[Tuple[int, int]] = None) -> float:
        """
        Calcule le RSSI à partir des données de spectrogramme waterfall.
        
        Args:
            waterfall_data: Tableau NumPy de données de spectrogramme
            freq_range: Tuple optionnel de (début, fin) pour limiter la plage de fréquences
            
        Returns:
            Valeur RSSI en dBm
        """
        if len(waterfall_data) == 0:
            return self.noise_floor
        
        # Si une plage de fréquences est spécifiée, la sélectionner
        if freq_range and len(waterfall_data) > 1:
            start_idx = max(0, min(int(freq_range[0] * len(waterfall_data)), len(waterfall_data) - 1))
            end_idx = max(0, min(int(freq_range[1] * len(waterfall_data)), len(waterfall_data)))
            data = waterfall_data[start_idx:end_idx]
        else:
            data = waterfall_data
        
        # Les données waterfall sont généralement en dB, mais peuvent nécessiter un ajustement
        # Conversion en valeur linéaire pour les calculs
        samples = 10 ** (data / 10)
        
        # Calcul selon la méthode choisie
        if self.method == RSSIMethod.PEAK:
            # Valeur de crête
            raw_rssi = np.max(samples)
        elif self.method == RSSIMethod.MEAN:
            # Moyenne
            raw_rssi = np.mean(samples)
        elif self.method == RSSIMethod.RMS:
            # Root Mean Square (valeur efficace)
            raw_rssi = np.sqrt(np.mean(np.square(samples)))
        elif self.method == RSSIMethod.MEDIAN:
            # Médiane
            raw_rssi = np.median(samples)
        elif self.method == RSSIMethod.WEIGHTED:
            # Moyenne pondérée
            peak = np.max(samples)
            rms = np.sqrt(np.mean(np.square(samples)))
            mean = np.mean(samples)
            # Pondération: 40% peak, 40% RMS, 20% mean pour waterfall
            raw_rssi = 0.4 * peak + 0.4 * rms + 0.2 * mean
        else:
            # Par défaut: moyenne
            raw_rssi = np.mean(samples)
        
        # Reconversion en dBm
        rssi_dbm = 10 * np.log10(raw_rssi)
        
        # Appliquer le facteur de calibration
        rssi_dbm = rssi_dbm * self.calibration_factor
        
        # Limiter à des valeurs raisonnables
        rssi_dbm = max(rssi_dbm, self.noise_floor)
        rssi_dbm = min(rssi_dbm, 20.0)  # dBm max typique pour un récepteur SDR
        
        # Appliquer le lissage et mettre à jour l'historique
        smoothed_rssi = self._smooth_rssi(rssi_dbm)
        
        return smoothed_rssi
    
    def _smooth_rssi(self, rssi: float) -> float:
        """
        Applique un lissage temporel au RSSI.
        
        Args:
            rssi: Valeur RSSI brute
            
        Returns:
            Valeur RSSI lissée
        """
        # Ajouter à l'historique
        self.history.append(rssi)
        
        # Lissage exponentiel: new = alpha * current + (1-alpha) * previous
        if self.last_rssi == 0.0:
            smoothed = rssi  # Premier échantillon
        else:
            smoothed = self.smoothing_factor * rssi + (1 - self.smoothing_factor) * self.last_rssi
        
        # Mettre à jour la dernière valeur
        self.last_rssi = smoothed
        
        return smoothed
    
    def get_average_rssi(self) -> float:
        """
        Retourne la moyenne des valeurs RSSI dans la fenêtre d'historique.
        
        Returns:
            Moyenne des valeurs RSSI
        """
        if not self.history:
            return self.noise_floor
        
        return sum(self.history) / len(self.history)
    
    def get_peak_rssi(self) -> float:
        """
        Retourne la valeur maximale de RSSI dans la fenêtre d'historique.
        
        Returns:
            Valeur maximale de RSSI
        """
        if not self.history:
            return self.noise_floor
        
        return max(self.history)
    
    def calibrate(self, reference_rssi: float, measured_rssi: float) -> None:
        """
        Calibre le calculateur RSSI par rapport à une valeur de référence.
        
        Args:
            reference_rssi: Valeur RSSI de référence (réelle)
            measured_rssi: Valeur RSSI mesurée (non calibrée)
        """
        if measured_rssi == 0:
            logger.warning("Impossible de calibrer: mesure RSSI nulle")
            return
        
        # Calcul du facteur de calibration
        self.calibration_factor = reference_rssi / measured_rssi
        logger.info(f"Facteur de calibration RSSI: {self.calibration_factor}")
    
    def set_noise_floor(self, noise_floor: float) -> None:
        """
        Définit le niveau de bruit de fond.
        
        Args:
            noise_floor: Niveau de bruit en dBm
        """
        self.noise_floor = noise_floor
        logger.info(f"Niveau de bruit défini à {noise_floor} dBm")
    
    def reset(self) -> None:
        """
        Réinitialise le calculateur RSSI.
        """
        self.last_rssi = 0.0
        self.history.clear()
        logger.debug("Réinitialisation du calculateur RSSI")


class RSSIManager:
    """
    Gestionnaire de RSSI pour plusieurs récepteurs.
    
    Cette classe permet de gérer et calibrer les mesures RSSI
    entre différents récepteurs SDR.
    """
    
    def __init__(self):
        """
        Initialise le gestionnaire RSSI.
        """
        self.computers: Dict[str, RSSIComputer] = {}
        self.reference_receiver = None
        self.last_update = {}
        self.propagation_model = PropagationModel()
    
    def add_receiver(self, 
                    name: str, 
                    method: RSSIMethod = RSSIMethod.RMS,
                    window_size: int = 10,
                    smoothing_factor: float = 0.3) -> None:
        """
        Ajoute un récepteur au gestionnaire.
        
        Args:
            name: Nom du récepteur
            method: Méthode de calcul du RSSI
            window_size: Taille de la fenêtre de lissage
            smoothing_factor: Facteur de lissage exponentiel
        """
        self.computers[name] = RSSIComputer(
            window_size=window_size,
            method=method,
            smoothing_factor=smoothing_factor
        )
        self.last_update[name] = 0
        logger.info(f"Récepteur {name} ajouté au gestionnaire RSSI")
        
        # Définir comme référence si c'est le premier
        if self.reference_receiver is None:
            self.reference_receiver = name
            logger.info(f"Récepteur {name} défini comme référence pour la calibration RSSI")
    
    def remove_receiver(self, name: str) -> bool:
        """
        Supprime un récepteur du gestionnaire.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si la suppression a réussi, False sinon
        """
        if name not in self.computers:
            logger.warning(f"Impossible de supprimer: le récepteur {name} n'existe pas")
            return False
        
        del self.computers[name]
        del self.last_update[name]
        
        # Réinitialiser la référence si nécessaire
        if self.reference_receiver == name:
            if self.computers:
                self.reference_receiver = next(iter(self.computers.keys()))
                logger.info(f"Nouveau récepteur de référence: {self.reference_receiver}")
            else:
                self.reference_receiver = None
                logger.info("Aucun récepteur de référence défini")
        
        logger.info(f"Récepteur {name} supprimé du gestionnaire RSSI")
        return True
    
    def set_reference_receiver(self, name: str) -> bool:
        """
        Définit le récepteur de référence pour la calibration.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si le changement a réussi, False sinon
        """
        if name not in self.computers:
            logger.warning(f"Impossible de définir la référence: le récepteur {name} n'existe pas")
            return False
        
        self.reference_receiver = name
        logger.info(f"Récepteur {name} défini comme référence pour la calibration RSSI")
        return True
    
    def update_rssi_audio(self, name: str, audio_samples: np.ndarray) -> float:
        """
        Met à jour et retourne le RSSI à partir de données audio pour un récepteur.
        
        Args:
            name: Nom du récepteur
            audio_samples: Données audio
            
        Returns:
            Valeur RSSI en dBm
        """
        if name not in self.computers:
            logger.warning(f"Le récepteur {name} n'existe pas")
            return -120.0
        
        rssi = self.computers[name].compute_from_audio(audio_samples)
        self.last_update[name] = time.time()
        return rssi
    
    def update_rssi_waterfall(self, name: str, waterfall_data: np.ndarray,
                             freq_range: Optional[Tuple[int, int]] = None) -> float:
        """
        Met à jour et retourne le RSSI à partir de données waterfall pour un récepteur.
        
        Args:
            name: Nom du récepteur
            waterfall_data: Données waterfall
            freq_range: Plage de fréquences (optionnel)
            
        Returns:
            Valeur RSSI en dBm
        """
        if name not in self.computers:
            logger.warning(f"Le récepteur {name} n'existe pas")
            return -120.0
        
        rssi = self.computers[name].compute_from_waterfall(waterfall_data, freq_range)
        self.last_update[name] = time.time()
        return rssi
    
    def get_rssi(self, name: str) -> float:
        """
        Retourne la dernière valeur RSSI pour un récepteur.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            Dernière valeur RSSI en dBm
        """
        if name not in self.computers:
            logger.warning(f"Le récepteur {name} n'existe pas")
            return -120.0
        
        return self.computers[name].last_rssi
    
    def calibrate_receivers(self, known_signal_strength: Optional[float] = None) -> None:
        """
        Calibre tous les récepteurs par rapport au récepteur de référence.
        
        Si known_signal_strength est fourni, le récepteur de référence est calibré
        à cette valeur absolue d'abord.
        
        Args:
            known_signal_strength: Force du signal connue pour le récepteur de référence (optionnel)
        """
        if self.reference_receiver is None:
            logger.warning("Impossible de calibrer: aucun récepteur de référence défini")
            return
        
        # Calibrer le récepteur de référence si une valeur absolue est fournie
        if known_signal_strength is not None:
            ref_computer = self.computers[self.reference_receiver]
            ref_rssi = ref_computer.last_rssi
            ref_computer.calibrate(known_signal_strength, ref_rssi)
            logger.info(f"Récepteur de référence {self.reference_receiver} calibré à {known_signal_strength} dBm")
        
        # Calibrer tous les autres récepteurs par rapport à la référence
        ref_rssi = self.computers[self.reference_receiver].last_rssi
        
        for name, computer in self.computers.items():
            if name != self.reference_receiver:
                computer.calibrate(ref_rssi, computer.last_rssi)
                logger.info(f"Récepteur {name} calibré par rapport à la référence")
    
    def get_all_rssi(self) -> Dict[str, float]:
        """
        Retourne toutes les valeurs RSSI actuelles.
        
        Returns:
            Dictionnaire {nom_récepteur: valeur_rssi}
        """
        return {name: computer.last_rssi for name, computer in self.computers.items()}
    
    def estimate_signal_strength(self, frequency: int, distance: float) -> float:
        """
        Estime la force du signal à une distance donnée pour une fréquence.
        
        Utilise un modèle de propagation radio pour estimer l'atténuation.
        
        Args:
            frequency: Fréquence en Hz
            distance: Distance en km
            
        Returns:
            Force du signal estimée en dBm
        """
        return self.propagation_model.estimate_signal_strength(frequency, distance)


class PropagationModel:
    """
    Modèle de propagation pour estimer l'atténuation du signal radio.
    
    Implémente plusieurs modèles de propagation adaptés à différentes
    bandes de fréquences.
    """
    
    def __init__(self):
        """
        Initialise le modèle de propagation.
        """
        # Facteurs d'atténuation pour différentes bandes (en dB/km)
        self.band_factors = {
            # LF (30-300 kHz)
            "LF": 0.2,
            # MF (300-3000 kHz) - Ondes moyennes
            "MF": 0.5,
            # HF (3-30 MHz) - Ondes courtes
            "HF": 1.0,
            # VHF (30-300 MHz)
            "VHF": 2.0,
            # UHF (300-3000 MHz)
            "UHF": 3.0
        }
    
    def get_band(self, frequency: int) -> str:
        """
        Détermine la bande de fréquence.
        
        Args:
            frequency: Fréquence en Hz
            
        Returns:
            Nom de la bande
        """
        freq_khz = frequency / 1000
        
        if freq_khz < 30:
            return "VLF"  # Very Low Frequency
        elif 30 <= freq_khz < 300:
            return "LF"   # Low Frequency
        elif 300 <= freq_khz < 3000:
            return "MF"   # Medium Frequency
        elif 3000 <= freq_khz < 30000:
            return "HF"   # High Frequency
        elif 30000 <= freq_khz < 300000:
            return "VHF"  # Very High Frequency
        else:
            return "UHF"  # Ultra High Frequency
    
    def free_space_path_loss(self, frequency: int, distance: float) -> float:
        """
        Calcule l'atténuation en espace libre.
        
        Args:
            frequency: Fréquence en Hz
            distance: Distance en km
            
        Returns:
            Atténuation en dB
        """
        # Formule de Friis: FSPL = 20*log10(d) + 20*log10(f) + 32.44
        # d en km, f en MHz
        freq_mhz = frequency / 1_000_000
        return 20 * np.log10(distance) + 20 * np.log10(freq_mhz) + 32.44
    
    def estimate_signal_strength(self, frequency: int, distance: float, 
                                transmitter_power: float = 100.0) -> float:
        """
        Estime la force du signal à une distance donnée pour une fréquence.
        
        Args:
            frequency: Fréquence en Hz
            distance: Distance en km
            transmitter_power: Puissance de l'émetteur en W
            
        Returns:
            Force du signal estimée en dBm
        """
        if distance <= 0:
            return 30.0  # Maximum théorique (30 dBm = 1W)
        
        # Convertir la puissance de l'émetteur en dBm
        tx_power_dbm = 10 * np.log10(transmitter_power) + 30
        
        # Calculer l'atténuation en espace libre
        path_loss = self.free_space_path_loss(frequency, distance)
        
        # Appliquer des facteurs de correction selon la bande
        band = self.get_band(frequency)
        band_factor = self.band_factors.get(band, 1.0)
        
        # Ajustement selon la bande (simplifié)
        additional_loss = distance * band_factor
        
        # Puissance reçue = Puissance émise - Pertes
        rx_power = tx_power_dbm - path_loss - additional_loss
        
        # Limiter à des valeurs raisonnables
        rx_power = max(rx_power, -120.0)  # Seuil de bruit typique
        rx_power = min(rx_power, 30.0)    # Maximum théorique
        
        return rx_power 