"""
Module d'analyse des performances et d'optimisation.

Ce module fournit:
- Des outils pour identifier les goulots d'étranglement
- Des décorateurs pour mesurer les performances des fonctions
- Des utilitaires pour l'implémentation du multiprocessing/multithreading
- Des classes pour optimiser les tâches intensives
"""

import cProfile
import functools
import logging
import multiprocessing
import os
import pstats
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from src.utils.logger import get_logger

# Configuration du logger
logger = get_logger(__name__)


class PerformanceMonitor:
    """
    Classe pour surveiller les performances des différentes fonctions et méthodes.
    
    Cette classe permet de:
    - Mesurer le temps d'exécution des fonctions
    - Identifier les appels fréquents et coûteux
    - Générer des rapports de performance
    """
    
    def __init__(self):
        """Initialise le moniteur de performance."""
        self.stats = {}
        self.enabled = True
        self._lock = threading.RLock()
    
    def start(self):
        """Active la surveillance des performances."""
        self.enabled = True
    
    def stop(self):
        """Désactive la surveillance des performances."""
        self.enabled = False
    
    def reset(self):
        """Réinitialise les statistiques collectées."""
        with self._lock:
            self.stats = {}
    
    def record(self, function_name: str, execution_time: float, args_size: int = 0, result_size: int = 0):
        """
        Enregistre une mesure de performance pour une fonction.
        
        Args:
            function_name: Nom de la fonction mesurée
            execution_time: Temps d'exécution en secondes
            args_size: Taille approximative des arguments (en octets)
            result_size: Taille approximative du résultat (en octets)
        """
        if not self.enabled:
            return
        
        with self._lock:
            if function_name not in self.stats:
                self.stats[function_name] = {
                    'count': 0,
                    'total_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0,
                    'avg_time': 0.0,
                    'total_args_size': 0,
                    'total_result_size': 0
                }
            
            stats = self.stats[function_name]
            stats['count'] += 1
            stats['total_time'] += execution_time
            stats['min_time'] = min(stats['min_time'], execution_time)
            stats['max_time'] = max(stats['max_time'], execution_time)
            stats['avg_time'] = stats['total_time'] / stats['count']
            stats['total_args_size'] += args_size
            stats['total_result_size'] += result_size
    
    def get_report(self, sort_by: str = 'total_time', limit: int = 10) -> List[Dict[str, Any]]:
        """
        Génère un rapport sur les performances des fonctions mesurées.
        
        Args:
            sort_by: Critère de tri ('total_time', 'avg_time', 'count')
            limit: Nombre maximum de fonctions à inclure dans le rapport
            
        Returns:
            Liste des fonctions avec leurs statistiques, triée selon le critère spécifié
        """
        with self._lock:
            if not self.stats:
                return []
            
            # Créer une liste de dictionnaires avec le nom de la fonction et ses stats
            report = []
            for func_name, stats in self.stats.items():
                func_stats = stats.copy()
                func_stats['function'] = func_name
                report.append(func_stats)
            
            # Trier le rapport selon le critère spécifié
            report.sort(key=lambda x: x[sort_by], reverse=True)
            
            # Limiter le nombre d'entrées
            return report[:limit]
    
    def print_report(self, sort_by: str = 'total_time', limit: int = 10):
        """
        Affiche un rapport de performance dans les logs.
        
        Args:
            sort_by: Critère de tri ('total_time', 'avg_time', 'count')
            limit: Nombre maximum de fonctions à inclure dans le rapport
        """
        report = self.get_report(sort_by, limit)
        if not report:
            logger.info("Aucune statistique de performance disponible.")
            return
        
        logger.info("=== Rapport de performance ===")
        logger.info(f"Trié par: {sort_by}, limité à: {limit} fonctions")
        logger.info("{:<40} {:>10} {:>12} {:>12} {:>12}".format(
            "Fonction", "Appels", "Temps total", "Temps moyen", "Temps max"
        ))
        logger.info("-" * 90)
        
        for stats in report:
            logger.info("{:<40} {:>10} {:>12.6f} {:>12.6f} {:>12.6f}".format(
                stats['function'],
                stats['count'],
                stats['total_time'],
                stats['avg_time'],
                stats['max_time']
            ))


# Créer une instance globale du moniteur de performance
performance_monitor = PerformanceMonitor()


