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
- Comparar modelos y arquitecturas: `python bench.py` y la página `/estadisticas`.
