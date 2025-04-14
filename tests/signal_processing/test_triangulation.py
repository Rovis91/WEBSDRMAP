"""
Tests unitaires pour le module de triangulation.
"""

import unittest
import math
import time
from unittest.mock import patch, MagicMock
import logging

from src.signal_processing.triangulation import (
    Location, ReliabilityLevel, TriangulationResult,
    GeoUtils, Triangulator, TriangulationManager
)

# Désactiver les logs pendant les tests
logging.disable(logging.CRITICAL)


class TestLocation(unittest.TestCase):
    """Tests pour la classe Location."""
    
    def test_initialization(self):
        """Vérifier l'initialisation d'un objet Location."""
        # Avec altitude
        loc1 = Location(48.8566, 2.3522, 35.0)
        self.assertEqual(loc1.latitude, 48.8566)
        self.assertEqual(loc1.longitude, 2.3522)
        self.assertEqual(loc1.altitude, 35.0)
        
        # Sans altitude (valeur par défaut)
        loc2 = Location(48.8566, 2.3522)
        self.assertEqual(loc2.latitude, 48.8566)
        self.assertEqual(loc2.longitude, 2.3522)
        self.assertEqual(loc2.altitude, 0.0)
    
    def test_string_representation(self):
        """Vérifier la représentation textuelle."""
        loc = Location(48.8566, 2.3522, 35.0)
        self.assertEqual(str(loc), "(48.856600°, 2.352200°, 35.0m)")


class TestReliabilityLevel(unittest.TestCase):
    """Tests pour l'enum ReliabilityLevel."""
    
    def test_reliability_levels(self):
        """Vérifier les valeurs de l'enum."""
        self.assertEqual(ReliabilityLevel.HIGH.value, "high")
        self.assertEqual(ReliabilityLevel.MEDIUM.value, "medium")
        self.assertEqual(ReliabilityLevel.LOW.value, "low")
        self.assertEqual(ReliabilityLevel.VERY_LOW.value, "very_low")


