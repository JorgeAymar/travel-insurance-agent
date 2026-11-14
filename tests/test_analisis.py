"""La página de análisis y la referencia: no guardan nada y la referencia es coherente.

Ejecutar: python3 -m unittest discover -s tests
"""
import os
import time
import unittest

import app
import config as cfg


class Analisis(unittest.TestCase):
    def setUp(self):
        self.cliente = app.app.test_client()

    def test_la_pagina_carga(self):
        resp = self.cliente.get("/analisis")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Ejecutar el análisis", resp.get_data(as_text=True))

    def test_el_campo_de_maximo_de_reclamaciones_arranca_con_el_valor_del_env(self):
        html = self.cliente.get("/analisis").get_data(as_text=True)
        total = len(self.cliente.get("/api/claims").get_json())
        por_defecto = max(1, min(cfg.entero("ANALISIS_RECLAMACIONES_DEFECTO"), total))
        self.assertIn('id="ana-n"', html)
        self.assertIn(f'max="{total}"', html)
        self.assertIn(f'value="{por_defecto}"', html)

    def test_referencia_tiene_veredicto_y_lineas_de_cada_reclamacion(self):
        antes = sorted(os.listdir(os.path.dirname(cfg.ruta("CLAIMS_FILE"))))
        t = time.time()
        datos = self.cliente.get("/api/referencia").get_json()
        self.assertLess(time.time() - t, 15)  # sin pausas: debe ser casi instantáneo
        self.assertEqual(len(datos), len(self.cliente.get("/api/claims").get_json()))
        for x in datos:
            self.assertIn(x["veredicto"], ("Aprobado", "Validar", "Rechazado"))
            self.assertTrue(x["lineas"])
            if x["veredicto"] == "Aprobado":
                self.assertIsNotNone(x["importe"])
        # nada se guarda: la carpeta de datos queda igual
        self.assertEqual(antes, sorted(os.listdir(os.path.dirname(cfg.ruta("CLAIMS_FILE")))))


if __name__ == "__main__":
    unittest.main()
