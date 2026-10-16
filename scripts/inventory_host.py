#!/usr/bin/env python3
"""Inventario de solo lectura para ejecutar en Proxmox vía SSH.

Salida privada por defecto. Usa listas permitidas; excluye campos explícitos de
seriales, MACs, direcciones de red, contraseñas y claves SSH. Nombres de recursos
y unidades pueden ser privados: la salida NO es publicable automáticamente.
No monta discos, instala paquetes, inicia self-tests ni cambia servicios.
Solo Python estándar; no instala dependencias en el hipervisor.
"""

import datetime
import json
import pathlib
import re
import subprocess


def run(args, errors, timeout=30):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append({"tool": args[0], "status": type(exc).__name__})
        return None
    if result.returncode:
        # stderr puede contener rutas, seriales o tokens: no exportarlo.
        errors.append({"tool": args[0], "returncode": result.returncode})
    return result


def text(args, errors):
    result = run(args, errors)
    return result.stdout.strip() if result and result.returncode == 0 else None


def json_command(args, errors):
    result = run(args, errors)
    if result is None or result.returncode:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        errors.append({"tool": args[0], "status": "invalid_json"})
        return None


def selected(data, fields):
    return {key: data[key] for key in fields if key in data}


def lvm_summary(raw):
    # LVM añade a veces un bloque log con UUIDs y mensajes: descartarlo entero.
    fields = ["vg_name", "lv_name", "lv_size", "data_percent", "metadata_percent"]
    return [selected(lv, fields) for report in raw.get("report", [])
            for lv in report.get("lv", [])]


def dimms(raw):
    fields = {"Size", "Locator", "Bank Locator", "Type", "Speed",
              "Configured Memory Speed", "Manufacturer", "Part Number"}
    output = []
    for block in (raw or "").split("Memory Device\n")[1:]:
        item = {}
        for line in block.splitlines():
            key, separator, value = line.strip().partition(":")
            if separator and key in fields:
                item[key] = value.strip()
        if item:
            output.append(item)
    return output


def guest_config(raw):
    scalar_fields = {"name", "memory", "cores", "sockets", "cpu", "bios",
                     "machine", "ostype", "onboot", "agent", "balloon", "scsihw"}
    output = {"disks": {}, "network": {}}
    for line in (raw or "").splitlines():
        key, separator, value = line.partition(": ")
        if not separator:
            continue
        if key in scalar_fields:
            output[key] = value
        elif re.fullmatch(r"(?:scsi|sata|ide|virtio)\d+", key):
            pieces = value.split(",")
            # No incluir file=, disk-by-id ni nombre de ISO: contienen identidad.
            first = pieces[0].removeprefix("file=")
            disk = {"physical_device": first.startswith("/dev/"),
                    "storage": None if first.startswith("/") else first.partition(":")[0]}
            for piece in pieces[1:]:
                field, _, val = piece.partition("=")
                if field in {"size", "media", "backup", "cache", "ro", "discard", "ssd"}:
                    disk[field] = val
            output["disks"][key] = disk
        elif re.fullmatch(r"net\d+", key):
            network = {}
            for piece in value.split(","):
                field, _, val = piece.partition("=")
                if field in {"virtio", "rtl8139", "e1000", "e1000e", "vmxnet3"}:
                    network["model"] = field
                elif field in {"bridge", "firewall", "link_down", "tag", "rate"}:
                    network[field] = val
            output["network"][key] = network
    return output


def smart_summary(device, errors):
    # -n standby evita despertar un HDD dormido; no inicia self-tests.
    result = run(["smartctl", "-a", "-j", "-n", "standby", device], errors)
    if result is None:
        return {"device": device, "available": False}
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"device": device, "available": False, "exit_status": result.returncode}
    summary = {"device": device, "exit_status": result.returncode}
    summary.update(selected(raw, ["model_name", "power_on_time", "power_cycle_count"]))
    # No incluir mensajes smartctl: algunos traen seriales.
    summary["health_passed"] = raw.get("smart_status", {}).get("passed")
    summary["temperature_c"] = raw.get("temperature", {}).get("current")
    summary["ata_attributes"] = [
        {"id": attr["id"], "name": attr.get("name"),
         "raw": attr.get("raw", {}).get("value"), "when_failed": attr.get("when_failed")}
        for attr in raw.get("ata_smart_attributes", {}).get("table", [])
        if attr["id"] in {5, 9, 12, 193, 194, 196, 197, 198, 199}
    ]
    summary["nvme"] = selected(raw.get("nvme_smart_health_information_log", {}), [
        "critical_warning", "available_spare", "percentage_used", "power_on_hours",
        "unsafe_shutdowns", "media_errors", "num_err_log_entries",
    ])
    return summary


