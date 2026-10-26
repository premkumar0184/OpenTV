"""
tests/test_discovery.py
Milestone 3: Local Network Android TV Auto-Discovery Test Suite.

Verifies:
- mDNS (RFC 6762 / 6763) wire query construction and binary response parsing
- DNS label decompression (0xc0 pointers), chained pointers, loop protection, and boundary checks
- SSDP / UPnP M-SEARCH packet crafting and case-insensitive header parsing
- Android TV signature heuristics (Bravia, CCwGTV, Shield, Fire TV, TCL, Xiaomi, etc.)
- Non-TV / non-Android disqualification (Roku, Samsung Tizen, LG webOS, Sonos, Apple)
- Deduplication and reconciliation across mDNS and SSDP by numeric IPv4 octets
- Error handling, timeouts, malformed buffers, and network exceptions
- CLI integration (opentv connect --discover, opentv discover, table formatter)
- TUI integration (_run_interactive_network_scan, fallback wizard scan)

STRICTLY ZERO EXTERNAL PIP DEPENDENCIES. 100% MOCKED NETWORK CALLS.
"""
from __future__ import annotations

import io
import json
import select
import socket
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Ensure companion is on sys.path for direct module test execution
REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANION_DIR = REPO_ROOT / "companion"
if COMPANION_DIR.exists() and str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))

from opentv.core.discovery import (
    ADB_SERVICE,
    ADB_TLS_SERVICE,
    MDNS_GROUP,
    MDNS_PORT,
    SSDP_MULTICAST_ADDR,
    SSDP_PORT,
    DiscoveredDevice,
    MdnsDeviceAggregator,
    build_mdns_query,
    build_msearch_packet,
    deduplicate_devices,
    discover_devices,
    discover_mdns,
    discover_ssdp,
    fetch_ssdp_descriptor,
    identify_ssdp_device,
    parse_dns_name,
    parse_dns_response,
    parse_ssdp_headers,
)
from opentv.cli import (
    EXIT_DEVICE_NOT_FOUND,
    EXIT_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE,
    create_parser,
    format_device_table,
    handle_connect,
    handle_discover,
    main as cli_main,
)
from opentv.tui.app import KeyCode, KeyEvent, OpenTVApp


# ============================================================================
# 1. DiscoveredDevice Data Model Tests
# ============================================================================

class TestDiscoveredDeviceModel(unittest.TestCase):
    def test_device_defaults_and_address(self):
        dev = DiscoveredDevice(ip="192.168.1.100")
        self.assertEqual(dev.ip, "192.168.1.100")
        self.assertEqual(dev.port, 5555)
        self.assertEqual(dev.address, "192.168.1.100:5555")
        self.assertEqual(dev.device_type, "unknown")
        self.assertEqual(dev.source, "unknown")
        self.assertFalse(dev.is_android)

    def test_device_is_android_heuristics(self):
        dev_mdns = DiscoveredDevice(ip="192.168.1.100", source="mdns")
        self.assertTrue(dev_mdns.is_android)

        dev_gtv = DiscoveredDevice(ip="192.168.1.101", device_type="google_tv", source="ssdp")
        self.assertTrue(dev_gtv.is_android)

        dev_fire = DiscoveredDevice(ip="192.168.1.102", device_type="fire_tv", source="ssdp")
        self.assertTrue(dev_fire.is_android)

        dev_atv = DiscoveredDevice(ip="192.168.1.103", device_type="android_tv", source="ssdp")
        self.assertTrue(dev_atv.is_android)

        dev_roku = DiscoveredDevice(ip="192.168.1.104", device_type="roku", source="ssdp")
        self.assertFalse(dev_roku.is_android)

    def test_display_name_and_serialization(self):
        dev = DiscoveredDevice(
            ip="192.168.1.50",
            port=5555,
            model="Sony BRAVIA 4K",
            device_type="android_tv",
            source="mdns+ssdp",
            raw_info={"test": 123},
        )
        self.assertIn("Sony BRAVIA 4K", dev.display_name)
        self.assertIn("192.168.1.50:5555", dev.display_name)
        self.assertIn("mdns+ssdp", dev.display_name)

        d = dev.to_dict()
        self.assertEqual(d["ip"], "192.168.1.50")
        self.assertEqual(d["port"], 5555)
        self.assertEqual(d["model"], "Sony BRAVIA 4K")
        self.assertEqual(d["raw_info"]["test"], 123)
        self.assertTrue(d["is_android"])


