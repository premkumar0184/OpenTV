#!/bin/sh
# OpenTV Standalone Reproducible Release Build Pipeline
# Compatible with Linux, macOS, and WSL environments.
# Uses Android SDK CLI tools directly: aapt2, javac, d8, jar/python, zipalign, apksigner.
set -e

# Resolve execution directory (handles invocation from root or app/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/src/main" ]; then
  APP_DIR="$SCRIPT_DIR"
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -d "$SCRIPT_DIR/app/src/main" ]; then
  APP_DIR="$SCRIPT_DIR/app"
  PROJECT_ROOT="$SCRIPT_DIR"
else
  echo "Error: Cannot locate OpenTV source tree" >&2
  exit 1
fi

cd "$APP_DIR"

# 1. Android SDK Auto-Discovery
# Prioritizes /home/prem/Android/Sdk and valid SDK installations with platforms and build-tools
find_sdk() {
  for d in "/home/prem/Android/Sdk" "$ANDROID_HOME" "$ANDROID_SDK_ROOT" "$HOME/Android/Sdk" $(ls -d /home/*/Android/Sdk 2>/dev/null) "/opt/android-sdk"; do
    if [ -n "$d" ] && [ -d "$d/platforms" ] && [ -d "$d/build-tools" ]; then
      echo "$d"
      return 0
    fi
  done
  return 1
}

SDK=$(find_sdk) || {
  echo "Error: Functional Android SDK with platforms and build-tools not found." >&2
  echo "Checked: /home/prem/Android/Sdk, \$ANDROID_HOME, \$ANDROID_SDK_ROOT, \$HOME/Android/Sdk" >&2
  exit 1
}

# Select build-tools (prefer 36.0.0 if present, else highest version)
if [ -d "$SDK/build-tools/36.0.0" ]; then
  BT="$SDK/build-tools/36.0.0"
else
  BT="${BUILD_TOOLS:-$(find "$SDK/build-tools" -maxdepth 1 -mindepth 1 -type d | sort -V | tail -n 1)}"
fi

# Select platform jar (prefer android-35 if present, else highest available)
if [ -f "$SDK/platforms/android-35/android.jar" ]; then
  JAR="$SDK/platforms/android-35/android.jar"
elif [ -f "$SDK/platforms/android-36/android.jar" ]; then
  JAR="$SDK/platforms/android-36/android.jar"
else
  JAR="${PLATFORM_JAR:-$(find "$SDK/platforms" -maxdepth 2 -name "android.jar" | sort -V | tail -n 1)}"
fi

[ -x "$BT/aapt2" ] || { echo "Error: aapt2 not found at $BT/aapt2" >&2; exit 1; }
[ -x "$BT/d8" ] || { echo "Error: d8 not found at $BT/d8" >&2; exit 1; }
[ -x "$BT/zipalign" ] || { echo "Error: zipalign not found at $BT/zipalign" >&2; exit 1; }
[ -x "$BT/apksigner" ] || { echo "Error: apksigner not found at $BT/apksigner" >&2; exit 1; }
[ -f "$JAR" ] || { echo "Error: android.jar not found at $JAR" >&2; exit 1; }

echo "=== OpenTV Standalone Build ==="
echo "SDK:         $SDK"
echo "Build-Tools: $BT"
echo "Platform:    $JAR"

# 2. Output Directory Preparation
rm -rf out
mkdir -p out/classes out/dex out/gen/org/opentv/launcher

# 3. AAPT2 Link Manifest & Resources
echo "[1/6] Compiling manifest and resources with AAPT2..."
"$BT/aapt2" link -o out/base.apk -I "$JAR" --manifest src/main/AndroidManifest.xml \
  --min-sdk-version 21 --target-sdk-version 34

# 4. Java Compilation (Targeting Java 17 for D8 compatibility under JDK 21)
echo "[2/6] Compiling Java sources with javac (Java 17 target)..."
JAVA_SOURCES=$(find src/main/java out/gen -name "*.java" 2>/dev/null)
if [ -z "$JAVA_SOURCES" ]; then
  echo "Error: No Java sources found in src/main/java" >&2
  exit 1
fi

javac -nowarn -Xlint:-options -encoding UTF-8 -source 17 -target 17 -cp "$JAR" \
  -d out/classes $JAVA_SOURCES

# 5. Dex Compilation via D8 (Desugaring down to min-api 21)
echo "[3/6] Compiling bytecode to DEX with D8 (min-api 21)..."
"$BT/d8" --min-api 21 --release --lib "$JAR" --output out/dex $(find out/classes -name '*.class')

# 6. Packaging DEX into Base APK (Zero-dependency archive injection)
echo "[4/6] Packaging classes.dex into APK..."
cp out/base.apk out/unsigned.apk
if command -v jar >/dev/null 2>&1; then
  (cd out/dex && jar uf ../unsigned.apk classes.dex)
elif command -v python3 >/dev/null 2>&1; then
  python3 -c "import zipfile, sys; z=zipfile.ZipFile(sys.argv[1], 'a'); z.write(sys.argv[2], arcname='classes.dex'); z.close()" out/unsigned.apk out/dex/classes.dex
elif command -v zip >/dev/null 2>&1; then
  (cd out/dex && zip -q ../unsigned.apk classes.dex)
else
  echo "Error: Neither jar, python3, nor zip found on host" >&2
  exit 1
fi

# 7. 4-Byte Zip Alignment
echo "[5/6] Aligning APK boundaries with zipalign..."
"$BT/zipalign" -f 4 out/unsigned.apk out/aligned.apk
"$BT/zipalign" -c 4 out/aligned.apk

# 8. Automated Keystore Generation & Multi-Scheme Signing (v1, v2, v3)
echo "[6/6] Signing release APK with apksigner..."
KS="${KEYSTORE:-$PROJECT_ROOT/release.jks}"
PASS="${KEYSTORE_PASS:-opentv123}"
ALIAS="${KEY_ALIAS:-opentv}"

if [ ! -f "$KS" ]; then
  echo "Generating release keystore at $KS..."
  keytool -genkeypair -keystore "$KS" -storepass "$PASS" -keypass "$PASS" \
    -alias "$ALIAS" -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=OpenTV, O=OpenTV, C=US" >/dev/null 2>&1
fi

"$BT/apksigner" sign --ks "$KS" --ks-pass "pass:$PASS" --key-pass "pass:$PASS" \
  --ks-key-alias "$ALIAS" \
  --v1-signing-enabled true \
  --v2-signing-enabled true \
  --v3-signing-enabled true \
  --out out/opentv.apk out/aligned.apk

# Copy output to root app-release.apk and app/out/opentv.apk
cp out/opentv.apk "$PROJECT_ROOT/app-release.apk"
cp out/opentv.apk out/app-release.apk

# 9. Verification Assertion
echo "=== Signature Verification ==="
VERIFY_OUTPUT=$("$BT/apksigner" verify --verbose "$PROJECT_ROOT/app-release.apk")
echo "$VERIFY_OUTPUT"

# Assert v1, v2, v3 schemes
echo "$VERIFY_OUTPUT" | grep -q "Verified using v1 scheme (JAR signing): true" || { echo "Error: v1 signature missing" >&2; exit 1; }
echo "$VERIFY_OUTPUT" | grep -q "Verified using v2 scheme (APK Signature Scheme v2): true" || { echo "Error: v2 signature missing" >&2; exit 1; }
echo "$VERIFY_OUTPUT" | grep -q "Verified using v3 scheme (APK Signature Scheme v3): true" || { echo "Error: v3 signature missing" >&2; exit 1; }

echo "=== Build Complete ==="
echo "Artifact (project root): $PROJECT_ROOT/app-release.apk"
echo "Artifact (app out):      $APP_DIR/out/opentv.apk"
ls -lh "$PROJECT_ROOT/app-release.apk"
