// Application principale du SDR Viewer Simplifié

// Variables globales
let map;
let markers = [];
let receivers = [];
let activeReceiver = null;
let socket;
let waterfallCanvas;
let waterfallCtx;
let audioContext;
let audioBuffer = [];
let audioBufferSize = 4096;  // Taille réduite pour moins de latence
let audioNode;
let audioPlaying = false;
let volume = 0.5;
let socketConnected = false;
let reconnectAttempts = 0;
let maxReconnectAttempts = 5;

// Variables pour limiter les mises à jour
let lastWaterfallUpdateTime = 0;
let waterfallUpdateInterval = 100;  // ms
let pendingWaterfallData = null;

// Initialisation de l'application
document.addEventListener('DOMContentLoaded', function() {
    // Initialisation de la carte
    initMap();
    
    // Initialisation du waterfall
    initWaterfall();
    
    // Initialisation de l'audio
    initAudio();
    
    // Chargement des récepteurs depuis l'API
    loadReceivers();
    
    // Initialisation des WebSockets
    initSocket();
    
    // Connexion des événements UI
    connectUIEvents();
    
    // Afficher le statut initial
    updateStatus('Prêt. Sélectionnez un récepteur sur la carte.', 'info');
});

// Initialisation de la carte Leaflet
function initMap() {
    try {
        // Désactiver les animations pour économiser des ressources
        L.Icon.Default.imagePath = 'https://unpkg.com/leaflet@1.9.3/dist/images/';
        
        // Créer la carte avec un niveau de zoom plus bas pour économiser des ressources
        map = L.map('map', {
            zoomControl: true,
            attributionControl: true,
            zoomAnimation: false,  // Désactiver les animations
            fadeAnimation: false   // Désactiver les animations
        }).setView([48.8566, 2.3522], 3);
        
        // Utiliser une carte moins détaillée pour moins de données
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 12  // Limiter le zoom maximal
        }).addTo(map);
    } catch (e) {
        console.error('Erreur lors de l\'initialisation de la carte:', e);
        updateStatus('Erreur lors de l\'initialisation de la carte', 'danger');
    }
}

// Initialisation du canvas pour le waterfall
function initWaterfall() {
    try {
        waterfallCanvas = document.getElementById('waterfall');
        waterfallCtx = waterfallCanvas.getContext('2d', { alpha: false });  // Désactiver l'alpha pour de meilleures performances
        
        // Ajuster la taille du canvas pour qu'il corresponde à la taille d'affichage
        resizeWaterfall();
        
        // Utiliser un gestionnaire d'événements throttlé pour le redimensionnement
        let resizeTimeout;
        window.addEventListener('resize', function() {
            if (resizeTimeout) clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(resizeWaterfall, 200);
        });
    } catch (e) {
        console.error('Erreur lors de l\'initialisation du waterfall:', e);
    }
}

// Redimensionnement du canvas waterfall
function resizeWaterfall() {
    try {
        const container = waterfallCanvas.parentElement;
        
        // Ajuster la taille du canvas en fonction de la taille du conteneur
        const scale = window.devicePixelRatio || 1;
        waterfallCanvas.width = container.clientWidth;
        waterfallCanvas.height = 400;
        
        // Effacer le canvas avec un fond noir
        waterfallCtx.fillStyle = 'black';
        waterfallCtx.fillRect(0, 0, waterfallCanvas.width, waterfallCanvas.height);
    } catch (e) {
        console.error('Erreur lors du redimensionnement du waterfall:', e);
    }
}

// Initialisation de l'audio
function initAudio() {
    try {
        // Création du contexte audio
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        
        // Attendre que l'utilisateur interagisse avec la page avant de créer le contexte audio
        // Cela évite les problèmes de lecture automatique bloquée par les navigateurs
        document.addEventListener('click', initAudioContext, { once: true });
        
        // Configuration du volume
        const volumeControl = document.getElementById('volume');
        volumeControl.addEventListener('input', function() {
            volume = parseFloat(this.value);
            updateAudioVolume();
        });
        
        // Récupérer la valeur initiale
        volume = parseFloat(volumeControl.value);
    } catch (e) {
        console.error('Erreur lors de l\'initialisation de l\'audio:', e);
        document.getElementById('audio-status').textContent = 'Erreur: Audio non supporté par votre navigateur';
    }
}

// Initialisation du contexte audio après l'interaction utilisateur
function initAudioContext() {
    if (!audioContext) {
        try {
            audioContext = new AudioContext();
            updateStatus('Audio activé', 'success');
        } catch (e) {
            console.error('Erreur lors de l\'activation de l\'audio:', e);
        }
    }
}

