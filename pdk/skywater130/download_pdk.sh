#!/bin/bash
# Download SkyWater 130nm PDK SPICE models

set -e

echo "Downloading SkyWater 130nm PDK SPICE models..."

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Clone the PDK repository (shallow clone for speed)
echo "Cloning PDK repository..."
git clone --depth 1 https://github.com/google/skywater-pdk.git

# Extract just the SPICE models we need
echo "Extracting SPICE models..."
MODELS_SRC="skywater-pdk/libraries/sky130_fd_pr/latest/models"
DEST_DIR="$(dirname "$0")/models"

# Copy NMOS and PMOS models
cp "$MODELS_SRC/sky130.lib.spice" "$DEST_DIR/"

# Create simplified model includes
cat > "$DEST_DIR/nfet_01v8.pm3.spice" << 'EOF'
* NMOS 1.8V device models for SkyWater 130nm
.lib sky130.lib.spice tt
.include sky130.lib.spice
EOF

cat > "$DEST_DIR/pfet_01v8.pm3.spice" << 'EOF'
* PMOS 1.8V device models for SkyWater 130nm
.lib sky130.lib.spice tt
.include sky130.lib.spice
EOF

echo "✓ PDK models installed to $DEST_DIR"

# Cleanup
cd -
rm -rf "$TEMP_DIR"

echo ""
echo "Next steps:"
echo "  cd pdk/skywater130/gm_id_tables"
echo "  python generate_gmid_tables.py"
echo ""
echo "This will generate accurate Gm/ID lookup tables (~5-10 minutes)"