class TestTriangulationResult(unittest.TestCase):
    """Tests pour la classe TriangulationResult."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.location = Location(48.8566, 2.3522)
        self.receivers = {
            "receiver1": Location(48.85, 2.35),
            "receiver2": Location(48.86, 2.36)
        }
        self.rssi_values = {
            "receiver1": -70.0,
            "receiver2": -75.0
        }
        self.result = TriangulationResult(
            estimated_location=self.location,
            error_radius=10.0,
            reliability=ReliabilityLevel.MEDIUM,
            receiver_locations=self.receivers,
            rssi_values=self.rssi_values,
            frequency=14.2e6,
            timestamp=time.time()
        )
    
    def test_initialization(self):
        """Vérifier l'initialisation d'un résultat de triangulation."""
        self.assertEqual(self.result.estimated_location, self.location)
        self.assertEqual(self.result.error_radius, 10.0)
        self.assertEqual(self.result.reliability, ReliabilityLevel.MEDIUM)
        self.assertEqual(self.result.receiver_locations, self.receivers)
        self.assertEqual(self.result.rssi_values, self.rssi_values)
        self.assertEqual(self.result.frequency, 14.2e6)
        self.assertTrue(isinstance(self.result.timestamp, float))
    
    def test_string_representation(self):
        """Vérifier la représentation textuelle."""
        expected = "Position estimée: (48.856600°, 2.352200°, 0.0m), Rayon d'erreur: 10.00 km, Fiabilité: medium"
        self.assertEqual(str(self.result), expected)


class TestGeoUtils(unittest.TestCase):
    """Tests pour la classe GeoUtils."""
    
    def test_haversine_distance(self):
        """Vérifier le calcul de distance Haversine."""
        # Paris
        paris = Location(48.8566, 2.3522)
        # Londres
        london = Location(51.5074, -0.1278)
        
        # Distance approximative Paris-Londres: ~340 km
        distance = GeoUtils.haversine_distance(paris, london)
        self.assertAlmostEqual(distance, 344.0, delta=10.0)  # Ajusté pour correspondre au calcul réel
        
        # Distance symétrique
        distance_reverse = GeoUtils.haversine_distance(london, paris)
        self.assertAlmostEqual(distance, distance_reverse)
        
        # Distance à soi-même = 0
        self.assertAlmostEqual(GeoUtils.haversine_distance(paris, paris), 0.0)
    
    def test_destination_point(self):
        """Vérifier le calcul de point de destination."""
        # Paris
        paris = Location(48.8566, 2.3522)
        
        # 100 km à l'est
        dest = GeoUtils.destination_point(paris, 90.0, 100.0)
        
        # Vérifier que la destination est approximativement à 100 km
        distance = GeoUtils.haversine_distance(paris, dest)
        self.assertAlmostEqual(distance, 100.0, delta=1.0)
        
        # Vérifier que la direction est correcte (à l'est, même latitude mais longitude plus grande)
        self.assertAlmostEqual(dest.latitude, paris.latitude, delta=0.5)
        self.assertTrue(dest.longitude > paris.longitude)
    
    def test_midpoint(self):
        """Vérifier le calcul du point médian."""
        # Quelques points
        locations = [
            Location(48.0, 2.0),
            Location(49.0, 2.0),
            Location(48.5, 3.0)
        ]
        
        # Calculer le point médian
        midpoint = GeoUtils.midpoint(locations)
        
        # Le point médian devrait être approximativement au centre
        self.assertAlmostEqual(midpoint.latitude, 48.5, delta=0.1)
        self.assertAlmostEqual(midpoint.longitude, 2.33, delta=0.1)
        
        # Test avec un seul point
        single_location = [Location(48.0, 2.0)]
        self.assertEqual(GeoUtils.midpoint(single_location), single_location[0])
        
        # Test avec liste vide
        with self.assertRaises(ValueError):
            GeoUtils.midpoint([])


class TestTriangulator(unittest.TestCase):
    """Tests pour la classe Triangulator."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.triangulator = Triangulator()
        
        # Ajouter quelques récepteurs
        self.triangulator.add_receiver("Paris", Location(48.8566, 2.3522))
        self.triangulator.add_receiver("Lyon", Location(45.7640, 4.8357))
        self.triangulator.add_receiver("Marseille", Location(43.2965, 5.3698))
    
    def test_add_and_remove_receiver(self):
        """Vérifier l'ajout et la suppression de récepteurs."""
        # Ajouter un récepteur
        self.triangulator.add_receiver("Bordeaux", Location(44.8378, -0.5792))
        self.assertIn("Bordeaux", self.triangulator.receiver_locations)
        
        # Supprimer un récepteur
        result = self.triangulator.remove_receiver("Bordeaux")
        self.assertTrue(result)
        self.assertNotIn("Bordeaux", self.triangulator.receiver_locations)
        
        # Supprimer un récepteur inexistant
        result = self.triangulator.remove_receiver("NonExistant")
        self.assertFalse(result)
    
    def test_estimate_distances(self):
        """Vérifier l'estimation des distances."""
        # Valeurs RSSI simulées
        rssi_values = {
            "Paris": -70.0,  # Signal fort
            "Lyon": -80.0,   # Signal moyen
            "Marseille": -90.0  # Signal faible
        }
        
        # Estimer les distances
        distances = self.triangulator._estimate_distances(rssi_values, 14.2e6)
        
        # Vérifier les distances relatives (plus le signal est fort, plus la distance est faible)
        self.assertTrue(distances["Paris"] < distances["Lyon"])
        self.assertTrue(distances["Lyon"] < distances["Marseille"])
        
        # Vérifier les limites
        self.assertTrue(0 < distances["Paris"] < self.triangulator.max_distance)
        self.assertTrue(0 < distances["Lyon"] < self.triangulator.max_distance)
        self.assertTrue(0 < distances["Marseille"] < self.triangulator.max_distance)
    
    @patch('src.signal_processing.triangulation.Triangulator._calculate_circle_intersections')
    @patch('src.signal_processing.triangulation.GeoUtils.midpoint')
    def test_triangulate_signal(self, mock_midpoint, mock_intersections):
        """Vérifier la triangulation d'un signal."""
        # Configurer les mocks pour pouvoir contrôler le résultat
        mock_intersections.return_value = [Location(46.0, 3.0), Location(46.1, 3.1)]
        mock_midpoint.return_value = Location(46.05, 3.05)
        
        # Valeurs RSSI simulées
        rssi_values = {
            "Paris": -70.0,
            "Lyon": -80.0,
            "Marseille": -90.0
        }
        
        # On patch la méthode de triangulation par cercles pour retourner un résultat contrôlé
        with patch.object(
            self.triangulator, 
            '_triangulate_by_estimated_circles',
            return_value=TriangulationResult(
                estimated_location=Location(46.05, 3.05),
                error_radius=10.0,
                reliability=ReliabilityLevel.MEDIUM,
                receiver_locations={name: self.triangulator.receiver_locations[name] for name in rssi_values},
                rssi_values=rssi_values,
                frequency=14.2e6,
                timestamp=time.time()
            )
        ):
            # Trianguler le signal
            result = self.triangulator.triangulate_signal(rssi_values, 14.2e6)
            
            # Vérifier le résultat
            self.assertIsNotNone(result)
            self.assertEqual(result.estimated_location.latitude, 46.05)
            self.assertEqual(result.estimated_location.longitude, 3.05)
            
            # Vérifier que le résultat est mis en cache
            self.assertIn(14200, self.triangulator.last_results)
        
        # Test avec un nombre insuffisant de récepteurs
        insufficient_rssi = {"Paris": -70.0}
        result = self.triangulator.triangulate_signal(insufficient_rssi, 14.2e6)
        self.assertIsNone(result)
        
        # Test avec des valeurs RSSI sous le seuil
        under_threshold_rssi = {
            "Paris": -105.0,
            "Lyon": -110.0
        }
        result = self.triangulator.triangulate_signal(under_threshold_rssi, 14.2e6)
        self.assertIsNone(result)
    
    def test_determine_reliability(self):
        """Vérifier la détermination du niveau de fiabilité."""
        # Fiabilité en fonction du nombre de récepteurs et du rayon d'erreur
        
        # Beaucoup de récepteurs, petit rayon d'erreur -> haute fiabilité
        self.assertEqual(
            self.triangulator._determine_reliability(5, 20.0),
            ReliabilityLevel.HIGH
        )
        
        # Beaucoup de récepteurs, grand rayon d'erreur -> fiabilité moyenne
        self.assertEqual(
            self.triangulator._determine_reliability(5, 60.0),
            ReliabilityLevel.MEDIUM
        )
        
        # Beaucoup de récepteurs, très grand rayon d'erreur -> fiabilité faible
        self.assertEqual(
            self.triangulator._determine_reliability(5, 120.0),
            ReliabilityLevel.LOW
        )
        
        # Nombre moyen de récepteurs, petit rayon d'erreur -> fiabilité moyenne
        self.assertEqual(
            self.triangulator._determine_reliability(3, 20.0),
            ReliabilityLevel.MEDIUM
        )
        
        # Peu de récepteurs, petit rayon d'erreur -> fiabilité faible
        self.assertEqual(
            self.triangulator._determine_reliability(2, 20.0),
            ReliabilityLevel.LOW
        )
        
        # Peu de récepteurs, grand rayon d'erreur -> fiabilité très faible
        self.assertEqual(
            self.triangulator._determine_reliability(2, 60.0),
            ReliabilityLevel.VERY_LOW
        )
    
    def test_calculate_bearing(self):
        """Vérifier le calcul de cap."""
        # Paris -> Lyon (sud-est)
        paris = Location(48.8566, 2.3522)
        lyon = Location(45.7640, 4.8357)
        bearing = self.triangulator._calculate_bearing(paris, lyon)
        # Cap approximatif: 150° (sud-est)
        self.assertTrue(120 < bearing < 180)
        
        # Lyon -> Paris (nord-ouest)
        bearing_return = self.triangulator._calculate_bearing(lyon, paris)
        # Cap approximatif: 330° (nord-ouest)
        self.assertTrue(300 < bearing_return < 360)


