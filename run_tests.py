import unittest
import sys
import os

# Adiciona o diretório atual ao path para importar modulos locais
sys.path.append(os.getcwd())

class TestImports(unittest.TestCase):
    def test_imports_core(self):
        try:
            import core.pdf_ops
            import core.pdf_scanner
            import core.utils
            import core.bates
            import core.diff
            import core.redact
        except ImportError as e:
            self.fail(f"Falha ao importar core modules: {e}")

    def test_imports_ui(self):
        try:
            import config
            import ui.components
            import ui.styles
            import ui.tabs.merge
            import ui.tabs.split
            import ui.tabs.visual
            import ui.tabs.remove
            import ui.tabs.extract
            import ui.tabs.legal
            import ui.tabs.optimize
            import ui.tabs.bates
            import ui.tabs.converter
            import ui.tabs.redact
            import ui.tabs.diff
        except ImportError as e:
            self.fail(f"Falha ao importar ui modules: {e}")

    def test_core_functions_exist(self):
        import core.pdf_ops
        import core.bates
        self.assertTrue(hasattr(core.pdf_ops, 'merge_pdfs'))
        self.assertTrue(hasattr(core.pdf_ops, 'images_to_pdf'))
        self.assertTrue(hasattr(core.pdf_ops, 'rotate_pages'))
        self.assertTrue(hasattr(core.bates, 'apply_bates_stamping'))

if __name__ == '__main__':
    unittest.main()