def collect():
    errors = []
    data = {"schema_version": 1,
            "collected_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "proxmox-host-only", "errors": errors}
    release = {}
    for line in pathlib.Path("/etc/os-release").read_text().splitlines():
        key, _, value = line.partition("=")
        if key in {"PRETTY_NAME", "VERSION_ID", "VERSION_CODENAME"}:
            release[key] = value.strip('"')
    data["system"] = {"os": release, "kernel": text(["uname", "-r"], errors),
                      "pve_version": text(["pveversion"], errors)}
    data["platform"] = {key: text(["dmidecode", "-s", key], errors) for key in [
        "system-manufacturer", "system-product-name", "baseboard-manufacturer", "baseboard-product-name"]}
    data["dimms"] = dimms(text(["dmidecode", "-t", "memory"], errors))
    cpu_raw = json_command(["lscpu", "-J"], errors) or {}
    cpu_fields = {"Architecture", "CPU(s)", "Model name", "Thread(s) per core",
                  "Core(s) per socket", "Socket(s)", "Virtualization", "CPU max MHz"}
    data["cpu"] = {row["field"].rstrip(":"): row["data"] for row in cpu_raw.get("lscpu", [])
                   if row["field"].rstrip(":") in cpu_fields}
    data["memory_kib"] = {}
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            data["memory_kib"][key] = int(value.split()[0])
    blocks = json_command(["lsblk", "-b", "-J", "-o", "NAME,SIZE,TYPE,MODEL"], errors) or {}
    data["physical_disks"] = [selected(block, ["name", "size", "type", "model"])
                              for block in blocks.get("blockdevices", []) if block.get("type") == "disk"]
    data["smart"] = [smart_summary("/dev/" + disk["name"], errors) for disk in data["physical_disks"]]
    data["storage_status"] = text(["pvesm", "status"], errors)
    lvm = run(["lvs", "--reportformat", "json", "--units", "b", "--nosuffix",
               "-o", "vg_name,lv_name,lv_size,data_percent,metadata_percent"], errors)
    data["lvm_old_pv_header_warning"] = bool(lvm and "old PV header" in lvm.stderr)
    if lvm and lvm.returncode == 0:
        try:
            data["lvm"] = lvm_summary(json.loads(lvm.stdout))
        except json.JSONDecodeError:
            errors.append({"tool": "lvs", "status": "invalid_json"})
    mdstat = pathlib.Path("/proc/mdstat")
    data["mdraid_status"] = mdstat.read_text() if mdstat.exists() else None
    data["root_filesystem"] = text(["df", "-B1", "--output=size,used,avail,pcent,target", "/"], errors)
    guests = json_command(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"], errors)
    data["guests"] = []
    for guest in guests or []:
        item = selected(guest, ["vmid", "name", "type", "status", "maxmem", "maxcpu", "template"])
        cli = "qm" if guest.get("type") == "qemu" else "pct"
        item["config"] = guest_config(text([cli, "config", str(guest["vmid"])], errors))
        data["guests"].append(item)
    data["network_links"] = []
    for interface in pathlib.Path("/sys/class/net").iterdir():
        if (interface / "device").exists():
            item = {"name": interface.name}
            for field in ["speed", "duplex", "operstate"]:
                try:
                    item[field] = (interface / field).read_text().strip()
                except OSError:
                    item[field] = None
            data["network_links"].append(item)
    pci = text(["lspci"], errors) or ""
    data["pci_controllers"] = [line for line in pci.splitlines()
                               if re.search(r"ethernet|network|vga|display|sata|non-volatile", line, re.I)]
    units = json_command(["systemctl", "list-units", "--type=service", "--state=running",
                          "--output=json", "--no-pager"], errors)
    data["running_services"] = [selected(unit, ["unit", "active", "sub"]) for unit in units or []]
    failed = json_command(["systemctl", "--failed", "--output=json", "--no-pager"], errors)
    data["failed_units"] = [selected(unit, ["unit", "active", "sub"]) for unit in failed or []]
    data["custom_units"] = {unit: text(["systemctl", "show", unit, "-p", "LoadState",
                                      "-p", "ActiveState", "-p", "SubState"], errors)
                            for unit in ["log2ram.service", "proxmenux-monitor.service"]}
    data["pve_firewall_status"] = text(["pve-firewall", "status"], errors)
    jobs = json_command(["pvesh", "get", "/cluster/backup", "--output-format", "json"], errors)
    data["backup_jobs_count"] = len(jobs) if jobs is not None else None
    # No exportar destinos, usuarios, mails o tokens de jobs de backup.
    data["local_backup_content"] = text(["pvesm", "list", "local", "--content", "backup"], errors)
    packages = text(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"], errors) or ""
    exact = {"intel-microcode", "lvm2", "mdadm", "btrfs-progs", "smartmontools", "ethtool",
             "wireguard-tools", "log2ram", "docker-ce", "docker.io", "podman", "tailscale",
             "nut", "lm-sensors"}
    data["relevant_packages"] = {}
    for line in packages.splitlines():
        package, _, version = line.partition("\t")
        if package in exact or package.startswith(("pve-", "proxmox-", "qemu-server", "lxc-pve")):
            data["relevant_packages"][package] = version
    return data


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2, ensure_ascii=False))
