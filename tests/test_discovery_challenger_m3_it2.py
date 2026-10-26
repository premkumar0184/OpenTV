"""
tests/test_discovery_challenger_m3_it2.py
Adversarial Empirical Stress Testing Suite for OpenTV Auto-Discovery Hardening.
Challenger 2 for Milestone 3 Iteration 2 (M3_AUTO_DISCOVERY).

Empirically validates:
1. Multi-target SSDP stress testing (varied arrival sequences: DIAL -> Rootdevice,
   Rootdevice -> DIAL, MediaRenderer -> DIAL -> Rootdevice, duplicate packet storms,
   interleaved multi-device packet streams).
2. Heterogeneous device coexistence (simultaneous network responses from Android TV,
   Google TV, Fire TV, Roku, Apple TV, Sonos, Samsung Tizen, LG webOS; accurate
   classification, is_android filtering, and priority resolution).
3. Socket error injections (non-blocking EAGAIN / BlockingIOError, WSAECONNRESET /
   ConnectionResetError 10054, InterruptedError / EINTR, corrupted UDP headers / wire bytes).
4. Full regression verification across discovery components.
"""
from __future__ import annotations

import errno
import os
import select
import socket
import struct
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


# Helper to build mock UDP responses
def make_ssdp_packet(
    status: str = "HTTP/1.1 200 OK",
    st: str = "upnp:rootdevice",
    usn: str = "uuid:mock-device::upnp:rootdevice",
    location: str = "http://192.168.1.100:8008/desc.xml",
    server: str = "Linux/4.9 UPnP/1.0",
    extra: Optional[Dict[str, str]] = None,
) -> bytes:
    lines = [
        status,
        f"CACHE-CONTROL: max-age=1800",
        f"LOCATION: {location}",
        f"SERVER: {server}",
        f"ST: {st}",
        f"USN: {usn}",
    ]
    if extra:
        for k, v in extra.items():
            lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("")
    return "\r\n".join(lines).encode("utf-8")


class MockSequencedSocket:
    """
    Mock socket that simulates UDP network packet delivery, sequence delays,
    and simulated OS/network errors (BlockingIOError, ConnectionResetError, etc.).
    """

    def __init__(self, sequence: List[Any], send_recorder: Optional[List[Tuple[bytes, Any]]] = None) -> None:
        # sequence items can be (bytes_data, (ip, port)) or an Exception class / instance
        self._sequence = list(sequence)
        self.send_recorder = send_recorder if send_recorder is not None else []
        self.closed = False

    def fileno(self) -> int:
        return 999

    def setsockopt(self, *args: Any) -> None:
        pass

    def bind(self, addr: Any) -> None:
        pass

    def setblocking(self, flag: bool) -> None:
        pass

    def sendto(self, data: bytes, addr: Any) -> int:
        self.send_recorder.append((data, addr))
        return len(data)

    def recvfrom(self, bufsize: int) -> Tuple[bytes, Tuple[str, int]]:
        if not self._sequence:
            raise BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")
        item = self._sequence.pop(0)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item()
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


# ============================================================================
# Suite 1: Multi-Target SSDP Stress Testing
# ============================================================================

