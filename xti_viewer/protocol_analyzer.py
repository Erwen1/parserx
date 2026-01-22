"""
Advanced protocol analyzer for XTI viewer - analyzes higher-layer protocols
in SEND/RECEIVE DATA payloads according to SGP.32-style RSP traffic.

Supports:
- TLS handshake analysis (ClientHello/ServerHello, SNI extraction)
- DNS message decoding
- ASN.1/BER structure detection
- JSON parsing and validation
- X.509 certificate chain parsing
- Payload classification and media type detection
"""

import struct
import json
import binascii
import re
import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class PayloadType(Enum):
    """Enumeration of detected payload types"""
    TLS_HANDSHAKE_CLIENT_HELLO = "TLS ClientHello"
    TLS_HANDSHAKE_SERVER_HELLO = "TLS ServerHello"
    TLS_HANDSHAKE_CERTIFICATE = "TLS Certificate"
    TLS_APPLICATION_DATA = "TLS Application Data"
    DNS_QUERY = "DNS Query"
    DNS_RESPONSE = "DNS Response"
    HTTP_REQUEST = "HTTP Request"
    HTTP_RESPONSE = "HTTP Response"
    JSON_MESSAGE = "JSON Message"
    ASN1_BER_STRUCTURE = "ASN.1/BER Structure"
    BINARY_DATA = "Binary Data"
    UNKNOWN = "Unknown"


@dataclass
class TlsHandshakeInfo:
    """Information extracted from TLS handshake messages"""
    handshake_type: str
    version: str
    cipher_suites: List[str]
    chosen_cipher: Optional[str]
    sni_hostname: Optional[str]
    extensions: List[str]
    compliance_ok: bool
    compliance_issues: List[str]


@dataclass
class DnsInfo:
    """Information extracted from DNS messages"""
    transaction_id: int
    is_query: bool
    questions: List[Dict[str, Any]]
    answers: List[Dict[str, Any]]
    nameservers: List[Dict[str, Any]]
    additional: List[Dict[str, Any]]


@dataclass
class CertificateInfo:
    """Information extracted from X.509 certificates"""
    subject_cn: str
    issuer_cn: str
    valid_from: datetime.datetime
    valid_to: datetime.datetime
    public_key_type: str
    is_valid: bool
    issues: List[str]


@dataclass
class AnalysisResult:
    """Complete analysis result for a payload"""
    payload_type: PayloadType
    media_type: Optional[str]
    tls_info: Optional[TlsHandshakeInfo]
    dns_info: Optional[DnsInfo]
    certificates: List[CertificateInfo]
    json_content: Optional[Dict[str, Any]]
    asn1_structure: Optional[List[str]]
    channel_role: Optional[str]
    raw_classification: str


class ChannelRoleDetector:
    """Maps SNI hostnames and IP patterns to channel roles"""
    
    # Hostname pattern to role mapping
    HOSTNAME_PATTERNS = {
        r'.*smdp.*': 'SM-DP+',
        r'.*smdpplus.*': 'SM-DP+',
        r'.*dpplus.*': 'DP+',
        r'.*smds.*': 'SM-DS',
        r'.*eim.*': 'eIM',
        r'.*tac\..*': 'TAC',
        r'.*thales.*': 'TAC',
    }
    
    @classmethod
    def detect_role_from_sni(cls, hostname: str) -> Optional[str]:
        """Detect channel role from SNI hostname"""
        if not hostname:
            return None
            
        hostname_lower = hostname.lower()
        for pattern, role in cls.HOSTNAME_PATTERNS.items():
            if re.match(pattern, hostname_lower):
                return role
        return None


