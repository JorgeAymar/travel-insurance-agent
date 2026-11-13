#!/usr/bin/env python3
"""Valida que lo que se sube a GitHub no lleve datos privados ni configuración fija en el código.

Modos:
  --staged   lo que está en el índice (lo usa el hook pre-commit)
  --push     los commits que se van a subir (lo usa el hook pre-push; lee el stdin de git)
  --todo     todos los archivos versionados (para ejecutarlo a mano)

Reglas (si alguna falla, la subida se bloquea):
  1. Archivos que nunca deben subirse (.env, resultados de ejecución, claves).
  2. Secretos: tokens, claves de API, claves privadas, cadenas hexadecimales largas.
  3. Los valores privados del .env local (tokens, URLs, nombre del usuario) no pueden aparecer en ningún archivo.
  4. En .env.example los valores privados deben estar vacíos.
  5. En el código: nada de URLs, IPs, rutas personales ni valores por defecto de os.environ (todo va al .env).
  6. Sin correos reales (solo @example.*) ni rutas del equipo (/Users/...).
  7. El autor y el committer de cada commit deben usar el correo «noreply» de GitHub (el correo personal queda
     visible públicamente en el historial).
Esta validación mira también TODOS los commits que se suben, no solo el último: un secreto añadido
y borrado después sigue estando en el historial.
"""
import os
import re
import subprocess
import sys

RAIZ = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or os.getcwd()

ARCHIVOS_PROHIBIDOS = [
    (re.compile(r"(^|/)\.env(\..+)?$"), "archivo de entorno con valores reales (solo .env.example se puede subir)"),
    (re.compile(r"(^|/)data/revisiones\.json$"), "resultados de ejecución del agente"),
    (re.compile(r"(^|/)data/corridas\.jsonl$"), "historial de corridas del agente"),
    (re.compile(r"\.(pem|key|p12|pfx)$|(^|/)id_(rsa|ed25519)"), "clave privada o certificado"),
]
PERMITIDOS = {".env.example"}

PATRONES_SECRETO = [
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}"), "cabecera Authorization con token"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "clave de API de Anthropic"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "token de GitHub"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "clave de acceso de AWS"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "token de Slack"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "clave privada"),
    (re.compile(r"\b[0-9a-fA-F]{40,}\b"), "cadena hexadecimal larga (parece un token)"),
]
EXT_CODIGO = (".py", ".html", ".js", ".sh")
PATRONES_CODIGO = [
    (re.compile(r"https?://"), "URL fija en el código (va en el .env)"),
    (re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b"), "dirección IP fija en el código (va en el .env)"),
    (re.compile(r"environ\.get\(\s*[^,()]+,|getenv\(\s*[^,()]+,"), "valor por defecto en os.environ.get (usa config.py y el .env)"),
    (re.compile(r"environ\[[^\]]+\](?!\s*=)"), "lectura directa de os.environ (usa config.py)"),
]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"@example\.(com|org|net)$", re.I)
RUTA_PERSONAL = re.compile(r"/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|[A-Z]:\\Users\\")
# Claves del .env cuyo valor es privado: tokens, claves, contraseñas y URLs de servidores.
CLAVE_PRIVADA = re.compile(r"(^|_)(TOKEN|API_KEY|KEY|SECRET|PASSWORD|PASSWD)$|_URL$", re.I)
# Claves cuyo valor es un dato personal: no pueden aparecer en ningún archivo, aunque en .env.example lleven un valor de ejemplo.
CLAVES_PERSONALES = re.compile(r"^APP_USER_NAME$")
CORREO_PERMITIDO = re.compile(r"@users\.noreply\.github\.com$|@example\.(com|org|net)$", re.I)  # correos de autor válidos
EXENTOS_CODIGO = {"config.py"}  # el único sitio donde se lee os.environ
EXENTOS_VALIDADOR = {"scripts/validar_subida.py"}  # contiene ejemplos de rutas y patrones en su propio texto


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=RAIZ, errors="replace").stdout


def valores_privados_locales():
    """Valores del .env local que no pueden aparecer en ningún archivo que se suba."""
    ruta = os.path.join(RAIZ, ".env")
    valores = {}
    if not os.path.exists(ruta):
        return valores
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if "=" not in linea or linea.startswith("#"):
            continue
        k, v = linea.split("=", 1)
        v = re.sub(r"\s+#.*$", "", v).strip()
        if (CLAVE_PRIVADA.search(k.strip()) or CLAVES_PERSONALES.search(k.strip())) and len(v) >= 6:
            valores[k.strip()] = v
    return valores