# ============================================================================
# 2. mDNS Packet Crafting Tests
# ============================================================================

class TestMdnsPacketCrafting(unittest.TestCase):
    def test_build_mdns_query_adb_tcp(self):
        packet = build_mdns_query("_adb._tcp.local")
        self.assertEqual(len(packet), 33)
        # Header: ID=0, Flags=0, QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
        header = struct.unpack("!HHHHHH", packet[:12])
        self.assertEqual(header, (0, 0, 1, 0, 0, 0))

        # Question name: \x04_adb\x04_tcp\x05local\x00
        expected_qname = b"\x04_adb\x04_tcp\x05local\x00"
        self.assertEqual(packet[12:12 + len(expected_qname)], expected_qname)

        # QTYPE=12 (PTR), QCLASS=0x0001 (QM)
        qtype, qclass = struct.unpack("!HH", packet[-4:])
        self.assertEqual(qtype, 12)
        self.assertEqual(qclass, 0x0001)

    def test_build_mdns_query_unicast_qu(self):
        packet = build_mdns_query("_adb._tcp.local", unicast_response=True)
        qtype, qclass = struct.unpack("!HH", packet[-4:])
        self.assertEqual(qtype, 12)
        self.assertEqual(qclass, 0x8001)

    def test_build_mdns_query_tls_connect(self):
        packet = build_mdns_query(ADB_TLS_SERVICE)
        self.assertIn(b"_adb-tls-connect", packet)
        self.assertIn(b"_tcp", packet)
        self.assertIn(b"local", packet)


# ============================================================================
# 3. mDNS Name & Response Parsing Tests
# ============================================================================