class CertificateAnalyzer:
    """Analyzes X.509 certificates from TLS handshakes"""
    
    @classmethod
    def parse_certificate_chain(cls, data: bytes) -> List[CertificateInfo]:
        """Parse certificate chain from TLS Certificate handshake message"""
        try:
            certificates = []
            
            # Check TLS record header
            if len(data) < 5 or data[0] != 0x16:  # Must be handshake record
                return certificates
            
            pos = 5  # Skip TLS record header
            
            # Check handshake message type (should be 11 for Certificate)
            if data[pos] != 0x0B:
                return certificates
            pos += 4  # Skip handshake header
            
            # Parse certificate chain length
            if pos + 3 > len(data):
                return certificates
            chain_len = struct.unpack(">I", b'\x00' + data[pos:pos+3])[0]
            pos += 3
            
            chain_end = pos + chain_len
            
            # Parse individual certificates
            while pos + 3 < chain_end:
                cert_len = struct.unpack(">I", b'\x00' + data[pos:pos+3])[0]
                pos += 3
                
                if pos + cert_len > chain_end:
                    break
                
                cert_data = data[pos:pos+cert_len]
                cert_info = cls._parse_x509_certificate(cert_data)
                if cert_info:
                    certificates.append(cert_info)
                
                pos += cert_len
            
            return certificates
            
        except Exception:
            return []
    
    @classmethod
    def _parse_x509_certificate(cls, cert_data: bytes) -> Optional[CertificateInfo]:
        """Parse basic X.509 certificate information using minimal ASN.1 parsing"""
        try:
            # This is a simplified X.509 parser - in production you'd use a library like cryptography
            # For demo purposes, we'll extract what we can with basic ASN.1 parsing
            
            if len(cert_data) < 10:
                return None
            
            # Basic ASN.1 structure validation
            if cert_data[0] != 0x30:  # Must start with SEQUENCE
                return None
            
            # Extract some basic info through pattern matching
            # This is a simplified approach - real implementation would use proper ASN.1 decoder
            
            # Extract CN values by scanning for OID 2.5.4.3 (CN) followed by string
            cn_values = cls._extract_cn_values(cert_data)
            # Heuristic: first CN is usually issuer, last CN is subject
            subject_cn = cn_values[-1] if cn_values else None
            issuer_cn = cn_values[0] if len(cn_values) > 1 else None
            
            # For validity dates, we'd need proper ASN.1 parsing
            # Using current time +/- reasonable defaults for demo
            now = datetime.datetime.now()
            valid_from = now - datetime.timedelta(days=365)
            valid_to = now + datetime.timedelta(days=365)
            
            return CertificateInfo(
                subject_cn=subject_cn or "Unknown Subject",
                issuer_cn=issuer_cn or "Unknown Issuer",
                valid_from=valid_from,
                valid_to=valid_to,
                public_key_type="RSA",  # Default assumption
                is_valid=True,
                issues=[]
            )
            
        except Exception:
            return None
    
    @classmethod
    def _extract_cn_values(cls, cert_data: bytes) -> List[str]:
        """Extract CN values by scanning for OID 2.5.4.3 (CN) followed by a string value.
        Handles UTF8String (0x0C), PrintableString (0x13), IA5String (0x16) with short/long lengths.
        """
        values: List[str] = []
        try:
            oid = b"\x06\x03\x55\x04\x03"  # 2.5.4.3
            i = 0
            n = len(cert_data)
            while i < n - len(oid) - 2:
                j = cert_data.find(oid, i)
                if j < 0:
                    break
                k = j + len(oid)
                if k >= n:
                    break
                tag = cert_data[k]
                k += 1
                if k >= n:
                    break
                length_byte = cert_data[k]
                k += 1
                if length_byte & 0x80:
                    num_len = length_byte & 0x7F
                    if k + num_len > n:
                        break
                    L = 0
                    for m in range(num_len):
                        L = (L << 8) | cert_data[k + m]
                    k += num_len
                    length = L
                else:
                    length = length_byte
                if k + length > n:
                    i = j + 1
                    continue
                val = cert_data[k:k+length]
                if tag in (0x0C, 0x13, 0x16) and length > 0:
                    try:
                        s = val.decode('utf-8', errors='ignore').strip()
                    except Exception:
                        try:
                            s = val.decode('latin-1', errors='ignore').strip()
                        except Exception:
                            s = ''
                    s = ''.join(ch for ch in s if 32 <= ord(ch) <= 126)
                    if s:
                        values.append(s)
                i = k + length
        except Exception:
            return values
        return values


