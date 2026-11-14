"""Etapa 1 de todos los agentes: si falta información no se analiza ni se llama al LLM; el caso queda en «Validar».

Ejecutar: python3 -m unittest discover -s tests
"""
import copy
import json
import unittest

import agent
import config as cfg


def _datos():
    claim = json.load(open(cfg.ruta("CLAIMS_FILE"), encoding="utf-8"))[0]
    pols = json.load(open(cfg.ruta("POLICIES_FILE"), encoding="utf-8"))
    pol = next(p for p in pols if p["numero"] == claim["numeroPoliza"])
    clauses = {c["codigo"]: c for c in json.load(open(cfg.ruta("CLAUSES_FILE"), encoding="utf-8"))}
    return claim, pol, clauses


class DatosSuficientes(unittest.TestCase):
    def test_con_datos_completos_pasa_la_etapa_y_se_analiza(self):
        claim, pol, clauses = _datos()
        self.assertEqual(agent.verificar_datos(claim, pol, clauses), [])
        r = agent.revisar(claim, pol, clauses, motor="reglas", pausa=0)
        self.assertEqual(r["lineas"][0]["id"], "datos")
        self.assertEqual(r["lineas"][0]["estado"], "cumple")
        self.assertGreater(len(r["lineas"]), 1)

    def test_sin_poliza_o_sin_calculo_el_agente_se_detiene_y_pide_validar(self):
        claim, pol, clauses = _datos()
        quebrada = copy.deepcopy(claim)
        del quebrada["calculo"]
        for arq in agent.ARQUITECTURAS:  # cada tecnología hace la comprobación al principio
            for c, p in ((claim, None), (quebrada, pol)):
                r = agent.revisar(c, p, clauses, motor="ollama", arquitectura=arq, pausa=0)
                self.assertEqual(r["veredicto"], "Validar", arq)
                self.assertEqual(r["stats"]["llamadas"], 0, arq)  # ni una consulta al LLM
                self.assertEqual([l["id"] for l in r["lineas"]], ["datos"])
                self.assertIn("falta información", r["comentario"])


if __name__ == "__main__":
    unittest.main()