// Mise à jour du volume audio
function updateAudioVolume() {
    if (audioNode) {
        audioNode.gain.value = volume;
    }
}

// Affichage d'un message de statut
function updateStatus(message, type = 'info') {
    const container = document.getElementById('status-container');
    if (container) {
        container.textContent = message;
        container.className = `alert alert-${type}`;
    }
}

// Chargement des récepteurs depuis l'API
function loadReceivers() {
    updateStatus('Chargement des récepteurs...', 'warning');
    
    fetch('/api/receivers')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            receivers = data;
            addReceiversToMap(receivers);
            updateStatus('Récepteurs chargés. Cliquez sur un marqueur pour vous connecter.', 'success');
        })
        .catch(error => {
            console.error('Erreur lors du chargement des récepteurs:', error);
            updateStatus('Erreur de chargement des récepteurs. Rafraîchissez la page.', 'danger');
        });
}

// Ajout des récepteurs sur la carte
function addReceiversToMap(receivers) {
    try {
        // Supprimer les marqueurs existants
        if (markers && markers.length) {
            markers.forEach(marker => {
                if (map && marker) map.removeLayer(marker);
            });
        }
        markers = [];
        
        if (!receivers || receivers.length === 0) {
            updateStatus('Aucun récepteur disponible', 'warning');
            return;
        }
        
        // Ajouter les nouveaux marqueurs
        receivers.forEach((receiver, index) => {
            if (!receiver.location || typeof receiver.location.latitude !== 'number' || typeof receiver.location.longitude !== 'number') {
                console.error('Localisation invalide pour le récepteur:', receiver);
                return;
            }
            
            const marker = L.marker([receiver.location.latitude, receiver.location.longitude])
                .addTo(map)
                .bindPopup(createPopupContent(receiver, index));
            
            markers.push(marker);
        });
        
        // Ajuster la vue pour voir tous les marqueurs
        if (markers.length > 0) {
            const group = new L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.2));
        }
    } catch (e) {
        console.error('Erreur lors de l\'ajout des récepteurs sur la carte:', e);
    }
}

// Création du contenu d'une popup pour un récepteur
function createPopupContent(receiver, index) {
    const div = document.createElement('div');
    div.className = 'marker-popup';
    
    const title = document.createElement('h5');
    title.textContent = receiver.name;
    div.appendChild(title);
    
    const button = document.createElement('button');
    button.className = 'btn btn-primary';
    button.textContent = 'Connecter';
    button.onclick = function() {
        connectToReceiver(index);
        return false;  // Éviter de fermer la popup automatiquement
    };
    div.appendChild(button);
    
    return div;
}

// Connexion à un récepteur spécifique
function connectToReceiver(index) {
    updateStatus('Connexion en cours...', 'warning');
    
    fetch(`/api/receiver/${index}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ action: 'connect' })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            activeReceiver = index;
            updateStatus(`Connecté à ${receivers[index].name}`, 'success');
            
            // Vider le buffer audio pour éviter des sons parasites
            audioBuffer = [];
            audioPlaying = false;
            
            // Vider le canvas waterfall
            if (waterfallCtx) {
                waterfallCtx.fillStyle = 'black';
                waterfallCtx.fillRect(0, 0, waterfallCanvas.width, waterfallCanvas.height);
            }
            
            // Mise à jour du statut des marqueurs
            updateMarkerStatus();
            
            // Initialiser le contexte audio si nécessaire
            initAudioContext();
            
            // Vérifier la connexion WebSocket
            checkSocketConnection();
        } else {
            updateStatus(`Erreur: ${data.message || 'Connexion échouée'}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Erreur lors de la connexion au récepteur:', error);
        updateStatus('Erreur de connexion. Réessayez plus tard.', 'danger');
    });
}

// Vérification de la connexion WebSocket
function checkSocketConnection() {
    if (!socketConnected && socket) {
        updateStatus('Reconnexion au serveur WebSocket...', 'warning');
        try {
            socket.connect();
        } catch (e) {
            console.error('Erreur lors de la reconnexion au WebSocket:', e);
        }
    }
}

// Mise à jour du statut visuel des marqueurs
function updateMarkerStatus() {
    try {
        markers.forEach((marker, index) => {
            if (index === activeReceiver) {
                marker.openPopup();
            } else {
                marker.closePopup();
            }
        });
    } catch (e) {
        console.error('Erreur lors de la mise à jour des marqueurs:', e);
    }
}

