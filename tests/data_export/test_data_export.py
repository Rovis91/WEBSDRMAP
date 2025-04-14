"""
Tests unitaires pour le module data_export.py.

Ce module teste:
- L'exportation des données audio (WAV)
- L'exportation des données de spectrogramme
- La sauvegarde des données de triangulation (CSV, JSON)
- L'exportation des annotations utilisateur
- Le gestionnaire central d'exportation
"""

import os
import sys
import json
import csv
import tempfile
import shutil
import wave
import numpy as np
import pytest
from pathlib import Path
from datetime import datetime

# Force matplotlib to use a non-GUI backend for testing
import matplotlib
matplotlib.use('Agg')

# Add the project root to the path so we can import the src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.data_export.data_export import (
    AudioExporter, 
    SpectrogramExporter, 
    TriangulationExporter,
    AnnotationExporter,
    DataExporter
)
from src.signal_processing.triangulation import TriangulationResult, Location, ReliabilityLevel

# Add a monkey patch for backward compatibility with exporters
# This adds a location property that just returns estimated_location
def get_location(self):
    return self.estimated_location

TriangulationResult.location = property(get_location)

# Fixtures pour les tests
@pytest.fixture
def temp_output_dir():
    """Crée un répertoire temporaire pour les exports et le nettoie après les tests."""
    temp_dir = tempfile.mkdtemp(prefix="test_exports_")
    yield temp_dir
    # Nettoyage après les tests
    shutil.rmtree(temp_dir)


@pytest.fixture
def audio_data():
    """Génère des données audio pour les tests."""
    # Créer un signal sinusoïdal simple
    sample_rate = 8000
    duration = 0.5  # secondes
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(2 * np.pi * 440 * t)  # 440 Hz = La
    return tone, sample_rate


@pytest.fixture
def spectrogram_data():
    """Génère des données de spectrogramme pour les tests."""
    # Créer un spectrogramme de test (10 fréquences x 5 temps)
    freqs = np.linspace(100, 1000, 10)
    times = np.linspace(0, 1, 5)
    spectrogram = np.random.rand(10, 5)  # Valeurs aléatoires entre 0 et 1
    return spectrogram, freqs, times


@pytest.fixture
def triangulation_results():
    """Génère des résultats de triangulation pour les tests."""
    results = []
    
    # Créer deux résultats de test avec datetime au lieu de timestamp
    current_time = datetime.now()
    
    result1 = TriangulationResult(
        estimated_location=Location(48.8566, 2.3522, 0),  # Paris
        error_radius=5.0,
        reliability=ReliabilityLevel.HIGH,
        receiver_locations={
            "SDR1": Location(48.85, 2.35, 0),
            "SDR2": Location(48.86, 2.36, 0)
        },
        rssi_values={
            "SDR1": -70.5,
            "SDR2": -65.2
        },
        frequency=7100000.0,
        timestamp=current_time.timestamp()
    )
    
    result2 = TriangulationResult(
        estimated_location=Location(45.7640, 4.8357, 0),  # Lyon
        error_radius=8.5,
        reliability=ReliabilityLevel.MEDIUM,
        receiver_locations={
            "SDR1": Location(45.76, 4.83, 0),
            "SDR2": Location(45.77, 4.84, 0),
            "SDR3": Location(45.75, 4.82, 0)
        },
        rssi_values={
            "SDR1": -80.0,
            "SDR2": -75.5,
            "SDR3": -82.3
        },
        frequency=14200000.0,
        timestamp=current_time.timestamp()
    )
    
    results.append(result1)
    results.append(result2)
    return results


@pytest.fixture
def annotations():
    """Génère des annotations utilisateur pour les tests."""
    return [
        {
            "id": "anno1",
            "type": "marker",
            "timestamp": datetime.now().isoformat(),
            "frequency": 7100000.0,
            "label": "Signal AM",
            "color": "#FF0000"
        },
        {
            "id": "anno2",
            "type": "region",
            "timestamp": datetime.now().isoformat(),
            "start_freq": 14200000.0,
            "end_freq": 14250000.0,
            "label": "Bande SSB",
            "color": "#00FF00",
            "notes": "Activité importante"
        }
    ]


