"""
Module data_export.py pour l'exportation des données.

Ce module implémente:
- Exportation des données audio (WAV)
- Exportation des données de spectrogramme
- Sauvegarde des données de triangulation (CSV, JSON)
- Exportation des annotations utilisateur
"""

import os
import json
import csv
import wave
import time
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, BinaryIO

import numpy as np
# Configure matplotlib to use a non-GUI backend when needed
import sys
import matplotlib
if 'pytest' in sys.modules or not os.environ.get('DISPLAY'):
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

from src.utils.logger import get_logger
from src.signal_processing.triangulation import TriangulationResult, Location, ReliabilityLevel

# Configuration du logger
logger = get_logger(__name__)


class AudioExporter:
    """
    Exportateur de données audio.
    
    Cette classe gère l'exportation des données audio capturées
    vers des fichiers WAV.
    """
    
    def __init__(self, output_dir: str = "exports/audio"):
        """
        Initialise l'exportateur audio.
        
        Args:
            output_dir: Répertoire de sortie pour les fichiers audio
        """
        self.output_dir = output_dir
        self._ensure_output_dir_exists()
    
    def _ensure_output_dir_exists(self) -> None:
        """Assure que le répertoire de sortie existe."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_wav(self, audio_data: np.ndarray, sample_rate: int, 
                   filename: Optional[str] = None) -> str:
        """
        Exporte des données audio en format WAV.
        
        Args:
            audio_data: Données audio à exporter
            sample_rate: Taux d'échantillonnage des données
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .wav
        if not filename.lower().endswith('.wav'):
            filename += '.wav'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        # Normaliser les données audio entre -32768 et 32767 (16 bits)
        if audio_data.dtype != np.int16:
            if np.max(np.abs(audio_data)) > 0:
                # Normaliser seulement si les données ne sont pas nulles
                normalized_data = audio_data / np.max(np.abs(audio_data))
                audio_int16 = (normalized_data * 32767).astype(np.int16)
            else:
                audio_int16 = np.zeros_like(audio_data, dtype=np.int16)
        else:
            audio_int16 = audio_data
        
        try:
            # Écrire le fichier WAV
            with wave.open(filepath, 'wb') as wav_file:
                # Configurer les paramètres WAV
                nchannels = 1  # Mono
                sampwidth = 2  # 2 octets = 16 bits
                
                wav_file.setparams((nchannels, sampwidth, sample_rate, 
                                   len(audio_int16), 'NONE', 'not compressed'))
                wav_file.writeframes(audio_int16.tobytes())
            
            logger.info(f"Fichier audio exporté avec succès: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation du fichier audio: {e}")
            raise


