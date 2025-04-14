"""
Module de triangulation de sources de signaux.

Ce module permet de:
- Trianguler la position d'un émetteur à partir de mesures RSSI
- Intégrer des calculs géographiques pour l'estimation de position
- Fournir un indicateur de fiabilité des estimations
- Prendre en compte les caractéristiques de propagation selon la bande
"""

import numpy as np
import time
from typing import Dict, List, Tuple, Optional, Set, Any, NamedTuple
from dataclasses import dataclass
import logging
import math
from enum import Enum

from src.utils.logger import get_logger
from src.signal_processing.rssi import PropagationModel

# Configuration du logger
logger = get_logger(__name__)


class Location(NamedTuple):
    """
    Tuple nommé représentant une position géographique.
    
    Attributes:
        latitude: Latitude en degrés décimaux
        longitude: Longitude en degrés décimaux
        altitude: Altitude en mètres (optionnelle)
    """
    latitude: float
    longitude: float
    altitude: float = 0.0
    
    def __str__(self) -> str:
        """Représentation textuelle de la position."""
        return f"({self.latitude:.6f}°, {self.longitude:.6f}°, {self.altitude:.1f}m)"


class ReliabilityLevel(Enum):
    """Niveaux de fiabilité d'une triangulation."""
    HIGH = "high"         # Fiabilité élevée
    MEDIUM = "medium"     # Fiabilité moyenne
    LOW = "low"           # Fiabilité faible
    VERY_LOW = "very_low" # Fiabilité très faible


@dataclass
class TriangulationResult:
    """
    Résultat d'une triangulation.
    
    Attributes:
        estimated_location: Position estimée de l'émetteur
        error_radius: Rayon d'erreur estimé en kilomètres
        reliability: Niveau de fiabilité de l'estimation
        receiver_locations: Positions des récepteurs utilisés
        rssi_values: Valeurs RSSI utilisées pour la triangulation
        frequency: Fréquence du signal en Hz
        timestamp: Timestamp de la triangulation
    """
    estimated_location: Location
    error_radius: float
    reliability: ReliabilityLevel
    receiver_locations: Dict[str, Location]
    rssi_values: Dict[str, float]
    frequency: float
    timestamp: float
    
    def __str__(self) -> str:
        """Représentation textuelle du résultat."""
        return (f"Position estimée: {self.estimated_location}, "
                f"Rayon d'erreur: {self.error_radius:.2f} km, "
                f"Fiabilité: {self.reliability.value}")


