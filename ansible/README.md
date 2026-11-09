# ExamVault Ansible Deployment Guide

This directory contains the Ansible automation playbooks and configuration for deploying **ExamVault** to remote or local Linux servers.

---

## Directory Structure

```
ansible/
├── ansible.cfg        # Ansible global configuration
├── inventory.ini      # Target hosts inventory (staging & production)
├── vars.yml           # Deployment variables and credentials template
├── deploy.yml         # Main deployment playbook
└── README.md          # Usage documentation
```

---

## Prerequisites

On your control machine (the machine running Ansible):
* Python 3.8+
* Ansible core: `pip install ansible-core`
* Target machine with SSH access and sudo privileges

---

## Quick Start Deployment

### 1. Configure Target Server
Edit `ansible/inventory.ini` and specify your server IP address and SSH user:

```ini
[production]
examvault_prod ansible_host=203.0.113.10 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa
```

### 2. Configure Environment Secrets
You can provide environment variables directly or encrypt sensitive credentials using Ansible Vault:

```bash
# Set environment variables:
export SECRET_KEY="my-production-secret-key"
export DB_PASSWORD="my-secure-database-password"
export MYSQL_ROOT_PASSWORD="my-secure-root-password"
```

Or encrypt secrets using Ansible Vault:
```bash
ansible-vault encrypt_string 'super_secret_db_pass' --name 'db_password'
```

### 3. Syntax Verification
Test your playbook syntax before execution:

```bash
ansible-playbook -i inventory.ini deploy.yml --syntax-check
```

### 4. Run Deployment
Deploy the full stack:

```bash
ansible-playbook -i inventory.ini deploy.yml
```

The playbook will automatically:
1. Check and install Docker & Docker Compose if missing.
2. Ensure Docker daemon is enabled and running.
3. Synchronize application files to `/opt/examvault`.
4. Generate the secure production `.env` file with `0600` permissions.
5. Build and launch Flask & MySQL containers.
6. Verify deployment by polling `http://<SERVER_IP>:5003/health`.
