"""
Tests unitaires pour le module waterfall.py.

Ce module teste:
- La génération de spectrogrammes avec FFT configurable
- Les options de coloration et d'échelle
- Le zoom et la sélection de plages de fréquences
- Les optimisations pour le traitement en temps réel
"""

import numpy as np
import pytest
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import sys
import os

# Add the project root to the path so we can import the src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.signal_processing.waterfall import (
    ColorScheme, 
    WaterfallConfig, 
    ColorMap, 
    FrequencySelection,
    SpectrogramGenerator, 
    WaterfallProcessor
)


class TestColorScheme:
    """Tests pour l'énumération ColorScheme."""
    
    def test_enum_values(self):
        """Vérifie que les valeurs attendues sont présentes dans l'énumération."""
        assert ColorScheme.DEFAULT.value == "default"
        assert ColorScheme.VIRIDIS.value == "viridis"
        assert ColorScheme.TURBO.value == "turbo"
        assert ColorScheme.HOT.value == "hot"
        assert ColorScheme.JET.value == "jet"
        assert ColorScheme.GRAYSCALE.value == "grayscale"
        assert ColorScheme.NIGHT.value == "night"
        assert ColorScheme.RADIO.value == "radio"


class TestWaterfallConfig:
    """Tests pour la classe WaterfallConfig."""
    
    def test_default_values(self):
        """Vérifie que les valeurs par défaut sont correctes."""
        config = WaterfallConfig()
        
        # Paramètres FFT
        assert config.fft_size == 1024
        assert config.window_type == "hann"
        assert config.overlap == 0.5
        
        # Paramètres d'affichage
        assert config.color_scheme == ColorScheme.DEFAULT
        assert config.min_db == -100.0
        assert config.max_db == -20.0
        
        # Optimisation
        assert config.downsample_factor == 1
        assert config.optimize_for_realtime is True
        
        # Paramètres de zoom
        assert config.freq_start == 0.0
        assert config.freq_end is None
        
        # Métadonnées
        assert config.sample_rate == 12000.0
        assert config.center_frequency == 7100000.0
    
    def test_custom_values(self):
        """Vérifie que les valeurs personnalisées sont correctement assignées."""
        config = WaterfallConfig(
            fft_size=2048,
            window_type="blackman",
            overlap=0.75,
            color_scheme=ColorScheme.HOT,
            min_db=-120.0,
            max_db=-10.0,
            downsample_factor=2,
            optimize_for_realtime=False,
            freq_start=7000000.0,
            freq_end=7200000.0,
            sample_rate=48000.0,
            center_frequency=14100000.0
        )
        
        # Vérifier que toutes les valeurs sont correctement assignées
        assert config.fft_size == 2048
        assert config.window_type == "blackman"
        assert config.overlap == 0.75
        assert config.color_scheme == ColorScheme.HOT
        assert config.min_db == -120.0
        assert config.max_db == -10.0
        assert config.downsample_factor == 2
        assert config.optimize_for_realtime is False
        assert config.freq_start == 7000000.0
        assert config.freq_end == 7200000.0
        assert config.sample_rate == 48000.0
        assert config.center_frequency == 14100000.0


