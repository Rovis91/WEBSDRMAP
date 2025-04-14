#!/usr/bin/env python3
"""
Outil CLI pour la visualisation et l'enregistrement de waterfalls SDR

Cet outil permet de:
1. Se connecter à un récepteur SDR distant
2. Visualiser et enregistrer des flux waterfall
3. Sauvegarder les données dans différents formats

Usage:
  python waterfall_cli.py --host <hostname> --freq <khz> [--options]
"""

import os
import sys
import asyncio
import argparse
import datetime
import numpy as np
from PIL import Image

# Import du module SDR et Waterfall
from src.sdr_client.kiwi_connection import KiwiConnection
from src.sdr_client.waterfall_stream import (
    WaterfallStream,
    WaterfallProcessor,
    WaterfallStreamManager
)


class WaterfallCLI:
    """Interface en ligne de commande pour les flux waterfall."""

    def __init__(self, args):
        """Initialise l'interface CLI avec les arguments fournis."""
        self.args = args
        self.kiwi = None
        self.manager = None
        self.streams = {}
        self.running = False
        self.processed_lines = 0
        self.last_update = datetime.datetime.now()
        self.data_directory = args.output_dir or "waterfall_data"
        
        # Créer le répertoire de sortie s'il n'existe pas
        if not os.path.exists(self.data_directory):
            os.makedirs(self.data_directory)
    
    async def connect(self):
        """Établit la connexion au KiwiSDR."""
        print(f"Connexion à {self.args.host}:{self.args.port}...")
        self.kiwi = KiwiConnection(
            host=self.args.host,
            port=self.args.port,
            name=self.args.user or "waterfall_cli"
        )
        
        connected = await self.kiwi.connect()
        if not connected:
            print(f"Échec de connexion à {self.args.host}")
            return False
        
        print(f"Connecté à {self.args.host}")
        return True
    
    async def setup_streams(self):
        """Configure les flux waterfall selon les paramètres."""
        print("Configuration du gestionnaire de flux...")
        self.manager = WaterfallStreamManager()
        
        # Extraire les fréquences cibles
        frequencies = []
        if self.args.freq:
            frequencies.append(float(self.args.freq) * 1000)  # Convertir kHz en Hz
        
        if self.args.freq_list:
            try:
                with open(self.args.freq_list, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            frequencies.append(float(line) * 1000)  # Convertir kHz en Hz
            except Exception as e:
                print(f"Erreur lors de la lecture du fichier de fréquences: {e}")
                return False
        
        if not frequencies:
            print("Aucune fréquence spécifiée. Utilisation de 7100 kHz par défaut.")
            frequencies.append(7100000)  # 7.1 MHz (40m) par défaut
        
        # Créer et configurer les flux pour chaque fréquence
        for freq in frequencies:
            stream_name = f"stream_{int(freq/1000)}"
            print(f"Configuration du flux {stream_name} à {freq/1000} kHz...")
            
            # Créer le flux
            stream = WaterfallStream(
                kiwi=self.kiwi,
                buffer_lines=self.args.lines or 1000,
                line_width=self.args.width or 1024
            )
            
            # Enregistrer un callback pour les mises à jour
            stream.register_update_callback(
                lambda data, freq=freq: self.on_waterfall_update(data, freq)
            )
            
            # Ajouter le flux au gestionnaire
            self.manager.add_stream(stream_name, stream)
            self.streams[stream_name] = {
                "frequency": freq,
                "span": self.args.span * 1000 if self.args.span else 20000,  # Convertir kHz en Hz
                "stream": stream
            }
        
        return True
    
    async def start_streams(self):
        """Démarre tous les flux configurés."""
        print("Démarrage des flux waterfall...")
        self.running = True
        
        for stream_name, info in self.streams.items():
            print(f"Démarrage du flux {stream_name} à {info['frequency']/1000} kHz...")
            result = await info["stream"].start(
                center_freq=info["frequency"],
                span=info["span"]
            )
            
            if not result:
                print(f"Échec de démarrage du flux {stream_name}")
                print(f"Erreur: {info['stream'].last_error}")
                continue
            
            print(f"Flux {stream_name} démarré avec succès")
        
        return True
    
    async def stop_streams(self):
        """Arrête tous les flux en cours."""
        print("Arrêt des flux waterfall...")
        if self.manager:
            await self.manager.stop_all_streams()
        
        self.running = False
        print("Tous les flux sont arrêtés")
        return True
    
    def on_waterfall_update(self, line_data, frequency):
        """Callback appelé à chaque mise à jour du waterfall."""
        self.processed_lines += 1
        
        # Afficher des statistiques périodiquement
        now = datetime.datetime.now()
        if (now - self.last_update).total_seconds() >= 5:
            print(f"Lignes traitées: {self.processed_lines}, Dernier waterfall: {frequency/1000} kHz")
            self.last_update = now
        
        # Rechercher des pics si demandé
        if self.args.detect_peaks:
            processor = WaterfallProcessor(min_db=-100, max_db=-20)
            peaks = processor.detect_peaks(
                line_data, 
                threshold=self.args.peak_threshold or 0.7,
                min_distance=self.args.peak_distance or 10
            )
            
            if peaks.size > 0:
                stream_name = f"stream_{int(frequency/1000)}"
                stream_info = self.streams.get(stream_name, {})
                span = stream_info.get("span", 20000)
                
                # Convertir les indices de pics en fréquences
                freq_step = span / line_data.size
                for peak_idx in peaks:
                    freq_offset = peak_idx * freq_step - span / 2
                    peak_freq = frequency + freq_offset
                    print(f"Signal détecté à {peak_freq/1000:.1f} kHz (force: {line_data[peak_idx]/255:.2f})")
    
    async def save_waterfall_images(self):
        """Sauvegarde les images waterfall périodiquement."""
        while self.running:
            # Attendre l'intervalle spécifié
            await asyncio.sleep(self.args.save_interval or 60)
            
            if not self.running:
                break
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Sauvegarder l'image pour chaque flux
            for stream_name, info in self.streams.items():
                # Récupérer les données du waterfall
                waterfall_data = info["stream"].get_waterfall_image()
                if waterfall_data.size == 0:
                    continue
                
                # Créer le nom de fichier
                freq_mhz = info["frequency"] / 1000000
                filename = f"{self.data_directory}/{timestamp}_{freq_mhz:.3f}MHz_waterfall.png"
                
                # Sauvegarder l'image
                print(f"Sauvegarde de l'image waterfall: {filename}")
                try:
                    # Convertir en image PIL et sauvegarder
                    img = Image.fromarray(waterfall_data)
                    img.save(filename)
                    
                    # Sauvegarder également les données brutes si demandé
                    if self.args.save_raw:
                        raw_filename = f"{self.data_directory}/{timestamp}_{freq_mhz:.3f}MHz_waterfall.npy"
                        np.save(raw_filename, waterfall_data)
                except Exception as e:
                    print(f"Erreur lors de la sauvegarde de l'image: {e}")
    
    async def run(self):
        """Exécute le programme principal."""
        try:
            # Établir la connexion
            if not await self.connect():
                return 1
            
            # Configurer les flux
            if not await self.setup_streams():
                await self.cleanup()
                return 1
            
            # Démarrer les flux
            if not await self.start_streams():
                await self.cleanup()
                return 1
            
            # Lancer la tâche de sauvegarde si nécessaire
            save_task = None
            if self.args.save_images:
                save_task = asyncio.create_task(self.save_waterfall_images())
            
            # Durée d'exécution
            if self.args.duration:
                print(f"Exécution pendant {self.args.duration} secondes...")
                await asyncio.sleep(self.args.duration)
            else:
                print("Appuyez sur Ctrl+C pour arrêter...")
                # Attendre indéfiniment
                while self.running:
                    await asyncio.sleep(1)
            
            # Annuler la tâche de sauvegarde si elle existe
            if save_task:
                save_task.cancel()
                try:
                    await save_task
                except asyncio.CancelledError:
                    pass
            
            return 0
            
        except KeyboardInterrupt:
            print("\nInterruption clavier détectée")
            return 0
        except Exception as e:
            print(f"Erreur: {e}")
            return 1
        finally:
            # Nettoyer les ressources
            await self.cleanup()
    
    async def cleanup(self):
        """Nettoie les ressources."""
        print("Nettoyage des ressources...")
        
        if self.manager:
            await self.manager.stop_all_streams()
        
        if self.kiwi and self.kiwi.is_connected():
            await self.kiwi.disconnect()
        
        self.running = False
        print("Ressources nettoyées")


def parse_arguments():
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Outil de visualisation et d'enregistrement de waterfalls SDR"
    )
    
    # Arguments de connexion
    parser.add_argument("--host", type=str, help="Nom d'hôte ou adresse IP du KiwiSDR")
    parser.add_argument("--port", type=int, default=8073, help="Port du KiwiSDR (défaut: 8073)")
    parser.add_argument("--user", type=str, help="Nom d'utilisateur à utiliser pour la connexion")
    
    # Arguments de fréquence
    parser.add_argument("--freq", type=float, help="Fréquence centrale en kHz")
    parser.add_argument("--freq-list", type=str, help="Fichier contenant une liste de fréquences en kHz")
    parser.add_argument("--span", type=float, default=20, help="Largeur de bande en kHz (défaut: 20)")
    
    # Arguments de configuration du waterfall
    parser.add_argument("--width", type=int, help="Largeur du waterfall en pixels")
    parser.add_argument("--lines", type=int, help="Nombre de lignes à conserver dans le buffer")
    
    # Arguments de détection
    parser.add_argument("--detect-peaks", action="store_true", help="Activer la détection des pics")
    parser.add_argument("--peak-threshold", type=float, help="Seuil de détection des pics (0.0-1.0)")
    parser.add_argument("--peak-distance", type=int, help="Distance minimale entre les pics")
    
    # Arguments de sauvegarde
    parser.add_argument("--save-images", action="store_true", help="Activer la sauvegarde des images")
    parser.add_argument("--save-interval", type=int, help="Intervalle de sauvegarde en secondes")
    parser.add_argument("--save-raw", action="store_true", help="Sauvegarder également les données brutes")
    parser.add_argument("--output-dir", type=str, help="Répertoire de sortie pour les fichiers")
    
    # Arguments divers
    parser.add_argument("--duration", type=int, help="Durée d'exécution en secondes")
    
    return parser.parse_args()


# Point d'entrée du programme
if __name__ == "__main__":
    args = parse_arguments()
    
    # Vérifier les arguments obligatoires
    if not args.host:
        print("Erreur: L'argument --host est obligatoire")
        sys.exit(1)
    
    # Exécuter le programme
    cli = WaterfallCLI(args)
    exit_code = asyncio.run(cli.run())
    sys.exit(exit_code) 