class TestMultiTargetSsdpStress(unittest.TestCase):
    """Stress-test varied SSDP arrival sequences, bursts, and duplicate packet handling."""

    def test_ssdp_arrival_dial_then_rootdevice_upgrades(self):
        """Sequence: DIAL response arrives first, then Sony Rootdevice response."""
        dial_pkt = make_ssdp_packet(
            st="urn:dial-multiscreen-org:service:dial:1",
            location="http://192.168.1.101:8008/ssdp/device-desc.xml",
            server="Linux/3.10 UPnP/1.0",
        )
        sony_pkt = make_ssdp_packet(
            st="upnp:rootdevice",
            location="http://192.168.1.101:52323/dmr.xml",
            server="Linux/4.19 UPnP/1.0 Sony-BRAVIA-4K-GB/1.0",
        )

        mock_sock = MockSequencedSocket([
            (dial_pkt, ("192.168.1.101", 1900)),
            (sony_pkt, ("192.168.1.101", 1900)),
        ])

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.1)

        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev.ip, "192.168.1.101")
        self.assertEqual(dev.device_type, "android_tv")
        self.assertIn("Sony BRAVIA", dev.model)
        self.assertTrue(dev.is_android)
        self.assertEqual(len(dev.raw_info.get("additional_responses", [])), 1)

    def test_ssdp_arrival_rootdevice_then_dial_preserves(self):
        """Sequence: Sony Rootdevice arrives first, then DIAL response arrives."""
        sony_pkt = make_ssdp_packet(
            st="upnp:rootdevice",
            location="http://192.168.1.102:52323/dmr.xml",
            server="Linux/4.19 UPnP/1.0 Sony-BRAVIA-4K-GB/1.0",
        )
        dial_pkt = make_ssdp_packet(
            st="urn:dial-multiscreen-org:service:dial:1",
            location="http://192.168.1.102:8008/ssdp/device-desc.xml",
            server="Linux/3.10 UPnP/1.0",
        )

        mock_sock = MockSequencedSocket([
            (sony_pkt, ("192.168.1.102", 1900)),
            (dial_pkt, ("192.168.1.102", 1900)),
        ])

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.1)

        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev.device_type, "android_tv")
        self.assertIn("Sony BRAVIA", dev.model)
        self.assertTrue(dev.is_android)

    def test_ssdp_arrival_mediarenderer_then_dial_then_rootdevice(self):
        """Sequence: MediaRenderer -> DIAL -> Google TV Rootdevice."""
        mr_pkt = make_ssdp_packet(
            st="urn:schemas-upnp-org:device:MediaRenderer:1",
            location="http://192.168.1.103:8008/ssdp/device-desc.xml",
            server="Linux/4.9 UPnP/1.0",
        )
        dial_pkt = make_ssdp_packet(
            st="urn:dial-multiscreen-org:service:dial:1",
            location="http://192.168.1.103:8008/ssdp/device-desc.xml",
            server="Linux/4.9 UPnP/1.0",
        )
        gtv_pkt = make_ssdp_packet(
            st="upnp:rootdevice",
            location="http://192.168.1.103:8008/setup/eureka_info",
            server="Linux/4.9 UPnP/1.0 Chromecast/1.0",
        )

        mock_sock = MockSequencedSocket([
            (mr_pkt, ("192.168.1.103", 1900)),
            (dial_pkt, ("192.168.1.103", 1900)),
            (gtv_pkt, ("192.168.1.103", 1900)),
        ])

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.1)

        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev.device_type, "google_tv")
        self.assertEqual(dev.model, "Chromecast with Google TV")
        self.assertTrue(dev.is_android)
        self.assertEqual(len(dev.raw_info.get("additional_responses", [])), 2)

    def test_ssdp_arrival_rootdevice_then_mediarenderer_then_dial(self):
        """Sequence: Amazon Fire TV Rootdevice -> MediaRenderer -> DIAL."""
        fire_pkt = make_ssdp_packet(
            st="upnp:rootdevice",
            location="http://192.168.1.104:8008/desc.xml",
            server="Amazon-FireTV/1.0 UPnP/1.0",
        )
        mr_pkt = make_ssdp_packet(
            st="urn:schemas-upnp-org:device:MediaRenderer:1",
            location="http://192.168.1.104:8008/desc.xml",
            server="Linux/4.9 UPnP/1.0",
        )
        dial_pkt = make_ssdp_packet(
            st="urn:dial-multiscreen-org:service:dial:1",
            location="http://192.168.1.104:8008/desc.xml",
            server="Linux/4.9 UPnP/1.0",
        )

        mock_sock = MockSequencedSocket([
            (fire_pkt, ("192.168.1.104", 1900)),
            (mr_pkt, ("192.168.1.104", 1900)),
            (dial_pkt, ("192.168.1.104", 1900)),
        ])

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.1)

        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev.device_type, "fire_tv")
        self.assertEqual(dev.model, "Amazon Fire TV")
        self.assertTrue(dev.is_android)

    def test_ssdp_duplicate_packet_burst(self):
        """Stress: 150 duplicate identical packets from a single device."""
        pkt = make_ssdp_packet(
            st="upnp:rootdevice",
            server="Linux/4.19 UPnP/1.0 Sony-BRAVIA-4K/1.0",
        )
        burst = [(pkt, ("192.168.1.105", 1900)) for _ in range(150)]
        mock_sock = MockSequencedSocket(burst)

        # Allow select to return socket as long as sequence is non-empty
        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.5)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.105")
        self.assertEqual(len(devices[0].raw_info["additional_responses"]), 149)

    def test_ssdp_interleaved_multi_device_arrival(self):
        """Interleaved packet stream from Sony, Chromecast, Fire TV, and Roku."""
        sony_dial = make_ssdp_packet(st="urn:dial-multiscreen-org:service:dial:1", server="Linux UPnP/1.0")
        chromecast_dial = make_ssdp_packet(st="urn:dial-multiscreen-org:service:dial:1", server="Eureka/1.0")
        sony_root = make_ssdp_packet(st="upnp:rootdevice", server="Linux UPnP/1.0 Sony-BRAVIA-4K/1.0")
        roku_root = make_ssdp_packet(st="upnp:rootdevice", server="Roku/9.4.0 UPnP/1.0")
        chromecast_root = make_ssdp_packet(st="upnp:rootdevice", server="Chromecast/1.0 Eureka/1.0")
        fire_root = make_ssdp_packet(st="upnp:rootdevice", server="Amazon-FireTV/1.0 UPnP/1.0")

        stream = [
            (sony_dial, ("192.168.1.11", 1900)),
            (chromecast_dial, ("192.168.1.12", 1900)),
            (roku_root, ("192.168.1.13", 1900)),
            (sony_root, ("192.168.1.11", 1900)),
            (fire_root, ("192.168.1.14", 1900)),
            (chromecast_root, ("192.168.1.12", 1900)),
            (sony_dial, ("192.168.1.11", 1900)),  # Duplicate
        ]
        mock_sock = MockSequencedSocket(stream)

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.5)

        by_ip = {d.ip: d for d in devices}
        self.assertEqual(len(by_ip), 4)

        self.assertEqual(by_ip["192.168.1.11"].device_type, "android_tv")
        self.assertIn("Sony BRAVIA", by_ip["192.168.1.11"].model)

        self.assertEqual(by_ip["192.168.1.12"].device_type, "google_tv")
        self.assertEqual(by_ip["192.168.1.12"].model, "Chromecast with Google TV")

        self.assertEqual(by_ip["192.168.1.13"].device_type, "roku")
        self.assertEqual(by_ip["192.168.1.13"].is_android, False)

        self.assertEqual(by_ip["192.168.1.14"].device_type, "fire_tv")
        self.assertEqual(by_ip["192.168.1.14"].model, "Amazon Fire TV")


