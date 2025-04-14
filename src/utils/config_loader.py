"""
Module de chargement de la configuration pour l'outil de triangulation SDR.

Ce module permet de:
- Charger les fichiers de configuration YAML
- Charger les variables d'environnement
- Valider la configuration
- Fournir une configuration par défaut
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

import yaml
from dotenv import load_dotenv

# Configuration du logging pour ce module
logger = logging.getLogger(__name__)

# Définition des chemins par défaut
DEFAULT_CONFIG_PATH = os.path.join("config", "default_config.yaml")
DEFAULT_ENV_PATH = ".env"


class ConfigurationError(Exception):
    """Exception levée lors d'erreurs de configuration."""
    pass


def load_yaml_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Charge un fichier de configuration YAML.
    
    Args:
        config_path: Chemin vers le fichier YAML
        
    Returns:
        Dict contenant la configuration
        
    Raises:
        ConfigurationError: Si le fichier n'existe pas ou n'est pas valide
    """
    try:
        config_path = Path(config_path)
        if not config_path.exists():
            raise ConfigurationError(f"Le fichier de configuration '{config_path}' n'existe pas")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        if not isinstance(config, dict):
            raise ConfigurationError(f"Le fichier de configuration '{config_path}' ne contient pas un dictionnaire valide")
            
        logger.info(f"Configuration chargée depuis '{config_path}'")
        return config
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Erreur lors du chargement du fichier YAML '{config_path}': {str(e)}")
    except Exception as e:
        raise ConfigurationError(f"Erreur lors du chargement de la configuration '{config_path}': {str(e)}")


def load_env_variables(env_path: Union[str, Path] = DEFAULT_ENV_PATH) -> Dict[str, str]:
    """
    Charge les variables d'environnement depuis un fichier .env.
    
    Args:
        env_path: Chemin vers le fichier .env
        
    Returns:
        Dict contenant les variables d'environnement
        
    Notes:
        Ne lève pas d'exception si le fichier .env n'existe pas
    """
    env_vars = {}
    
    try:
        env_path = Path(env_path)
        if env_path.exists():
            # Charger les variables d'environnement
            load_dotenv(env_path)
            logger.info(f"Variables d'environnement chargées depuis '{env_path}'")
            
            # Extraire celles qui commencent par APP_, SERVER_, etc.
            prefixes = ["APP_", "SERVER_", "EXPORT_", "LOG_", "CONFIG_"]
            for key, value in os.environ.items():
                if any(key.startswith(prefix) for prefix in prefixes):
                    env_vars[key] = value
        else:
            logger.warning(f"Fichier .env '{env_path}' non trouvé, utilisation des variables d'environnement système")
            
        return env_vars
    except Exception as e:
        logger.warning(f"Erreur lors du chargement des variables d'environnement: {str(e)}")
        return {}


def override_config_with_env(config: Dict[str, Any], env_vars: Dict[str, str]) -> Dict[str, Any]:
    """
    Remplace les valeurs de configuration par les variables d'environnement correspondantes.
    
    Args:
        config: Dictionnaire de configuration
        env_vars: Dictionnaire des variables d'environnement
        
    Returns:
        Dict contenant la configuration mise à jour
    """
    # Mapping entre les variables d'environnement et les clés de configuration
    env_mapping = {
        "APP_DEBUG": ["app", "debug"],
        "APP_LOG_LEVEL": ["app", "log_level"],
        "SERVER_HOST": ["server", "host"],
        "SERVER_PORT": ["server", "port"],
        "SECRET_KEY": ["server", "secret_key"],
        "EXPORT_PATH": ["export", "export_path"],
        "LOG_FILE": ["app", "log_file"],
        "CONFIG_FILE": ["app", "config_file"]
    }
    
    # Convertir les valeurs de chaîne en types appropriés
    type_converters = {
        bool: lambda x: x.lower() in ("true", "yes", "1", "y"),
        int: int,
        float: float,
        str: str
    }
    
    # Mise à jour de la configuration
    for env_var, config_path in env_mapping.items():
        if env_var in env_vars:
            # Accéder à la configuration imbriquée
            config_section = config
            for i, key in enumerate(config_path[:-1]):
                if key not in config_section:
                    logger.warning(f"Clé de configuration '{'.'.join(config_path[:i+1])}' non trouvée")
                    break
                config_section = config_section[key]
            
            # Mettre à jour la valeur si la section existe
            last_key = config_path[-1]
            if last_key in config_section:
                original_value = config_section[last_key]
                value_type = type(original_value)
                
                try:
                    # Convertir la valeur au bon type
                    if value_type in type_converters:
                        converter = type_converters[value_type]
                        config_section[last_key] = converter(env_vars[env_var])
                        logger.debug(f"Variable d'environnement '{env_var}' appliquée à '{'.'.join(config_path)}'")
                    else:
                        logger.warning(f"Type non pris en charge pour '{env_var}': {value_type}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Erreur lors de la conversion de '{env_var}': {str(e)}")
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Valide la configuration en vérifiant les champs obligatoires.
    
    Args:
        config: Dictionnaire de configuration
        
    Returns:
        True si la configuration est valide, False sinon
        
    Raises:
        ConfigurationError: Si la configuration est invalide
    """
    # Liste des champs obligatoires
    required_fields = [
        ["app", "name"],
        ["app", "version"],
        ["server", "host"],
        ["server", "port"],
        ["sdr", "receivers"]
    ]
    
    # Vérification des champs obligatoires
    for field_path in required_fields:
        config_section = config
        for i, key in enumerate(field_path):
            if key not in config_section:
                raise ConfigurationError(f"Champ de configuration obligatoire '{'.'.join(field_path[:i+1])}' non trouvé")
            config_section = config_section[key]
    
    # Validation spécifique pour les récepteurs SDR
    if not isinstance(config.get("sdr", {}).get("receivers", []), list):
        raise ConfigurationError("Le champ 'sdr.receivers' doit être une liste")
    
    for i, receiver in enumerate(config.get("sdr", {}).get("receivers", [])):
        if not isinstance(receiver, dict):
            raise ConfigurationError(f"Le récepteur #{i+1} doit être un dictionnaire")
        
        for field in ["name", "url"]:
            if field not in receiver:
                raise ConfigurationError(f"Champ obligatoire '{field}' non trouvé dans le récepteur #{i+1}")
        
        if "location" not in receiver:
            raise ConfigurationError(f"Champ obligatoire 'location' non trouvé dans le récepteur #{i+1}")
        
        for field in ["latitude", "longitude"]:
            if field not in receiver.get("location", {}):
                raise ConfigurationError(f"Champ obligatoire 'location.{field}' non trouvé dans le récepteur #{i+1}")
    
    return True


