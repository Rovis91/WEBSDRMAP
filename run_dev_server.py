#!/usr/bin/env python3
"""
Script pour lancer le serveur de développement avec le mode debug activé.

Ce script lance l'application avec:
- Le mode debug activé
- Génération de données de test
- Rechargement automatique en cas de modification
"""

import asyncio
import sys
import os
import traceback

# Ajout du répertoire parent au path pour permettre l'import de src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import le point d'entrée de l'application
from src.main import main


if __name__ == "__main__":
    # Définir les arguments par défaut pour le mode développement
    sys.argv = [
        sys.argv[0],
        "--debug",
        "--host", "localhost",
        "--port", "5000",
        "--demo"  # Réactiver le mode démo pour contourner les problèmes de connexion
    ]
    
    # Lancer l'application avec gestion d'erreur
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print("\nERREUR FATALE:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print("\nTraceback:")
        traceback.print_exc()
        sys.exit(1) 