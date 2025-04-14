"""
Module principal de l'outil de triangulation SDR.

Ce module:
- Initialise et configure tous les composants de l'application
- Gère les connections aux récepteurs SDR
- Coordonne le traitement du signal et la triangulation
- Optimise les performances avec multiprocessing
- Expose l'interface web
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from typing import Dict, List, Any, Optional

import numpy as np

from src.utils.logger import get_logger, configure_logger
from src.utils.config_loader import load_config
from src.utils.performance import process_pool, thread_pool, performance_monitor, timeit
from src.sdr_client.kiwi_connection import KiwiConnection, KiwiSDRMode
from src.sdr_client.audio_stream import AudioStream, AudioStreamManager
from src.sdr_client.waterfall_stream import WaterfallStream, WaterfallStreamManager
from src.signal_processing.optimized_processing import OptimizedSignalProcessor
from src.signal_processing.detection import SignalDetector, AlertManager, SignalType, SignalDetection
from src.signal_processing.triangulation import Triangulator, TriangulationResult
from src.signal_processing.rssi import RSSIComputer, RSSIMethod
from src.data_export.data_export import DataExporter

# Configuration du logger
logger = get_logger(__name__)


class SDRTriangulationApp:
    """
    Application principale de triangulation SDR.
    
    Cette classe coordonne tous les composants et gère les ressources de l'application.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialise l'application de triangulation SDR.
        
        Args:
            config_path: Chemin vers le fichier de configuration (None = config par défaut)
        """
        self.config = load_config(config_path)
        self.kiwi_connections = {}
        self.audio_manager = AudioStreamManager()
        self.waterfall_manager = WaterfallStreamManager()
        self.signal_processor = OptimizedSignalProcessor()
        
        # Composants additionnels
        self.signal_detector = None
        self.alert_manager = AlertManager()
        self.triangulator = None
        self.rssi_computer = None
        self.data_exporter = DataExporter()
        
        # Données de l'application
        self.active_signals = {}  # {signal_id: SignalDetection}
        self.triangulation_results = {}  # {signal_id: TriangulationResult}
        
        self.is_running = False
        self.stopping_event = asyncio.Event()
        self.demo_mode = False  # Mode démo sans connexions réelles
        
        # Statistiques de performances
        self.performance_stats = {
            'connections': {},
            'audio_streams': {},
            'waterfall_streams': {},
            'signal_processing': {},
            'triangulation': {},
            'data_export': {}
        }
    
    async def initialize(self):
        """
        Initialise l'application et ses composants.
        
        Returns:
            True si l'initialisation a réussi, False sinon
        """
        logger.info("Initialisation de l'application de triangulation SDR")
        
        try:
            # Initialiser les pools
            process_pool.start()
            thread_pool.start()
            
            # Activer le monitoring des performances
            performance_monitor.reset()
            performance_monitor.start()
            
            # Charger les récepteurs SDR depuis la configuration
            if 'sdr' in self.config and 'receivers' in self.config['sdr']:
                for receiver_config in self.config['sdr']['receivers']:
                    await self._add_receiver(receiver_config)
            
            # Initialiser le processor de signal
            fft_size = self.config.get('signal_processing', {}).get('fft_size', 1024)
            sample_rate = self.config.get('signal_processing', {}).get('sample_rate', 12000)
            self.signal_processor = OptimizedSignalProcessor(
                sample_rate=sample_rate,
                fft_size=fft_size
            )
            
            # Initialiser le détecteur de signaux
            detection_config = self.config.get('detection', {})
            self.signal_detector = SignalDetector(
                threshold_db=detection_config.get('threshold_db', -80.0),
                min_snr_db=detection_config.get('min_snr_db', 10.0),
                min_duration_sec=detection_config.get('min_duration_sec', 2.0),
                max_inactive_sec=detection_config.get('max_inactive_sec', 5.0),
                frequency_tolerance_hz=detection_config.get('frequency_tolerance_hz', 100.0)
            )
            
            # Initialiser le calculateur RSSI
            rssi_config = self.config.get('rssi', {})
            self.rssi_computer = RSSIComputer(
                method=RSSIMethod(rssi_config.get('method', 'rms')),
                window_size=rssi_config.get('window_size', 10),
                smoothing_factor=rssi_config.get('smoothing_factor', 0.3)
            )
            
            # Initialiser le triangulateur
            triangulation_config = self.config.get('triangulation', {})
            self.triangulator = Triangulator()
            
            # Configurer les paramètres du triangulateur
            if 'min_receivers' in triangulation_config:
                self.triangulator.min_receivers = triangulation_config.get('min_receivers')
            if 'max_distance' in triangulation_config:
                self.triangulator.max_distance = triangulation_config.get('max_distance')
            
            # Configurer les règles d'alerte si disponibles
            if 'alert_rules' in self.config:
                for rule in self.config['alert_rules']:
                    self.alert_manager.add_rule(
                        name=rule.get('name', 'Alerte sans nom'),
                        min_frequency=rule.get('min_frequency'),
                        max_frequency=rule.get('max_frequency'),
                        min_power=rule.get('min_power'),
                        signal_type=SignalType(rule.get('signal_type', 'unknown')) if rule.get('signal_type') else None,
                        min_duration=rule.get('min_duration')
                    )
            
            # Initialiser l'exportateur de données
            export_config = self.config.get('data_export', {})
            self.data_exporter.configure(
                output_dir=export_config.get('output_dir', 'exports'),
                audio_format=export_config.get('audio_format', 'wav'),
                enable_audio_export=export_config.get('enable_audio_export', True),
                enable_spectrum_export=export_config.get('enable_spectrum_export', True),
                enable_triangulation_export=export_config.get('enable_triangulation_export', True)
            )
            
            logger.info("Initialisation réussie")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation: {e}")
            return False
    
    async def _add_receiver(self, receiver_config: Dict[str, Any]):
        """
        Ajoute un récepteur SDR à l'application.
        
        Args:
            receiver_config: Configuration du récepteur
            
        Returns:
            True si l'ajout a réussi, False sinon
        """
        url = receiver_config.get('url')
        name = receiver_config.get('name', url)
        location = receiver_config.get('location', {"latitude": 0.0, "longitude": 0.0})
        
        if not url:
            logger.error("URL du récepteur manquante")
            return False
        
        logger.info(f"Ajout du récepteur {name} ({url})")
        
        # Créer la connexion
        kiwi = KiwiConnection(url, name, location)
        
        # Stocker la connexion
        self.kiwi_connections[name] = kiwi
        
        return True
    
    @timeit
    async def connect_receivers(self):
        """
        Connecte tous les récepteurs SDR.
        
        Returns:
            Dictionnaire avec les résultats des connexions
        """
        logger.info("Connexion aux récepteurs SDR")
        results = {}
        
        # Si en mode démo, simuler des connexions réussies
        if self.demo_mode:
            logger.info("Mode démo - Simulation de connexions réussies")
            for name in self.kiwi_connections:
                results[name] = True
            
            # Compter les succès
            success_count = len(results)
            logger.info(f"Mode démo: {success_count}/{len(self.kiwi_connections)} récepteurs simulés connectés")
            return results
        
        # En mode normal, créer une liste de tâches pour les connexions
        connection_tasks = []
        for name, kiwi in self.kiwi_connections.items():
            connection_tasks.append(self._connect_receiver(name, kiwi))
        
        # Exécuter toutes les connexions en parallèle
        if connection_tasks:
            results_list = await asyncio.gather(*connection_tasks, return_exceptions=True)
            
            # Traiter les résultats
            for i, (name, _) in enumerate(self.kiwi_connections.items()):
                result = results_list[i]
                if isinstance(result, Exception):
                    logger.error(f"Erreur lors de la connexion à {name}: {result}")
                    results[name] = False
                else:
                    results[name] = result
        
        # Compter les succès
        success_count = sum(1 for result in results.values() if result)
        logger.info(f"{success_count}/{len(self.kiwi_connections)} récepteurs connectés avec succès")
        
        return results
    
    async def _connect_receiver(self, name: str, kiwi: KiwiConnection):
        """
        Connecte un récepteur SDR spécifique.
        
        Args:
            name: Nom du récepteur
            kiwi: Connexion KiwiSDR
            
        Returns:
            True si la connexion a réussi, False sinon
        """
        try:
            # Connecter
            if not await kiwi.connect():
                logger.error(f"Échec de la connexion à {name}")
                return False
            
            # Authentifier
            if not await kiwi.authenticate():
                logger.error(f"Échec de l'authentification pour {name}")
                await kiwi.disconnect()
                return False
            
            # Configurer
            frequency = self.config.get('signal_processing', {}).get('initial_frequency', 7100000)  # 7.1 MHz
            mode = KiwiSDRMode(self.config.get('signal_processing', {}).get('modulation_mode', 'am'))
            
            if not await kiwi.set_frequency(frequency):
                logger.error(f"Échec de la configuration de la fréquence pour {name}")
                await kiwi.disconnect()
                return False
            
            if not await kiwi.set_mode(mode):
                logger.error(f"Échec de la configuration du mode pour {name}")
                await kiwi.disconnect()
                return False
            
            logger.info(f"Récepteur {name} connecté et configuré avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à {name}: {e}")
            return False
    
    @timeit
    async def start_streams(self):
        """
        Démarre les flux audio et waterfall pour tous les récepteurs connectés.
        
        Returns:
            Dictionnaire avec les résultats des démarrages de flux
        """
        logger.info("Démarrage des flux audio et waterfall")
        
        results = {
            'audio': {},
            'waterfall': {}
        }
        
        # Si en mode démo, simuler des démarrages de flux réussis
        if self.demo_mode:
            logger.info("Mode démo - Simulation de démarrage des flux")
            for name in self.kiwi_connections:
                results['audio'][name] = True
                results['waterfall'][name] = True
            
            total_audio = sum(1 for result in results['audio'].values() if result)
            total_waterfall = sum(1 for result in results['waterfall'].values() if result)
            
            logger.info(f"Mode démo: {total_audio} flux audio et {total_waterfall} flux waterfall simulés")
            return results
        
        # En mode normal, démarrer les flux pour chaque connexion
        for name, kiwi in self.kiwi_connections.items():
            if not kiwi.is_authenticated or kiwi.state.value != 'ready':
                logger.warning(f"Récepteur {name} non authentifié ou pas prêt, impossible de démarrer les flux")
                results['audio'][name] = False
                results['waterfall'][name] = False
                continue
            
            # Démarrer le flux audio
            audio_result = await self.audio_manager.add_stream(kiwi)
            results['audio'][name] = audio_result
            
            # Démarrer le flux waterfall
            waterfall_result = await self.waterfall_manager.add_stream(kiwi)
            results['waterfall'][name] = waterfall_result
        
        # Compter les succès
        audio_success = sum(1 for result in results['audio'].values() if result)
        waterfall_success = sum(1 for result in results['waterfall'].values() if result)
        
        logger.info(f"{audio_success}/{len(self.kiwi_connections)} flux audio démarrés avec succès")
        logger.info(f"{waterfall_success}/{len(self.kiwi_connections)} flux waterfall démarrés avec succès")
        
        return results
    
    async def start(self):
        """
        Démarre l'application de triangulation SDR.
        
        Returns:
            True si le démarrage a réussi, False sinon
        """
        if self.is_running:
            logger.warning("L'application est déjà en cours d'exécution")
            return True
        
        logger.info("Démarrage de l'application de triangulation SDR")
        
        try:
            # Initialiser l'application
            if not await self.initialize():
                logger.error("Échec de l'initialisation de l'application")
                return False
            
            # Connecter les récepteurs
            connections_result = await self.connect_receivers()
            if not any(connections_result.values()):
                logger.error("Aucun récepteur n'a pu être connecté")
                await self.cleanup()
                return False
            
            # Démarrer les flux
            streams_result = await self.start_streams()
            if not any(streams_result['audio'].values()) and not any(streams_result['waterfall'].values()):
                logger.error("Aucun flux n'a pu être démarré")
                await self.cleanup()
                return False
            
            # Démarrer la boucle principale
            self.is_running = True
            self.stopping_event.clear()
            
            # Démarrer la boucle dans un thread séparé
            asyncio.create_task(self._main_loop())
            
            logger.info("Application démarrée avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage de l'application: {e}")
            await self.cleanup()
            return False
    
    async def _main_loop(self):
        """
        Boucle principale de l'application.
        """
        logger.info("Démarrage de la boucle principale")
        
        try:
            # Variables pour le monitoring des performances
            last_perf_report = time.time()
            perf_report_interval = self.config.get('performance', {}).get('report_interval', 60)  # 1 minute
            
            while self.is_running and not self.stopping_event.is_set():
                loop_start = time.time()
                
                # Vérifier l'état des connexions et reconnecter si nécessaire
                await self._check_connections()
                
                # Traiter les données waterfall
                await self._process_waterfall_data()
                
                # Générer un rapport de performance périodique
                if time.time() - last_perf_report > perf_report_interval:
                    self._generate_performance_report()
                    last_perf_report = time.time()
                
                # Attendre pour limiter l'utilisation CPU
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info("Boucle principale annulée")
        except Exception as e:
            logger.error(f"Erreur dans la boucle principale: {e}")
            self.is_running = False
        finally:
            logger.info("Fin de la boucle principale")
    
    async def _check_connections(self):
        """
        Vérifie l'état des connexions et tente de reconnecter si nécessaire.
        """
        for name, kiwi in list(self.kiwi_connections.items()):
            if not kiwi.is_healthy():
                logger.warning(f"Connexion au récepteur {name} en mauvais état, tentative de reconnexion")
                
                # Tenter une reconnexion
                if await kiwi.reconnect():
                    logger.info(f"Reconnexion réussie pour {name}")
                    
                    # Reconfigurer le récepteur
                    frequency = self.config.get('signal_processing', {}).get('initial_frequency', 7100000)
                    mode = KiwiSDRMode(self.config.get('signal_processing', {}).get('modulation_mode', 'am'))
                    
                    await kiwi.set_frequency(frequency)
                    await kiwi.set_mode(mode)
                    
                    # Redémarrer les flux
                    stream = self.audio_manager.get_stream(name)
                    if stream:
                        await stream.stop()
                        await stream.start()
                    
                    stream = self.waterfall_manager.get_stream(name)
                    if stream:
                        await stream.stop()
                        await stream.start()
                else:
                    logger.error(f"Échec de la reconnexion pour {name}")
    
    @timeit
    async def _process_waterfall_data(self):
        """
        Traite les données waterfall pour la détection de signaux et la triangulation.
        """
        # Dictionnaire pour stocker les données RSSI par fréquence et récepteur
        rssi_by_freq = {}  # {freq: {receiver_name: rssi_value}}
        
        # Récupérer les données waterfall
        waterfall_streams = self.waterfall_manager.get_all_streams()
        if not waterfall_streams:
            return
            
        current_time = time.time()
        
        # Pour chaque récepteur, traiter les données waterfall
        for name, stream in waterfall_streams.items():
            # Récupérer la dernière ligne de waterfall et les fréquences
            spectrum_data = stream.get_latest_spectrum()
            frequencies = stream.get_frequency_range()
            
            if spectrum_data is None or len(spectrum_data) == 0 or frequencies is None:
                continue
            
            # Détecter les signaux
            try:
                # Traitement optimisé du signal si nécessaire
                processed_spectrum = self.signal_processor.process_spectrum(spectrum_data)
                
                # Détecter les signaux avec notre détecteur
                detected_signals = self.signal_detector.detect_from_spectrum(
                    processed_spectrum, frequencies, current_time
                )
                
                # Stocker les signaux détectés pour ce récepteur
                if detected_signals:
                    logger.debug(f"Récepteur {name}: {len(detected_signals)} signaux détectés")
                    
                    # Stocker les valeurs RSSI pour la triangulation
                    for signal in detected_signals:
                        if signal.frequency not in rssi_by_freq:
                            rssi_by_freq[signal.frequency] = {}
                        
                        # Calculer le RSSI avec notre calculateur
                        rssi = self.rssi_computer.compute_rssi(
                            spectrum=processed_spectrum,
                            frequencies=frequencies,
                            center_frequency=signal.frequency,
                            bandwidth=signal.bandwidth
                        )
                        
                        rssi_by_freq[signal.frequency][name] = rssi
                
                # Mettre à jour les signaux actifs
                for signal in detected_signals:
                    self.active_signals[id(signal)] = signal
                    
                # Vérifier les alertes
                alerts = self.alert_manager.check_signals(detected_signals)
                for alert in alerts:
                    logger.warning(f"ALERTE: {alert['rule_name']} - {alert['message']}")
                    
                # Exporter les données si nécessaire
                if self.config.get('data_export', {}).get('auto_export_detected', False):
                    for signal in detected_signals:
                        self.data_exporter.export_signal_detection(signal, name)
                        
                        # Exporter l'audio si c'est un signal important
                        if signal.power > -60 and signal.confidence > 0.8:
                            audio_stream = self.audio_manager.get_stream(name)
                            if audio_stream:
                                audio_data = audio_stream.get_recent_audio(seconds=3.0)
                                if audio_data is not None:
                                    self.data_exporter.export_audio(
                                        audio_data, 
                                        signal.frequency, 
                                        name,
                                        sample_rate=audio_stream.sample_rate
                                    )
                
            except Exception as e:
                logger.error(f"Erreur lors de la détection des signaux pour {name}: {e}")
        
        # Effectuer la triangulation pour les signaux ayant des RSSI de plusieurs récepteurs
        self._perform_triangulation(rssi_by_freq, current_time)
    
    @timeit
    def _perform_triangulation(self, rssi_by_freq, timestamp):
        """
        Effectue la triangulation pour les signaux détectés par plusieurs récepteurs.
        
        Args:
            rssi_by_freq: Dictionnaire {freq: {receiver_name: rssi_value}}
            timestamp: Horodatage de la détection
        """
        # Pour chaque fréquence
        for frequency, rssi_values in rssi_by_freq.items():
            # Ne triangule que si nous avons suffisamment de récepteurs
            min_receivers = self.triangulator.min_receivers
            
            if len(rssi_values) >= min_receivers:
                # Préparer les données de récepteurs pour la triangulation
                receivers_data = {}
                for receiver_name, rssi in rssi_values.items():
                    if receiver_name in self.kiwi_connections:
                        kiwi = self.kiwi_connections[receiver_name]
                        receivers_data[receiver_name] = {
                            'location': kiwi.location,
                            'rssi': rssi
                        }
                
                # Effectuer la triangulation
                try:
                    result = self.triangulator.triangulate(
                        receivers_data=receivers_data,
                        frequency=frequency,
                        timestamp=timestamp
                    )
                    
                    if result:
                        # Stocker le résultat
                        self.triangulation_results[frequency] = result
                        
                        # Log du résultat
                        logger.info(f"Triangulation pour {frequency/1e6:.3f} MHz: "
                                    f"Lat {result.latitude:.5f}, Lon {result.longitude:.5f}, "
                                    f"Rayon {result.radius_km:.1f} km, Confiance {result.confidence:.2f}")
                        
                        # Exporter le résultat si configuré
                        if self.config.get('data_export', {}).get('auto_export_triangulation', False):
                            self.data_exporter.export_triangulation(result)
                    
                except Exception as e:
                    logger.error(f"Erreur lors de la triangulation pour {frequency/1e6:.3f} MHz: {e}")
                
    def _generate_performance_report(self):
        """
        Génère un rapport de performance.
        """
        logger.info("Génération du rapport de performance")
        
        # Récupérer et afficher le rapport
        performance_monitor.print_report(sort_by='total_time', limit=15)
        
        # Réinitialiser les statistiques si configuré
        if self.config.get('performance', {}).get('reset_stats_after_report', False):
            performance_monitor.reset()
            performance_monitor.start()
    
    async def stop(self):
        """
        Arrête l'application de triangulation SDR.
        """
        if not self.is_running:
            logger.warning("L'application n'est pas en cours d'exécution")
            return
        
        logger.info("Arrêt de l'application de triangulation SDR")
        
        # Signaler l'arrêt de la boucle principale
        self.is_running = False
        self.stopping_event.set()
        
        # Attendre un peu pour que la boucle se termine proprement
        await asyncio.sleep(0.5)
        
        # Nettoyer les ressources
        await self.cleanup()
        
        logger.info("Application arrêtée avec succès")
    
    async def cleanup(self):
        """
        Nettoie les ressources utilisées par l'application.
        """
        logger.info("Nettoyage des ressources")
        
        # Arrêter les flux
        await self.audio_manager.stop_all()
        await self.waterfall_manager.stop_all()
        
        # Déconnecter les récepteurs
        for name, kiwi in list(self.kiwi_connections.items()):
            await kiwi.disconnect()
        
        # Nettoyer le processeur de signal
        if hasattr(self, 'signal_processor'):
            self.signal_processor.cleanup()
        
        # Nettoyer le détecteur de signaux
        if self.signal_detector:
            self.signal_detector.reset()
        
        # Nettoyer le calculateur RSSI
        if self.rssi_computer:
            self.rssi_computer.reset()
        
        # Finaliser les exports en cours si nécessaire
        if self.data_exporter:
            self.data_exporter.flush()
        
        # Réinitialiser les données
        self.active_signals.clear()
        self.triangulation_results.clear()
        
        # Arrêter les pools
        thread_pool.stop()
        process_pool.stop()
        
        # Désactiver le monitoring des performances
        performance_monitor.stop()
        
        logger.info("Nettoyage terminé")

    # Méthodes pour interfacer avec le frontend
    
    def get_active_signals(self):
        """
        Récupère les signaux actifs actuellement détectés.
        
        Returns:
            Liste des signaux actifs
        """
        return list(self.active_signals.values())
    
    def get_triangulation_results(self):
        """
        Récupère les résultats de triangulation.
        
        Returns:
            Liste des résultats de triangulation
        """
        return list(self.triangulation_results.values())
    
    def export_data(self, data_type, frequency=None, duration=None, receivers=None):
        """
        Exporte des données sur demande.
        
        Args:
            data_type: Type de données à exporter ('audio', 'spectrum', 'triangulation')
            frequency: Fréquence à exporter (obligatoire pour audio et spectrum)
            duration: Durée en secondes (pour audio)
            receivers: Liste des noms de récepteurs (None = tous)
            
        Returns:
            Chemin vers le fichier exporté ou None en cas d'échec
        """
        if receivers is None:
            receivers = list(self.kiwi_connections.keys())
        
        try:
            if data_type == 'audio':
                if frequency is None:
                    logger.error("Fréquence requise pour l'export audio")
                    return None
                
                if not duration:
                    duration = 5.0  # Valeur par défaut
                
                # Exporter l'audio pour les récepteurs spécifiés
                export_paths = []
                for name in receivers:
                    if name in self.audio_manager.streams:
                        audio_stream = self.audio_manager.streams[name]
                        audio_data = audio_stream.get_recent_audio(seconds=duration)
                        if audio_data is not None:
                            path = self.data_exporter.export_audio(
                                audio_data, 
                                frequency, 
                                name,
                                sample_rate=audio_stream.sample_rate
                            )
                            if path:
                                export_paths.append(path)
                
                return export_paths
                
            elif data_type == 'spectrum':
                if frequency is None:
                    logger.error("Fréquence requise pour l'export du spectre")
                    return None
                
                # Trouver le signal correspondant à cette fréquence
                for signal_id, signal in self.active_signals.items():
                    if abs(signal.frequency - frequency) < signal.bandwidth / 2:
                        # Exporter le spectre pour ce signal
                        return self.data_exporter.export_spectrum_data(signal)
                
                logger.warning(f"Aucun signal actif trouvé à la fréquence {frequency/1e6:.3f} MHz")
                return None
                
            elif data_type == 'triangulation':
                # Si une fréquence est spécifiée, exporter seulement ce résultat
                if frequency is not None:
                    for freq, result in self.triangulation_results.items():
                        if abs(freq - frequency) < 1000:  # Tolérance de 1 kHz
                            return self.data_exporter.export_triangulation(result)
                    
                    logger.warning(f"Aucun résultat de triangulation trouvé pour {frequency/1e6:.3f} MHz")
                    return None
                    
                # Sinon exporter tous les résultats
                export_paths = []
                for result in self.triangulation_results.values():
                    path = self.data_exporter.export_triangulation(result)
                    if path:
                        export_paths.append(path)
                
                return export_paths
                
            else:
                logger.error(f"Type de données inconnu: {data_type}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de l'export de données {data_type}: {e}")
            return None
            
    def set_detection_threshold(self, threshold_db):
        """
        Modifie le seuil de détection des signaux.
        
        Args:
            threshold_db: Nouveau seuil en dB
            
        Returns:
            True si la modification a réussi, False sinon
        """
        if self.signal_detector:
            try:
                self.signal_detector.set_threshold(threshold_db)
                logger.info(f"Seuil de détection modifié: {threshold_db} dB")
                return True
            except Exception as e:
                logger.error(f"Erreur lors de la modification du seuil: {e}")
                return False
        else:
            logger.error("Détecteur de signaux non initialisé")
            return False

    def get_status(self):
        """
        Récupère l'état actuel de l'application.
        
        Returns:
            Dict contenant les informations d'état
        """
        # Collecter les informations sur les récepteurs
        receivers_info = {}
        for name, kiwi in self.kiwi_connections.items():
            receivers_info[name] = {
                "name": name,
                "url": kiwi.url,
                "location": kiwi.location,
                "state": kiwi.state.value if hasattr(kiwi.state, 'value') else str(kiwi.state),
                "is_connected": kiwi.state.value == "connected" if hasattr(kiwi.state, 'value') else False,
                "is_healthy": kiwi.is_healthy() if hasattr(kiwi, 'is_healthy') else True,
                "connected_since": kiwi.connected_since
            }
            
        # En mode démo, forcer le statut à "connecté"
        if self.demo_mode:
            for name in receivers_info:
                receivers_info[name]["state"] = "ready"  # Prêt en mode démo
                receivers_info[name]["is_connected"] = True
                receivers_info[name]["is_healthy"] = True
                if not receivers_info[name]["connected_since"]:
                    receivers_info[name]["connected_since"] = time.time()
            
            # S'il n'y a aucun récepteur et qu'on est en mode démo, ajouter un récepteur démo
            if not receivers_info:
                receivers_info["Récepteur Démo (Paris)"] = {
                    "name": "Récepteur Démo (Paris)",
                    "url": "wss://demo.example.com/kiwi",
                    "location": {
                        "latitude": 48.8566,
                        "longitude": 2.3522
                    },
                    "state": "ready",
                    "is_connected": True,
                    "is_healthy": True,
                    "connected_since": time.time()
                }
        
        # Collecter les informations sur les signaux détectés
        signals_info = []
        for signal_id, signal in self.active_signals.items():
            signals_info.append({
                "id": signal_id,
                "frequency": signal.frequency,
                "bandwidth": signal.bandwidth,
                "power": signal.power,
                "snr": signal.snr,
                "confidence": signal.confidence,
                "type": signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type),
                "first_seen": signal.first_seen,
                "last_seen": signal.last_seen
            })
        
        # Collecter les résultats de triangulation
        triangulation_info = []
        for freq, result in self.triangulation_results.items():
            triangulation_info.append({
                "frequency": freq,
                "latitude": result.latitude,
                "longitude": result.longitude,
                "radius_km": result.radius_km,
                "confidence": result.confidence,
                "timestamp": result.timestamp
            })
        
        # Renvoyer l'état global
        status_value = "inactive"
        if self.is_running:
            status_value = "active"
        elif self.demo_mode:
            status_value = "demo"
        
        # Renvoyer l'état complet
        return {
            "status": status_value,
            "is_running": self.is_running,
            "demo_mode": self.demo_mode,
            "receivers": receivers_info,
            "signals": signals_info,
            "triangulation": triangulation_info,
            "performance": performance_monitor.get_stats() if hasattr(performance_monitor, 'get_stats') else {}
        }


async def main():
    """
    Fonction principale de l'application.
    
    Returns:
        Code de retour (0 si succès, 1 si erreur)
    """
    # Parser les arguments
    parser = argparse.ArgumentParser(description='Outil de triangulation SDR')
    parser.add_argument('--config', type=str, help='Chemin vers le fichier de configuration')
    parser.add_argument('--debug', action='store_true', help='Activer le mode debug')
    parser.add_argument('--port', type=int, default=5000, help='Port du serveur web')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Adresse du serveur web')
    parser.add_argument('--demo', action='store_true', help='Activer le mode démo sans connexions réseau')
    args = parser.parse_args()
    
    # Configurer le logger
    log_level = "DEBUG" if args.debug else "INFO"
    configure_logger({
        "app": {
            "log_level": log_level
        }
    })
    
    # Initialiser l'application
    app = SDRTriangulationApp(config_path=args.config)
    
    # Si mode démo, utiliser des faux récepteurs
    if args.demo:
        logger.info("Mode démo activé - Utilisation de récepteurs simulés")
        app.demo_mode = True
        
        # Ajouter un récepteur démo
        demo_receiver = {
            "name": "Récepteur Démo (Paris)",
            "url": "wss://demo.example.com/kiwi",
            "location": {
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        }
        
        # Ajouter le récepteur démo à l'application
        asyncio.run_coroutine_threadsafe(app._add_receiver(demo_receiver), asyncio.get_event_loop())
        
    try:
        # Démarrer l'application SDR
        if not await app.start():
            logger.error("Échec du démarrage de l'application")
            return 1
            
        # Importer Flask seulement après la configuration de l'application SDR
        from flask import Flask, render_template, jsonify, request, send_from_directory

        # Créer l'application web
        web_app = Flask(__name__, 
                         static_folder='frontend/static', 
                         template_folder='frontend/templates')
        web_app.config['SECRET_KEY'] = app.config.get('server', {}).get('secret_key', 'default_secret_key')
        
        # Route d'accueil
        @web_app.route('/')
        def index():
            return render_template('index.html')
            
        # API pour récupérer l'état de l'application
        @web_app.route('/api/status', methods=['GET'])
        def get_status():
            return jsonify(app.get_status())
            
        # API pour récupérer les données de triangulation
        @web_app.route('/api/triangulation', methods=['GET'])
        def get_triangulation():
            return jsonify(app.get_triangulation_results())
        
        # API pour récupérer les récepteurs
        @web_app.route('/api/receivers', methods=['GET'])
        def get_receivers():
            status = app.get_status()
            return jsonify(list(status['receivers'].values()))
        
        # API pour ajouter un récepteur
        @web_app.route('/api/receivers', methods=['POST'])
        def add_receiver():
            data = request.json
            if not data or 'url' not in data or 'name' not in data:
                return jsonify({"error": "Données incomplètes"}), 400
                
            # Créer la configuration du récepteur
            receiver_config = {
                "url": data['url'],
                "name": data['name'],
                "location": data.get('location', {"latitude": 0, "longitude": 0})
            }
            
            # Tenter d'ajouter le récepteur
            asyncio.run_coroutine_threadsafe(app._add_receiver(receiver_config), asyncio.get_event_loop())
            return jsonify({"success": True, "message": "Récepteur ajouté"})
        
        # API pour démarrer l'écoute
        @web_app.route('/api/listen/start', methods=['POST'])
        def start_listening():
            data = request.json or {}
            frequency = data.get('frequency', 7100000)  # 7.1 MHz par défaut
            mode = data.get('mode', 'am')
            bandwidth = data.get('bandwidth', 3000)
            
            # TODO: Implémenter la logique pour démarrer l'écoute
            # Pour l'instant, retourner simplement une confirmation
            return jsonify({"success": True, "message": "Écoute démarrée"})
        
        # API pour arrêter l'écoute
        @web_app.route('/api/listen/stop', methods=['POST'])
        def stop_listening():
            # TODO: Implémenter la logique pour arrêter l'écoute
            return jsonify({"success": True, "message": "Écoute arrêtée"})
            
        # Lancer le serveur web
        host = args.host
        port = args.port
        logger.info(f"Démarrage du serveur web sur {host}:{port}")
        
        # Utiliser directement Flask au lieu de SocketIO pour éviter les problèmes avec eventlet
        web_app.run(host=host, port=port, debug=args.debug)
        
        return 0
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur dans l'application principale: {e}")
    finally:
        # Nettoyage
        if app.is_running:
            await app.stop()
    
    return 0


async def handle_shutdown(app):
    """
    Gère l'arrêt propre de l'application lors d'un signal de terminaison.
    
    Args:
        app: Instance de l'application SDRTriangulationApp
    """
    logger.info("Signal de terminaison reçu, arrêt en cours...")
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main()) 