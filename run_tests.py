import sys
import os
import unittest

# Adiciona o diretório atual ao path para garantir que 'core' e 'ui' sejam encontrados
sys.path.append(os.getcwd())

class TestRefactoring(unittest.TestCase):
    
    def test_01_imports_core(self):
        """Testa se os módulos do Core são importáveis."""
        try:
            import core.pdf_ops
            import core.pdf_scanner
            import core.utils
            import config
        except ImportError as e:
            self.fail(f"Falha ao importar módulos do Core: {e}")

    def test_02_imports_ui(self):
        """Testa se os módulos de UI são importáveis."""
        try:
            import ui.components
            import ui.styles
            import ui.tabs.merge
            import ui.tabs.split
        except ImportError as e:
            self.fail(f"Falha ao importar módulos de UI: {e}")

    def test_03_utils_safe_slug(self):
        """Testa a função safe_slug do core.utils."""
        from core.utils import safe_slug
        self.assertEqual(safe_slug("Arquivo de Teste!"), "arquivo_de_teste")
        self.assertEqual(safe_slug("Ação & Reação"), "acao_reacao")

    def test_04_config_constants(self):
        """Testa se as constantes de configuração existem."""
        from config import DEFAULT_BRAND, LEGAL_KEYWORDS
        self.assertIn("name", DEFAULT_BRAND)
        self.assertIn("Petição Inicial", LEGAL_KEYWORDS)

if __name__ == '__main__':
    print("Iniciando testes de integridade da refatoração...")
    unittest.main(verbosity=2)
