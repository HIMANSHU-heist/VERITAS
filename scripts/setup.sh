#!/usr/bin/env bash
set -e
sudo apt-get update
sudo apt-get install -y build-essential cmake nlohmann-json3-dev libssl-dev
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cmake -S cpp -B cpp/build
cmake --build cpp/build
echo "SETUP DONE"
