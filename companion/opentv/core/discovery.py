"""
OpenTV Local Device Auto-Discovery Engine.
Milestone 3: Pure Python 3 standard library mDNS and SSDP discovery.
Strictly zero external pip dependencies.

Supports:
- mDNS (RFC 6762 / RFC 6763) query encoding and response parsing for
  Android ADB services (_adb._tcp.local, _adb-tls-connect._tcp.local)
  over 224.0.0.251:5353 with full DNS name pointer decompression (0xc0)
  and loop guard.
- SSDP / UPnP M-SEARCH multicast discovery over 239.255.255.250:1900
  with heuristic signature detection for Android TV brands and non-TV rejection.
- Unified DiscoveredDevice representation, stateful record aggregation,
  and numeric IPv4 octet deduplication.
"""
from __future__ import annotations

import re
import select
import socket
import struct
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union


# ============================================================================
# 1. Unified Device Model
# ============================================================================

@dataclass
class DiscoveredDevice:
    """
    Unified representation of a smart TV discovered on the local network
    via mDNS, SSDP, or a merged combination of both protocols.
    """
    ip: str
    port: int = 5555
    hostname: str = ""
    device_type: str = "unknown"  # "android_tv", "google_tv", "fire_tv", "smart_tv", "unknown"
    model: str = ""
    source: str = "unknown"       # "mdns", "ssdp", "mdns+ssdp"
    raw_info: Dict[str, Any] = field(default_factory=dict)

    @property
    def address(self) -> str:
        """Formatted target address for adb connect (e.g. '192.168.1.100:5555')."""
        return f"{self.ip}:{self.port}"

    @property
    def is_android(self) -> bool:
        """Returns True if the device signature indicates an Android-based TV/device."""
        if "mdns" in self.source:
            # mDNS discovery specifically queries _adb._tcp, which is Android-specific
            return True
        android_types = {"android_tv", "google_tv", "fire_tv"}
        return self.device_type.lower() in android_types

    @property
    def display_name(self) -> str:
        """User-friendly summary string for TUI / CLI selection tables."""
        name_part = self.model or self.hostname or self.device_type.replace("_", " ").title()
        type_tag = f" [{self.device_type.upper()}]" if self.device_type != "unknown" else ""
        source_tag = f" ({self.source})"
        return f"{name_part}{type_tag} - {self.address}{source_tag}"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the discovered device to a plain dictionary."""
        return {
            "ip": self.ip,
            "port": self.port,
            "hostname": self.hostname,
            "device_type": self.device_type,
            "model": self.model,
            "source": self.source,
            "is_android": self.is_android,
            "address": self.address,
            "display_name": self.display_name,
            "raw_info": self.raw_info,
        }


# ============================================================================
# 2. mDNS Constants & Binary Packet Utilities (RFC 6762 / RFC 6763)
# ============================================================================

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
ADB_SERVICE = "_adb._tcp.local"
ADB_TLS_SERVICE = "_adb-tls-connect._tcp.local"


def build_mdns_query(service_name: str, unicast_response: bool = False, qtype: int = 12) -> bytes:
    """
    Constructs an RFC 6762 compliant DNS query packet for mDNS.
    - Transaction ID: 0x0000
    - Flags: 0x0000 (standard query)
    - Questions: 1 (QDCOUNT = 1)
    - QTYPE: 12 (PTR) by default
    - QCLASS: 0x0001 (IN, multicast response QM) or 0x8001 (IN, unicast response QU)
    """
    header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)

    parts = service_name.strip(".").split(".")
    qname = b""
    for part in parts:
        bpart = part.encode("utf-8")
        qname += bytes([len(bpart)]) + bpart
    qname += b"\x00"

    qclass = 0x8001 if unicast_response else 0x0001
    question = qname + struct.pack("!HH", qtype, qclass)
    return header + question


def parse_dns_name(data: bytes, offset: int) -> Tuple[str, int]:
    """
    Parse a DNS domain name from packet bytes supporting 0xc0 compression pointers,
    hybrid prefixes, chained pointers, recursion limits, and boundary checks.
    Enforces RFC 1035 label length limits (<= 63 bytes) and cyclic loop guards.
    Returns (domain_name_str, next_offset).
    """
    labels: List[str] = []
    initial_offset = offset
    jumped = False
    max_jumps = 20
    jumps = 0
    visited_offsets: Set[int] = set()

    while True:
        if offset < 0 or offset >= len(data):
            break
        if offset in visited_offsets:
            # Pointer cycle detected - terminate parsing immediately
            break
        visited_offsets.add(offset)

        length = data[offset]
        if length == 0:
            if not jumped:
                offset += 1
            break
        elif (length & 0xC0) == 0xC0:
            if offset + 1 >= len(data):
                break
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                initial_offset = offset + 2
                jumped = True
            jumps += 1
            if jumps > max_jumps or pointer >= len(data) or pointer < 0:
                break
            offset = pointer
        elif (length & 0xC0) != 0:
            # RFC 1035: Reserved label type indicator (0x40 or 0x80)
            break
        elif length > 63:
            # RFC 1035 section 2.3.4: labels must be 63 octets or less
            break
        else:
            offset += 1
            if offset + length > len(data):
                break
            label = data[offset:offset + length].decode("utf-8", errors="replace")
            labels.append(label)
            offset += length
            if not jumped:
                initial_offset = offset

    return ".".join(labels), (initial_offset if jumped else offset)


def parse_dns_response(data: bytes) -> List[Dict[str, Any]]:
    """
    Parse full DNS response packet into structured records (PTR, SRV, TXT, A).
    Safely ignores malformed or truncated records without throwing exceptions.
    """
    if len(data) < 12:
        return []

    try:
        tid, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
    except struct.error:
        return []

    offset = 12

    # Skip question records
    for _ in range(qdcount):
        if offset >= len(data):
            break
        _, offset = parse_dns_name(data, offset)
        offset += 4  # Skip QTYPE and QCLASS

    records: List[Dict[str, Any]] = []
    total_records = ancount + nscount + arcount

    for _ in range(total_records):
        if offset >= len(data):
            break
        rname, offset = parse_dns_name(data, offset)
        if offset + 10 > len(data):
            break

        try:
            rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        except struct.error:
            break

        offset += 10
        if offset + rdlength > len(data):
            break
        rdata = data[offset:offset + rdlength]

        parsed_rdata: Any = None
        if rtype == 12:  # PTR
            parsed_rdata, _ = parse_dns_name(data, offset)
        elif rtype == 1:  # A (IPv4)
            if len(rdata) == 4:
                try:
                    parsed_rdata = socket.inet_ntoa(rdata)
                except (OSError, ValueError):
                    parsed_rdata = None
        elif rtype == 33:  # SRV
            if len(rdata) >= 6:
                try:
                    priority, weight, port = struct.unpack("!HHH", rdata[:6])
                    target, _ = parse_dns_name(data, offset + 6)
                    parsed_rdata = {
                        "priority": priority,
                        "weight": weight,
                        "port": port,
                        "target": target,
                    }
                except struct.error:
                    parsed_rdata = None
        elif rtype == 16:  # TXT
            txt_dict: Dict[str, str] = {}
            pos = 0
            while pos < len(rdata):
                txt_len = rdata[pos]
                pos += 1
                if pos + txt_len > len(rdata):
                    break
                item = rdata[pos:pos + txt_len]
                pos += txt_len
                if b"=" in item:
                    k, v = item.split(b"=", 1)
                    txt_dict[k.decode("utf-8", errors="replace")] = v.decode("utf-8", errors="replace")
                elif item:
                    txt_dict[item.decode("utf-8", errors="replace")] = ""
            parsed_rdata = txt_dict

        records.append({
            "name": rname,
            "type": rtype,
            "class": rclass & 0x7FFF,
            "ttl": ttl,
            "data": parsed_rdata,
        })
        offset += rdlength

    return records


class MdnsDeviceAggregator:
    """
    Collects and correlates mDNS resource records across datagrams
    to build unified DiscoveredDevice instances.
    """

    def __init__(self) -> None:
        # Keyed by instance / service name or IP
        self._ptr_records: List[str] = []
        self._srv_records: Dict[str, Dict[str, Any]] = {}
        self._txt_records: Dict[str, Dict[str, str]] = {}
        self._a_records: Dict[str, str] = {}  # target_name -> ip
        self._ip_sources: Set[str] = set()
        self._sender_ips: Dict[str, str] = {}  # service_name -> sender_ip

    def ingest_records(self, records: List[Dict[str, Any]], sender_ip: str) -> None:
        """Process parsed DNS records from a response datagram."""
        self._ip_sources.add(sender_ip)
        for r in records:
            rtype = r.get("type")
            rname = r.get("name", "")
            rdata = r.get("data")
            if not rdata:
                continue

            if rtype == 12:  # PTR
                if isinstance(rdata, str) and rdata not in self._ptr_records:
                    self._ptr_records.append(rdata)
                    self._sender_ips[rdata] = sender_ip
            elif rtype == 33:  # SRV
                if isinstance(rdata, dict):
                    self._srv_records[rname] = rdata
                    self._sender_ips[rname] = sender_ip
            elif rtype == 16:  # TXT
                if isinstance(rdata, dict):
                    self._txt_records[rname] = rdata
                    self._sender_ips[rname] = sender_ip
            elif rtype == 1:  # A
                if isinstance(rdata, str):
                    self._a_records[rname] = rdata

    def get_devices(self) -> List[DiscoveredDevice]:
        """Synthesizes collected records into DiscoveredDevice instances."""
        devices: Dict[str, DiscoveredDevice] = {}

        # 1. Correlate by PTR services
        for ptr in self._ptr_records:
            sender_ip = self._sender_ips.get(ptr, "")
            srv = self._srv_records.get(ptr, {})
            txt = self._txt_records.get(ptr, {})

            port = srv.get("port", 5555)
            target = srv.get("target", "")
            ip = self._a_records.get(target) or sender_ip
            if not ip:
                continue

            # Model & hostname heuristics
            hostname = target or ptr.split(".")[0]
            model = txt.get("model", "") or txt.get("device", "") or ptr.split(".")[0]

            devices[ip] = DiscoveredDevice(
                ip=ip,
                port=port,
                hostname=hostname,
                device_type="android_tv",
                model=model,
                source="mdns",
                raw_info={
                    "service": ptr,
                    "srv": srv,
                    "txt": txt,
                    "target": target,
                },
            )

        # 2. Correlate any orphan SRV records
        for srv_name, srv in self._srv_records.items():
            target = srv.get("target", "")
            sender_ip = self._sender_ips.get(srv_name, "")
            ip = self._a_records.get(target) or sender_ip
            if ip and ip not in devices:
                port = srv.get("port", 5555)
                txt = self._txt_records.get(srv_name, {})
                model = txt.get("model", "") or srv_name.split(".")[0]
                devices[ip] = DiscoveredDevice(
                    ip=ip,
                    port=port,
                    hostname=target or srv_name.split(".")[0],
                    device_type="android_tv",
                    model=model,
                    source="mdns",
                    raw_info={"service": srv_name, "srv": srv, "txt": txt},
                )

        # 3. If no PTR/SRV correlated but we received mDNS datagrams with sender IP
        if not devices and self._ip_sources:
            for ip in self._ip_sources:
                devices[ip] = DiscoveredDevice(
                    ip=ip,
                    port=5555,
                    hostname="",
                    device_type="android_tv",
                    model="Android TV Device",
                    source="mdns",
                    raw_info={},
                )

        return list(devices.values())


def discover_mdns(
    timeout: float = 3.0,
    service_types: Optional[List[str]] = None,
    sock: Optional[socket.socket] = None,
) -> List[DiscoveredDevice]:
    """
    Executes pure Python stdlib mDNS discovery for Android TV ADB services.
    Uses a dual-socket pool (ephemeral unicast + multicast listener 5353)
    or accepts an optional injected mock socket for offline test isolation.
    """
    if not service_types:
        service_types = [ADB_SERVICE, ADB_TLS_SERVICE]

    sockets: List[socket.socket] = []
    close_sockets = False

    if sock is not None:
        sockets.append(sock)
    else:
        close_sockets = True
        # Socket 1: Ephemeral sender / direct unicast receiver
        try:
            s_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s_send.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s_send.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
                s_send.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            except OSError:
                pass
            s_send.bind(("", 0))
            s_send.setblocking(False)
            sockets.append(s_send)
        except OSError:
            pass

        # Socket 2: Multicast listener (port 5353) with graceful fallback
        try:
            s_listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    s_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except (AttributeError, OSError):
                    pass
            s_listen.bind(("", MDNS_PORT))
            try:
                mreq = struct.pack("4s4s", socket.inet_aton(MDNS_GROUP), socket.inet_aton("0.0.0.0"))
                s_listen.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            except OSError:
                pass
            s_listen.setblocking(False)
            sockets.append(s_listen)
        except OSError:
            # Fall back to ephemeral socket alone (e.g. Windows port 5353 conflicts)
            pass

    if not sockets:
        return []

    try:
        # Transmit queries for all service types
        sender = sockets[0]
        for st in service_types:
            q_qm = build_mdns_query(st, unicast_response=False)
            q_qu = build_mdns_query(st, unicast_response=True)
            try:
                sender.sendto(q_qm, (MDNS_GROUP, MDNS_PORT))
                sender.sendto(q_qu, (MDNS_GROUP, MDNS_PORT))
            except OSError:
                continue

        aggregator = MdnsDeviceAggregator()
        deadline = time.time() + timeout

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            try:
                rlist, _, _ = select.select(sockets, [], [], min(remaining, 0.5))
            except (OSError, ValueError):
                break

            if not rlist:
                continue

            for s in rlist:
                try:
                    data, addr = s.recvfrom(4096)
                    records = parse_dns_response(data)
                    if records:
                        aggregator.ingest_records(records, addr[0])
                except (BlockingIOError, OSError, socket.error):
                    continue

        return aggregator.get_devices()

    finally:
        if close_sockets:
            for s in sockets:
                try:
                    s.close()
                except OSError:
                    pass


# ============================================================================
# 3. SSDP Constants & Packet Utilities (UPnP 1.1 Specification)
# ============================================================================

SSDP_MULTICAST_ADDR = "239.255.255.250"
SSDP_PORT = 1900

SSDP_SEARCH_TARGETS = [
    "urn:dial-multiscreen-org:service:dial:1",
    "upnp:rootdevice",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "ssdp:all",
]


def build_msearch_packet(st: str, mx: int = 2) -> bytes:
    """
    Constructs an RFC-compliant UPnP M-SEARCH HTTP over UDP datagram.
    Uses strict CRLF delimiters and required UPnP headers.
    """
    lines = [
        "M-SEARCH * HTTP/1.1",
        f"HOST: {SSDP_MULTICAST_ADDR}:{SSDP_PORT}",
        'MAN: "ssdp:discover"',
        f"MX: {mx}",
        f"ST: {st}",
        "USER-AGENT: OpenTV/1.0 UPnP/1.1",
        "",
        "",
    ]
    return "\r\n".join(lines).encode("utf-8")


def parse_ssdp_headers(raw_data: bytes | str) -> Tuple[str, Dict[str, str]]:
    """
    Parses a raw SSDP HTTP over UDP response into status line and headers dict.
    Headers are normalized to UPPERCASE keys for case-insensitive lookup.
    """
    if isinstance(raw_data, bytes):
        text = raw_data.decode("utf-8", errors="replace")
    else:
        text = str(raw_data)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", {}

    status_line = lines[0]
    headers: Dict[str, str] = {}

    for line in lines[1:]:
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        headers[key.strip().upper()] = val.strip()

    return status_line, headers


def identify_ssdp_device(
    headers: Dict[str, str],
    ip: str,
    descriptor_info: Optional[Dict[str, str]] = None,
) -> DiscoveredDevice:
    """
    Analyzes SSDP response headers and optional UPnP XML descriptor metadata
    to identify the device manufacturer, model, and platform type.
    """
    server = headers.get("SERVER", "")
    st = headers.get("ST", "")
    usn = headers.get("USN", "")
    location = headers.get("LOCATION", "")

    desc = descriptor_info or {}
    friendly_name = desc.get("friendlyName", "")
    mfg = desc.get("manufacturer", "")
    model_name = desc.get("modelName", "")
    model_num = desc.get("modelNumber", "")

    combined_text = (
        f"{server} {st} {usn} {location} {friendly_name} {mfg} {model_name} {model_num}"
    ).lower()

    device_type = "unknown"
    model = friendly_name or model_name or "Unknown Smart TV"
    hostname = ""

    # Disqualify Non-Android Devices
    if "roku" in combined_text or "roku" in server.lower():
        device_type = "roku"
        model = friendly_name or "Roku Streaming Device"
    elif "samsung" in combined_text or "tizen" in combined_text or "sec_hhp_" in combined_text:
        device_type = "samsung_tizen"
        model = friendly_name or "Samsung Smart TV"
    elif "webos" in combined_text or "lg electronics" in combined_text:
        device_type = "lg_webos"
        model = friendly_name or "LG Smart TV"
    elif "sonos" in combined_text:
        device_type = "sonos"
        model = friendly_name or "Sonos Audio Device"
    elif "apple" in combined_text or "airplay" in combined_text:
        device_type = "apple_device"
        model = friendly_name or "Apple Device"

    # Identify Android / Google TV Brands
    elif (
        "eureka" in combined_text
        or "chromecast" in combined_text
        or "sabrina" in combined_text
        or "boreal" in combined_text
        or "google" in mfg.lower()
    ):
        device_type = "google_tv"
        model = friendly_name or "Chromecast with Google TV"
    elif "sony" in combined_text or "bravia" in combined_text or "kd-" in combined_text or "xr-" in combined_text:
        device_type = "android_tv"
        model = friendly_name or (f"Sony BRAVIA {model_name}".strip() if model_name else "Sony BRAVIA TV")
    elif "nvidia" in combined_text or "shield" in combined_text:
        device_type = "android_tv"
        model = friendly_name or "Nvidia SHIELD TV"
    elif "tcl" in combined_text or "beyondtv" in combined_text or "tte" in combined_text or "iffalcon" in combined_text:
        device_type = "android_tv"
        model = friendly_name or "TCL Android TV"
    elif "firetv" in combined_text or "amazon-firetv" in combined_text or "aft" in combined_text:
        device_type = "fire_tv"
        model = friendly_name or "Amazon Fire TV"
    elif "xiaomi" in combined_text or "mitv" in combined_text or "patchwall" in combined_text:
        device_type = "android_tv"
        model = friendly_name or "Xiaomi Mi TV"
    elif "philips" in combined_text or "tp vision" in combined_text or "tpv" in combined_text or "droidtv" in combined_text:
        device_type = "android_tv"
        model = friendly_name or "Philips Android TV"
    elif "hisense" in combined_text or "jamdeo" in combined_text:
        device_type = "android_tv"
        model = friendly_name or "Hisense Android TV"
    elif "dial" in st.lower() or "dial" in combined_text or ":8008" in location:
        device_type = "smart_tv"
        model = friendly_name or "Smart TV (DIAL)"
    elif "mediarenderer" in combined_text:
        device_type = "smart_tv"
        model = friendly_name or "Smart TV / Media Renderer"

    return DiscoveredDevice(
        ip=ip,
        port=5555,
        hostname=hostname,
        device_type=device_type,
        model=model,
        source="ssdp",
        raw_info={
            "headers": headers,
            "st": st,
            "location": location,
            "server": server,
            "usn": usn,
            "descriptor": desc,
        },
    )


def fetch_ssdp_descriptor(location_url: str, timeout: float = 0.5) -> Dict[str, str]:
    """
    Fetches the UPnP device description XML from LOCATION URL and parses
    standard UPnP metadata fields (friendlyName, manufacturer, modelName, modelNumber).
    Returns an empty dict if the network fetch fails, times out, or contains invalid XML.
    """
    if not location_url or not (location_url.startswith("http://") or location_url.startswith("https://")):
        return {}

    try:
        req = urllib.request.Request(
            location_url,
            headers={"User-Agent": "OpenTV/1.0 UPnP/1.1", "Accept": "text/xml, application/xml"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_bytes = resp.read(65536)  # Cap read to 64KB

        root = ET.fromstring(xml_bytes)
        desc_info: Dict[str, str] = {}
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("friendlyName", "manufacturer", "modelName", "modelNumber", "deviceType", "UDN"):
                if elem.text and tag not in desc_info:
                    desc_info[tag] = elem.text.strip()
        return desc_info
    except Exception:
        return {}


def discover_ssdp(
    targets: Optional[List[str]] = None,
    timeout: float = 3.0,
    mx: int = 2,
    resolve_descriptors: bool = False,
    sock: Optional[socket.socket] = None,
) -> List[DiscoveredDevice]:
    """
    Executes SSDP M-SEARCH discovery over UDP multicast (239.255.255.250:1900).
    Accepts an optional pre-configured or mocked socket for 100% test isolation.
    """
    if targets is None:
        targets = SSDP_SEARCH_TARGETS

    close_socket = False
    if sock is None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except (AttributeError, OSError):
                    pass
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            except OSError:
                pass
            sock.bind(("", 0))
            sock.setblocking(False)
            close_socket = True
        except OSError:
            return []

    try:
        # 1. Broadcast M-SEARCH for each target
        for st in targets:
            packet = build_msearch_packet(st, mx=mx)
            try:
                sock.sendto(packet, (SSDP_MULTICAST_ADDR, SSDP_PORT))
            except OSError:
                continue

        # 2. Collect responses with select
        devices_by_ip: Dict[str, DiscoveredDevice] = {}
        deadline = time.time() + timeout

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            try:
                r, _, _ = select.select([sock], [], [], min(remaining, 0.5))
            except (OSError, ValueError):
                break

            if not r:
                continue

            try:
                data, addr = sock.recvfrom(65535)
            except (BlockingIOError, OSError, socket.error):
                continue

            ip = addr[0]
            status_line, headers = parse_ssdp_headers(data)
            if not headers:
                continue

            desc_info: Dict[str, str] = {}
            location = headers.get("LOCATION", "")
            if resolve_descriptors and location:
                desc_info = fetch_ssdp_descriptor(location, timeout=min(remaining, 0.5))

            device = identify_ssdp_device(headers, ip, desc_info)
            if ip not in devices_by_ip:
                devices_by_ip[ip] = device
            else:
                existing = devices_by_ip[ip]
                if (existing.model.startswith("Unknown") or existing.model.startswith("Smart TV")) and not (device.model.startswith("Unknown") or device.model.startswith("Smart TV")):
                    existing.model = device.model
                elif existing.model.startswith("Unknown") and not device.model.startswith("Unknown"):
                    existing.model = device.model

                android_types = {"android_tv", "google_tv", "fire_tv"}
                if existing.device_type in ("unknown", "smart_tv") and device.device_type in android_types:
                    existing.device_type = device.device_type
                elif existing.device_type == "unknown" and device.device_type != "unknown":
                    existing.device_type = device.device_type

                existing.raw_info.setdefault("additional_responses", []).append(device.raw_info)

        return list(devices_by_ip.values())

    finally:
        if close_socket and sock:
            try:
                sock.close()
            except OSError:
                pass


# ============================================================================
# 4. Deduplication & Unified Discovery
# ============================================================================

def deduplicate_devices(
    mdns_devices: List[DiscoveredDevice],
    ssdp_devices: List[DiscoveredDevice],
) -> List[DiscoveredDevice]:
    """
    Merges mDNS and SSDP findings into a unified list keyed by IPv4 address.
    Orders output numerically by IPv4 octets.
    """
    by_ip: Dict[str, DiscoveredDevice] = {}

    for m in mdns_devices:
        by_ip[m.ip] = m

    for s in ssdp_devices:
        if s.ip in by_ip:
            m = by_ip[s.ip]
            best_port = m.port if m.port and m.port != 5555 else (s.port or 5555)
            best_hostname = m.hostname or s.hostname
            if (
                s.model
                and not s.model.startswith("Unknown")
                and not s.model.startswith("Smart TV")
                and (not m.model or m.model.startswith("Android"))
            ):
                best_model = s.model
            else:
                best_model = m.model or s.model

            if s.device_type in ("google_tv", "fire_tv"):
                best_type = s.device_type
            elif m.device_type == "android_tv":
                best_type = "android_tv"
            else:
                best_type = m.device_type or s.device_type

            merged_raw = {
                "mdns": m.raw_info,
                "ssdp": s.raw_info,
            }

            by_ip[s.ip] = DiscoveredDevice(
                ip=s.ip,
                port=best_port,
                hostname=best_hostname,
                device_type=best_type,
                model=best_model,
                source="mdns+ssdp",
                raw_info=merged_raw,
            )
        else:
            by_ip[s.ip] = s

    def ip_sort_key(dev: DiscoveredDevice) -> List[int]:
        try:
            return [int(x) for x in dev.ip.split(".")]
        except ValueError:
            return [0, 0, 0, 0]

    return sorted(by_ip.values(), key=ip_sort_key)


def discover_devices(
    timeout: float = 3.0,
    filter_android: bool = True,
    targets: Optional[List[str]] = None,
    resolve_descriptors: bool = False,
    methods: Sequence[str] = ("mdns", "ssdp"),
) -> List[DiscoveredDevice]:
    """
    Unified high-level entrypoint for local TV auto-discovery.
    Runs mDNS and SSDP queries in parallel or sequence, reconciles and deduplicates results.
    """
    mdns_list: List[DiscoveredDevice] = []
    if "mdns" in methods:
        try:
            mdns_list = discover_mdns(timeout=timeout)
        except Exception:
            mdns_list = []

    ssdp_list: List[DiscoveredDevice] = []
    if "ssdp" in methods:
        try:
            ssdp_list = discover_ssdp(
                targets=targets,
                timeout=timeout,
                resolve_descriptors=resolve_descriptors,
            )
        except Exception:
            ssdp_list = []

    all_devices = deduplicate_devices(mdns_list, ssdp_list)

    if filter_android:
        return [d for d in all_devices if d.is_android]
    return all_devices
