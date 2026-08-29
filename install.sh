#!/bin/sh

set -e

INSTALL_DIR="$HOME/.local/share/tua"
BIN_DIR="$HOME/.local/bin"

echo "Installing Tua..."

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Copy the entire project
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} \;

cp -R "$SOURCE_DIR"/. "$INSTALL_DIR"/

# Remove installer files from installation
rm -f "$INSTALL_DIR/install.sh"
rm -f "$INSTALL_DIR/install.ps1"

# Create executable launcher
cat > "$BIN_DIR/tua" <<'EOF'
#!/bin/sh

exec python3 "$HOME/.local/share/tua/tuac.py" "$@"
EOF

chmod +x "$BIN_DIR/tua"

# Add ~/.local/bin to PATH
add_path() {
    FILE="$1"

    if [ -f "$FILE" ]; then
        if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$FILE"; then
            printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$FILE"
        fi
    fi
}

add_path "$HOME/.profile"
add_path "$HOME/.bashrc"
add_path "$HOME/.zshrc"

# Make available in the current shell
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
esac

echo ""
echo "Tua installed successfully!"
echo ""
echo "Installation:"
echo "  $INSTALL_DIR"
echo ""
echo "Executable:"
echo "  $BIN_DIR/tua"
echo ""

if [ -f "$INSTALL_DIR/tuac.py" ]; then
    echo "[OK] tuac.py"
else
    echo "[MISSING] tuac.py"
fi

if [ -f "$INSTALL_DIR/tua/__init__.py" ]; then
    echo "[OK] tua package"
else
    echo "[MISSING] tua package"
fi

if [ -f "$INSTALL_DIR/tua/cli.py" ]; then
    echo "[OK] tua/cli.py"
else
    echo "[MISSING] tua/cli.py"
fi

echo ""
echo "Run:"
echo "  tua"