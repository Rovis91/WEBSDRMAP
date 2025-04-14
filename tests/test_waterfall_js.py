"""
Test pour vérifier que le composant waterfall.js est correctement disponible
dans l'application Flask.
"""
import os
import unittest


class TestWaterfallComponent(unittest.TestCase):
    """Tests pour le composant Waterfall JS."""

    def test_waterfall_js_exists(self):
        """Vérifie que le fichier waterfall.js existe dans le bon répertoire."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'static', 'js', 'waterfall.js'
        )
        self.assertTrue(
            os.path.exists(js_path),
            f"Le fichier waterfall.js n'existe pas à l'emplacement {js_path}"
        )
    
    def test_index_html_includes_waterfall_js(self):
        """Vérifie que index.html inclut bien le script waterfall.js."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'templates', 'index.html'
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn(
            "waterfall.js",
            content,
            "Le fichier index.html ne référence pas waterfall.js"
        )


if __name__ == '__main__':
    unittest.main() 