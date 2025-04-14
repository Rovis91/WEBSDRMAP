"""
Module waterfall.py pour le traitement et l'affichage des données de spectre.

Ce module implémente:
- La génération de spectrogrammes avec FFT configurable
- L'optimisation pour le traitement en temps réel
- Des options variées de coloration et d'échelle
- Le zoom et la sélection de plages de fréquences
- Des fonctions d'analyse spectrale

Fonctionnalités principales:
1. Génération de spectrogrammes à partir de données audio brutes
2. Configuration flexible des paramètres FFT (taille, type de fenêtre, chevauchement)
3. Multiples schémas de coloration pour différents usages
4. Sélection et zoom sur des plages de fréquences spécifiques
5. Optimisation automatique des performances pour le traitement en temps réel

Exemple d'utilisation:
```python
from src.signal_processing.waterfall import WaterfallConfig, WaterfallProcessor, ColorScheme

# Créer une configuration avec des paramètres personnalisés
config = WaterfallConfig(
    fft_size=2048,
    window_type="blackman",
    color_scheme=ColorScheme.RADIO,
    min_db=-110.0,
    max_db=-30.0,
    sample_rate=12000.0, 
    center_frequency=7100000.0
)

# Initialiser le processeur
processor = WaterfallProcessor(config)

# Traiter des données audio
audio_data = np.random.randn(12000)  # Exemple: 1 seconde à 12kHz
line = processor.process_audio_data(audio_data)

# Zoomer sur une plage de fréquences
processor.zoom_frequency_range(7105000.0, 7110000.0)

# Obtenir l'image du spectrogramme pour affichage
image = processor.get_spectrogram_image()
```

Classes principales:
- WaterfallConfig: Configuration du traitement waterfall
- ColorMap: Options de coloration pour les spectrogrammes
- SpectrogramGenerator: Génération de spectrogrammes avec FFT
- FrequencySelection: Gestion des sélections de fréquences
- WaterfallProcessor: Traitement principal des données waterfall

@author: Équipe de développement SDR Triangulation Tool
@version: 1.0
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable, Any, Union

import numpy as np
from scipy import signal
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from src.utils.logger import get_logger
from src.utils.performance import timeit

# Configuration du logger
logger = get_logger(__name__)


class ColorScheme(Enum):
    """Schémas de couleurs prédéfinis pour les spectrogrammes."""
    DEFAULT = "default"  # Bleu -> Cyan -> Vert -> Jaune -> Rouge
    VIRIDIS = "viridis"  # Colormap scientifique de Matplotlib
    TURBO = "turbo"  # Amélioration de jet avec meilleure perception
    HOT = "hot"  # Noir -> Rouge -> Jaune -> Blanc
    JET = "jet"  # Bleu -> Cyan -> Jaune -> Rouge
    GRAYSCALE = "grayscale"  # Noir -> Blanc
    NIGHT = "night"  # Noir -> Bleu -> Violet
    RADIO = "radio"  # Bleu foncé -> Bleu clair -> Vert -> Jaune -> Rouge


@dataclass
class WaterfallConfig:
    """Configuration du traitement waterfall."""
    
    # Paramètres FFT
    fft_size: int = 1024  # Taille de la FFT (nombre de points)
    window_type: str = "hann"  # Type de fenêtre (hann, hamming, blackman, etc.)
    overlap: float = 0.5  # Chevauchement entre les segments (0.0 - 0.9)
    
    # Paramètres d'affichage
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    min_db: float = -100.0  # Limite inférieure en dB
    max_db: float = -20.0  # Limite supérieure en dB
    
    # Optimisation
    downsample_factor: int = 1  # Facteur de sous-échantillonnage
    optimize_for_realtime: bool = True  # Activer l'optimisation pour le temps réel
    
    # Paramètres de zoom
    freq_start: float = 0.0  # Fréquence de départ (Hz)
    freq_end: Optional[float] = None  # Fréquence de fin (Hz), None = max
    
    # Métadonnées
    sample_rate: float = 12000.0  # Taux d'échantillonnage (Hz)
    center_frequency: float = 7100000.0  # Fréquence centrale (Hz)


class ColorMap:
    """
    Gestion des colormap pour les spectrogrammes.
    
    Cette classe fournit différentes options de coloration pour
    les spectrogrammes et permet de personnaliser les colormap.
    """
    
    # Colormap personnalisée pour le mode "radio"
    RADIO_DATA = {
        'red': [(0.0, 0.0, 0.0),
                (0.3, 0.0, 0.0),
                (0.5, 0.0, 0.0),
                (0.7, 1.0, 1.0),
                (0.85, 1.0, 1.0),
                (1.0, 0.8, 0.8)],
        'green': [(0.0, 0.0, 0.0),
                  (0.3, 0.0, 0.0),
                  (0.5, 1.0, 1.0),
                  (0.7, 1.0, 1.0),
                  (0.85, 0.0, 0.0),
                  (1.0, 0.0, 0.0)],
        'blue': [(0.0, 0.2, 0.2),
                 (0.3, 1.0, 1.0),
                 (0.5, 0.0, 0.0),
                 (0.7, 0.0, 0.0),
                 (0.85, 0.0, 0.0),
                 (1.0, 0.0, 0.0)]
    }
    
    # Colormap personnalisée pour le mode "night"
    NIGHT_DATA = {
        'red': [(0.0, 0.0, 0.0),
                (0.5, 0.0, 0.0),
                (0.8, 0.4, 0.4),
                (1.0, 0.8, 0.8)],
        'green': [(0.0, 0.0, 0.0),
                  (0.5, 0.0, 0.0),
                  (0.8, 0.0, 0.0),
                  (1.0, 0.4, 0.4)],
        'blue': [(0.0, 0.0, 0.0),
                 (0.5, 0.7, 0.7),
                 (0.8, 1.0, 1.0),
                 (1.0, 1.0, 1.0)]
    }
    
    # Cache des colormaps personnalisées
    _custom_colormaps = {}
    
    @classmethod
    def get_colormap(cls, scheme: ColorScheme) -> Any:
        """
        Récupère la colormap correspondant au schéma spécifié.
        
        Args:
            scheme: Schéma de couleurs à utiliser
            
        Returns:
            Colormap pour le rendu du spectrogramme
        """
        if scheme == ColorScheme.DEFAULT:
            return plt.get_cmap('inferno')
        elif scheme == ColorScheme.VIRIDIS:
            return plt.get_cmap('viridis')
        elif scheme == ColorScheme.TURBO:
            return plt.get_cmap('turbo')
        elif scheme == ColorScheme.HOT:
            return plt.get_cmap('hot')
        elif scheme == ColorScheme.JET:
            return plt.get_cmap('jet')
        elif scheme == ColorScheme.GRAYSCALE:
            return plt.get_cmap('gray')
        elif scheme == ColorScheme.NIGHT:
            if 'night' not in cls._custom_colormaps:
                cls._custom_colormaps['night'] = LinearSegmentedColormap('night', cls.NIGHT_DATA)
            return cls._custom_colormaps['night']
        elif scheme == ColorScheme.RADIO:
            if 'radio' not in cls._custom_colormaps:
                cls._custom_colormaps['radio'] = LinearSegmentedColormap('radio', cls.RADIO_DATA)
            return cls._custom_colormaps['radio']
        else:
            logger.warning(f"Schéma de couleurs {scheme} non reconnu, utilisation du schéma par défaut")
            return plt.get_cmap('inferno')
    
    @classmethod
    def apply_colormap(cls, data: np.ndarray, scheme: ColorScheme) -> np.ndarray:
        """
        Applique une colormap à un tableau de données.
        
        Args:
            data: Tableau 2D de valeurs normalisées (0-1)
            scheme: Schéma de couleurs à appliquer
            
        Returns:
            Tableau 3D (RGBA) contenant l'image colorée
        """
        colormap = cls.get_colormap(scheme)
        return colormap(data)
    
    @classmethod
    def preview_colormap(cls, scheme: ColorScheme, figsize=(10, 2)) -> None:
        """
        Affiche un aperçu de la colormap.
        
        Args:
            scheme: Schéma de couleurs à prévisualiser
            figsize: Taille de la figure (largeur, hauteur)
        """
        colormap = cls.get_colormap(scheme)
        gradient = np.linspace(0, 1, 256)
        gradient = np.vstack((gradient, gradient))
        
        fig, ax = plt.subplots(figsize=figsize)
        ax.imshow(gradient, aspect='auto', cmap=colormap)
        ax.set_title(f"Colormap: {scheme.value}")
        ax.set_yticks([])
        ax.set_xticks([0, 64, 128, 192, 255])
        ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'])
        plt.tight_layout()
        plt.show()


class FrequencySelection:
    """
    Gestion des sélections de fréquences pour le zoom et l'analyse.
    
    Cette classe permet de:
    - Sélectionner des plages de fréquences
    - Zoomer sur des régions spécifiques
    - Convertir entre indices et fréquences
    """
    
    def __init__(self, sample_rate: float, fft_size: int, center_freq: float):
        """
        Initialise la gestion des sélections de fréquences.
        
        Args:
            sample_rate: Taux d'échantillonnage en Hz
            fft_size: Taille de la FFT
            center_freq: Fréquence centrale en Hz
        """
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.center_freq = center_freq
        
        # Calculer les fréquences de bin FFT
        self.bin_width = sample_rate / fft_size
        self.freqs = np.fft.rfftfreq(fft_size, 1.0/sample_rate) + center_freq
        
        # Sélection courante (par défaut: tout le spectre)
        self.selection_start = 0
        self.selection_end = len(self.freqs) - 1
    
    def select_frequency_range(self, start_freq: float, end_freq: float) -> Tuple[int, int]:
        """
        Sélectionne une plage de fréquences.
        
        Args:
            start_freq: Fréquence de début en Hz
            end_freq: Fréquence de fin en Hz
            
        Returns:
            Tuple avec les indices de début et de fin de la sélection
        """
        if start_freq > end_freq:
            start_freq, end_freq = end_freq, start_freq
        
        # Vérifier que les fréquences sont dans la plage disponible
        if start_freq < self.freqs[0]:
            start_freq = self.freqs[0]
            logger.warning(f"Fréquence de début ajustée à {start_freq} Hz (minimum disponible)")
        
        if end_freq > self.freqs[-1]:
            end_freq = self.freqs[-1]
            logger.warning(f"Fréquence de fin ajustée à {end_freq} Hz (maximum disponible)")
            
        # Trouver les indices correspondant aux fréquences
        start_idx = np.argmin(np.abs(self.freqs - start_freq))
        end_idx = np.argmin(np.abs(self.freqs - end_freq))
        
        # Assurer qu'on a au moins 2 points
        if start_idx == end_idx:
            if end_idx < len(self.freqs) - 1:
                end_idx += 1
            elif start_idx > 0:
                start_idx -= 1
        
        # Mettre à jour la sélection courante
        self.selection_start = start_idx
        self.selection_end = end_idx
        
        return start_idx, end_idx
    
    def get_selected_frequencies(self) -> Tuple[float, float]:
        """
        Récupère les fréquences actuellement sélectionnées.
        
        Returns:
            Tuple avec les fréquences de début et de fin en Hz
        """
        return (
            self.freqs[self.selection_start],
            self.freqs[self.selection_end]
        )
    
    def get_selection_indices(self) -> Tuple[int, int]:
        """
        Récupère les indices de la sélection actuelle.
        
        Returns:
            Tuple avec les indices de début et de fin
        """
        return self.selection_start, self.selection_end
    
    def zoom_to_selection(self) -> None:
        """
        Zoom sur la sélection courante.
        Cette méthode ne fait que confirmer que la sélection est la vue actuelle.
        """
        # Déjà implémenté via selection_start et selection_end
        pass
    
    def reset_zoom(self) -> None:
        """Réinitialise le zoom pour afficher tout le spectre."""
        self.selection_start = 0
        self.selection_end = len(self.freqs) - 1
    
    def bin_to_frequency(self, bin_index: int) -> float:
        """
        Convertit un indice de bin FFT en fréquence.
        
        Args:
            bin_index: Indice du bin FFT
            
        Returns:
            Fréquence correspondante en Hz
        """
        if bin_index < 0 or bin_index >= len(self.freqs):
            raise ValueError(f"Indice de bin {bin_index} hors limites [0-{len(self.freqs)-1}]")
        
        return self.freqs[bin_index]
    
    def frequency_to_bin(self, frequency: float) -> int:
        """
        Convertit une fréquence en indice de bin FFT.
        
        Args:
            frequency: Fréquence en Hz
            
        Returns:
            Indice du bin FFT le plus proche
        """
        return np.argmin(np.abs(self.freqs - frequency))


class SpectrogramGenerator:
    """
    Générateur de spectrogrammes avec FFT configurable.
    
    Cette classe implémente:
    - La génération de spectrogrammes à partir de données temporelles
    - Le calcul de FFT configurables
    - L'optimisation des performances pour le temps réel
    """
    
    def __init__(self, config: WaterfallConfig):
        """
        Initialise le générateur de spectrogrammes.
        
        Args:
            config: Configuration du traitement waterfall
        """
        self.config = config
        self._window = self._create_window(config.window_type, config.fft_size)
        
        # Paramètres pour optimisation
        self._last_calc_time = 0
        self._avg_calc_time = 0
        self._calc_count = 0
    
    def _create_window(self, window_type: str, window_size: int) -> np.ndarray:
        """
        Crée une fenêtre d'analyse pour la FFT.
        
        Args:
            window_type: Type de fenêtre (hann, hamming, blackman, etc.)
            window_size: Taille de la fenêtre
            
        Returns:
            Tableau numpy contenant la fenêtre
        """
        try:
            return getattr(signal.windows, window_type)(window_size)
        except AttributeError:
            logger.warning(f"Type de fenêtre {window_type} non reconnu, utilisation de hann")
            return signal.windows.hann(window_size)
    
    @timeit
    def compute_spectrogram(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Calcule le spectrogramme à partir de données audio.
        
        Args:
            audio_data: Tableau numpy contenant les données audio
            
        Returns:
            Tableau 2D contenant le spectrogramme
        """
        start_time = time.time()
        
        # Paramètres pour le calcul du spectrogramme
        nperseg = self.config.fft_size
        noverlap = int(nperseg * self.config.overlap)
        
        # Sous-échantillonnage si nécessaire
        if self.config.downsample_factor > 1:
            audio_data = audio_data[::self.config.downsample_factor]
        
        # Calcul du spectrogramme
        frequencies, times, spectrogram = signal.spectrogram(
            audio_data,
            fs=self.config.sample_rate / self.config.downsample_factor,
            window=self._window,
            nperseg=nperseg,
            noverlap=noverlap,
            detrend=False,
            scaling='spectrum',
            mode='magnitude'
        )
        
        # Convertir en dB
        # Ajouter une petite valeur pour éviter log(0)
        spectrogram_db = 10 * np.log10(spectrogram + 1e-10)
        
        # Mettre à jour les statistiques de calcul
        calc_time = time.time() - start_time
        self._update_performance_stats(calc_time)
        
        return spectrogram_db
    
    def _update_performance_stats(self, calc_time: float) -> None:
        """
        Met à jour les statistiques de performances.
        
        Args:
            calc_time: Temps de calcul en secondes
        """
        # S'assurer que _last_calc_time est toujours supérieur à zéro
        self._last_calc_time = max(calc_time, 0.000001)
        self._calc_count += 1
        
        # Moyenne glissante
        if self._avg_calc_time == 0:
            self._avg_calc_time = self._last_calc_time
        else:
            self._avg_calc_time = 0.9 * self._avg_calc_time + 0.1 * self._last_calc_time
    
    def optimize_parameters(self, target_time: float = 0.05) -> None:
        """
        Optimise les paramètres pour le temps réel.
        
        Ajuste automatiquement le facteur de sous-échantillonnage et la taille de la FFT
        pour atteindre une cible de temps de calcul.
        
        Args:
            target_time: Temps de calcul cible en secondes
        """
        if not self.config.optimize_for_realtime or self._calc_count < 10:
            return
        
        if self._avg_calc_time > target_time * 1.5:
            # Trop lent, augmenter le facteur de sous-échantillonnage
            self.config.downsample_factor = min(self.config.downsample_factor + 1, 4)
            logger.debug(f"Augmentation du facteur de sous-échantillonnage à {self.config.downsample_factor}")
        
        elif self._avg_calc_time < target_time * 0.5 and self.config.downsample_factor > 1:
            # Trop rapide, diminuer le facteur de sous-échantillonnage
            self.config.downsample_factor = max(self.config.downsample_factor - 1, 1)
            logger.debug(f"Diminution du facteur de sous-échantillonnage à {self.config.downsample_factor}")
    
    def get_performance_stats(self) -> Dict[str, float]:
        """
        Récupère les statistiques de performances.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        return {
            "last_calc_time": self._last_calc_time,
            "avg_calc_time": self._avg_calc_time,
            "calc_count": self._calc_count,
            "downsample_factor": self.config.downsample_factor,
            "fft_size": self.config.fft_size
        }


class WaterfallProcessor:
    """
    Processeur principal pour les données waterfall.
    
    Cette classe intègre les différentes fonctionnalités:
    - Configuration et gestion des paramètres
    - Génération de spectrogrammes
    - Gestion des couleurs et de l'échelle
    - Zoom et sélection de fréquences
    - Optimisation des performances
    """
    
    def __init__(self, config: Optional[WaterfallConfig] = None):
        """
        Initialise le processeur waterfall.
        
        Args:
            config: Configuration du traitement waterfall
        """
        self.config = config or WaterfallConfig()
        self.spectrogram_generator = SpectrogramGenerator(self.config)
        self.frequency_selection = FrequencySelection(
            self.config.sample_rate,
            self.config.fft_size,
            self.config.center_frequency
        )
        
        # Buffer pour le spectrogramme
        self.spectrogram_buffer = []
        self.max_buffer_lines = 600  # Nombre de lignes max dans le buffer
    
    def process_audio_data(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Traite les données audio pour générer une ligne de spectrogramme.
        
        Args:
            audio_data: Données audio à traiter
            
        Returns:
            Ligne de spectrogramme (données normalisées)
        """
        # Calculer le spectrogramme
        spectrogram_db = self.spectrogram_generator.compute_spectrogram(audio_data)
        
        # Prendre la dernière ligne du spectrogramme
        if spectrogram_db.shape[1] > 0:
            line = spectrogram_db[:, -1]
        else:
            # Cas où le spectrogramme est vide
            line = np.zeros(self.config.fft_size // 2 + 1)
        
        # Normaliser la ligne selon les paramètres min_db et max_db
        normalized_line = self._normalize_db_values(line)
        
        # Ajouter au buffer
        self._add_to_buffer(normalized_line)
        
        # Optimiser les paramètres si nécessaire
        if self.config.optimize_for_realtime:
            self.spectrogram_generator.optimize_parameters()
        
        return normalized_line
    
    def _normalize_db_values(self, db_values: np.ndarray) -> np.ndarray:
        """
        Normalise les valeurs dB dans la plage [0, 1].
        
        Args:
            db_values: Valeurs en dB
            
        Returns:
            Valeurs normalisées entre 0 et 1
        """
        # Limiter les valeurs à la plage min_db - max_db
        clipped = np.clip(db_values, self.config.min_db, self.config.max_db)
        
        # Normaliser à [0, 1]
        normalized = (clipped - self.config.min_db) / (self.config.max_db - self.config.min_db)
        
        return normalized
    
    def _add_to_buffer(self, line: np.ndarray) -> None:
        """
        Ajoute une ligne au buffer du spectrogramme.
        
        Args:
            line: Ligne à ajouter
        """
        self.spectrogram_buffer.append(line)
        
        # Limiter la taille du buffer
        if len(self.spectrogram_buffer) > self.max_buffer_lines:
            self.spectrogram_buffer.pop(0)
    
    def get_spectrogram_image(self) -> np.ndarray:
        """
        Récupère l'image du spectrogramme avec le zoom et les couleurs appliqués.
        
        Returns:
            Image du spectrogramme (RGBA)
        """
        if not self.spectrogram_buffer:
            # Créer une image vide si le buffer est vide
            height = 100
            width = self.config.fft_size // 2 + 1
            empty_image = np.zeros((height, width, 4))
            return empty_image
        
        # Convertir le buffer en array 2D
        spectrogram_data = np.array(self.spectrogram_buffer)
        
        # Appliquer le zoom (sélection de fréquences)
        start_idx, end_idx = self.frequency_selection.get_selection_indices()
        zoomed_data = spectrogram_data[:, start_idx:end_idx+1]
        
        # Appliquer la colormap
        colored_image = ColorMap.apply_colormap(zoomed_data, self.config.color_scheme)
        
        return colored_image
    
    def get_latest_spectrum(self) -> np.ndarray:
        """
        Récupère le dernier spectre analysé.
        
        Returns:
            Dernière ligne de spectrogramme (normalisée)
        """
        if not self.spectrogram_buffer:
            return np.zeros(self.config.fft_size // 2 + 1)
        
        return self.spectrogram_buffer[-1]
    
    def zoom_frequency_range(self, start_freq: float, end_freq: float) -> None:
        """
        Zoome sur une plage de fréquences spécifique.
        
        Args:
            start_freq: Fréquence de début en Hz
            end_freq: Fréquence de fin en Hz
        """
        self.frequency_selection.select_frequency_range(start_freq, end_freq)
    
    def reset_zoom(self) -> None:
        """Réinitialise le zoom pour afficher tout le spectre."""
        self.frequency_selection.reset_zoom()
    
    def set_color_scheme(self, scheme: ColorScheme) -> None:
        """
        Définit le schéma de couleurs pour le spectrogramme.
        
        Args:
            scheme: Schéma de couleurs à utiliser
        """
        self.config.color_scheme = scheme
    
    def set_db_range(self, min_db: float, max_db: float) -> None:
        """
        Définit la plage de dB pour l'affichage.
        
        Args:
            min_db: Valeur minimum en dB
            max_db: Valeur maximum en dB
        """
        if min_db >= max_db:
            raise ValueError(f"min_db ({min_db}) doit être inférieur à max_db ({max_db})")
        
        self.config.min_db = min_db
        self.config.max_db = max_db
    
    def set_fft_parameters(self, fft_size: int, window_type: str = "hann", overlap: float = 0.5) -> None:
        """
        Configure les paramètres de la FFT.
        
        Args:
            fft_size: Taille de la FFT
            window_type: Type de fenêtre
            overlap: Chevauchement entre segments
        """
        if fft_size < 64 or fft_size > 8192:
            raise ValueError(f"fft_size ({fft_size}) doit être entre 64 et 8192")
        
        if overlap < 0.0 or overlap > 0.9:
            raise ValueError(f"overlap ({overlap}) doit être entre 0.0 et 0.9")
        
        # Mettre à jour la configuration
        self.config.fft_size = fft_size
        self.config.window_type = window_type
        self.config.overlap = overlap
        
        # Recréer les objets dépendants
        self.spectrogram_generator = SpectrogramGenerator(self.config)
        self.frequency_selection = FrequencySelection(
            self.config.sample_rate,
            self.config.fft_size,
            self.config.center_frequency
        )
        
        # Vider le buffer car les dimensions changent
        self.spectrogram_buffer = []
    
    def get_config(self) -> WaterfallConfig:
        """
        Récupère la configuration actuelle.
        
        Returns:
            Configuration du traitement waterfall
        """
        return self.config
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques de performances.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        stats = self.spectrogram_generator.get_performance_stats()
        stats.update({
            "buffer_lines": len(self.spectrogram_buffer),
            "max_buffer_lines": self.max_buffer_lines
        })
        return stats 