# ============================================================================
# Suite 2: Heterogeneous Device Coexistence & Classification
# ============================================================================

class TestHeterogeneousDeviceCoexistence(unittest.TestCase):
    """Verify simultaneous coexistence of 8 distinct TV and media devices."""

    def setUp(self):
        self.heterogeneous_definitions = [
            ("192.168.1.10", "Linux/4.19 UPnP/1.0 Sony-BRAVIA-4K/1.0", "upnp:rootdevice", "android_tv", "Sony BRAVIA TV", True),
            ("192.168.1.20", "Eureka/1.0 UPnP/1.0", "upnp:rootdevice", "google_tv", "Chromecast with Google TV", True),
            ("192.168.1.30", "Amazon-FireTV/1.0 UPnP/1.0", "upnp:rootdevice", "fire_tv", "Amazon Fire TV", True),
            ("192.168.1.40", "Roku/9.4.0 UPnP/1.0", "upnp:rootdevice", "roku", "Roku Streaming Device", False),
            ("192.168.1.50", "AirPlay/320.20 UPnP/1.0", "upnp:rootdevice", "apple_device", "Apple Device", False),
            ("192.168.1.60", "Linux UPnP/1.0 Sonos/56.0-76060", "urn:schemas-upnp-org:device:ZonePlayer:1", "sonos", "Sonos Audio Device", False),
            ("192.168.1.70", "SHP/2.4.0 SEC_HHP_[TV] Samsung Q60/1.0", "upnp:rootdevice", "samsung_tizen", "Samsung Smart TV", False),
            ("192.168.1.80", "webOS/4.0 UPnP/1.0 LG Electronics", "upnp:rootdevice", "lg_webos", "LG Smart TV", False),
        ]

    def test_eight_heterogeneous_devices_individual_classification(self):
        """Validate accurate device_type, model, and is_android for each platform."""
        for ip, server, st, expected_type, expected_model, expected_is_android in self.heterogeneous_definitions:
            headers = {"SERVER": server, "ST": st}
            dev = identify_ssdp_device(headers, ip)
            self.assertEqual(dev.device_type, expected_type, f"Mismatch for {server}")
            self.assertEqual(dev.model, expected_model, f"Mismatch for {server}")
            self.assertEqual(dev.is_android, expected_is_android, f"Mismatch is_android for {server}")

    def test_eight_heterogeneous_devices_simultaneous_discovery(self):
        """Simulate all 8 devices responding simultaneously to discover_devices."""
        packets = [
            (make_ssdp_packet(server=server, st=st), (ip, 1900))
            for ip, server, st, _, _, _ in self.heterogeneous_definitions
        ]
        mock_sock = MockSequencedSocket(packets)

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("companion.opentv.core.discovery.discover_mdns", return_value=[]), \
             patch("companion.opentv.core.discovery.socket.socket", return_value=mock_sock), \
             patch("select.select", side_effect=select_mock):

            # Case A: filter_android=True -> exactly 3 devices returned
            android_only = discover_devices(filter_android=True, methods=["ssdp"])
            self.assertEqual(len(android_only), 3)
            android_ips = [d.ip for d in android_only]
            self.assertEqual(android_ips, ["192.168.1.10", "192.168.1.20", "192.168.1.30"])
            self.assertTrue(all(d.is_android for d in android_only))

            # Reset socket sequence for second run
            mock_sock._sequence = list(packets)

            # Case B: filter_android=False -> all 8 devices returned
            all_devs = discover_devices(filter_android=False, methods=["ssdp"])
            self.assertEqual(len(all_devs), 8)
            all_ips = [d.ip for d in all_devs]
            self.assertEqual(
                all_ips,
                [
                    "192.168.1.10", "192.168.1.20", "192.168.1.30", "192.168.1.40",
                    "192.168.1.50", "192.168.1.60", "192.168.1.70", "192.168.1.80"
                ]
            )

    def test_numeric_ipv4_octet_sorting_stress(self):
        """Deduplication and sorting must handle numeric octet comparison (e.g. 10 < 100)."""
        unsorted_ips = [
            "192.168.1.100",
            "10.0.0.1",
            "192.168.1.2",
            "172.16.0.50",
            "192.168.1.10",
            "10.0.0.25",
            "172.16.0.5",
        ]
        devs = [
            DiscoveredDevice(ip=ip, device_type="android_tv", source="mdns")
            for ip in unsorted_ips
        ]
        sorted_devs = deduplicate_devices(devs, [])
        sorted_ips = [d.ip for d in sorted_devs]

        expected_order = [
            "10.0.0.1",
            "10.0.0.25",
            "172.16.0.5",
            "172.16.0.50",
            "192.168.1.2",
            "192.168.1.10",
            "192.168.1.100",
        ]
        self.assertEqual(sorted_ips, expected_order)

    def test_deduplication_priority_preserves_android_over_all_non_android_ssdp(self):
        """mDNS android_tv classification must NOT be overwritten by any non-Android SSDP report."""
        non_android_types = ["roku", "samsung_tizen", "lg_webos", "sonos", "apple_device", "smart_tv", "unknown"]

        for na_type in non_android_types:
            mdns_dev = DiscoveredDevice(
                ip="192.168.1.99",
                port=5555,
                hostname="android-tv.local",
                device_type="android_tv",
                model="Android TV Device",
                source="mdns",
            )
            ssdp_dev = DiscoveredDevice(
                ip="192.168.1.99",
                port=5555,
                hostname="device.local",
                device_type=na_type,
                model=f"Fake {na_type.title()}",
                source="ssdp",
            )
            merged = deduplicate_devices([mdns_dev], [ssdp_dev])[0]
            self.assertEqual(
                merged.device_type,
                "android_tv",
                f"Failed to preserve android_tv when SSDP reported {na_type}"
            )
            self.assertEqual(merged.source, "mdns+ssdp")

    def test_deduplication_model_selection_matrix(self):
        """Verify model reconciliation across various combinations."""
        # 1. Generic mDNS + Specific SSDP -> Take SSDP
        m1 = DiscoveredDevice(ip="192.168.1.1", model="Android TV Device", device_type="android_tv", source="mdns")
        s1 = DiscoveredDevice(ip="192.168.1.1", model="Sony BRAVIA 4K", device_type="android_tv", source="ssdp")
        self.assertEqual(deduplicate_devices([m1], [s1])[0].model, "Sony BRAVIA 4K")

        # 2. Generic mDNS + Generic Smart TV SSDP -> Keep mDNS
        m2 = DiscoveredDevice(ip="192.168.1.2", model="Android TV Device", device_type="android_tv", source="mdns")
        s2 = DiscoveredDevice(ip="192.168.1.2", model="Smart TV (DIAL)", device_type="smart_tv", source="ssdp")
        self.assertEqual(deduplicate_devices([m2], [s2])[0].model, "Android TV Device")

        # 3. Custom mDNS name + Specific SSDP -> Preserve custom mDNS name
        m3 = DiscoveredDevice(ip="192.168.1.3", model="Living Room TV", device_type="android_tv", source="mdns")
        s3 = DiscoveredDevice(ip="192.168.1.3", model="Sony BRAVIA 4K", device_type="android_tv", source="ssdp")
        self.assertEqual(deduplicate_devices([m3], [s3])[0].model, "Living Room TV")