class GeoUtils:
    """
    Utilitaires pour les calculs géographiques.
    """
    # Rayon moyen de la Terre en kilomètres
    EARTH_RADIUS = 6371.0
    
    @staticmethod
    def haversine_distance(loc1: Location, loc2: Location) -> float:
        """
        Calcule la distance entre deux points en utilisant la formule de Haversine.
        
        Args:
            loc1: Premier point
            loc2: Deuxième point
            
        Returns:
            Distance en kilomètres
        """
        # Convertir les latitudes/longitudes en radians
        lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
        lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)
        
        # Différence de latitude et longitude
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Formule de Haversine
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Distance en kilomètres
        return GeoUtils.EARTH_RADIUS * c
    
    @staticmethod
    def destination_point(start: Location, bearing: float, distance: float) -> Location:
        """
        Calcule le point de destination à partir d'un point de départ,
        d'un cap et d'une distance.
        
        Args:
            start: Point de départ
            bearing: Cap en degrés (0° = Nord, 90° = Est, etc.)
            distance: Distance en kilomètres
            
        Returns:
            Point de destination
        """
        # Convertir en radians
        lat1 = math.radians(start.latitude)
        lon1 = math.radians(start.longitude)
        bearing_rad = math.radians(bearing)
        
        # Distance angulaire
        angular_distance = distance / GeoUtils.EARTH_RADIUS
        
        # Calcul de la nouvelle latitude
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular_distance) +
            math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing_rad)
        )
        
        # Calcul de la nouvelle longitude
        lon2 = lon1 + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1),
            math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2)
        )
        
        # Convertir en degrés
        lat2_deg = math.degrees(lat2)
        lon2_deg = math.degrees(lon2)
        
        # Normaliser la longitude entre -180 et 180 degrés
        lon2_deg = (lon2_deg + 540) % 360 - 180
        
        return Location(lat2_deg, lon2_deg, start.altitude)
    
    @staticmethod
    def midpoint(locations: List[Location]) -> Location:
        """
        Calcule le point médian entre plusieurs points.
        
        Args:
            locations: Liste des points
            
        Returns:
            Point médian
        """
        if not locations:
            raise ValueError("La liste de locations ne peut pas être vide")
        
        if len(locations) == 1:
            return locations[0]
        
        # Convertir en coordonnées cartésiennes
        x_sum = y_sum = z_sum = 0.0
        
        for loc in locations:
            lat_rad = math.radians(loc.latitude)
            lon_rad = math.radians(loc.longitude)
            
            # Coordonnées cartésiennes
            x = math.cos(lat_rad) * math.cos(lon_rad)
            y = math.cos(lat_rad) * math.sin(lon_rad)
            z = math.sin(lat_rad)
            
            x_sum += x
            y_sum += y
            z_sum += z
        
        # Moyennes
        x_avg = x_sum / len(locations)
        y_avg = y_sum / len(locations)
        z_avg = z_sum / len(locations)
        
        # Reconvertir en coordonnées sphériques
        lon_avg = math.atan2(y_avg, x_avg)
        hyp = math.sqrt(x_avg**2 + y_avg**2)
        lat_avg = math.atan2(z_avg, hyp)
        
        # Convertir en degrés
        lat_avg_deg = math.degrees(lat_avg)
        lon_avg_deg = math.degrees(lon_avg)
        
        # Calculer l'altitude moyenne
        alt_avg = sum(loc.altitude for loc in locations) / len(locations)
        
        return Location(lat_avg_deg, lon_avg_deg, alt_avg)


