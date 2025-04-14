"""
Module de logging pour l'outil de triangulation SDR.

Ce module permet de:
- Configurer le système de logging pour l'application
- Définir différents niveaux de logging
- Ajouter la rotation des fichiers de log
- Formater les messages de log
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional, Union, List


# Mapping des niveaux de log
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}


class SDRLogger:
    """
    Classe de gestion du logging pour l'application.
    
    Cette classe configure et gère les différents loggers de l'application.
    """
    
    def __init__(self):
        """Initialise le logger avec des valeurs par défaut."""
        self.root_logger = logging.getLogger()
        self.loggers = {}
        self.handlers = {}
        self.log_dir = None
        self.log_file = None
        self.log_level = logging.INFO
        self.is_configured = False
    
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Configure le système de logging à partir du dictionnaire de configuration.
        
        Args:
            config: Dictionnaire de configuration contenant les informations de logging
        """
        # Extraire les paramètres de configuration
        app_config = config.get("app", {})
        
        # Déterminer le niveau de log
        log_level_str = app_config.get("log_level", "INFO")
        self.log_level = LOG_LEVELS.get(log_level_str.upper(), logging.INFO)
        
        # Déterminer le chemin du fichier de log
        self.log_file = app_config.get("log_file", "logs/app.log")
        self.log_dir = os.path.dirname(self.log_file)
        
        # Créer le répertoire de logs s'il n'existe pas
        if self.log_dir and not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        
        # Configurer le logger racine
        self._configure_root_logger()
        
        # Configurer les loggers spécifiques
        self._configure_module_loggers(config)
        
        self.is_configured = True
    
    def _configure_root_logger(self) -> None:
        """Configure le logger racine de l'application."""
        # Supprimer les handlers existants
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)
        
        # Définir le niveau de log
        self.root_logger.setLevel(self.log_level)
        
        # Ajouter le handler de console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.root_logger.addHandler(console_handler)
        self.handlers["console"] = console_handler
        
        # Ajouter le handler de fichier avec rotation
        if self.log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_file,
                maxBytes=10485760,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(self.log_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.root_logger.addHandler(file_handler)
            self.handlers["file"] = file_handler
        
        self.loggers["root"] = self.root_logger
    
    def _configure_module_loggers(self, config: Dict[str, Any]) -> None:
        """
        Configure les loggers spécifiques aux modules de l'application.
        
        Args:
            config: Dictionnaire de configuration
        """
        # Modules à configurer
        modules = ["utils", "sdr_client", "signal_processing", "data_export", "frontend"]
        
        # Configurer chaque module
        for module in modules:
            logger = logging.getLogger(f"src.{module}")
            
            # Appliquer un niveau de log spécifique au module si configuré
            module_level = config.get(module, {}).get("log_level")
            if module_level:
                level = LOG_LEVELS.get(module_level.upper(), self.log_level)
                logger.setLevel(level)
            else:
                # Hériter du niveau du logger parent
                logger.setLevel(logging.NOTSET)
            
            # Ne pas propager les logs au logger parent si des handlers sont ajoutés
            logger.propagate = True
            
            self.loggers[module] = logger
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Récupère un logger par son nom.
        
        Args:
            name: Nom du logger à récupérer
            
        Returns:
            Logger demandé
        """
        if not self.is_configured:
            # Configuration par défaut si pas encore configuré
            self.configure({
                "app": {
                    "log_level": "INFO",
                    "log_file": "logs/app.log"
                }
            })
        
        # Préfixer avec src. si ce n'est pas déjà fait
        if name != "root" and not name.startswith("src."):
            name = f"src.{name}"
        
        # Récupérer ou créer le logger
        if name in self.loggers:
            return self.loggers[name]
        else:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
            return logger
    
    def set_level(self, level: Union[str, int], logger_name: Optional[str] = None) -> None:
        """
        Définit le niveau de log pour un logger spécifique ou pour tous les loggers.
        
        Args:
            level: Niveau de log (soit la chaîne, soit la constante entière)
            logger_name: Nom du logger à modifier (None pour tous)
        """
        # Convertir le niveau de log en entier si nécessaire
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.upper(), logging.INFO)
        
        if logger_name:
            # Modifier un seul logger
            logger = self.get_logger(logger_name)
            logger.setLevel(level)
        else:
            # Modifier tous les loggers
            self.log_level = level
            self.root_logger.setLevel(level)
            
            for handler in self.root_logger.handlers:
                handler.setLevel(level)
            
            for name, logger in self.loggers.items():
                if name != "root":
                    logger.setLevel(level)


# Instance singleton du logger pour l'application
_logger_instance = SDRLogger()


def configure_logger(config: Dict[str, Any]) -> SDRLogger:
    """
    Configure le système de logging à partir du dictionnaire de configuration.
    
    Args:
        config: Dictionnaire de configuration contenant les informations de logging
        
    Returns:
        Instance du logger configuré
    """
    _logger_instance.configure(config)
    return _logger_instance


def get_logger(name: str = "root") -> logging.Logger:
    """
    Récupère un logger configuré par son nom.
    
    Args:
        name: Nom du logger à récupérer (modules ou sous-modules)
        
    Returns:
        Logger configuré
    """
    return _logger_instance.get_logger(name)


def set_log_level(level: Union[str, int], logger_name: Optional[str] = None) -> None:
    """
    Définit le niveau de log pour un logger spécifique ou pour tous les loggers.
    
    Args:
        level: Niveau de log (soit la chaîne, soit la constante entière)
        logger_name: Nom du logger à modifier (None pour tous)
    """
    _logger_instance.set_level(level, logger_name) 