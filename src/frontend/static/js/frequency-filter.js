/**
 * SDR Triangulation - Frequency Filtering
 * 
 * This module provides frequency filtering and selection functionality for the SDR triangulation tool.
 * It handles:
 * - Frequency band filtering
 * - Signal highlighting
 * - Frequency selection and favorites
 * - Band allocation display
 */

class FrequencyFilter {
    /**
     * Create a new frequency filter
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        // Configuration options
        this.options = {
            filterElementId: options.filterElementId || 'frequency-filter',
            bandsElementId: options.bandsElementId || 'frequency-bands',
            favoritesElementId: options.favoritesElementId || 'frequency-favorites',
            frequencyInputId: options.frequencyInputId || 'frequency',
            frequencyUnitId: options.frequencyUnitId || 'frequency-unit',
            waterfallDisplay: options.waterfallDisplay || null,
            onFrequencySelect: options.onFrequencySelect || null
        };
        
        // DOM elements
        this.filterElement = document.getElementById(this.options.filterElementId);
        this.bandsElement = document.getElementById(this.options.bandsElementId);
        this.favoritesElement = document.getElementById(this.options.favoritesElementId);
        this.frequencyInput = document.getElementById(this.options.frequencyInputId);
        this.frequencyUnit = document.getElementById(this.options.frequencyUnitId);
        
        // State
        this.bands = [];
        this.favorites = [];
        this.currentFilter = null;
        this.waterfallDisplay = this.options.waterfallDisplay;
        
        // Common amateur radio bands (name, start, end, mode)
        this.commonBands = [
            { name: '160m', start: 1800000, end: 2000000, modes: ['CW', 'LSB'] },
            { name: '80m', start: 3500000, end: 4000000, modes: ['CW', 'LSB'] },
            { name: '60m', start: 5330500, end: 5405000, modes: ['USB'] },
            { name: '40m', start: 7000000, end: 7300000, modes: ['CW', 'LSB'] },
            { name: '30m', start: 10100000, end: 10150000, modes: ['CW', 'DIGITAL'] },
            { name: '20m', start: 14000000, end: 14350000, modes: ['CW', 'USB'] },
            { name: '17m', start: 18068000, end: 18168000, modes: ['CW', 'USB'] },
            { name: '15m', start: 21000000, end: 21450000, modes: ['CW', 'USB'] },
            { name: '12m', start: 24890000, end: 24990000, modes: ['CW', 'USB'] },
            { name: '10m', start: 28000000, end: 29700000, modes: ['CW', 'USB', 'FM'] },
            { name: '6m', start: 50000000, end: 54000000, modes: ['CW', 'USB', 'FM'] },
            { name: '2m', start: 144000000, end: 148000000, modes: ['CW', 'USB', 'FM'] }
        ];
        
        // Important frequencies (emergency, calling, etc)
        this.importantFrequencies = [
            { name: 'International Distress', freq: 2182000, mode: 'USB' },
            { name: 'Maritime Calling', freq: 2182000, mode: 'USB' },
            { name: 'International Calling SSB', freq: 14300000, mode: 'USB' },
            { name: 'International Calling CW', freq: 14050000, mode: 'CW' },
            { name: 'WWV Time Signal', freq: 10000000, mode: 'AM' },
            { name: 'WWV Time Signal', freq: 15000000, mode: 'AM' },
            { name: 'Aviation Emergency', freq: 121500000, mode: 'AM' }
        ];
        
        // Initialize
        this.initialize();
    }
    
    /**
     * Initialize the frequency filter
     */
    initialize() {
        // Load saved favorites
        this.loadFavorites();
        
        // Initialize bands if element exists
        if (this.bandsElement) {
            this.initializeBands();
        }
        
        // Initialize favorites if element exists
        if (this.favoritesElement) {
            this.renderFavorites();
        }
        
        // Initialize frequency input
        if (this.frequencyInput && this.frequencyUnit) {
            // Handle frequency input changes
            this.frequencyInput.addEventListener('change', () => {
                const value = parseFloat(this.frequencyInput.value);
                if (isNaN(value)) return;
                
                const unit = parseFloat(this.frequencyUnit.value);
                const frequency = value * unit;
                
                this.selectFrequency(frequency);
            });
            
            // Handle unit changes
            this.frequencyUnit.addEventListener('change', () => {
                const value = parseFloat(this.frequencyInput.value);
                if (isNaN(value)) return;
                
                const oldUnit = this.frequencyUnit.dataset.lastValue || 1000;
                const newUnit = parseFloat(this.frequencyUnit.value);
                
                // Convert the value to maintain the same frequency
                const oldFreq = value * parseFloat(oldUnit);
                this.frequencyInput.value = (oldFreq / newUnit).toFixed(
                    newUnit >= 1000000 ? 6 : newUnit >= 1000 ? 3 : 0
                );
                
                // Save the current unit for next conversion
                this.frequencyUnit.dataset.lastValue = newUnit;
            });
        }
    }
    