// Initialisation de la connexion WebSocket
function initSocket() {
    try {
        // Options pour réduire la consommation de ressources
        const socketOptions = {
            reconnectionAttempts: maxReconnectAttempts,
            reconnectionDelay: 1000,
            timeout: 10000,
            forceNew: false,
            autoConnect: true
        };
        
        socket = io(socketOptions);
        
        socket.on('connect', () => {
            console.log('Connecté au serveur WebSocket');
            socketConnected = true;
            reconnectAttempts = 0;
            updateStatus('Connexion WebSocket établie', 'success');
        });
        
        socket.on('disconnect', () => {
            console.log('Déconnecté du serveur WebSocket');
            socketConnected = false;
            document.getElementById('audio-status').textContent = 'Connexion perdue';
            updateStatus('Connexion WebSocket perdue. Tentative de reconnexion...', 'warning');
        });
        
        socket.on('connect_error', (error) => {
            console.error('Erreur de connexion WebSocket:', error);
            socketConnected = false;
            reconnectAttempts++;
            if (reconnectAttempts >= maxReconnectAttempts) {
                updateStatus('Impossible de se connecter au serveur. Rafraîchissez la page.', 'danger');
            } else {
                updateStatus(`Erreur de connexion. Tentative ${reconnectAttempts}/${maxReconnectAttempts}...`, 'warning');
            }
        });
        
        // Gestion des données waterfall avec throttling
        socket.on('waterfall_data', (data) => {
            pendingWaterfallData = data;
            requestAnimationFrame(processPendingWaterfallData);
        });
        
        // Gestion des données audio
        socket.on('audio_data', (data) => {
            processAudioData(data);
        });
    } catch (e) {
        console.error('Erreur lors de l\'initialisation du WebSocket:', e);
        updateStatus('Erreur de connexion au serveur. Rafraîchissez la page.', 'danger');
    }
}

// Traitement des données waterfall en attente
function processPendingWaterfallData() {
    if (!pendingWaterfallData) return;
    
    const now = Date.now();
    if (now - lastWaterfallUpdateTime >= waterfallUpdateInterval) {
        processWaterfallData(pendingWaterfallData);
        pendingWaterfallData = null;
        lastWaterfallUpdateTime = now;
    } else {
        requestAnimationFrame(processPendingWaterfallData);
    }
}

