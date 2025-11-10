#!/bin/bash
# Install SKY130 PDK via open_pdks

set -e

echo "=========================================="
echo "SKY130 PDK Installation via open_pdks"
echo "=========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
which git > /dev/null || { echo "Error: git not found"; exit 1; }
which ngspice > /dev/null || { echo "Error: ngspice not found"; exit 1; }
which make > /dev/null || { echo "Error: make not found"; exit 1; }

# macOS: check for Xcode command line tools
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! xcode-select -p &> /dev/null; then
        echo "Installing Xcode command line tools..."
        xcode-select --install
        echo "Please complete Xcode tools installation and re-run this script"
        exit 1
    fi
fi

echo "✓ Prerequisites OK"
echo ""

# Clone open_pdks
WORK_DIR="/tmp/sky130_install_$$"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo "Cloning open_pdks repository..."
git clone --depth 1 https://github.com/RTimothyEdwards/open_pdks.git
cd open_pdks

echo "Configuring with SKY130 PDK enabled..."
./configure --enable-sky130-pdk --prefix=/usr/local

echo "Building (this may take 5-10 minutes)..."
make -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)

echo ""
echo "Installing PDK (requires sudo)..."
echo "You may be prompted for your password..."
sudo make install

# Verify installation
PDK_PATH="/usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice"
if [ -f "$PDK_PATH" ]; then
    echo ""
    echo "=========================================="
    echo "✓ Installation successful!"
    echo "=========================================="
    echo ""
    echo "PDK installed to: /usr/local/share/pdk/sky130A/"
    echo "Model library: $PDK_PATH"
    echo ""
    echo "Next steps:"
    echo "  1. Test the installation:"
    echo "     cd pdk/skywater130/models"
    echo "     ngspice -b test_sky130.sp"
    echo ""
    echo "  2. Generate Gm/ID tables:"
    echo "     cd ../gm_id_tables"
    echo "     python generate_gmid_tables_sky130.py"
    echo ""
else
    echo ""
    echo "⚠ Installation completed but model file not found at expected location"
    echo "Check: $PDK_PATH"
    exit 1
fi

# Cleanup
cd /
rm -rf "$WORK_DIR"

echo "Installation complete!"

