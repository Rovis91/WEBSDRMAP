"""
Tests pour le module logger.
"""

import os
import logging
import tempfile
from unittest.mock import patch, MagicMock
import pytest
import time

from src.utils.logger import (
    configure_logger,
    get_logger,
    set_log_level,
    LOG_LEVELS,
    SDRLogger
)


class TestLogger:
    """Tests pour le module de logging."""
    
    def setup_method(self):
        """Configuration avant chaque test."""
        # Créer un répertoire temporaire pour les logs
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = os.path.join(self.temp_dir.name, "test.log")
        
        # Configuration de base pour les tests
        self.test_config = {
            "app": {
                "name": "Test App",
                "version": "0.1.0",
                "log_level": "INFO",
                "log_file": self.log_file
            }
        }
        
        # Garder la trace des handlers pour les fermer proprement
        self.handlers_to_close = []
    
    def teardown_method(self):
        """Nettoyage après chaque test."""
        # Fermer tous les handlers pour éviter les problèmes de fichiers verrouillés
        from src.utils.logger import _logger_instance
        if _logger_instance:
            for handler_name, handler in list(_logger_instance.handlers.items()):
                try:
                    handler.close()
                    _logger_instance.handlers.pop(handler_name, None)
                except Exception:
                    pass
        
        # Fermer les handlers qu'on a enregistrés manuellement
        for handler in self.handlers_to_close:
            try:
                handler.close()
            except Exception:
                pass
        
        # Réinitialiser le singleton du logger
        from src.utils.logger import _logger_instance
        if _logger_instance:
            _logger_instance.is_configured = False
            _logger_instance.handlers = {}
        
        # Attendre un moment pour que les fichiers se libèrent
        time.sleep(0.1)
        
        # Nettoyer le répertoire temporaire avec gestion d'erreur
        try:
            self.temp_dir.cleanup()
        except (PermissionError, OSError):
            # Sur Windows, les fichiers peuvent rester verrouillés un moment
            # Ignorer les erreurs et continuer
            pass
    
    def test_configure_logger(self):
        """Teste la configuration initiale du logger."""
        # Configurer le logger
        logger_instance = configure_logger(self.test_config)
        
        # Vérifier que le logger est configuré
        assert logger_instance.is_configured
        assert logger_instance.log_level == logging.INFO
        assert logger_instance.log_file == self.log_file
        
        # Vérifier que les handlers sont configurés
        assert "console" in logger_instance.handlers
        assert "file" in logger_instance.handlers
        
        # Vérifier que le fichier de log existe
        assert os.path.exists(self.log_file)
    
    def test_get_logger(self):
        """Teste la récupération d'un logger."""
        # Configurer le logger
        configure_logger(self.test_config)
        
        # Récupérer différents loggers
        root_logger = get_logger()
        utils_logger = get_logger("utils")
        
        # Vérifier les noms des loggers
        assert root_logger.name == "root"
        assert utils_logger.name == "src.utils"
        
        # Vérifier les niveaux de log
        assert root_logger.level == logging.INFO
        assert utils_logger.level == logging.NOTSET  # Hérite du niveau parent
    
    def test_set_log_level(self):
        """Teste la modification du niveau de log."""
        # Configurer le logger
        configure_logger(self.test_config)
        
        # Modifier le niveau de log global
        set_log_level("DEBUG")
        
        # Vérifier que le niveau est modifié
        root_logger = get_logger()
        assert root_logger.level == logging.DEBUG
        
        # Modifier le niveau de log d'un module spécifique
        set_log_level("ERROR", "utils")
        
        # Vérifier que le niveau est modifié uniquement pour ce module
        utils_logger = get_logger("utils")
        assert utils_logger.level == logging.ERROR
        assert root_logger.level == logging.DEBUG
    
    def test_log_rotation(self):
        """Teste la rotation des fichiers de log."""
        # Configuration avec une taille maximale très petite pour forcer la rotation
        config = self.test_config.copy()
        
        # Configurer le logger
        logger_instance = configure_logger(config)
        
        # Vérifier que le handler de fichier est un RotatingFileHandler
        file_handler = logger_instance.handlers.get("file")
        assert isinstance(file_handler, logging.handlers.RotatingFileHandler)
        
        # Vérifier les paramètres de rotation
        assert file_handler.maxBytes == 10485760  # 10 MB
        assert file_handler.backupCount == 5
    
    def test_multiple_modules_logging(self):
        """Teste le logging pour différents modules."""
        # Configuration avec des niveaux spécifiques par module
        config = {
            "app": {
                "name": "Test App",
                "version": "0.1.0",
                "log_level": "INFO",
                "log_file": self.log_file
            },
            "utils": {
                "log_level": "DEBUG"
            },
            "sdr_client": {
                "log_level": "WARNING"
            }
        }
        
        # Configurer le logger
        configure_logger(config)
        
        # Récupérer les loggers
        utils_logger = get_logger("utils")
        sdr_logger = get_logger("sdr_client")
        other_logger = get_logger("data_export")
        
        # Vérifier les niveaux de log
        assert utils_logger.level == logging.DEBUG
        assert sdr_logger.level == logging.WARNING
        assert other_logger.level == logging.NOTSET  # Hérite du niveau parent
    
    @patch("logging.handlers.RotatingFileHandler")
    def test_log_file_creation(self, mock_handler):
        """Teste la création du répertoire de logs si nécessaire."""
        # Configurer un chemin de log dans un sous-répertoire
        nested_log_path = os.path.join(self.temp_dir.name, "logs", "app.log")
        config = self.test_config.copy()
        config["app"]["log_file"] = nested_log_path
        
        # S'assurer que le répertoire n'existe pas avant
        log_dir = os.path.dirname(nested_log_path)
        if os.path.exists(log_dir):
            os.rmdir(log_dir)
        
        # Configurer le logger
        configure_logger(config)
        
        # Vérifier que le répertoire a été créé
        assert os.path.exists(log_dir)
    
    def test_default_config_when_no_config(self):
        """Teste l'utilisation de la configuration par défaut si non configuré."""
        # Récupérer un logger sans configurer explicitement
        logger = get_logger("test_module")
        
        # Vérifier que le logger est configuré avec les valeurs par défaut
        assert logger.name == "src.test_module"
        
        # Vérifier que le singleton a été configuré avec les valeurs par défaut
        from src.utils.logger import _logger_instance
        assert _logger_instance.is_configured
        assert _logger_instance.log_level == logging.INFO
        # Check just the basename instead of the full path to be platform-independent
        assert os.path.basename(_logger_instance.log_file) == "app.log" 