def load_config(config_path: Optional[str] = None, env_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge la configuration depuis les fichiers et les variables d'environnement.
    
    Args:
        config_path: Chemin vers le fichier de configuration YAML (None pour utiliser la valeur par défaut)
        env_path: Chemin vers le fichier .env (None pour utiliser la valeur par défaut)
        
    Returns:
        Dict contenant la configuration complète
        
    Raises:
        ConfigurationError: Si la configuration est invalide
    """
    # Utilisation des chemins par défaut si non spécifiés
    config_path = config_path or os.environ.get("CONFIG_FILE", DEFAULT_CONFIG_PATH)
    env_path = env_path or DEFAULT_ENV_PATH
    
    # Chargement de la configuration
    config = load_yaml_config(config_path)
    
    # Chargement des variables d'environnement
    env_vars = load_env_variables(env_path)
    
    # Remplacement des valeurs de configuration par les variables d'environnement
    config = override_config_with_env(config, env_vars)
    
    # Validation de la configuration
    validate_config(config)
    
    logger.info("Configuration chargée et validée avec succès")
    return config


def get_default_config() -> Dict[str, Any]:
    """
    Retourne une configuration par défaut minimale pour un démarrage rapide.
    
    Returns:
        Dict contenant la configuration par défaut
    """
    return {
        "app": {
            "name": "SDR Triangulation Tool",
            "version": "0.1.0",
            "debug": True,
            "log_level": "INFO",
            "log_file": "logs/app.log"
        },
        "server": {
            "host": "127.0.0.1",
            "port": 5000,
            "secret_key": "default_secret_key_change_me"
        },
        "sdr": {
            "connection_timeout": 30,
            "reconnect_attempts": 3,
            "reconnect_delay": 5,
            "max_connections": 2,
            "receivers": [
                {
                    "name": "WebSDR Twente (Netherlands)",
                    "url": "wss://websdr.ewi.utwente.nl:8901/",
                    "location": {
                        "latitude": 52.2389,
                        "longitude": 6.8575
                    }
                },
                {
                    "name": "KiwiSDR Demo",
                    "url": "wss://kiwisdr.com/kiwi/",
                    "location": {
                        "latitude": 37.7749,
                        "longitude": -122.4194
                    }
                }
            ]
        },
        "signal_processing": {
            "fft_size": 1024,
            "sample_rate": 12000,
            "rssi_threshold": -85,
            "detection_sensitivity": 0.75,
            "calibration_factor": 1.0,
            "waterfall": {
                "colormap": "viridis",
                "min_level": -120,
                "max_level": -20
            }
        },
        "triangulation": {
            "min_receivers": 2,
            "confidence_margin": 0.85,
            "propagation_model": "free_space",
            "update_interval": 5
        },
        "export": {
            "audio_format": "wav",
            "data_format": "json",
            "export_path": "exports/",
            "max_recording_time": 300
        }
    } 