#!/usr/bin/env bash
# CodinX installer — aman untuk Termux maupun Linux.
set -Eeuo pipefail

command -v python3 >/dev/null 2>&1 || { echo "Python 3 tidak ditemukan. Install dengan: pkg install python"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "CodinX membutuhkan Python >= 3.9"; exit 1; }

SRC="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${CODINX_INSTALL_DIR:-}" ]; then
  DEST="$CODINX_INSTALL_DIR"
elif [ -n "${PREFIX:-}" ]; then
  DEST="$PREFIX/share/codinx"
elif [ "$(id -u)" = "0" ]; then
  DEST=/opt/codinx
else
  DEST="$HOME/.local/share/codinx"
fi

if [ -n "${CODINX_BIN_DIR:-}" ]; then
  BIN_DIR="$CODINX_BIN_DIR"
elif [ -n "${PREFIX:-}" ]; then
  BIN_DIR="$PREFIX/bin"
elif [ "$(id -u)" = "0" ]; then
  BIN_DIR=/usr/local/bin
else
  BIN_DIR="$HOME/.local/bin"
fi

# Fail early rather than installing an incomplete source tree.
for f in cx/__init__.py cx/api.py cx/wire.py cx/cli.py bin/codinx; do
  if [ ! -f "$SRC/$f" ]; then
    echo "ERROR: file sumber tidak ditemukan: $SRC/$f"
    echo "Ekstrak ulang ZIP CodinX, lalu jalankan install.sh dari folder CodinX."
    exit 1
  fi
done

mkdir -p "$(dirname "$DEST")" "$BIN_DIR"
STAGE="${DEST}.staging.$$"
BACKUP="${DEST}.backup.$$"
cleanup() {
  rc=$?
  rm -rf "$STAGE"
  if [ "$rc" -ne 0 ] && [ ! -e "$DEST" ] && [ -e "$BACKUP" ]; then
    mv "$BACKUP" "$DEST" || true
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

if [ "$SRC" != "$DEST" ]; then
  rm -rf "$STAGE"
  mkdir -p "$STAGE"
  cp -a "$SRC"/. "$STAGE"/
  # Verify the staged package can actually be imported before replacing the old install.
  for f in cx/__init__.py cx/api.py cx/wire.py cx/cli.py bin/codinx; do
    [ -f "$STAGE/$f" ] || { echo "ERROR: hasil salin tidak lengkap: $f"; exit 1; }
  done
  PYTHONPATH="$STAGE" python3 -c 'import cx.api, cx.cli; print("Pemeriksaan package: OK")'
  if [ -e "$DEST" ]; then
    mv "$DEST" "$BACKUP"
  fi
  mv "$STAGE" "$DEST"
else
  PYTHONPATH="$DEST" python3 -c 'import cx.api, cx.cli; print("Pemeriksaan package: OK")'
fi

chmod +x "$DEST/bin/codinx"
[ ! -f "$DEST/.env" ] || chmod 600 "$DEST/.env"
[ ! -f "$DEST/api.py" ] || chmod 600 "$DEST/api.py"
SH="$(command -v sh)"
printf '#!%s\nexec python3 "%s/bin/codinx" "$@"\n' "$SH" "$DEST" > "$BIN_DIR/codinx"
chmod +x "$BIN_DIR/codinx"

echo "✓ CodinX terpasang dan modul API sudah diverifikasi: $DEST"
echo "Jalankan: codinx"
case ":${PATH}:" in *":$BIN_DIR:"*) ;; *) echo "Tambahkan ke PATH: export PATH=\"$BIN_DIR:\$PATH\"" ;; esac

# Keep the previous install as a rollback copy until the new install is confirmed.
if [ -e "$BACKUP" ]; then
  echo "Backup instalasi sebelumnya: $BACKUP"
fi
trap - EXIT INT TERM
