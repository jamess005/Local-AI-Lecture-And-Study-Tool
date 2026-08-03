#!/bin/bash
cd "$(dirname "$0")"

# Pin to the discrete GPU. This machine exposes two ROCm devices:
#
#   0: AMD Radeon RX 7800 XT      16.0 GiB   30 CUs   <- the real GPU
#   1: AMD Radeon Graphics        15.2 GiB    1 CU    <- integrated Raphael
#
# Device 1 is the CPU's integrated adapter. It advertises ~15 GiB because that
# is carved out of system RAM, so anything picking a device by free memory will
# happily choose it — and then fail, because it has a single compute unit.
# HSA_OVERRIDE_GFX_VERSION=11.0.0 (needed to make the 7800 XT present as
# gfx1100) makes it worse: those kernels are wrong for Raphael's gfx1036.
#
# Must be exported before Python starts — ROCm reads it at HSA init, so
# setting it in .env or app.py is too late.
export HIP_VISIBLE_DEVICES=0

# ROCm's libraries live in /opt/rocm/lib, which Ubuntu's ROCm packages do NOT
# add to ldconfig. Without this, `dlopen("libMIOpen.so.1")` fails even though
# miopen-hip is installed — and vLLM's EngineCore subprocess dies during init
# with "Engine core initialization failed ... Failed core proc(s)", whose real
# cause is printed inside the dead child. Basic torch works without it (plain
# matmul never touches MIOpen), which is what makes this one hard to spot.
export LD_LIBRARY_PATH="/opt/rocm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# The desktop entry sets Terminal=false, so stdout and stderr are /dev/null:
# everything Python and vLLM print on the way down is discarded. That is what
# turned an OOM-killed engine core into a silent failure — the kernel names the
# victim in dmesg, but the app itself only ever showed vLLM's "Failed core
# proc(s)". Keep the output on disk. logs/ is gitignored.
mkdir -p logs
exec >> logs/app.log 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') starting ==="

exec .venv/bin/python3 src/app.py