    /**
     * Initialize frequency bands
     */
    initializeBands() {
        // Clear the bands element
        this.bandsElement.innerHTML = '';
        
        // Create header
        const header = document.createElement('h3');
        header.textContent = 'Bandes de fréquences';
        this.bandsElement.appendChild(header);
        
        // Create list of bands
        const bandsList = document.createElement('ul');
        bandsList.className = 'bands-list';
        
        // Add each common band
        this.commonBands.forEach(band => {
            const bandItem = document.createElement('li');
            bandItem.className = 'band-item';
            
            // Format frequency range
            const startFormatted = this.formatFrequency(band.start);
            const endFormatted = this.formatFrequency(band.end);
            
            // Create band element
            bandItem.innerHTML = `
                <span class="band-name">${band.name}</span>
                <span class="band-range">${startFormatted} - ${endFormatted}</span>
                <span class="band-modes">${band.modes.join(', ')}</span>
            `;
            
            // Add click handler
            bandItem.addEventListener('click', () => {
                this.selectBand(band);
            });
            
            bandsList.appendChild(bandItem);
        });
        
        this.bandsElement.appendChild(bandsList);
    }
    
    /**
     * Load favorites from local storage
     */
    loadFavorites() {
        try {
            const saved = localStorage.getItem('frequency_favorites');
            if (saved) {
                this.favorites = JSON.parse(saved);
            }
        } catch (error) {
            console.error('Error loading favorites:', error);
            this.favorites = [];
        }
        
        // Add important frequencies if no favorites
        if (this.favorites.length === 0) {
            this.favorites = this.importantFrequencies.slice(0, 3);
            this.saveFavorites();
        }
    }
    
    /**
     * Save favorites to local storage
     */
    saveFavorites() {
        try {
            localStorage.setItem('frequency_favorites', JSON.stringify(this.favorites));
        } catch (error) {
            console.error('Error saving favorites:', error);
        }
    }
    
