#!/usr/bin/env python3
"""
Selectel GPU VM lifecycle management.
Usage:
  python3 selectel_vm.py create --name <name> --flavor <flavor_id> --image <image_id> --key <keypair> --network <net_id>
  python3 selectel_vm.py wait --id <server_id>
  python3 selectel_vm.py delete --id <server_id>
  python3 selectel_vm.py ip --id <server_id>
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

REGION = "ru-7"
AUTH_URL = "https://cloud.api.selcloud.ru/identity/v3/auth/tokens"
COMPUTE_URL = f"https://{REGION}.cloud.api.selcloud.ru/compute/v2.1"

def get_token():
    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": os.environ["SELECTEL_USER"],
                        "domain": {"name": os.environ["SELECTEL_ACCOUNT_ID"]},
                        "password": os.environ["SELECTEL_PASSWORD"],
                    }
                },
            },
            "scope": {
                "project": {
                    "id": os.environ["SELECTEL_PROJECT_ID"],
                    "domain": {"name": os.environ["SELECTEL_ACCOUNT_ID"]},
                }
            },
        }
    }
    req = urllib.request.Request(
        AUTH_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    return resp.headers.get("X-Subject-Token")


def api(method, path, token, body=None):
    url = COMPUTE_URL + path
    data = json.dumps(body).encode() if body else None
    headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()) if resp.read else {}
    except urllib.error.HTTPError as e:
        print(f"API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def cmd_create(args, token):
    import base64
    userdata = None
    if args.userdata:
        with open(args.userdata) as f:
            userdata = base64.b64encode(f.read().encode()).decode()

    # GL10 (RTX 4090) и другие GPU флейворы имеют Disk:0 —
    # Selectel требует boot-from-volume для таких флейворов.
    body = {
        "server": {
            "name": args.name,
            "flavorRef": args.flavor,
            "key_name": args.key,
            "networks": [{"uuid": args.network}],
            "availability_zone": os.environ.get("AVAILABILITY_ZONE", "ru-7b"),
            "user_data": userdata,
            "block_device_mapping_v2": [
                {
                    "boot_index": 0,
                    "uuid": args.image,
                    "source_type": "image",
                    "destination_type": "volume",
                    "volume_size": args.disk_size,
                    "delete_on_termination": True,  # том удаляется вместе с VM
                }
            ],
        }
    }
    # Remove None values
    body["server"] = {k: v for k, v in body["server"].items() if v is not None}
    result = api("POST", "/servers", token, body)
    server_id = result["server"]["id"]
    print(server_id)


def cmd_wait(args, token):
    for _ in range(60):  # max 10 minutes
        result = api("GET", f"/servers/{args.id}", token)
        status = result["server"]["status"]
        print(f"Status: {status}", file=sys.stderr)
        if status == "ACTIVE":
            print("ACTIVE")
            return
        if status == "ERROR":
            print("ERROR", file=sys.stderr)
            sys.exit(1)
        time.sleep(10)
    print("TIMEOUT", file=sys.stderr)
    sys.exit(1)


def cmd_ip(args, token):
    result = api("GET", f"/servers/{args.id}", token)
    addresses = result["server"].get("addresses", {})
    for net, addrs in addresses.items():
        for addr in addrs:
            if addr.get("OS-EXT-IPS:type") == "floating" or addr.get("version") == 4:
                print(addr["addr"])
                return
    print("NO_IP", file=sys.stderr)
    sys.exit(1)


def cmd_delete(args, token):
    api("DELETE", f"/servers/{args.id}", token)
    print(f"Deleted {args.id}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--flavor", required=True)
    p_create.add_argument("--image", required=True)
    p_create.add_argument("--key", required=True)
    p_create.add_argument("--network", required=True)
    p_create.add_argument("--userdata")
    p_create.add_argument("--disk-size", type=int, default=200,
                          help="Boot volume size in GB (default: 200)")

    p_wait = sub.add_parser("wait")
    p_wait.add_argument("--id", required=True)

    p_ip = sub.add_parser("ip")
    p_ip.add_argument("--id", required=True)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--id", required=True)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    token = get_token()

    if args.cmd == "create":
        cmd_create(args, token)
    elif args.cmd == "wait":
        cmd_wait(args, token)
    elif args.cmd == "ip":
        cmd_ip(args, token)
    elif args.cmd == "delete":
        cmd_delete(args, token)


if __name__ == "__main__":
    main()