class TestMdnsResponseParsing(unittest.TestCase):
    def test_parse_dns_name_uncompressed(self):
        raw = b"\x03foo\x03bar\x05local\x00"
        name, offset = parse_dns_name(raw, 0)
        self.assertEqual(name, "foo.bar.local")
        self.assertEqual(offset, len(raw))

    def test_parse_dns_name_pointer_decompression(self):
        # Header (12 bytes) + original name at offset 12 ("local")
        # Then name at offset 20: "tv" + pointer to offset 12 -> "tv.local"
        prefix = b"\x00" * 12 + b"\x05local\x00"
        packet = prefix + b"\x02tv\xc0\x0c"
        name, offset = parse_dns_name(packet, 19)
        self.assertEqual(name, "tv.local")
        self.assertEqual(offset, len(packet))

    def test_parse_dns_name_chained_pointers(self):
        # offset 0: "org"
        # offset 5: "example" + pointer to 0 -> "example.org"
        # offset 15: "tv" + pointer to 5 -> "tv.example.org"
        buf = bytearray(30)
        buf[0:5] = b"\x03org\x00"
        buf[5:15] = b"\x07example\xc0\x00"
        buf[15:20] = b"\x02tv\xc0\x05"

        name, _ = parse_dns_name(bytes(buf), 15)
        self.assertEqual(name, "tv.example.org")

    def test_parse_dns_name_pointer_loop_guard(self):
        # Pointer pointing to itself (infinite cycle)
        buf = bytearray(20)
        buf[0] = 0xC0
        buf[1] = 0x00  # Jump to offset 0!
        name, _ = parse_dns_name(bytes(buf), 0)
        # Should terminate safely without infinite recursion
        self.assertEqual(name, "")

    def test_parse_dns_name_out_of_bounds_pointer(self):
        buf = bytes([0xC0, 0xFF])  # offset 255 in a 2-byte packet
        name, offset = parse_dns_name(buf, 0)
        self.assertEqual(name, "")

    def test_parse_dns_response_full_synthetic_packet(self):
        # Synthesize a complete mDNS response:
        # Header: ID=0, Flags=0x8400 (Response, Authoritative), QD=0, AN=4, NS=0, AR=0
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 4, 0, 0)

        # We'll place records:
        # 1. PTR: _adb._tcp.local -> BRAVIA._adb._tcp.local
        # 2. SRV: BRAVIA._adb._tcp.local -> port 5555, target bravia.local
        # 3. TXT: BRAVIA._adb._tcp.local -> model=BRAVIA 4K, device=bravia_atv
        # 4. A:   bravia.local -> 192.168.1.120
        # Let's construct raw bytes:
        data = bytearray(header)

        # Helper to append label
        def append_name(b: bytearray, name_str: str) -> int:
            pos = len(b)
            for part in name_str.split("."):
                bp = part.encode("utf-8")
                b.append(len(bp))
                b.extend(bp)
            b.append(0)
            return pos

        # Record 1: PTR
        append_name(data, "_adb._tcp.local")
        ptr_target_pos = len(data) + 10
        # Type=12 (PTR), Class=1, TTL=120, RDLENGTH
        # RDATA will be BRAVIA._adb._tcp.local
        rdata_ptr = bytearray()
        append_name(rdata_ptr, "BRAVIA._adb._tcp.local")
        data.extend(struct.pack("!HHIH", 12, 1, 120, len(rdata_ptr)))
        data.extend(rdata_ptr)

        # Record 2: SRV
        append_name(data, "BRAVIA._adb._tcp.local")
        rdata_srv = struct.pack("!HHH", 0, 0, 5555) + b"\x06bravia\x05local\x00"
        data.extend(struct.pack("!HHIH", 33, 1, 120, len(rdata_srv)))
        data.extend(rdata_srv)

        # Record 3: TXT
        append_name(data, "BRAVIA._adb._tcp.local")
        t1 = b"model=BRAVIA 4K"
        t2 = b"device=bravia_atv"
        rdata_txt = bytes([len(t1)]) + t1 + bytes([len(t2)]) + t2
        data.extend(struct.pack("!HHIH", 16, 1, 120, len(rdata_txt)))
        data.extend(rdata_txt)

        # Record 4: A
        append_name(data, "bravia.local")
        rdata_a = socket.inet_aton("192.168.1.120")
        data.extend(struct.pack("!HHIH", 1, 1, 120, len(rdata_a)))
        data.extend(rdata_a)

        records = parse_dns_response(bytes(data))
        self.assertEqual(len(records), 4)

        # Feed to aggregator
        agg = MdnsDeviceAggregator()
        agg.ingest_records(records, "192.168.1.120")
        devices = agg.get_devices()
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev.ip, "192.168.1.120")
        self.assertEqual(dev.port, 5555)
        self.assertEqual(dev.model, "BRAVIA 4K")
        self.assertEqual(dev.hostname, "bravia.local")
        self.assertEqual(dev.source, "mdns")
        self.assertTrue(dev.is_android)

    def test_aggregator_fallback_to_sender_ip(self):
        agg = MdnsDeviceAggregator()
        # PTR record with no matching A record
        records = [
            {"type": 12, "name": "_adb._tcp.local", "data": "shield._adb._tcp.local"},
            {"type": 33, "name": "shield._adb._tcp.local", "data": {"port": 5555, "target": "shield.local"}},
            {"type": 16, "name": "shield._adb._tcp.local", "data": {"model": "Nvidia Shield"}},
        ]
        agg.ingest_records(records, "192.168.1.75")
        devices = agg.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.75")
        self.assertEqual(devices[0].model, "Nvidia Shield")


# ============================================================================
# 4. SSDP Packet Crafting & Header Parsing Tests
# ============================================================================

class TestSsdpPacketCrafting(unittest.TestCase):
    def test_build_msearch_packet_format(self):
        packet = build_msearch_packet("urn:dial-multiscreen-org:service:dial:1", mx=2)
        text = packet.decode("utf-8")
        self.assertTrue(text.startswith("M-SEARCH * HTTP/1.1\r\n"))
        self.assertIn("HOST: 239.255.255.250:1900\r\n", text)
        self.assertIn('MAN: "ssdp:discover"\r\n', text)
        self.assertIn("MX: 2\r\n", text)
        self.assertIn("ST: urn:dial-multiscreen-org:service:dial:1\r\n", text)
        self.assertTrue(text.endswith("\r\n\r\n"))

    def test_parse_ssdp_headers_case_insensitivity(self):
        raw_resp = (
            "HTTP/1.1 200 OK\r\n"
            "sErVeR: Linux/4.9.113 UPnP/1.0 Sony-Bravia/2.0\r\n"
            "LOCATION: http://192.168.1.55:8008/ssdp/desc.xml\r\n"
            "st: urn:dial-multiscreen-org:service:dial:1\r\n"
            "Usn: uuid:12345678-abcd::urn:dial-multiscreen-org:service:dial:1\r\n"
            "\r\n"
        )
        status, headers = parse_ssdp_headers(raw_resp)
        self.assertEqual(status, "HTTP/1.1 200 OK")
        self.assertIn("SERVER", headers)
        self.assertIn("LOCATION", headers)
        self.assertIn("ST", headers)
        self.assertIn("USN", headers)
        self.assertEqual(headers["LOCATION"], "http://192.168.1.55:8008/ssdp/desc.xml")


