#!/usr/bin/env bash
# Restores the dev toolchain in a fresh cloud container (idempotent).
# Blender (bpy wheel), Godot 4.5.1, Xvfb + Mesa (lavapipe) for headless rendering, npm deps.
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT=/opt/godot/Godot_v4.5.1-stable_linux.x86_64
if [ ! -x "$GODOT" ]; then
  mkdir -p /opt/godot
  curl -sSL -o /opt/godot/godot.zip https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_linux.x86_64.zip
  unzip -o -q /opt/godot/godot.zip -d /opt/godot && rm /opt/godot/godot.zip
fi
python3 -c "import bpy" 2>/dev/null || pip install -q bpy==5.0.1
if ! command -v xvfb-run >/dev/null; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq xvfb libgl1-mesa-dri mesa-vulkan-drivers libvulkan1 \
    libxcursor1 libxinerama1 libxrandr2 libxi6 libasound2t64 libpulse0 >/dev/null
fi
[ -d node_modules ] || npm ci --silent
# Android export without Google SDK (dl.google.com is blocked): Ubuntu apksigner/zipalign/adb + Godot templates.
if ! command -v apksigner >/dev/null; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-17-jdk-headless apksigner zipalign adb >/dev/null
fi
TD=~/.local/share/godot/export_templates/4.5.1.stable
if [ ! -f "$TD/android_debug.apk" ]; then
  mkdir -p "$TD"
  curl -sSL -o /tmp/templates.tpz https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_export_templates.tpz
  unzip -o -q /tmp/templates.tpz 'templates/android_*' 'templates/version.txt' -d /tmp/tpl && cp /tmp/tpl/templates/* "$TD/" && rm -rf /tmp/tpl /tmp/templates.tpz
fi
mkdir -p /opt/android-sdk/platform-tools /opt/android-sdk/build-tools/35.0.0
ln -sf /usr/bin/adb /opt/android-sdk/platform-tools/adb
ln -sf /usr/bin/apksigner /opt/android-sdk/build-tools/35.0.0/apksigner
ln -sf /usr/bin/zipalign /opt/android-sdk/build-tools/35.0.0/zipalign
mkdir -p ~/.android
[ -f ~/.android/debug.keystore ] || keytool -genkeypair -keystore ~/.android/debug.keystore -storepass android -alias androiddebugkey \
  -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US" >/dev/null 2>&1
JH=$(dirname "$(dirname "$(readlink -f "$(which java)")")")
mkdir -p ~/.config/godot
cat > ~/.config/godot/editor_settings-4.5.tres <<EOT
[gd_resource type="EditorSettings" format=3]

[resource]
export/android/android_sdk_path = "/opt/android-sdk"
export/android/java_sdk_path = "$JH"
export/android/debug_keystore = "$HOME/.android/debug.keystore"
export/android/debug_keystore_user = "androiddebugkey"
export/android/debug_keystore_pass = "android"
EOT
# Godot import (creates game/.godot cache)
"$GODOT" --headless --path game --import >/dev/null 2>&1 || true
echo "toolchain ready"
