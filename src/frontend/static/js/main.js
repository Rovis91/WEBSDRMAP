/**
 * SDR Triangulation - Main JavaScript
 * This file handles the frontend functionality for the SDR triangulation web interface
 */

// Initialize global variables
let map = null;
let waterfallDisplay = null;
let audioController = null;
let frequencyFilter = null;
const annotationSystem = null;
const markers = {};
let circles = [];
let triangulationResult = null;
let demoMode = false; // Flag to indicate if the app is in demo mode (no receivers)

// DOM elements references
const statusValue = document.getElementById('status-value');
const receiversList = document.getElementById('receivers-list');
const signalsList = document.getElementById('signals-list');
const frequencyInput = document.getElementById('frequency');
const frequencyUnit = document.getElementById('frequency-unit');
const modeSelect = document.getElementById('mode');
const bandwidthInput = document.getElementById('bandwidth');
const startListeningBtn = document.getElementById('btn-start-listening');
const stopListeningBtn = document.getElementById('btn-stop-listening');
const connectionStatus = document.getElementById('connection-status');
const processingStatus = document.getElementById('processing-status');
const triangulationData = document.getElementById('triangulation-data');
const spectrogramCanvas = document.getElementById('spectrogram');
const addReceiverBtn = document.getElementById('btn-add-receiver');
const addReceiverModal = document.getElementById('modal-add-receiver');
const addReceiverForm = document.getElementById('add-receiver-form');
const modalClose = document.querySelector('.modal-close');
const modalCancel = document.querySelector('.modal-cancel');
const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');
const triangulateBtn = document.getElementById('btn-triangulate');
const exportButtons = document.querySelectorAll('.export-buttons button');

/**
 * Helpers for AJAX requests
 */
function fetchJSON(url, options = {}) {
    return fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    }).then(response => {
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return response.json();
    });
}

function getStatus() {
    return fetchJSON('/api/status')
        .then(data => {
            updateAppStatus(data);
            return data;
        })
        .catch(error => {
            console.error('Error fetching status:', error);
            updateConnectionStatus(false);
        });
}

function getReceivers() {
    return fetchJSON('/api/receivers')
        .then(receivers => {
            // Update each receiver
            receivers.forEach(receiver => {
                updateReceiver({
                    name: receiver.name,
                    status: receiver
                });
            });
            return receivers;
        })
        .catch(error => {
            console.error('Error fetching receivers:', error);
            // If we can't get receivers, enable demo mode
            enableDemoMode(true);
        });
}

function getTriangulation() {
    return fetchJSON('/api/triangulation')
        .then(data => {
            data.forEach(triangulation => {
                addTriangulation(triangulation);
            });
            return data;
        })
        .catch(error => {
            console.error('Error fetching triangulation:', error);
        });
}

/**
 * Initialize the application after DOM content is loaded
 */
function initialize() {
    // Initialize components
    initializeMap();
    initializeSpectrogram();
    initializeEventListeners();
    
    // Set default active tab
    switchTab('spectro');
    
    // Initial data load
    getStatus()
        .then(() => getReceivers())
        .then(() => getTriangulation())
        .catch(error => {
            console.error('Error during initialization:', error);
            // If we fail to load data, enable demo mode
            enableDemoMode(true);
        });
        
    // Set up periodic status refresh
    setInterval(getStatus, 5000);
}

/**
 * Initialize the Leaflet map
 */
function initializeMap() {
    // Create map centered on France
    map = L.map('map').setView([46.71109, 1.7191036], 6);
    
    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Add scale control
    L.control.scale().addTo(map);
    
    // Add custom controls
    addMapControls();
    
    // Register map event listeners
    map.on('click', handleMapClick);
}

/**
 * Add custom controls to the map
 */
function addMapControls() {
    // Add layer control for toggling receiver and signal layers
    const baseLayers = {
        "OpenStreetMap": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
    };
    
    const overlays = {
        "Récepteurs": L.layerGroup().addTo(map),
        "Signaux": L.layerGroup().addTo(map),
        "Triangulations": L.layerGroup().addTo(map)
    };
    
    L.control.layers(baseLayers, overlays, { position: 'topright', collapsed: false }).addTo(map);
    
    // Add measurement control
    L.control.measure({
        primaryLengthUnit: 'kilometers',
        secondaryLengthUnit: 'miles',
        primaryAreaUnit: 'sqkilometers',
        secondaryAreaUnit: 'sqmiles',
        position: 'bottomright'
    }).addTo(map);
}

