/**
 * SDR Triangulation - Annotation System
 * 
 * This module provides annotation and marking functionality for the SDR triangulation tool.
 * It handles:
 * - Signal annotation and tagging
 * - Geolocation markers
 * - Note-taking functionality
 * - Export of annotations
 */

class AnnotationSystem {
    /**
     * Create a new annotation system
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        // Configuration options
        this.options = {
            annotationsListId: options.annotationsListId || 'annotations-list',
            annotationFormId: options.annotationFormId || 'annotation-form',
            addAnnotationBtnId: options.addAnnotationBtnId || 'btn-add-annotation',
            exportAnnotationsBtnId: options.exportAnnotationsBtnId || 'btn-export-annotations',
            waterfallDisplay: options.waterfallDisplay || null,
            mapInstance: options.mapInstance || null,
            onAnnotationSelect: options.onAnnotationSelect || null
        };
        
        // DOM elements
        this.annotationsList = document.getElementById(this.options.annotationsListId);
        this.annotationForm = document.getElementById(this.options.annotationFormId);
        this.addAnnotationBtn = document.getElementById(this.options.addAnnotationBtnId);
        this.exportAnnotationsBtn = document.getElementById(this.options.exportAnnotationsBtnId);
        
        // State
        this.annotations = [];
        this.waterfallDisplay = this.options.waterfallDisplay;
        this.mapInstance = this.options.mapInstance;
        this.markers = {};
        
        // Unique ID counter
        this.nextId = 1;
        
        // Initialize
        this.initialize();
    }
    
    /**
     * Initialize the annotation system
     */
    initialize() {
        // Create annotations array if not exists
        this.annotations = [];
        this.selectedAnnotationId = null;
        this.mapMarkers = {};
        
        // Set up socket event listeners for real-time updates
        if (socket) {
            // Listen for updated annotations from server
            socket.on('annotation_updated', (annotation) => {
                this.handleAnnotationUpdate(annotation);
            });
            
            // Listen for annotation deletions
            socket.on('annotation_deleted', (data) => {
                this.handleAnnotationDeleted(data.id);
            });
            
            // Get existing annotations from server
            this.loadAnnotationsFromServer();
        } else {
            console.warn('Socket not available, using local storage only for annotations');
            // Fall back to local storage
            this.loadAnnotations();
        }
        
        // Initialize the UI
        this.setupEventListeners();
        this.renderAnnotationsList();
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Add annotation button
        if (this.addAnnotationBtn) {
            this.addAnnotationBtn.addEventListener('click', () => {
                this.showAnnotationForm();
            });
        }
        
        // Export annotations button
        if (this.exportAnnotationsBtn) {
            this.exportAnnotationsBtn.addEventListener('click', () => {
                this.exportAnnotations();
            });
        }
        
        // Annotation form
        if (this.annotationForm) {
            this.annotationForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleAnnotationFormSubmit();
            });
        }
    }
    
    /**
     * Load annotations from the server
     */
    loadAnnotationsFromServer() {
        if (!socket) return;
        
        socket.emit('get_annotations', {}, (response) => {
            if (response && response.status === 'success') {
                this.annotations = response.annotations || [];
                console.log(`Loaded ${this.annotations.length} annotations from server`);
                
                // Update UI
                this.renderAnnotationsList();
                this.updateMapMarkers();
            } else {
                console.error('Failed to load annotations from server', response);
                // Fall back to local storage
                this.loadAnnotations();
            }
        });
    }
    
    /**
     * Load annotations from local storage
     */
    loadAnnotations() {
        try {
            const savedAnnotations = localStorage.getItem('sdr_annotations');
            if (savedAnnotations) {
                this.annotations = JSON.parse(savedAnnotations);
                console.log(`Loaded ${this.annotations.length} annotations from local storage`);
            }
        } catch (error) {
            console.error('Error loading annotations from local storage:', error);
            this.annotations = [];
        }
    }
    
    /**
     * Save annotations to local storage as backup
     */
    saveAnnotations() {
        try {
            localStorage.setItem('sdr_annotations', JSON.stringify(this.annotations));
        } catch (error) {
            console.error('Error saving annotations to local storage:', error);
        }
    }
    
    /**
     * Render annotations in the list element
     */
    renderAnnotationsList() {
        if (!this.annotationsList) return;
        
        // Clear the list
        this.annotationsList.innerHTML = '';
        
        if (this.annotations.length === 0) {
            // Show empty state
            const emptyState = document.createElement('p');
            emptyState.className = 'empty-state';
            emptyState.textContent = 'Aucune annotation';
            this.annotationsList.appendChild(emptyState);
            return;
        }
        
        // Create list
        const list = document.createElement('ul');
        list.className = 'annotations-list';
        
        // Add each annotation
        this.annotations.forEach(annotation => {
            const item = document.createElement('li');
            item.className = 'annotation-item';
            item.dataset.id = annotation.id;
            
            // Format date
            const date = new Date(annotation.timestamp);
            const dateFormatted = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
            
            // Format frequency
            const freqFormatted = this.formatFrequency(annotation.frequency);
            
            // Create annotation element
            item.innerHTML = `
                <div class="annotation-header">
                    <span class="annotation-title">${annotation.title}</span>
                    <span class="annotation-actions">
                        <button class="btn-edit-annotation" title="Modifier"><i class="fas fa-edit"></i></button>
                        <button class="btn-delete-annotation" title="Supprimer"><i class="fas fa-trash"></i></button>
                    </span>
                </div>
                <div class="annotation-details">
                    <div class="annotation-meta">
                        <span class="annotation-time">${dateFormatted}</span>
                        <span class="annotation-freq">${freqFormatted}</span>
                        <span class="annotation-mode">${annotation.mode}</span>
                    </div>
                    <div class="annotation-text">${annotation.notes}</div>
                    ${annotation.position ? `
                        <div class="annotation-position">
                            <i class="fas fa-map-marker-alt"></i>
                            ${annotation.position.lat.toFixed(6)}, ${annotation.position.lng.toFixed(6)}
                        </div>
                    ` : ''}
                    ${annotation.tags ? `
                        <div class="annotation-tags">
                            ${annotation.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
            
            // Add click handler
            item.addEventListener('click', (e) => {
                // Ignore if clicking buttons
                if (e.target.closest('.btn-edit-annotation') || 
                    e.target.closest('.btn-delete-annotation')) {
                    return;
                }
                
                this.selectAnnotation(annotation);
            });
            
            // Add edit button handler
            const editBtn = item.querySelector('.btn-edit-annotation');
            if (editBtn) {
                editBtn.addEventListener('click', () => {
                    this.editAnnotation(annotation);
                });
            }
            
            // Add delete button handler
            const deleteBtn = item.querySelector('.btn-delete-annotation');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', () => {
                    this.deleteAnnotation(annotation);
                });
            }
            
            list.appendChild(item);
        });
        
        this.annotationsList.appendChild(list);
        
        // Update map markers
        this.updateMapMarkers();
    }
    
    /**
     * Update map markers for annotations
     */
    updateMapMarkers() {
        if (!this.mapInstance) return;
        
        // Clear existing markers
        Object.values(this.markers).forEach(marker => {
            marker.remove();
        });
        this.markers = {};
        
        // Create new markers for annotations with positions
        this.annotations.forEach(annotation => {
            if (annotation.position) {
                // Create marker
                const marker = L.marker([annotation.position.lat, annotation.position.lng], {
                    icon: L.divIcon({
                        className: 'annotation-marker',
                        html: `<i class="fas fa-book"></i>`,
                        iconSize: [25, 25],
                        iconAnchor: [12, 25],
                        popupAnchor: [0, -25]
                    })
                }).addTo(this.mapInstance);
                
                // Add popup
                marker.bindPopup(`
                    <div class="annotation-popup">
                        <h3>${annotation.title}</h3>
                        <p>${annotation.notes}</p>
                        <p>
                            <strong>Fréquence:</strong> ${this.formatFrequency(annotation.frequency)}<br>
                            <strong>Mode:</strong> ${annotation.mode}<br>
                            <strong>Date:</strong> ${new Date(annotation.timestamp).toLocaleString()}
                        </p>
                    </div>
                `);
                
                // Store reference
                this.markers[annotation.id] = marker;
            }
        });
    }
    
    /**
     * Show the annotation form
     * @param {Object} annotation - Existing annotation for editing (null for new)
     */
    showAnnotationForm(annotation = null) {
        if (!this.annotationForm) return;
        
        // Clear form
        this.annotationForm.reset();
        
        // Set title
        const formTitle = this.annotationForm.querySelector('.form-title');
        if (formTitle) {
            formTitle.textContent = annotation ? 'Modifier Annotation' : 'Nouvelle Annotation';
        }
        
        // If editing existing annotation
        if (annotation) {
            // Set form ID
            this.annotationForm.dataset.editId = annotation.id;
            
            // Fill form fields
            const titleInput = this.annotationForm.querySelector('#annotation-title');
            if (titleInput) titleInput.value = annotation.title;
            
            const notesInput = this.annotationForm.querySelector('#annotation-notes');
            if (notesInput) notesInput.value = annotation.notes;
            
            const modeInput = this.annotationForm.querySelector('#annotation-mode');
            if (modeInput) modeInput.value = annotation.mode;
            
            const frequencyInput = this.annotationForm.querySelector('#annotation-frequency');
            if (frequencyInput) {
                if (annotation.frequency >= 1000000) {
                    frequencyInput.value = (annotation.frequency / 1000000).toFixed(6);
                    const unitSelect = this.annotationForm.querySelector('#annotation-frequency-unit');
                    if (unitSelect) unitSelect.value = '1000000'; // MHz
                } else if (annotation.frequency >= 1000) {
                    frequencyInput.value = (annotation.frequency / 1000).toFixed(3);
                    const unitSelect = this.annotationForm.querySelector('#annotation-frequency-unit');
                    if (unitSelect) unitSelect.value = '1000'; // kHz
                } else {
                    frequencyInput.value = annotation.frequency;
                    const unitSelect = this.annotationForm.querySelector('#annotation-frequency-unit');
                    if (unitSelect) unitSelect.value = '1'; // Hz
                }
            }
            
            const tagsInput = this.annotationForm.querySelector('#annotation-tags');
            if (tagsInput && annotation.tags) tagsInput.value = annotation.tags.join(', ');
            
            // Position
            const latInput = this.annotationForm.querySelector('#annotation-lat');
            const lngInput = this.annotationForm.querySelector('#annotation-lng');
            if (latInput && lngInput && annotation.position) {
                latInput.value = annotation.position.lat.toFixed(6);
                lngInput.value = annotation.position.lng.toFixed(6);
            }
        } else {
            // New annotation, pre-fill current values if available
            this.annotationForm.dataset.editId = '';
            
            // Pre-fill frequency
            if (this.waterfallDisplay && this.waterfallDisplay.selectedFreq) {
                const frequencyInput = this.annotationForm.querySelector('#annotation-frequency');
                const unitSelect = this.annotationForm.querySelector('#annotation-frequency-unit');
                
                if (frequencyInput && unitSelect) {
                    const freq = this.waterfallDisplay.selectedFreq;
                    
                    if (freq >= 1000000) {
                        frequencyInput.value = (freq / 1000000).toFixed(6);
                        unitSelect.value = '1000000'; // MHz
                    } else if (freq >= 1000) {
                        frequencyInput.value = (freq / 1000).toFixed(3);
                        unitSelect.value = '1000'; // kHz
                    } else {
                        frequencyInput.value = freq;
                        unitSelect.value = '1'; // Hz
                    }
                }
            }
            
            // Pre-fill mode
            const modeInput = this.annotationForm.querySelector('#annotation-mode');
            const modeSelect = document.getElementById('mode');
            if (modeInput && modeSelect) {
                modeInput.value = modeSelect.value;
            }
        }
        
        // Show form
        this.annotationForm.style.display = 'block';
    }
    
    /**
     * Handle annotation form submission
     */
    handleAnnotationFormSubmit() {
        const annotationForm = document.getElementById('annotation-form');
        if (!annotationForm) return;
        
        // Get form data
        const titleInput = document.getElementById('annotation-title');
        const notesInput = document.getElementById('annotation-notes');
        const frequencyInput = document.getElementById('annotation-frequency');
        const frequencyUnitSelect = document.getElementById('annotation-frequency-unit');
        const modeSelect = document.getElementById('annotation-mode');
        const tagsInput = document.getElementById('annotation-tags');
        const latInput = document.getElementById('annotation-lat');
        const lngInput = document.getElementById('annotation-lng');
        const idInput = document.getElementById('annotation-id');
        
        if (!titleInput || !titleInput.value.trim()) {
            alert('Please enter a title for the annotation');
            return;
        }
        
        // Calculate frequency in Hz if provided
        let frequency = null;
        if (frequencyInput && frequencyInput.value && frequencyUnitSelect) {
            const freqValue = parseFloat(frequencyInput.value);
            const multiplier = parseInt(frequencyUnitSelect.value) || 1;
            frequency = freqValue * multiplier;
        }
        
        // Create annotation object
        const annotation = {
            id: idInput && idInput.value ? idInput.value : null,
            title: titleInput ? titleInput.value : '',
            notes: notesInput ? notesInput.value : '',
            frequency: frequency,
            mode: modeSelect ? modeSelect.value : '',
            tags: tagsInput && tagsInput.value ? tagsInput.value.split(',').map(tag => tag.trim()) : [],
            latitude: latInput && latInput.value ? parseFloat(latInput.value) : null,
            longitude: lngInput && lngInput.value ? parseFloat(lngInput.value) : null,
            timestamp: new Date().toISOString()
        };
        
        // Save to server if socket is available
        if (socket) {
            socket.emit('save_annotation', annotation, (response) => {
                if (response && response.status === 'success') {
                    console.log('Annotation saved to server:', response.annotation);
                    
                    // Close the form
                    annotationForm.style.display = 'none';
                    
                    // Clear form
                    if (titleInput) titleInput.value = '';
                    if (notesInput) notesInput.value = '';
                    if (frequencyInput) frequencyInput.value = '';
                    if (tagsInput) tagsInput.value = '';
                    if (latInput) latInput.value = '';
                    if (lngInput) lngInput.value = '';
                    if (idInput) idInput.value = '';
                } else {
                    console.error('Failed to save annotation to server:', response);
                    alert('Failed to save annotation: ' + (response.message || 'Unknown error'));
                }
            });
        } else {
            // Fall back to local storage
            this.saveAnnotationToLocalStorage(annotation);
        }
    }
    
    /**
     * Save annotation to local storage (used as fallback when server is unavailable)
     * @param {Object} annotation The annotation to save
     */
    saveAnnotationToLocalStorage(annotation) {
        // Generate ID if not provided
        if (!annotation.id) {
            annotation.id = 'local_' + new Date().getTime();
        }
        
        // Find if this annotation already exists
        const index = this.annotations.findIndex(a => a.id === annotation.id);
        
        if (index >= 0) {
            // Update existing annotation
            this.annotations[index] = annotation;
        } else {
            // Add new annotation
            this.annotations.push(annotation);
        }
        
        // Save to local storage
        this.saveAnnotations();
        
        // Update UI
        this.renderAnnotationsList();
        this.updateMapMarkers();
        
        // Close the form
        const annotationForm = document.getElementById('annotation-form');
        if (annotationForm) {
            annotationForm.style.display = 'none';
        }
        
        // Clear form inputs
        const form = document.getElementById('annotation-form');
        if (form) {
            form.reset();
        }
    }
    
    /**
     * Select an annotation
     * @param {Object} annotation - The annotation to select
     */
    selectAnnotation(annotation) {
        console.log(`Selected annotation #${annotation.id}`);
        
        // Highlight in the list
        if (this.annotationsList) {
            const items = this.annotationsList.querySelectorAll('.annotation-item');
            items.forEach(item => {
                item.classList.remove('active');
                if (item.dataset.id == annotation.id) {
                    item.classList.add('active');
                }
            });
        }
        
        // Set frequency if waterfall display available
        if (this.waterfallDisplay) {
            this.waterfallDisplay.selectedFreq = annotation.frequency;
            this.waterfallDisplay.redraw();
        }
        
        // Pan to marker if position available
        if (this.mapInstance && annotation.position) {
            this.mapInstance.setView([annotation.position.lat, annotation.position.lng], 10);
            
            // Open popup if marker exists
            if (this.markers[annotation.id]) {
                this.markers[annotation.id].openPopup();
            }
        }
        
        // Call the selection callback
        if (this.options.onAnnotationSelect) {
            this.options.onAnnotationSelect(annotation);
        }
    }
    
    /**
     * Edit an annotation
     * @param {Object} annotation - The annotation to edit
     */
    editAnnotation(annotation) {
        console.log(`Editing annotation #${annotation.id}`);
        this.showAnnotationForm(annotation);
    }
    
    /**
     * Delete an annotation
     * @param {Object} annotation - The annotation to delete
     */
    deleteAnnotation(annotation) {
        if (!annotation || !annotation.id) return;
        
        if (!confirm(`Are you sure you want to delete annotation "${annotation.title}"?`)) {
            return;
        }
        
        // Delete from server if socket is available
        if (socket) {
            socket.emit('delete_annotation', { id: annotation.id }, (response) => {
                if (response && response.status === 'success') {
                    console.log('Annotation deleted from server:', annotation.id);
                } else {
                    console.error('Failed to delete annotation from server:', response);
                    alert('Failed to delete annotation: ' + (response.message || 'Unknown error'));
                    
                    // Fall back to local deletion for UI purposes
                    this.deleteAnnotationLocal(annotation.id);
                }
            });
        } else {
            // Fall back to local storage
            this.deleteAnnotationLocal(annotation.id);
        }
    }
    
    /**
     * Delete annotation locally (used as fallback when server is unavailable)
     * @param {string} annotationId The ID of the annotation to delete
     */
    deleteAnnotationLocal(annotationId) {
        // Remove the annotation from our array
        this.annotations = this.annotations.filter(a => a.id !== annotationId);
        
        // Save to local storage
        this.saveAnnotations();
        
        // Update UI
        this.renderAnnotationsList();
        this.updateMapMarkers();
    }
    
    /**
     * Export annotations to a file
     */
    exportAnnotations() {
        if (this.annotations.length === 0) {
            alert('Aucune annotation à exporter');
            return;
        }
        
        // Format annotations data
        const data = JSON.stringify(this.annotations, null, 2);
        
        // Create blob
        const blob = new Blob([data], { type: 'application/json' });
        
        // Create URL
        const url = URL.createObjectURL(blob);
        
        // Generate filename
        const date = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `sdr-annotations-${date}.json`;
        
        // Create download link
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Clean up URL
        setTimeout(() => {
            URL.revokeObjectURL(url);
        }, 100);
        
        console.log(`Exported ${this.annotations.length} annotations to ${filename}`);
    }
    
    /**
     * Format frequency for display
     * @param {number} freq - Frequency in Hz
     * @returns {string} Formatted frequency string
     */
    formatFrequency(freq) {
        if (freq >= 1000000) {
            return `${(freq / 1000000).toFixed(3)} MHz`;
        } else if (freq >= 1000) {
            return `${(freq / 1000).toFixed(2)} kHz`;
        } else {
            return `${freq} Hz`;
        }
    }
    
    /**
     * Set the waterfall display reference
     * @param {Object} waterfallDisplay - WaterfallDisplay instance
     */
    setWaterfallDisplay(waterfallDisplay) {
        this.waterfallDisplay = waterfallDisplay;
    }
    
    /**
     * Set the map instance reference
     * @param {Object} mapInstance - Leaflet map instance
     */
    setMapInstance(mapInstance) {
        this.mapInstance = mapInstance;
        this.updateMapMarkers();
    }
    
    /**
     * Handle an annotation update from the server
     * @param {Object} annotation The updated annotation
     */
    handleAnnotationUpdate(annotation) {
        if (!annotation || !annotation.id) return;
        
        // Find if this annotation already exists
        const index = this.annotations.findIndex(a => a.id === annotation.id);
        
        if (index >= 0) {
            // Update existing annotation
            this.annotations[index] = annotation;
        } else {
            // Add new annotation
            this.annotations.push(annotation);
        }
        
        // Update UI
        this.renderAnnotationsList();
        this.updateMapMarkers();
        
        // Save to local storage as backup
        this.saveAnnotations();
    }
    
    /**
     * Handle annotation deletion from the server
     * @param {string} annotationId The ID of the deleted annotation
     */
    handleAnnotationDeleted(annotationId) {
        if (!annotationId) return;
        
        // Remove the annotation from our array
        this.annotations = this.annotations.filter(a => a.id !== annotationId);
        
        // Update UI
        this.renderAnnotationsList();
        this.updateMapMarkers();
        
        // Save to local storage as backup
        this.saveAnnotations();
    }
}

// Export the class for use in other modules
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = { AnnotationSystem };
} else {
    window.AnnotationSystem = AnnotationSystem;
} 