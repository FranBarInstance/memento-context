#!/usr/bin/env bash
# See licence: https://github.com/FranBarInstance/memento-context
# Memento Context Installation Script for Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/FranBarInstance/memento-context/main/scripts/install.sh | bash

set -e

REPO_URL="https://github.com/FranBarInstance/memento-context.git"
INSTALL_DIR="${HOME}/.memento-context-src"

echo "======================================"
echo "    Installing Memento Context Server      "
echo "======================================"

# 1. Ensure git is installed
if ! command -v git &> /dev/null; then
    echo "Error: git is required but not installed."
    exit 1
fi

# 2. Clone or update repository in a hidden local folder
if [ ! -d "$INSTALL_DIR" ]; then
    echo "=> Cloning repository..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
else
    echo "=> Updating existing repository..."
    cd "$INSTALL_DIR"
    git pull --quiet
fi

cd "$INSTALL_DIR"

# 3. Install via Pipx (recommended) or Pip
if command -v pipx &> /dev/null; then
    echo "=> Installing via pipx (Isolated Environment)..."
    pipx install .
elif command -v pip &> /dev/null || command -v pip3 &> /dev/null; then
    echo "=> Warning: pipx not found. Falling back to standard pip..."
    if command -v pip3 &> /dev/null; then
        pip3 install --user .
    else
        pip install --user .
    fi
else
    echo "Error: Python pip or pipx is required to install Memento Context."
    exit 1
fi

echo "======================================"
echo "✅ Installation Complete!            "
echo "   You can now use the command:       "
echo "   memento-context                         "
echo "======================================"