class TestTriangulationManager(unittest.TestCase):
    """Tests pour la classe TriangulationManager."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        # Créer un mock pour le triangulateur
        self.mock_triangulator = MagicMock()
        self.manager = TriangulationManager(self.mock_triangulator)
        
        # Résultat de triangulation simulé
        self.mock_result = TriangulationResult(
            estimated_location=Location(48.0, 2.0),
            error_radius=10.0,
            reliability=ReliabilityLevel.MEDIUM,
            receiver_locations={"Paris": Location(48.8566, 2.3522)},
            rssi_values={"Paris": -70.0},
            frequency=14.2e6,
            timestamp=time.time()
        )
    
    def test_triangulate(self):
        """Vérifier la triangulation et l'ajout à l'historique."""
        # Configurer le mock pour renvoyer un résultat
        self.mock_triangulator.triangulate_signal.return_value = self.mock_result
        
        # Trianguler un signal
        result = self.manager.triangulate({"Paris": -70.0}, 14.2e6)
        
        # Vérifier le résultat et l'historique
        self.assertEqual(result, self.mock_result)
        self.assertIn(14200, self.manager.history)
        self.assertEqual(len(self.manager.history[14200]), 1)
        
        # Trianguler à nouveau pour tester la limite de l'historique
        for _ in range(self.manager.max_history_length + 10):
            self.manager.triangulate({"Paris": -70.0}, 14.2e6)
        
        # Vérifier que l'historique est limité
        self.assertEqual(len(self.manager.history[14200]), self.manager.max_history_length)
        
        # Tester avec un résultat None
        self.mock_triangulator.triangulate_signal.return_value = None
        result = self.manager.triangulate({"Paris": -70.0}, 14.2e6)
        self.assertIsNone(result)
    
    def test_get_latest_result(self):
        """Vérifier la récupération du dernier résultat."""
        # Ajout d'un résultat à l'historique
        self.manager.history[14200] = [self.mock_result]
        
        # Récupérer le dernier résultat
        result = self.manager.get_latest_result(14.2e6)
        self.assertEqual(result, self.mock_result)
        
        # Fréquence sans historique
        result = self.manager.get_latest_result(7.0e6)
        self.assertIsNone(result)
    
    def test_get_history(self):
        """Vérifier la récupération de l'historique."""
        # Créer quelques résultats avec des timestamps différents
        now = time.time()
        result1 = TriangulationResult(
            estimated_location=Location(48.0, 2.0),
            error_radius=10.0,
            reliability=ReliabilityLevel.MEDIUM,
            receiver_locations={"Paris": Location(48.8566, 2.3522)},
            rssi_values={"Paris": -70.0},
            frequency=14.2e6,
            timestamp=now - 100  # Ancien
        )
        
        result2 = TriangulationResult(
            estimated_location=Location(48.1, 2.1),
            error_radius=15.0,
            reliability=ReliabilityLevel.LOW,
            receiver_locations={"Paris": Location(48.8566, 2.3522)},
            rssi_values={"Paris": -75.0},
            frequency=14.2e6,
            timestamp=now - 10  # Récent
        )
        
        # Ajouter à l'historique
        self.manager.history[14200] = [result1, result2]
        
        # Récupérer tout l'historique
        history = self.manager.get_history(14.2e6)
        self.assertEqual(len(history), 2)
        
        # Récupérer l'historique récent
        recent_history = self.manager.get_history(14.2e6, max_age=50)
        self.assertEqual(len(recent_history), 1)
        self.assertEqual(recent_history[0], result2)
        
        # Fréquence sans historique
        empty_history = self.manager.get_history(7.0e6)
        self.assertEqual(empty_history, [])
    
    def test_get_average_location(self):
        """Vérifier le calcul de la position moyenne."""
        # Créer quelques résultats avec des fiabilités différentes
        result1 = TriangulationResult(
            estimated_location=Location(48.0, 2.0),
            error_radius=10.0,
            reliability=ReliabilityLevel.HIGH,
            receiver_locations={"Paris": Location(48.8566, 2.3522)},
            rssi_values={"Paris": -70.0},
            frequency=14.2e6,
            timestamp=time.time()
        )
        
        result2 = TriangulationResult(
            estimated_location=Location(48.1, 2.1),
            error_radius=15.0,
            reliability=ReliabilityLevel.LOW,
            receiver_locations={"Paris": Location(48.8566, 2.3522)},
            rssi_values={"Paris": -75.0},
            frequency=14.2e6,
            timestamp=time.time()
        )
        
        # Ajouter à l'historique
        self.manager.history[14200] = [result1, result2]
        
        # Configurer le mock pour midpoint
        with patch('src.signal_processing.triangulation.GeoUtils.midpoint') as mock_midpoint:
            mock_midpoint.return_value = Location(48.05, 2.05)
            
            # Calculer la position moyenne
            avg_location = self.manager.get_average_location(14.2e6)
            self.assertEqual(avg_location.latitude, 48.05)
            self.assertEqual(avg_location.longitude, 2.05)
            
            # Vérifier que les positions ont été pondérées (HIGH x4, LOW x1)
            # On s'attend à avoir 5 positions: 4 fois result1 et 1 fois result2
            self.assertEqual(len(mock_midpoint.call_args[0][0]), 5)
            
            # Fréquence sans historique
            avg_location = self.manager.get_average_location(7.0e6)
            self.assertIsNone(avg_location)
    
    def test_clear_history(self):
        """Vérifier l'effacement de l'historique."""
        # Ajouter des résultats à l'historique
        self.manager.history[14200] = [self.mock_result]
        self.manager.history[7000] = [self.mock_result]
        
        # Effacer une fréquence spécifique
        self.manager.clear_history(14.2e6)
        self.assertNotIn(14200, self.manager.history)
        self.assertIn(7000, self.manager.history)
        
        # Effacer tout l'historique
        self.manager.clear_history()
        self.assertEqual(len(self.manager.history), 0)
    
    def test_get_all_frequencies(self):
        """Vérifier la récupération de toutes les fréquences."""
        # Ajouter des résultats à l'historique
        self.manager.history[14200] = [self.mock_result]
        self.manager.history[7000] = [self.mock_result]
        
        # Récupérer toutes les fréquences
        frequencies = self.manager.get_all_frequencies()
        self.assertEqual(len(frequencies), 2)
        self.assertIn(14200000.0, frequencies)
        self.assertIn(7000000.0, frequencies)
    
    def test_receiver_management(self):
        """Vérifier la gestion des récepteurs."""
        # Ajouter un récepteur
        self.manager.add_receiver("Test", Location(0.0, 0.0))
        self.mock_triangulator.add_receiver.assert_called_once_with("Test", Location(0.0, 0.0))
        
        # Supprimer un récepteur
        self.mock_triangulator.remove_receiver.return_value = True
        result = self.manager.remove_receiver("Test")
        self.assertTrue(result)
        self.mock_triangulator.remove_receiver.assert_called_once_with("Test")
        
        # Récupérer les récepteurs
        self.mock_triangulator.receiver_locations = {"Paris": Location(48.8566, 2.3522)}
        receivers = self.manager.get_receivers()
        self.assertEqual(receivers, {"Paris": Location(48.8566, 2.3522)})


# Exécuter les tests
if __name__ == "__main__":
    unittest.main() 