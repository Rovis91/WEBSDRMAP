"""
Test pour vérifier que le composant audio-control.js est correctement disponible
dans l'application Flask.
"""
import os
import unittest


class TestAudioControlComponent(unittest.TestCase):
    """Tests pour le composant Audio Control JS."""

    def test_audio_control_js_exists(self):
        """Vérifie que le fichier audio-control.js existe dans le bon répertoire."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'static', 'js', 'audio-control.js'
        )
        self.assertTrue(
            os.path.exists(js_path),
            f"Le fichier audio-control.js n'existe pas à l'emplacement {js_path}"
        )
    
    def test_index_html_includes_audio_control_js(self):
        """Vérifie que index.html inclut bien le script audio-control.js."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'templates', 'index.html'
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn(
            "audio-control.js",
            content,
            "Le fichier index.html ne référence pas audio-control.js"
        )
    
    def test_index_html_has_audio_elements(self):
        """Vérifie que index.html contient les éléments audio nécessaires."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'src', 'frontend', 'templates', 'index.html'
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_elements = [
            'audio-player',
            'audio-visualizer',
            'volume-control',
            'mute-button',
            'btn-record',
            'btn-save-audio'
        ]
        
        for element in required_elements:
            self.assertIn(
                element,
                content,
                f"Le fichier index.html ne contient pas l'élément '{element}'"
            )


if __name__ == '__main__':
    unittest.main() 