    /**
     * Render favorites in the favorites element
     */
    renderFavorites() {
        if (!this.favoritesElement) return;
        
        // Clear the favorites element
        this.favoritesElement.innerHTML = '';
        
        // Create header
        const header = document.createElement('h3');
        header.textContent = 'Fréquences favorites';
        this.favoritesElement.appendChild(header);
        
        // Create favorites list
        const favoritesList = document.createElement('ul');
        favoritesList.className = 'favorites-list';
        
        // Add each favorite
        this.favorites.forEach(favorite => {
            const favoriteItem = document.createElement('li');
            favoriteItem.className = 'favorite-item';
            
            // Format frequency
            const freqFormatted = this.formatFrequency(favorite.freq);
            
            // Create favorite element
            favoriteItem.innerHTML = `
                <span class="favorite-freq">${freqFormatted}</span>
                <span class="favorite-name">${favorite.name}</span>
                <span class="favorite-mode">${favorite.mode}</span>
                <button class="btn-remove-favorite" title="Supprimer des favoris">×</button>
            `;
            
            // Add click handler for selecting frequency
            favoriteItem.addEventListener('click', (e) => {
                // Don't trigger if clicking the remove button
                if (e.target.classList.contains('btn-remove-favorite')) return;
                
                this.selectFrequency(favorite.freq);
                
                // Select the mode if available
                const modeSelect = document.getElementById('mode');
                if (modeSelect && favorite.mode) {
                    modeSelect.value = favorite.mode;
                    // Trigger change event
                    const event = new Event('change');
                    modeSelect.dispatchEvent(event);
                }
            });
            
            // Add click handler for remove button
            const removeBtn = favoriteItem.querySelector('.btn-remove-favorite');
            removeBtn.addEventListener('click', () => {
                this.removeFavorite(favorite);
            });
            
            favoritesList.appendChild(favoriteItem);
        });
        
        // Add "add favorite" button
        const addFavoriteItem = document.createElement('li');
        addFavoriteItem.className = 'add-favorite-item';
        
        const addButton = document.createElement('button');
        addButton.className = 'btn-add-favorite';
        addButton.innerHTML = '<i class="fas fa-plus"></i> Ajouter la fréquence actuelle';
        addButton.addEventListener('click', () => {
            this.addCurrentFrequency();
        });
        
        addFavoriteItem.appendChild(addButton);
        favoritesList.appendChild(addFavoriteItem);
        
        this.favoritesElement.appendChild(favoritesList);
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
     * Select a frequency
     * @param {number} frequency - Frequency in Hz
     */
    selectFrequency(frequency) {
        // Update frequency input if it exists
        if (this.frequencyInput && this.frequencyUnit) {
            let displayValue, unit;
            
            if (frequency >= 1000000) {
                displayValue = frequency / 1000000;
                unit = '1000000'; // MHz
            } else if (frequency >= 1000) {
                displayValue = frequency / 1000;
                unit = '1000'; // kHz
            } else {
                displayValue = frequency;
                unit = '1'; // Hz
            }
            
            this.frequencyInput.value = displayValue;
            this.frequencyUnit.value = unit;
            this.frequencyUnit.dataset.lastValue = unit;
        }
        
        // Update waterfall display if available
        if (this.waterfallDisplay) {
            // Select frequency in waterfall
            this.waterfallDisplay.selectedFreq = frequency;
            this.waterfallDisplay.redraw();
        }
        
        // Call the frequency selection callback
        if (this.options.onFrequencySelect) {
            this.options.onFrequencySelect(frequency);
        }
        
        console.log(`Frequency selected: ${frequency} Hz`);
    }
    
    /**
     * Select a band
     * @param {Object} band - Band object with start and end frequencies
     */
    selectBand(band) {
        // Get center frequency of the band
        const centerFreq = (band.start + band.end) / 2;
        
        // Update waterfall range if available
        if (this.waterfallDisplay) {
            this.waterfallDisplay.setFrequencyRange(band.start, band.end);
        }
        
        // Select center frequency
        this.selectFrequency(centerFreq);
        
        // Set filter
        this.currentFilter = band;
        
        // Update UI to show current filter
        if (this.bandsElement) {
            const bandItems = this.bandsElement.querySelectorAll('.band-item');
            bandItems.forEach(item => {
                item.classList.remove('active');
                if (item.querySelector('.band-name').textContent === band.name) {
                    item.classList.add('active');
                }
            });
        }
        
        console.log(`Band selected: ${band.name} (${band.start} - ${band.end} Hz)`);
    }
    
    /**
     * Add current frequency to favorites
     */
    addCurrentFrequency() {
        if (!this.frequencyInput || !this.frequencyUnit) return;
        
        // Get current frequency
        const value = parseFloat(this.frequencyInput.value);
        if (isNaN(value)) return;
        
        const unit = parseFloat(this.frequencyUnit.value);
        const frequency = value * unit;
        
        // Get current mode
        const modeSelect = document.getElementById('mode');
        const mode = modeSelect ? modeSelect.value : 'AM';
        
        // Prompt for name
        const name = prompt("Nom de la fréquence:", "");
        if (name === null) return; // User cancelled
        
        // Add to favorites
        this.favorites.push({
            name: name || this.formatFrequency(frequency),
            freq: frequency,
            mode: mode
        });
        
        // Save and update UI
        this.saveFavorites();
        this.renderFavorites();
        
        console.log(`Added frequency to favorites: ${frequency} Hz (${name})`);
    }
    
    /**
     * Remove a favorite frequency
     * @param {Object} favorite - Favorite to remove
     */
    removeFavorite(favorite) {
        // Find index of favorite
        const index = this.favorites.findIndex(f => 
            f.freq === favorite.freq && f.name === favorite.name
        );
        
        if (index !== -1) {
            // Remove from array
            this.favorites.splice(index, 1);
            
            // Save and update UI
            this.saveFavorites();
            this.renderFavorites();
            
            console.log(`Removed frequency from favorites: ${favorite.freq} Hz (${favorite.name})`);
        }
    }
    
    /**
     * Set the waterfall display reference
     * @param {Object} waterfallDisplay - WaterfallDisplay instance
     */
    setWaterfallDisplay(waterfallDisplay) {
        this.waterfallDisplay = waterfallDisplay;
    }
}

// Export the class for use in other modules
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = { FrequencyFilter };
} else {
    window.FrequencyFilter = FrequencyFilter;
} 