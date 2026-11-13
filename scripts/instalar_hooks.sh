#!/bin/sh
# Activa los hooks del repositorio (la configuración de git no se sube; cada clon debe ejecutar esto).
git config core.hooksPath .githooks && chmod +x .githooks/* scripts/*.py && echo "Hooks activados: pre-commit y pre-push validan datos privados."
