"""
Tests unitaires pour les optimisations de performance.

Ce module teste:
- Les fonctions de performance optimisées
- Les gestionnaires de pool de processus et threads
- Les décorateurs de mesure de performance
"""

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock
import platform
from typing import List, Dict, Any

import numpy as np

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.performance import performance_monitor, timeit, process_pool, thread_pool, parallelize
from src.signal_processing.optimized_processing import (
    parallelize_processing, fft_process, detect_peaks, 
    calculate_rssi, OptimizedSignalProcessor
)

# Module-level functions for process pool testing
def square(x):
    return x * x

def cube(x):
    return x ** 3

def double(x):
    return x * 2

def increment(x):
    return x + 1

def compute_factorial(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

def multiply_by_two(data):
    return [item * 2 for item in data]

class TestPerformanceMonitor(unittest.TestCase):
    """Tests pour le moniteur de performance."""
    
    def setUp(self):
        """Configuration initiale pour chaque test."""
        performance_monitor.reset()
        performance_monitor.start()
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        performance_monitor.stop()
    
    def test_record_function_stats(self):
        """Teste l'enregistrement des statistiques de fonction."""
        performance_monitor.record("test_function", 0.5, 100, 50)
        performance_monitor.record("test_function", 1.0, 200, 100)
        
        report = performance_monitor.get_report()
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]['function'], "test_function")
        self.assertEqual(report[0]['count'], 2)
        self.assertAlmostEqual(report[0]['total_time'], 1.5)
        self.assertAlmostEqual(report[0]['avg_time'], 0.75)
    
    def test_performance_report_sorting(self):
        """Teste le tri du rapport de performance."""
        performance_monitor.record("slow_function", 2.0)
        performance_monitor.record("fast_function", 0.5)
        performance_monitor.record("medium_function", 1.0)
        
        # Tri par temps total
        report = performance_monitor.get_report(sort_by='total_time')
        self.assertEqual(report[0]['function'], "slow_function")
        self.assertEqual(report[1]['function'], "medium_function")
        self.assertEqual(report[2]['function'], "fast_function")
        
        # Tri par nombre d'appels
        performance_monitor.record("fast_function", 0.5)  # 2 appels au total
        report = performance_monitor.get_report(sort_by='count')
        self.assertEqual(report[0]['function'], "fast_function")


class TestTimeitDecorator(unittest.TestCase):
    """Tests pour le décorateur timeit."""
    
    def setUp(self):
        """Configuration initiale pour chaque test."""
        performance_monitor.reset()
        performance_monitor.start()
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        performance_monitor.stop()
    
    def test_function_timing(self):
        """Teste que le décorateur timeit mesure correctement le temps d'exécution."""
        @timeit
        def slow_function():
            time.sleep(0.1)
            return 42
        
        result = slow_function()
        self.assertEqual(result, 42)
        
        report = performance_monitor.get_report()
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]['function'], "slow_function")
        self.assertEqual(report[0]['count'], 1)
        # Le temps devrait être d'environ 0.1s, mais avec une marge pour l'overhead
        self.assertGreaterEqual(report[0]['total_time'], 0.08)
        self.assertLess(report[0]['total_time'], 0.2)


class TestProcessPool(unittest.TestCase):
    """Tests pour le gestionnaire de pool de processus."""
    
    def setUp(self):
        """Configuration initiale pour chaque test."""
        process_pool.start()
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        process_pool.stop()
    
    def test_process_pool_submit(self):
        """Teste la soumission d'une tâche au pool de processus."""
        future = process_pool.submit(square, 5)
        result = future.result()
        
        self.assertEqual(result, 25)
    
    def test_process_pool_map(self):
        """Teste le mapping d'une fonction sur plusieurs valeurs."""
        values = [1, 2, 3, 4, 5]
        results = process_pool.map(cube, values)
        
        self.assertEqual(list(results), [1, 8, 27, 64, 125])


class TestThreadPool(unittest.TestCase):
    """Tests pour le gestionnaire de pool de threads."""
    
    def setUp(self):
        """Configuration initiale pour chaque test."""
        thread_pool.start()
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        thread_pool.stop()
    
    def test_thread_pool_submit(self):
        """Teste la soumission d'une tâche au pool de threads."""
        future = thread_pool.submit(double, 5)
        result = future.result()
        
        # Vérifier le résultat
        self.assertEqual(result, 10)
    
    def test_thread_pool_map(self):
        """Teste le mapping d'une fonction sur plusieurs valeurs."""
        values = [1, 2, 3, 4, 5]
        results = thread_pool.map(increment, values)
        
        self.assertEqual(list(results), [2, 3, 4, 5, 6])


