"""Configuración centralizada. TODO valor variable viene del .env; el código no tiene valores por defecto.

Si falta una variable obligatoria, la app no arranca y dice cuáles faltan (ver .env.example).
"""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # las variables ya definidas en el entorno tienen prioridad


class ConfigError(RuntimeError):
    pass


# Siempre obligatorias (aunque se usen solo en parte de la app).
OBLIGATORIAS = (
    "APP_NAME", "APP_TAGLINE", "APP_USER_NAME", "APP_USER_ROLE",
    "HOST", "PORT", "FLASK_DEBUG", "PER_PAGE_OPTIONS",
    "CLAIMS_FILE", "POLICIES_FILE", "CLAUSES_FILE", "REVIEWS_FILE", "CORRIDAS_FILE",
    "AGENT_MODE", "AGENT_ARCH", "AGENT_STEP_DELAY", "IMPORTE_ALTO_VALIDAR", "PLAZO_RECLAMACION_DIAS",
)
# Solo para bench.py y generate_data.py (se comprueban al usarlos): BENCH_*, GEN_*
# Solo si el modo del agente las necesita.
POR_MODO = {
    "ollama": ("OLLAMA_URL", "OLLAMA_TOKEN", "OLLAMA_MODEL", "OLLAMA_TIMEOUT", "OLLAMA_MODELS_TIMEOUT",
               "OLLAMA_MODELS_CACHE_SEG", "OLLAMA_TEMPERATURE", "OLLAMA_REINTENTOS", "OLLAMA_REINTENTO_SEG", "AGENT_USER_AGENT"),
    "claude": ("ANTHROPIC_API_KEY", "AGENT_MODEL", "AGENT_MAX_TOKENS"),
}


def get(nombre):
    """Valor de una variable obligatoria."""
    v = os.environ.get(nombre)
    if v is None or not v.strip() or v.strip().startswith("#"):
        raise ConfigError(f"Falta la variable {nombre} en el .env (ver .env.example)")
    return v.strip()


def opcional(nombre):
    """Valor de una variable que puede estar vacía (devuelve '' si no existe)."""
    v = (os.environ.get(nombre) or "").strip()
    return "" if v.startswith("#") else v


def entero(nombre):
    try:
        return int(get(nombre))
    except ValueError:
        raise ConfigError(f"{nombre} debe ser un número entero") from None


def decimal(nombre):
    try:
        return float(get(nombre))
    except ValueError:
        raise ConfigError(f"{nombre} debe ser un número") from None


def booleano(nombre):
    return get(nombre).lower() in ("1", "true", "si", "sí", "yes")


def enteros(nombre):
    """Lista de enteros separados por coma (p. ej. 10,25,50)."""
    try:
        return tuple(int(x) for x in get(nombre).split(",") if x.strip())
    except ValueError:
        raise ConfigError(f"{nombre} debe ser una lista de enteros separados por coma") from None


def ruta(nombre):
    """Ruta de archivo: relativa a la carpeta del proyecto o absoluta."""
    return os.path.join(BASE_DIR, get(nombre))


def modo_agente():
    """Modo efectivo del agente: reglas | ollama | claude."""
    modo = get("AGENT_MODE").lower()
    if modo == "auto":
        if opcional("ANTHROPIC_API_KEY"):
            return "claude"
        return "ollama" if opcional("OLLAMA_URL") and opcional("OLLAMA_TOKEN") else "reglas"
    if modo not in ("reglas", "ollama", "claude"):
        raise ConfigError("AGENT_MODE debe ser reglas, ollama, claude o auto")
    return modo


def validar_entorno():
    """Comprueba al arrancar que están todas las variables necesarias; si no, lista las que faltan."""
    faltan = [n for n in OBLIGATORIAS if not opcional(n)]
    if not faltan:
        faltan += [n for n in POR_MODO.get(modo_agente(), ()) if not opcional(n)]
    if faltan:
        raise ConfigError("Faltan variables en el .env: " + ", ".join(faltan) + ". Copia .env.example a .env y rellénalas.")
