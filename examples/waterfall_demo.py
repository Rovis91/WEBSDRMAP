#!/usr/bin/env python3
"""
Démonstration d'utilisation du module waterfall_stream.py

Ce script montre comment:
1. Créer une connexion à un récepteur KiwiSDR
2. Configurer un flux waterfall
3. Démarrer l'acquisition de données
4. Traiter les données en temps réel
5. Afficher les résultats

Nécessite: matplotlib, numpy
"""

import asyncio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Import du module SDR et Waterfall
from src.sdr_client.kiwi_connection import KiwiConnection
from src.sdr_client.waterfall_stream import (
    WaterfallStream,
    WaterfallProcessor
)


class WaterfallDemo:
    """Démonstrateur pour le module waterfall_stream."""

    def __init__(self):
        """Initialise la démo."""
        # Configuration de la connexion
        self.kiwi_host = "kiwisdr.example.com"  # À remplacer par une adresse réelle
        self.kiwi_port = 8073
        self.kiwi_name = "demo_connection"
        
        # Configuration du waterfall
        self.center_freq = 7100000  # 7.1 MHz (40m)
        self.span = 20000  # 20 kHz
        self.buffer_lines = 200  # 200 lignes d'historique
        
        # Variables de l'application
        self.kiwi = None
        self.waterfall_stream = None
        self.running = False
        
        # Interface graphique
        self.fig = None
        self.waterfall_img = None
        self.spectrum_line = None
        self.animation = None
    
    async def connect(self):
        """Établit la connexion au KiwiSDR."""
        print(f"Connexion à {self.kiwi_host}...")
        self.kiwi = KiwiConnection(
            host=self.kiwi_host,
            port=self.kiwi_port,
            name=self.kiwi_name
        )
        
        # Se connecter au serveur
        connected = await self.kiwi.connect()
        if not connected:
            print(f"Échec de connexion à {self.kiwi_host}")
            return False
        
        print(f"Connecté à {self.kiwi_host}")
        return True
    
    async def setup_waterfall(self):
        """Configure le flux waterfall."""
        if not self.kiwi:
            print("Pas de connexion disponible")
            return False
        
        print("Configuration du flux waterfall...")
        self.waterfall_stream = WaterfallStream(
            kiwi=self.kiwi,
            buffer_lines=self.buffer_lines,
            line_width=1024
        )
        
        # Enregistrer un callback pour les mises à jour
        self.waterfall_stream.register_update_callback(self.on_waterfall_update)
        
        return True
    
    async def start_waterfall(self):
        """Démarre le flux waterfall."""
        if not self.waterfall_stream:
            print("Le flux waterfall n'est pas configuré")
            return False
        
        print(f"Démarrage du flux waterfall à {self.center_freq/1000} kHz...")
        result = await self.waterfall_stream.start(
            center_freq=self.center_freq,
            span=self.span
        )
        
        if not result:
            print("Échec de démarrage du flux waterfall")
            print(f"Erreur: {self.waterfall_stream.last_error}")
            return False
        
        self.running = True
        print("Flux waterfall démarré avec succès")
        return True
    
    async def stop_waterfall(self):
        """Arrête le flux waterfall."""
        if not self.waterfall_stream:
            return False
        
        print("Arrêt du flux waterfall...")
        await self.waterfall_stream.stop()
        self.running = False
        print("Flux waterfall arrêté")
        return True
    
    async def cleanup(self):
        """Nettoie les ressources."""
        print("Nettoyage des ressources...")
        
        if self.waterfall_stream and self.waterfall_stream.is_running:
            await self.waterfall_stream.stop()
        
        if self.kiwi and self.kiwi.is_connected():
            await self.kiwi.disconnect()
        
        self.running = False
        print("Ressources nettoyées")
    
    def on_waterfall_update(self, line_data):
        """Callback appelé à chaque mise à jour du waterfall."""
        # On peut effectuer ici un traitement en temps réel des données
        # Par exemple, détection de signaux, analyse, etc.
        
        # Pour cet exemple, on se contente de détecter les pics
        processor = WaterfallProcessor(min_db=-100, max_db=-20)
        peaks = processor.detect_peaks(line_data, threshold=0.7, min_distance=10)
        
        if peaks.size > 0:
            # Convertir les indices de pics en fréquences
            freq_step = self.span / line_data.size
            for peak_idx in peaks:
                freq_offset = peak_idx * freq_step - self.span / 2
                peak_freq = self.center_freq + freq_offset
                print(f"Signal détecté à {peak_freq/1000:.1f} kHz")
    
    def setup_gui(self):
        """Configure l'interface graphique."""
        print("Configuration de l'interface graphique...")
        
        # Créer la figure et les axes
        self.fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        self.fig.suptitle(f"SDR Waterfall - {self.kiwi_host}", fontsize=14)
        
        # Configurer l'axe du waterfall
        ax1.set_title("Waterfall")
        ax1.set_xlabel("Fréquence (kHz)")
        ax1.set_ylabel("Temps")
        
        # Configurer l'axe du spectre
        ax2.set_title("Spectre actuel")
        ax2.set_xlabel("Fréquence (kHz)")
        ax2.set_ylabel("Niveau (dB)")
        ax2.set_ylim(-100, -20)
        
        # Initialiser l'affichage du waterfall avec des données vides
        empty_waterfall = np.zeros((self.buffer_lines, 1024), dtype=np.uint8)
        self.waterfall_img = ax1.imshow(
            empty_waterfall,
            aspect='auto',
            cmap='viridis',
            extent=[
                (self.center_freq - self.span/2) / 1000,
                (self.center_freq + self.span/2) / 1000,
                self.buffer_lines,
                0
            ]
        )
        
        # Initialiser l'affichage du spectre avec des données vides
        freq_range = np.linspace(
            (self.center_freq - self.span/2) / 1000,
            (self.center_freq + self.span/2) / 1000,
            1024
        )
        self.spectrum_line, = ax2.plot(freq_range, np.full(1024, -100))
        
        # Configurer la mise à jour de l'affichage
        self.animation = FuncAnimation(
            self.fig,
            self.update_plot,
            interval=100,
            blit=False
        )
        
        # Ajouter une barre de couleur
        plt.colorbar(self.waterfall_img, ax=ax1, label="Niveau (dB)")
        
        # Ajuster la mise en page
        plt.tight_layout()
        
        return True
    
    def update_plot(self, frame):
        """Mise à jour de l'affichage."""
        if not self.running or not self.waterfall_stream:
            return self.waterfall_img, self.spectrum_line
        
        # Récupérer les données waterfall
        waterfall_data = self.waterfall_stream.get_waterfall_image()
        if waterfall_data.size > 0:
            self.waterfall_img.set_data(waterfall_data)
        
        # Récupérer le spectre actuel
        spectrum_data = self.waterfall_stream.get_latest_spectrum()
        
        # Convertir les valeurs de pixels en dB pour le spectre
        processor = WaterfallProcessor(min_db=-100, max_db=-20)
        spectrum_db = processor.pixel_to_db(spectrum_data)
        
        # Mettre à jour le graphique du spectre
        self.spectrum_line.set_ydata(spectrum_db)
        
        # Ajouter les marqueurs pour les pics
        peaks = processor.detect_peaks(spectrum_data, threshold=0.7, min_distance=10)
        
        return self.waterfall_img, self.spectrum_line
    
    def show_gui(self):
        """Affiche l'interface graphique."""
        print("Affichage de l'interface graphique...")
        plt.show()
    
    async def run(self):
        """Exécute la démo complète."""
        try:
            # Établir la connexion
            if not await self.connect():
                return
            
            # Configurer le flux waterfall
            if not await self.setup_waterfall():
                await self.cleanup()
                return
            
            # Configurer l'interface graphique
            self.setup_gui()
            
            # Démarrer le flux waterfall
            if not await self.start_waterfall():
                await self.cleanup()
                return
            
            # Afficher l'interface graphique
            self.show_gui()
            
        except KeyboardInterrupt:
            print("Interruption clavier détectée")
        except Exception as e:
            print(f"Erreur: {e}")
        finally:
            # Nettoyer les ressources
            await self.cleanup()


# Point d'entrée du programme
if __name__ == "__main__":
    demo = WaterfallDemo()
    asyncio.run(demo.run()) 