// Traitement des données waterfall reçues
function processWaterfallData(data) {
    if (!data || !data.data) return;
    
    try {
        // Conversion des données hexadécimales en tableau d'octets
        const bytes = new Uint8Array(data.data.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
        
        // Dessiner les données sur le waterfall
        drawWaterfall(bytes);
    } catch (e) {
        console.error('Erreur de traitement des données waterfall:', e);
    }
}

// Dessiner les données sur le waterfall
function drawWaterfall(data) {
    // Si le canvas n'est pas initialisé, ne rien faire
    if (!waterfallCtx) return;
    
    try {
        // Décaler l'image existante vers le bas
        waterfallCtx.drawImage(
            waterfallCanvas,
            0, 0, waterfallCanvas.width, waterfallCanvas.height - 1,
            0, 1, waterfallCanvas.width, waterfallCanvas.height - 1
        );
        
        // Dessiner la nouvelle ligne en haut
        const imgData = waterfallCtx.createImageData(waterfallCanvas.width, 1);
        
        // Convertir les données en couleurs pour le spectrogramme
        // Version optimisée pour de meilleures performances
        const dataLength = Math.min(data.length, waterfallCanvas.width);
        for (let i = 0; i < dataLength; i++) {
            const value = data[i];
            
            // Palette de couleurs simplifiée pour de meilleures performances
            // Bleu (froid) -> vert -> rouge (chaud)
            const r = Math.max(0, Math.min(255, (value - 128) * 4));
            const g = Math.max(0, Math.min(255, value * 1.5));
            const b = Math.max(0, Math.min(255, (255 - value) * 1.5));
            
            const pixelIndex = i * 4;
            imgData.data[pixelIndex] = r;
            imgData.data[pixelIndex + 1] = g;
            imgData.data[pixelIndex + 2] = b;
            imgData.data[pixelIndex + 3] = 255;  // Alpha
        }
        
        // Dessiner la ligne
        waterfallCtx.putImageData(imgData, 0, 0);
    } catch (e) {
        console.error('Erreur lors du dessin du waterfall:', e);
    }
}

// Traitement des données audio reçues
function processAudioData(data) {
    if (!data || !data.data || !audioContext) return;
    
    try {
        // Conversion des données hexadécimales en tableau d'octets
        const bytes = new Uint8Array(data.data.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
        
        // Ajouter les données au buffer avec une limite pour éviter une consommation excessive de mémoire
        const maxBufferLength = audioBufferSize * 5;
        if (audioBuffer.length + bytes.length > maxBufferLength) {
            // Si le buffer devient trop grand, supprimer des données du début
            audioBuffer = audioBuffer.slice(bytes.length);
        }
        
        // Ajouter les nouvelles données
        audioBuffer.push(...bytes);
        
        // Si nous avons assez de données, jouer l'audio
        if (audioBuffer.length >= audioBufferSize && !audioPlaying) {
            playAudioBuffer();
        }
        
        // Mettre à jour le statut audio
        const audioStatus = document.getElementById('audio-status');
        if (audioStatus) {
            audioStatus.textContent = 'Réception audio en cours';
        }
    } catch (e) {
        console.error('Erreur de traitement des données audio:', e);
    }
}

// Jouer le buffer audio
function playAudioBuffer() {
    if (!audioContext || audioBuffer.length < audioBufferSize) return;
    
    try {
        // Prendre uniquement la quantité nécessaire de données
        const dataToPlay = audioBuffer.splice(0, audioBufferSize);
        
        // Convertir en Float32Array pour l'API Web Audio
        const audioData = new Float32Array(audioBufferSize);
        for (let i = 0; i < audioBufferSize; i++) {
            // Convertir les valeurs 0-255 en -1.0 à 1.0
            audioData[i] = (dataToPlay[i] - 128) / 128.0;
        }
        
        // Créer le buffer audio
        const buffer = audioContext.createBuffer(1, audioBufferSize, 44100);
        buffer.getChannelData(0).set(audioData);
        
        // Créer la source audio
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        
        // Créer le nœud de gain pour le volume
        audioNode = audioContext.createGain();
        audioNode.gain.value = volume;
        
        // Connecter les nœuds
        source.connect(audioNode);
        audioNode.connect(audioContext.destination);
        
        // Démarrer la lecture
        source.start();
        audioPlaying = true;
        
        // Lorsque la lecture est terminée
        source.onended = function() {
            audioPlaying = false;
            // Jouer le prochain buffer si disponible
            if (audioBuffer.length >= audioBufferSize) {
                playAudioBuffer();
            }
        };
    } catch (e) {
        console.error('Erreur lors de la lecture audio:', e);
        audioPlaying = false;
    }
}

// Connexion des événements UI
function connectUIEvents() {
    try {
        // Événement de changement de fréquence avec debounce
        const freqButton = document.getElementById('set-frequency');
        if (freqButton) {
            freqButton.addEventListener('click', debounce(function() {
                const frequencyInput = document.getElementById('frequency');
                if (!frequencyInput) return;
                
                const frequency = parseFloat(frequencyInput.value);
                
                if (isNaN(frequency) || frequency <= 0) {
                    alert('Veuillez entrer une fréquence valide');
                    return;
                }
                
                setFrequency(frequency);
            }, 300));
        }
        
        // Événements de changement de mode
        const modeRadios = document.querySelectorAll('input[name="mode"]');
        if (modeRadios && modeRadios.length) {
            modeRadios.forEach(function(radio) {
                radio.addEventListener('change', debounce(function() {
                    setMode(this.value);
                }, 300));
            });
        }
    } catch (e) {
        console.error('Erreur lors de la connexion des événements UI:', e);
    }
}

// Fonction debounce pour limiter les appels rapides aux fonctions
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// Définition de la fréquence
function setFrequency(frequency) {
    if (activeReceiver === null) {
        alert('Veuillez d\'abord vous connecter à un récepteur');
        return;
    }
    
    updateStatus(`Changement de fréquence à ${frequency} kHz...`, 'info');
    
    fetch(`/api/receiver/${activeReceiver}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ frequency: frequency })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            updateStatus(`Fréquence définie à ${frequency} kHz`, 'success');
        } else {
            updateStatus(`Erreur: ${data.error || 'Changement de fréquence échoué'}`, 'danger');
            console.error('Erreur lors du changement de fréquence:', data.error);
        }
    })
    .catch(error => {
        updateStatus('Erreur de communication', 'danger');
        console.error('Erreur lors du changement de fréquence:', error);
    });
}

// Définition du mode
function setMode(mode) {
    if (activeReceiver === null) {
        alert('Veuillez d\'abord vous connecter à un récepteur');
        return;
    }
    
    updateStatus(`Changement de mode vers ${mode.toUpperCase()}...`, 'info');
    
    fetch(`/api/receiver/${activeReceiver}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ mode: mode })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            updateStatus(`Mode défini à ${mode.toUpperCase()}`, 'success');
        } else {
            updateStatus(`Erreur: ${data.error || 'Changement de mode échoué'}`, 'danger');
            console.error('Erreur lors du changement de mode:', data.error);
        }
    })
    .catch(error => {
        updateStatus('Erreur de communication', 'danger');
        console.error('Erreur lors du changement de mode:', error);
    });
} 