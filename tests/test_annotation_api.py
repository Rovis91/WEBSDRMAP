import unittest
import json
from unittest.mock import patch, MagicMock
from src.frontend.app import app, socketio


class TestAnnotationAPI(unittest.TestCase):
    """Test suite for annotation API endpoints."""
    
    def setUp(self):
        """Set up test client and configure the app for testing."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create a test SocketIO client
        self.socketio_test_client = socketio.test_client(app)
        
        # Reset app_data for each test
        from src.frontend.app import app_data
        if 'annotations' in app_data:
            app_data['annotations'] = {}
            
    def test_save_annotation(self):
        """Test saving an annotation via SocketIO."""
        # Test data
        test_annotation = {
            'title': 'Test Annotation',
            'notes': 'This is a test annotation',
            'frequency': 14250000,  # 14.25 MHz
            'mode': 'USB',
            'tags': ['test', 'api'],
            'latitude': 48.8566,
            'longitude': 2.3522
        }
        
        # Emit event and get response
        self.socketio_test_client.emit('save_annotation', test_annotation)
        response = self.socketio_test_client.get_received()
        
        # Check if we have annotation_updated event
        has_update_event = False
        for event in response:
            if event['name'] == 'annotation_updated':
                has_update_event = False
                saved_annotation = event['args'][0]
                self.assertEqual(saved_annotation['title'], test_annotation['title'])
                self.assertEqual(saved_annotation['frequency'], test_annotation['frequency'])
                self.assertEqual(saved_annotation['mode'], test_annotation['mode'])
                
        # Get all annotations to verify it was saved
        self.socketio_test_client.emit('get_annotations')
        response = self.socketio_test_client.get_received()
        
        for event in response:
            if event['name'] == 'get_annotations':
                annotations = event['args'][0]['annotations']
                self.assertEqual(len(annotations), 1)
                self.assertEqual(annotations[0]['title'], test_annotation['title'])
    
    def test_get_annotations(self):
        """Test retrieving annotations via SocketIO."""
        # Add a test annotation first
        test_annotation = {
            'title': 'Test Annotation',
            'frequency': 14250000
        }
        
        self.socketio_test_client.emit('save_annotation', test_annotation)
        
        # Get annotations
        self.socketio_test_client.emit('get_annotations')
        response = self.socketio_test_client.get_received()
        
        # Check if response includes our test annotation
        annotations_response = None
        for event in response:
            if event['name'] == 'get_annotations':
                annotations_response = event['args'][0]
                break
        
        self.assertIsNotNone(annotations_response)
        self.assertEqual(annotations_response['status'], 'success')
        self.assertEqual(len(annotations_response['annotations']), 1)
        self.assertEqual(annotations_response['annotations'][0]['title'], 'Test Annotation')
    
    def test_delete_annotation(self):
        """Test deleting an annotation via SocketIO."""
        # First save an annotation
        test_annotation = {
            'title': 'Annotation to Delete',
            'frequency': 7100000
        }
        
        self.socketio_test_client.emit('save_annotation', test_annotation)
        response = self.socketio_test_client.get_received()
        
        # Get the ID of the saved annotation
        annotation_id = None
        for event in response:
            if event['name'] == 'annotation_updated':
                annotation_id = event['args'][0]['id']
                break
        
        self.assertIsNotNone(annotation_id)
        
        # Delete the annotation
        self.socketio_test_client.emit('delete_annotation', {'id': annotation_id})
        
        # Verify it was deleted
        self.socketio_test_client.emit('get_annotations')
        response = self.socketio_test_client.get_received()
        
        for event in response:
            if event['name'] == 'get_annotations':
                annotations = event['args'][0]['annotations']
                self.assertEqual(len(annotations), 0)


if __name__ == '__main__':
    unittest.main() 