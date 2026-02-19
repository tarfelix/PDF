import fitz
import unittest
import os
import sys

# Adiciona root ao path
sys.path.append(os.getcwd())

from core.redact import redact_text_matches

class TestRedactRegex(unittest.TestCase):
    def test_redact_patterns(self):
        doc = fitz.open()
        page = doc.new_page()
        # Texto com CPF, CNPJ e Email
        text = "Dados: CPF: 123.456.789-00, CNPJ: 12.345.678/0001-90, Email: teste@exemplo.com"
        page.insert_text((50, 50), text)
        pdf_bytes = doc.tobytes()
        
        # 1. Testar CPF
        _, count = redact_text_matches(pdf_bytes, [], built_in_patterns=['cpf'])
        self.assertEqual(count, 1, "Deve encontrar 1 CPF")
        
        # 2. Testar CNPJ
        _, count = redact_text_matches(pdf_bytes, [], built_in_patterns=['cnpj'])
        self.assertEqual(count, 1, "Deve encontrar 1 CNPJ")
        
        # 3. Testar Email
        _, count = redact_text_matches(pdf_bytes, [], built_in_patterns=['email'])
        self.assertEqual(count, 1, "Deve encontrar 1 Email")
        
        # 4. Testar Múltiplos
        _, count = redact_text_matches(pdf_bytes, [], built_in_patterns=['cpf', 'email'])
        self.assertEqual(count, 2, "Deve encontrar 2 padrões (CPF + Email)")

if __name__ == '__main__':
    unittest.main()
