"""Los mensajes que llegan al navegador no deben revelar el servidor LLM ni credenciales.

Se comprueba con los valores reales del .env local (no se imprimen). Ejecutar: python3 -m unittest discover -s tests
"""
import unittest

import config as cfg


class OcultarSecretos(unittest.TestCase):
    def test_quita_token_url_y_host(self):
        token, url = cfg.get("OLLAMA_TOKEN"), cfg.get("OLLAMA_URL").rstrip("/")
        host = url.split("//")[-1].split("/")[0]
        texto = cfg.ocultar(f"fallo con {token} contra {url}/ruta y {host}")
        for valor in (token, url, host):
            self.assertNotIn(valor, texto)
        self.assertIn("[oculto]", texto)

    def test_deja_intacto_un_texto_sin_secretos(self):
        self.assertEqual(cfg.ocultar("HTTP Error 429: Too Many Requests"), "HTTP Error 429: Too Many Requests")

    def test_no_rompe_con_valores_no_texto(self):
        self.assertEqual(cfg.ocultar(None), "None")


if __name__ == "__main__":
    unittest.main()
