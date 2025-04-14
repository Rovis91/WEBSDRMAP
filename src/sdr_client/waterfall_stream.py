"""
Module de gestion des flux waterfall (diagramme en cascade) provenant de récepteurs KiwiSDR.

Ce module fournit les classes nécessaires pour:
- Extraire et traiter les données waterfall à partir des récepteurs KiwiSDR
- Générer des visualisations de type diagramme en cascade (waterfall)
- Effectuer des analyses de spectre
- Gérer les métadonnées associées (fréquence, bande passante, etc.)
- Détecter automatiquement les signaux et pics de puissance

Classes principales:
- WaterfallBuffer: Buffer spécialisé pour stocker les données de waterfall
- WaterfallProcessor: Traitement des données brutes de waterfall
- WaterfallStream: Gestion du flux de données waterfall pour un récepteur KiwiSDR
- WaterfallStreamManager: Gestion de plusieurs flux waterfall
"""

import logging
import threading
import time
import numpy as np
from collections import deque

from .kiwi_connection import KiwiConnection, KiwiConnectionState


class WaterfallStreamError(Exception):
    """Exception spécifique pour les erreurs de traitement du flux waterfall."""
    pass


class WaterfallBuffer:
    """
    Buffer spécifique pour stocker les données waterfall.
    
    Le buffer waterfall stocke les lignes de données spectrales successives,
    permettant de construire une image waterfall (diagramme en cascade).
    """
    
    def __init__(self, max_lines=600, line_width=1024):
        """
        Initialise le buffer waterfall.
        
        Args:
            max_lines (int): Nombre maximum de lignes à stocker
            line_width (int): Nombre de points par ligne (résolution en fréquence)
        """
        self.max_lines = max_lines
        self.line_width = line_width
        self.buffer = deque(maxlen=max_lines)
        self.lines_count = 0
        self.dropped_lines = 0
        self._lock = threading.Lock()
    
    def add_line(self, line_data):
        """
        Ajoute une ligne de données spectrales au buffer.
        
        Args:
            line_data (numpy.ndarray): Données spectrales pour une ligne
                (généralement un tableau de valeurs de puissance sur le spectre)
        
        Returns:
            bool: True si la ligne a été ajoutée, False si ignorée
        """
        with self._lock:
            # Vérifier que la taille de la ligne est correcte
            if len(line_data) != self.line_width:
                logging.warning(f"Taille de ligne incorrecte: {len(line_data)} vs {self.line_width} attendu")
                return False
            
            self.buffer.append(line_data)
            self.lines_count += 1
            
            # Si le buffer est plein, on compte les lignes supprimées
            if len(self.buffer) == self.max_lines and self.lines_count > self.max_lines:
                self.dropped_lines += 1
            
            return True
    
    def get_waterfall_data(self):
        """
        Récupère toutes les données du buffer pour construire l'image waterfall.
        
        Returns:
            numpy.ndarray: Tableau 2D contenant les données waterfall
                (chaque ligne est un spectre à un instant donné)
        """
        with self._lock:
            if not self.buffer:
                return np.zeros((0, self.line_width), dtype=np.uint8)
            
            # Convertir la deque en array numpy
            return np.array(self.buffer, dtype=np.uint8)
    
    def get_latest_line(self):
        """
        Récupère la dernière ligne ajoutée au buffer.
        
        Returns:
            numpy.ndarray: Dernière ligne de données spectrales,
                ou tableau vide si le buffer est vide
        """
        with self._lock:
            if not self.buffer:
                return np.zeros(self.line_width, dtype=np.uint8)
            
            return self.buffer[-1].copy()
    
    def clear(self):
        """Vide le buffer et réinitialise les compteurs."""
        with self._lock:
            self.buffer.clear()
            self.lines_count = 0
            self.dropped_lines = 0
    
    def get_info(self):
        """
        Récupère les informations sur l'état du buffer.
        
        Returns:
            dict: Dictionnaire contenant les informations du buffer
        """
        with self._lock:
            return {
                "max_lines": self.max_lines,
                "line_width": self.line_width,
                "current_lines": len(self.buffer),
                "total_lines_received": self.lines_count,
                "dropped_lines": self.dropped_lines
            }