@unittest.skipIf(platform.system() == 'Windows', "Skipping parallelize tests on Windows due to multiprocessing issues")
class TestParallelizationDecorators(unittest.TestCase):
    """Tests pour les décorateurs de parallélisation."""
    
    def setUp(self):
        """Configuration initiale pour chaque test."""
        process_pool.start()
        thread_pool.start()
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        process_pool.stop()
        thread_pool.stop()
    
    def test_parallelize_decorator(self):
        """Teste le décorateur parallelize."""
        @parallelize(use_processes=True)
        def decorated_factorial(n):
            return compute_factorial(n)
        
        future = decorated_factorial(5)
        result = future.result()
        
        self.assertEqual(result, 120)
    
    def test_parallelize_processing_decorator(self):
        """Teste le décorateur parallelize_processing."""
        @parallelize_processing
        def decorated_multiply(data):
            return multiply_by_two(data)
        
        data = [1, 2, 3, 4, 5]
        result = decorated_multiply(data)
        
        # Vérifier le résultat
        self.assertEqual(result, [2, 4, 6, 8, 10])


class TestOptimizedSignalProcessing(unittest.TestCase):
    """Tests pour le traitement du signal optimisé."""
    
    def setUp(self):
        """Initialisation avant chaque test."""
        from src.signal_processing.optimized_processing import OptimizedSignalProcessor
        self.processor = OptimizedSignalProcessor(sample_rate=12000, fft_size=1024)
    
    def tearDown(self):
        """Nettoyage après chaque test."""
        self.processor.cleanup()
    
    def test_fft_process(self):
        """Teste le traitement FFT optimisé."""
        # Créer un signal sinusoïdal simple
        t = np.linspace(0, 1, 1024)
        signal = np.sin(2 * np.pi * 100 * t)  # Signal sinusoïdal de 100 Hz
        
        # Calculer le spectre
        spectrum = fft_process(signal)
        
        # Vérifier que le spectre a la bonne forme
        self.assertEqual(len(spectrum), 1024)
        
        # Vérifier qu'il y a un pic au bon endroit
        # Pour une FFT avec fftshift, le pic pour un 100 Hz devrait être autour de 1024/2 + 100
        # Comme nous utilisons np.fft.fftshift dans fft_process
        peak_indices = np.argsort(spectrum)[-5:]  # Top 5 indices
        self.assertTrue(any(abs(idx - (1024//2 + 100)) < 20 for idx in peak_indices) or
                        any(abs(idx - (1024//2 - 100)) < 20 for idx in peak_indices))
    
    def test_detect_peaks(self):
        """Teste la détection de pics optimisée."""
        # Créer un spectre avec des pics connus
        spectrum = np.zeros(100)
        spectrum[20] = 10  # Un grand pic à l'indice 20
        spectrum[60] = 15  # Un autre grand pic à l'indice 60
        spectrum[10] = 5   # Un pic plus petit à l'indice 10
        
        # Détecter les pics
        peaks = detect_peaks(spectrum, threshold=0.3, min_distance=5)
        
        # Trier les pics par valeur
        peaks.sort(key=lambda x: x[1], reverse=True)
        
        # Vérifier que les bons pics sont détectés
        self.assertEqual(len(peaks), 3)
        self.assertEqual(peaks[0][0], 60)  # Le plus grand pic
        self.assertEqual(peaks[1][0], 20)  # Le deuxième plus grand
        self.assertEqual(peaks[2][0], 10)  # Le plus petit
    
    def test_calculate_rssi(self):
        """Teste le calcul du RSSI optimisé."""
        # Créer des échantillons I/Q simulés
        np.random.seed(42)  # Pour la reproductibilité
        real = np.random.normal(0, 0.5, 1000)
        imag = np.random.normal(0, 0.5, 1000)
        iq_samples = real + 1j * imag
        
        # Calculer le RSSI
        rssi = calculate_rssi(iq_samples, window_size=100)
        
        # L'implémentation ajoute +30 dBm comme facteur de calibration
        # ce qui peut rendre le RSSI positif
        self.assertGreater(rssi, -100)  # Valeur en dBm, peut être positive avec le facteur de calibration
        self.assertLess(rssi, 50)  # Mais devrait être dans une plage raisonnable
    
    def test_signal_processor_spectrum(self):
        """Teste le traitement de spectre par le processeur de signal."""
        # Créer un signal sinusoïdal simple
        t = np.linspace(0, 1, 1024)
        signal = np.sin(2 * np.pi * 1000 * t)  # Signal sinusoïdal de 1 kHz
        
        # Calculer le spectre
        spectrum = self.processor.process_spectrum(signal)
        
        # Vérifier que le spectre a la bonne forme
        self.assertEqual(len(spectrum), 1024)
    
    def test_signal_processor_detect_signals(self):
        """Teste la détection de signaux par le processeur de signal."""
        # Créer un spectre avec des pics connus
        spectrum = np.zeros(1024)
        spectrum[300] = 20  # Un grand pic
        spectrum[700] = 30  # Un autre grand pic
        
        # Détecter les signaux
        signals = self.processor.detect_signals(spectrum, threshold_db=-50)
        
        # Vérifier qu'il y a le bon nombre de signaux détectés
        self.assertEqual(len(signals), 2)


if __name__ == '__main__':
    unittest.main() 