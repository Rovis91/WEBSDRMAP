"""
Module de détection de signaux.

Ce module permet de:
- Détecter des signaux par seuil sur le spectre ou le RSSI
- Filtrer les faux positifs basés sur la durée et stabilité
- Classifier les types de signaux (AM, FM, numérique, etc.)
- Émettre des alertes configurables
"""

import numpy as np
import time
from typing import Dict, List, Tuple, Optional, Set, Deque, Any
from collections import deque
from enum import Enum
from dataclasses import dataclass
import logging

from src.utils.logger import get_logger
from src.signal_processing.rssi import RSSIMethod, RSSIComputer
from src.signal_processing.optimized_processing import detect_peaks, parallelize_processing

# Configuration du logger
logger = get_logger(__name__)


class SignalType(Enum):
    """Types de signaux détectables."""
    UNKNOWN = "unknown"  # Type inconnu
    AM = "am"            # Modulation d'amplitude
    FM = "fm"            # Modulation de fréquence
    SSB = "ssb"          # Single Side Band (BLU)
    CW = "cw"            # Continuous Wave (Morse)
    DIGITAL = "digital"  # Signal numérique


@dataclass
class SignalDetection:
    """Classe représentant un signal détecté."""
    frequency: float  # Fréquence centrale en Hz
    bandwidth: float  # Largeur de bande en Hz
    power: float      # Puissance en dBm
    snr: float        # Rapport signal/bruit en dB
    signal_type: SignalType  # Type de signal
    confidence: float  # Indice de confiance (0-1)
    timestamp: float  # Timestamp de détection
    duration: float = 0.0  # Durée de détection en secondes
    is_active: bool = True  # Signal actif ou non