/**
 * Handle map click event
 * @param {Object} e - Map click event
 */
function handleMapClick(e) {
    // Show coordinates in console for debugging
    console.log(`Map clicked at: ${e.latlng.lat}, ${e.latlng.lng}`);
    
    // Check if we're in location picking mode (for adding receivers)
    if (window.pickingLocation) {
        // Update the latitude and longitude fields in the add receiver form
        document.getElementById('receiver-lat').value = e.latlng.lat.toFixed(6);
        document.getElementById('receiver-lon').value = e.latlng.lng.toFixed(6);
        
        // Exit location picking mode
        window.pickingLocation = false;
        map.getContainer().style.cursor = '';
        
        // Show the modal again if it was hidden
        const modal = document.getElementById('modal-add-receiver');
        if (modal.style.display !== 'block') {
            modal.style.display = 'block';
        }
    } 
    // Check if we're in annotation location picking mode
    else if (window.pickingAnnotationLocation) {
        // Get the lat/lng
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        
        // Fill the form fields
        const latInput = document.getElementById('annotation-lat');
        const lngInput = document.getElementById('annotation-lng');
        
        if (latInput && lngInput) {
            latInput.value = lat.toFixed(6);
            lngInput.value = lng.toFixed(6);
        }
        
        // Reset the cursor
        map.getContainer().style.cursor = '';
        
        // Clear the flag
        window.pickingAnnotationLocation = false;
        
        // Show the annotation form again and switch to annotation tab
        const annotationForm = document.getElementById('annotation-form');
        if (annotationForm) {
            annotationForm.style.display = 'block';
        }
        
        // Switch back to the annotation tab
        switchTab('annotation');
    }
    // Regular map click - send to server
    else {
        if (socket) {
            socket.emit('map_click', {
                latitude: e.latlng.lat,
                longitude: e.latlng.lng,
                create_marker: window.creatingMarker || false
            }, (response) => {
                if (response && response.status === 'success') {
                    console.log('Map click registered');
                    
                    // If we created a marker, exit marker creation mode
                    if (window.creatingMarker) {
                        window.creatingMarker = false;
                        map.getContainer().style.cursor = '';
                    }
                }
            });
        }
    }
}

/**
 * Function to enable creating a marker at a map click location
 */
function enableMarkerCreation() {
    // Set the cursor to crosshair
    map.getContainer().style.cursor = 'crosshair';
    
    // Set a flag for the map click handler
    window.creatingMarker = true;
    
    // Show a helper message
    alert('Click on the map to create a marker');
}

/**
 * Handle signal selection in the UI
 * @param {string} signalId - ID of the signal
 * @param {boolean} selected - Whether the signal is selected
 */
function handleSignalSelection(signalId, selected) {
    if (!signalId) return;
    
    // Update the UI to show the signal as selected/deselected
    const signalElement = document.querySelector(`.signal-item[data-id="${signalId}"]`);
    if (signalElement) {
        if (selected) {
            signalElement.classList.add('selected');
        } else {
            signalElement.classList.remove('selected');
        }
    }
    
    // Notify the server about the selection
    if (socket) {
        socket.emit('signal_select', {
            signal_id: signalId,
            selected: selected
        });
    }
}

/**
 * Handle frequency selection from the waterfall display
 * @param {number} frequency - Selected frequency in Hz
 */
function handleFrequencySelection(frequency) {
    if (!frequency) return;
    
    // Update the frequency input
    updateFrequencyDisplay(frequency);
    
    // Notify the server about the selection
    if (socket) {
        socket.emit('frequency_select', { frequency: frequency });
    }
    
    // If we have selected receivers, change their frequency
    const selectedReceivers = getSelectedReceivers();
    if (selectedReceivers.length > 0) {
        if (socket) {
            socket.emit('set_frequency', {
                frequency: frequency,
                receivers: selectedReceivers
            });
        }
    }
}

/**
 * Update the frequency display in the UI
 * @param {number} frequency - Frequency in Hz
 */
function updateFrequencyDisplay(frequency) {
    const freqInput = document.getElementById('frequency');
    const freqUnitSelect = document.getElementById('frequency-unit');
    
    if (!freqInput || !freqUnitSelect) return;
    
    let displayValue, unit;
    
    if (frequency >= 1000000) {
        displayValue = (frequency / 1000000).toFixed(3);
        unit = '1000000'; // MHz
    } else if (frequency >= 1000) {
        displayValue = (frequency / 1000).toFixed(3);
        unit = '1000'; // kHz
    } else {
        displayValue = frequency;
        unit = '1'; // Hz
    }
    
    freqInput.value = displayValue;
    freqUnitSelect.value = unit;
}