class Triangulator:
    """
    Classe principale pour la triangulation de sources de signaux.
    
    Cette classe utilise les mesures RSSI de plusieurs récepteurs
    pour estimer la position d'un émetteur.
    """
    
    def __init__(self, propagation_model: Optional[PropagationModel] = None):
        """
        Initialise le triangulateur.
        
        Args:
            propagation_model: Modèle de propagation à utiliser (None = créer un nouveau)
        """
        self.propagation_model = propagation_model or PropagationModel()
        self.receiver_locations: Dict[str, Location] = {}
        
        # Paramètres de triangulation
        self.min_receivers = 2  # Nombre minimum de récepteurs pour une triangulation
        self.rssi_threshold = -100.0  # Seuil RSSI minimum en dBm
        self.max_distance = 500.0  # Distance maximale estimée en kilomètres
        
        # Cache des derniers résultats
        self.last_results: Dict[int, TriangulationResult] = {}
        
        logger.info("Triangulateur initialisé")
    
    def add_receiver(self, name: str, location: Location) -> None:
        """
        Ajoute un récepteur avec sa position.
        
        Args:
            name: Nom du récepteur
            location: Position du récepteur
        """
        self.receiver_locations[name] = location
        logger.info(f"Récepteur ajouté: {name} à {location}")
    
    def remove_receiver(self, name: str) -> bool:
        """
        Supprime un récepteur.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si supprimé, False sinon
        """
        if name in self.receiver_locations:
            del self.receiver_locations[name]
            logger.info(f"Récepteur supprimé: {name}")
            return True
        return False
    
    def triangulate_signal(self, 
                          rssi_values: Dict[str, float],
                          frequency: float,
                          timestamp: Optional[float] = None) -> Optional[TriangulationResult]:
        """
        Triangule la position d'un émetteur à partir de mesures RSSI.
        
        Args:
            rssi_values: Dictionnaire {nom_récepteur: valeur_rssi}
            frequency: Fréquence du signal en Hz
            timestamp: Timestamp de la mesure (None = utiliser time.time())
            
        Returns:
            Résultat de triangulation ou None si impossible
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Filtrer les récepteurs valides (présents dans la liste et avec RSSI > seuil)
        valid_receivers = {
            name: rssi for name, rssi in rssi_values.items()
            if name in self.receiver_locations and rssi > self.rssi_threshold
        }
        
        # Vérifier le nombre minimum de récepteurs
        if len(valid_receivers) < self.min_receivers:
            logger.warning(f"Triangulation impossible: seulement {len(valid_receivers)} récepteurs valides")
            return None
        
        # Locations des récepteurs valides
        valid_locations = {name: self.receiver_locations[name] for name in valid_receivers}
        
        # Estimer la distance pour chaque récepteur en fonction du RSSI
        distances = self._estimate_distances(valid_receivers, frequency)
        
        # Trianguler en utilisant les cercles d'estimation
        result = self._triangulate_by_estimated_circles(valid_locations, distances, frequency, timestamp)
        
        if result:
            # Mettre en cache le résultat
            self.last_results[int(frequency/1000)] = result  # Clé = fréquence en kHz
            
            logger.info(f"Triangulation: {result}")
        
        return result
    
    def _estimate_distances(self, 
                          rssi_values: Dict[str, float],
                          frequency: float) -> Dict[str, float]:
        """
        Estime la distance entre chaque récepteur et l'émetteur en fonction du RSSI.
        
        Args:
            rssi_values: Dictionnaire {nom_récepteur: valeur_rssi}
            frequency: Fréquence du signal en Hz
            
        Returns:
            Dictionnaire {nom_récepteur: distance_estimée_km}
        """
        distances = {}
        
        # Paramètres du modèle de propagation
        transmitter_power = 100.0  # Puissance d'émission supposée en Watts
        
        for receiver_name, rssi in rssi_values.items():
            # Estimer la distance en inversant le modèle de propagation
            # Formule: RSSI = Pt - FSPL(d)
            # où FSPL est la perte en espace libre et d est la distance
            
            # Perte en espace libre en dB: FSPL = RSSI - Pt
            free_space_loss = self.propagation_model.estimate_signal_strength(
                frequency, 1.0, transmitter_power
            ) - rssi
            
            # Perte en espace libre en dB: 20*log10(d) + 20*log10(f) + 32.44
            # où d est en km et f en MHz
            # => d = 10^((FSPL - 20*log10(f) - 32.44) / 20)
            f_mhz = frequency / 1e6
            log_term = 20 * math.log10(f_mhz) + 32.44
            
            # Distance en kilomètres
            distance = 10 ** ((free_space_loss - log_term) / 20)
            
            # Limiter à une distance maximale raisonnable
            distance = min(distance, self.max_distance)
            
            distances[receiver_name] = distance
            logger.debug(f"Distance estimée pour {receiver_name}: {distance:.2f} km (RSSI: {rssi:.1f} dBm)")
        
        return distances
    
    def _triangulate_by_estimated_circles(self, 
                                        locations: Dict[str, Location],
                                        distances: Dict[str, float],
                                        frequency: float,
                                        timestamp: float) -> Optional[TriangulationResult]:
        """
        Triangule en utilisant les cercles d'estimation.
        
        Pour chaque récepteur, on trace un cercle de rayon égal à la distance estimée.
        L'émetteur est supposé se trouver à l'intersection de ces cercles.
        
        Args:
            locations: Dictionnaire {nom_récepteur: position}
            distances: Dictionnaire {nom_récepteur: distance_estimée_km}
            frequency: Fréquence du signal en Hz
            timestamp: Timestamp de la mesure
            
        Returns:
            Résultat de triangulation ou None si impossible
        """
        # Points d'intersection potentiels
        intersection_points = []
        
        # Pour chaque paire de récepteurs
        receiver_names = list(locations.keys())
        for i in range(len(receiver_names)):
            for j in range(i+1, len(receiver_names)):
                name1, name2 = receiver_names[i], receiver_names[j]
                loc1, loc2 = locations[name1], locations[name2]
                r1, r2 = distances[name1], distances[name2]
                
                # Calculer la distance entre les deux récepteurs
                d = GeoUtils.haversine_distance(loc1, loc2)
                
                # Si les cercles sont trop éloignés ou l'un contient l'autre, ignorer cette paire
                if d > r1 + r2 or d < abs(r1 - r2):
                    logger.debug(f"Cercles {name1} et {name2} sans intersection valide")
                    continue
                
                # Calculer les points d'intersection (si possible)
                intersections = self._calculate_circle_intersections(loc1, loc2, r1, r2)
                if intersections:
                    intersection_points.extend(intersections)
        
        # Si aucun point d'intersection n'a été trouvé
        if not intersection_points:
            logger.warning("Aucun point d'intersection trouvé entre les cercles")
            
            # Utiliser le barycentre pondéré par l'inverse du RSSI comme fallback
            # Plus le RSSI est élevé, plus le récepteur est proche de l'émetteur
            rssi_values = {name: -1/distances[name] for name in locations}
            
            return self._weighted_centroid_triangulation(locations, rssi_values, frequency, timestamp)
        
        # Calculer le centre de tous les points d'intersection
        estimated_location = GeoUtils.midpoint(intersection_points)
        
        # Calculer le rayon d'erreur (distance max entre la position estimée et tous les points d'intersection)
        error_radius = max(GeoUtils.haversine_distance(estimated_location, p) for p in intersection_points)
        
        # Déterminer la fiabilité en fonction du nombre de récepteurs et du rayon d'erreur
        reliability = self._determine_reliability(len(locations), error_radius)
        
        # Créer le résultat
        rssi_values = {name: -1/distances[name] for name in locations}  # Convertir les distances en RSSI
        result = TriangulationResult(
            estimated_location=estimated_location,
            error_radius=error_radius,
            reliability=reliability,
            receiver_locations=locations,
            rssi_values=rssi_values,
            frequency=frequency,
            timestamp=timestamp
        )
        
        return result
    
    def _calculate_circle_intersections(self, 
                                      center1: Location, 
                                      center2: Location, 
                                      radius1: float, 
                                      radius2: float) -> List[Location]:
        """
        Calcule les points d'intersection entre deux cercles sur une sphère.
        
        Args:
            center1: Centre du premier cercle
            center2: Centre du deuxième cercle
            radius1: Rayon du premier cercle en kilomètres
            radius2: Rayon du deuxième cercle en kilomètres
            
        Returns:
            Liste des points d'intersection (0, 1 ou 2)
        """
        # Distance entre les centres
        d = GeoUtils.haversine_distance(center1, center2)
        
        # Si les cercles sont trop éloignés ou l'un contient l'autre
        if d > radius1 + radius2 or d < abs(radius1 - radius2):
            return []
        
        # Si les cercles sont tangents (un seul point d'intersection)
        if abs(d - (radius1 + radius2)) < 1e-6 or abs(d - abs(radius1 - radius2)) < 1e-6:
            # Calculer le point d'intersection (sur la ligne entre les centres)
            # Proportion de la distance depuis center1
            if d > radius1:
                prop = radius1 / d
                # Calculer le point à cette proportion de la distance
                bearing = self._calculate_bearing(center1, center2)
                return [GeoUtils.destination_point(center1, bearing, radius1)]
            else:
                prop = radius2 / d
                bearing = self._calculate_bearing(center2, center1)
                return [GeoUtils.destination_point(center2, bearing, radius2)]
        
        # Cas général: deux points d'intersection
        # Le calcul exact est complexe sur une sphère, on utilise une approximation
        
        # Calculer le cap de center1 à center2
        bearing = self._calculate_bearing(center1, center2)
        
        # Calculer la distance depuis center1 jusqu'au point médian des intersections
        # Loi des cosinus: a² = b² + c² - 2bc·cos(A)
        # Où a = d, b = radius1, c = radius2
        cos_angle = (radius1**2 + d**2 - radius2**2) / (2 * radius1 * d)
        cos_angle = max(-1.0, min(1.0, cos_angle))  # Assurer que c'est entre -1 et 1
        
        # Distance depuis center1 jusqu'au point médian
        distance_to_mid = radius1 * cos_angle
        
        # Point médian des intersections
        mid_point = GeoUtils.destination_point(center1, bearing, distance_to_mid)
        
        # Calculer la distance perpendiculaire du centre à la ligne des centres
        # Loi de Pythagore: h² = r² - d²
        h = math.sqrt(radius1**2 - distance_to_mid**2)
        
        # Calculer les deux points d'intersection
        bearing_perp1 = (bearing + 90) % 360
        bearing_perp2 = (bearing - 90) % 360
        
        p1 = GeoUtils.destination_point(mid_point, bearing_perp1, h)
        p2 = GeoUtils.destination_point(mid_point, bearing_perp2, h)
        
        return [p1, p2]
    
    def _calculate_bearing(self, start: Location, end: Location) -> float:
        """
        Calcule le cap initial de start à end.
        
        Args:
            start: Point de départ
            end: Point d'arrivée
            
        Returns:
            Cap en degrés (0° = Nord, 90° = Est, etc.)
        """
        # Convertir en radians
        lat1 = math.radians(start.latitude)
        lon1 = math.radians(start.longitude)
        lat2 = math.radians(end.latitude)
        lon2 = math.radians(end.longitude)
        
        # Différence de longitude
        dlon = lon2 - lon1
        
        # Formule du cap initial
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing_rad = math.atan2(y, x)
        
        # Convertir en degrés et normaliser
        bearing_deg = (math.degrees(bearing_rad) + 360) % 360
        
        return bearing_deg 

    def _weighted_centroid_triangulation(self, 
                                      locations: Dict[str, Location],
                                      rssi_values: Dict[str, float],
                                      frequency: float,
                                      timestamp: float) -> TriangulationResult:
        """
        Triangule en utilisant le barycentre pondéré par le RSSI.
        
        Cette méthode est utilisée comme fallback quand la triangulation
        par cercles d'estimation échoue.
        
        Args:
            locations: Dictionnaire {nom_récepteur: position}
            rssi_values: Dictionnaire {nom_récepteur: valeur_rssi}
            frequency: Fréquence du signal en Hz
            timestamp: Timestamp de la mesure
            
        Returns:
            Résultat de triangulation
        """
        # Plus le RSSI est élevé, plus le poids est important
        # On normalise pour avoir des valeurs positives
        min_rssi = min(rssi_values.values())
        weights = {name: rssi - min_rssi + 1.0 for name, rssi in rssi_values.items()}
        
        # Convertir en coordonnées cartésiennes pondérées
        x_sum = y_sum = z_sum = 0.0
        weight_sum = 0.0
        
        for name, weight in weights.items():
            location = locations[name]
            lat_rad = math.radians(location.latitude)
            lon_rad = math.radians(location.longitude)
            
            # Coordonnées cartésiennes
            x = math.cos(lat_rad) * math.cos(lon_rad) * weight
            y = math.cos(lat_rad) * math.sin(lon_rad) * weight
            z = math.sin(lat_rad) * weight
            
            x_sum += x
            y_sum += y
            z_sum += z
            weight_sum += weight
        
        # Moyennes pondérées
        x_avg = x_sum / weight_sum
        y_avg = y_sum / weight_sum
        z_avg = z_sum / weight_sum
        
        # Reconvertir en coordonnées sphériques
        lon_avg = math.atan2(y_avg, x_avg)
        hyp = math.sqrt(x_avg**2 + y_avg**2)
        lat_avg = math.atan2(z_avg, hyp)
        
        # Convertir en degrés
        lat_avg_deg = math.degrees(lat_avg)
        lon_avg_deg = math.degrees(lon_avg)
        
        # Calculer l'altitude moyenne pondérée
        alt_sum = 0.0
        for name, weight in weights.items():
            location = locations[name]
            alt_sum += location.altitude * weight
        
        alt_avg = alt_sum / weight_sum
        
        # Position estimée
        estimated_location = Location(lat_avg_deg, lon_avg_deg, alt_avg)
        
        # Calculer le rayon d'erreur (distance maximale pondérée aux récepteurs)
        max_distance = 0.0
        for name, location in locations.items():
            distance = GeoUtils.haversine_distance(estimated_location, location)
            max_distance = max(max_distance, distance)
        
        # Rayon d'erreur: distance max + 20%
        error_radius = max_distance * 1.2
        
        # Fiabilité: très faible car méthode de fallback
        reliability = ReliabilityLevel.VERY_LOW
        
        logger.info(f"Triangulation par barycentre pondéré: {estimated_location}, "
                  f"rayon d'erreur: {error_radius:.2f} km")
        
        return TriangulationResult(
            estimated_location=estimated_location,
            error_radius=error_radius,
            reliability=reliability,
            receiver_locations=locations,
            rssi_values=rssi_values,
            frequency=frequency,
            timestamp=timestamp
        )
    
    def _determine_reliability(self, num_receivers: int, error_radius: float) -> ReliabilityLevel:
        """
        Détermine le niveau de fiabilité de la triangulation.
        
        Args:
            num_receivers: Nombre de récepteurs utilisés
            error_radius: Rayon d'erreur en kilomètres
            
        Returns:
            Niveau de fiabilité
        """
        # Fiabilité en fonction du nombre de récepteurs
        if num_receivers >= 5:
            base_reliability = ReliabilityLevel.HIGH
        elif num_receivers >= 3:
            base_reliability = ReliabilityLevel.MEDIUM
        else:
            base_reliability = ReliabilityLevel.LOW
        
        # Ajuster en fonction du rayon d'erreur
        if error_radius > 100.0:
            # Dégrader de 2 niveaux
            if base_reliability == ReliabilityLevel.HIGH:
                return ReliabilityLevel.LOW
            else:
                return ReliabilityLevel.VERY_LOW
        elif error_radius > 50.0:
            # Dégrader d'un niveau
            if base_reliability == ReliabilityLevel.HIGH:
                return ReliabilityLevel.MEDIUM
            elif base_reliability == ReliabilityLevel.MEDIUM:
                return ReliabilityLevel.LOW
            else:
                return ReliabilityLevel.VERY_LOW
        
        # Sinon, conserver la fiabilité de base
        return base_reliability


class TriangulationManager:
    """
    Gestionnaire pour coordonner les triangulations et stocker l'historique.
    
    Cette classe permet de:
    - Gérer plusieurs triangulations simultanées à différentes fréquences
    - Maintenir un historique des triangulations récentes
    - Fournir des statistiques et des estimations de qualité
    """
    
    def __init__(self, triangulator: Optional[Triangulator] = None):
        """
        Initialise le gestionnaire de triangulation.
        
        Args:
            triangulator: Triangulateur à utiliser (None = créer un nouveau)
        """
        self.triangulator = triangulator or Triangulator()
        
        # Historique des triangulations
        self.history: Dict[int, List[TriangulationResult]] = {}
        self.max_history_length = 50  # Par fréquence
        
        logger.info("Gestionnaire de triangulation initialisé")
    
    def triangulate(self, 
                   rssi_values: Dict[str, float],
                   frequency: float,
                   timestamp: Optional[float] = None) -> Optional[TriangulationResult]:
        """
        Triangule la position d'un émetteur et stocke le résultat dans l'historique.
        
        Args:
            rssi_values: Dictionnaire {nom_récepteur: valeur_rssi}
            frequency: Fréquence du signal en Hz
            timestamp: Timestamp de la mesure (None = utiliser time.time())
            
        Returns:
            Résultat de triangulation ou None si impossible
        """
        result = self.triangulator.triangulate_signal(rssi_values, frequency, timestamp)
        
        if result:
            # Ajouter à l'historique
            freq_key = int(frequency / 1000)  # Clé = fréquence en kHz
            
            if freq_key not in self.history:
                self.history[freq_key] = []
                
            self.history[freq_key].append(result)
            
            # Limiter la taille de l'historique
            if len(self.history[freq_key]) > self.max_history_length:
                self.history[freq_key] = self.history[freq_key][-self.max_history_length:]
        
        return result
    
    def get_latest_result(self, frequency: float) -> Optional[TriangulationResult]:
        """
        Récupère le dernier résultat pour une fréquence donnée.
        
        Args:
            frequency: Fréquence en Hz
            
        Returns:
            Dernier résultat ou None si aucun disponible
        """
        freq_key = int(frequency / 1000)
        
        if freq_key in self.history and self.history[freq_key]:
            return self.history[freq_key][-1]
        
        return None
    
    def get_history(self, 
                   frequency: float, 
                   max_age: Optional[float] = None) -> List[TriangulationResult]:
        """
        Récupère l'historique pour une fréquence donnée.
        
        Args:
            frequency: Fréquence en Hz
            max_age: Âge maximum en secondes (None = pas de limite)
            
        Returns:
            Liste des résultats
        """
        freq_key = int(frequency / 1000)
        
        if freq_key not in self.history:
            return []
            
        if max_age is None:
            return self.history[freq_key].copy()
        
        # Filtrer par âge
        now = time.time()
        return [r for r in self.history[freq_key] if now - r.timestamp <= max_age]
    
    def get_average_location(self, 
                           frequency: float,
                           max_age: Optional[float] = None) -> Optional[Location]:
        """
        Calcule la position moyenne sur l'historique.
        
        Args:
            frequency: Fréquence en Hz
            max_age: Âge maximum en secondes (None = pas de limite)
            
        Returns:
            Position moyenne ou None si aucun historique
        """
        history = self.get_history(frequency, max_age)
        
        if not history:
            return None
            
        # Extraire les positions et pondérer par la fiabilité
        locations = []
        
        for result in history:
            # Facteur de pondération basé sur la fiabilité
            if result.reliability == ReliabilityLevel.HIGH:
                weight = 4.0
            elif result.reliability == ReliabilityLevel.MEDIUM:
                weight = 2.0
            elif result.reliability == ReliabilityLevel.LOW:
                weight = 1.0
            else:  # VERY_LOW
                weight = 0.5
                
            # Ajouter plusieurs fois selon le poids
            for _ in range(int(weight)):
                locations.append(result.estimated_location)
        
        # Calculer la moyenne
        return GeoUtils.midpoint(locations)
    
    def clear_history(self, frequency: Optional[float] = None) -> None:
        """
        Efface l'historique.
        
        Args:
            frequency: Fréquence en Hz (None = toutes les fréquences)
        """
        if frequency is None:
            self.history.clear()
            logger.info("Historique de triangulation effacé pour toutes les fréquences")
        else:
            freq_key = int(frequency / 1000)
            if freq_key in self.history:
                del self.history[freq_key]
                logger.info(f"Historique de triangulation effacé pour {frequency/1e6:.3f} MHz")
    
    def get_all_frequencies(self) -> List[float]:
        """
        Récupère toutes les fréquences ayant un historique.
        
        Returns:
            Liste des fréquences en Hz
        """
        return [float(key * 1000) for key in self.history.keys()]
    
    def add_receiver(self, name: str, location: Location) -> None:
        """
        Ajoute un récepteur au triangulateur.
        
        Args:
            name: Nom du récepteur
            location: Position du récepteur
        """
        self.triangulator.add_receiver(name, location)
    
    def remove_receiver(self, name: str) -> bool:
        """
        Supprime un récepteur du triangulateur.
        
        Args:
            name: Nom du récepteur
            
        Returns:
            True si supprimé, False sinon
        """
        return self.triangulator.remove_receiver(name)
    
    def get_receivers(self) -> Dict[str, Location]:
        """
        Récupère la liste des récepteurs.
        
        Returns:
            Dictionnaire {nom: position}
        """
        return self.triangulator.receiver_locations.copy() 