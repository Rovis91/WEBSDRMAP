"""
Tests pour le module config_loader.
"""

import os
import tempfile
from pathlib import Path
import pytest
import yaml

from src.utils.config_loader import (
    load_yaml_config,
    load_env_variables,
    override_config_with_env,
    validate_config,
    load_config,
    get_default_config,
    ConfigurationError
)


class TestConfigLoader:
    """Tests pour le module de chargement de configuration."""

    def test_load_yaml_config_valid(self):
        """Teste le chargement d'un fichier YAML valide."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            config_data = {
                "app": {"name": "Test App", "version": "0.1.0"},
                "server": {"host": "localhost", "port": 5000}
            }
            yaml.dump(config_data, tmp, default_flow_style=False)
            tmp_path = tmp.name

        try:
            config = load_yaml_config(tmp_path)
            assert config["app"]["name"] == "Test App"
            assert config["app"]["version"] == "0.1.0"
            assert config["server"]["host"] == "localhost"
            assert config["server"]["port"] == 5000
        finally:
            os.unlink(tmp_path)

    def test_load_yaml_config_nonexistent(self):
        """Teste le chargement d'un fichier YAML inexistant."""
        with pytest.raises(ConfigurationError):
            load_yaml_config("/path/to/nonexistent/config.yaml")

    def test_load_yaml_config_invalid(self):
        """Teste le chargement d'un fichier YAML invalide."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
            tmp.write(b"invalid: yaml: content: - not properly formatted")
            tmp_path = tmp.name

        try:
            with pytest.raises(ConfigurationError):
                load_yaml_config(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_load_env_variables(self):
        """Teste le chargement des variables d'environnement."""
        with tempfile.NamedTemporaryFile(suffix='.env', delete=False) as tmp:
            tmp.write(b"APP_DEBUG=true\nSERVER_PORT=8080\nEXPORT_PATH=/exports\n")
            tmp_path = tmp.name

        try:
            os.environ["APP_DEBUG"] = "true"  # Ajouter une variable déjà présente
            os.environ["APP_LOG_LEVEL"] = "DEBUG"  # Ajouter une nouvelle variable
            
            env_vars = load_env_variables(tmp_path)
            
            # Ces variables devraient être présentes
            assert "APP_DEBUG" in env_vars
            assert "APP_LOG_LEVEL" in env_vars
            assert "SERVER_PORT" in env_vars
            assert "EXPORT_PATH" in env_vars
            
            # Ces valeurs devraient être correctes
            assert env_vars["APP_DEBUG"] == "true"
            assert env_vars["APP_LOG_LEVEL"] == "DEBUG"
            assert env_vars["SERVER_PORT"] == "8080"
            assert env_vars["EXPORT_PATH"] == "/exports"
            
            # Nettoyage des variables d'environnement
            del os.environ["APP_DEBUG"]
            del os.environ["APP_LOG_LEVEL"]
        finally:
            os.unlink(tmp_path)

    def test_override_config_with_env(self):
        """Teste le remplacement des valeurs de configuration par les variables d'environnement."""
        config = {
            "app": {
                "debug": False,
                "log_level": "INFO"
            },
            "server": {
                "host": "localhost",
                "port": 5000
            }
        }
        
        env_vars = {
            "APP_DEBUG": "true",
            "SERVER_PORT": "8080"
        }
        
        updated_config = override_config_with_env(config, env_vars)
        
        # Les valeurs devraient être remplacées
        assert updated_config["app"]["debug"] is True
        assert updated_config["server"]["port"] == 8080
        
        # Les autres valeurs devraient rester inchangées
        assert updated_config["app"]["log_level"] == "INFO"
        assert updated_config["server"]["host"] == "localhost"

    def test_validate_config_valid(self):
        """Teste la validation d'une configuration valide."""
        config = {
            "app": {
                "name": "Test App",
                "version": "0.1.0"
            },
            "server": {
                "host": "localhost",
                "port": 5000
            },
            "sdr": {
                "receivers": [
                    {
                        "name": "Test Receiver",
                        "url": "wss://test.com/",
                        "location": {
                            "latitude": 0.0,
                            "longitude": 0.0
                        }
                    }
                ]
            }
        }
        
        assert validate_config(config) is True

    def test_validate_config_invalid(self):
        """Teste la validation d'une configuration invalide."""
        # Configuration sans app.name
        config1 = {
            "app": {
                "version": "0.1.0"
            },
            "server": {
                "host": "localhost",
                "port": 5000
            },
            "sdr": {
                "receivers": []
            }
        }
        
        with pytest.raises(ConfigurationError):
            validate_config(config1)
        
        # Configuration avec un récepteur mal formé
        config2 = {
            "app": {
                "name": "Test App",
                "version": "0.1.0"
            },
            "server": {
                "host": "localhost",
                "port": 5000
            },
            "sdr": {
                "receivers": [
                    {
                        "name": "Test Receiver"
                        # Manque url et location
                    }
                ]
            }
        }
        
        with pytest.raises(ConfigurationError):
            validate_config(config2)

    def test_load_config(self, monkeypatch):
        """Teste le chargement complet de la configuration."""
        # Créer un fichier de configuration temporaire
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_config:
            config_data = {
                "app": {"name": "Test App", "version": "0.1.0", "debug": False},
                "server": {"host": "localhost", "port": 5000, "secret_key": "test_key"},
                "sdr": {
                    "receivers": [
                        {
                            "name": "Test Receiver",
                            "url": "wss://test.com/",
                            "location": {
                                "latitude": 0.0,
                                "longitude": 0.0
                            }
                        }
                    ]
                }
            }
            yaml.dump(config_data, tmp_config, default_flow_style=False)
            tmp_config_path = tmp_config.name
        
        # Créer un fichier .env temporaire
        with tempfile.NamedTemporaryFile(suffix='.env', delete=False) as tmp_env:
            tmp_env.write(b"APP_DEBUG=true\nSERVER_PORT=8080\n")
            tmp_env_path = tmp_env.name
        
        try:
            # Charger la configuration
            config = load_config(tmp_config_path, tmp_env_path)
            
            # Vérifier que les valeurs sont correctement chargées et remplacées
            assert config["app"]["name"] == "Test App"
            assert config["app"]["debug"] is True  # Remplacé par la variable d'environnement
            assert config["server"]["port"] == 8080  # Remplacé par la variable d'environnement
            assert config["server"]["secret_key"] == "test_key"
            assert len(config["sdr"]["receivers"]) == 1
            assert config["sdr"]["receivers"][0]["name"] == "Test Receiver"
        finally:
            os.unlink(tmp_config_path)
            os.unlink(tmp_env_path)

    def test_get_default_config(self):
        """Teste la génération d'une configuration par défaut."""
        config = get_default_config()
        
        # Vérifier que les sections principales sont présentes
        assert "app" in config
        assert "server" in config
        assert "sdr" in config
        assert "signal_processing" in config
        assert "triangulation" in config
        assert "export" in config
        
        # Vérifier quelques valeurs spécifiques
        assert config["app"]["name"] == "SDR Triangulation Tool"
        assert config["server"]["host"] == "127.0.0.1"
        assert len(config["sdr"]["receivers"]) == 2
        assert config["signal_processing"]["fft_size"] == 1024 