/**
 * Handle receiver selection in the UI
 * @param {string} receiverName - Name of the receiver
 * @param {boolean} selected - Whether the receiver is selected
 */
function handleReceiverSelection(receiverName, selected) {
    if (!receiverName) return;
    
    // Update the UI to show the receiver as selected/deselected
    const receiverElement = document.querySelector(`.receiver-item[data-id="${receiverName}"]`);
    if (receiverElement) {
        const checkbox = receiverElement.querySelector('input[type="checkbox"]');
        if (checkbox) {
            checkbox.checked = selected;
        }
        
        if (selected) {
            receiverElement.classList.add('selected');
        } else {
            receiverElement.classList.remove('selected');
        }
    }
    
    // Notify the server about the selection
    if (socket) {
        socket.emit('receiver_select', {
            receiver: receiverName,
            selected: selected
        });
    }
}

/**
 * Initialize event listeners for UI elements
 */
function initializeEventListeners() {
    // Control panel events
    startListeningBtn.addEventListener('click', startListening);
    stopListeningBtn.addEventListener('click', stopListening);
    
    // Initialize the audio controller if available
    if (typeof AudioController !== 'undefined') {
        audioController = new AudioController({
            onError: (message) => {
                alert(message);
            }
        });
    }
    
    // Initialize the frequency filter if available
    if (typeof FrequencyFilter !== 'undefined') {
        frequencyFilter = new FrequencyFilter({
            onChange: (frequency) => {
                // Handle frequency change
                console.log(`Frequency changed to ${frequency}`);
            }
        });
    }
    
    // Receiver modal events
    addReceiverBtn.addEventListener('click', showAddReceiverModal);
    if (modalClose) modalClose.addEventListener('click', hideAddReceiverModal);
    if (modalCancel) modalCancel.addEventListener('click', hideAddReceiverModal);
    if (addReceiverForm) addReceiverForm.addEventListener('submit', handleAddReceiver);
    
    // Tab navigation
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            switchTab(button.id.replace('tab-', ''));
        });
    });
    
    // Map control buttons
    if (document.getElementById('btn-zoom-in')) {
        document.getElementById('btn-zoom-in').addEventListener('click', () => map.zoomIn());
    }
    if (document.getElementById('btn-zoom-out')) {
        document.getElementById('btn-zoom-out').addEventListener('click', () => map.zoomOut());
    }
    if (document.getElementById('btn-center-map')) {
        document.getElementById('btn-center-map').addEventListener('click', centerMap);
    }
    
    // Triangulation button
    if (triangulateBtn) {
        triangulateBtn.addEventListener('click', requestTriangulation);
    }
    
    // Export buttons
    if (document.getElementById('btn-export-json')) {
        document.getElementById('btn-export-json').addEventListener('click', () => exportData('json'));
    }
    if (document.getElementById('btn-export-csv')) {
        document.getElementById('btn-export-csv').addEventListener('click', () => exportData('csv'));
    }
    if (document.getElementById('btn-export-kml')) {
        document.getElementById('btn-export-kml').addEventListener('click', () => exportData('kml'));
    }
    
    // Pick location on map
    if (document.getElementById('btn-pick-location')) {
        document.getElementById('btn-pick-location').addEventListener('click', enableLocationPicker);
    }
}

/**
 * Initialize the spectrogram canvas
 */
function initializeSpectrogram() {
    if (!spectrogramCanvas) return;
    
    // Initialize the waterfall display
    waterfallDisplay = new WaterfallDisplay('spectrogram', {
        colorScheme: 'default',
        minLevel: -120,
        maxLevel: -30,
        historySize: 200,
        freqStart: 0,
        freqEnd: 12000,
        sampleRate: 12000,
        fftSize: 1024,
        labelInterval: 1000,
        onFrequencySelect: (freq) => {
            // Update the frequency input
            const freqInKHz = Math.round(freq / 1000 * 10) / 10;
            frequencyInput.value = freqInKHz;
            frequencyUnit.value = '1000'; // kHz
            
            console.log(`Selected frequency: ${freq} Hz`);
            
            // Update the UI to reflect the selected frequency
            const formattedFreq = freq >= 1000000 
                ? `${(freq / 1000000).toFixed(3)} MHz` 
                : freq >= 1000 
                    ? `${(freq / 1000).toFixed(2)} kHz` 
                    : `${freq.toFixed(0)} Hz`;
            
            // Optionally notify server about frequency selection
            // socket.emit('set_frequency', { frequency: freq });
            
            // Update frequency filter if available
            if (frequencyFilter) {
                frequencyFilter.selectFrequency(freq);
            }
        }
    });
    
    // Start the waterfall display
    waterfallDisplay.start();
    
    // Initialize frequency filter
    frequencyFilter = new FrequencyFilter({
        waterfallDisplay: waterfallDisplay,
        onFrequencySelect: (freq) => {
            // Emit the frequency change to the server
            socket.emit('set_frequency', {
                frequency: freq,
                receivers: getSelectedReceivers()
            });
        }
    });
    
    // Handle window resize events
    window.addEventListener('resize', () => {
        if (waterfallDisplay) {
            waterfallDisplay.handleResize();
        }
    });
}