class TestColorMap:
    """Tests pour la classe ColorMap."""
    
    def test_get_colormap(self):
        """Vérifie que get_colormap renvoie les bonnes colormaps."""
        # Tester les colormaps standards
        assert isinstance(ColorMap.get_colormap(ColorScheme.DEFAULT), plt.Colormap)
        assert isinstance(ColorMap.get_colormap(ColorScheme.VIRIDIS), plt.Colormap)
        assert isinstance(ColorMap.get_colormap(ColorScheme.HOT), plt.Colormap)
        
        # Tester les colormaps personnalisées
        assert isinstance(ColorMap.get_colormap(ColorScheme.NIGHT), LinearSegmentedColormap)
        assert isinstance(ColorMap.get_colormap(ColorScheme.RADIO), LinearSegmentedColormap)
        
        # Vérifier le cache
        night_cm1 = ColorMap.get_colormap(ColorScheme.NIGHT)
        night_cm2 = ColorMap.get_colormap(ColorScheme.NIGHT)
        assert night_cm1 is night_cm2  # Vérifier que c'est la même instance (cache)
    
    def test_apply_colormap(self):
        """Vérifie que apply_colormap applique correctement la colormap aux données."""
        # Créer des données de test
        data = np.linspace(0, 1, 100).reshape(10, 10)
        
        # Appliquer différentes colormaps
        result_default = ColorMap.apply_colormap(data, ColorScheme.DEFAULT)
        result_hot = ColorMap.apply_colormap(data, ColorScheme.HOT)
        result_night = ColorMap.apply_colormap(data, ColorScheme.NIGHT)
        
        # Vérifier les dimensions (RGBA)
        assert result_default.shape == (10, 10, 4)
        assert result_hot.shape == (10, 10, 4)
        assert result_night.shape == (10, 10, 4)
        
        # Vérifier que les valeurs sont dans la plage [0, 1]
        assert np.all(result_default >= 0) and np.all(result_default <= 1)
        assert np.all(result_hot >= 0) and np.all(result_hot <= 1)
        assert np.all(result_night >= 0) and np.all(result_night <= 1)
        
        # Vérifier que les résultats sont différents pour des colormaps différentes
        assert not np.allclose(result_default, result_hot)
        assert not np.allclose(result_default, result_night)


class TestFrequencySelection:
    """Tests pour la classe FrequencySelection."""
    
    def test_initialization(self):
        """Vérifie que l'initialisation calcule correctement les fréquences."""
        # Paramètres de test
        sample_rate = 12000.0
        fft_size = 1024
        center_freq = 7100000.0
        
        # Initialiser la sélection de fréquences
        freq_sel = FrequencySelection(sample_rate, fft_size, center_freq)
        
        # Vérifier les valeurs calculées
        assert freq_sel.bin_width == sample_rate / fft_size
        assert len(freq_sel.freqs) == fft_size // 2 + 1  # Pour FFT réelle
        assert freq_sel.freqs[0] == center_freq  # La première fréquence doit être la fréquence centrale
        
        # Vérifier la sélection par défaut (tout le spectre)
        assert freq_sel.selection_start == 0
        assert freq_sel.selection_end == len(freq_sel.freqs) - 1
    
    def test_select_frequency_range(self):
        """Vérifie que la sélection de plage de fréquences fonctionne correctement."""
        # Initialiser la sélection de fréquences
        freq_sel = FrequencySelection(12000.0, 1024, 7100000.0)
        
        # Sélectionner une plage
        start_freq = 7105000.0
        end_freq = 7110000.0
        start_idx, end_idx = freq_sel.select_frequency_range(start_freq, end_freq)
        
        # Vérifier que les indices sont corrects
        assert start_idx >= 0
        assert end_idx <= len(freq_sel.freqs) - 1
        assert start_idx < end_idx
        
        # Vérifier que la sélection a été mise à jour
        assert freq_sel.selection_start == start_idx
        assert freq_sel.selection_end == end_idx
        
        # Vérifier que les fréquences sélectionnées sont proches des valeurs demandées
        selected_start, selected_end = freq_sel.get_selected_frequencies()
        assert abs(selected_start - start_freq) < 5000  # Tolérance: 5000 Hz
        assert abs(selected_end - end_freq) < 5000  # Tolérance: 5000 Hz
        
        # Tester l'inversion automatique des fréquences
        start_idx2, end_idx2 = freq_sel.select_frequency_range(end_freq, start_freq)
        assert start_idx2 == start_idx
        assert end_idx2 == end_idx
    
    def test_reset_zoom(self):
        """Vérifie que reset_zoom réinitialise correctement la sélection."""
        # Initialiser la sélection de fréquences
        freq_sel = FrequencySelection(12000.0, 1024, 7100000.0)
        
        # Sélectionner une plage
        freq_sel.select_frequency_range(7105000.0, 7110000.0)
        
        # Réinitialiser le zoom
        freq_sel.reset_zoom()
        
        # Vérifier que la sélection est revenue à tout le spectre
        assert freq_sel.selection_start == 0
        assert freq_sel.selection_end == len(freq_sel.freqs) - 1
    
    def test_bin_frequency_conversion(self):
        """Vérifie les conversions entre indices de bin et fréquences."""
        # Initialiser la sélection de fréquences
        freq_sel = FrequencySelection(12000.0, 1024, 7100000.0)
        
        # Tester bin_to_frequency
        freq = freq_sel.bin_to_frequency(100)
        assert isinstance(freq, float)
        
        # Tester frequency_to_bin
        bin_idx = freq_sel.frequency_to_bin(freq)
        assert bin_idx == 100  # Devrait retourner le même indice
        
        # Tester la conversion aller-retour pour plusieurs indices
        for idx in [0, 10, 100, 500]:
            freq = freq_sel.bin_to_frequency(idx)
            bin_idx = freq_sel.frequency_to_bin(freq)
            assert bin_idx == idx
        
        # Tester les erreurs de validation
        with pytest.raises(ValueError):
            freq_sel.bin_to_frequency(-1)  # Indice négatif
        
        with pytest.raises(ValueError):
            freq_sel.bin_to_frequency(1000000)  # Indice trop grand