class SpectrogramExporter:
    """
    Exportateur de données de spectrogramme.
    
    Cette classe gère l'exportation des données de spectrogramme générées
    vers différents formats (image, NumPy, CSV).
    """
    
    def __init__(self, output_dir: str = "exports/spectrograms"):
        """
        Initialise l'exportateur de spectrogrammes.
        
        Args:
            output_dir: Répertoire de sortie pour les fichiers de spectrogramme
        """
        self.output_dir = output_dir
        self._ensure_output_dir_exists()
    
    def _ensure_output_dir_exists(self) -> None:
        """Assure que le répertoire de sortie existe."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_image(self, spectrogram_data: np.ndarray, 
                     filename: Optional[str] = None, 
                     colormap: str = "inferno") -> str:
        """
        Exporte un spectrogramme en tant qu'image PNG.
        
        Args:
            spectrogram_data: Données du spectrogramme (2D ou 3D pour RGBA)
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            colormap: Nom de la colormap à utiliser si les données ne sont pas déjà en RGBA
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"spectrogram_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .png
        if not filename.lower().endswith('.png'):
            filename += '.png'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Vérifier si les données sont déjà en RGBA
            if len(spectrogram_data.shape) == 3 and spectrogram_data.shape[2] in [3, 4]:
                # Cas d'une image déjà colorée (RGB ou RGBA)
                # Convertir en valeurs 0-255 si nécessaire
                if spectrogram_data.dtype != np.uint8:
                    if np.max(spectrogram_data) <= 1.0:
                        image_data = (spectrogram_data * 255).astype(np.uint8)
                    else:
                        image_data = np.clip(spectrogram_data, 0, 255).astype(np.uint8)
                else:
                    image_data = spectrogram_data
                
                # Créer l'image
                img = Image.fromarray(image_data)
                
            else:
                # Cas d'un spectrogramme en 2D (intensité seulement)
                # Normaliser les données entre 0 et 1
                if np.max(spectrogram_data) > 1.0 or np.min(spectrogram_data) < 0.0:
                    vmin = np.min(spectrogram_data)
                    vmax = np.max(spectrogram_data)
                    normalized_data = (spectrogram_data - vmin) / (vmax - vmin) if vmax > vmin else spectrogram_data
                else:
                    normalized_data = spectrogram_data
                
                # Créer la visualisation du spectrogramme
                plt.figure(figsize=(10, 6))
                plt.imshow(normalized_data, aspect='auto', cmap=colormap, origin='lower')
                plt.axis('off')  # Masquer les axes
                plt.tight_layout(pad=0)
                
                # Sauvegarder l'image
                plt.savefig(filepath, dpi=150, bbox_inches='tight', pad_inches=0)
                plt.close()
                
                # Retourner directement car l'image est déjà sauvegardée
                logger.info(f"Spectrogramme exporté avec succès en tant qu'image: {filepath}")
                return filepath
            
            # Sauvegarder l'image (cas RGBA)
            img.save(filepath)
            logger.info(f"Spectrogramme exporté avec succès en tant qu'image: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation du spectrogramme en image: {e}")
            raise
    
    def export_numpy(self, spectrogram_data: np.ndarray, freq_data: np.ndarray,
                     time_data: np.ndarray, filename: Optional[str] = None) -> str:
        """
        Exporte un spectrogramme en tant que fichier NumPy (.npz).
        
        Args:
            spectrogram_data: Données du spectrogramme
            freq_data: Données de fréquence associées
            time_data: Données temporelles associées
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"spectrogram_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .npz
        if not filename.lower().endswith('.npz'):
            filename += '.npz'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Sauvegarder les données en format .npz (compressé)
            np.savez_compressed(
                filepath,
                spectrogram=spectrogram_data,
                frequencies=freq_data,
                times=time_data,
                metadata={
                    'date': datetime.datetime.now().isoformat(),
                    'shape': spectrogram_data.shape
                }
            )
            
            logger.info(f"Spectrogramme exporté avec succès en format NumPy: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation en format NumPy: {e}")
            raise
    
    def export_csv(self, spectrogram_data: np.ndarray, freq_data: np.ndarray,
                  time_data: np.ndarray, filename: Optional[str] = None) -> str:
        """
        Exporte un spectrogramme en tant que fichier CSV.
        
        Args:
            spectrogram_data: Données du spectrogramme
            freq_data: Données de fréquence associées
            time_data: Données temporelles associées
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"spectrogram_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .csv
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Ouvrir le fichier CSV pour écriture
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Écrire l'en-tête avec les temps
                header = ['Frequency (Hz)'] + [f'{t:.2f}' for t in time_data]
                writer.writerow(header)
                
                # Écrire les données du spectrogramme
                for i, freq in enumerate(freq_data):
                    row = [f'{freq:.2f}'] + [f'{val:.6f}' for val in spectrogram_data[i]]
                    writer.writerow(row)
            
            logger.info(f"Spectrogramme exporté avec succès en format CSV: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation en format CSV: {e}")
            raise