/**
 * Get the currently selected receivers
 * @returns {Array} Array of selected receiver names
 */
function getSelectedReceivers() {
    // Get all checked receiver checkboxes
    const checkedReceivers = document.querySelectorAll('.receiver-checkbox:checked');
    
    // Extract the receiver names
    return Array.from(checkedReceivers).map(checkbox => checkbox.value);
}

/**
 * Resize the spectrogram canvas to match its container
 */
function resizeSpectrogram() {
    if (!spectrogramCanvas) return;
    
    const container = spectrogramCanvas.parentElement;
    spectrogramCanvas.width = container.clientWidth;
    spectrogramCanvas.height = container.clientHeight;
}

/**
 * Update the connection status indicator
 * @param {boolean} connected - Whether the client is connected to the server
 */
function updateConnectionStatus(connected) {
    if (connectionStatus) {
        connectionStatus.className = connected ? 
            'connection-status connected' : 
            'connection-status disconnected';
        connectionStatus.innerHTML = connected ? 
            '<i class="fas fa-wifi"></i> Connecté' : 
            '<i class="fas fa-wifi"></i> Déconnecté';
    }
    
    // Enable/disable buttons based on connection status
    startListeningBtn.disabled = !connected || Object.keys(markers).length === 0;
}

/**
 * Update the application status based on server data
 * @param {Object} data - Status data from the server
 */
function updateAppStatus(data) {
    // Update status indicator
    if (statusValue) {
        statusValue.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
        statusValue.className = 'status-value';
        
        if (data.status === 'active') {
            statusValue.classList.add('active');
        } else if (data.status === 'processing') {
            statusValue.classList.add('processing');
        }
    }
    
    // Update processing status
    if (processingStatus) {
        if (data.status === 'active' || data.status === 'processing') {
            processingStatus.className = 'processing-status active';
            processingStatus.innerHTML = '<i class="fas fa-cogs"></i> En cours';
        } else {
            processingStatus.className = 'processing-status';
            processingStatus.innerHTML = '<i class="fas fa-cogs"></i> Inactif';
        }
    }
    
    // Enable/disable buttons based on status
    startListeningBtn.disabled = data.status !== 'idle' || Object.keys(markers).length === 0;
    stopListeningBtn.disabled = data.status === 'idle';
    triangulateBtn.disabled = data.status !== 'active' || Object.keys(markers).length < 2;
}

/**
 * Update a receiver's status and map marker
 * @param {Object} data - Receiver data
 */
function updateReceiver(data) {
    const name = data.name;
    const status = data.status || {};
    
    // Check if we have a location
    if (!status.location || (!status.location.latitude && !status.location.longitude)) {
        console.warn(`Receiver ${name} has no location, cannot add to map`);
        return;
    }
    
    // Check if the receiver already exists on map
    if (markers[name]) {
        // Update existing marker
        updateReceiverMarker({
            name: name,
            location: status.location,
            status: status.state || 'unknown'
        });
    } else {
        // Create new marker
        const marker = L.marker([status.location.latitude, status.location.longitude], {
            title: name,
            alt: name,
            riseOnHover: true
        }).addTo(map);
        
        // Set popup
        const popupContent = createReceiverPopupContent(name, status);
        marker.bindPopup(popupContent);
        
        // Store marker reference
        markers[name] = marker;
        
        // Update marker icon based on status
        updateReceiverMarker({
            name: name,
            location: status.location,
            status: status.state || 'unknown'
        });
    }
    
    // Update receivers list
    updateReceiversList();
}

/**
 * Create HTML content for a receiver's popup
 * @param {string} name - Receiver name
 * @param {Object} status - Receiver status
 * @returns {string} HTML content
 */