class TestSpectrogramGenerator:
    """Tests pour la classe SpectrogramGenerator."""
    
    def test_initialization(self):
        """Vérifie que l'initialisation crée correctement la fenêtre."""
        config = WaterfallConfig(fft_size=1024, window_type="hann")
        sg = SpectrogramGenerator(config)
        
        # Vérifier que la fenêtre a été créée avec la bonne taille
        assert len(sg._window) == config.fft_size
        
        # Vérifier que les compteurs de performance sont initialisés
        assert sg._last_calc_time == 0
        assert sg._avg_calc_time == 0
        assert sg._calc_count == 0
    
    def test_window_creation(self):
        """Vérifie que différents types de fenêtres peuvent être créés."""
        # Tester différents types de fenêtres
        for window_type in ["hann", "hamming", "blackman", "bartlett", "flattop"]:
            config = WaterfallConfig(fft_size=1024, window_type=window_type)
            sg = SpectrogramGenerator(config)
            assert len(sg._window) == config.fft_size
        
        # Tester un type de fenêtre invalide (devrait utiliser hann par défaut)
        config = WaterfallConfig(fft_size=1024, window_type="invalid_window")
        sg = SpectrogramGenerator(config)
        assert len(sg._window) == config.fft_size
    
    def test_compute_spectrogram(self):
        """Vérifie que le calcul du spectrogramme fonctionne correctement."""
        config = WaterfallConfig(fft_size=1024, window_type="hann", sample_rate=12000.0)
        sg = SpectrogramGenerator(config)
        
        # Créer des données audio test (signal sinusoïdal + bruit)
        t = np.linspace(0, 1, 12000)  # 1 seconde à 12kHz
        audio_data = np.sin(2 * np.pi * 1000 * t) + 0.1 * np.random.randn(len(t))
        
        # Calculer le spectrogramme
        spectrogram = sg.compute_spectrogram(audio_data)
        
        # Vérifier que le spectrogramme a les bonnes dimensions
        assert spectrogram.ndim == 2
        assert spectrogram.shape[0] <= config.fft_size // 2 + 1  # Devrait être <= nbins FFT
        
        # Vérifier que les statistiques de performance ont été mises à jour
        assert sg._last_calc_time > 0
        assert sg._avg_calc_time > 0
        assert sg._calc_count == 1
    
    def test_downsample_factor(self):
        """Vérifie que le facteur de sous-échantillonnage est correctement appliqué."""
        # Créer des données audio test
        t = np.linspace(0, 1, 12000)  # 1 seconde à 12kHz
        audio_data = np.sin(2 * np.pi * 1000 * t)
        
        # Calculer avec différents facteurs de sous-échantillonnage
        config1 = WaterfallConfig(downsample_factor=1, sample_rate=12000.0)
        sg1 = SpectrogramGenerator(config1)
        spec1 = sg1.compute_spectrogram(audio_data)
        
        config2 = WaterfallConfig(downsample_factor=2, sample_rate=12000.0)
        sg2 = SpectrogramGenerator(config2)
        spec2 = sg2.compute_spectrogram(audio_data)
        
        # Le temps-fréquence d'un spectrogramme avec downsample devrait être différent
        # car on traite moins d'échantillons
        assert spec1.shape != spec2.shape
    
    def test_optimize_parameters(self):
        """Vérifie que l'optimisation des paramètres fonctionne correctement."""
        config = WaterfallConfig(
            optimize_for_realtime=True,
            downsample_factor=2
        )
        sg = SpectrogramGenerator(config)
        
        # Simuler des calculs précédents
        sg._avg_calc_time = 0.1  # 100ms (trop lent)
        sg._calc_count = 20
        
        # Optimiser pour un temps cible de 50ms
        sg.optimize_parameters(target_time=0.05)
        
        # Le facteur de sous-échantillonnage devrait avoir augmenté
        assert config.downsample_factor == 3
        
        # Maintenant simuler un calcul rapide
        sg._avg_calc_time = 0.01  # 10ms (trop rapide)
        
        # Optimiser à nouveau
        sg.optimize_parameters(target_time=0.05)
        
        # Le facteur de sous-échantillonnage devrait avoir diminué
        assert config.downsample_factor == 2


