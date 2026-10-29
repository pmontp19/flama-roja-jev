#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH=x86_64
ROOT=.mgba-${ARCH}
BUILD_DIR=${ROOT}/mgba
PREFIX=$PWD/${ROOT}/install
SP=.venv/lib/python3.11/site-packages

if [ ! -d "${SP}/mgba" ]; then
  echo "crea primer el venv: uv sync" >&2
  exit 1
fi

uv pip install cffi setuptools pip pytest-runner --quiet
export VIRTUAL_ENV="$PWD/.venv"
export PATH="${VIRTUAL_ENV}/bin:${PATH}"

if [ ! -d "${BUILD_DIR}" ]; then
  git clone --depth 1 https://github.com/mgba-emu/mgba.git "${BUILD_DIR}"
fi

python3 - <<'EOF'
import pathlib

header = pathlib.Path(".mgba-x86_64/mgba/include/mgba/internal/gba/cart/ereader.h")
text = header.read_text()
if "#ifdef USE_FFMPEG" not in text:
    text = text.replace(
        "struct EReaderAnchor;\nstruct EReaderBlock;\nDECLARE_VECTOR(EReaderAnchorList, struct EReaderAnchor);",
        "#ifdef USE_FFMPEG\nstruct EReaderAnchor;\nstruct EReaderBlock;\nDECLARE_VECTOR(EReaderAnchorList, struct EReaderAnchor);",
        1,
    )
    text = text.replace(
        "\tstruct EReaderBlockList blocks;\n};",
        "\tstruct EReaderBlockList blocks;\n};\n#endif",
        1,
    )
    text = text.replace(
        "struct EReaderScan* EReaderScanCreate(unsigned width, unsigned height);",
        "#ifdef USE_FFMPEG\nstruct EReaderScan* EReaderScanCreate(unsigned width, unsigned height);",
        1,
    )
    text = text.replace(
        "bool EReaderScanScanBlock(struct EReaderScan*, int block, bool strict);",
        "bool EReaderScanScanBlock(struct EReaderScan*, int block, bool strict);\n#endif",
        1,
    )
    header.write_text(text)
    print("header E-Reader apingardat")

interface_header = pathlib.Path(".mgba-x86_64/mgba/include/mgba/gba/interface.h")
itext = interface_header.read_text()
if "#if defined(USE_FFMPEG)" not in itext:
    itext = itext.replace(
        "struct EReaderScan;\n",
        "#if defined(USE_FFMPEG)\nstruct EReaderScan;\n",
        1,
    )
    itext = itext.replace(
        "\nCXX_GUARD_END",
        "#endif\n\nCXX_GUARD_END",
        1,
    )
    interface_header.write_text(itext)
    print("header interface apingardat")

cmake_pylists = pathlib.Path(".mgba-x86_64/mgba/src/platform/python/CMakeLists.txt")
ctext = cmake_pylists.read_text()
if "DEFINES_FLAGS" not in ctext:
    ctext = ctext.replace(
        'CPPFLAGS="${INCLUDE_FLAGS}"',
        'CPPFLAGS="${INCLUDE_FLAGS} ${DEFINES_FLAGS}"',
    )
    inject = """
get_target_property(MGBA_PY_DEFS mgba COMPILE_DEFINITIONS)
set(DEFINES_FLAGS "")
foreach(_DEF IN LISTS MGBA_PY_DEFS)
  if(_DEF)
    list(APPEND DEFINES_FLAGS "-D${_DEF}")
  endif()
endforeach()

file(GLOB PYTHON_HEADERS"""
    ctext = ctext.replace("\nfile(GLOB PYTHON_HEADERS", inject, 1)
    cmake_pylists.write_text(ctext)
    print("CMakeLists python apingardat")
EOF

find .mgba-x86_64/mgba/build/python -name lib.c -delete 2>/dev/null || true

cmake -S "${BUILD_DIR}" -B "${BUILD_DIR}/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=${ARCH} \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
  -DBUILD_LTO=OFF \
  -DPython3_EXECUTABLE="$PWD/.venv/bin/python" \
  -DPYTHON_EXECUTABLE="$PWD/.venv/bin/python" \
  -DBUILD_QT=OFF -DBUILD_SDL=OFF -DBUILD_SUITE=OFF -DBUILD_TESTS=OFF \
  -DBUILD_STATIC=OFF -DBUILD_SHARED=ON -DBUILD_PYTHON=ON \
  -DUSE_FFMPEG=OFF -DUSE_MAGICK=OFF -DUSE_ELF=OFF -DUSE_ZIP=OFF \
  -DUSE_PNG=OFF -DUSE_LIBZIP=OFF -DUSE_MINIZIP=OFF -DUSE_SQLITE3=OFF \
  -DUSE_EPOXY=OFF -DUSE_DISCORD_RPC=OFF -DUSE_EMBEDDED_VFS=OFF   -DUSE_LUA=OFF -DUSE_JSON_C=OFF -DUSE_FREETYPE=OFF -DUSE_LIBPNG=OFF
cmake --build "${BUILD_DIR}/build" -j
cmake --install "${BUILD_DIR}/build"

NEW_SP=$(ls -d "${PREFIX}"/lib/python3*/site-packages/mgba 2>/dev/null | head -1 || true)
if [ -z "${NEW_SP}" ]; then
  NEW_SP=$(find "${BUILD_DIR}/build/python" -type d -name mgba -path "*lib*" 2>/dev/null | head -1)
fi
if [ -z "${NEW_SP}" ]; then
  echo "no trobo el package mgba generat" >&2
  find "${PREFIX}" -name "_pylib*" -o -name "core.py" | head >&2
  exit 1
fi

rm -rf "${SP}/mgba"
cp -R "${NEW_SP}" "${SP}/mgba"

NEW_SO=$(ls "${SP}"/mgba/_pylib*.so | head -1)
DYLIB_DIR="$(cd "${BUILD_DIR}/build" && pwd)"
OLD_PATH=$(otool -L "${NEW_SO}" | grep "libmgba" | awk '{print $1}' | head -1) || true
if [ -n "${OLD_PATH:-}" ] && [ "${OLD_PATH}" != "@rpath/libmgba.0.10.dylib" ]; then
  install_name_tool -change "${OLD_PATH}" "@rpath/libmgba.0.10.dylib" "${NEW_SO}"
fi

if ! otool -l "${NEW_SO}" | grep -q "${DYLIB_DIR}"; then
  install_name_tool -add_rpath "${DYLIB_DIR}" "${NEW_SO}" 2>/dev/null || true
fi

if [ ! -e "${DYLIB_DIR}/libmgba.0.10.dylib" ]; then
  REAL=$(readlink -f "${DYLIB_DIR}/libmgba.dylib")
  ln -sf "$(basename "${REAL}")" "${DYLIB_DIR}/libmgba.0.10.dylib"
fi

codesign --force --sign - "${NEW_SO}" 2>/dev/null || true

uv run python -c "import mgba, mgba.core; print('mgba ok:', mgba.__file__)"
echo "fet"
