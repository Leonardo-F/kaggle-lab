#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for p in order factor bilayer hyper synth congruence/congruence variants/basis12free/basis variants/synth9/synth9; do
  "${SANTA_CXX:-g++}" -I ../native/compat -O3 -std=c++17 "$p.cpp" -o "$p"
done
