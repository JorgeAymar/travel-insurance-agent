# Portal de reclamaciones de seguros de viaje

App web en Flask que lista reclamaciones, pólizas y cláusulas leídas de JSON en disco, con un agente de
revisión que analiza cada caso línea por línea y emite un veredicto (Aprobado, Rechazado o Validar).
Todos los datos son ficticios.

```bash
pip install -r requirements.txt
cp .env.example .env          # rellena los valores
sh scripts/instalar_hooks.sh  # valida que no se suban datos privados
python3 app.py
```

- Toda la configuración está en el `.env` (nada va fijo en el código). `.env.example` es la plantilla.
- Documentación completa: [docs/DOCUMENTACION.md](docs/DOCUMENTACION.md).
- Los resultados del agente son solo virtuales: no se guardan y desaparecen al refrescar la página.
- Comparar modelos y arquitecturas: los 3 botones y el panel de comparación de la ficha, o `python bench.py`.
- Tests de regresión: `python3 -m unittest discover -s tests`.