class WaterfallProcessor:
    """
    Processeur de données waterfall.
    
    Cette classe traite les données brutes du waterfall pour:
    - Normaliser les données
    - Détecter les pics/signaux
    - Convertir les données pour l'affichage
    """
    
    def __init__(self, min_db=-120, max_db=-30):
        """
        Initialise le processeur waterfall.
        
        Args:
            min_db (float): Valeur minimum en dB pour l'échelle
            max_db (float): Valeur maximum en dB pour l'échelle
        """
        self.min_db = min_db
        self.max_db = max_db
        self.db_range = max_db - min_db
    
    def process_waterfall_data(self, data):
        """
        Traite les données waterfall brutes.
        
        Les données du KiwiSDR sont déjà sous forme de valeurs 0-255 représentant
        les niveaux de puissance normalisés.
        
        Args:
            data (bytes): Données brutes waterfall en octets
        
        Returns:
            numpy.ndarray: Tableau d'octets représentant une ligne du waterfall
        """
        # Convertir les données en tableau numpy
        try:
            return np.frombuffer(data, dtype=np.uint8)
        except Exception as e:
            logging.error(f"Erreur lors du traitement des données waterfall: {e}")
            return np.array([])
    
    def db_to_pixel(self, db_values):
        """
        Convertit des valeurs en dB en valeurs de pixels (0-255).
        
        Args:
            db_values (numpy.ndarray): Tableau de valeurs en dB
        
        Returns:
            numpy.ndarray: Tableau de valeurs 0-255 pour l'affichage
        """
        # Limiter les valeurs à la plage min_db - max_db
        clipped = np.clip(db_values, self.min_db, self.max_db)
        
        # Normaliser à 0-255
        normalized = ((clipped - self.min_db) / self.db_range) * 255
        
        return normalized.astype(np.uint8)
    
    def pixel_to_db(self, pixel_values):
        """
        Convertit des valeurs de pixels (0-255) en valeurs en dB.
        
        Args:
            pixel_values (numpy.ndarray): Tableau de valeurs 0-255
        
        Returns:
            numpy.ndarray: Tableau de valeurs en dB
        """
        return self.min_db + (pixel_values / 255.0) * self.db_range
    
    def detect_peaks(self, line_data, threshold=0.7, min_distance=10):
        """
        Détecte les pics (signaux) dans une ligne de données waterfall.
        
        Args:
            line_data (numpy.ndarray): Ligne de données waterfall
            threshold (float): Seuil relatif pour la détection (0.0-1.0)
            min_distance (int): Distance minimale entre les pics
        
        Returns:
            list: Liste des indices des pics détectés
        """
        # Convertir les valeurs de pixels en dB pour le traitement
        db_values = self.pixel_to_db(line_data)
        
        # Calculer le seuil absolu
        abs_threshold = self.min_db + threshold * self.db_range
        
        # Trouver les indices où la valeur dépasse le seuil
        peaks = []
        i = 0
        while i < len(db_values):
            if db_values[i] >= abs_threshold:
                # Trouver la position exacte du pic
                start = max(0, i - min_distance // 2)
                end = min(len(db_values), i + min_distance // 2)
                peak_idx = start + np.argmax(db_values[start:end])
                
                peaks.append(peak_idx)
                # Sauter à la distance minimale pour éviter les doublons
                i = peak_idx + min_distance
            else:
                i += 1
        
        return peaks


class WaterfallStream:
    """
    Gestion du flux de données waterfall pour un récepteur KiwiSDR.
    
    Cette classe gère:
    - La réception des données waterfall
    - Le stockage des données dans un buffer
    - Le traitement pour l'analyse et l'affichage
    - Les callbacks pour notifier les mises à jour
    """
    
    def __init__(self, kiwi, buffer_lines=600, line_width=1024):
        """
        Initialise le flux waterfall.
        
        Args:
            kiwi (KiwiConnection): Connexion au récepteur KiwiSDR
            buffer_lines (int): Nombre de lignes à conserver dans le buffer
            line_width (int): Nombre de points par ligne (résolution en fréquence)
        """
        self.kiwi = kiwi
        self.processor = WaterfallProcessor()
        self.buffer = WaterfallBuffer(max_lines=buffer_lines, line_width=line_width)
        self.is_running = False
        self.last_error = None
        self.update_callback = None
        self.center_frequency = 0
        self.span = 0
        self.timestamp = 0
        
        # Enregistrer le callback pour les données waterfall
        self.kiwi.set_waterfall_callback(self._on_waterfall_data)
    
    async def start(self, center_freq=None, span=None):
        """
        Démarre le flux waterfall.
        
        Args:
            center_freq (int, optional): Fréquence centrale en Hz
            span (int, optional): Largeur de bande en Hz
        
        Returns:
            bool: True si le flux a démarré avec succès, False sinon
        """
        # Définir la fréquence si spécifiée
        if center_freq is not None:
            success = await self.kiwi.set_frequency(center_freq)
            if not success:
                logging.error(f"Impossible de définir la fréquence {center_freq} Hz")
                self.last_error = "Erreur de configuration de la fréquence"
                return False
            
            self.center_frequency = center_freq
        
        # Configurer la largeur de bande si spécifiée
        if span is not None:
            # Note: La configuration de la largeur de bande n'est pas 
            # directement exposée via l'API KiwiSDR, mais pourrait 
            # être ajoutée ultérieurement
            self.span = span
        
        # Démarrer le flux waterfall
        success = await self.kiwi.start_waterfall_stream()
        if not success:
            logging.error("Impossible de démarrer le flux waterfall")
            self.last_error = "Erreur de démarrage du flux waterfall"
            return False
        
        # Vider le buffer au démarrage
        self.buffer.clear()
        self.is_running = True
        self.timestamp = time.time()
        
        logging.info(f"Flux waterfall démarré pour {self.kiwi.name}")
        return True
    
    async def stop(self):
        """
        Arrête le flux waterfall.
        
        Returns:
            bool: True si le flux a été arrêté avec succès
        """
        self.is_running = False
        
        # Arrêter le flux depuis la connexion KiwiSDR
        success = await self.kiwi.stop_waterfall_stream()
        
        # Vider le buffer
        self.buffer.clear()
        
        logging.info(f"Flux waterfall arrêté pour {self.kiwi.name}")
        return success
    
    def register_update_callback(self, callback):
        """
        Enregistre un callback pour les mises à jour waterfall.
        
        Args:
            callback (callable): Fonction à appeler lors de la réception de nouvelles données
                La fonction doit accepter un paramètre (la ligne de données)
        """
        self.update_callback = callback
    
    def get_waterfall_image(self):
        """
        Récupère l'image waterfall complète.
        
        Returns:
            numpy.ndarray: Tableau 2D contenant l'image waterfall
        """
        return self.buffer.get_waterfall_data()
    
    def get_latest_spectrum(self):
        """
        Récupère le dernier spectre reçu.
        
        Returns:
            numpy.ndarray: Tableau 1D contenant le dernier spectre
        """
        return self.buffer.get_latest_line()
    
    def get_status(self):
        """
        Récupère l'état actuel du flux waterfall.
        
        Returns:
            dict: État du flux waterfall
        """
        buffer_info = self.buffer.get_info()
        
        return {
            "is_running": self.is_running,
            "last_error": self.last_error,
            "center_frequency": self.center_frequency,
            "span": self.span,
            "uptime": time.time() - self.timestamp if self.is_running else 0,
            "buffer": buffer_info
        }
    
    def _on_waterfall_data(self, data):
        """
        Callback appelé lors de la réception de données waterfall.
        
        Args:
            data (bytes): Données waterfall brutes
        """
        if not self.is_running:
            return
        
        try:
            # Traiter les données
            line_data = self.processor.process_waterfall_data(data)
            
            if len(line_data) == 0:
                return
            
            # Ajouter au buffer
            self.buffer.add_line(line_data)
            
            # Notifier via le callback si enregistré
            if self.update_callback:
                self.update_callback(line_data)
                
        except Exception as e:
            logging.error(f"Erreur lors du traitement des données waterfall: {e}")
            self.last_error = str(e)


class WaterfallStreamManager:
    """
    Gestionnaire de flux waterfall pour plusieurs récepteurs KiwiSDR.
    
    Cette classe permet de:
    - Gérer plusieurs flux waterfall simultanément
    - Prioriser certains flux
    - Regrouper les données de plusieurs récepteurs
    """
    
    def __init__(self, max_connections=5):
        """
        Initialise le gestionnaire de flux waterfall.
        
        Args:
            max_connections (int): Nombre maximum de connexions waterfall simultanées
        """
        self.streams = {}
        self.max_connections = max_connections
    
    async def add_stream(self, kiwi, buffer_lines=600, line_width=1024):
        """
        Ajoute un nouveau flux waterfall.
        
        Args:
            kiwi (KiwiConnection): Connexion au récepteur KiwiSDR
            buffer_lines (int): Nombre de lignes à conserver dans le buffer
            line_width (int): Nombre de points par ligne
        
        Returns:
            bool: True si le flux a été ajouté avec succès, False sinon
        """
        # Vérifier si ce flux existe déjà
        if kiwi.name in self.streams:
            logging.warning(f"Le flux waterfall pour {kiwi.name} existe déjà")
            return False
        
        # Vérifier le nombre maximum de connexions
        if len(self.streams) >= self.max_connections:
            logging.error(f"Nombre maximum de connexions waterfall atteint ({self.max_connections})")
            return False
        
        # Créer et ajouter le flux
        stream = WaterfallStream(kiwi, buffer_lines, line_width)
        self.streams[kiwi.name] = stream
        
        logging.info(f"Flux waterfall ajouté pour {kiwi.name}")
        return True
    
    async def remove_stream(self, name):
        """
        Supprime un flux waterfall.
        
        Args:
            name (str): Nom du récepteur KiwiSDR
        
        Returns:
            bool: True si le flux a été supprimé, False s'il n'existait pas
        """
        if name not in self.streams:
            logging.warning(f"Tentative de suppression d'un flux waterfall inexistant: {name}")
            return False
        
        # Arrêter le flux avant de le supprimer
        stream = self.streams[name]
        if stream.is_running:
            await stream.stop()
        
        # Supprimer le flux
        del self.streams[name]
        
        logging.info(f"Flux waterfall supprimé pour {name}")
        return True
    
    async def start_all(self, center_freq=None, span=None):
        """
        Démarre tous les flux waterfall.
        
        Args:
            center_freq (int, optional): Fréquence centrale en Hz
            span (int, optional): Largeur de bande en Hz
        
        Returns:
            dict: Résultats du démarrage pour chaque flux
        """
        results = {}
        
        for name, stream in self.streams.items():
            success = await stream.start(center_freq, span)
            results[name] = success
        
        return results
    
    async def stop_all(self):
        """
        Arrête tous les flux waterfall.
        
        Returns:
            dict: Résultats de l'arrêt pour chaque flux
        """
        results = {}
        
        for name, stream in self.streams.items():
            success = await stream.stop()
            results[name] = success
        
        return results
    
    def get_stream(self, name):
        """
        Récupère un flux waterfall par son nom.
        
        Args:
            name (str): Nom du récepteur KiwiSDR
        
        Returns:
            WaterfallStream: Le flux waterfall, ou None s'il n'existe pas
        """
        return self.streams.get(name)
    
    def get_all_streams(self):
        """
        Récupère tous les flux waterfall.
        
        Returns:
            dict: Dictionnaire de tous les flux waterfall
        """
        return self.streams.copy()
    
    def get_combined_waterfall(self):
        """
        Combine les données waterfall de tous les flux actifs.
        
        Cette méthode peut être utilisée pour créer une vue combinée de plusieurs
        récepteurs, par exemple pour étendre la couverture spectrale.
        
        Returns:
            dict: Dictionnaire contenant l'image combinée et les métadonnées
        """
        # Cette implémentation est simple - dans une application réelle,
        # la fusion des données nécessiterait plus de traitement en fonction
        # des fréquences, largeurs de bande, etc.
        
        result = {
            "streams_count": 0,
            "active_streams": [],
            "images": {}
        }
        
        for name, stream in self.streams.items():
            if stream.is_running:
                result["streams_count"] += 1
                result["active_streams"].append(name)
                result["images"][name] = {
                    "data": stream.get_waterfall_image(),
                    "frequency": stream.center_frequency,
                    "span": stream.span
                }
        
        return result 