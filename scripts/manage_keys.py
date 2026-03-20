#!/usr/bin/env python3
"""
Script quản lý API Keys cho NGINX Gateway.
Tạo key mới, list keys, revoke key.

Usage:
  python manage_keys.py generate --name client-app
  python manage_keys.py list
  python manage_keys.py revoke --name client-app
  python manage_keys.py apply   # sync keys lên cluster
"""
import argparse
import secrets
import subprocess
import yaml
import sys
from pathlib import Path

VALUES_FILE = Path(__file__).parent.parent / "helm/charts/nginx-gateway/values.yaml"


def load_values():
    with open(VALUES_FILE) as f:
        return yaml.safe_load(f)


def save_values(values):
    with open(VALUES_FILE, "w") as f:
        yaml.dump(values, f, default_flow_style=False, allow_unicode=True)


def generate_key(name: str):
    values = load_values()
    if name in values["apiKeys"]:
        print(f"❌ Key '{name}' đã tồn tại. Dùng --force để overwrite.")
        sys.exit(1)

    new_key = f"sk-{name}-{secrets.token_urlsafe(24)}"
    values["apiKeys"][name] = new_key
    save_values(values)

    print(f"✅ Generated API key for '{name}':")
    print(f"   {new_key}")
    print(f"\nClient dùng header:")
    print(f'   X-API-Key: {new_key}')
    return new_key


def list_keys():
    values = load_values()
    keys = values.get("apiKeys", {})
    if not keys:
        print("Không có API key nào.")
        return

    print(f"{'Name':<20} {'Key (masked)':<40}")
    print("-" * 60)
    for name, key in keys.items():
        masked = key[:12] + "..." + key[-4:]
        print(f"{name:<20} {masked:<40}")


def revoke_key(name: str):
    values = load_values()
    if name not in values["apiKeys"]:
        print(f"❌ Key '{name}' không tồn tại.")
        sys.exit(1)

    del values["apiKeys"][name]
    save_values(values)
    print(f"✅ Revoked key '{name}'")
    print("Chạy 'python manage_keys.py apply' để apply lên cluster.")


def apply_keys():
    """Sync values.yaml lên cluster bằng helm upgrade."""
    print("Applying API keys to cluster...")
    result = subprocess.run(
        [
            "helm", "upgrade", "--install", "nginx-gateway",
            "./helm/charts/nginx-gateway",
            "-n", "ingress-nginx",
            "--create-namespace",
        ],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("✅ Keys applied successfully!")
    else:
        print(f"❌ Error: {result.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage API Keys")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate new API key")
    gen.add_argument("--name", required=True, help="Client name")

    sub.add_parser("list", help="List all API keys")

    rev = sub.add_parser("revoke", help="Revoke an API key")
    rev.add_argument("--name", required=True, help="Client name to revoke")

    sub.add_parser("apply", help="Apply keys to cluster")

    args = parser.parse_args()

    if args.command == "generate":
        generate_key(args.name)
    elif args.command == "list":
        list_keys()
    elif args.command == "revoke":
        revoke_key(args.name)
    elif args.command == "apply":
        apply_keys()
    else:
        parser.print_help()