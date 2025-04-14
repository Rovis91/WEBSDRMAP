/**
 * SDR Triangulation - Waterfall Visualization
 * 
 * This module provides the waterfall spectrogramme visualization for the SDR triangulation tool.
 * It handles:
 * - Rendering the spectrogram data using HTML5 Canvas
 * - Managing the color palette for visualization
 * - Handling user interactions like frequency selection and zoom
 * - Processing waterfall data from the backend
 */

class WaterfallDisplay {
    /**
     * Create a new waterfall display
     * @param {string} canvasId - ID of the canvas element to render on
     * @param {Object} options - Configuration options
     */
    constructor(canvasId, options = {}) {
        // Get canvas element
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`Canvas element with ID '${canvasId}' not found`);
            return;
        }
        
        this.ctx = this.canvas.getContext('2d');
        
        // Configuration options with defaults
        this.options = {
            colorScheme: options.colorScheme || 'default',
            minLevel: options.minLevel || -120,  // dB
            maxLevel: options.maxLevel || -30,   // dB
            historySize: options.historySize || 200, // Number of lines to keep
            freqStart: options.freqStart || 0,    // Hz
            freqEnd: options.freqEnd || 12000,    // Hz
            sampleRate: options.sampleRate || 12000, // Hz
            fftSize: options.fftSize || 1024,
            drawLabels: options.drawLabels !== undefined ? options.drawLabels : true,
            labelInterval: options.labelInterval || 1000 // Hz
        };
        
        // Internal state
        this.data = [];          // Array of waterfall lines (newest at end)
        this.isInitialized = false;
        this.selectedFreq = null;
        this.isRunning = false;
        this.colorMap = this.generateColorMap(this.options.colorScheme);
        
        // Bind event handlers
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('click', this.handleClick.bind(this));
        this.canvas.addEventListener('wheel', this.handleWheel.bind(this));
        
        // Handle resizing
        window.addEventListener('resize', this.handleResize.bind(this));
        this.handleResize();
        
        // Initial drawing
        this.drawEmptyWaterfall();
        this.isInitialized = true;
    }
    
    /**
     * Generate a color map for the waterfall display
     * @param {string} scheme - Name of the color scheme to use
     * @returns {Array} Array of RGBA values for each level
     */
    generateColorMap(scheme) {
        // Number of color levels
        const levels = 256;
        const colorMap = new Array(levels);
        
        switch (scheme) {
            case 'grayscale':
                // Simple black to white
                for (let i = 0; i < levels; i++) {
                    const v = i;
                    colorMap[i] = [v, v, v, 255];
                }
                break;
                
            case 'hot':
                // Black - Red - Yellow - White
                for (let i = 0; i < levels; i++) {
                    const normalized = i / (levels - 1);
                    let r, g, b;
                    
                    if (normalized < 0.33) {
                        // Black to Red
                        r = Math.round(normalized * 3 * 255);
                        g = 0;
                        b = 0;
                    } else if (normalized < 0.66) {
                        // Red to Yellow
                        r = 255;
                        g = Math.round((normalized - 0.33) * 3 * 255);
                        b = 0;
                    } else {
                        // Yellow to White
                        r = 255;
                        g = 255;
                        b = Math.round((normalized - 0.66) * 3 * 255);
                    }
                    
                    colorMap[i] = [r, g, b, 255];
                }
                break;
                
            case 'viridis':
                // A perceptually uniform color map (approximated)
                for (let i = 0; i < levels; i++) {
                    const t = i / (levels - 1);
                    let r, g, b;
                    
                    // Approximate the viridis colormap
                    r = Math.round(70 + (t * t * 120));
                    g = Math.round(t * 230);
                    b = Math.round(255 - (t * 210));
                    
                    colorMap[i] = [r, g, b, 255];
                }
                break;
                
            case 'default':
            default:
                // SDR waterfall classic (blue to red)
                for (let i = 0; i < levels; i++) {
                    const normalized = i / (levels - 1);
                    let r, g, b;
                    
                    if (normalized < 0.33) {
                        // Blue to Cyan
                        r = 0;
                        g = Math.round(normalized * 3 * 255);
                        b = 255;
                    } else if (normalized < 0.66) {
                        // Cyan to Yellow
                        r = Math.round((normalized - 0.33) * 3 * 255);
                        g = 255;
                        b = Math.round(255 - ((normalized - 0.33) * 3 * 255));
                    } else {
                        // Yellow to Red
                        r = 255;
                        g = Math.round(255 - ((normalized - 0.66) * 3 * 255));
                        b = 0;
                    }
                    
                    colorMap[i] = [r, g, b, 255];
                }
                break;
        }
        
        return colorMap;
    }
    
    /**
     * Handle window resize event
     */
    handleResize() {
        const container = this.canvas.parentElement;
        const dpr = window.devicePixelRatio || 1;
        
        // Set canvas dimensions to match container
        this.canvas.width = container.clientWidth * dpr;
        this.canvas.height = container.clientHeight * dpr;
        
        // Scale canvas to match container size
        this.canvas.style.width = container.clientWidth + 'px';
        this.canvas.style.height = container.clientHeight + 'px';
        
        // Scale context to account for device pixel ratio
        this.ctx.scale(dpr, dpr);
        
        // Redraw the waterfall
        this.redraw();
    }
    
    /**
     * Handle mouse movement over the waterfall
     * @param {MouseEvent} event - Mouse event
     */
    handleMouseMove(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        
        // Convert x position to frequency
        const freqRange = this.options.freqEnd - this.options.freqStart;
        const frequency = this.options.freqStart + (x / rect.width) * freqRange;
        
        // Update frequency display (if needed)
        if (typeof this.options.onFrequencyHover === 'function') {
            this.options.onFrequencyHover(frequency);
        }
    }
    
    /**
     * Handle click on the waterfall
     * @param {MouseEvent} event - Mouse event
     */
    handleClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        
        // Convert x position to frequency
        const freqRange = this.options.freqEnd - this.options.freqStart;
        const frequency = this.options.freqStart + (x / rect.width) * freqRange;
        
        // Set selected frequency
        this.selectedFreq = frequency;
        
        // Call the frequency selection callback
        if (typeof this.options.onFrequencySelect === 'function') {
            this.options.onFrequencySelect(frequency);
        }
        
        // Redraw to show the selected frequency
        this.redraw();
    }
    
    /**
     * Handle mouse wheel for zooming
     * @param {WheelEvent} event - Wheel event
     */
    handleWheel(event) {
        event.preventDefault();
        
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        
        // Get the frequency at the mouse position
        const freqRange = this.options.freqEnd - this.options.freqStart;
        const frequency = this.options.freqStart + (x / rect.width) * freqRange;
        
        // Calculate zoom factor based on wheel delta
        const zoomFactor = 1 + (event.deltaY > 0 ? 0.1 : -0.1);
        
        // Apply zoom
        const newRange = freqRange * zoomFactor;
        
        // Calculate new start and end frequencies, keeping the mouse position fixed
        const ratio = (frequency - this.options.freqStart) / freqRange;
        const newStart = frequency - (ratio * newRange);
        const newEnd = newStart + newRange;
        
        // Enforce limits
        if (newStart >= 0 && newEnd <= this.options.sampleRate / 2) {
            this.options.freqStart = newStart;
            this.options.freqEnd = newEnd;
            this.redraw();
        }
    }
    
    /**
     * Draw an empty waterfall placeholder
     */
    drawEmptyWaterfall() {
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;
        
        // Clear background
        this.ctx.fillStyle = '#111';
        this.ctx.fillRect(0, 0, width, height);
        
        // Add placeholder text
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
        this.ctx.font = '16px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('En attente des données du spectrogramme...', width / 2, height / 2);
        
        // Draw frequency scale
        if (this.options.drawLabels) {
            this.drawFrequencyScale();
        }
    }
    
    /**
     * Draw frequency scale at the bottom of the waterfall
     */
    drawFrequencyScale() {
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;
        
        // Draw scale background
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        this.ctx.fillRect(0, height - 20, width, 20);
        
        // Draw frequency labels
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
        this.ctx.font = '10px Arial';
        this.ctx.textAlign = 'center';
        
        const freqRange = this.options.freqEnd - this.options.freqStart;
        const interval = this.options.labelInterval;
        const startLabel = Math.ceil(this.options.freqStart / interval) * interval;
        
        for (let freq = startLabel; freq <= this.options.freqEnd; freq += interval) {
            const x = ((freq - this.options.freqStart) / freqRange) * width;
            
            // Skip labels that would go off screen
            if (x < 0 || x > width) continue;
            
            // Draw tick mark
            this.ctx.fillRect(x - 0.5, height - 20, 1, 5);
            
            // Format label based on frequency value
            let label;
            if (freq >= 1000000) {
                label = (freq / 1000000).toFixed(1) + ' MHz';
            } else if (freq >= 1000) {
                label = (freq / 1000).toFixed(1) + ' kHz';
            } else {
                label = freq + ' Hz';
            }
            
            // Draw the label
            this.ctx.fillText(label, x, height - 5);
        }
    }
    
    /**
     * Add a new FFT data line to the waterfall
     * @param {Array} fftData - Array of FFT power values in dB
     */
    addData(fftData) {
        if (!this.isInitialized) return;
        
        // Process the FFT data if necessary (e.g., slice to the current frequency range)
        const processedData = this.processFFTData(fftData);
        
        // Add the new line to the data array
        this.data.push(processedData);
        
        // Trim the data array to the history size
        if (this.data.length > this.options.historySize) {
            this.data = this.data.slice(this.data.length - this.options.historySize);
        }
        
        // Update the display
        this.redraw();
    }
    
    /**
     * Process FFT data for the current frequency range
     * @param {Array} fftData - Raw FFT data
     * @returns {Array} Processed FFT data
     */
    processFFTData(fftData) {
        // If the data is already the right size and range, return it directly
        if (fftData.length === this.canvas.width / window.devicePixelRatio) {
            return fftData;
        }
        
        // Calculate the start and end indices in the FFT data
        const totalBins = this.options.fftSize;
        const startBin = Math.floor((this.options.freqStart / (this.options.sampleRate / 2)) * (totalBins / 2));
        const endBin = Math.ceil((this.options.freqEnd / (this.options.sampleRate / 2)) * (totalBins / 2));
        
        // Get the portion of FFT data for the current frequency range
        const rangeData = fftData.slice(startBin, endBin);
        
        // Resample to match canvas width
        const targetWidth = this.canvas.width / window.devicePixelRatio;
        const processedData = new Array(targetWidth);
        
        for (let i = 0; i < targetWidth; i++) {
            const sourceIndex = Math.floor((i / targetWidth) * rangeData.length);
            processedData[i] = rangeData[sourceIndex];
        }
        
        return processedData;
    }
    
    /**
     * Redraw the entire waterfall
     */
    redraw() {
        if (!this.isInitialized) return;
        
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;
        const lineHeight = Math.ceil((height - 20) / this.options.historySize);
        
        // Clear the canvas
        this.ctx.fillStyle = '#111';
        this.ctx.fillRect(0, 0, width, height);
        
        // If there's no data, show the empty state
        if (this.data.length === 0) {
            this.drawEmptyWaterfall();
            return;
        }
        
        // Draw each line of the waterfall
        for (let i = 0; i < this.data.length; i++) {
            const lineData = this.data[i];
            const y = height - 20 - (i + 1) * lineHeight;
            
            this.drawWaterfallLine(lineData, y, lineHeight);
        }
        
        // Draw the selected frequency indicator
        if (this.selectedFreq !== null) {
            const x = ((this.selectedFreq - this.options.freqStart) / 
                       (this.options.freqEnd - this.options.freqStart)) * width;
            
            this.ctx.strokeStyle = 'red';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, height - 20);
            this.ctx.stroke();
        }
        
        // Draw frequency scale
        if (this.options.drawLabels) {
            this.drawFrequencyScale();
        }
    }
    
    /**
     * Draw a single line of the waterfall
     * @param {Array} lineData - FFT data for the line
     * @param {number} y - Y-coordinate to start drawing
     * @param {number} height - Height of the line
     */
    drawWaterfallLine(lineData, y, height) {
        const width = this.canvas.width / window.devicePixelRatio;
        const imgData = this.ctx.createImageData(width, height);
        const data = imgData.data;
        
        // For each pixel in the line
        for (let x = 0; x < width; x++) {
            // Map the value to a color
            const value = lineData[x];
            
            // Normalize value to 0-1 range for color mapping
            let normalized = (value - this.options.minLevel) / 
                            (this.options.maxLevel - this.options.minLevel);
            normalized = Math.max(0, Math.min(1, normalized));
            
            // Get the color from the colormap
            const colorIndex = Math.floor(normalized * (this.colorMap.length - 1));
            const color = this.colorMap[colorIndex];
            
            // Set the value for each pixel in the height
            for (let h = 0; h < height; h++) {
                const offset = ((h * width) + x) * 4;
                data[offset] = color[0];     // R
                data[offset + 1] = color[1]; // G
                data[offset + 2] = color[2]; // B
                data[offset + 3] = color[3]; // A
            }
        }
        
        // Draw the image data
        this.ctx.putImageData(imgData, 0, y);
    }
    
    /**
     * Start the waterfall display
     */
    start() {
        this.isRunning = true;
    }
    
    /**
     * Stop the waterfall display
     */
    stop() {
        this.isRunning = false;
    }
    
    /**
     * Clear all waterfall data
     */
    clear() {
        this.data = [];
        this.redraw();
    }
    
    /**
     * Set the frequency range for the waterfall display
     * @param {number} start - Start frequency in Hz
     * @param {number} end - End frequency in Hz
     */
    setFrequencyRange(start, end) {
        this.options.freqStart = start;
        this.options.freqEnd = end;
        this.redraw();
    }
    
    /**
     * Set the color scheme for the waterfall
     * @param {string} scheme - Color scheme name
     */
    setColorScheme(scheme) {
        this.options.colorScheme = scheme;
        this.colorMap = this.generateColorMap(scheme);
        this.redraw();
    }
}

// Export the class for use in other modules
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = { WaterfallDisplay };
} else {
    window.WaterfallDisplay = WaterfallDisplay;
} 