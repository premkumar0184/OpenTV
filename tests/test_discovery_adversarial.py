"""
tests/test_discovery_adversarial.py
Adversarial and Empirical Stress-Testing Harness for OpenTV Auto-Discovery Engine.
Challenger 1 for Milestone 3 (M3_AUTO_DISCOVERY).

Tests cover:
- DNS pointer decompression: deep chains, loops (0xc000), out-of-bounds offsets, malformed labels.
- mDNS parsing: truncated packets, missing SRV/A records, corrupt RDATA.
- SSDP parsing: malformed HTTP headers, missing CRLF, lowercase headers, extra headers.
- Deduplication: conflicting hostnames, partial records, IP collisions, numeric octet sorting.
- Fuzzing / Property stress: 2500 randomized malformed packets.
- Empirical reproduction of confirmed bugs in discovery engine.
"""
from __future__ import annotations

import io
import os
import random
import socket
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestDnsPointerDecompressionAdversarial(unittest.TestCase):
    """Stress-test DNS pointer decompression against adversarial and boundary packets."""

    def test_pointer_self_loop(self):
        """Pointer pointing directly to its own offset (offset 0 -> 0x00)."""
        data = b"\xC0\x00"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(offset, 2)

    def test_pointer_self_loop_at_nonzero_offset(self):
        """Pointer pointing directly to its own non-zero offset (offset 10 -> 0x0a)."""
        data = b"\x00" * 10 + b"\xC0\x0A"
        name, offset = parse_dns_name(data, 10)
        self.assertEqual(name, "")
        self.assertEqual(offset, 12)

    def test_pointer_two_hop_loop(self):
        """Two-hop pointer loop: offset 10 -> 14, offset 14 -> 10."""
        buf = bytearray(20)
        buf[10:12] = b"\xC0\x0E"  # pointer to 14
        buf[14:16] = b"\xC0\x0A"  # pointer to 10
        name, offset = parse_dns_name(bytes(buf), 10)
        self.assertEqual(name, "")
        self.assertEqual(offset, 12)

    def test_pointer_three_hop_loop_with_labels(self):
        """Loop containing labels inside the cycle: 10 -> 20 -> 30 -> 10."""
        buf = bytearray(40)
        # 10: "a" + ptr to 20
        buf[10:14] = b"\x01a\xC0\x14"
        # 20: "b" + ptr to 30
        buf[20:24] = b"\x01b\xC0\x1E"
        # 30: "c" + ptr to 10
        buf[30:34] = b"\x01c\xC0\x0A"
        name, offset = parse_dns_name(bytes(buf), 10)
        # Should break after max_jumps (20 jumps)
        self.assertTrue(len(name.split(".")) <= 25)
        self.assertEqual(offset, 14)  # original pointer offset + 2

    def test_pointer_deep_chain_valid_boundary(self):
        """Valid chained pointer sequence with 15 hops ending at 'target.local'."""
        buf = bytearray(200)
        # offset 0: "local\x00"
        buf[0:7] = b"\x05local\x00"
        # offset 10: "target" + ptr to 0
        buf[10:19] = b"\x06target\xC0\x00"
        # Chain from offset 20 to 140 (12 hops)
        prev = 10
        for i in range(1, 13):
            curr = 10 + i * 10
            buf[curr:curr + 2] = bytes([0xC0, prev])
            prev = curr

        name, offset = parse_dns_name(bytes(buf), prev)
        self.assertEqual(name, "target.local")

    def test_pointer_chain_exceeds_max_jumps(self):
        """Chain of 25 pointers (> max_jumps = 20) safely terminates."""
        buf = bytearray(300)
        buf[0:5] = b"\x03end\x00"
        prev = 0
        for i in range(1, 26):
            curr = i * 4
            buf[curr:curr + 2] = bytes([0xC0, prev])
            prev = curr

        name, offset = parse_dns_name(bytes(buf), prev)
        # Safely terminated without infinite loop or RecursionError
        self.assertIsInstance(name, str)
        self.assertIsInstance(offset, int)

    def test_pointer_out_of_bounds_exact_length(self):
        """Pointer points to len(data) exactly."""
        data = b"\xC0\x02"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(offset, 2)

    def test_pointer_out_of_bounds_maximum_14bit(self):
        """Pointer points to 0x3FFF (16383)."""
        data = b"\xFF\xFF"  # (0xFF & 0xC0 == 0xC0), pointer = 0x3FFF
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(offset, 2)

    def test_pointer_truncated_single_byte(self):
        """Packet ends abruptly at pointer tag byte 0xC0."""
        data = b"\xC0"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")

    def test_pointer_truncated_after_label(self):
        """Label followed by truncated pointer byte 0xC0."""
        data = b"\x03abc\xC0"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "abc")

    def test_label_length_exceeds_buffer(self):
        """Label claims length 50, but packet only has 3 bytes left."""
        data = b"\x32\x61\x62"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")

    def test_label_length_zero(self):
        """Root null label."""
        data = b"\x00"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(offset, 1)

    def test_consecutive_null_labels(self):
        """Multiple null bytes."""
        data = b"\x00\x00\x00"
        name, offset = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(offset, 1)

    def test_non_ascii_utf8_in_labels(self):
        """Label contains invalid UTF-8 byte sequences."""
        data = b"\x04\xff\xfe\x80\xaa\x00"
        name, offset = parse_dns_name(data, 0)
        self.assertIn("\ufffd", name)
        self.assertEqual(offset, 6)

    def test_empty_buffer(self):
        """Empty input buffer."""
        name, offset = parse_dns_name(b"", 0)
        self.assertEqual(name, "")
        self.assertEqual(offset, 0)

    def test_offset_beyond_buffer(self):
        """Offset provided is larger than buffer length."""
        name, offset = parse_dns_name(b"\x03foo\x00", 100)
        self.assertEqual(name, "")
        self.assertEqual(offset, 100)

    def test_negative_offset_boundary(self):
        """parse_dns_name safely breaks on negative offsets without IndexError."""
        name, off = parse_dns_name(b"\x03foo\x00", -1)
        self.assertEqual(name, "")
        self.assertEqual(off, -1)
        name2, off2 = parse_dns_name(b"\x03foo\x00", -10)
        self.assertEqual(name2, "")
        self.assertEqual(off2, -10)


