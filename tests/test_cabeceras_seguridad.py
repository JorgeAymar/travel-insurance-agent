"""La app responde con cabeceras de seguridad. Ejecutar: python3 -m unittest discover -s tests"""
import unittest

import app


class Cabeceras(unittest.TestCase):
    def test_todas_las_respuestas_llevan_cabeceras_defensivas(self):
        for ruta in ("/", "/polizas", "/analisis", "/api/claims"):
            h = app.app.test_client().get(ruta).headers
            self.assertEqual(h["X-Content-Type-Options"], "nosniff", ruta)
            self.assertEqual(h["X-Frame-Options"], "DENY", ruta)
            self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"], ruta)


if __name__ == "__main__":
    unittest.main()
