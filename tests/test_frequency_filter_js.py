"""
Test pour vérifier que le composant frequency-filter.js est correctement disponible
dans l'application Flask.
"""
import os
import unittest


class TestFrequencyFilterComponent(unittest.TestCase):
    """Tests pour le composant Frequency Filter JS."""

    def test_frequency_filter_js_exists(self):
        """Vérifie que le fichier frequency-filter.js existe dans le bon répertoire."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'static', 'js', 'frequency-filter.js'
        )
        self.assertTrue(
            os.path.exists(js_path),
            f"Le fichier frequency-filter.js n'existe pas à l'emplacement {js_path}"
        )
    
    def test_index_html_includes_frequency_filter_js(self):
        """Vérifie que index.html inclut bien le script frequency-filter.js."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'templates', 'index.html'
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn(
            "frequency-filter.js",
            content,
            "Le fichier index.html ne référence pas frequency-filter.js"
        )
    
    def test_index_html_has_frequency_filter_elements(self):
        """Vérifie que index.html contient les éléments de filtre de fréquence nécessaires."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'templates', 'index.html'
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_elements = [
            'frequency-favorites',
            'frequency-bands',
            'frequency',
            'frequency-unit'
        ]
        
        for element in required_elements:
            self.assertIn(
                element,
                content,
                f"Le fichier index.html ne contient pas l'élément '{element}'"
            )


if __name__ == '__main__':
    unittest.main() 