class TlsAnalyzer:
    """Analyzes TLS handshake messages"""
    
    # TLS version mappings
    TLS_VERSIONS = {
        (3, 1): "TLS 1.0",
        (3, 2): "TLS 1.1", 
        (3, 3): "TLS 1.2",
        (3, 4): "TLS 1.3"
    }
    
    # Common cipher suites (subset for SGP.32 compliance)
    CIPHER_SUITES = {
        0x002F: "TLS_RSA_WITH_AES_128_CBC_SHA",
        0x0035: "TLS_RSA_WITH_AES_256_CBC_SHA",
        # Correct non-RSA mappings for observed TAC suites
        0x008B: "ECDHE_ECDSA_AES_128_CBC",
        0x008C: "ECDHE_ECDSA_AES_256_CBC",
        0x009C: "TLS_RSA_WITH_AES_128_GCM_SHA256",
        0x009D: "TLS_RSA_WITH_AES_256_GCM_SHA384",
        0xC013: "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
        0xC014: "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
        0xC027: "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256",
        0xC028: "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384",
        0xC02B: "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
        0xC02C: "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
        0xC02F: "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
        0xC030: "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
        0x1301: "TLS_AES_128_GCM_SHA256",
        0x1302: "TLS_AES_256_GCM_SHA384",
        0x1303: "TLS_CHACHA20_POLY1305_SHA256"
    }
    
    # SGP.32 compliant cipher suites
    SGP32_APPROVED_CIPHERS = {
        0xC02F, 0xC030,  # ECDHE-RSA-AES-GCM
        0x1301, 0x1302,  # TLS 1.3 AES-GCM
    }
    
    @classmethod
    def detect_tls_record(cls, data: bytes) -> Optional[Tuple[int, int, int]]:
        """Detect TLS record header. Returns (record_type, version_major, version_minor)"""
        if len(data) < 5:
            return None
            
        record_type = data[0]
        version_major = data[1]
        version_minor = data[2]
        
        # Check for valid TLS record type and version
        if record_type in [0x16, 0x17, 0x15, 0x14] and version_major == 3 and version_minor in [1, 2, 3, 4]:
            return (record_type, version_major, version_minor)
        return None
    
    @classmethod
    def parse_client_hello(cls, data: bytes) -> Optional[TlsHandshakeInfo]:
        """Parse TLS ClientHello message"""
        try:
            if len(data) < 40:
                return None
                
            # Check TLS record header
            tls_info = cls.detect_tls_record(data)
            if not tls_info or tls_info[0] != 0x16:  # Must be handshake record
                return None
            
            # Skip TLS record header (5 bytes)
            pos = 5
            
            # Check handshake message type (should be 1 for ClientHello)
            if data[pos] != 0x01:
                return None
            pos += 4  # Skip handshake header
            
            # Parse TLS version
            version_major, version_minor = data[pos:pos+2]
            version_str = cls.TLS_VERSIONS.get((version_major, version_minor), f"Unknown {version_major}.{version_minor}")
            pos += 2
            
            # Skip random (32 bytes)
            pos += 32
            
            # Session ID length
            if pos >= len(data):
                return None
            session_id_len = data[pos]
            pos += 1 + session_id_len
            
            # Cipher suites
            if pos + 2 >= len(data):
                return None
            cipher_suites_len = struct.unpack(">H", data[pos:pos+2])[0]
            pos += 2
            
            cipher_suites = []
            for i in range(0, cipher_suites_len, 2):
                if pos + 2 > len(data):
                    break
                cipher_id = struct.unpack(">H", data[pos:pos+2])[0]
                cipher_name = cls.CIPHER_SUITES.get(cipher_id, f"Unknown_0x{cipher_id:04X}")
                cipher_suites.append(cipher_name)
                pos += 2
            
            # Skip compression methods
            if pos >= len(data):
                return None
            compression_len = data[pos]
            pos += 1 + compression_len
            
            # Parse extensions
            extensions = []
            sni_hostname = None
            
            if pos + 2 < len(data):
                extensions_len = struct.unpack(">H", data[pos:pos+2])[0]
                pos += 2
                extensions_end = pos + extensions_len
                
                while pos + 4 < extensions_end:
                    ext_type = struct.unpack(">H", data[pos:pos+2])[0]
                    ext_len = struct.unpack(">H", data[pos+2:pos+4])[0]
                    pos += 4
                    
                    if ext_type == 0:  # SNI extension
                        sni_hostname = cls._parse_sni_extension(data[pos:pos+ext_len])
                        extensions.append("SNI")
                    elif ext_type == 10:
                        extensions.append("supported_groups")
                    elif ext_type == 13:
                        extensions.append("signature_algorithms")
                    elif ext_type == 16:
                        extensions.append("ALPN")
                    else:
                        extensions.append(f"Extension_{ext_type}")
                    
                    pos += ext_len
            
            # Compliance check
            compliance_issues = []
            if version_major < 3 or (version_major == 3 and version_minor < 3):
                compliance_issues.append("TLS version < 1.2")
            
            compliant_ciphers = [cs for cs in cipher_suites if any(cls.CIPHER_SUITES.get(cid) == cs for cid in cls.SGP32_APPROVED_CIPHERS)]
            if not compliant_ciphers:
                compliance_issues.append("No SGP.32 approved cipher suites")
            
            return TlsHandshakeInfo(
                handshake_type="ClientHello",
                version=version_str,
                cipher_suites=cipher_suites[:5],  # Show first 5 
                chosen_cipher=None,
                sni_hostname=sni_hostname,
                extensions=extensions,
                compliance_ok=len(compliance_issues) == 0,
                compliance_issues=compliance_issues
            )
            
        except Exception:
            return None
    
    @classmethod
    def _parse_sni_extension(cls, ext_data: bytes) -> Optional[str]:
        """Parse SNI extension to extract hostname"""
        try:
            if len(ext_data) < 5:
                return None
                
            # Skip server name list length (2 bytes)
            pos = 2
            # Check server name type (should be 0 for hostname)
            if ext_data[pos] != 0:
                return None
            pos += 1
            
            # Get hostname length
            hostname_len = struct.unpack(">H", ext_data[pos:pos+2])[0]
            pos += 2
            
            # Extract hostname
            if pos + hostname_len <= len(ext_data):
                hostname = ext_data[pos:pos+hostname_len].decode('utf-8', errors='ignore')
                return hostname
                
        except Exception:
            pass
        return None


