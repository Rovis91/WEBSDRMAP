"""
Module de traitement du signal optimisé.

Ce module fournit des versions optimisées des fonctions de traitement du signal
en utilisant le multiprocessing et d'autres techniques d'optimisation pour
améliorer les performances.
"""

import functools
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, List, Tuple, Dict, Any, Optional, Union

from src.utils.logger import get_logger
from src.utils.performance import process_pool, timeit

# Configuration du logger
logger = get_logger(__name__)


def parallelize_processing(func: Callable) -> Callable:
    """
    Décorateur pour paralléliser une fonction de traitement du signal.
    
    Ce décorateur divise les données d'entrée en chunks et les traite en parallèle
    en utilisant le pool de processus configuré.
    
    Args:
        func: Fonction de traitement à paralléliser
        
    Returns:
        Fonction parallélisée
    """
    @functools.wraps(func)
    def wrapper(data, *args, **kwargs):
        # Si les données sont trop petites, pas besoin de paralléliser
        if isinstance(data, np.ndarray) and data.size < 10000:
            return func(data, *args, **kwargs)
        
        # Obtenir le nombre de workers
        num_workers = process_pool.max_workers
        
        # Diviser les données en chunks
        if isinstance(data, np.ndarray):
            chunks = np.array_split(data, num_workers)
        elif isinstance(data, list):
            chunk_size = max(1, len(data) // num_workers)
            chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        else:
            # Si on ne peut pas diviser les données, exécuter normalement
            return func(data, *args, **kwargs)
        
        # S'assurer que le pool est démarré
        process_pool.start()
        
        # Soumettre les tâches au pool
        futures = []
        for chunk in chunks:
            future = process_pool.submit(func, chunk, *args, **kwargs)
            futures.append(future)
        
        # Récupérer les résultats
        results = [future.result() for future in futures]
        
        # Fusionner les résultats
        if isinstance(results[0], np.ndarray):
            if results[0].ndim == 1:
                return np.concatenate(results)
            else:
                return np.vstack(results)
        elif isinstance(results[0], list):
            merged = []
            for result in results:
                merged.extend(result)
            return merged
        else:
            # Si on ne peut pas fusionner les résultats, renvoyer la liste
            return results
    
    return wrapper


@parallelize_processing
@timeit
def fft_process(samples: np.ndarray, window: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Calcule la FFT (Fast Fourier Transform) d'un signal.
    
    Version optimisée utilisant le multiprocessing pour les grands tableaux.
    
    Args:
        samples: Échantillons du signal
        window: Fenêtre à appliquer avant la FFT (None = fenêtre rectangulaire)
        
    Returns:
        Spectre de puissance en dB
    """
    # Appliquer la fenêtre si fournie
    if window is not None:
        if len(window) != len(samples):
            window = np.hanning(len(samples))
        windowed_samples = samples * window
    else:
        windowed_samples = samples
    
    # Calcul de la FFT
    fft_result = np.fft.fft(windowed_samples)
    fft_result = np.fft.fftshift(fft_result)
    
    # Calcul du spectre de puissance en dB
    power_spectrum = 10 * np.log10(np.abs(fft_result)**2 + 1e-10)
    
    return power_spectrum


@parallelize_processing
@timeit
def filter_signal(samples: np.ndarray, filter_coeffs: np.ndarray) -> np.ndarray:
    """
    Applique un filtre à un signal.
    
    Version optimisée utilisant le multiprocessing pour les grands tableaux.
    
    Args:
        samples: Échantillons du signal
        filter_coeffs: Coefficients du filtre
        
    Returns:
        Signal filtré
    """
    # Appliquer le filtre par convolution
    filtered = np.convolve(samples, filter_coeffs, mode='same')
    
    return filtered


@parallelize_processing
@timeit
def detect_peaks(spectrum: np.ndarray, threshold: float = 0.7, min_distance: int = 10) -> List[Tuple[int, float]]:
    """
    Détecte les pics dans un spectre.
    
    Version optimisée utilisant le multiprocessing pour les grands tableaux.
    
    Args:
        spectrum: Spectre de puissance
        threshold: Seuil relatif (0-1) par rapport au maximum
        min_distance: Distance minimale entre les pics
        
    Returns:
        Liste de tuples (position, valeur) des pics détectés
    """
    # Normaliser le spectre entre 0 et 1
    norm_spectrum = (spectrum - np.min(spectrum)) / (np.max(spectrum) - np.min(spectrum))
    
    # Trouver les pics qui dépassent le seuil
    peaks = []
    for i in range(1, len(norm_spectrum) - 1):
        if (norm_spectrum[i] > threshold and
            norm_spectrum[i] > norm_spectrum[i-1] and
            norm_spectrum[i] > norm_spectrum[i+1]):
            peaks.append((i, spectrum[i]))
    
    # Filtrer les pics trop proches
    if not peaks:
        return []
    
    peaks.sort(key=lambda x: x[1], reverse=True)
    filtered_peaks = [peaks[0]]
    
    for peak in peaks[1:]:
        # Vérifier si le pic est assez éloigné des pics déjà sélectionnés
        if all(abs(peak[0] - p[0]) >= min_distance for p in filtered_peaks):
            filtered_peaks.append(peak)
    
    return filtered_peaks


@parallelize_processing
@timeit
def calculate_rssi(iq_samples: np.ndarray, window_size: int = 1024) -> float:
    """
    Calcule le RSSI (Received Signal Strength Indicator) à partir d'échantillons I/Q.
    
    Version optimisée utilisant le multiprocessing pour les grands tableaux.
    
    Args:
        iq_samples: Échantillons I/Q complexes
        window_size: Taille de la fenêtre pour le moyennage
        
    Returns:
        RSSI en dBm
    """
    # Calculer la puissance du signal
    power = np.abs(iq_samples)**2
    
    # Moyenner sur la fenêtre
    if len(power) > window_size:
        # Diviser en fenêtres et moyenner
        num_windows = len(power) // window_size
        power_windowed = power[:num_windows * window_size].reshape(num_windows, window_size)
        avg_power = np.mean(power_windowed, axis=1)
        # Moyenne globale
        avg_power = np.mean(avg_power)
    else:
        # Moyenne directe si moins d'échantillons que la taille de fenêtre
        avg_power = np.mean(power)
    
    # Convertir en dBm (facteur de calibration à ajuster)
    rssi_dbm = 10 * np.log10(avg_power) + 30  # +30 est un facteur de calibration arbitraire
    
    return rssi_dbm


@parallelize_processing
@timeit
def generate_waterfall_line(spectrum: np.ndarray, min_db: float = -120, max_db: float = -30) -> np.ndarray:
    """
    Génère une ligne de waterfall à partir d'un spectre.
    
    Version optimisée utilisant le multiprocessing pour les grands tableaux.
    
    Args:
        spectrum: Spectre de puissance en dB
        min_db: Valeur minimum en dB pour l'échelle
        max_db: Valeur maximum en dB pour l'échelle
        
    Returns:
        Ligne de waterfall (valeurs 0-255)
    """
    # Limiter les valeurs à la plage min_db - max_db
    clipped = np.clip(spectrum, min_db, max_db)
    
    # Normaliser à 0-255
    db_range = max_db - min_db
    normalized = ((clipped - min_db) / db_range) * 255
    
    return normalized.astype(np.uint8)


@parallelize_processing
@timeit
def process_audio_samples(raw_samples: np.ndarray, is_iq: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """
    Traite les échantillons audio bruts.
    
    Version optimisée utilisant le multiprocessing pour les grands tableaux.
    
    Args:
        raw_samples: Échantillons bruts
        is_iq: True si les données sont I/Q, False sinon
        
    Returns:
        Échantillons traités (tableau simple ou tuple de I et Q)
    """
    # Convertir en float et normaliser
    samples = raw_samples.astype(np.float32) / 32768.0
    
    if is_iq:
        # Séparer les composantes I et Q
        i_samples = samples[0::2]
        q_samples = samples[1::2]
        return i_samples, q_samples
    else:
        return samples


class OptimizedSignalProcessor:
    """
    Processeur de signal optimisé.
    
    Cette classe fournit des méthodes optimisées pour traiter les signaux
    en utilisant le multiprocessing et d'autres techniques d'optimisation.
    """
    
    def __init__(self, sample_rate: int = 12000, fft_size: int = 1024):
        """
        Initialise le processeur de signal optimisé.
        
        Args:
            sample_rate: Taux d'échantillonnage en Hz
            fft_size: Taille de la FFT
        """
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.window = np.hanning(fft_size)
        
        # Démarrer le pool de processus
        process_pool.start()
    
    @timeit
    def process_spectrum(self, samples: np.ndarray) -> np.ndarray:
        """
        Calcule le spectre de puissance d'un signal.
        
        Args:
            samples: Échantillons du signal
            
        Returns:
            Spectre de puissance en dB
        """
        # Adapter la taille des données à la FFT
        if len(samples) > self.fft_size:
            # Prendre les échantillons les plus récents
            samples = samples[-self.fft_size:]
        elif len(samples) < self.fft_size:
            # Compléter avec des zéros
            padding = np.zeros(self.fft_size - len(samples))
            samples = np.concatenate([samples, padding])
        
        # Calculer la FFT
        return fft_process(samples, self.window)
    
    @timeit
    def process_waterfall_data(self, samples_buffer: List[np.ndarray]) -> np.ndarray:
        """
        Traite les données pour générer une image waterfall.
        
        Args:
            samples_buffer: Liste de tableaux d'échantillons
            
        Returns:
            Image waterfall (tableau 2D)
        """
        # Calculer le spectre pour chaque bloc d'échantillons
        spectra = []
        for samples in samples_buffer:
            spectrum = self.process_spectrum(samples)
            spectra.append(spectrum)
        
        # Convertir les spectres en lignes de waterfall
        waterfall_lines = []
        for spectrum in spectra:
            line = generate_waterfall_line(spectrum)
            waterfall_lines.append(line)
        
        # Construire l'image waterfall
        return np.array(waterfall_lines)
    
    @timeit
    def detect_signals(self, spectrum: np.ndarray, threshold_db: float = -80) -> List[Tuple[float, float]]:
        """
        Détecte les signaux dans un spectre.
        
        Args:
            spectrum: Spectre de puissance en dB
            threshold_db: Seuil de détection en dB
            
        Returns:
            Liste de tuples (fréquence, puissance) des signaux détectés
        """
        # Calculer le seuil relatif
        max_power = np.max(spectrum)
        relative_threshold = (threshold_db - np.min(spectrum)) / (max_power - np.min(spectrum))
        
        # Détecter les pics
        peaks = detect_peaks(spectrum, threshold=relative_threshold)
        
        # Convertir les positions en fréquences
        freq_resolution = self.sample_rate / self.fft_size
        signals = []
        
        for pos, power in peaks:
            # Calculer la fréquence relative à la fréquence centrale
            relative_freq = (pos - self.fft_size/2) * freq_resolution
            signals.append((relative_freq, power))
        
        return signals
    
    def cleanup(self):
        """
        Nettoie les ressources utilisées par le processeur.
        """
        process_pool.stop() 