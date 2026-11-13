"""Regresión: una petición de revisión mal formada no debe arrancar ninguna revisión.

Regression: ISSUE-003 — un POST con JSON roto o sin arquitectura arrancaba una revisión completa con el LLM
(15 llamadas) usando los valores por defecto, y ocupaba un hueco del cupo de revisiones simultáneas.
Found by /qa on 2026-11-13
Ejecutar: python3 -m unittest discover -s tests
"""
import json
import unittest
from unittest import mock

import app


def _resultado_falso():
    return {"veredicto": "Aprobado", "motivo": "", "comentario": None, "importeAPagar": 0, "lineas": [],
            "stats": {"arquitectura": "reglas"}, "agente": {}, "nota": None}


class RevisionPeticionMalFormada(unittest.TestCase):
    def setUp(self):
        self.cliente = app.app.test_client()
        self.llamadas = []
        parche = mock.patch.object(app.agent, "revisar", side_effect=self._revisar)  # sin LLM: solo se cuenta
        parche.start()
        self.addCleanup(parche.stop)

    def _revisar(self, *args, **kwargs):
        self.llamadas.append(kwargs)
        return _resultado_falso()

    def _post(self, cuerpo, tipo="application/json"):
        resp = self.cliente.post("/reclamaciones/CLM-0003/revision", data=cuerpo, content_type=tipo)
        resp.get_data()  # consume el flujo: así el hilo de trabajo termina antes de comprobar
        return resp

    def test_json_roto_devuelve_400_y_no_revisa(self):
        resp = self._post("{roto")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.llamadas, [])

    def test_sin_arquitectura_devuelve_400_y_no_revisa(self):
        resp = self._post("{}")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.llamadas, [])

    def test_arquitectura_desconocida_devuelve_400_y_no_revisa(self):
        resp = self._post(json.dumps({"arquitectura": "x"}))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.llamadas, [])

    def test_peticion_valida_sigue_funcionando(self):  # camino feliz adyacente
        resp = self._post(json.dumps({"arquitectura": "langgraph", "motor": "reglas"}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.llamadas), 1)
        self.assertEqual(json.loads(resp.get_data(as_text=True).splitlines()[-1])["tipo"], "fin")


if __name__ == "__main__":
    unittest.main()
