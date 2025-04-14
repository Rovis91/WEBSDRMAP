"""
Module signal_processing pour l'outil de triangulation SDR.
Ce module gère le traitement du signal, la détection et la triangulation.
"""

from src.signal_processing.rssi import RSSIMethod, RSSIComputer, RSSIManager, PropagationModel
from src.signal_processing.detection import SignalType, SignalDetection, SignalDetector, AlertManager
from src.signal_processing.triangulation import (
    Location, ReliabilityLevel, TriangulationResult, 
    GeoUtils, Triangulator, TriangulationManager
)
from src.signal_processing.waterfall import (
    ColorScheme, WaterfallConfig, ColorMap, FrequencySelection,
    SpectrogramGenerator, WaterfallProcessor
)

__all__ = [
    'RSSIMethod', 'RSSIComputer', 'RSSIManager', 'PropagationModel',
    'SignalType', 'SignalDetection', 'SignalDetector', 'AlertManager',
    'Location', 'ReliabilityLevel', 'TriangulationResult', 'GeoUtils',
    'Triangulator', 'TriangulationManager',
    'ColorScheme', 'WaterfallConfig', 'ColorMap', 'FrequencySelection',
    'SpectrogramGenerator', 'WaterfallProcessor'
] 