#!/usr/bin/env bash
# ==============================================================================
# OpenStack Safir All-in-One Master Automation Runner
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=============================================================================="
echo "          OPENSTACK SAFIR ALL-IN-ONE AUTOMATED INSTALLER                      "
echo "=============================================================================="

# 1. Check Ansible installation
if ! command -v ansible-playbook &> /dev/null; then
    echo "[!] Ansible not found. Installing Ansible and required dependencies..."
    apt-get update -qq && apt-get install -y -qq ansible python3-pip
fi

# 2. Check inventory presence
if [ ! -f "inventory/hosts.ini" ]; then
    echo "[CRITICAL ERROR] inventory/hosts.ini not found!"
    exit 1
fi

echo "[+] Running OpenStack Safir Master Orchestration Playbook..."
ansible-playbook -i inventory/hosts.ini playbooks/deploy_all.yml "$@"

echo "[+] Deployment completed successfully!"