class TriangulationExporter:
    """
    Exportateur de données de triangulation.
    
    Cette classe gère l'exportation des résultats de triangulation
    vers différents formats (CSV, JSON, KML).
    """
    
    def __init__(self, output_dir: str = "exports/triangulation"):
        """
        Initialise l'exportateur de triangulation.
        
        Args:
            output_dir: Répertoire de sortie pour les fichiers de triangulation
        """
        self.output_dir = output_dir
        self._ensure_output_dir_exists()
    
    def _ensure_output_dir_exists(self) -> None:
        """Assure que le répertoire de sortie existe."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_csv(self, triangulation_results: List[TriangulationResult],
                   filename: Optional[str] = None) -> str:
        """
        Exporte les résultats de triangulation en format CSV.
        
        Args:
            triangulation_results: Liste des résultats de triangulation
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"triangulation_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .csv
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Ouvrir le fichier CSV pour écriture
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Écrire l'en-tête
                header = [
                    'Timestamp', 'Frequency (Hz)', 'Latitude', 'Longitude', 
                    'Error Radius (km)', 'Reliability', 'Signal Strength (dB)',
                    'Number of Receivers'
                ]
                writer.writerow(header)
                
                # Écrire les données pour chaque résultat
                for result in triangulation_results:
                    row = [
                        # Formater le timestamp ISO
                        result.timestamp.isoformat() if hasattr(result, 'timestamp') else 
                        datetime.datetime.now().isoformat(),
                        
                        # Fréquence
                        result.frequency if hasattr(result, 'frequency') else 0,
                        
                        # Position
                        result.estimated_location.latitude,
                        result.estimated_location.longitude,
                        
                        # Rayon d'erreur
                        result.error_radius,
                        
                        # Fiabilité
                        result.reliability.name if result.reliability else "UNKNOWN",
                        
                        # Force du signal
                        result.signal_strength if hasattr(result, 'signal_strength') else "N/A",
                        
                        # Nombre de récepteurs
                        len(result.receiver_locations) if hasattr(result, 'receiver_locations') else 0
                    ]
                    writer.writerow(row)
            
            logger.info(f"Résultats de triangulation exportés avec succès en CSV: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation en CSV: {e}")
            raise
    
    def export_json(self, triangulation_results: List[TriangulationResult],
                    filename: Optional[str] = None, pretty: bool = True) -> str:
        """
        Exporte les résultats de triangulation en format JSON.
        
        Args:
            triangulation_results: Liste des résultats de triangulation
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            pretty: Ajouter une indentation pour faciliter la lecture
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"triangulation_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .json
        if not filename.lower().endswith('.json'):
            filename += '.json'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Convertir les objets en dictionnaires
            results_data = []
            for result in triangulation_results:
                result_dict = {
                    'timestamp': result.timestamp.isoformat() if hasattr(result, 'timestamp') else
                                 datetime.datetime.now().isoformat(),
                    'frequency': result.frequency if hasattr(result, 'frequency') else 0,
                    'location': {
                        'latitude': result.estimated_location.latitude,
                        'longitude': result.estimated_location.longitude
                    },
                    'error_radius': result.error_radius,
                    'reliability': result.reliability.name if result.reliability else "UNKNOWN",
                    'signal_strength': result.signal_strength if hasattr(result, 'signal_strength') else None
                }
                
                # Ajouter les données des récepteurs si disponibles
                if hasattr(result, 'receiver_locations'):
                    receivers = []
                    for recv_name, recv_loc in result.receiver_locations.items():
                        recv_dict = {
                            'name': recv_name,
                            'location': {
                                'latitude': recv_loc.latitude if isinstance(recv_loc, Location) else 0,
                                'longitude': recv_loc.longitude if isinstance(recv_loc, Location) else 0
                            },
                            'rssi': result.rssi_values.get(recv_name, 0) if hasattr(result, 'rssi_values') else 0
                        }
                        receivers.append(recv_dict)
                    
                    result_dict['receiver_locations'] = receivers
                
                results_data.append(result_dict)
            
            # Écrire le fichier JSON
            with open(filepath, 'w') as jsonfile:
                indent = 2 if pretty else None
                json.dump(results_data, jsonfile, indent=indent)
            
            logger.info(f"Résultats de triangulation exportés avec succès en JSON: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation en JSON: {e}")
            raise
            
    def export_kml(self, triangulation_results: List[TriangulationResult],
                  filename: Optional[str] = None) -> str:
        """
        Exporte les résultats de triangulation en format KML pour Google Earth.
        
        Args:
            triangulation_results: Liste des résultats de triangulation
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"triangulation_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .kml
        if not filename.lower().endswith('.kml'):
            filename += '.kml'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Créer le contenu KML
            kml = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<kml xmlns="http://www.opengis.net/kml/2.2">',
                '<Document>',
                '<name>SDR Triangulation Results</name>',
                '<description>Exported triangulation results</description>'
            ]
            
            # Définir des styles pour les différents niveaux de fiabilité
            reliability_styles = {
                'HIGH': {'color': 'ff00ff00', 'scale': '1.2'},  # Vert
                'MEDIUM': {'color': 'ff00ffff', 'scale': '1.0'},  # Jaune
                'LOW': {'color': 'ff0000ff', 'scale': '0.8'},  # Rouge
                'UNKNOWN': {'color': 'ff888888', 'scale': '0.6'}  # Gris
            }
            
            # Ajouter les styles
            for rel, style in reliability_styles.items():
                kml.append(f'<Style id="{rel.lower()}_style">')
                kml.append('  <IconStyle>')
                kml.append(f'    <color>{style["color"]}</color>')
                kml.append(f'    <scale>{style["scale"]}</scale>')
                kml.append('    <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>')
                kml.append('  </IconStyle>')
                kml.append('  <LabelStyle>')
                kml.append('    <scale>0.8</scale>')
                kml.append('  </LabelStyle>')
                kml.append('</Style>')
            
            # Ajouter chaque point de triangulation
            for i, result in enumerate(triangulation_results):
                rel = result.reliability.name if result.reliability else "UNKNOWN"
                freq = result.frequency if hasattr(result, 'frequency') else 0
                timestamp = result.timestamp.isoformat() if hasattr(result, 'timestamp') else datetime.datetime.now().isoformat()
                
                kml.append('<Placemark>')
                kml.append(f'  <name>Signal {i+1}: {freq/1000:.3f} kHz</name>')
                kml.append('  <description>')
                kml.append(f'    <![CDATA[')
                kml.append(f'    <p><b>Frequency:</b> {freq/1000:.3f} kHz</p>')
                kml.append(f'    <p><b>Timestamp:</b> {timestamp}</p>')
                kml.append(f'    <p><b>Error Radius:</b> {result.error_radius:.2f} km</p>')
                kml.append(f'    <p><b>Reliability:</b> {rel}</p>')
                
                if hasattr(result, 'signal_strength'):
                    kml.append(f'    <p><b>Signal Strength:</b> {result.signal_strength} dB</p>')
                
                kml.append(f'    ]]>')
                kml.append('  </description>')
                kml.append(f'  <styleUrl>#{rel.lower()}_style</styleUrl>')
                kml.append('  <Point>')
                kml.append(f'    <coordinates>{result.estimated_location.longitude},{result.estimated_location.latitude},0</coordinates>')
                kml.append('  </Point>')
                
                # Ajouter un cercle représentant la marge d'erreur
                kml.append('  <LineString>')
                kml.append('    <tessellate>1</tessellate>')
                kml.append('    <coordinates>')
                
                # Créer un cercle avec 36 points
                import math
                radius_deg = result.error_radius / 111.32  # Conversion approximative km -> degrés
                for degree in range(0, 360, 10):
                    rad = math.radians(degree)
                    lat = result.estimated_location.latitude + radius_deg * math.sin(rad)
                    lon = result.estimated_location.longitude + radius_deg * math.cos(rad) / math.cos(math.radians(result.estimated_location.latitude))
                    kml.append(f'      {lon},{lat},0')
                
                # Fermer le cercle
                kml.append(f'      {result.estimated_location.longitude + radius_deg},{result.estimated_location.latitude},0')
                kml.append('    </coordinates>')
                kml.append('  </LineString>')
                kml.append('</Placemark>')
            
            # Fermer le document KML
            kml.append('</Document>')
            kml.append('</kml>')
            
            # Écrire le fichier KML
            with open(filepath, 'w') as kmlfile:
                kmlfile.write('\n'.join(kml))
            
            logger.info(f"Résultats de triangulation exportés avec succès en KML: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation en KML: {e}")
            raise


