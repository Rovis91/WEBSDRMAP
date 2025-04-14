#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SDR Web Viewer - Script de démarrage
Ce script démarre l'application SDR Web Viewer en mode production.
"""

import os
import sys
import subprocess
import webbrowser
import time

def main():
    print("Démarrage de SDR Web Viewer...")
    
    # Kill any existing process on port 8000
    try:
        if sys.platform == 'win32':
            os.system('netstat -ano | findstr :8000 | findstr LISTENING > nul && FOR /F "tokens=5" %a in (\'netstat -ano ^| findstr :8000 ^| findstr LISTENING\') do taskkill /F /PID %a')
        else:
            os.system('kill $(lsof -t -i:8000) 2>/dev/null || true')
    except:
        pass
    
    # Start the application in a separate process
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, 'basic_app.py')
    
    print("Démarrage du serveur SDR Web...")
    
    # Run the server
    proc = subprocess.Popen([sys.executable, app_path], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           universal_newlines=True)
    
    # Wait for the server to start
    print("En attente du démarrage du serveur...")
    time.sleep(3)
    
    # Open browser
    try:
        print("Ouverture du navigateur...")
        webbrowser.open('http://127.0.0.1:8000')
        
        print("\nL'application SDR Web Viewer est en cours d'exécution.")
        print("Accédez à http://127.0.0.1:8000 dans votre navigateur.")
        print("Appuyez sur Ctrl+C pour arrêter le serveur.")
        
        # Keep the script running to keep the subprocess alive
        while proc.poll() is None:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print("\nArrêt du serveur...")
                proc.terminate()
                break
    
    except Exception as e:
        print(f"Erreur: {str(e)}")
    finally:
        # Ensure subprocess is terminated
        if proc.poll() is None:
            proc.terminate()
            
    return 0

if __name__ == '__main__':
    sys.exit(main()) 