function createReceiverPopupContent(name, status) {
    const statusText = status.is_connected ? 'Connecté' : 'Déconnecté';
    const statusClass = status.is_connected ? 'status-connected' : 'status-disconnected';
    
    const frequency = status.frequency ? 
        (status.frequency / 1000000).toFixed(3) + ' MHz' : 
        'N/A';
    
    return `
        <div class="receiver-popup">
            <h3>${name}</h3>
            <p class="${statusClass}">État: ${statusText}</p>
            <p>Fréquence: ${frequency}</p>
            <p>Mode: ${status.mode || 'N/A'}</p>
            <p>Location: ${status.location.latitude.toFixed(4)}, ${status.location.longitude.toFixed(4)}</p>
        </div>
    `;
}

/**
 * Update the receivers list in the sidebar
 */
function updateReceiversList() {
    if (!receiversList) return;
    
    receiversList.innerHTML = '';
    
    if (Object.keys(markers).length === 0) {
        receiversList.innerHTML = '<p class="empty-message">Aucun récepteur connecté</p>';
        return;
    }
    
    // Create receivers list
    Object.keys(markers).forEach(name => {
        const receiverDiv = document.createElement('div');
        receiverDiv.className = 'receiver-item';
        
        // Create checkbox for selection
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'receiver-checkbox';
        checkbox.value = name;
        checkbox.id = `receiver-check-${name.replace(/[^a-z0-9]/gi, '-')}`;
        checkbox.checked = true; // Default to checked
        
        checkbox.addEventListener('change', (e) => {
            handleReceiverSelection(name, e.target.checked);
        });
        
        // Create label
        const label = document.createElement('label');
        label.htmlFor = checkbox.id;
        label.textContent = name;
        
        // Append to div
        receiverDiv.appendChild(checkbox);
        receiverDiv.appendChild(label);
        
        // Add to list
        receiversList.appendChild(receiverDiv);
    });
    
    // Update buttons
    startListeningBtn.disabled = false;
}

/**
 * Update a receiver marker on the map based on status
 * @param {Object} data - Data containing name, location and status
 */