class TestMdnsResponseParsingAdversarial(unittest.TestCase):
    """Stress-test mDNS response parser against malformed and corrupted payloads."""

    def test_truncated_headers_all_lengths(self):
        """DNS header requires 12 bytes; test all lengths 0..11."""
        for length in range(12):
            raw = b"\x00" * length
            records = parse_dns_response(raw)
            self.assertEqual(records, [], f"Expected empty records for header length {length}")

    def test_qdcount_overflow_against_short_packet(self):
        """QDCOUNT claims 65535 questions, but packet is only 12 bytes."""
        header = struct.pack("!HHHHHH", 0, 0, 65535, 0, 0, 0)
        records = parse_dns_response(header)
        self.assertEqual(records, [])

    def test_ancount_overflow_against_short_packet(self):
        """ANCOUNT claims 65535 answers, but packet is only 12 bytes."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 65535, 0, 0)
        records = parse_dns_response(header)
        self.assertEqual(records, [])

    def test_truncated_record_header(self):
        """Record name is present, but record header (< 10 bytes) is truncated."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        # name is "test.local", followed by only 4 bytes (needs 10 for type, class, ttl, rdlength)
        packet = header + b"\x04test\x05local\x00" + b"\x00\x01\x00\x01"
        records = parse_dns_response(packet)
        self.assertEqual(records, [])

    def test_corrupted_rdlength_exceeds_packet(self):
        """Record rdlength is 1000, but only 2 bytes remaining in packet."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        # name "test\x00", type 1 (A), class 1, ttl 60, rdlength 1000, then only 2 bytes
        rec = b"\x04test\x00" + struct.pack("!HHIH", 1, 1, 60, 1000) + b"\x01\x02"
        records = parse_dns_response(header + rec)
        self.assertEqual(records, [])

    def test_corrupted_a_record_wrong_length(self):
        """A record with rdlength != 4 (e.g. 2 bytes or 6 bytes)."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 2, 0, 0)
        rec1 = b"\x04test\x00" + struct.pack("!HHIH", 1, 1, 60, 2) + b"\x01\x02"
        rec2 = b"\x04test\x00" + struct.pack("!HHIH", 1, 1, 60, 6) + b"\x01\x02\x03\x04\x05\x06"
        records = parse_dns_response(header + rec1 + rec2)
        self.assertEqual(len(records), 2)
        self.assertIsNone(records[0]["data"])
        self.assertIsNone(records[1]["data"])

    def test_corrupted_srv_record_short_length(self):
        """SRV record requires >= 6 bytes (priority, weight, port); test with 4 bytes."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        rec = b"\x04test\x00" + struct.pack("!HHIH", 33, 1, 60, 4) + b"\x00\x00\x15\xb3"
        records = parse_dns_response(header + rec)
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["data"])

    def test_corrupted_txt_record_boundary_overflow(self):
        """TXT record length byte claims string longer than RDATA."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        # rdlength 5, but first item length byte claims 10
        rdata = b"\x0ahello"
        rec = b"\x04test\x00" + struct.pack("!HHIH", 16, 1, 60, len(rdata)) + rdata
        records = parse_dns_response(header + rec)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["data"], {})

    def test_txt_record_items_without_equals(self):
        """TXT record containing boolean or flag attributes without '='."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        t1 = b"flag_enable"
        t2 = b"model=SonyTV"
        rdata = bytes([len(t1)]) + t1 + bytes([len(t2)]) + t2
        rec = b"\x04test\x00" + struct.pack("!HHIH", 16, 1, 60, len(rdata)) + rdata
        records = parse_dns_response(header + rec)
        self.assertEqual(len(records), 1)
        txt = records[0]["data"]
        self.assertIn("flag_enable", txt)
        self.assertEqual(txt["flag_enable"], "")
        self.assertEqual(txt["model"], "SonyTV")

    def test_unknown_record_types_handled_gracefully(self):
        """Unsupported record types (e.g. AAAA=28, OPT=41, ANY=255) are parsed without error."""
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 2, 0, 0)
        rec1 = b"\x04test\x00" + struct.pack("!HHIH", 28, 1, 60, 16) + (b"\x00" * 16)
        rec2 = b"\x04test\x00" + struct.pack("!HHIH", 255, 1, 60, 4) + b"\x11\x22\x33\x44"
        records = parse_dns_response(header + rec1 + rec2)
        self.assertEqual(len(records), 2)
        self.assertIsNone(records[0]["data"])
        self.assertIsNone(records[1]["data"])

    def test_aggregator_missing_srv_missing_a(self):
        """Aggregator receives only a PTR record, without SRV or A."""
        agg = MdnsDeviceAggregator()
        records = [{"type": 12, "name": "_adb._tcp.local", "data": "bravia._adb._tcp.local"}]
        agg.ingest_records(records, "192.168.1.55")
        devices = agg.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.55")
        self.assertEqual(devices[0].port, 5555)
        self.assertEqual(devices[0].hostname, "bravia")

    def test_aggregator_orphan_srv(self):
        """Aggregator receives SRV without PTR."""
        agg = MdnsDeviceAggregator()
        records = [
            {"type": 33, "name": "tcl._adb._tcp.local", "data": {"port": 5555, "target": "tcl.local"}},
            {"type": 16, "name": "tcl._adb._tcp.local", "data": {"model": "TCL C825"}},
        ]
        agg.ingest_records(records, "192.168.1.66")
        devices = agg.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.66")
        self.assertEqual(devices[0].model, "TCL C825")
        self.assertEqual(devices[0].hostname, "tcl.local")

    def test_aggregator_no_records_fallback_to_sender(self):
        """Aggregator receives datagram with no PTR/SRV (e.g. unknown RR) but valid sender IP."""
        agg = MdnsDeviceAggregator()
        records = [{"type": 28, "name": "test.local", "data": None}]
        agg.ingest_records(records, "192.168.1.77")
        devices = agg.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.77")
        self.assertEqual(devices[0].model, "Android TV Device")


class TestSsdpParsingAdversarial(unittest.TestCase):
    """Stress-test SSDP header parsing, line separators, and device heuristics."""

    def test_parse_ssdp_headers_unix_newlines_only(self):
        """Headers separated by Unix LF ('\\n') instead of CRLF."""
        raw = "HTTP/1.1 200 OK\nSERVER: Sony Bravia\nLOCATION: http://192.168.1.10:8008/desc.xml\nST: dial\n\n"
        status, headers = parse_ssdp_headers(raw)
        self.assertEqual(status, "HTTP/1.1 200 OK")
        self.assertEqual(headers.get("SERVER"), "Sony Bravia")
        self.assertEqual(headers.get("LOCATION"), "http://192.168.1.10:8008/desc.xml")
        self.assertEqual(headers.get("ST"), "dial")

    def test_parse_ssdp_headers_mac_newlines_only(self):
        """Headers separated by classic Mac CR ('\\r') instead of CRLF."""
        raw = "HTTP/1.1 200 OK\rSERVER: Sony Bravia\rLOCATION: http://192.168.1.10:8008/desc.xml\rST: dial\r\r"
        status, headers = parse_ssdp_headers(raw)
        self.assertEqual(status, "HTTP/1.1 200 OK")
        self.assertEqual(headers.get("SERVER"), "Sony Bravia")

    def test_parse_ssdp_headers_all_lowercase(self):
        """Headers with strictly lowercase header keys."""
        raw = "http/1.1 200 ok\r\nserver: Linux/4.9\r\nlocation: http://192.168.1.20:8080/xml\r\nst: upnp:rootdevice\r\n\r\n"
        status, headers = parse_ssdp_headers(raw)
        self.assertIn("SERVER", headers)
        self.assertIn("LOCATION", headers)
        self.assertIn("ST", headers)
        self.assertEqual(headers["SERVER"], "Linux/4.9")

    def test_parse_ssdp_headers_malformed_lines_without_colon(self):
        """Malformed lines mixed in with valid headers."""
        raw = "HTTP/1.1 200 OK\r\nINVALID LINE WITHOUT COLON\r\nSERVER: TestServer\r\nANOTHER BAD LINE\r\n\r\n"
        status, headers = parse_ssdp_headers(raw)
        self.assertEqual(status, "HTTP/1.1 200 OK")
        self.assertEqual(headers, {"SERVER": "TestServer"})

    def test_parse_ssdp_headers_empty_and_whitespace(self):
        """Empty string or pure whitespace."""
        self.assertEqual(parse_ssdp_headers(""), ("", {}))
        self.assertEqual(parse_ssdp_headers(b""), ("", {}))
        self.assertEqual(parse_ssdp_headers("   \r\n\r\n  \n"), ("", {}))

    def test_parse_ssdp_headers_multiple_colons_in_value(self):
        """Header value containing multiple colons (URLs, UUIDs, USNs)."""
        raw = "HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.50:8008/ssdp/desc.xml\r\nUSN: uuid:1234:5678::urn:dial\r\n\r\n"
        _, headers = parse_ssdp_headers(raw)
        self.assertEqual(headers["LOCATION"], "http://192.168.1.50:8008/ssdp/desc.xml")
        self.assertEqual(headers["USN"], "uuid:1234:5678::urn:dial")

    def test_identify_ssdp_all_supported_brands(self):
        """Exhaustive check of brand detection across headers."""
        cases = [
            ({"SERVER": "Sony-Bravia"}, "android_tv", "Sony BRAVIA"),
            ({"SERVER": "Eureka Dongle"}, "google_tv", "Chromecast with Google TV"),
            ({"SERVER": "Chromecast"}, "google_tv", "Chromecast with Google TV"),
            ({"SERVER": "Sabrina"}, "google_tv", "Chromecast with Google TV"),
            ({"SERVER": "Amazon-FireTV/1.0"}, "fire_tv", "Amazon Fire TV"),
            ({"SERVER": "TCL BeyondTV"}, "android_tv", "TCL Android TV"),
            ({"SERVER": "Xiaomi MiTV"}, "android_tv", "Xiaomi Mi TV"),
            ({"SERVER": "Philips DroidTV"}, "android_tv", "Philips Android TV"),
            ({"SERVER": "Hisense Jamdeo"}, "android_tv", "Hisense Android TV"),
            ({"ST": "urn:dial-multiscreen-org:service:dial:1"}, "smart_tv", "Smart TV (DIAL)"),
        ]
        for headers, expected_type, expected_model in cases:
            dev = identify_ssdp_device(headers, "192.168.1.100")
            self.assertEqual(dev.device_type, expected_type, f"Failed for headers: {headers}")
            self.assertIn(expected_model, dev.model, f"Failed for headers: {headers}")

    def test_identify_ssdp_disqualify_non_android(self):
        """Ensure Roku, Samsung Tizen, LG webOS, Sonos, and Apple are disqualified."""
        non_android_headers = [
            ({"SERVER": "Roku/11.0"}, "roku"),
            ({"SERVER": "SHP, SEC_HHP_[TV] Samsung"}, "samsung_tizen"),
            ({"SERVER": "webOS TV/7.0"}, "lg_webos"),
            ({"SERVER": "Sonos/55.1"}, "sonos"),
            ({"SERVER": "AirPlay/1.0 Apple"}, "apple_device"),
        ]
        for headers, expected_type in non_android_headers:
            dev = identify_ssdp_device(headers, "192.168.1.100")
            self.assertEqual(dev.device_type, expected_type)
            self.assertFalse(dev.is_android, f"Device with headers {headers} should not be marked Android")

    def test_fetch_ssdp_descriptor_failures(self):
        """Malformed XML, non-HTTP URLs, and network errors return empty dict."""
        self.assertEqual(fetch_ssdp_descriptor(""), {})
        self.assertEqual(fetch_ssdp_descriptor("ftp://invalid"), {})
        self.assertEqual(fetch_ssdp_descriptor("file:///etc/passwd"), {})

        # Mock with malformed XML
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"<malformed<xml>><>>"
            mock_resp.__enter__.return_value = mock_resp
            mock_open.return_value = mock_resp
            desc = fetch_ssdp_descriptor("http://192.168.1.1:8008/desc.xml")
            self.assertEqual(desc, {})


class TestDeduplicationAndSortingAdversarial(unittest.TestCase):
    """Stress-test deduplication, hostname conflict resolution, partial records, and sorting."""

    def test_dedup_conflicting_hostnames(self):
        """When mDNS and SSDP report different hostnames or one is empty, best is chosen."""
        mdns_dev = DiscoveredDevice(ip="192.168.1.50", port=5555, hostname="bravia-mdns.local", source="mdns")
        ssdp_dev = DiscoveredDevice(ip="192.168.1.50", port=5555, hostname="", source="ssdp")
        merged = deduplicate_devices([mdns_dev], [ssdp_dev])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].hostname, "bravia-mdns.local")
        self.assertEqual(merged[0].source, "mdns+ssdp")

    def test_dedup_ssdp_hostname_when_mdns_empty(self):
        """When mDNS hostname is empty, SSDP hostname is preserved."""
        mdns_dev = DiscoveredDevice(ip="192.168.1.50", port=5555, hostname="", source="mdns")
        ssdp_dev = DiscoveredDevice(ip="192.168.1.50", port=5555, hostname="shield-ssdp", source="ssdp")
        merged = deduplicate_devices([mdns_dev], [ssdp_dev])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].hostname, "shield-ssdp")

    def test_dedup_port_priority_non_standard(self):
        """mDNS non-5555 port (e.g. 37421 TLS ADB) takes precedence over SSDP default 5555."""
        mdns_dev = DiscoveredDevice(ip="192.168.1.50", port=37421, source="mdns")
        ssdp_dev = DiscoveredDevice(ip="192.168.1.50", port=5555, source="ssdp")
        merged = deduplicate_devices([mdns_dev], [ssdp_dev])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].port, 37421)

    def test_dedup_model_priority_descriptive_over_generic(self):
        """Descriptive SSDP model replaces generic mDNS 'Android TV Device'."""
        mdns_dev = DiscoveredDevice(ip="192.168.1.50", model="Android TV Device", source="mdns")
        ssdp_dev = DiscoveredDevice(ip="192.168.1.50", model="Sony BRAVIA XR-65A80J", source="ssdp")
        merged = deduplicate_devices([mdns_dev], [ssdp_dev])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].model, "Sony BRAVIA XR-65A80J")

    def test_numeric_ipv4_octet_sorting(self):
        """IPs must be sorted numerically by octet, not lexicographically."""
        ips = [
            "192.168.1.100",
            "192.168.1.20",
            "192.168.1.2",
            "10.0.0.100",
            "10.0.0.2",
            "172.16.0.5",
        ]
        devices = [DiscoveredDevice(ip=ip) for ip in ips]
        sorted_devs = deduplicate_devices(devices, [])
        sorted_ips = [d.ip for d in sorted_devs]
        expected_ips = [
            "10.0.0.2",
            "10.0.0.100",
            "172.16.0.5",
            "192.168.1.2",
            "192.168.1.20",
            "192.168.1.100",
        ]
        self.assertEqual(sorted_ips, expected_ips)

    def test_sorting_with_malformed_ips(self):
        """IP sort key survives non-standard, empty, or hostname strings without crashing."""
        malformed = [
            DiscoveredDevice(ip=""),
            DiscoveredDevice(ip="hostname.local"),
            DiscoveredDevice(ip="192.168.1.1"),
        ]
        result = deduplicate_devices(malformed, [])
        self.assertEqual(len(result), 3)

    def test_filter_android_exclusion(self):
        """discover_devices(filter_android=True) filters out non-Android devices."""
        d_android = DiscoveredDevice(ip="192.168.1.10", device_type="android_tv", source="ssdp")
        d_roku = DiscoveredDevice(ip="192.168.1.11", device_type="roku", source="ssdp")
        d_tizen = DiscoveredDevice(ip="192.168.1.12", device_type="samsung_tizen", source="ssdp")
        d_mdns = DiscoveredDevice(ip="192.168.1.13", source="mdns")  # mDNS is always android

        with patch("opentv.core.discovery.discover_mdns", return_value=[d_mdns]):
            with patch("opentv.core.discovery.discover_ssdp", return_value=[d_android, d_roku, d_tizen]):
                filtered = discover_devices(filter_android=True)
                filtered_ips = {d.ip for d in filtered}
                self.assertIn("192.168.1.10", filtered_ips)
                self.assertIn("192.168.1.13", filtered_ips)
                self.assertNotIn("192.168.1.11", filtered_ips)
                self.assertNotIn("192.168.1.12", filtered_ips)

                unfiltered = discover_devices(filter_android=False)
                self.assertEqual(len(unfiltered), 4)


class TestFuzzRandomizedByteStress(unittest.TestCase):
    """Property/Fuzz stress: 2500 randomized byte payloads must never raise unhandled exceptions."""

    def test_fuzz_parse_dns_name_random_bytes(self):
        rng = random.Random(42)
        for _ in range(1000):
            length = rng.randint(0, 256)
            payload = rng.randbytes(length) if hasattr(rng, "randbytes") else bytes(rng.getrandbits(8) for _ in range(length))
            offset = rng.randint(0, max(0, length - 1)) if length > 0 else 0
            try:
                name, next_off = parse_dns_name(payload, offset)
                self.assertIsInstance(name, str)
                self.assertIsInstance(next_off, int)
            except Exception as e:
                self.fail(f"parse_dns_name raised unhandled exception {type(e).__name__}: {e} on payload {payload.hex()}")

    def test_fuzz_parse_dns_response_random_bytes(self):
        rng = random.Random(1337)
        for _ in range(1000):
            length = rng.randint(0, 512)
            payload = rng.randbytes(length) if hasattr(rng, "randbytes") else bytes(rng.getrandbits(8) for _ in range(length))
            try:
                records = parse_dns_response(payload)
                self.assertIsInstance(records, list)
            except Exception as e:
                self.fail(f"parse_dns_response raised unhandled exception {type(e).__name__}: {e} on payload {payload.hex()}")

    def test_fuzz_parse_ssdp_headers_random_bytes(self):
        rng = random.Random(9999)
        for _ in range(500):
            length = rng.randint(0, 512)
            payload = rng.randbytes(length) if hasattr(rng, "randbytes") else bytes(rng.getrandbits(8) for _ in range(length))
            try:
                status, headers = parse_ssdp_headers(payload)
                self.assertIsInstance(status, str)
                self.assertIsInstance(headers, dict)
            except Exception as e:
                self.fail(f"parse_ssdp_headers raised unhandled exception {type(e).__name__}: {e} on payload {payload.hex()}")


class TestEmpiricalVulnerabilitiesAndBugs(unittest.TestCase):
    """
    Empirically demonstrates confirmed failure modes and bugs identified in Milestone 3.
    """

    def test_demonstrate_bug1_discover_ssdp_aborts_on_transient_blocking_io(self):
        """
        [Finding 1: HIGH] In discover_ssdp (line 725), 'except (OSError, socket.error): break'
        causes the discovery loop to terminate on the very first transient socket error
        (such as BlockingIOError/EAGAIN on spurious select wakeup or ConnectionResetError
        from ICMP port unreachable on Windows), dropping all subsequent discovery packets.
        """
        valid_pkt = b"HTTP/1.1 200 OK\r\nSERVER: Sony Bravia\r\n\r\n"
        called = 0

        def mock_recvfrom(size):
            nonlocal called
            called += 1
            if called == 1:
                # Spurious wakeup / non-blocking socket EAGAIN
                raise BlockingIOError("Resource temporarily unavailable")
            elif called == 2:
                return (valid_pkt, ("192.168.1.50", 1900))
            raise BlockingIOError("EAGAIN")

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = mock_recvfrom

        with patch("select.select", return_value=([mock_sock], [], [])):
            devs = discover_ssdp(timeout=0.1, sock=mock_sock)

        # Fixed: discover_ssdp continues past transient socket error
        self.assertEqual(len(devs), 1, "Fixed: discover_ssdp continues past transient socket error")

    def test_expected_fix_discover_ssdp_survives_transient_blocking_io(self):
        """Expected behavior: discover_ssdp should use continue (like discover_mdns) and receive packets."""
        valid_pkt = b"HTTP/1.1 200 OK\r\nSERVER: Sony Bravia\r\n\r\n"
        called = 0

        def mock_recvfrom(size):
            nonlocal called
            called += 1
            if called == 1:
                raise BlockingIOError("Resource temporarily unavailable")
            elif called == 2:
                return (valid_pkt, ("192.168.1.50", 1900))
            raise BlockingIOError("EAGAIN")

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = mock_recvfrom

        with patch("select.select", return_value=([mock_sock], [], [])):
            devs = discover_ssdp(timeout=0.1, sock=mock_sock)

        self.assertEqual(len(devs), 1, "Expected fix: discover_ssdp should continue and discover device")

    def test_demonstrate_bug2_dial_response_drops_android_tv_under_filter_android(self):
        """
        [Finding 2: HIGH] When SSDP DIAL or MediaRenderer response arrives before rootdevice
        response, the device is tagged device_type='smart_tv'. Subsequent responses from
        Sony-Bravia or Chromecast fail to upgrade device_type or model because existing.device_type != 'unknown'
        and existing.model does not start with 'Unknown'. Consequently, is_android is False,
        and discover_devices(filter_android=True) drops the device completely!
        """
        headers_dial = {
            "ST": "urn:dial-multiscreen-org:service:dial:1",
            "LOCATION": "http://192.168.1.50:8008/ssdp/desc.xml",
        }
        headers_sony = {
            "SERVER": "Linux/4.9 Sony-Bravia/2.0",
            "ST": "upnp:rootdevice",
        }
        dev_dial = identify_ssdp_device(headers_dial, "192.168.1.50")
        dev_sony = identify_ssdp_device(headers_sony, "192.168.1.50")

        # Simulate discover_ssdp multi-response aggregation logic
        devices_by_ip = {}
        for dev in [dev_dial, dev_sony]:
            ip = dev.ip
            if ip not in devices_by_ip:
                devices_by_ip[ip] = dev
            else:
                existing = devices_by_ip[ip]
                if (existing.model.startswith("Unknown") or existing.model.startswith("Smart TV")) and not (dev.model.startswith("Unknown") or dev.model.startswith("Smart TV")):
                    existing.model = dev.model
                elif existing.model.startswith("Unknown") and not dev.model.startswith("Unknown"):
                    existing.model = dev.model

                android_types = {"android_tv", "google_tv", "fire_tv"}
                if existing.device_type in ("unknown", "smart_tv") and dev.device_type in android_types:
                    existing.device_type = dev.device_type
                elif existing.device_type == "unknown" and dev.device_type != "unknown":
                    existing.device_type = dev.device_type

        ssdp_devices = list(devices_by_ip.values())
        with patch("opentv.core.discovery.discover_mdns", return_value=[]):
            with patch("opentv.core.discovery.discover_ssdp", return_value=ssdp_devices):
                found = discover_devices(filter_android=True)

        # Fixed: real Sony Bravia Android TV is preserved!
        self.assertEqual(len(found), 1, "Fixed: Sony Bravia upgraded to android_tv and preserved")
        self.assertIn("Sony BRAVIA", found[0].model)

    def test_expected_fix_dial_upgraded_to_android_tv(self):
        """Expected behavior: SSDP multi-response aggregation upgrades smart_tv to android_tv and model to Sony."""
        pkt_dial = b"HTTP/1.1 200 OK\r\nST: urn:dial-multiscreen-org:service:dial:1\r\nLOCATION: http://192.168.1.50:8008/ssdp/desc.xml\r\n\r\n"
        pkt_sony = b"HTTP/1.1 200 OK\r\nSERVER: Linux/4.9 Sony-Bravia/2.0\r\nST: upnp:rootdevice\r\n\r\n"

        def make_recv():
            called = 0
            def mock_recvfrom(size):
                nonlocal called
                called += 1
                if called == 1:
                    return (pkt_dial, ("192.168.1.50", 1900))
                elif called == 2:
                    return (pkt_sony, ("192.168.1.50", 1900))
                raise BlockingIOError("EAGAIN")
            return mock_recvfrom

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = make_recv()

        with patch("select.select", return_value=([mock_sock], [], [])):
            devs = discover_ssdp(timeout=0.1, sock=mock_sock)

        self.assertEqual(len(devs), 1)
        # In unpatched code, device_type stays 'smart_tv' and model stays 'Smart TV (DIAL)'
        self.assertEqual(devs[0].device_type, "android_tv", "Expected fix: device_type should be upgraded to android_tv")
        self.assertIn("Sony BRAVIA", devs[0].model, "Expected fix: model should be upgraded to Sony BRAVIA")

    def test_demonstrate_bug3_dedup_overrides_mdns_android_with_ssdp_roku(self):
        """
        [Finding 3: MEDIUM] In deduplicate_devices (line 785):
        (m.device_type == 'android_tv' and s.device_type != 'unknown')
        evaluates to True when s.device_type is 'roku', 'samsung_tizen', etc.,
        causing the non-Android SSDP type to override mDNS's verified android_tv!
        """
        m = DiscoveredDevice(ip="192.168.1.50", device_type="android_tv", source="mdns")
        s = DiscoveredDevice(ip="192.168.1.50", device_type="roku", source="ssdp")
        merged = deduplicate_devices([m], [s])[0]

        # Fixed: mDNS android_tv is preserved over non-Android SSDP type
        self.assertEqual(merged.device_type, "android_tv")
        self.assertTrue(merged.is_android)

    def test_expected_fix_dedup_preserves_android_tv_over_roku(self):
        """Expected behavior: mDNS android_tv should NOT be overwritten by non-Android SSDP types."""
        m = DiscoveredDevice(ip="192.168.1.50", device_type="android_tv", source="mdns")
        s = DiscoveredDevice(ip="192.168.1.50", device_type="roku", source="ssdp")
        merged = deduplicate_devices([m], [s])[0]
        self.assertEqual(merged.device_type, "android_tv", "Expected fix: android_tv should be preserved")

    def test_demonstrate_bug4_dedup_downgrades_android_tv_to_smart_tv_dial(self):
        """
        [Finding 4: MEDIUM] In deduplicate_devices (line 780):
        if s.model and not s.model.startswith('Unknown') and (not m.model or m.model.startswith('Android')):
        best_model = s.model
        replaces 'Android TV Device' with 'Smart TV (DIAL)'.
        """
        m = DiscoveredDevice(ip="192.168.1.50", model="Android TV Device", device_type="android_tv", source="mdns")
        s = DiscoveredDevice(ip="192.168.1.50", model="Smart TV (DIAL)", device_type="smart_tv", source="ssdp")
        merged = deduplicate_devices([m], [s])[0]

        # Fixed: mDNS model is preserved against generic Smart TV (DIAL)
        self.assertEqual(merged.model, "Android TV Device")

    def test_expected_fix_dedup_does_not_downgrade_to_smart_tv_dial(self):
        """Expected behavior: mDNS 'Android TV Device' should not be downgraded to 'Smart TV (DIAL)'."""
        m = DiscoveredDevice(ip="192.168.1.50", model="Android TV Device", device_type="android_tv", source="mdns")
        s = DiscoveredDevice(ip="192.168.1.50", model="Smart TV (DIAL)", device_type="smart_tv", source="ssdp")
        merged = deduplicate_devices([m], [s])[0]
        self.assertEqual(merged.model, "Android TV Device", "Expected fix: generic smart_tv should not downgrade android")


if __name__ == "__main__":
    unittest.main()