def revisar_linea(archivo, n, texto, privados, problemas):
    base = archivo
    for valor_k, valor in privados.items():
        if valor in texto and archivo not in PERMITIDOS | {".env"}:
            problemas.append((archivo, n, f"contiene el valor privado de {valor_k} (del .env local)"))
    for rx, que in PATRONES_SECRETO:
        if rx.search(texto):
            problemas.append((archivo, n, f"posible secreto: {que}"))
    for m in EMAIL.finditer(texto):
        if not EMAIL_OK.search(m.group(0)):
            problemas.append((archivo, n, f"correo que no es de ejemplo: {m.group(0)}"))
    if archivo in EXENTOS_VALIDADOR:
        return
    if RUTA_PERSONAL.search(texto):
        problemas.append((archivo, n, "ruta del equipo (/Users/...)"))
    if archivo.endswith(EXT_CODIGO) and archivo not in EXENTOS_CODIGO:
        for rx, que in PATRONES_CODIGO:
            if rx.search(texto):
                problemas.append((archivo, n, que))
    if base == ".env.example":
        m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*([^#\s][^#]*)", texto)
        if m and CLAVE_PRIVADA.search(m.group(1)):
            problemas.append((archivo, n, f"{m.group(1)} debe estar vacío en .env.example"))


def revisar_ruta(archivo, problemas):
    if os.path.basename(archivo) in PERMITIDOS:
        return
    for rx, que in ARCHIVOS_PROHIBIDOS:
        if rx.search(archivo):
            problemas.append((archivo, 0, que))


def lineas_añadidas(diff):
    """Recorre un diff unificado y devuelve (archivo, nº de línea, texto) de las líneas añadidas."""
    archivo, n = None, 0
    for l in diff.splitlines():
        if l.startswith("+++ "):
            archivo = None if l.endswith("/dev/null") else l[6:]
        elif l.startswith("@@"):
            m = re.search(r"\+(\d+)", l)
            n = int(m.group(1)) - 1 if m else 0
        elif l.startswith("+") and archivo:
            n += 1
            yield archivo, n, l[1:]
        elif not l.startswith("-"):
            n += 1


def revisar_autor(etiqueta, correo, problemas):
    if correo and not CORREO_PERMITIDO.search(correo):
        problemas.append((etiqueta, 0, "el correo del autor es personal y quedaría público: usa el correo noreply de GitHub "
                                       "(git config user.email <id>+<usuario>@users.noreply.github.com)"))


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "--todo"
    privados, problemas = valores_privados_locales(), []
    if modo != "--push":  # en commit y en la revisión manual se mira la identidad configurada
        revisar_autor("git config user.email", git("config", "user.email").strip(), problemas)

    if modo == "--staged":
        for a in git("diff", "--cached", "--name-only", "--diff-filter=AM").split():
            revisar_ruta(a, problemas)
        for a, n, t in lineas_añadidas(git("diff", "--cached", "-U0", "--no-color")):
            revisar_linea(a, n, t, privados, problemas)
    elif modo == "--push":
        commits = set()
        for linea in sys.stdin.read().splitlines():
            partes = linea.split()
            if len(partes) < 4 or set(partes[1]) == {"0"}:
                continue  # borrado de rama
            local, remoto = partes[1], partes[3]
            rango = [local] if set(remoto) == {"0"} else [f"{remoto}..{local}"]
            if set(remoto) == {"0"}:
                rango += ["--not", "--remotes"]
            commits |= set(git("rev-list", *rango).split())
        for c in sorted(commits):
            ae, ce = (git("log", "-1", "--format=%ae %ce", c).split() + ["", ""])[:2]
            revisar_autor(f"commit {c[:7]} (autor)", ae, problemas)
            revisar_autor(f"commit {c[:7]} (committer)", ce, problemas)
            for a in git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "--diff-filter=AM", c).split():
                revisar_ruta(a, problemas)
            for a, n, t in lineas_añadidas(git("show", "--format=", "-U0", "--no-color", c)):
                revisar_linea(a, n, t, privados, problemas)
        print(f"Validando {len(commits)} commit(s) que se van a subir…")
    else:  # --todo
        for a in git("ls-files").split("\n"):
            if not a:
                continue
            revisar_ruta(a, problemas)
            try:
                with open(os.path.join(RAIZ, a), encoding="utf-8") as f:
                    for n, t in enumerate(f, 1):
                        revisar_linea(a, n, t.rstrip("\n"), privados, problemas)
            except (UnicodeDecodeError, FileNotFoundError):
                continue  # binarios (p. ej. el PDF)

    # sin duplicados, en orden
    vistos, unicos = set(), []
    for p in problemas:
        if p not in vistos:
            vistos.add(p)
            unicos.append(p)
    if unicos:
        print("\n✗ SUBIDA BLOQUEADA: se encontraron datos privados o configuración fija:\n")
        for a, n, que in unicos:
            print(f"  {a}{':' + str(n) if n else ''}  →  {que}")
        print("\nQuita el dato, muévelo al .env (y deja .env.example sin valores privados) y vuelve a intentarlo.")
        print("Si el dato ya estaba en un commit anterior, hay que reescribir el historial antes de subir.")
        return 1
    print("✓ Validación de subida correcta: sin datos privados ni configuración fija.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