function updateReceiverMarker(data) {
    const marker = markers[data.name];
    if (!marker) return;
    
    // Create custom icon based on status
    const icon = L.divIcon({
        className: `receiver-marker receiver-status-${data.status || 'unknown'}`,
        html: `<div class="marker-icon"></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });
    
    // Update marker icon
    marker.setIcon(icon);
    
    // Update marker position if location changed
    if (data.location) {
        marker.setLatLng([data.location.latitude, data.location.longitude]);
    }
}

/**
 * Add a signal to the signals list
 * @param {Object} signal - Signal data from the server
 */
function addSignal(signal) {
    if (!signalsList) return;
    
    // Remove empty state if present
    const emptyState = signalsList.querySelector('.empty-state');
    if (emptyState) {
        signalsList.removeChild(emptyState);
    }
    
    // Create new signal element
    const signalElement = document.createElement('div');
    signalElement.className = 'signal-item';
    signalElement.innerHTML = `
        <div class="signal-freq">${(signal.frequency / 1000).toFixed(2)} kHz</div>
        <div class="signal-details">
            <span class="signal-strength">RSSI: ${signal.rssi.toFixed(1)} dB</span>
            <span class="signal-time">${new Date(signal.timestamp).toLocaleTimeString()}</span>
        </div>
    `;
    
    signalsList.appendChild(signalElement);
    
    // Limit list size
    while (signalsList.children.length > 20) {
        signalsList.removeChild(signalsList.firstChild);
    }
    
    // Scroll to bottom
    signalsList.scrollTop = signalsList.scrollHeight;
}

/**
 * Add a triangulation result to the map and update UI
 * @param {Object} triangulation - Triangulation data from the server
 */
function addTriangulation(triangulation) {
    // Store the latest triangulation result
    triangulationResult = triangulation;
    
    // Clear previous circles
    circles.forEach(circle => map.removeLayer(circle));
    circles = [];
    
    // Add triangulation circles to the map
    if (triangulation.position) {
        // Add estimated position marker
        const resultMarker = L.marker([
            triangulation.position.latitude, 
            triangulation.position.longitude
        ], {
            icon: L.divIcon({
                className: 'triangulation-marker',
                html: '<i class="fas fa-broadcast-tower"></i>',
                iconSize: [30, 30]
            })
        });
        
        resultMarker.bindPopup(`
            <div class="triangulation-popup">
                <h3>Émetteur estimé</h3>
                <p>Coordonnées: ${triangulation.position.latitude.toFixed(5)}, ${triangulation.position.longitude.toFixed(5)}</p>
                <p>Précision: ±${triangulation.accuracy.toFixed(1)} km</p>
                <p>Fréquence: ${(triangulation.frequency / 1000).toFixed(2)} kHz</p>
                <p>Confiance: ${(triangulation.confidence * 100).toFixed(0)}%</p>
            </div>
        `);
        
        resultMarker.addTo(map);
        circles.push(resultMarker);
        
        // Add accuracy circle
        const accuracyCircle = L.circle([
            triangulation.position.latitude, 
            triangulation.position.longitude
        ], {
            radius: triangulation.accuracy * 1000, // Convert km to meters
            color: '#ff6b35',
            fillColor: '#ff6b35',
            fillOpacity: 0.2,
            weight: 1
        });
        
        accuracyCircle.addTo(map);
        circles.push(accuracyCircle);
        
        // Center map on result
        map.setView([triangulation.position.latitude, triangulation.position.longitude]);
    }
    
    // Update triangulation data view
    updateTriangulationDataView(triangulation);
    
    // Enable export buttons
    exportButtons.forEach(button => button.disabled = false);
}

/**
 * Update the triangulation data view with results
 * @param {Object} triangulation - Triangulation data
 */
function updateTriangulationDataView(triangulation) {
    if (!triangulationData) return;
    
    if (!triangulation || !triangulation.position) {
        triangulationData.innerHTML = '<p class="empty-state">Aucune triangulation effectuée</p>';
        return;
    }
    
    triangulationData.innerHTML = `
        <div class="triangulation-result">
            <div class="result-item">
                <span class="result-label">Position estimée:</span>
                <span class="result-value">${triangulation.position.latitude.toFixed(5)}, ${triangulation.position.longitude.toFixed(5)}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Précision:</span>
                <span class="result-value">±${triangulation.accuracy.toFixed(1)} km</span>
            </div>
            <div class="result-item">
                <span class="result-label">Confiance:</span>
                <span class="result-value">${(triangulation.confidence * 100).toFixed(0)}%</span>
            </div>
            <div class="result-item">
                <span class="result-label">Fréquence:</span>
                <span class="result-value">${(triangulation.frequency / 1000).toFixed(2)} kHz</span>
            </div>
            <div class="result-item">
                <span class="result-label">Récepteurs utilisés:</span>
                <span class="result-value">${triangulation.receivers.join(', ')}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Horodatage:</span>
                <span class="result-value">${new Date(triangulation.timestamp).toLocaleString()}</span>
            </div>
        </div>
    `;
}

/**
 * Switch between tabs in the data view
 * @param {string} tabId - ID of the tab to switch to
 */
function switchTab(tabId) {
    // Update tab buttons
    tabButtons.forEach(button => {
        if (button.id === `tab-${tabId}`) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
    
    // Update tab panes
    tabPanes.forEach(pane => {
        if (pane.id === `${tabId}-view`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });
    
    // Additional actions when switching to spectro tab
    if (tabId === 'spectro') {
        resizeSpectrogram();
    }
}

/**
 * Show the add receiver modal
 */
function showAddReceiverModal() {
    if (addReceiverModal) {
        addReceiverModal.style.display = 'flex';
    }
}

/**
 * Hide the add receiver modal
 */
function hideAddReceiverModal() {
    if (addReceiverModal) {
        addReceiverModal.style.display = 'none';
    }
}

/**
 * Handle add receiver form submission
 */
function handleAddReceiver(event) {
    event.preventDefault();
    
    // Get form data
    const name = document.getElementById('receiver-name').value;
    const url = document.getElementById('receiver-url').value;
    const latitude = parseFloat(document.getElementById('receiver-lat').value);
    const longitude = parseFloat(document.getElementById('receiver-lon').value);
    
    // Validate form data
    if (!name || !url || isNaN(latitude) || isNaN(longitude)) {
        alert('Veuillez remplir tous les champs correctement.');
        return;
    }
    
    // Send data to server
    fetchJSON('/api/receivers', {
        method: 'POST',
        body: JSON.stringify({
            name: name,
            url: url,
            location: {
                latitude: latitude,
                longitude: longitude
            }
        })
    })
    .then(response => {
        if (response.success) {
            // Refresh receivers list
            getReceivers();
            
            // Hide modal
            hideAddReceiverModal();
        } else {
            alert(`Erreur: ${response.message || 'Impossible d\'ajouter le récepteur'}`);
        }
    })
    .catch(error => {
        console.error('Error adding receiver:', error);
        alert(`Erreur: ${error.message}`);
    });
}

/**
 * Start listening for signals
 */
function startListening() {
    // Get frequency
    const frequency = parseFloat(frequencyInput.value) * parseFloat(frequencyUnit.value);
    
    // Get mode
    const mode = modeSelect.value;
    
    // Get bandwidth
    const bandwidth = parseInt(bandwidthInput.value);
    
    // Send request to start listening
    fetchJSON('/api/listen/start', {
        method: 'POST',
        body: JSON.stringify({
            frequency: frequency,
            mode: mode,
            bandwidth: bandwidth
        })
    })
    .then(response => {
        if (response.success) {
            // Disable start button and enable stop button
            startListeningBtn.disabled = true;
            stopListeningBtn.disabled = false;
            
            // Update UI
            statusValue.textContent = "Écoute en cours";
            statusValue.classList.add('status-active');
            
            // If in demo mode, simulate waterfall data
            if (demoMode) {
                simulateDemoData();
            }
        } else {
            alert(`Erreur: ${response.message || 'Impossible de démarrer l\'écoute'}`);
        }
    })
    .catch(error => {
        console.error('Error starting listening:', error);
        alert(`Erreur: ${error.message}`);
    });
}

/**
 * Simulate data for demo mode
 */
function simulateDemoData() {
    if (!demoMode) return;
    
    // Create sample FFT data with peaks
    function generateFFTData() {
        const fftSize = 512;
        const data = new Array(fftSize);
        
        // Base noise between -100 and -85 dBm
        for (let i = 0; i < fftSize; i++) {
            data[i] = -100 + Math.random() * 15;
        }
        
        // Add 2-3 peaks representing signals
        const numPeaks = 2 + Math.floor(Math.random() * 2);
        for (let i = 0; i < numPeaks; i++) {
            const pos = Math.floor(Math.random() * fftSize);
            const width = 5 + Math.floor(Math.random() * 10);
            const strength = -60 + Math.random() * 30;
            
            for (let j = Math.max(0, pos - width); j < Math.min(fftSize, pos + width); j++) {
                const distance = Math.abs(j - pos);
                const falloff = Math.exp(-(distance ** 2) / (2 * (width / 3) ** 2));
                data[j] = strength * falloff + data[j] * (1 - falloff);
            }
        }
        
        return data;
    }
    
    // Update waterfall display with new data every 100ms
    const interval = setInterval(() => {
        if (!demoMode || statusValue.textContent !== "Écoute en cours") {
            clearInterval(interval);
            return;
        }
        
        if (waterfallDisplay) {
            waterfallDisplay.addData(generateFFTData());
        }
    }, 100);
}

/**
 * Stop listening
 */
function stopListening() {
    console.log('Stopping listening');
    
    // Send request to server
    fetchJSON('/api/listen/stop', {
        method: 'POST'
    })
    .then(response => {
        // Update UI
        startListeningBtn.disabled = false;
        stopListeningBtn.disabled = true;
        
        statusValue.textContent = "Inactif";
        statusValue.classList.remove('status-active');
    })
    .catch(error => {
        console.error('Error stopping listening:', error);
        alert(`Erreur: ${error.message}`);
    });
}

/**
 * Center the map on active receivers or default location
 */
function centerMap() {
    if (Object.keys(markers).length > 0) {
        // Create a bounds object from all markers
        const bounds = L.latLngBounds(Object.values(markers).map(m => m.getLatLng()));
        map.fitBounds(bounds, { padding: [30, 30] });
    } else {
        // Default to center on France
        map.setView([46.71109, 1.7191036], 6);
    }
}

/**
 * Enable the location picker for adding receivers
 */
function enableLocationPicker() {
    // Display a message to the user
    alert('Cliquez sur la carte pour sélectionner la position du récepteur');
    
    // Set up one-time click event on the map
    const onMapClick = (e) => {
        document.getElementById('receiver-lat').value = e.latlng.lat.toFixed(6);
        document.getElementById('receiver-lon').value = e.latlng.lng.toFixed(6);
        
        // Remove the click event listener
        map.off('click', onMapClick);
    };
    
    map.on('click', onMapClick);
}

/**
 * Request triangulation from the server
 */
function requestTriangulation() {
    console.log('Requesting triangulation');
    
    // In a real implementation, this would send a request to the server
    // For demonstration, we'll simulate a response
    setTimeout(() => {
        const simulatedData = {
            position: {
                latitude: 48.8566,
                longitude: 2.3522
            },
            accuracy: 15.5,
            confidence: 0.75,
            frequency: parseInt(frequencyInput.value) * parseInt(frequencyUnit.value),
            receivers: Object.keys(markers),
            timestamp: Date.now()
        };
        
        addTriangulation(simulatedData);
    }, 1000);
    
    // Update UI
    triangulateBtn.disabled = true;
    triangulateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Calcul en cours...';
    
    // Re-enable after delay
    setTimeout(() => {
        triangulateBtn.disabled = false;
        triangulateBtn.innerHTML = '<i class="fas fa-map-marker-alt"></i> Trianguler';
    }, 2000);
}

/**
 * Export triangulation data
 * @param {string} format - Export format (json, csv, kml)
 */
function exportData(format) {
    if (!triangulationResult) return;
    
    let content = '';
    let filename = `triangulation-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}`;
    let mimeType = '';
    
    switch (format) {
        case 'json':
            content = JSON.stringify(triangulationResult, null, 2);
            filename += '.json';
            mimeType = 'application/json';
            break;
            
        case 'csv':
            content = 'latitude,longitude,accuracy,confidence,frequency,timestamp\n';
            content += `${triangulationResult.position.latitude},`;
            content += `${triangulationResult.position.longitude},`;
            content += `${triangulationResult.accuracy},`;
            content += `${triangulationResult.confidence},`;
            content += `${triangulationResult.frequency},`;
            content += `${triangulationResult.timestamp}`;
            filename += '.csv';
            mimeType = 'text/csv';
            break;
            
        case 'kml':
            content = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>SDR Triangulation</name>
    <Placemark>
      <name>Émetteur estimé</name>
      <description>
        <![CDATA[
          <p>Fréquence: ${(triangulationResult.frequency / 1000).toFixed(2)} kHz</p>
          <p>Précision: ${triangulationResult.accuracy.toFixed(1)} km</p>
          <p>Confiance: ${(triangulationResult.confidence * 100).toFixed(0)}%</p>
          <p>Horodatage: ${new Date(triangulationResult.timestamp).toLocaleString()}</p>
        ]]>
      </description>
      <Point>
        <coordinates>${triangulationResult.position.longitude},${triangulationResult.position.latitude},0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>`;
            filename += '.kml';
            mimeType = 'application/vnd.google-earth.kml+xml';
            break;
    }
    
    // Create download link
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 0);
}

