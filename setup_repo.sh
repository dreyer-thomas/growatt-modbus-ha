#!/usr/bin/env bash
# Einmalig im Projektordner ausführen:
#   ./setup_repo.sh DEIN_GITHUB_NAME
# Trägt deinen GitHub-Namen in manifest.json und README ein, legt das lokale
# Git-Repository an, macht den ersten Commit und verknüpft es mit GitHub.
set -euo pipefail
USER_NAME="${1:?Bitte GitHub-Benutzernamen angeben: ./setup_repo.sh DEIN_NAME}"
REPO_NAME="${2:-growatt-modbus-ha}"
cd "$(dirname "$0")"

for f in custom_components/growatt_sph_local/manifest.json README.md; do
  if grep -q "GITHUB_USER" "$f"; then
    sed -i.bak "s/GITHUB_USER/${USER_NAME}/g; s#/growatt-modbus-ha#/${REPO_NAME}#g; s#repository=growatt-modbus-ha#repository=${REPO_NAME}#g" "$f"
    rm -f "$f.bak"
  fi
done

if [ ! -d .git ]; then
  git init -b main
fi
git add .
git commit -m "Growatt SPH (lokal) v0.1.0" || echo "(nichts zu committen)"
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "https://github.com/${USER_NAME}/${REPO_NAME}.git"
fi

cat <<EOF

Lokales Repository ist bereit.

Nächste Schritte:
  1. Auf github.com ein neues, ÖFFENTLICHES Repository "${REPO_NAME}" anlegen
     – ohne README, .gitignore oder Lizenz (ist alles schon da).
  2. git push -u origin main
  3. Version veröffentlichen, damit HACS sie anbietet:
     git tag v0.1.0 && git push origin v0.1.0
  4. In Home Assistant: HACS → ⋮ → Benutzerdefinierte Repositories →
     https://github.com/${USER_NAME}/${REPO_NAME}  (Kategorie: Integration)
EOF
