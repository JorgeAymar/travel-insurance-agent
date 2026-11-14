"""La revisión en lote del listado usa TODO el listado filtrado (no solo la página) y un máximo con valor inicial del .env.

Ejecutar: python3 -m unittest discover -s tests
"""
import json
import re
import unittest

import app
import config as cfg


class ListadoLote(unittest.TestCase):
    def setUp(self):
        self.cliente = app.app.test_client()

    def _ids(self, url):
        html = self.cliente.get(url).get_data(as_text=True)
        return html, json.loads(re.search(r'id="ids-filtrados">(.*?)</script>', html, re.S).group(1))

    def test_los_ids_son_todo_el_listado_aunque_solo_se_vea_una_pagina(self):
        html, ids = self._ids("/?n=10")
        total = len(self.cliente.get("/api/claims").get_json())
        self.assertEqual(len(ids), total)  # 100 ids con 10 filas en la página
        self.assertTrue(all({"id", "tipo"} <= set(x) for x in ids))
        self.assertGreater(len(ids), html.count('class="run-btn"'))

    def test_el_filtro_limita_los_ids_y_el_maximo_del_campo(self):
        html, ids = self._ids("/?tipo=Huelga")
        self.assertTrue(0 < len(ids) < 100)
        self.assertIn(f'max="{len(ids)}"', html)
        self.assertIn(f'value="{min(cfg.entero("ANALISIS_RECLAMACIONES_DEFECTO"), len(ids))}"', html)

    def test_el_resultado_va_en_la_misma_fila_de_la_reclamacion(self):
        html = self.cliente.get("/").get_data(as_text=True)
        for campo in ("Estado", "¿Aplica devolución?", "Duración de la revisión", "Fecha de ejecución", "Comentarios de la ejecución"):
            self.assertIn(f"<th>{campo}</th>", html)
        self.assertIn('class="r-com"', html)
        self.assertNotIn('id="resultado-ejecucion"', html)
        self.assertNotIn('id="res-tabla"', html)

    def test_sin_resultados_el_listado_no_rompe(self):
        html, ids = self._ids("/?q=zzzzzz")
        self.assertEqual(ids, [])
        self.assertIn('id="max-rec"', html)


if __name__ == "__main__":
    unittest.main()
