"""El Claude Agent SDK usa el mismo LLM de Ollama y no puede tocar credenciales de Claude ni salirse de los datos.

Estos tests no llaman a ningún modelo: comprueban las opciones con las que se lanzaría el agente.
Ejecutar: python3 -m unittest discover -s tests
"""
import asyncio
import json
import os
import tempfile
import unittest

import agent
import arq_claude_sdk as sdk
import config as cfg


class AislamientoDelSdk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.path.join(self.tmp.name, "datos")
        self.cfgdir = os.path.join(self.tmp.name, "config")
        os.makedirs(self.cwd)
        os.makedirs(self.cfgdir)
        self.rutas = sdk._copias_saneadas(self.cwd)
        self.op = sdk._opciones(cfg.get("OLLAMA_URL"), "token-de-prueba", "modelo-x", self.cwd, self.rutas.values(), self.cfgdir)

    def test_apunta_al_servidor_ollama_con_su_token_y_el_modelo_elegido(self):
        env = self.op.env
        self.assertEqual(env["ANTHROPIC_BASE_URL"], cfg.get("OLLAMA_URL"))
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "token-de-prueba")
        self.assertEqual(self.op.model, "modelo-x")
        for nombre in sdk._ENV_MODELOS:  # opus/sonnet/haiku/rápido: todo al mismo modelo
            self.assertEqual(env[nombre], "modelo-x", nombre)

    def test_no_hereda_credenciales_ni_proveedores_de_claude(self):
        for nombre in sdk._ENV_ANULADAS:
            self.assertEqual(self.op.env[nombre], "", nombre)
        self.assertEqual(self.op.env["CLAUDE_CONFIG_DIR"], self.cfgdir)  # sin sesión, ajustes ni plugins del usuario
        self.assertEqual(self.op.env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"], "1")
        self.assertEqual(self.op.setting_sources, [])

    def test_solo_herramientas_de_lectura(self):
        self.assertEqual(self.op.allowed_tools, ["Read", "Grep"])
        self.assertTrue({"Bash", "Write", "Edit", "WebFetch", "WebSearch"} <= set(self.op.disallowed_tools))

    def test_copias_sin_campos_de_resultado(self):
        reclamaciones = json.load(open(self.rutas["reclamaciones"], encoding="utf-8"))
        polizas = json.load(open(self.rutas["polizas"], encoding="utf-8"))
        self.assertTrue(reclamaciones)
        for campo in agent.CAMPOS_OCULTOS:
            self.assertNotIn(campo, reclamaciones[0], campo)
        self.assertNotIn("estado", polizas[0])

    def test_el_hook_solo_deja_leer_los_tres_archivos(self):
        hook = self.op.hooks["PreToolUse"][0].hooks[0]

        def decide(herramienta, **args):
            r = asyncio.run(hook({"tool_name": herramienta, "tool_input": args}, None, None))
            return (r.get("hookSpecificOutput") or {}).get("permissionDecision", "allow")

        self.assertEqual(decide("Read", file_path=self.rutas["reclamaciones"]), "allow")
        self.assertEqual(decide("Grep", pattern="CLM", path=self.rutas["polizas"]), "allow")
        self.assertEqual(decide("Read", file_path=os.path.join(self.cwd, "..", ".env")), "deny")
        self.assertEqual(decide("Grep", pattern="CLM"), "deny")  # sin ruta: buscaría en toda la carpeta
        self.assertEqual(decide("Bash", command="ls"), "deny")


if __name__ == "__main__":
    unittest.main()
