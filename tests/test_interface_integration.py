import unittest
import os
import time
import json
import platform
import sys
from flask_testing import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.frontend.app import app, socketio


@unittest.skipIf(platform.system() == 'Windows', "Skipping LiveServerTestCase tests on Windows due to multiprocessing issues")
class TestInterfaceIntegration(LiveServerTestCase):
    """Integration tests for the SDR Triangulation tool interface."""
    
    def create_app(self):
        """Create and configure the Flask app for testing."""
        app.config['TESTING'] = True
        # Use a random port
        app.config['LIVESERVER_PORT'] = 0
        return app
    
    def setUp(self):
        """Set up the browser for testing."""
        # Configure Chrome options for headless testing
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Create a new Chrome webdriver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        
        # Add some test data to the app
        from src.frontend.app import app_data
        app_data['receivers'] = {
            'test_receiver_1': {
                'name': 'Test Receiver 1',
                'location': {'latitude': 48.8566, 'longitude': 2.3522},
                'frequency': 7100000,
                'mode': 'AM',
                'status': 'online',
                'selected': True
            },
            'test_receiver_2': {
                'name': 'Test Receiver 2',
                'location': {'latitude': 45.7640, 'longitude': 4.8357},
                'frequency': 14200000,
                'mode': 'USB',
                'status': 'online',
                'selected': False
            }
        }
        
        app_data['signals'] = [
            {
                'id': 'signal_1',
                'frequency': 7100000,
                'mode': 'AM',
                'rssi': -75,
                'location': {'latitude': 47.3215, 'longitude': 5.0415},
                'timestamp': time.time(),
                'receiver': 'test_receiver_1'
            }
        ]
    
    def tearDown(self):
        """Close the browser after testing."""
        self.driver.quit()
        
        # Properly terminate the server process
        if hasattr(self, '_process') and self._process is not None:
            try:
                self._process.terminate()
            except AttributeError:
                pass
            self._process = None

        # Clean up SocketIO if needed
        if hasattr(socketio, 'server'):
            socketio.server.disconnect()
    
    def test_interface_loads(self):
        """Test that the interface loads properly."""
        # Navigate to the homepage
        self.driver.get(self.get_server_url())
        
        # Check that the title is correct
        self.assertEqual('SDR Triangulation Tool', self.driver.title)
        
        # Check that the main elements are present
        self.assertTrue(self.driver.find_element(By.ID, 'map').is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, 'receivers-list').is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, 'spectrogram').is_displayed())
    
    def test_tab_navigation(self):
        """Test that tab navigation works."""
        self.driver.get(self.get_server_url())
        
        # Get all tabs
        tabs = self.driver.find_elements(By.CLASS_NAME, 'tab-btn')
        
        # Check that we have at least 3 tabs
        self.assertGreaterEqual(len(tabs), 3)
        
        # Test clicking each tab
        for tab in tabs:
            tab_id = tab.get_attribute('id')
            pane_id = tab_id.replace('tab-', '') + '-view'
            
            # Click the tab
            tab.click()
            
            # Wait for the tab to be active
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, pane_id))
            )
            
            # Check that the correct pane is active
            pane = self.driver.find_element(By.ID, pane_id)
            self.assertTrue('active' in pane.get_attribute('class'))
    
    def test_receiver_selection(self):
        """Test selecting a receiver."""
        self.driver.get(self.get_server_url())
        
        # Wait for receivers to be populated
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'receiver-item'))
        )
        
        # Get the receivers
        receivers = self.driver.find_elements(By.CLASS_NAME, 'receiver-item')
        
        # Check that we have at least one receiver
        self.assertGreaterEqual(len(receivers), 1)
        
        # Select the first receiver
        first_receiver = receivers[0]
        checkbox = first_receiver.find_element(By.TAG_NAME, 'input')
        
        # Check current state
        initial_state = checkbox.is_selected()
        
        # Click the checkbox to change selection
        checkbox.click()
        
        # Check that the state has changed
        self.assertNotEqual(initial_state, checkbox.is_selected())
    
    def test_frequency_input(self):
        """Test setting a frequency."""
        self.driver.get(self.get_server_url())
        
        # Wait for frequency input to be available
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.ID, 'frequency'))
        )
        
        # Get the frequency input and unit select
        freq_input = self.driver.find_element(By.ID, 'frequency')
        unit_select = self.driver.find_element(By.ID, 'frequency-unit')
        
        # Set a test frequency (14.250 MHz)
        freq_input.clear()
        freq_input.send_keys('14.250')
        
        # Set the unit to MHz
        unit_select.click()
        self.driver.find_element(By.CSS_SELECTOR, 'option[value="1000000"]').click()
        
        # Trigger a change event by clicking elsewhere
        self.driver.find_element(By.TAG_NAME, 'body').click()
        
        # Verify the frequency is set (can't easily verify the socket event)
        self.assertEqual('14.250', freq_input.get_attribute('value'))
        self.assertEqual('1000000', unit_select.get_attribute('value'))
    
    def test_annotation_creation(self):
        """Test creating an annotation."""
        self.driver.get(self.get_server_url())
        
        # Switch to the annotation tab
        annotation_tab = self.driver.find_element(By.ID, 'tab-annotation')
        annotation_tab.click()
        
        # Wait for the annotation pane to become active
        WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'annotation-view'))
        )
        
        # Click the add annotation button
        add_button = self.driver.find_element(By.ID, 'btn-add-annotation')
        add_button.click()
        
        # Wait for the annotation form to appear
        WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'annotation-form'))
        )
        
        # Fill out the form
        title_input = self.driver.find_element(By.ID, 'annotation-title')
        title_input.send_keys('Test Annotation')
        
        notes_input = self.driver.find_element(By.ID, 'annotation-notes')
        notes_input.send_keys('This is a test annotation')
        
        freq_input = self.driver.find_element(By.ID, 'annotation-frequency')
        freq_input.send_keys('7.100')
        
        # Submit the form
        submit_button = self.driver.find_element(By.ID, 'btn-save-annotation')
        submit_button.click()
        
        # Wait for the form to disappear
        WebDriverWait(self.driver, 5).until(
            EC.invisibility_of_element_located((By.ID, 'annotation-form'))
        )
        
        # Check if the annotation was added to the list
        annotations_list = self.driver.find_element(By.ID, 'annotations-list')
        annotation_items = annotations_list.find_elements(By.CLASS_NAME, 'annotation-item')
        
        # This will fail if the annotation wasn't added
        self.assertGreaterEqual(len(annotation_items), 1)
        
        # Check the content of the first annotation
        first_annotation = annotation_items[0]
        self.assertIn('Test Annotation', first_annotation.text)


if __name__ == '__main__':
    unittest.main() 