class AnnotationExporter:
    """
    Exportateur d'annotations utilisateur.
    
    Cette classe gère l'exportation des annotations créées par l'utilisateur
    (marqueurs, notes, régions d'intérêt, etc.).
    """
    
    def __init__(self, output_dir: str = "exports/annotations"):
        """
        Initialise l'exportateur d'annotations.
        
        Args:
            output_dir: Répertoire de sortie pour les fichiers d'annotations
        """
        self.output_dir = output_dir
        self._ensure_output_dir_exists()
    
    def _ensure_output_dir_exists(self) -> None:
        """Assure que le répertoire de sortie existe."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_json(self, annotations: List[Dict[str, Any]],
                    filename: Optional[str] = None, pretty: bool = True) -> str:
        """
        Exporte les annotations utilisateur en format JSON.
        
        Args:
            annotations: Liste des annotations à exporter
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            pretty: Ajouter une indentation pour faciliter la lecture
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"annotations_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .json
        if not filename.lower().endswith('.json'):
            filename += '.json'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Ajouter des métadonnées aux annotations
            export_data = {
                'metadata': {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'count': len(annotations),
                    'version': '1.0'
                },
                'annotations': annotations
            }
            
            # Écrire le fichier JSON
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                indent = 2 if pretty else None
                json.dump(export_data, jsonfile, indent=indent, ensure_ascii=False)
            
            logger.info(f"Annotations exportées avec succès en JSON: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation des annotations: {e}")
            raise
    
    def export_csv(self, annotations: List[Dict[str, Any]], 
                   filename: Optional[str] = None) -> str:
        """
        Exporte les annotations utilisateur en format CSV.
        
        Args:
            annotations: Liste des annotations à exporter
            filename: Nom du fichier (sans extension) ou None pour générer automatiquement
            
        Returns:
            Chemin complet du fichier sauvegardé
        """
        # Générer un nom de fichier si non spécifié
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"annotations_{timestamp}"
        
        # Assurer que le nom de fichier a l'extension .csv
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        # Chemin complet du fichier
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Créer l'ensemble des en-têtes à partir de toutes les annotations
            headers = set(['id', 'type', 'timestamp'])
            for annotation in annotations:
                headers.update(annotation.keys())
            
            headers = sorted(list(headers))
            
            # Écrire le fichier CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                
                # Écrire chaque annotation
                for annotation in annotations:
                    # Ajouter un timestamp s'il n'existe pas
                    if 'timestamp' not in annotation:
                        annotation['timestamp'] = datetime.datetime.now().isoformat()
                    
                    # Écrire la ligne
                    writer.writerow(annotation)
            
            logger.info(f"Annotations exportées avec succès en CSV: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exportation des annotations en CSV: {e}")
            raise


