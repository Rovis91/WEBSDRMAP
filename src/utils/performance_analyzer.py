"""
Script d'analyse des performances pour l'outil de triangulation SDR.

Ce script permet d'identifier les goulots d'étranglement dans l'application
en instrumentant les modules existants avec les outils de mesure de performance.
"""

import argparse
import asyncio
import logging
import sys
import time

from src.utils.logger import get_logger, configure_logger
from src.utils.config_loader import load_config
from src.utils.performance import performance_monitor, timeit, profile, process_pool, thread_pool
from src.sdr_client.kiwi_connection import KiwiConnection
from src.sdr_client.audio_stream import AudioStream
from src.sdr_client.waterfall_stream import WaterfallStream

# Configuration du logger
logger = get_logger(__name__)


class PerformanceAnalyzer:
    """
    Analyseur de performances pour l'outil de triangulation SDR.
    
    Cette classe permet de:
    - Instrumenter les modules existants avec des mesures de performance
    - Exécuter des scénarios de test pour identifier les goulots d'étranglement
    - Générer des rapports détaillés sur les performances
    """
    
    def __init__(self, config_path=None):
        """
        Initialise l'analyseur de performances.
        
        Args:
            config_path: Chemin vers le fichier de configuration
        """
        self.config = load_config(config_path) if config_path else {}
        self.kiwi_connections = []
        self.audio_streams = []
        self.waterfall_streams = []
        self.is_running = False
    
    async def setup(self):
        """
        Configure l'environnement d'analyse.
        
        - Charge la configuration
        - Initialise les pools de processus et de threads
        - Instrumente les modules avec les décorateurs de performance
        """
        logger.info("Configuration de l'analyseur de performances")
        
        # Démarrer les pools
        process_pool.start()
        thread_pool.start()
        
        # Instrumenter les modules
        self._instrument_modules()
        
        logger.info("Analyseur de performances configuré avec succès")
    
    def _instrument_modules(self):
        """
        Instrumente les modules clés avec des décorateurs de mesure de performance.
        """
        # Modules à instrumenter et leurs fonctions critiques
        modules_to_instrument = {
            "src.sdr_client.kiwi_connection": [
                "KiwiConnection._on_message",
                "KiwiConnection._handle_sound_message",
                "KiwiConnection._handle_waterfall_message"
            ],
            "src.sdr_client.audio_stream": [
                "AudioProcessor.process_sound_data",
                "AudioBuffer.add_samples",
                "AudioBuffer.get_samples"
            ],
            "src.sdr_client.waterfall_stream": [
                "WaterfallProcessor.process_waterfall_data",
                "WaterfallBuffer.add_line",
                "WaterfallBuffer.get_waterfall_data",
                "WaterfallStream._on_waterfall_data"
            ]
        }
        
        # Pour chaque module, appliquer le décorateur timeit aux fonctions spécifiées
        for module_name, function_names in modules_to_instrument.items():
            try:
                module = sys.modules.get(module_name)
                if not module:
                    logger.warning(f"Module {module_name} non trouvé, impossible d'instrumenter")
                    continue
                
                for func_name in function_names:
                    # Récupérer le nom de classe et de méthode
                    if "." in func_name:
                        class_name, method_name = func_name.split(".")
                        class_obj = getattr(module, class_name, None)
                        if not class_obj:
                            logger.warning(f"Classe {class_name} non trouvée dans {module_name}")
                            continue
                        
                        # Récupérer la méthode originale
                        original_method = getattr(class_obj, method_name, None)
                        if not original_method:
                            logger.warning(f"Méthode {method_name} non trouvée dans {class_name}")
                            continue
                        
                        # Appliquer le décorateur
                        setattr(class_obj, method_name, timeit(original_method))
                        logger.debug(f"Instrumenté {module_name}.{func_name}")
                    else:
                        # Fonction de niveau module
                        original_func = getattr(module, func_name, None)
                        if not original_func:
                            logger.warning(f"Fonction {func_name} non trouvée dans {module_name}")
                            continue
                        
                        # Appliquer le décorateur
                        setattr(module, func_name, timeit(original_func))
                        logger.debug(f"Instrumenté {module_name}.{func_name}")
            
            except Exception as e:
                logger.error(f"Erreur lors de l'instrumentation de {module_name}: {e}")
    
    async def run_connection_test(self, kiwi_urls, duration=60):
        """
        Exécute un test de connexion aux KiwiSDR.
        
        Args:
            kiwi_urls: Liste d'URLs des KiwiSDR à tester
            duration: Durée du test en secondes
        """
        logger.info(f"Démarrage du test de connexion avec {len(kiwi_urls)} KiwiSDR pour {duration} secondes")
        
        # Réinitialiser le moniteur de performance
        performance_monitor.reset()
        performance_monitor.start()
        
        try:
            # Créer et connecter les KiwiSDR
            for url in kiwi_urls:
                kiwi = KiwiConnection(url)
                if await kiwi.connect():
                    self.kiwi_connections.append(kiwi)
                    logger.info(f"Connexion établie avec {url}")
                else:
                    logger.warning(f"Échec de la connexion à {url}")
            
            # Attendre la durée spécifiée
            await asyncio.sleep(duration)
            
        finally:
            # Fermer les connexions
            for kiwi in self.kiwi_connections:
                await kiwi.disconnect()
            
            # Générer le rapport
            performance_monitor.stop()
            performance_monitor.print_report()
    
    async def run_audio_test(self, kiwi_urls, duration=60):
        """
        Exécute un test des flux audio.
        
        Args:
            kiwi_urls: Liste d'URLs des KiwiSDR à tester
            duration: Durée du test en secondes
        """
        logger.info(f"Démarrage du test de flux audio avec {len(kiwi_urls)} KiwiSDR pour {duration} secondes")
        
        # Réinitialiser le moniteur de performance
        performance_monitor.reset()
        performance_monitor.start()
        
        try:
            # Créer et connecter les KiwiSDR
            for url in kiwi_urls:
                kiwi = KiwiConnection(url)
                if await kiwi.connect() and await kiwi.authenticate():
                    # Configurer le récepteur
                    await kiwi.set_frequency(7100000)  # 7.1 MHz (40m)
                    
                    # Créer le flux audio
                    audio_stream = AudioStream(kiwi)
                    if await audio_stream.start():
                        self.kiwi_connections.append(kiwi)
                        self.audio_streams.append(audio_stream)
                        logger.info(f"Flux audio démarré pour {url}")
                    else:
                        await kiwi.disconnect()
                        logger.warning(f"Échec du démarrage du flux audio pour {url}")
                else:
                    logger.warning(f"Échec de la connexion/authentification à {url}")
            
            # Attendre la durée spécifiée
            await asyncio.sleep(duration)
            
        finally:
            # Arrêter les flux audio et fermer les connexions
            for audio_stream in self.audio_streams:
                await audio_stream.stop()
            
            for kiwi in self.kiwi_connections:
                await kiwi.disconnect()
            
            # Générer le rapport
            performance_monitor.stop()
            performance_monitor.print_report()
    
    async def run_waterfall_test(self, kiwi_urls, duration=60):
        """
        Exécute un test des flux waterfall.
        
        Args:
            kiwi_urls: Liste d'URLs des KiwiSDR à tester
            duration: Durée du test en secondes
        """
        logger.info(f"Démarrage du test de flux waterfall avec {len(kiwi_urls)} KiwiSDR pour {duration} secondes")
        
        # Réinitialiser le moniteur de performance
        performance_monitor.reset()
        performance_monitor.start()
        
        try:
            # Créer et connecter les KiwiSDR
            for url in kiwi_urls:
                kiwi = KiwiConnection(url)
                if await kiwi.connect() and await kiwi.authenticate():
                    # Configurer le récepteur
                    await kiwi.set_frequency(7100000)  # 7.1 MHz (40m)
                    
                    # Créer le flux waterfall
                    waterfall_stream = WaterfallStream(kiwi)
                    if await waterfall_stream.start():
                        self.kiwi_connections.append(kiwi)
                        self.waterfall_streams.append(waterfall_stream)
                        logger.info(f"Flux waterfall démarré pour {url}")
                    else:
                        await kiwi.disconnect()
                        logger.warning(f"Échec du démarrage du flux waterfall pour {url}")
                else:
                    logger.warning(f"Échec de la connexion/authentification à {url}")
            
            # Attendre la durée spécifiée
            await asyncio.sleep(duration)
            
        finally:
            # Arrêter les flux waterfall et fermer les connexions
            for waterfall_stream in self.waterfall_streams:
                await waterfall_stream.stop()
            
            for kiwi in self.kiwi_connections:
                await kiwi.disconnect()
            
            # Générer le rapport
            performance_monitor.stop()
            performance_monitor.print_report()
    
    async def run_combined_test(self, kiwi_urls, duration=60):
        """
        Exécute un test combiné (audio + waterfall).
        
        Args:
            kiwi_urls: Liste d'URLs des KiwiSDR à tester
            duration: Durée du test en secondes
        """
        logger.info(f"Démarrage du test combiné avec {len(kiwi_urls)} KiwiSDR pour {duration} secondes")
        
        # Réinitialiser le moniteur de performance
        performance_monitor.reset()
        performance_monitor.start()
        
        try:
            # Créer et connecter les KiwiSDR
            for url in kiwi_urls:
                kiwi = KiwiConnection(url)
                if await kiwi.connect() and await kiwi.authenticate():
                    # Configurer le récepteur
                    await kiwi.set_frequency(7100000)  # 7.1 MHz (40m)
                    
                    # Créer le flux audio
                    audio_stream = AudioStream(kiwi)
                    waterfall_stream = WaterfallStream(kiwi)
                    
                    audio_success = await audio_stream.start()
                    waterfall_success = await waterfall_stream.start()
                    
                    if audio_success and waterfall_success:
                        self.kiwi_connections.append(kiwi)
                        self.audio_streams.append(audio_stream)
                        self.waterfall_streams.append(waterfall_stream)
                        logger.info(f"Flux audio et waterfall démarrés pour {url}")
                    else:
                        if audio_success:
                            await audio_stream.stop()
                        if waterfall_success:
                            await waterfall_stream.stop()
                        await kiwi.disconnect()
                        logger.warning(f"Échec du démarrage des flux pour {url}")
                else:
                    logger.warning(f"Échec de la connexion/authentification à {url}")
            
            # Attendre la durée spécifiée
            await asyncio.sleep(duration)
            
        finally:
            # Arrêter les flux et fermer les connexions
            for audio_stream in self.audio_streams:
                await audio_stream.stop()
            
            for waterfall_stream in self.waterfall_streams:
                await waterfall_stream.stop()
            
            for kiwi in self.kiwi_connections:
                await kiwi.disconnect()
            
            # Générer le rapport
            performance_monitor.stop()
            performance_monitor.print_report()
    
    async def cleanup(self):
        """
        Nettoie les ressources utilisées par l'analyseur.
        """
        logger.info("Nettoyage des ressources de l'analyseur de performances")
        
        # Arrêter les pools
        process_pool.stop()
        thread_pool.stop()
        
        # Réinitialiser le moniteur de performance
        performance_monitor.reset()
        
        logger.info("Nettoyage terminé")


