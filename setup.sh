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

# 1. Target Host IP Argument Handling (Zero-Touch)
if [ "${1:-}" != "" ] && [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    TARGET_IP="$1"
    shift
    echo "[+] Dynamically configuring target OpenStack host to: ${TARGET_IP}"
    cat << EOF > inventory/hosts.ini
[openstack_host]
target_node ansible_host=${TARGET_IP} ansible_user=root

[deployer_node]
deployer_local ansible_host=127.0.0.1 ansible_connection=local

[all:vars]
ansible_python_interpreter=/usr/bin/python3
EOF
fi

# 2. Export environment variables for Ansible
export ANSIBLE_CONFIG="${SCRIPT_DIR}/ansible.cfg"
export ANSIBLE_ROLES_PATH="${SCRIPT_DIR}/roles"

# 3. Check Ansible installation
if ! command -v ansible-playbook &> /dev/null; then
    echo "[!] Ansible not found. Installing Ansible and required dependencies..."
    apt-get update -qq && apt-get install -y -qq ansible python3-pip
fi

# 4. Check inventory presence
if [ ! -f "inventory/hosts.ini" ]; then
    echo "[CRITICAL ERROR] inventory/hosts.ini not found!"
    exit 1
fi

echo "[+] Running OpenStack Safir Master Orchestration Playbook..."
ansible-playbook -i inventory/hosts.ini playbooks/deploy_all.yml "$@"

echo "[+] Deployment completed successfully!"