# ============================================================================
# Suite 3: Socket Error Injections & Malformed Header Hardening
# ============================================================================

class TestSocketErrorInjectionStress(unittest.TestCase):
    """Stress test non-blocking socket exceptions, OS errors, and corrupted wire datagrams."""

    def test_ssdp_eagain_and_wsaeconnreset_sequence(self):
        """Sequence with BlockingIOError, ConnectionResetError, valid packet, OSError, valid packet."""
        pkt1 = make_ssdp_packet(server="Sony-BRAVIA", st="upnp:rootdevice")
        pkt2 = make_ssdp_packet(server="Eureka/1.0", st="upnp:rootdevice")

        sequence = [
            BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable"),
            (pkt1, ("192.168.1.201", 1900)),
            ConnectionResetError(10054, "WSAECONNRESET"),
            OSError(errno.EINTR, "Interrupted system call"),
            (pkt2, ("192.168.1.202", 1900)),
            socket.error(errno.ENETUNREACH, "Network unreachable"),
        ]
        mock_sock = MockSequencedSocket(sequence)

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_ssdp(sock=mock_sock, timeout=0.5)

        self.assertEqual(len(devices), 2)
        ips = {d.ip for d in devices}
        self.assertEqual(ips, {"192.168.1.201", "192.168.1.202"})

    def test_mdns_socket_error_injection_resilience(self):
        """discover_mdns must not crash when recvfrom raises transient socket exceptions."""
        valid_query = build_mdns_query(ADB_SERVICE)
        # Build synthetic valid response datagram
        # Header (12 bytes) + Question (copied from query) + PTR Answer
        tx_id, flags, qd, an, ns, ar = 0, 0x8400, 1, 1, 0, 0
        header = struct.pack("!HHHHHH", tx_id, flags, qd, an, ns, ar)
        qname = b"\x04_adb\x04_tcp\x05local\x00"
        question = qname + struct.pack("!HH", 12, 1)
        rdata = b"\x07tv-room\xC0\x0C"  # tv-room._adb._tcp.local
        answer = qname + struct.pack("!HHIH", 12, 1, 120, len(rdata)) + rdata
        valid_dns_pkt = header + question + answer

        sequence = [
            BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable"),
            ConnectionResetError(10054, "WSAECONNRESET"),
            (valid_dns_pkt, ("192.168.1.205", 5353)),
            OSError(errno.EIO, "I/O error"),
        ]
        mock_sock = MockSequencedSocket(sequence)

        def select_mock(r, w, x, t):
            if mock_sock._sequence:
                return ([mock_sock], [], [])
            return ([], [], [])

        with patch("select.select", side_effect=select_mock):
            devices = discover_mdns(sock=mock_sock, timeout=0.5)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip, "192.168.1.205")

    def test_corrupted_udp_ssdp_headers_fuzzing(self):
        """Corrupted SSDP datagrams must be safely rejected without unhandled exceptions."""
        adversarial_payloads = [
            b"",
            b"\n",
            b"\r\n\r\n",
            b"HTTP/1.1 200 OK",
            b"HTTP/1.1 200 OK\r\n",
            b"GARBAGE_WITHOUT_HTTP_SIGNATURE\r\nST: upnp:rootdevice\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nLINE_WITHOUT_COLON\r\n\r\n",
            b"\x00\x01\x02\x03\xff\xfe\xfd\r\nST: dial\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nST: \xff\xfe\xfd\r\nSERVER: Sony\r\n\r\n",
            b": missing key\r\nkey:\r\n: \r\n",
            b"A" * 70000,  # Oversized datagram
        ]

        for payload in adversarial_payloads:
            status, headers = parse_ssdp_headers(payload)
            self.assertIsInstance(status, str)
            self.assertIsInstance(headers, dict)
            # identify_ssdp_device should survive empty or corrupted headers
            dev = identify_ssdp_device(headers, "192.168.1.250")
            self.assertIsInstance(dev, DiscoveredDevice)

    def test_corrupted_udp_mdns_headers_and_pointers(self):
        """Corrupted mDNS byte streams must be safely rejected."""
        malformed_packets = [
            b"",
            b"\x00",
            b"\x00" * 11,  # Header truncated (< 12 bytes)
            struct.pack("!HHHHHH", 0, 0, 10, 0, 0, 0),  # QDCOUNT claims 10, but 0 bytes follow
            struct.pack("!HHHHHH", 0, 0x8400, 0, 10, 0, 0),  # ANCOUNT claims 10, but 0 bytes follow
            b"\x00" * 12 + b"\xC0\x00",  # Pointer loop
            b"\x00" * 12 + b"\xFF" * 50,  # Corrupted labels
        ]

        for pkt in malformed_packets:
            try:
                records = parse_dns_response(pkt)
                self.assertIsInstance(records, list)
            except Exception as e:
                self.fail(f"parse_dns_response crashed on malformed packet: {e}")