class DnsAnalyzer:
    """Analyzes DNS messages"""
    
    DNS_TYPES = {
        1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR",
        15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV"
    }
    
    @classmethod
    def parse_dns_message(cls, data: bytes, is_udp53: bool = True) -> Optional[DnsInfo]:
        """Parse DNS message"""
        try:
            if len(data) < 12:  # DNS header is 12 bytes minimum
                return None
                
            # Parse header
            header = struct.unpack(">HHHHHH", data[:12])
            transaction_id = header[0]
            flags = header[1]
            qdcount = header[2]
            ancount = header[3]
            nscount = header[4]
            arcount = header[5]
            
            is_query = (flags & 0x8000) == 0
            
            pos = 12
            
            # Parse questions
            questions = []
            for _ in range(qdcount):
                qname, pos = cls._parse_domain_name(data, pos)
                if pos + 4 > len(data):
                    break
                qtype = struct.unpack(">H", data[pos:pos+2])[0]
                qclass = struct.unpack(">H", data[pos+2:pos+4])[0]
                pos += 4
                
                questions.append({
                    'name': qname,
                    'type': cls.DNS_TYPES.get(qtype, f"TYPE{qtype}"),
                    'class': qclass
                })
            
            # Parse answers
            answers = []
            for _ in range(ancount):
                answer, pos = cls._parse_dns_rr(data, pos)
                if answer:
                    answers.append(answer)
            
            # Parse nameservers
            nameservers = []
            for _ in range(nscount):
                ns, pos = cls._parse_dns_rr(data, pos)
                if ns:
                    nameservers.append(ns)
            
            # Parse additional records
            additional = []
            for _ in range(arcount):
                add, pos = cls._parse_dns_rr(data, pos)
                if add:
                    additional.append(add)
            
            return DnsInfo(
                transaction_id=transaction_id,
                is_query=is_query,
                questions=questions,
                answers=answers,
                nameservers=nameservers,
                additional=additional
            )
            
        except Exception:
            return None
    
    @classmethod
    def _parse_domain_name(cls, data: bytes, pos: int) -> Tuple[str, int]:
        """Parse domain name from DNS message with proper null terminator handling."""
        labels = []
        original_pos = pos
        jumped = False
        max_labels = 127  # RFC limit
        
        for _ in range(max_labels):
            if pos >= len(data):
                break
            
            length = data[pos]
            
            # Check for null terminator FIRST (end of domain name)
            if length == 0:
                pos += 1
                break
            
            # Check for compression pointer
            if (length & 0xC0) == 0xC0:
                if not jumped:
                    original_pos = pos + 2
                    jumped = True
                if pos + 1 >= len(data):
                    break
                pos = ((length & 0x3F) << 8) | data[pos + 1]
                continue
            
            # Valid label length should be 1-63
            if length > 63:
                break
            
            pos += 1
            if pos + length > len(data):
                break
            
            # Extract label, filtering out any embedded nulls
            label_bytes = data[pos:pos+length]
            # Remove any null bytes that shouldn't be there
            label_bytes = label_bytes.replace(b'\x00', b'')
            if label_bytes:
                labels.append(label_bytes.decode('utf-8', errors='ignore'))
            pos += length
        
        return '.'.join(labels), original_pos if jumped else pos
    
    @classmethod
    def _parse_dns_rr(cls, data: bytes, pos: int) -> Tuple[Optional[Dict[str, Any]], int]:
        """Parse DNS resource record"""
        try:
            name, pos = cls._parse_domain_name(data, pos)
            if pos + 10 > len(data):
                return None, pos
                
            rr_type = struct.unpack(">H", data[pos:pos+2])[0]
            rr_class = struct.unpack(">H", data[pos+2:pos+4])[0]
            ttl = struct.unpack(">L", data[pos+4:pos+8])[0]
            rdlength = struct.unpack(">H", data[pos+8:pos+10])[0]
            pos += 10
            
            if pos + rdlength > len(data):
                return None, pos + rdlength
            
            rdata = data[pos:pos+rdlength]
            pos += rdlength
            
            # Parse rdata based on type
            parsed_data = None
            if rr_type == 1 and rdlength == 4:  # A record
                parsed_data = ".".join(str(b) for b in rdata)
            elif rr_type == 28 and rdlength == 16:  # AAAA record
                parsed_data = ":".join(f"{b:02x}" for b in rdata)
            else:
                parsed_data = binascii.hexlify(rdata).decode()
            
            return {
                'name': name,
                'type': cls.DNS_TYPES.get(rr_type, f"TYPE{rr_type}"),
                'class': rr_class,
                'ttl': ttl,
                'data': parsed_data
            }, pos
            
        except Exception:
            return None, pos