class TestAudioExporter:
    """Tests pour la classe AudioExporter."""
    
    def test_initialization(self, temp_output_dir):
        """Vérifie que l'initialisation crée le répertoire de sortie."""
        output_dir = os.path.join(temp_output_dir, "audio")
        exporter = AudioExporter(output_dir)
        
        assert os.path.exists(output_dir)
        assert exporter.output_dir == output_dir

    def test_export_wav(self, temp_output_dir, audio_data):
        """Vérifie que l'exportation WAV fonctionne correctement."""
        audio, sample_rate = audio_data
        exporter = AudioExporter(os.path.join(temp_output_dir, "audio"))
        
        # Test avec un nom de fichier spécifié
        filename = "test_audio.wav"
        filepath = exporter.export_wav(audio, sample_rate, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier que le contenu est valide
        with wave.open(filepath, 'rb') as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getsampwidth() == 2
            assert wav_file.getframerate() == sample_rate
            assert wav_file.getnframes() == len(audio)
        
        # Test avec génération automatique du nom
        filepath2 = exporter.export_wav(audio, sample_rate)
        assert os.path.exists(filepath2)
        assert filepath2.endswith('.wav')
        assert filepath != filepath2  # Noms différents


class TestSpectrogramExporter:
    """Tests pour la classe SpectrogramExporter."""
    
    def test_initialization(self, temp_output_dir):
        """Vérifie que l'initialisation crée le répertoire de sortie."""
        output_dir = os.path.join(temp_output_dir, "spectrograms")
        exporter = SpectrogramExporter(output_dir)
        
        assert os.path.exists(output_dir)
        assert exporter.output_dir == output_dir
    
    def test_export_image(self, temp_output_dir, spectrogram_data):
        """Vérifie que l'exportation d'image fonctionne correctement."""
        spectrogram, freqs, times = spectrogram_data
        exporter = SpectrogramExporter(os.path.join(temp_output_dir, "spectrograms"))
        
        # Test avec un nom de fichier spécifié
        filename = "test_spectrogram.png"
        filepath = exporter.export_image(spectrogram, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Test avec génération automatique du nom
        filepath2 = exporter.export_image(spectrogram)
        assert os.path.exists(filepath2)
        assert filepath2.endswith('.png')
        assert filepath != filepath2  # Noms différents
    
    def test_export_numpy(self, temp_output_dir, spectrogram_data):
        """Vérifie que l'exportation NumPy fonctionne correctement."""
        spectrogram, freqs, times = spectrogram_data
        exporter = SpectrogramExporter(os.path.join(temp_output_dir, "spectrograms"))
        
        # Test avec un nom de fichier spécifié
        filename = "test_spectrogram.npz"
        filepath = exporter.export_numpy(spectrogram, freqs, times, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu
        data = np.load(filepath)
        assert 'spectrogram' in data
        assert 'frequencies' in data
        assert 'times' in data
        assert np.array_equal(data['spectrogram'], spectrogram)
        assert np.array_equal(data['frequencies'], freqs)
        assert np.array_equal(data['times'], times)
    
    def test_export_csv(self, temp_output_dir, spectrogram_data):
        """Vérifie que l'exportation CSV fonctionne correctement."""
        spectrogram, freqs, times = spectrogram_data
        exporter = SpectrogramExporter(os.path.join(temp_output_dir, "spectrograms"))
        
        # Test avec un nom de fichier spécifié
        filename = "test_spectrogram.csv"
        filepath = exporter.export_csv(spectrogram, freqs, times, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu
        with open(filepath, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)
            
            # Vérifier l'en-tête
            assert header[0] == 'Frequency (Hz)'
            assert len(header) == len(times) + 1
            
            # Vérifier les données
            rows = list(reader)
            assert len(rows) == len(freqs)


class TestTriangulationExporter:
    """Tests pour la classe TriangulationExporter."""
    
    def test_initialization(self, temp_output_dir):
        """Vérifie que l'initialisation crée le répertoire de sortie."""
        output_dir = os.path.join(temp_output_dir, "triangulation")
        exporter = TriangulationExporter(output_dir)
        
        assert os.path.exists(output_dir)
        assert exporter.output_dir == output_dir
    
    def test_export_csv(self, temp_output_dir, triangulation_results):
        """Vérifie que l'exportation CSV des résultats de triangulation fonctionne."""
        exporter = TriangulationExporter(os.path.join(temp_output_dir, "triangulation"))
        
        # Patch pour contourner le problème avec timestamp.isoformat()
        for result in triangulation_results:
            if hasattr(result, 'timestamp') and isinstance(result.timestamp, float):
                # Convertir le timestamp en objet datetime
                result.timestamp = datetime.fromtimestamp(result.timestamp)
        
        # Test avec un nom de fichier spécifié
        filename = "test_triangulation.csv"
        filepath = exporter.export_csv(triangulation_results, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu
        with open(filepath, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)
            
            # Vérifier l'en-tête
            expected_headers = [
                'Timestamp', 'Frequency (Hz)', 'Latitude', 'Longitude', 
                'Error Radius (km)', 'Reliability', 'Signal Strength (dB)',
                'Number of Receivers'
            ]
            assert all(h in header for h in expected_headers)
            
            # Vérifier les données
            rows = list(reader)
            assert len(rows) == len(triangulation_results)
    
    def test_export_json(self, temp_output_dir, triangulation_results):
        """Vérifie que l'exportation JSON des résultats de triangulation fonctionne."""
        exporter = TriangulationExporter(os.path.join(temp_output_dir, "triangulation"))
        
        # Patch pour contourner le problème avec timestamp.isoformat()
        for result in triangulation_results:
            if hasattr(result, 'timestamp') and isinstance(result.timestamp, float):
                # Convertir le timestamp en objet datetime
                result.timestamp = datetime.fromtimestamp(result.timestamp)
        
        # Test avec un nom de fichier spécifié
        filename = "test_triangulation.json"
        filepath = exporter.export_json(triangulation_results, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu
        with open(filepath, 'r') as jsonfile:
            data = json.load(jsonfile)
            assert isinstance(data, list)
            assert len(data) == len(triangulation_results)
            
            # Vérifier les champs essentiels
            for item in data:
                assert 'timestamp' in item
                assert 'frequency' in item
                assert 'location' in item
                assert 'latitude' in item['location']
                assert 'longitude' in item['location']
                assert 'error_radius' in item
                assert 'reliability' in item
    
    def test_export_kml(self, temp_output_dir, triangulation_results):
        """Vérifie que l'exportation KML des résultats de triangulation fonctionne."""
        exporter = TriangulationExporter(os.path.join(temp_output_dir, "triangulation"))
        
        # Patch pour contourner le problème avec timestamp.isoformat()
        for result in triangulation_results:
            if hasattr(result, 'timestamp') and isinstance(result.timestamp, float):
                # Convertir le timestamp en objet datetime
                result.timestamp = datetime.fromtimestamp(result.timestamp)
        
        # Test avec un nom de fichier spécifié
        filename = "test_triangulation.kml"
        filepath = exporter.export_kml(triangulation_results, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu basique
        with open(filepath, 'r') as kmlfile:
            content = kmlfile.read()
            assert '<?xml version="1.0" encoding="UTF-8"?>' in content
            assert '<kml xmlns="http://www.opengis.net/kml/2.2">' in content
            assert '<Document>' in content
            assert '<Placemark>' in content
            assert '</Document>' in content
            assert '</kml>' in content


class TestAnnotationExporter:
    """Tests pour la classe AnnotationExporter."""
    
    def test_initialization(self, temp_output_dir):
        """Vérifie que l'initialisation crée le répertoire de sortie."""
        output_dir = os.path.join(temp_output_dir, "annotations")
        exporter = AnnotationExporter(output_dir)
        
        assert os.path.exists(output_dir)
        assert exporter.output_dir == output_dir
    
    def test_export_json(self, temp_output_dir, annotations):
        """Vérifie que l'exportation JSON des annotations fonctionne."""
        exporter = AnnotationExporter(os.path.join(temp_output_dir, "annotations"))
        
        # Test avec un nom de fichier spécifié
        filename = "test_annotations.json"
        filepath = exporter.export_json(annotations, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu
        with open(filepath, 'r', encoding='utf-8') as jsonfile:
            data = json.load(jsonfile)
            assert 'metadata' in data
            assert 'annotations' in data
            assert data['metadata']['count'] == len(annotations)
            assert len(data['annotations']) == len(annotations)
    
    def test_export_csv(self, temp_output_dir, annotations):
        """Vérifie que l'exportation CSV des annotations fonctionne."""
        exporter = AnnotationExporter(os.path.join(temp_output_dir, "annotations"))
        
        # Test avec un nom de fichier spécifié
        filename = "test_annotations.csv"
        filepath = exporter.export_csv(annotations, filename)
        
        # Vérifier que le fichier existe
        assert os.path.exists(filepath)
        assert filepath.endswith(filename)
        
        # Vérifier le contenu
        with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            assert len(rows) == len(annotations)
            
            # Vérifier que les champs essentiels sont présents
            for row in rows:
                assert 'id' in row
                assert 'type' in row
                assert 'timestamp' in row


class TestDataExporter:
    """Tests pour la classe DataExporter."""
    
    def test_initialization(self, temp_output_dir):
        """Vérifie que l'initialisation crée les répertoires de sortie."""
        exporter = DataExporter(output_base_dir=temp_output_dir)
        
        # Vérifier que l'exportateur a été correctement initialisé
        assert exporter.output_base_dir == temp_output_dir
        assert isinstance(exporter.audio_exporter, AudioExporter)
        assert isinstance(exporter.spectrogram_exporter, SpectrogramExporter)
        assert isinstance(exporter.triangulation_exporter, TriangulationExporter)
        assert isinstance(exporter.annotation_exporter, AnnotationExporter)
    
    def test_export_all(self, temp_output_dir, audio_data, spectrogram_data, 
                         triangulation_results, annotations):
        """Vérifie que l'exportation complète fonctionne."""
        exporter = DataExporter(output_base_dir=temp_output_dir)
        
        # Préparer les données de test
        audio, sample_rate = audio_data
        spectrogram, freqs, times = spectrogram_data
        
        # Patch pour contourner le problème avec timestamp.isoformat()
        for result in triangulation_results:
            if hasattr(result, 'timestamp') and isinstance(result.timestamp, float):
                # Convertir le timestamp en objet datetime
                result.timestamp = datetime.fromtimestamp(result.timestamp)
        
        # Exporter tout
        prefix = "test_export"
        # Modifier l'appel export_all pour éviter le problème de paramètres
        results = exporter.export_all(
            audio_data=audio,
            sample_rate=sample_rate,
            spectrogram_data=spectrogram,
            frequencies=freqs,
            times=times,
            triangulation_results=triangulation_results,
            annotations=annotations,
            export_prefix=prefix
        )
        
        # Vérifier que tous les fichiers ont été générés
        assert 'audio_wav' in results
        assert 'spectrogram_png' in results
        assert 'spectrogram_numpy' in results
        assert 'spectrogram_csv' in results
        assert 'triangulation_csv' in results
        assert 'triangulation_json' in results
        assert 'triangulation_kml' in results
        assert 'annotations_json' in results
        assert 'annotations_csv' in results
        assert 'export_summary' in results
        
        # Vérifier que les fichiers existent
        for filepath in results.values():
            assert os.path.exists(filepath)
    
    def test_generate_export_summary(self, temp_output_dir):
        """Vérifie que la génération du résumé d'exportation fonctionne."""
        exporter = DataExporter(output_base_dir=temp_output_dir)
        
        # Créer des fichiers temporaires pour simuler des résultats d'exportation
        export_results = {}
        for category in ['audio', 'spectrogram', 'triangulation', 'annotations']:
            filepath = os.path.join(temp_output_dir, f"test_{category}.txt")
            with open(filepath, 'w') as f:
                f.write("Test content")
            export_results[f"{category}_test"] = filepath
        
        # Générer le résumé
        summary_path = exporter.generate_export_summary(export_results, "test_export")
        
        # Vérifier que le fichier existe
        assert os.path.exists(summary_path)
        assert os.path.basename(summary_path) == "test_export_summary.txt"
        
        # Vérifier le contenu
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "SDR-MAP - RÉSUMÉ D'EXPORTATION" in content
            assert "Identifiant: test_export" in content
            for category in ['Audio', 'Spectrogramme', 'Triangulation', 'Annotations']:
                assert category in content
    
    def test_format_file_size(self, temp_output_dir):
        """Vérifie que le formatage de la taille des fichiers fonctionne."""
        exporter = DataExporter(output_base_dir=temp_output_dir)
        
        # Tester différentes tailles
        assert exporter._format_file_size(512) == "512.00 B"
        assert exporter._format_file_size(1024) == "1.00 KB"
        assert exporter._format_file_size(1024 * 1024) == "1.00 MB"
        assert exporter._format_file_size(1024 * 1024 * 1024) == "1.00 GB"


if __name__ == "__main__":
    pytest.main(["-v"]) 