# ============================================================================
# Suite 4: Edge Boundary & Protocol Adversarial Stress
# ============================================================================

class TestEdgeBoundaryAdversarialStress(unittest.TestCase):
    """Deep boundary stress testing across parser limits and extreme inputs."""

    def test_parse_dns_name_extreme_negative_offsets(self):
        """parse_dns_name handles 32-bit and 64-bit negative offsets without IndexError."""
        buf = b"\x03foo\x03bar\x00"
        for neg_off in [-1, -10, -100, -2**31, -2**63]:
            name, off = parse_dns_name(buf, neg_off)
            self.assertEqual(name, "")
            self.assertEqual(off, neg_off)

    def test_discover_devices_zero_and_negative_timeout(self):
        """discover_devices survives zero and negative timeouts gracefully."""
        res_zero = discover_devices(timeout=0.0, methods=["ssdp", "mdns"])
        self.assertIsInstance(res_zero, list)

        res_neg = discover_devices(timeout=-1.5, methods=["ssdp", "mdns"])
        self.assertIsInstance(res_neg, list)

    def test_discover_devices_empty_and_unknown_methods(self):
        """discover_devices handles empty or unrecognized discovery methods."""
        res_empty = discover_devices(timeout=0.1, methods=[])
        self.assertEqual(res_empty, [])

        res_unknown = discover_devices(timeout=0.1, methods=["bluetooth", "zigbee"])
        self.assertEqual(res_unknown, [])

    def test_ssdp_notify_packet_parsing(self):
        """SSDP NOTIFY * HTTP/1.1 broadcast advertisement parsing."""
        notify_raw = (
            "NOTIFY * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "NT: upnp:rootdevice\r\n"
            "NTS: ssdp:alive\r\n"
            "LOCATION: http://192.168.1.188:8008/desc.xml\r\n"
            "SERVER: Linux/4.19 UPnP/1.0 Sony-BRAVIA-4K/1.0\r\n"
            "USN: uuid:sony-123::upnp:rootdevice\r\n\r\n"
        ).encode("utf-8")

        status, headers = parse_ssdp_headers(notify_raw)
        self.assertEqual(status, "NOTIFY * HTTP/1.1")
        self.assertEqual(headers.get("NTS"), "ssdp:alive")
        dev = identify_ssdp_device(headers, "192.168.1.188")
        self.assertEqual(dev.device_type, "android_tv")
        self.assertIn("Sony BRAVIA", dev.model)
        self.assertTrue(dev.is_android)

    def test_discovered_device_properties_and_serialization(self):
        """DiscoveredDevice serialization and display string edge cases."""
        # Non-standard port, empty hostname, mixed case device_type
        d = DiscoveredDevice(
            ip="10.20.30.40",
            port=5556,
            device_type="android_tv",
            model="",
            source="mdns+ssdp",
        )
        self.assertEqual(d.address, "10.20.30.40:5556")
        self.assertTrue(d.is_android)
        self.assertIn("Android Tv [ANDROID_TV] - 10.20.30.40:5556 (mdns+ssdp)", d.display_name)
        d_dict = d.to_dict()
        self.assertEqual(d_dict["ip"], "10.20.30.40")
        self.assertEqual(d_dict["port"], 5556)
        self.assertTrue(d_dict["is_android"])


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)