class DataExporter:
    """
    Gestionnaire central d'exportation de données.
    
    Cette classe coordonne l'exportation de tous les types de données
    (audio, spectrogramme, triangulation, annotations).
    """
    
    def __init__(self, output_base_dir: str = 'exports'):
        """
        Initialise le gestionnaire d'exportation.
        
        Args:
            output_base_dir: Répertoire de base pour toutes les exportations
        """
        self.output_base_dir = output_base_dir
        self.audio_exporter = AudioExporter(os.path.join(output_base_dir, 'audio'))
        self.spectrogram_exporter = SpectrogramExporter(os.path.join(output_base_dir, 'spectrograms'))
        self.triangulation_exporter = TriangulationExporter(os.path.join(output_base_dir, 'triangulation'))
        self.annotation_exporter = AnnotationExporter(os.path.join(output_base_dir, 'annotations'))
        
        # Options de configuration
        self.audio_format = 'wav'
        self.enable_audio_export = True
        self.enable_spectrum_export = True
        self.enable_triangulation_export = True
        
        # Créer le répertoire de base
        os.makedirs(output_base_dir, exist_ok=True)
        
    def configure(self, output_dir=None, audio_format=None, 
                  enable_audio_export=None, enable_spectrum_export=None, 
                  enable_triangulation_export=None):
        """Configure les options d'exportation"""
        if output_dir:
            self.output_base_dir = output_dir
            self.audio_exporter.output_dir = os.path.join(output_dir, 'audio')
            self.spectrogram_exporter.output_dir = os.path.join(output_dir, 'spectrograms')
            self.triangulation_exporter.output_dir = os.path.join(output_dir, 'triangulation')
            self.annotation_exporter.output_dir = os.path.join(output_dir, 'annotations')
            os.makedirs(output_dir, exist_ok=True)
            
        if audio_format:
            self.audio_format = audio_format
            
        if enable_audio_export is not None:
            self.enable_audio_export = enable_audio_export
            
        if enable_spectrum_export is not None:
            self.enable_spectrum_export = enable_spectrum_export
            
        if enable_triangulation_export is not None:
            self.enable_triangulation_export = enable_triangulation_export
    
    def export_all(self, audio_data: np.ndarray, sample_rate: int, 
                  spectrogram_data: np.ndarray, frequencies: np.ndarray, 
                  times: np.ndarray, triangulation_results: List[TriangulationResult],
                  annotations: List[Dict[str, Any]], export_prefix: str = None) -> Dict[str, str]:
        """
        Exporte toutes les données dans leurs formats respectifs.
        
        Args:
            audio_data: Données audio à exporter
            sample_rate: Taux d'échantillonnage de l'audio
            spectrogram_data: Données du spectrogramme
            frequencies: Tableau des fréquences du spectrogramme
            times: Tableau des temps du spectrogramme
            triangulation_results: Résultats de triangulation
            annotations: Annotations utilisateur
            export_prefix: Préfixe pour les noms de fichiers
            
        Returns:
            Dictionnaire avec les chemins de tous les fichiers exportés
        """
        # Générer un préfixe de fichier si non spécifié
        if export_prefix is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            export_prefix = f"export_{timestamp}"
        
        results = {}
        
        # Exporter l'audio
        if self.enable_audio_export:
            wav_path = self.audio_exporter.export_wav(
                audio_data, sample_rate, filename=f"{export_prefix}_audio"
            )
            results['audio_wav'] = wav_path
        
        # Exporter le spectrogramme
        if self.enable_spectrum_export:
            png_path = self.spectrogram_exporter.export_image(
                spectrogram_data, filename=f"{export_prefix}_spectrogram"
            )
            results['spectrogram_png'] = png_path
            
            npy_path = self.spectrogram_exporter.export_numpy(
                spectrogram_data, frequencies, times, filename=f"{export_prefix}_spectrogram"
            )
            results['spectrogram_numpy'] = npy_path
            
            csv_path = self.spectrogram_exporter.export_csv(
                spectrogram_data, frequencies, times, filename=f"{export_prefix}_spectrogram"
            )
            results['spectrogram_csv'] = csv_path
        
        # Exporter les données de triangulation
        if self.enable_triangulation_export and triangulation_results:
            csv_path = self.triangulation_exporter.export_csv(
                triangulation_results, filename=f"{export_prefix}_triangulation"
            )
            results['triangulation_csv'] = csv_path
            
            json_path = self.triangulation_exporter.export_json(
                triangulation_results, filename=f"{export_prefix}_triangulation"
            )
            results['triangulation_json'] = json_path
            
            kml_path = self.triangulation_exporter.export_kml(
                triangulation_results, filename=f"{export_prefix}_triangulation"
            )
            results['triangulation_kml'] = kml_path
        
        # Exporter les annotations
        if annotations:
            anno_json_path = self.annotation_exporter.export_json(
                annotations, filename=f"{export_prefix}_annotations"
            )
            results['annotations_json'] = anno_json_path
            
            anno_csv_path = self.annotation_exporter.export_csv(
                annotations, filename=f"{export_prefix}_annotations"
            )
            results['annotations_csv'] = anno_csv_path
        
        # Générer un résumé de l'exportation
        summary_path = self.generate_export_summary(results, export_prefix)
        results['export_summary'] = summary_path
        
        logger.info(f"Exportation complète terminée. {len(results)} fichiers exportés.")
        return results
    
    def generate_export_summary(self, export_results: Dict[str, str], 
                               export_prefix: str) -> str:
        """
        Génère un fichier résumé de l'exportation.
        
        Args:
            export_results: Dictionnaire des résultats d'exportation
            export_prefix: Préfixe utilisé pour l'exportation
            
        Returns:
            Chemin du fichier résumé
        """
        # Nom du fichier résumé
        summary_filename = f"{export_prefix}_summary.txt"
        summary_path = os.path.join(self.output_base_dir, summary_filename)
        
        # S'assurer que le répertoire existe
        os.makedirs(self.output_base_dir, exist_ok=True)
        
        try:
            with open(summary_path, 'w', encoding='utf-8') as summary_file:
                # Écrire l'en-tête
                summary_file.write(f"SDR-MAP - RÉSUMÉ D'EXPORTATION\n")
                summary_file.write(f"Date: {datetime.datetime.now().isoformat()}\n")
                summary_file.write(f"Identifiant: {export_prefix}\n\n")
                
                # Organiser les résultats par catégorie
                categories = {
                    'Audio': [k for k in export_results.keys() if k.startswith('audio_')],
                    'Spectrogramme': [k for k in export_results.keys() if k.startswith('spectrogram_')],
                    'Triangulation': [k for k in export_results.keys() if k.startswith('triangulation_')],
                    'Annotations': [k for k in export_results.keys() if k.startswith('annotations_')],
                    'Autre': [k for k in export_results.keys() if not any(
                        k.startswith(prefix) for prefix in ['audio_', 'spectrogram_', 'triangulation_', 'annotations_']
                    )]
                }
                
                # Écrire les fichiers par catégorie
                for category, keys in categories.items():
                    if keys:
                        summary_file.write(f"\n{category}:\n")
                        for key in keys:
                            file_path = export_results[key]
                            file_size = os.path.getsize(file_path)
                            file_size_str = self._format_file_size(file_size)
                            summary_file.write(f"  - {os.path.basename(file_path)} ({file_size_str})\n")
                
                # Ajouter des notes d'utilisation
                summary_file.write("\nNotes d'utilisation:\n")
                summary_file.write("  - Les fichiers audio sont au format WAV\n")
                summary_file.write("  - Les spectrogrammes sont exportés en PNG (visualisation) et NPY (données)\n")
                summary_file.write("  - Les résultats de triangulation sont en CSV, JSON et KML (Google Earth)\n")
                summary_file.write("  - Les annotations sont en formats JSON et CSV\n\n")
                
                # Ajouter un total
                total_size = sum(os.path.getsize(path) for path in export_results.values())
                summary_file.write(f"Taille totale des fichiers exportés: {self._format_file_size(total_size)}\n")
            
            logger.info(f"Résumé d'exportation généré: {summary_path}")
            return summary_path
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du résumé: {e}")
            raise
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        Formate la taille du fichier en unités lisibles.
        
        Args:
            size_bytes: Taille en octets
            
        Returns:
            Chaîne formatée (ex: "4.2 MB")
        """
        # Définir les suffixes
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
        
        # Déterminer l'indice du suffixe
        i = 0
        while size_bytes >= 1024 and i < len(suffixes) - 1:
            size_bytes /= 1024
            i += 1
        
        # Formater la chaîne
        return f"{size_bytes:.2f} {suffixes[i]}"
    
    def export_signal_detection(self, signal, receiver_name=None):
        """Exporte les informations d'un signal détecté"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"signal_{signal.frequency/1e6:.3f}MHz_{timestamp}"
        
        # Créer un fichier JSON avec les métadonnées du signal
        data = {
            "frequency": signal.frequency,
            "bandwidth": signal.bandwidth,
            "power": signal.power,
            "snr": signal.snr,
            "type": signal.signal_type.value,
            "confidence": signal.confidence,
            "timestamp": signal.timestamp,
            "duration": signal.duration,
            "is_active": signal.is_active
        }
        
        if receiver_name:
            data["receiver"] = receiver_name
            
        # Exporter en JSON
        filepath = os.path.join(self.output_base_dir, "signals", f"{filename}.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
        return filepath
    
    def export_audio(self, audio_data, frequency, receiver_name=None, sample_rate=12000):
        """Exporte des données audio pour un signal spécifique"""
        if not self.enable_audio_export:
            return None
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{frequency/1e6:.3f}MHz_{timestamp}"
        
        if receiver_name:
            filename += f"_{receiver_name}"
            
        return self.audio_exporter.export_wav(audio_data, sample_rate, filename)
    
    def export_spectrum_data(self, signal):
        """Exporte le spectre d'un signal détecté"""
        if not self.enable_spectrum_export:
            return None
            
        # Cette méthode est un placeholder - elle nécessiterait les données de spectre
        # qui ne sont pas directement disponibles dans l'objet signal
        logger.warning("export_spectrum_data appelé sans données de spectre")
        return None
    
    def export_triangulation(self, result):
        """Exporte un résultat de triangulation"""
        if not self.enable_triangulation_export:
            return None
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"triangulation_{result.signal_frequency/1e6:.3f}MHz_{timestamp}"
        
        return self.triangulation_exporter.export_json([result], filename)
    
    def flush(self):
        """Finalise toutes les opérations d'export en cours (si applicable)"""
        logger.info("Finalisation des exports en cours")
        # Cette méthode peut être étendue si certains exportateurs
        # ont besoin de finaliser des opérations (fermer des fichiers, etc.) 