class SignalDetector:
    """
    Classe de détection de signaux.
    
    Cette classe permet de détecter des signaux dans un spectre ou 
    à partir de données RSSI, avec filtrage des faux positifs.
    """
    
    def __init__(self, 
                threshold_db: float = -80.0,
                min_snr_db: float = 10.0,
                min_duration_sec: float = 2.0,
                max_inactive_sec: float = 5.0,
                frequency_tolerance_hz: float = 100.0):
        """
        Initialise le détecteur de signaux.
        
        Args:
            threshold_db: Seuil de détection en dB
            min_snr_db: Rapport signal/bruit minimum pour validation
            min_duration_sec: Durée minimale pour considérer un signal valide
            max_inactive_sec: Durée maximale d'inactivité avant de supprimer un signal
            frequency_tolerance_hz: Tolérance en Hz pour considérer qu'il s'agit du même signal
        """
        self.threshold_db = threshold_db
        self.min_snr_db = min_snr_db
        self.min_duration_sec = min_duration_sec
        self.max_inactive_sec = max_inactive_sec
        self.frequency_tolerance_hz = frequency_tolerance_hz
        
        # Liste des signaux détectés
        self.signals: Dict[int, SignalDetection] = {}
        self.next_signal_id = 1
        
        # Historique de détection pour filtrage des faux positifs
        self.detection_history: Dict[float, List[float]] = {}  # {freq: [timestamps]}
        
        # Statistiques de détection
        self.total_detections = 0
        self.false_positives = 0
        self.active_signals = 0
        
        # Référence de bruit
        self.noise_floor = -120.0  # dBm
        self.noise_history: Deque[float] = deque(maxlen=50)  # Historique des mesures de bruit
        
        # État interne
        self.last_detection_time = 0.0
        
        logger.info(f"Détecteur de signaux initialisé avec seuil: {threshold_db} dB, SNR min: {min_snr_db} dB")
    
    def detect_from_spectrum(self, 
                            spectrum: np.ndarray, 
                            frequencies: np.ndarray,
                            timestamp: Optional[float] = None) -> List[SignalDetection]:
        """
        Détecte les signaux dans un spectre.
        
        Args:
            spectrum: Tableau NumPy du spectre de puissance en dB
            frequencies: Tableau NumPy des fréquences correspondantes en Hz
            timestamp: Timestamp de la détection (None = utiliser time.time())
            
        Returns:
            Liste des signaux détectés
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.last_detection_time = timestamp
        
        # Estimer le niveau de bruit (10% des valeurs les plus basses)
        sorted_spectrum = np.sort(spectrum)
        noise_level = np.mean(sorted_spectrum[:int(len(sorted_spectrum) * 0.1)])
        self.noise_history.append(noise_level)
        self.noise_floor = np.mean(self.noise_history) if len(self.noise_history) > 0 else noise_level
        
        # Détecter les pics dans le spectre
        peaks = detect_peaks(spectrum, threshold=(self.threshold_db - self.noise_floor) / (np.max(spectrum) - self.noise_floor), 
                          min_distance=max(1, int(len(spectrum) / 200)))
        
        new_detections = []
        
        for idx, power in peaks:
            if idx >= len(frequencies):
                continue
                
            frequency = frequencies[idx]
            
            # Calculer le SNR
            snr = power - self.noise_floor
            
            if snr < self.min_snr_db:
                continue
            
            # Estimer la largeur de bande
            bandwidth = self._estimate_bandwidth(spectrum, idx, frequencies)
            
            # Classifier le type de signal
            signal_type, confidence = self._classify_signal(spectrum, idx, bandwidth, frequencies)
            
            # Créer ou mettre à jour la détection
            detection = self._process_detection(frequency, bandwidth, power, snr, 
                                            signal_type, confidence, timestamp)
            
            if detection:
                new_detections.append(detection)
        
        # Mettre à jour l'état des signaux existants
        self._update_signals_state(timestamp)
        
        return new_detections
    
    def detect_from_rssi(self, 
                        rssi_values: Dict[str, float],
                        frequency: float,
                        bandwidth: float,
                        timestamp: Optional[float] = None) -> Optional[SignalDetection]:
        """
        Détecte un signal à partir de mesures RSSI de plusieurs récepteurs.
        
        Args:
            rssi_values: Dictionnaire {nom_récepteur: valeur_rssi}
            frequency: Fréquence d'écoute en Hz
            bandwidth: Largeur de bande en Hz
            timestamp: Timestamp de la détection (None = utiliser time.time())
            
        Returns:
            Signal détecté ou None si pas de détection
        """
        if not rssi_values:
            return None
            
        if timestamp is None:
            timestamp = time.time()
            
        self.last_detection_time = timestamp
        
        # Calculer la puissance moyenne
        power = sum(rssi_values.values()) / len(rssi_values)
        
        # Ignorer si en dessous du seuil
        if power < self.threshold_db:
            return None
        
        # Estimer le SNR (en utilisant l'écart-type comme indicateur)
        rssi_std = np.std(list(rssi_values.values())) if len(rssi_values) > 1 else 0
        snr = power - self.noise_floor
        
        if snr < self.min_snr_db:
            return None
        
        # Classifier le type de signal (plus difficile sans spectre)
        # Par défaut, type inconnu avec confiance moyenne
        signal_type = SignalType.UNKNOWN
        confidence = 0.5
        
        # Créer ou mettre à jour la détection
        detection = self._process_detection(frequency, bandwidth, power, snr, 
                                       signal_type, confidence, timestamp)
        
        # Mettre à jour l'état des signaux existants
        self._update_signals_state(timestamp)
        
        return detection
    
    def _process_detection(self, 
                         frequency: float, 
                         bandwidth: float,
                         power: float, 
                         snr: float,
                         signal_type: SignalType, 
                         confidence: float,
                         timestamp: float) -> Optional[SignalDetection]:
        """
        Traite une détection pour filtrer les faux positifs et suivre les signaux.
        
        Args:
            frequency: Fréquence du signal en Hz
            bandwidth: Largeur de bande en Hz
            power: Puissance en dBm
            snr: Rapport signal/bruit en dB
            signal_type: Type de signal détecté
            confidence: Indice de confiance (0-1)
            timestamp: Timestamp de la détection
            
        Returns:
            SignalDetection ou None si rejeté
        """
        # Incrémenter le compteur total de détections
        self.total_detections += 1
        
        # Vérifier si c'est un signal existant
        existing_signal_id = self._find_existing_signal(frequency)
        
        if existing_signal_id:
            # Mettre à jour le signal existant
            signal = self.signals[existing_signal_id]
            signal.power = power
            signal.snr = snr
            signal.is_active = True
            signal.duration = timestamp - signal.timestamp
            
            # Mise à jour des attributs avec moyenne mobile
            alpha = 0.3  # Facteur de lissage
            signal.frequency = (1-alpha) * signal.frequency + alpha * frequency
            signal.bandwidth = (1-alpha) * signal.bandwidth + alpha * bandwidth
            
            # Si le nouveau type a une meilleure confiance, le mettre à jour
            if confidence > signal.confidence:
                signal.signal_type = signal_type
                signal.confidence = confidence
            
            return signal
        else:
            # Ajouter à l'historique de détection pour cette fréquence
            freq_key = round(frequency / self.frequency_tolerance_hz) * self.frequency_tolerance_hz
            if freq_key not in self.detection_history:
                self.detection_history[freq_key] = []
            self.detection_history[freq_key].append(timestamp)
            
            # Filtrer l'historique (garder seulement les dernières N secondes)
            cutoff_time = timestamp - 30  # 30 secondes d'historique
            self.detection_history[freq_key] = [t for t in self.detection_history[freq_key] if t > cutoff_time]
            
            # Vérifier le critère de durée minimale (multiples détections)
            if len(self.detection_history[freq_key]) >= 3:
                # Créer un nouveau signal
                signal = SignalDetection(
                    frequency=frequency,
                    bandwidth=bandwidth,
                    power=power,
                    snr=snr,
                    signal_type=signal_type,
                    confidence=confidence,
                    timestamp=self.detection_history[freq_key][0],  # Premier timestamp de détection
                    duration=timestamp - self.detection_history[freq_key][0],
                    is_active=True
                )
                
                # Ajouter à la liste des signaux détectés
                self.signals[self.next_signal_id] = signal
                self.next_signal_id += 1
                self.active_signals += 1
                
                logger.info(f"Nouveau signal détecté: {frequency/1e6:.3f} MHz, "
                          f"type={signal_type.value}, SNR={snr:.1f} dB")
                
                return signal
            else:
                # Pas assez de détections pour confirmer - potentiel faux positif
                self.false_positives += 1
                return None
    
    def _update_signals_state(self, current_time: float) -> None:
        """
        Met à jour l'état des signaux existants et supprime les inactifs.
        
        Args:
            current_time: Timestamp actuel
        """
        signals_to_remove = []
        
        for signal_id, signal in self.signals.items():
            # Si le signal n'a pas été mis à jour, le marquer comme inactif
            if signal.is_active and current_time - self.last_detection_time > 1.0:
                signal.is_active = False
                self.active_signals -= 1
                logger.debug(f"Signal {signal.frequency/1e6:.3f} MHz marqué inactif")
            
            # Si inactif depuis trop longtemps, le supprimer
            if not signal.is_active and current_time - (signal.timestamp + signal.duration) > self.max_inactive_sec:
                signals_to_remove.append(signal_id)
                logger.debug(f"Signal {signal.frequency/1e6:.3f} MHz supprimé après "
                           f"{current_time - (signal.timestamp + signal.duration):.1f}s d'inactivité")
        
        # Supprimer les signaux inactifs
        for signal_id in signals_to_remove:
            del self.signals[signal_id]
    
    def _find_existing_signal(self, frequency: float) -> Optional[int]:
        """
        Trouve un signal existant à la fréquence donnée.
        
        Args:
            frequency: Fréquence en Hz
            
        Returns:
            ID du signal ou None si non trouvé
        """
        for signal_id, signal in self.signals.items():
            if abs(signal.frequency - frequency) <= self.frequency_tolerance_hz:
                return signal_id
        return None
    
    def _estimate_bandwidth(self, spectrum: np.ndarray, peak_idx: int, frequencies: np.ndarray) -> float:
        """
        Estime la largeur de bande d'un signal détecté.
        
        Args:
            spectrum: Tableau du spectre
            peak_idx: Index du pic dans le spectre
            frequencies: Tableau des fréquences
            
        Returns:
            Largeur de bande en Hz
        """
        # Niveau à -3dB par rapport au pic
        peak_power = spectrum[peak_idx]
        threshold_power = peak_power - 3
        
        # Recherche des points à -3dB de chaque côté
        left_idx = peak_idx
        right_idx = peak_idx
        
        for i in range(peak_idx - 1, 0, -1):
            if spectrum[i] <= threshold_power:
                left_idx = i
                break
                
        for i in range(peak_idx + 1, len(spectrum) - 1):
            if spectrum[i] <= threshold_power:
                right_idx = i
                break
        
        # Calcul de la largeur de bande
        if left_idx < right_idx and left_idx < len(frequencies) and right_idx < len(frequencies):
            bandwidth = frequencies[right_idx] - frequencies[left_idx]
            return max(bandwidth, 10.0)  # Minimum 10 Hz pour éviter les valeurs trop faibles
        else:
            # Valeur par défaut si estimation impossible
            return 100.0
    
    def _classify_signal(self, 
                       spectrum: np.ndarray, 
                       peak_idx: int, 
                       bandwidth: float, 
                       frequencies: np.ndarray) -> Tuple[SignalType, float]:
        """
        Classifie le type de signal en fonction de ses caractéristiques.
        
        Args:
            spectrum: Tableau du spectre
            peak_idx: Index du pic dans le spectre
            bandwidth: Largeur de bande estimée en Hz
            frequencies: Tableau des fréquences
            
        Returns:
            Tuple (type_signal, confiance)
        """
        # Extraire la partie du spectre correspondant au signal
        left_idx = max(0, peak_idx - 20)
        right_idx = min(len(spectrum) - 1, peak_idx + 20)
        signal_spectrum = spectrum[left_idx:right_idx+1]
        
        # Caractéristiques du signal
        peak_power = spectrum[peak_idx]
        avg_power = np.mean(signal_spectrum)
        std_power = np.std(signal_spectrum)
        
        # Asymétrie (utile pour détecter SSB)
        left_power = np.mean(spectrum[max(0, peak_idx-10):peak_idx])
        right_power = np.mean(spectrum[peak_idx+1:min(len(spectrum), peak_idx+11)])
        asymmetry = abs(left_power - right_power)
        
        # Décision basée sur les caractéristiques
        if bandwidth < 50:
            # Signal très étroit, probablement CW
            signal_type = SignalType.CW
            confidence = 0.8
        elif bandwidth < 400 and asymmetry > 2:
            # Signal étroit avec asymétrie: probablement SSB
            signal_type = SignalType.SSB
            confidence = 0.7
        elif 2500 < bandwidth < 6000:
            # Signal de largeur moyenne: probablement AM
            signal_type = SignalType.AM
            confidence = 0.6
        elif 6000 < bandwidth < 20000:
            # Signal large: probablement FM
            signal_type = SignalType.FM
            confidence = 0.7
        elif std_power < 1.0 and bandwidth > 500:
            # Signal à spectre plat et relativement large: probablement numérique
            signal_type = SignalType.DIGITAL
            confidence = 0.6
        else:
            # Par défaut: type inconnu
            signal_type = SignalType.UNKNOWN
            confidence = 0.4
            
        logger.debug(f"Classification: {signal_type.value}, confiance: {confidence:.1f}, "
                   f"BW: {bandwidth:.0f}Hz, asymétrie: {asymmetry:.1f}")
        
        return signal_type, confidence
    
    def get_active_signals(self) -> List[SignalDetection]:
        """
        Retourne la liste des signaux actifs.
        
        Returns:
            Liste des signaux actifs
        """
        return [signal for signal in self.signals.values() if signal.is_active]
    
    def get_all_signals(self) -> List[SignalDetection]:
        """
        Retourne la liste de tous les signaux (actifs et inactifs).
        
        Returns:
            Liste de tous les signaux
        """
        return list(self.signals.values())
    
    def set_threshold(self, threshold_db: float) -> None:
        """
        Modifie le seuil de détection.
        
        Args:
            threshold_db: Nouveau seuil en dB
        """
        self.threshold_db = threshold_db
        logger.info(f"Seuil de détection modifié: {threshold_db} dB")
    
    def reset(self) -> None:
        """
        Réinitialise le détecteur (supprime tous les signaux).
        """
        self.signals.clear()
        self.detection_history.clear()
        self.active_signals = 0
        self.next_signal_id = 1
        logger.info("Détecteur réinitialisé")


class AlertManager:
    """
    Gestionnaire d'alertes pour les signaux détectés.
    
    Cette classe permet de configurer des règles d'alerte et
    de générer des notifications lorsque des signaux correspondent aux critères.
    """
    
    def __init__(self):
        """
        Initialise le gestionnaire d'alertes.
        """
        self.alert_rules: List[Dict[str, Any]] = []
        self.active_alerts: Dict[int, Dict[str, Any]] = {}  # {alert_id: alert_info}
        self.next_alert_id = 1
        self.callbacks: List[callable] = []
    
    def add_rule(self, 
                name: str,
                min_frequency: Optional[float] = None,
                max_frequency: Optional[float] = None,
                min_power: Optional[float] = None,
                signal_type: Optional[SignalType] = None,
                min_duration: Optional[float] = None) -> int:
        """
        Ajoute une règle d'alerte.
        
        Args:
            name: Nom de la règle
            min_frequency: Fréquence minimale (Hz)
            max_frequency: Fréquence maximale (Hz)
            min_power: Puissance minimale (dBm)
            signal_type: Type de signal
            min_duration: Durée minimale (secondes)
            
        Returns:
            ID de la règle
        """
        rule_id = len(self.alert_rules) + 1
        
        rule = {
            "id": rule_id,
            "name": name,
            "min_frequency": min_frequency,
            "max_frequency": max_frequency,
            "min_power": min_power,
            "signal_type": signal_type,
            "min_duration": min_duration,
            "active": True
        }
        
        self.alert_rules.append(rule)
        logger.info(f"Règle d'alerte ajoutée: {name}")
        
        return rule_id
    
    def remove_rule(self, rule_id: int) -> bool:
        """
        Supprime une règle d'alerte.
        
        Args:
            rule_id: ID de la règle
            
        Returns:
            True si supprimée, False sinon
        """
        for i, rule in enumerate(self.alert_rules):
            if rule["id"] == rule_id:
                self.alert_rules.pop(i)
                logger.info(f"Règle d'alerte supprimée: {rule['name']}")
                return True
        
        return False
    
    def check_signals(self, signals: List[SignalDetection]) -> List[Dict[str, Any]]:
        """
        Vérifie si des signaux correspondent aux règles d'alerte.
        
        Args:
            signals: Liste des signaux à vérifier
            
        Returns:
            Liste des alertes déclenchées
        """
        new_alerts = []
        
        for signal in signals:
            for rule in self.alert_rules:
                if not rule["active"]:
                    continue
                    
                # Vérifier tous les critères définis
                match = True
                
                if rule["min_frequency"] is not None and signal.frequency < rule["min_frequency"]:
                    match = False
                    
                if rule["max_frequency"] is not None and signal.frequency > rule["max_frequency"]:
                    match = False
                    
                if rule["min_power"] is not None and signal.power < rule["min_power"]:
                    match = False
                    
                if rule["signal_type"] is not None and signal.signal_type != rule["signal_type"]:
                    match = False
                    
                if rule["min_duration"] is not None and signal.duration < rule["min_duration"]:
                    match = False
                
                if match:
                    # Vérifier si cette alerte existe déjà
                    existing_alert = False
                    for alert in self.active_alerts.values():
                        if (alert["rule_id"] == rule["id"] and 
                            abs(alert["frequency"] - signal.frequency) <= 100):
                            existing_alert = True
                            # Mettre à jour l'alerte existante
                            alert["last_update"] = time.time()
                            break
                    
                    if not existing_alert:
                        # Créer une nouvelle alerte
                        alert = {
                            "id": self.next_alert_id,
                            "rule_id": rule["id"],
                            "rule_name": rule["name"],
                            "frequency": signal.frequency,
                            "power": signal.power,
                            "signal_type": signal.signal_type.value,
                            "timestamp": time.time(),
                            "last_update": time.time()
                        }
                        
                        self.active_alerts[self.next_alert_id] = alert
                        self.next_alert_id += 1
                        new_alerts.append(alert)
                        
                        logger.warning(f"ALERTE: {rule['name']} - "
                                     f"Signal {signal.frequency/1e6:.3f} MHz, "
                                     f"{signal.power:.1f} dBm, type={signal.signal_type.value}")
                        
                        # Appeler les callbacks
                        for callback in self.callbacks:
                            try:
                                callback(alert)
                            except Exception as e:
                                logger.error(f"Erreur dans callback d'alerte: {str(e)}")
        
        # Nettoyer les alertes inactives
        self._clean_inactive_alerts()
        
        return new_alerts
    
    def _clean_inactive_alerts(self, max_age_sec: float = 60.0) -> None:
        """
        Supprime les alertes inactives.
        
        Args:
            max_age_sec: Âge maximum en secondes
        """
        current_time = time.time()
        alerts_to_remove = []
        
        for alert_id, alert in self.active_alerts.items():
            if current_time - alert["last_update"] > max_age_sec:
                alerts_to_remove.append(alert_id)
        
        for alert_id in alerts_to_remove:
            del self.active_alerts[alert_id]
    
    def add_callback(self, callback: callable) -> None:
        """
        Ajoute une fonction de callback appelée lors d'une alerte.
        
        Args:
            callback: Fonction à appeler avec l'alerte en paramètre
        """
        self.callbacks.append(callback)
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des alertes actives.
        
        Returns:
            Liste des alertes actives
        """
        return list(self.active_alerts.values()) 