class TestWaterfallProcessor:
    """Tests pour la classe WaterfallProcessor."""
    
    def test_initialization(self):
        """Vérifie que l'initialisation crée correctement les objets dépendants."""
        config = WaterfallConfig()
        processor = WaterfallProcessor(config)
        
        # Vérifier que les objets dépendants sont créés
        assert processor.config is config
        assert isinstance(processor.spectrogram_generator, SpectrogramGenerator)
        assert isinstance(processor.frequency_selection, FrequencySelection)
        
        # Vérifier que le buffer est initialisé
        assert processor.spectrogram_buffer == []
        assert processor.max_buffer_lines == 600
    
    def test_process_audio_data(self):
        """Vérifie que le traitement des données audio fonctionne correctement."""
        config = WaterfallConfig()
        processor = WaterfallProcessor(config)
        
        # Créer des données audio test
        t = np.linspace(0, 1, 12000)  # 1 seconde à 12kHz
        audio_data = np.sin(2 * np.pi * 1000 * t) + 0.1 * np.random.randn(len(t))
        
        # Traiter les données audio
        normalized_line = processor.process_audio_data(audio_data)
        
        # Vérifier que la sortie est correcte
        assert isinstance(normalized_line, np.ndarray)
        assert normalized_line.ndim == 1
        assert 0.0 <= np.min(normalized_line) <= np.max(normalized_line) <= 1.0
        
        # Vérifier que le buffer a été mis à jour
        assert len(processor.spectrogram_buffer) == 1
        assert np.array_equal(processor.spectrogram_buffer[0], normalized_line)
    
    def test_normalize_db_values(self):
        """Vérifie que la normalisation des valeurs dB fonctionne correctement."""
        config = WaterfallConfig(min_db=-100.0, max_db=-20.0)
        processor = WaterfallProcessor(config)
        
        # Créer des valeurs dB test
        db_values = np.array([-120.0, -100.0, -60.0, -20.0, 0.0])
        
        # Normaliser
        normalized = processor._normalize_db_values(db_values)
        
        # Vérifier les résultats
        assert np.isclose(normalized[0], 0.0)  # -120 dB -> 0.0 (clipping)
        assert np.isclose(normalized[1], 0.0)  # -100 dB -> 0.0
        assert np.isclose(normalized[2], 0.5)  # -60 dB -> 0.5
        assert np.isclose(normalized[3], 1.0)  # -20 dB -> 1.0
        assert np.isclose(normalized[4], 1.0)  # 0 dB -> 1.0 (clipping)
    
    def test_buffer_management(self):
        """Vérifie que la gestion du buffer fonctionne correctement."""
        config = WaterfallConfig()
        processor = WaterfallProcessor(config)
        processor.max_buffer_lines = 3  # Réduire pour le test
        
        # Ajouter 5 lignes au buffer
        for i in range(5):
            line = np.ones(10) * i
            processor._add_to_buffer(line)
        
        # Vérifier que le buffer contient seulement les 3 dernières lignes
        assert len(processor.spectrogram_buffer) == 3
        assert np.array_equal(processor.spectrogram_buffer[0], np.ones(10) * 2)
        assert np.array_equal(processor.spectrogram_buffer[1], np.ones(10) * 3)
        assert np.array_equal(processor.spectrogram_buffer[2], np.ones(10) * 4)
    
    def test_get_spectrogram_image(self):
        """Vérifie que la génération d'image spectrogramme fonctionne correctement."""
        config = WaterfallConfig(color_scheme=ColorScheme.VIRIDIS)
        processor = WaterfallProcessor(config)
        
        # Cas buffer vide
        empty_image = processor.get_spectrogram_image()
        assert empty_image.shape[2] == 4  # RGBA
        
        # Ajouter des données au buffer
        for i in range(5):
            line = np.linspace(0, 1, 513)  # fft_size=1024 -> 513 bins
            processor._add_to_buffer(line)
        
        # Générer l'image
        image = processor.get_spectrogram_image()
        
        # Vérifier les dimensions
        assert image.shape[0] == 5  # 5 lignes
        assert image.shape[1] == 513  # Tous les bins
        assert image.shape[2] == 4  # RGBA
    
    def test_zoom_and_color(self):
        """Vérifie que le zoom et les couleurs fonctionnent correctement."""
        config = WaterfallConfig()
        processor = WaterfallProcessor(config)
        
        # Ajouter des données au buffer
        for i in range(10):
            line = np.linspace(0, 1, 513)  # fft_size=1024 -> 513 bins
            processor._add_to_buffer(line)
        
        # Appliquer un zoom
        processor.zoom_frequency_range(7105000.0, 7110000.0)
        
        # Générer l'image avec zoom
        zoomed_image = processor.get_spectrogram_image()
        
        # L'image zoomée devrait avoir moins de colonnes que l'image complète
        assert zoomed_image.shape[0] == 10  # Même nombre de lignes
        assert zoomed_image.shape[1] < 513  # Moins de colonnes
        
        # Réinitialiser le zoom
        processor.reset_zoom()
        full_image = processor.get_spectrogram_image()
        assert full_image.shape[1] == 513  # Toutes les colonnes
        
        # Changer le schéma de couleurs
        processor.set_color_scheme(ColorScheme.HOT)
        hot_image = processor.get_spectrogram_image()
        
        # Les dimensions devraient être les mêmes, mais les couleurs différentes
        assert hot_image.shape == full_image.shape
        assert not np.allclose(hot_image, full_image)
    
    def test_set_db_range(self):
        """Vérifie que la modification de la plage dB fonctionne correctement."""
        config = WaterfallConfig(min_db=-100.0, max_db=-20.0)
        processor = WaterfallProcessor(config)
        
        # Modifier la plage dB
        processor.set_db_range(-80.0, -10.0)
        
        # Vérifier que la configuration a été mise à jour
        assert processor.config.min_db == -80.0
        assert processor.config.max_db == -10.0
        
        # Vérifier la validation des entrées
        with pytest.raises(ValueError):
            processor.set_db_range(-10.0, -20.0)  # min > max
    
    def test_set_fft_parameters(self):
        """Vérifie que la modification des paramètres FFT fonctionne correctement."""
        config = WaterfallConfig(fft_size=1024)
        processor = WaterfallProcessor(config)
        
        # Ajouter des données au buffer
        processor._add_to_buffer(np.ones(513))
        
        # Modifier les paramètres FFT
        processor.set_fft_parameters(fft_size=2048, window_type="blackman", overlap=0.75)
        
        # Vérifier que la configuration a été mise à jour
        assert processor.config.fft_size == 2048
        assert processor.config.window_type == "blackman"
        assert processor.config.overlap == 0.75
        
        # Le buffer devrait être vide après changement de taille FFT
        assert len(processor.spectrogram_buffer) == 0
        
        # Vérifier la validation des entrées
        with pytest.raises(ValueError):
            processor.set_fft_parameters(fft_size=10)  # Trop petit
        
        with pytest.raises(ValueError):
            processor.set_fft_parameters(fft_size=1024, overlap=1.0)  # Overlap trop grand 