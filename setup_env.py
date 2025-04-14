#!/usr/bin/env python
"""
Script de configuration de l'environnement de développement pour l'outil de triangulation SDR.

Ce script:
1. Crée un environnement virtuel Python
2. Installe les dépendances requises
3. Configure les outils de test
4. Met en place les hooks pre-commit (optionnel)
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


def print_step(message):
    """Affiche un message d'étape formatté."""
    print(f"\n{'='*80}\n{message}\n{'='*80}")


def run_command(command, cwd=None):
    """
    Exécute une commande shell et affiche sa sortie.
    
    Args:
        command: Commande à exécuter (liste ou chaîne)
        cwd: Répertoire de travail
        
    Returns:
        True si la commande s'est exécutée avec succès, False sinon
    """
    print(f"> {command if isinstance(command, str) else ' '.join(command)}")
    
    try:
        if isinstance(command, str):
            result = subprocess.run(
                command, 
                shell=True, 
                check=True, 
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
        else:
            result = subprocess.run(
                command,
                check=True, 
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
        if result.stdout:
            print(result.stdout)
            
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution de la commande: {e}")
        if e.stdout:
            print(e.stdout)
        return False


def create_virtualenv():
    """
    Crée un environnement virtuel Python.
    
    Returns:
        Path vers l'environnement virtuel ou None en cas d'échec
    """
    print_step("Création de l'environnement virtuel Python")
    
    venv_path = Path("venv")
    if venv_path.exists():
        print(f"L'environnement virtuel existe déjà dans {venv_path}")
        return venv_path
    
    # Créer l'environnement virtuel
    if not run_command([sys.executable, "-m", "venv", str(venv_path)]):
        return None
    
    print(f"Environnement virtuel créé dans {venv_path}")
    return venv_path


def install_dependencies(venv_path):
    """
    Installe les dépendances dans l'environnement virtuel.
    
    Args:
        venv_path: Chemin vers l'environnement virtuel
        
    Returns:
        True si l'installation a réussi, False sinon
    """
    print_step("Installation des dépendances")
    
    # Déterminer le chemin vers pip
    if platform.system() == "Windows":
        pip_path = venv_path / "Scripts" / "pip"
    else:
        pip_path = venv_path / "bin" / "pip"
    
    # Mettre à jour pip
    if not run_command([str(pip_path), "install", "--upgrade", "pip"]):
        return False
    
    # Installer les dépendances
    if not run_command([str(pip_path), "install", "-r", "requirements.txt"]):
        return False
    
    # Installer les dépendances de développement
    dev_dependencies = [
        "pytest==7.3.1",
        "pytest-cov==4.1.0",
        "flake8==6.0.0",
        "black==23.3.0",
        "isort==5.12.0",
        "pre-commit==3.3.1"
    ]
    
    dev_requirements_file = Path("requirements-dev.txt")
    with open(dev_requirements_file, "w") as f:
        f.write("\n".join(dev_dependencies))
    
    if not run_command([str(pip_path), "install", "-r", str(dev_requirements_file)]):
        return False
    
    print("Dépendances installées avec succès")
    return True


def configure_pytest():
    """
    Configure pytest pour les tests unitaires.
    
    Returns:
        True si la configuration a réussi, False sinon
    """
    print_step("Configuration de pytest")
    
    pytest_config = """
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --verbose --cov=src --cov-report=term --cov-report=html
"""
    
    pytest_ini = Path("pytest.ini")
    with open(pytest_ini, "w") as f:
        f.write(pytest_config.strip())
    
    print(f"Configuration pytest créée dans {pytest_ini}")
    return True


def configure_flake8():
    """
    Configure flake8 pour l'analyse statique du code.
    
    Returns:
        True si la configuration a réussi, False sinon
    """
    print_step("Configuration de flake8")
    
    flake8_config = """
[flake8]
max-line-length = 100
exclude = .git,__pycache__,venv,build,dist
ignore = E203, W503
"""
    
    flake8_ini = Path(".flake8")
    with open(flake8_ini, "w") as f:
        f.write(flake8_config.strip())
    
    print(f"Configuration flake8 créée dans {flake8_ini}")
    return True


def configure_precommit():
    """
    Configure pre-commit pour exécuter des vérifications avant les commits.
    
    Returns:
        True si la configuration a réussi, False sinon
    """
    print_step("Configuration de pre-commit")
    
    precommit_config = """
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
    -   id: trailing-whitespace
    -   id: end-of-file-fixer
    -   id: check-yaml
    -   id: check-added-large-files

-   repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
    -   id: flake8

-   repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
    -   id: isort

-   repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
    -   id: black
"""
    
    precommit_yaml = Path(".pre-commit-config.yaml")
    with open(precommit_yaml, "w") as f:
        f.write(precommit_config.strip())
    
    print(f"Configuration pre-commit créée dans {precommit_yaml}")
    return True


def setup_environment():
    """
    Met en place l'environnement de développement complet.
    
    Returns:
        0 en cas de succès, 1 en cas d'échec
    """
    print_step("Configuration de l'environnement de développement")
    
    # Créer l'environnement virtuel
    venv_path = create_virtualenv()
    if venv_path is None:
        return 1
    
    # Installer les dépendances
    if not install_dependencies(venv_path):
        return 1
    
    # Configurer pytest
    if not configure_pytest():
        return 1
    
    # Configurer flake8
    if not configure_flake8():
        return 1
    
    # Configurer pre-commit
    if not configure_precommit():
        return 1
    
    # Afficher un message de succès
    print_step("Environnement de développement configuré avec succès")
    
    # Instructions d'activation
    if platform.system() == "Windows":
        activate_cmd = f"{venv_path}\\Scripts\\activate"
    else:
        activate_cmd = f"source {venv_path}/bin/activate"
    
    print(f"""
Pour activer l'environnement virtuel:
    {activate_cmd}

Pour exécuter les tests:
    pytest

Pour exécuter la vérification de style:
    flake8

Pour installer les hooks pre-commit:
    pre-commit install
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(setup_environment()) 