async def main():
    """
    Fonction principale du script d'analyse des performances.
    """
    # Configurer le parser d'arguments
    parser = argparse.ArgumentParser(description="Analyseur de performances pour l'outil de triangulation SDR")
    parser.add_argument("--config", help="Chemin vers le fichier de configuration")
    parser.add_argument("--test", choices=["connection", "audio", "waterfall", "combined"], default="combined",
                        help="Type de test à exécuter")
    parser.add_argument("--duration", type=int, default=60, help="Durée du test en secondes")
    parser.add_argument("--kiwi", action="append", help="URL d'un KiwiSDR à tester (peut être spécifié plusieurs fois)")
    parser.add_argument("--verbose", action="store_true", help="Activer les logs verbeux")
    args = parser.parse_args()
    
    # Configurer le logger
    log_level = logging.DEBUG if args.verbose else logging.INFO
    configure_logger(log_level=log_level)
    
    # KiwiSDR par défaut pour les tests
    default_kiwis = [
        "wss://kiwisdr.example.com/kiwi",  # À remplacer par des KiwiSDR réels
    ]
    kiwi_urls = args.kiwi or default_kiwis
    
    # Créer et configurer l'analyseur
    analyzer = PerformanceAnalyzer(args.config)
    await analyzer.setup()
    
    try:
        # Exécuter le test spécifié
        if args.test == "connection":
            await analyzer.run_connection_test(kiwi_urls, args.duration)
        elif args.test == "audio":
            await analyzer.run_audio_test(kiwi_urls, args.duration)
        elif args.test == "waterfall":
            await analyzer.run_waterfall_test(kiwi_urls, args.duration)
        else:  # combined
            await analyzer.run_combined_test(kiwi_urls, args.duration)
    
    finally:
        # Nettoyer les ressources
        await analyzer.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 