/**
 * Handle socket.io message for audio stream URL
 * @param {Object} data - Audio stream data with URL
 */
function handleAudioStream(data) {
    const { url, receiverName } = data;
    
    if (audioController) {
        audioController.setAudioSource(url, receiverName);
        
        // Automatically start playing
        audioController.play();
    }
}

// Add socket.io handler for audio stream
socket.on('audio_stream', (data) => {
    handleAudioStream(data);
});

/**
 * Enable tab navigation regardless of connection status
 */
function enableTabNavigation() {
    if (tabButtons && tabButtons.length > 0) {
        tabButtons.forEach(tab => {
            tab.classList.remove('disabled');
        });
    }
}

/**
 * Enable demo mode when no receivers are connected
 */
function enableDemoMode(immediate = false) {
    // Function to set up demo mode
    const setupDemoMode = () => {
        if (Object.keys(markers).length === 0) {
            console.log("No receivers connected. Enabling demo mode...");
            demoMode = true;
            
            // Enable navigation and UI
            startListeningBtn.disabled = false;
            triangulateBtn.disabled = false;
            
            // Enable all tab buttons
            enableTabNavigation();
            
            // Update status to indicate demo mode
            if (statusValue) {
                statusValue.textContent = "Mode Démo";
                statusValue.classList.add('status-demo');
            }
            
            // Add a dummy receiver for demonstration
            const dummyReceiver = {
                name: "Démo Récepteur",
                status: {
                    connected: true,
                    location: { latitude: 48.8566, longitude: 2.3522 },
                    frequency: 7100000,
                    mode: 'AM',
                    status: 'online'
                }
            };
            
            updateReceiver(dummyReceiver);
        }
    };
    
    // Check if we should enable immediately or after a delay
    if (immediate) {
        setupDemoMode();
    } else {
        // Check after 2 seconds for normal initialization
        setTimeout(setupDemoMode, 2000);
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', initialize); 