def profile(func: Callable) -> Callable:
    """
    Décorateur pour profiler une fonction avec cProfile.
    
    Args:
        func: Fonction à profiler
        
    Returns:
        Fonction décorée qui sera profilée à chaque appel
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        try:
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()
            return result
        finally:
            s = StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(20)  # Afficher les 20 premières fonctions
            logger.debug(f"Profil de performance pour {func.__name__}:\n{s.getvalue()}")
    return wrapper


def timeit(func: Callable) -> Callable:
    """
    Décorateur pour mesurer le temps d'exécution d'une fonction.
    
    Args:
        func: Fonction à mesurer
        
    Returns:
        Fonction décorée qui enregistrera son temps d'exécution
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Estimation grossière de la taille des arguments et du résultat
        args_size = sum(get_approximate_size(arg) for arg in args)
        for _, value in kwargs.items():
            args_size += get_approximate_size(value)
        result_size = get_approximate_size(result)
        
        performance_monitor.record(
            func.__name__, 
            execution_time,
            args_size,
            result_size
        )
        
        return result
    return wrapper


def get_approximate_size(obj: Any) -> int:
    """
    Obtient une estimation grossière de la taille d'un objet en mémoire.
    
    Args:
        obj: Objet dont on veut estimer la taille
        
    Returns:
        Taille approximative en octets
    """
    if obj is None:
        return 0
    
    if isinstance(obj, (int, float, bool)):
        return 8
    
    if isinstance(obj, str):
        return len(obj) * 2
    
    if isinstance(obj, bytes):
        return len(obj)
    
    if isinstance(obj, (list, tuple)):
        return sum(get_approximate_size(item) for item in obj)
    
    if isinstance(obj, dict):
        return sum(get_approximate_size(k) + get_approximate_size(v) for k, v in obj.items())
    
    if isinstance(obj, np.ndarray):
        return obj.nbytes
    
    # Pour les autres objets, utiliser une estimation par défaut
    return 64  # Taille arbitraire pour les objets non reconnus


class ProcessPoolManager:
    """
    Gestionnaire de pool de processus pour les tâches intensives.
    
    Cette classe facilite l'utilisation du multiprocessing pour
    les opérations lourdes comme le traitement du signal.
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialise le gestionnaire de pool de processus.
        
        Args:
            max_workers: Nombre maximum de processus (None = nombre de CPU)
        """
        self.max_workers = max_workers or min(32, multiprocessing.cpu_count() + 4)
        self.executor = None
        self.futures = []
        self._lock = threading.RLock()
    
    def start(self):
        """Démarre le pool de processus."""
        with self._lock:
            if self.executor is None:
                self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
                logger.info(f"Pool de processus démarré avec {self.max_workers} workers")
    
    def stop(self):
        """Arrête le pool de processus."""
        with self._lock:
            if self.executor is not None:
                self.executor.shutdown(wait=True)
                self.executor = None
                self.futures = []
                logger.info("Pool de processus arrêté")
    
    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """
        Soumet une tâche au pool de processus.
        
        Args:
            fn: Fonction à exécuter
            *args: Arguments de la fonction
            **kwargs: Arguments nommés de la fonction
            
        Returns:
            Future représentant le résultat de la tâche
            
        Raises:
            RuntimeError: Si le pool n'est pas démarré
        """
        with self._lock:
            if self.executor is None:
                raise RuntimeError("Le pool de processus n'est pas démarré")
            
            future = self.executor.submit(fn, *args, **kwargs)
            self.futures.append(future)
            return future
    
    def map(self, fn: Callable, *iterables, timeout: Optional[float] = None) -> List[Any]:
        """
        Applique une fonction à chaque élément des itérables en parallèle.
        
        Args:
            fn: Fonction à appliquer
            *iterables: Itérables contenant les arguments
            timeout: Temps maximum d'attente en secondes
            
        Returns:
            Liste des résultats
            
        Raises:
            RuntimeError: Si le pool n'est pas démarré
        """
        with self._lock:
            if self.executor is None:
                raise RuntimeError("Le pool de processus n'est pas démarré")
            
            return list(self.executor.map(fn, *iterables, timeout=timeout))


