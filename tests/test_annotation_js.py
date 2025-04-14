import os
import unittest
from bs4 import BeautifulSoup


class TestAnnotationComponent(unittest.TestCase):
    """Test suite for the annotation.js component."""
    
    def test_annotation_js_exists(self):
        """Verify that the annotation.js file exists in the static/js directory."""
        js_file_path = os.path.join('src', 'frontend', 'static', 'js', 'annotation.js')
        self.assertTrue(os.path.exists(js_file_path), f"The file {js_file_path} does not exist")
    
    def test_index_html_includes_annotation_js(self):
        """Verify that index.html includes a reference to annotation.js."""
        # Path to the index.html file
        index_file_path = os.path.join('src', 'frontend', 'templates', 'index.html')
        self.assertTrue(os.path.exists(index_file_path), f"The file {index_file_path} does not exist")
        
        # Read the content of the file
        with open(index_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all script tags
        script_tags = soup.find_all('script')
        
        # Check if any script tag references annotation.js
        annotation_script_found = any('annotation.js' in script.get('src', '') for script in script_tags)
        self.assertTrue(annotation_script_found, "The index.html file does not include a reference to annotation.js")
    
    def test_index_html_has_annotation_elements(self):
        """Verify that index.html contains the necessary annotation elements."""
        # Path to the index.html file
        index_file_path = os.path.join('src', 'frontend', 'templates', 'index.html')
        self.assertTrue(os.path.exists(index_file_path), f"The file {index_file_path} does not exist")
        
        # Read the content of the file
        with open(index_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for the annotation elements
        self.assertIsNotNone(soup.find(id="annotation-view"), "The annotation-view element is missing")
        self.assertIsNotNone(soup.find(id="annotations-list"), "The annotations-list element is missing")
        self.assertIsNotNone(soup.find(id="annotation-form"), "The annotation-form element is missing")
        self.assertIsNotNone(soup.find(id="tab-annotation"), "The annotation tab button is missing")


if __name__ == '__main__':
    unittest.main() 