/**
 * SDR Triangulation - Audio Control
 * 
 * This module provides audio streaming and control functionality for the SDR triangulation tool.
 * It handles:
 * - Audio streaming from receivers
 * - Volume and mute controls
 * - Audio recording and export
 * - Visualization of audio levels
 */

class AudioController {
    /**
     * Create a new audio controller
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        // Configuration
        this.options = {
            audioElementId: options.audioElementId || 'audio-player',
            visualizerId: options.visualizerId || 'audio-visualizer',
            volumeElementId: options.volumeElementId || 'volume-control',
            muteButtonId: options.muteButtonId || 'mute-button',
            recordButtonId: options.recordButtonId || 'btn-record',
            saveButtonId: options.saveButtonId || 'btn-save-audio',
            onError: options.onError || console.error
        };
        
        // Audio elements
        this.audioElement = document.getElementById(this.options.audioElementId);
        this.visualizerCanvas = document.getElementById(this.options.visualizerId);
        this.volumeControl = document.getElementById(this.options.volumeElementId);
        this.muteButton = document.getElementById(this.options.muteButtonId);
        this.recordButton = document.getElementById(this.options.recordButtonId);
        this.saveButton = document.getElementById(this.options.saveButtonId);
        
        // Audio processing
        this.audioContext = null;
        this.audioSource = null;
        this.gainNode = null;
        this.analyser = null;
        this.animationFrame = null;
        
        // Recording state
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.isRecording = false;
        this.recordedAudioBlob = null;
        
        // Stream state
        this.activeReceiver = null;
        this.isPlaying = false;
        this.isMuted = false;
        
        // Initialize
        this.initialize();
    }
    
    /**
     * Initialize the audio controller
     */
    initialize() {
        // Check if the required elements exist
        if (!this.audioElement) {
            console.error(`Audio element with ID '${this.options.audioElementId}' not found`);
            return;
        }
        
        // Create audio context
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create audio source from the audio element
            this.audioSource = this.audioContext.createMediaElementSource(this.audioElement);
            
            // Create gain node for volume control
            this.gainNode = this.audioContext.createGain();
            this.audioSource.connect(this.gainNode);
            
            // Create analyser for visualization
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.gainNode.connect(this.analyser);
            
            // Connect to output
            this.analyser.connect(this.audioContext.destination);
            
            // Set up volume control
            if (this.volumeControl) {
                this.volumeControl.addEventListener('input', () => {
                    this.setVolume(this.volumeControl.value);
                });
                
                // Set initial volume
                this.setVolume(this.volumeControl.value || 0.75);
            }
            
            // Set up mute button
            if (this.muteButton) {
                this.muteButton.addEventListener('click', () => {
                    this.toggleMute();
                });
            }
            
            // Set up record button
            if (this.recordButton) {
                this.recordButton.addEventListener('click', () => {
                    if (this.isRecording) {
                        this.stopRecording();
                    } else {
                        this.startRecording();
                    }
                });
            }
            
            // Set up save button
            if (this.saveButton) {
                this.saveButton.addEventListener('click', () => {
                    this.saveRecording();
                });
                
                // Disable save button initially
                this.saveButton.disabled = true;
            }
            
            // Initialize audio visualization
            if (this.visualizerCanvas) {
                this.initializeVisualizer();
                this.startVisualization();
            }
            
            // Set up audio element events
            this.audioElement.addEventListener('play', () => {
                this.isPlaying = true;
                if (this.visualizerCanvas) this.startVisualization();
            });
            
            this.audioElement.addEventListener('pause', () => {
                this.isPlaying = false;
                if (this.visualizerCanvas) this.stopVisualization();
            });
            
            this.audioElement.addEventListener('ended', () => {
                this.isPlaying = false;
                if (this.visualizerCanvas) this.stopVisualization();
            });
            
            this.audioElement.addEventListener('error', (e) => {
                console.error('Audio element error:', e);
                this.isPlaying = false;
                if (this.visualizerCanvas) this.stopVisualization();
                if (this.options.onError) this.options.onError('Erreur de lecture audio');
            });
            
            console.log('Audio controller initialized successfully');
        } catch (error) {
            console.error('Failed to initialize audio controller:', error);
            if (this.options.onError) this.options.onError('Initialisation audio échouée');
        }
    }
    
    /**
     * Set the audio stream source URL
     * @param {string} url - The audio stream URL
     * @param {string} receiverName - Name of the receiver
     */
    setAudioSource(url, receiverName) {
        if (!this.audioElement) return;
        
        // Stop any current playback
        this.audioElement.pause();
        
        // Set the new source
        this.audioElement.src = url;
        this.activeReceiver = receiverName;
        
        // Enable record button if source is set
        if (this.recordButton) {
            this.recordButton.disabled = !url;
        }
        
        console.log(`Audio source set to: ${url} (${receiverName})`);
    }
    
    /**
     * Start playing the current audio source
     */
    play() {
        if (!this.audioElement || !this.audioElement.src) return;
        
        // Resume audio context if suspended
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
        
        this.audioElement.play()
            .catch(error => {
                console.error('Error playing audio:', error);
                if (this.options.onError) this.options.onError('Erreur de lecture audio');
            });
    }
    
    /**
     * Pause the current audio playback
     */
    pause() {
        if (!this.audioElement) return;
        this.audioElement.pause();
    }
    
    /**
     * Set the audio volume
     * @param {number} value - Volume value between 0 and 1
     */
    setVolume(value) {
        if (!this.gainNode) return;
        
        // Ensure the value is between 0 and 1
        const volume = Math.min(Math.max(0, value), 1);
        
        // Set the gain value
        this.gainNode.gain.value = volume;
        
        // Update the volume control if it exists
        if (this.volumeControl && this.volumeControl.value !== volume) {
            this.volumeControl.value = volume;
        }
        
        // Update the mute state
        this.isMuted = volume === 0;
        
        // Update the mute button if it exists
        if (this.muteButton) {
            this.muteButton.classList.toggle('muted', this.isMuted);
            this.muteButton.innerHTML = this.isMuted 
                ? '<i class="fas fa-volume-mute"></i>' 
                : '<i class="fas fa-volume-up"></i>';
        }
    }
    
    /**
     * Toggle mute state
     */
    toggleMute() {
        if (this.isMuted) {
            // Unmute - restore previous volume or default to 0.75
            this.setVolume(this.previousVolume || 0.75);
        } else {
            // Mute - save current volume and set to 0
            this.previousVolume = this.gainNode.gain.value;
            this.setVolume(0);
        }
    }
    
    /**
     * Initialize the audio visualizer
     */
    initializeVisualizer() {
        if (!this.visualizerCanvas) return;
        
        const ctx = this.visualizerCanvas.getContext('2d');
        
        // Resize canvas to match container
        const container = this.visualizerCanvas.parentElement;
        this.visualizerCanvas.width = container.clientWidth;
        this.visualizerCanvas.height = container.clientHeight;
        
        // Draw placeholder
        ctx.fillStyle = '#333';
        ctx.fillRect(0, 0, this.visualizerCanvas.width, this.visualizerCanvas.height);
        ctx.fillStyle = '#aaa';
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Pas d\'audio', this.visualizerCanvas.width / 2, this.visualizerCanvas.height / 2);
        
        // Add resize handler
        window.addEventListener('resize', () => {
            if (!this.visualizerCanvas) return;
            
            const container = this.visualizerCanvas.parentElement;
            this.visualizerCanvas.width = container.clientWidth;
            this.visualizerCanvas.height = container.clientHeight;
        });
    }
    
    /**
     * Start the audio visualization
     */
    startVisualization() {
        if (!this.visualizerCanvas || !this.analyser) return;
        
        const ctx = this.visualizerCanvas.getContext('2d');
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        
        const draw = () => {
            if (!this.isPlaying) return;
            
            this.animationFrame = requestAnimationFrame(draw);
            
            this.analyser.getByteFrequencyData(dataArray);
            
            ctx.fillStyle = '#333';
            ctx.fillRect(0, 0, this.visualizerCanvas.width, this.visualizerCanvas.height);
            
            const barWidth = (this.visualizerCanvas.width / bufferLength) * 2.5;
            let x = 0;
            
            for (let i = 0; i < bufferLength; i++) {
                const barHeight = dataArray[i] / 255 * this.visualizerCanvas.height;
                
                // Calculate color based on frequency (blue to red)
                const hue = i / bufferLength * 240;
                ctx.fillStyle = `hsl(${240 - hue}, 100%, 50%)`;
                
                ctx.fillRect(x, this.visualizerCanvas.height - barHeight, barWidth, barHeight);
                
                x += barWidth + 1;
            }
        };
        
        draw();
    }
    
    /**
     * Stop the audio visualization
     */
    stopVisualization() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
    }
    
    /**
     * Start recording the current audio
     */
    startRecording() {
        if (!this.audioElement || !this.audioElement.src || this.isRecording) return;
        
        console.log('Starting audio recording...');
        
        try {
            // Create a new audio stream from the audio element's output
            const stream = this.analyser.context.createMediaStreamDestination();
            this.gainNode.connect(stream);
            
            // Create a media recorder
            this.mediaRecorder = new MediaRecorder(stream.stream);
            this.recordedChunks = [];
            
            // Listen for data available events
            this.mediaRecorder.addEventListener('dataavailable', (event) => {
                if (event.data.size > 0) {
                    this.recordedChunks.push(event.data);
                }
            });
            
            // Listen for stop event
            this.mediaRecorder.addEventListener('stop', () => {
                // Create a blob from the recorded chunks
                this.recordedAudioBlob = new Blob(this.recordedChunks, { type: 'audio/wav' });
                
                // Enable the save button
                if (this.saveButton) {
                    this.saveButton.disabled = false;
                }
                
                console.log('Recording completed:', this.recordedAudioBlob.size, 'bytes');
            });
            
            // Start recording
            this.mediaRecorder.start();
            this.isRecording = true;
            
            // Update the record button
            if (this.recordButton) {
                this.recordButton.innerHTML = '<i class="fas fa-stop"></i> Arrêter';
                this.recordButton.classList.add('recording');
            }
            
            console.log('Recording started');
        } catch (error) {
            console.error('Error starting recording:', error);
            if (this.options.onError) this.options.onError('Erreur au démarrage de l\'enregistrement');
        }
    }
    
    /**
     * Stop the current recording
     */
    stopRecording() {
        if (!this.isRecording || !this.mediaRecorder) return;
        
        console.log('Stopping audio recording...');
        
        try {
            // Stop the media recorder
            this.mediaRecorder.stop();
            this.isRecording = false;
            
            // Update the record button
            if (this.recordButton) {
                this.recordButton.innerHTML = '<i class="fas fa-microphone"></i> Enregistrer';
                this.recordButton.classList.remove('recording');
            }
            
            console.log('Recording stopped');
        } catch (error) {
            console.error('Error stopping recording:', error);
            if (this.options.onError) this.options.onError('Erreur à l\'arrêt de l\'enregistrement');
        }
    }
    
    /**
     * Save the recorded audio as a WAV file
     */
    saveRecording() {
        if (!this.recordedAudioBlob) {
            console.warn('No recorded audio to save');
            return;
        }
        
        try {
            // Create a filename with date and receiver name
            const date = new Date().toISOString().replace(/[:.]/g, '-');
            const receiver = this.activeReceiver || 'unknown';
            const filename = `sdr_recording_${receiver}_${date}.wav`;
            
            // Create a URL for the blob
            const url = URL.createObjectURL(this.recordedAudioBlob);
            
            // Create a temporary anchor element
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            
            // Append to the body, click, and remove
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Clean up the URL
            setTimeout(() => {
                URL.revokeObjectURL(url);
            }, 100);
            
            console.log(`Recording saved as '${filename}'`);
        } catch (error) {
            console.error('Error saving recording:', error);
            if (this.options.onError) this.options.onError('Erreur lors de la sauvegarde de l\'enregistrement');
        }
    }
    
    /**
     * Clean up resources
     */
    cleanup() {
        // Stop any active operations
        if (this.isPlaying) this.pause();
        if (this.isRecording) this.stopRecording();
        this.stopVisualization();
        
        // Remove event listeners
        if (this.volumeControl) {
            this.volumeControl.removeEventListener('input', this.setVolume);
        }
        
        if (this.muteButton) {
            this.muteButton.removeEventListener('click', this.toggleMute);
        }
        
        if (this.recordButton) {
            this.recordButton.removeEventListener('click', this.startRecording);
        }
        
        if (this.saveButton) {
            this.saveButton.removeEventListener('click', this.saveRecording);
        }
        
        // Disconnect audio nodes
        if (this.audioSource) this.audioSource.disconnect();
        if (this.gainNode) this.gainNode.disconnect();
        if (this.analyser) this.analyser.disconnect();
        
        // Close audio context
        if (this.audioContext) this.audioContext.close();
        
        console.log('Audio controller cleaned up');
    }
}

// Export the class for use in other modules
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = { AudioController };
} else {
    window.AudioController = AudioController;
} 