# ============================================================================
# 5. SSDP Device Identification & Heuristics Tests
# ============================================================================

class TestSsdpDeviceIdentification(unittest.TestCase):
    def test_identify_sony_bravia(self):
        headers = {
            "SERVER": "Linux/4.9.113 UPnP/1.0 Sony-Bravia/2.0",
            "ST": "urn:dial-multiscreen-org:service:dial:1",
            "LOCATION": "http://192.168.1.50:8008/ssdp/desc.xml",
        }
        dev = identify_ssdp_device(headers, "192.168.1.50")
        self.assertEqual(dev.device_type, "android_tv")
        self.assertIn("Sony BRAVIA", dev.model)
        self.assertTrue(dev.is_android)

    def test_identify_chromecast_google_tv(self):
        headers = {
            "SERVER": "Eureka Dongle",
            "ST": "urn:dial-multiscreen-org:service:dial:1",
            "LOCATION": "http://192.168.1.60:8008/ssdp/desc.xml",
        }
        dev = identify_ssdp_device(headers, "192.168.1.60")
        self.assertEqual(dev.device_type, "google_tv")
        self.assertTrue(dev.is_android)

    def test_identify_fire_tv(self):
        headers = {
            "SERVER": "Amazon-FireTV/1.0 UPnP/1.0",
            "ST": "upnp:rootdevice",
            "LOCATION": "http://192.168.1.70:8080/desc.xml",
        }
        dev = identify_ssdp_device(headers, "192.168.1.70")
        self.assertEqual(dev.device_type, "fire_tv")
        self.assertTrue(dev.is_android)

    def test_identify_tcl_and_xiaomi_and_shield(self):
        dev_tcl = identify_ssdp_device({"SERVER": "TCL BeyondTV UPnP"}, "192.168.1.81")
        self.assertEqual(dev_tcl.device_type, "android_tv")
        self.assertTrue(dev_tcl.is_android)

        dev_mi = identify_ssdp_device({"SERVER": "Xiaomi MiTV UPnP"}, "192.168.1.82")
        self.assertEqual(dev_mi.device_type, "android_tv")
        self.assertTrue(dev_mi.is_android)

        dev_shield = identify_ssdp_device({"SERVER": "NVIDIA SHIELD UPnP"}, "192.168.1.83")
        self.assertEqual(dev_shield.device_type, "android_tv")
        self.assertTrue(dev_shield.is_android)

    def test_disqualify_non_android_devices(self):
        # Roku
        dev_roku = identify_ssdp_device({"SERVER": "Roku/11.5 UPnP/1.0"}, "192.168.1.90")
        self.assertEqual(dev_roku.device_type, "roku")
        self.assertFalse(dev_roku.is_android)

        # Samsung Tizen
        dev_tizen = identify_ssdp_device({"SERVER": "SHP, SEC_HHP_[TV] Samsung, UPnP/1.0"}, "192.168.1.91")
        self.assertEqual(dev_tizen.device_type, "samsung_tizen")
        self.assertFalse(dev_tizen.is_android)

        # LG webOS
        dev_webos = identify_ssdp_device({"SERVER": "webOS TV/7.0 UPnP/1.0"}, "192.168.1.92")
        self.assertEqual(dev_webos.device_type, "lg_webos")
        self.assertFalse(dev_webos.is_android)

        # Sonos
        dev_sonos = identify_ssdp_device({"SERVER": "Sonos/55.1 UPnP/1.0"}, "192.168.1.93")
        self.assertEqual(dev_sonos.device_type, "sonos")
        self.assertFalse(dev_sonos.is_android)

        # Apple
        dev_apple = identify_ssdp_device({"SERVER": "AirPlay/1.0 Apple"}, "192.168.1.94")
        self.assertEqual(dev_apple.device_type, "apple_device")
        self.assertFalse(dev_apple.is_android)

    def test_fetch_ssdp_descriptor_mock(self):
        xml_content = b"""<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0">
          <device>
            <friendlyName>Living Room Sony TV</friendlyName>
            <manufacturer>Sony Corporation</manufacturer>
            <modelName>XR-65A80J</modelName>
            <modelNumber>A80J</modelNumber>
          </device>
        </root>"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = xml_content
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            info = fetch_ssdp_descriptor("http://192.168.1.50:8008/ssdp/desc.xml")
            self.assertEqual(info["friendlyName"], "Living Room Sony TV")
            self.assertEqual(info["manufacturer"], "Sony Corporation")
            self.assertEqual(info["modelName"], "XR-65A80J")


# ============================================================================
# 6. Deduplication & Reconciliation Tests
# ============================================================================

class TestDeduplicationAndReconciliation(unittest.TestCase):
    def test_deduplicate_merges_mdns_and_ssdp_same_ip(self):
        m_dev = DiscoveredDevice(
            ip="192.168.1.50",
            port=5555,
            hostname="bravia.local",
            device_type="android_tv",
            model="Android Device",
            source="mdns",
            raw_info={"mdns_data": True},
        )
        s_dev = DiscoveredDevice(
            ip="192.168.1.50",
            port=5555,
            hostname="",
            device_type="android_tv",
            model="Sony BRAVIA 4K XR-65A80J",
            source="ssdp",
            raw_info={"ssdp_data": True},
        )
        merged = deduplicate_devices([m_dev], [s_dev])
        self.assertEqual(len(merged), 1)
        res = merged[0]
        self.assertEqual(res.ip, "192.168.1.50")
        self.assertEqual(res.source, "mdns+ssdp")
        self.assertEqual(res.hostname, "bravia.local")
        self.assertEqual(res.model, "Sony BRAVIA 4K XR-65A80J")
        self.assertTrue("mdns" in res.raw_info)
        self.assertTrue("ssdp" in res.raw_info)

    def test_deduplicate_sorts_by_numeric_ip(self):
        dev1 = DiscoveredDevice(ip="192.168.1.100")
        dev2 = DiscoveredDevice(ip="192.168.1.20")
        dev3 = DiscoveredDevice(ip="192.168.1.2")
        merged = deduplicate_devices([dev1, dev2, dev3], [])
        ips = [d.ip for d in merged]
        self.assertEqual(ips, ["192.168.1.2", "192.168.1.20", "192.168.1.100"])

    def test_deduplicate_devices_preserves_android_over_roku(self):
        """Ensures mDNS android_tv classification is preserved over non-Android SSDP type."""
        m_dev = DiscoveredDevice(ip="192.168.1.50", device_type="android_tv", source="mdns")
        s_dev = DiscoveredDevice(ip="192.168.1.50", device_type="roku", source="ssdp")
        merged = deduplicate_devices([m_dev], [s_dev])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].device_type, "android_tv")
        self.assertTrue(merged[0].is_android)

    def test_deduplicate_devices_does_not_downgrade_to_smart_tv_dial(self):
        """Ensures mDNS Android TV Device model is not downgraded to SSDP Smart TV (DIAL)."""
        m_dev = DiscoveredDevice(
            ip="192.168.1.50", model="Android TV Device", device_type="android_tv", source="mdns"
        )
        s_dev = DiscoveredDevice(
            ip="192.168.1.50", model="Smart TV (DIAL)", device_type="smart_tv", source="ssdp"
        )
        merged = deduplicate_devices([m_dev], [s_dev])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].model, "Android TV Device")


# ============================================================================
# 7. Mock Network Discovery Loops (Zero Network Calls)
# ============================================================================

class TestMockNetworkDiscovery(unittest.TestCase):
    @patch("select.select")
    def test_discover_mdns_mock_socket(self, mock_select):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = 1

        # Prepare synthetic response packet
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        qname = b"\x04_adb\x04_tcp\x05local\x00"
        ptr_target = b"\x07myatv4k\x04_adb\x04_tcp\x05local\x00"
        record = qname + struct.pack("!HHIH", 12, 1, 120, len(ptr_target)) + ptr_target
        packet = header + record

        def fake_recvfrom(*args):
            import time
            time.sleep(0.02)
            return (packet, ("192.168.1.155", 5353))

        mock_sock.recvfrom.side_effect = fake_recvfrom
        mock_select.return_value = ([mock_sock], [], [])

        devices = discover_mdns(timeout=0.01, sock=mock_sock)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.155")
        self.assertEqual(devices[0].source, "mdns")
        self.assertTrue(mock_sock.sendto.called)

    @patch("select.select")
    def test_discover_ssdp_mock_socket(self, mock_select):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = 2

        resp = (
            "HTTP/1.1 200 OK\r\n"
            "SERVER: Eureka Dongle\r\n"
            "LOCATION: http://192.168.1.180:8008/ssdp/desc.xml\r\n"
            "ST: urn:dial-multiscreen-org:service:dial:1\r\n"
            "\r\n"
        ).encode("utf-8")

        def fake_recvfrom(*args):
            import time
            time.sleep(0.02)
            return (resp, ("192.168.1.180", 1900))

        mock_sock.recvfrom.side_effect = fake_recvfrom
        mock_select.return_value = ([mock_sock], [], [])

        devices = discover_ssdp(timeout=0.01, sock=mock_sock)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.180")
        self.assertEqual(devices[0].device_type, "google_tv")
        self.assertTrue(devices[0].is_android)

    @patch("select.select")
    def test_discover_ssdp_survives_transient_socket_errors(self, mock_select):
        """Ensures discover_ssdp does not abort loop on transient BlockingIOError or ConnectionResetError."""
        valid_pkt = b"HTTP/1.1 200 OK\r\nSERVER: Sony Bravia\r\n\r\n"
        errors = [BlockingIOError("EAGAIN"), ConnectionResetError("WSAECONNRESET"), OSError("Interrupted")]
        call_idx = 0

        def fake_recvfrom(buf):
            nonlocal call_idx
            if call_idx < len(errors):
                err = errors[call_idx]
                call_idx += 1
                raise err
            elif call_idx == len(errors):
                call_idx += 1
                return (valid_pkt, ("192.168.1.100", 1900))
            raise BlockingIOError("EAGAIN")

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = fake_recvfrom
        mock_select.return_value = ([mock_sock], [], [])

        devs = discover_ssdp(timeout=0.1, sock=mock_sock)
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].ip, "192.168.1.100")
        self.assertEqual(devs[0].device_type, "android_tv")

    @patch("select.select")
    def test_discover_ssdp_multi_target_aggregation_dial_then_rootdevice(self, mock_select):
        """Ensures DIAL arriving before rootdevice upgrades generic smart_tv to android_tv."""
        pkt_dial = b"HTTP/1.1 200 OK\r\nST: urn:dial-multiscreen-org:service:dial:1\r\nLOCATION: http://192.168.1.101:8008/ssdp/desc.xml\r\n\r\n"
        pkt_root = b"HTTP/1.1 200 OK\r\nSERVER: Linux/4.9 Sony-Bravia/2.0\r\nST: upnp:rootdevice\r\n\r\n"
        pkts = [pkt_dial, pkt_root]
        call_idx = 0

        def fake_recvfrom(buf):
            nonlocal call_idx
            if call_idx < len(pkts):
                p = pkts[call_idx]
                call_idx += 1
                return (p, ("192.168.1.101", 1900))
            raise BlockingIOError("EAGAIN")

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = fake_recvfrom
        mock_select.return_value = ([mock_sock], [], [])

        devs = discover_ssdp(timeout=0.1, sock=mock_sock)
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].device_type, "android_tv")
        self.assertIn("Sony BRAVIA", devs[0].model)
        self.assertTrue(devs[0].is_android)

    @patch("select.select")
    def test_discover_ssdp_multi_target_preserves_android_when_dial_follows(self, mock_select):
        """Ensures rootdevice arriving before DIAL preserves android_tv and is not downgraded."""
        pkt_dial = b"HTTP/1.1 200 OK\r\nST: urn:dial-multiscreen-org:service:dial:1\r\nLOCATION: http://192.168.1.102:8008/ssdp/desc.xml\r\n\r\n"
        pkt_root = b"HTTP/1.1 200 OK\r\nSERVER: Linux/4.9 Sony-Bravia/2.0\r\nST: upnp:rootdevice\r\n\r\n"
        pkts = [pkt_root, pkt_dial]
        call_idx = 0

        def fake_recvfrom(buf):
            nonlocal call_idx
            if call_idx < len(pkts):
                p = pkts[call_idx]
                call_idx += 1
                return (p, ("192.168.1.102", 1900))
            raise BlockingIOError("EAGAIN")

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = fake_recvfrom
        mock_select.return_value = ([mock_sock], [], [])

        devs = discover_ssdp(timeout=0.1, sock=mock_sock)
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].device_type, "android_tv")
        self.assertIn("Sony BRAVIA", devs[0].model)
        self.assertTrue(devs[0].is_android)

    @patch("opentv.core.discovery.discover_mdns")
    @patch("opentv.core.discovery.discover_ssdp")
    def test_discover_devices_entrypoint_filtering(self, mock_ssdp, mock_mdns):
        mock_mdns.return_value = [
            DiscoveredDevice(ip="192.168.1.50", device_type="android_tv", source="mdns"),
        ]
        mock_ssdp.return_value = [
            DiscoveredDevice(ip="192.168.1.90", device_type="roku", source="ssdp"),
        ]

        # filter_android=True should drop Roku
        res_filtered = discover_devices(filter_android=True)
        self.assertEqual(len(res_filtered), 1)
        self.assertEqual(res_filtered[0].ip, "192.168.1.50")

        # filter_android=False should include Roku
        res_all = discover_devices(filter_android=False)
        self.assertEqual(len(res_all), 2)


# ============================================================================
# 8. Negative, Boundary & Adversarial Cases
# ============================================================================

class TestNegativeAndEdgeCases(unittest.TestCase):
    def test_empty_dns_packet(self):
        records = parse_dns_response(b"")
        self.assertEqual(records, [])

    def test_truncated_dns_header(self):
        records = parse_dns_response(b"\x00\x00\x00\x01")
        self.assertEqual(records, [])

    def test_truncated_record_rdata(self):
        # Header + 1 record header with rdlength=100 but only 2 bytes of data
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        qname = b"\x03foo\x00"
        rec_hdr = struct.pack("!HHIH", 1, 1, 60, 100)
        bad_packet = header + qname + rec_hdr + b"\x01\x02"
        records = parse_dns_response(bad_packet)
        self.assertEqual(records, [])

    def test_empty_ssdp_datagram(self):
        status, headers = parse_ssdp_headers(b"")
        self.assertEqual(status, "")
        self.assertEqual(headers, {})

    def test_garbage_ssdp_datagram(self):
        status, headers = parse_ssdp_headers(b"NOT_A_VALID_HTTP_PACKET\nNO_COLON_HERE\n")
        self.assertEqual(status, "NOT_A_VALID_HTTP_PACKET")
        self.assertEqual(headers, {})

    def test_fetch_ssdp_descriptor_invalid_url(self):
        self.assertEqual(fetch_ssdp_descriptor(""), {})
        self.assertEqual(fetch_ssdp_descriptor("ftp://invalid"), {})


# ============================================================================
# 9. CLI Discovery Integration Tests
# ============================================================================

class TestCliDiscoveryIntegration(unittest.TestCase):
    def test_cli_parser_connect_discover_flags(self):
        parser = create_parser()
        args = parser.parse_args(["connect", "--discover"])
        self.assertEqual(args.discover, 3.0)
        self.assertIsNone(args.target)

        args_custom = parser.parse_args(["connect", "--discover", "5.5", "--json"])
        self.assertEqual(args_custom.discover, 5.5)
        self.assertTrue(args_custom.json)

    def test_cli_parser_standalone_discover(self):
        parser = create_parser()
        args = parser.parse_args(["discover", "--timeout", "4.0", "--json", "-c"])
        self.assertEqual(args.subcommand, "discover")
        self.assertEqual(args.timeout, 4.0)
        self.assertTrue(args.json)
        self.assertTrue(args.connect)

    def test_format_device_table(self):
        devs = [
            DiscoveredDevice(ip="192.168.1.50", port=5555, model="Sony BRAVIA 4K", device_type="android_tv", source="mdns+ssdp"),
            DiscoveredDevice(ip="192.168.1.60", port=5555, model="Chromecast with Google TV", device_type="google_tv", source="ssdp"),
        ]
        table = format_device_table(devs)
        self.assertIn("192.168.1.50", table)
        self.assertIn("Sony BRAVIA 4K", table)
        self.assertIn("192.168.1.60", table)
        self.assertIn("Chromecast with Google TV", table)
        self.assertIn("MDNS+SSDP", table.upper())

    @patch("opentv.core.discovery.discover_devices")
    def test_cli_connect_discover_json_output(self, mock_discover):
        mock_discover.return_value = [
            DiscoveredDevice(ip="192.168.1.50", port=5555, model="Sony BRAVIA 4K", device_type="android_tv", source="mdns"),
        ]
        runner = MagicMock()
        stdout_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf):
            code = cli_main(["connect", "--discover", "--json"], runner=runner)

        self.assertEqual(code, EXIT_SUCCESS)
        output = json.loads(stdout_buf.getvalue())
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["ip"], "192.168.1.50")
        self.assertEqual(output[0]["model"], "Sony BRAVIA 4K")

    @patch("opentv.core.discovery.discover_devices")
    def test_cli_connect_discover_no_devices_found(self, mock_discover):
        mock_discover.return_value = []
        runner = MagicMock()
        stdout_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf):
            code = cli_main(["connect", "--discover"], runner=runner)

        self.assertEqual(code, EXIT_DEVICE_NOT_FOUND)
        self.assertIn("No Android TV devices discovered", stdout_buf.getvalue())

    @patch("opentv.core.discovery.discover_devices")
    def test_cli_connect_discover_interactive_selection(self, mock_discover):
        mock_discover.return_value = [
            DiscoveredDevice(ip="192.168.1.50", port=5555, model="Sony BRAVIA 4K", device_type="android_tv", source="mdns"),
        ]
        # Callable runner returning standard ADB (returncode, stdout, stderr)
        runner = lambda cmd: (0, "connected to 192.168.1.50:5555", "")
        stdout_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf), \
             patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="1"):
            code = cli_main(["connect", "--discover"], runner=runner)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("Successfully connected to 192.168.1.50:5555", stdout_buf.getvalue())

    @patch("opentv.core.discovery.discover_devices")
    def test_cli_connect_discover_user_cancel(self, mock_discover):
        mock_discover.return_value = [
            DiscoveredDevice(ip="192.168.1.50", port=5555, model="Sony BRAVIA 4K", device_type="android_tv", source="mdns"),
        ]
        runner = MagicMock()
        stdout_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf), \
             patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="q"):
            code = cli_main(["connect", "--discover"], runner=runner)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("Cancelled", stdout_buf.getvalue())

    @patch("opentv.core.discovery.discover_devices")
    def test_cli_standalone_discover_subcommand(self, mock_discover):
        mock_discover.return_value = [
            DiscoveredDevice(ip="192.168.1.60", port=5555, model="TCL Android TV", device_type="android_tv", source="ssdp"),
        ]
        runner = MagicMock()
        stdout_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf):
            code = cli_main(["discover"], runner=runner)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("TCL Android TV", stdout_buf.getvalue())


# ============================================================================
# 10. TUI Discovery Integration Tests
# ============================================================================

class TestTuiDiscoveryIntegration(unittest.TestCase):
    @patch("opentv.core.discovery.discover_devices")
    def test_tui_interactive_network_scan_connects(self, mock_discover):
        mock_discover.return_value = [
            DiscoveredDevice(ip="192.168.1.75", port=5555, model="Living Room Sony TV", device_type="android_tv", source="mdns"),
        ]
        fake_runner = MagicMock()
        fake_runner.return_value = (0, "connected to 192.168.1.75:5555", "")

        app = OpenTVApp(cmd_runner=fake_runner)
        app.connect_target = MagicMock(return_value=True)

        raw_engine = MagicMock()
        # User presses '1' to pick the first device
        raw_engine.read_key.return_value = KeyEvent(code=KeyCode.CHAR, char="1")

        app._run_interactive_network_scan(raw_engine)
        app.connect_target.assert_called_once_with("192.168.1.75", 5555)

    @patch("opentv.core.discovery.discover_devices")
    def test_tui_interactive_network_scan_empty(self, mock_discover):
        mock_discover.return_value = []
        app = OpenTVApp()
        raw_engine = MagicMock()

        app._run_interactive_network_scan(raw_engine)
        # Should prompt user to press key when no devices found
        self.assertTrue(raw_engine.read_key.called)

    @patch("opentv.core.discovery.discover_devices")
    def test_tui_fallback_connect_wizard_scan(self, mock_discover):
        mock_discover.return_value = [
            DiscoveredDevice(ip="192.168.1.88", port=5555, model="Shield TV", device_type="android_tv", source="mdns"),
        ]
        fake_runner = MagicMock()
        app = OpenTVApp(cmd_runner=fake_runner)
        app.connect_target = MagicMock(return_value=True)
        app.scan_devices = MagicMock(return_value=[])  # No USB devices

        # Mock fallback prompts:
        # prompt 1: select connection method -> index 0 is "Scan Local Network (mDNS/SSDP)"
        # prompt 2: select discovered TV -> index 0 is the Shield TV
        app.fallback.prompt_choice = MagicMock(side_effect=[0, 0])

        app._fallback_connect_wizard()
        app.connect_target.assert_called_once_with("192.168.1.88", 5555)


if __name__ == "__main__":
    unittest.main()