class ProtocolAnalyzer:
    """Main protocol analyzer class"""
    
    @classmethod
    def analyze_payload(cls, payload: bytes, channel_info: Optional[Dict] = None) -> AnalysisResult:
        """Analyze payload and return comprehensive analysis"""
        
        # Initialize result
        result = AnalysisResult(
            payload_type=PayloadType.UNKNOWN,
            media_type=None,
            tls_info=None,
            dns_info=None,
            certificates=[],
            json_content=None,
            asn1_structure=None,
            channel_role=None,
            raw_classification="Unknown binary data"
        )
        
        if not payload:
            return result
        
        # Try different analysis methods in order of priority
        # First, try to align to the start of a TLS record if present (handles wrappers)
        payload = cls._align_tls_start(payload)

        # 1. TLS analysis
        tls_info = TlsAnalyzer.parse_client_hello(payload)
        if tls_info:
            result.payload_type = PayloadType.TLS_HANDSHAKE_CLIENT_HELLO
            result.tls_info = tls_info
            result.raw_classification = f"TLS ClientHello ({tls_info.version})"
            if tls_info.sni_hostname:
                result.channel_role = ChannelRoleDetector.detect_role_from_sni(tls_info.sni_hostname)
            return result
        
        # Check for other TLS record types
        tls_record = TlsAnalyzer.detect_tls_record(payload)
        if tls_record:
            record_type = tls_record[0]
            if record_type == 0x17:
                result.payload_type = PayloadType.TLS_APPLICATION_DATA
                result.raw_classification = "TLS Application Data"
                return result
            if record_type == 0x14:
                result.payload_type = PayloadType.TLS_APPLICATION_DATA
                result.raw_classification = "TLS Change Cipher Spec"
                return result
            if record_type == 0x15:
                result.payload_type = PayloadType.TLS_APPLICATION_DATA
                # Decode alert if possible
                detail = cls._decode_tls_alert(payload)
                result.raw_classification = detail or "TLS Alert"
                return result

            # Handshake record: inspect handshake message type
            if record_type == 0x16 and len(payload) >= 9:
                # Scan all handshake messages within this record
                rec_len = (payload[3] << 8) | payload[4]
                end = min(len(payload), 5 + rec_len)
                pos = 5
                saw_serverhello = False
                serverhello_version = ""
                serverhello_cipher = None
                collected_certs: List[CertificateInfo] = []

                while pos + 4 <= end:
                    hs_type = payload[pos]
                    hs_len = (payload[pos+1] << 16) | (payload[pos+2] << 8) | payload[pos+3]
                    body_start = pos + 4
                    body_end = body_start + hs_len
                    if body_end > end:
                        break

                    if hs_type == 0x02 and body_start + 2 <= body_end and not saw_serverhello:
                        try:
                            vmaj, vmin = payload[body_start], payload[body_start+1]
                            serverhello_version = TlsAnalyzer.TLS_VERSIONS.get((vmaj, vmin), f"Unknown {vmaj}.{vmin}")
                            p = body_start + 2  # version
                            p += 32  # random
                            sid_len = payload[p] if p < body_end else 0
                            p += 1 + sid_len
                            if p + 2 <= body_end:
                                cipher_id = (payload[p] << 8) | payload[p+1]
                                serverhello_cipher = TlsAnalyzer.CIPHER_SUITES.get(cipher_id, f"Unknown_0x{cipher_id:04X}")
                            saw_serverhello = True
                        except Exception:
                            pass
                    elif hs_type == 0x0B:
                        # Build a minimal TLS record buffer around this Certificate handshake to reuse the parser
                        try:
                            hs_body = payload[body_start:body_end]
                            rec = bytearray()
                            rec.extend(b"\x16\x03\x03")
                            rec_len2 = 4 + len(hs_body)
                            rec.extend(bytes([(rec_len2 >> 8) & 0xFF, rec_len2 & 0xFF]))
                            rec.extend(bytes([0x0B, (len(hs_body) >> 16) & 0xFF, (len(hs_body) >> 8) & 0xFF, len(hs_body) & 0xFF]))
                            rec.extend(hs_body)
                            certs = CertificateAnalyzer.parse_certificate_chain(bytes(rec))
                            if certs:
                                collected_certs.extend(certs)
                        except Exception:
                            pass
                    elif hs_type == 0x0E:
                        # ServerHelloDone - nothing extra to parse here
                        result.raw_classification = "TLS ServerHello Done"

                    pos = body_end

                # Populate result based on what we found
                if saw_serverhello:
                    result.payload_type = PayloadType.TLS_HANDSHAKE_SERVER_HELLO
                    result.tls_info = TlsHandshakeInfo(
                        handshake_type="ServerHello",
                        version=serverhello_version or "",
                        cipher_suites=[],
                        chosen_cipher=serverhello_cipher,
                        sni_hostname=None,
                        extensions=[],
                        compliance_ok=True,
                        compliance_issues=[]
                    )
                    bits = []
                    if serverhello_version:
                        bits.append(serverhello_version)
                    if serverhello_cipher:
                        bits.append(f"cipher {serverhello_cipher}")
                    result.raw_classification = "TLS ServerHello (" + " • ".join(bits) + ")" if bits else "TLS ServerHello"
                else:
                    result.payload_type = PayloadType.TLS_HANDSHAKE_SERVER_HELLO
                    result.raw_classification = "TLS Handshake (other)"

                if collected_certs:
                    result.certificates = collected_certs
                return result
        
        # 2. DNS analysis (if UDP port 53 or DNS pattern detected)
        is_udp53 = channel_info and channel_info.get('protocol') == 'UDP' and channel_info.get('port') == 53
        
        # Try DNS parsing if port 53 is indicated OR if payload looks like DNS
        try_dns = is_udp53
        dns_offset = 0
        if not try_dns and len(payload) > 12:
            # Check for DNS-like patterns and find where DNS actually starts
            dns_offset = cls._find_dns_start(payload)
            try_dns = dns_offset >= 0
        
        if try_dns:
            # Strip BIP/GPRS header if present
            dns_payload = cls._strip_bip_wrapper(payload) if dns_offset == 0 else payload[dns_offset:]
            dns_info = DnsAnalyzer.parse_dns_message(dns_payload, True)
            if dns_info:
                result.payload_type = PayloadType.DNS_QUERY if dns_info.is_query else PayloadType.DNS_RESPONSE
                result.dns_info = dns_info
                result.raw_classification = f"DNS {'Query' if dns_info.is_query else 'Response'}"
                if dns_info.questions and dns_info.questions[0]['name']:
                    result.channel_role = ChannelRoleDetector.detect_role_from_sni(dns_info.questions[0]['name'])
                return result
        
        # 3. HTTP detection
        payload_str = cls._safe_decode(payload[:200])
        if payload_str:
            if payload_str.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'HEAD ', 'OPTIONS ')):
                result.payload_type = PayloadType.HTTP_REQUEST
                result.raw_classification = "HTTP Request"
                result.media_type = cls._extract_http_content_type(payload_str)
                return result
            elif payload_str.startswith('HTTP/'):
                result.payload_type = PayloadType.HTTP_RESPONSE
                result.raw_classification = "HTTP Response"
                result.media_type = cls._extract_http_content_type(payload_str)
                return result
        
        # 4. JSON detection
        json_content = cls._try_parse_json(payload)
        if json_content:
            result.payload_type = PayloadType.JSON_MESSAGE
            result.json_content = json_content
            result.raw_classification = "JSON Message"
            result.media_type = "application/json"
            return result
        
        # 5. ASN.1/BER detection
        asn1_structure = cls._detect_asn1_ber(payload)
        if asn1_structure:
            result.payload_type = PayloadType.ASN1_BER_STRUCTURE
            result.asn1_structure = asn1_structure
            result.raw_classification = "ASN.1/BER Structure"
            return result
        
        # 6. Binary data
        result.payload_type = PayloadType.BINARY_DATA
        result.raw_classification = f"Binary data ({len(payload)} bytes)"
        
        return result

    @classmethod
    def _align_tls_start(cls, payload: bytes) -> bytes:
        """Scan early bytes to locate a TLS record header and trim to it if found."""
        try:
            if not payload or len(payload) < 5:
                return payload
            max_scan = min(len(payload) - 5, 128)
            for off in range(0, max_scan + 1):
                hdr = TlsAnalyzer.detect_tls_record(payload[off:off+5])
                if hdr:
                    return payload[off:]
        except Exception:
            pass
        return payload

    @classmethod
    def _decode_tls_alert(cls, data: bytes) -> Optional[str]:
        """Decode TLS Alert level and description if record is at start of buffer."""
        try:
            if len(data) < 7 or data[0] != 0x15:
                return None
            level = data[5]
            desc = data[6]
            level_s = {1: 'warning', 2: 'fatal'}.get(level, f'level_{level}')
            desc_map = {
                0: 'close_notify',
                10: 'unexpected_message',
                20: 'bad_record_mac',
                21: 'decryption_failed',
                22: 'record_overflow',
                40: 'handshake_failure',
                41: 'no_certificate',
                42: 'bad_certificate',
                43: 'unsupported_certificate',
                44: 'certificate_revoked',
                45: 'certificate_expired',
                46: 'certificate_unknown',
                47: 'illegal_parameter',
                48: 'unknown_ca',
                49: 'access_denied',
                50: 'decode_error',
                51: 'decrypt_error',
                60: 'export_restriction',
                70: 'protocol_version',
                71: 'insufficient_security',
                80: 'internal_error',
                86: 'inappropriate_fallback',
                90: 'user_canceled',
                109: 'missing_extension',
                110: 'unsupported_extension',
                112: 'unrecognized_name',
                113: 'bad_certificate_status_response',
                115: 'unknown_psk_identity',
                116: 'certificate_required',
                120: 'no_application_protocol',
            }
            desc_s = desc_map.get(desc, f'alert_{desc}')
            # Normalize alert level and description names
            level_map = {
                'level_1': 'warning',
                'level_2': 'fatal',
                'level_151': 'warning',
                'level_172': 'fatal',
            }
            desc_map = {
                'alert_0': 'close_notify',
                'alert_10': 'unexpected_message',
                'alert_20': 'bad_record_mac',
                'alert_21': 'decryption_failed_RESERVED',
                'alert_22': 'record_overflow',
                'alert_30': 'decompression_failure',
                'alert_40': 'handshake_failure',
                'alert_41': 'no_certificate_RESERVED',
                'alert_42': 'bad_certificate',
                'alert_43': 'unsupported_certificate',
                'alert_44': 'certificate_revoked',
                'alert_45': 'certificate_expired',
                'alert_46': 'certificate_unknown',
                'alert_47': 'illegal_parameter',
                'alert_48': 'unknown_ca',
                'alert_49': 'access_denied',
                'alert_50': 'decode_error',
                'alert_51': 'decrypt_error',
                'alert_70': 'protocol_version',
                'alert_71': 'insufficient_security',
                'alert_80': 'internal_error',
                'alert_90': 'user_canceled',
                'alert_100': 'no_renegotiation',
                'alert_109': 'missing_extension',
                'alert_110': 'unsupported_extension',
                'alert_111': 'certificate_unobtainable',
                'alert_112': 'unrecognized_name',
                'alert_113': 'bad_certificate_status_response',
                'alert_114': 'bad_certificate_hash_value',
                'alert_115': 'unknown_psk_identity',
                'alert_82': 'close_notify',
                'alert_11': 'unexpected_message',
            }
            level = level_map.get(level_s, level_s)
            desc = desc_map.get(desc_s, desc_s)
            return f"TLS Alert: {level}, {desc}"
        except Exception:
            return None
    
    @classmethod
    def _strip_bip_wrapper(cls, payload: bytes) -> bytes:
        """Strip BIP/GPRS wrapper from payload if present."""
        if len(payload) < 12:
            return payload
        
        # First check if it's already DNS/TLS at offset 0 (no wrapper)
        if cls._looks_like_dns_at(payload, 0) or cls._looks_like_tls_at(payload, 0):
            return payload
        
        # Common BIP header patterns:
        # 02 03 01 00 ... (DNS over BIP)
        # 02 03 81 80 ... (DNS response over BIP)
        if payload[0:2] == b'\x02\x03':
            # BIP header detected, try to find where actual protocol starts
            # Usually 10-12 bytes
            for offset in [10, 12, 14, 16]:
                if offset < len(payload):
                    # Check if DNS or TLS starts here
                    if cls._looks_like_dns_at(payload, offset) or cls._looks_like_tls_at(payload, offset):
                        return payload[offset:]
            # If no match found, return original (might not be BIP wrapped DNS)
            return payload
        
        return payload
    
    @classmethod
    def _looks_like_dns_at(cls, payload: bytes, offset: int) -> bool:
        """Check if DNS message starts at given offset."""
        if offset + 12 > len(payload):
            return False
        try:
            flags = (payload[offset + 2] << 8) | payload[offset + 3]
            opcode = (flags >> 11) & 0xF
            qdcount = (payload[offset + 4] << 8) | payload[offset + 5]
            return opcode <= 2 and 0 < qdcount <= 10
        except:
            return False
    
    @classmethod
    def _looks_like_tls_at(cls, payload: bytes, offset: int) -> bool:
        """Check if TLS record starts at given offset."""
        if offset + 5 > len(payload):
            return False
        content_type = payload[offset]
        return content_type in [0x14, 0x15, 0x16, 0x17]
    
    @classmethod
    def _find_dns_start(cls, payload: bytes) -> int:
        """Find where DNS message starts in payload (handles BIP/GPRS headers). Returns offset or -1 if not found."""
        if len(payload) < 12:
            return -1
        
        # Try different offsets where DNS might start
        # BIP/GPRS headers are usually 10-14 bytes
        possible_offsets = [0, 10, 12, 14, 16]
        
        for offset in possible_offsets:
            if offset + 12 > len(payload):
                continue
            
            try:
                data = payload[offset:]
                
                # DNS messages start with transaction ID (2 bytes) + flags (2 bytes)
                flags = (data[2] << 8) | data[3]
                
                # Check QR bit, opcode
                opcode = (flags >> 11) & 0xF
                if opcode > 2:  # Valid opcodes: 0 (QUERY), 1 (IQUERY), 2 (STATUS)
                    continue
                
                # Check question/answer counts
                qdcount = (data[4] << 8) | data[5]
                ancount = (data[6] << 8) | data[7]
                
                # Reasonable limits
                if qdcount > 10 or ancount > 50:
                    continue
                
                # Look for DNS label encoding pattern after 12-byte header
                if len(data) > 12:
                    pos = 12
                    found_valid_label = False
                    
                    # Try to parse first label
                    for _ in range(10):  # Max 10 labels
                        if pos >= len(data):
                            break
                        label_len = data[pos]
                        
                        if label_len == 0:  # End of name
                            found_valid_label = True
                            break
                        
                        if label_len > 63:  # Check for compression pointer
                            if (label_len & 0xC0) == 0xC0:
                                found_valid_label = True
                                break
                            else:
                                break  # Invalid
                        
                        # Move past label
                        pos += 1 + label_len
                        
                        # Check if label content looks reasonable (letters, numbers, hyphens)
                        label_data = data[pos - label_len:pos]
                        if all(c >= 0x20 and c < 0x7F for c in label_data):  # Printable ASCII
                            found_valid_label = True
                    
                    if found_valid_label and (qdcount > 0 or ancount > 0):
                        return offset
            
            except:
                continue
        
        return -1
    
    @classmethod
    def _safe_decode(cls, data: bytes) -> Optional[str]:
        """Safely decode bytes to string"""
        try:
            return data.decode('utf-8', errors='ignore')
        except:
            return None
    
    @classmethod
    def _try_parse_json(cls, payload: bytes) -> Optional[Dict[str, Any]]:
        """Try to parse payload as JSON"""
        try:
            # Look for JSON-like patterns
            payload_str = payload.decode('utf-8', errors='ignore').strip()
            if payload_str.startswith('{') and payload_str.endswith('}'):
                return json.loads(payload_str)
        except:
            pass
        return None
    
    @classmethod
    def _extract_http_content_type(cls, http_text: str) -> Optional[str]:
        """Extract Content-Type from HTTP headers"""
        try:
            match = re.search(r'Content-Type:\s*([^\r\n]+)', http_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except:
            pass
        return None
    
    @classmethod
    def _detect_asn1_ber(cls, payload: bytes) -> Optional[List[str]]:
        """Detect ASN.1/BER structures and parse top-level tags"""
        try:
            if len(payload) < 2:
                return None
            
            structures = []
            pos = 0
            
            while pos < len(payload) - 1:
                tag = payload[pos]
                
                # Check for common ASN.1 tags
                if tag in [0x30, 0x31]:  # SEQUENCE, SET
                    length, length_bytes = cls._parse_ber_length(payload[pos+1:])
                    if length is not None:
                        structures.append(f"SEQUENCE (length {length})")
                        pos += 1 + length_bytes + min(length, len(payload) - pos - 1 - length_bytes)
                    else:
                        break
                elif tag & 0x80:  # Context-specific or private tags
                    tag_class = (tag & 0xC0) >> 6
                    tag_num = tag & 0x3F
                    length, length_bytes = cls._parse_ber_length(payload[pos+1:])
                    if length is not None:
                        if tag_class == 2:  # Context-specific
                            structures.append(f"Context-specific [{tag_num}] (length {length})")
                        else:
                            structures.append(f"Private tag 0x{tag:02X} (length {length})")
                        pos += 1 + length_bytes + min(length, len(payload) - pos - 1 - length_bytes)
                    else:
                        break
                else:
                    # Skip unknown bytes
                    pos += 1
            
            return structures if structures else None
        except:
            return None
    
    @classmethod
    def _parse_ber_length(cls, data: bytes) -> Tuple[Optional[int], int]:
        """Parse BER length encoding"""
        if not data:
            return None, 0
        
        if data[0] & 0x80 == 0:
            # Short form
            return data[0], 1
        else:
            # Long form
            length_bytes = data[0] & 0x7F
            if length_bytes == 0 or length_bytes > len(data) - 1:
                return None, 0
            
            length = 0
            for i in range(1, length_bytes + 1):
                length = (length << 8) | data[i]
            
            return length, length_bytes + 1