class ThreadPoolManager:
    """
    Gestionnaire de pool de threads pour les tâches I/O bound.
    
    Cette classe facilite l'utilisation du multithreading pour
    les opérations limitées par l'I/O comme les connexions réseau.
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialise le gestionnaire de pool de threads.
        
        Args:
            max_workers: Nombre maximum de threads (None = nombre de CPU * 5)
        """
        self.max_workers = max_workers or min(32, (multiprocessing.cpu_count() + 4) * 5)
        self.executor = None
        self.futures = []
        self._lock = threading.RLock()
    
    def start(self):
        """Démarre le pool de threads."""
        with self._lock:
            if self.executor is None:
                self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
                logger.info(f"Pool de threads démarré avec {self.max_workers} workers")
    
    def stop(self):
        """Arrête le pool de threads."""
        with self._lock:
            if self.executor is not None:
                self.executor.shutdown(wait=True)
                self.executor = None
                self.futures = []
                logger.info("Pool de threads arrêté")
    
    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """
        Soumet une tâche au pool de threads.
        
        Args:
            fn: Fonction à exécuter
            *args: Arguments de la fonction
            **kwargs: Arguments nommés de la fonction
            
        Returns:
            Future représentant le résultat de la tâche
            
        Raises:
            RuntimeError: Si le pool n'est pas démarré
        """
        with self._lock:
            if self.executor is None:
                raise RuntimeError("Le pool de threads n'est pas démarré")
            
            future = self.executor.submit(fn, *args, **kwargs)
            self.futures.append(future)
            return future
    
    def map(self, fn: Callable, *iterables, timeout: Optional[float] = None) -> List[Any]:
        """
        Applique une fonction à chaque élément des itérables en parallèle.
        
        Args:
            fn: Fonction à appliquer
            *iterables: Itérables contenant les arguments
            timeout: Temps maximum d'attente en secondes
            
        Returns:
            Liste des résultats
            
        Raises:
            RuntimeError: Si le pool n'est pas démarré
        """
        with self._lock:
            if self.executor is None:
                raise RuntimeError("Le pool de threads n'est pas démarré")
            
            return list(self.executor.map(fn, *iterables, timeout=timeout))


# Gestionnaires de pool globaux pour les processus et les threads
process_pool = ProcessPoolManager()
thread_pool = ThreadPoolManager()


def parallelize(use_processes: bool = True):
    """
    Décorateur pour paralléliser une fonction.
    
    Args:
        use_processes: True pour utiliser des processus, False pour des threads
        
    Returns:
        Décorateur qui soumettra la fonction au pool approprié
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            pool = process_pool if use_processes else thread_pool
            try:
                pool.start()
                return pool.submit(func, *args, **kwargs)
            except Exception as e:
                logger.error(f"Erreur lors de la parallélisation de {func.__name__}: {e}")
                # Exécuter en synchrone si la parallélisation échoue
                return func(*args, **kwargs)
        return wrapper
    return decorator


def analyze_bottlenecks(duration: int = 60):
    """
    Analyse les goulots d'étranglement dans l'application.
    
    Exécute l'application pendant une durée spécifiée et collecte
    des statistiques de performance pour identifier les fonctions critiques.
    
    Args:
        duration: Durée de l'analyse en secondes
        
    Returns:
        Rapport d'analyse des goulots d'étranglement
    """
    logger.info(f"Démarrage de l'analyse des goulots d'étranglement (durée: {duration}s)")
    
    # Activer le monitoring des performances
    performance_monitor.reset()
    performance_monitor.start()
    
    # Attendre la durée spécifiée pour collecter des données
    time.sleep(duration)
    
    # Désactiver le monitoring et générer un rapport
    performance_monitor.stop()
    report = performance_monitor.get_report(sort_by='total_time', limit=20)
    
    # Afficher le rapport
    performance_monitor.print_report(sort_by='total_time', limit=20)
    
    # Identifier les fonctions critiques (celles qui prennent plus de 5% du temps total)
    total_time = sum(stats['total_time'] for stats in report)
    critical_functions = []
    
    for stats in report:
        if stats['total_time'] / total_time > 0.05:  # Plus de 5% du temps total
            critical_functions.append({
                'function': stats['function'],
                'time_percentage': (stats['total_time'] / total_time) * 100,
                'call_count': stats['count'],
                'avg_time': stats['avg_time']
            })
    
    logger.info("=== Fonctions critiques (goulots d'étranglement potentiels) ===")
    for func in critical_functions:
        logger.info(f"{func['function']}: {func['time_percentage']:.2f}% du temps total, {func['call_count']} appels")
    
    return {
        'report': report,
        'critical_functions': critical_functions,
        'total_time': total_time
    } 