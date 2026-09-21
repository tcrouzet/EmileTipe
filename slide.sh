#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "Erreur : npm est requis pour générer les slides." >&2
  exit 1
fi

if [ ! -x node_modules/.bin/marp ]; then
  echo "Installation de Marp CLI…"
  npm ci
fi

echo "Génération de la présentation HTML…"
npm run slides:build

echo "Génération du PDF…"
npm run slides:pdf

echo "Génération du PowerPoint…"
npm run slides:pptx

echo
echo "Présentation générée :"
echo "  slides/presentation.html"
echo "  slides/presentation.pdf"
echo "  slides/presentation.pptx"
