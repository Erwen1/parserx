📋 Session Overview
TAC
Protocol
TCP
Port
443
Duration
9.0s
Total Messages
11
IP: 13.38.212.83
SNI: eim-demo-lab.eu.tac.thalescloud.io
🔐 Security Configuration
Version: TLS 1.2
Chosen Cipher Suite:
TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
✓ Perfect Forward Secrecy✓ AEAD Mode128-bit Encryption
Certificate Chain: 2 certificates
📊 Message Statistics
Handshake
2
Application Data
0
Alerts
1
🔄 Handshake Flow
ClientHello→ServerHello→Certificate→ServerKeyExchange→ServerHelloDone→ClientKeyExchange→ChangeCipherSpec→Encrypted Finished→ChangeCipherSpec→Encrypted Finished→ApplicationData→Alert (close_notify)
▼ Cipher Suite Negotiation
chosen: TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
key_exchange: ECDHE
authentication: ECDSA
aead: True
ClientHello
ServerHello
Certificate
ServerKeyExchange
ServerHelloDone
ClientKeyExchange
ChangeCipherSpec
Encrypted Finished
ChangeCipherSpec
Encrypted Finished
ApplicationData
Alert (close_notify)
Security Evaluation
OK: Modern AEAD/ECDHE detected
SNI: eim-demo-lab.eu.tac.thalescloud.io
Version: TLS 1.2
Chosen Cipher: TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
Certificates: 2
OPEN CHANNEL → ClientHello → ServerHello → Certificate → ServerKeyExchange → ServerHelloDone → ClientKeyExchange → ChangeCipherSpec → Encrypted Finished → ChangeCipherSpec → Encrypted Finished → ApplicationData → Alert (close_notify) → CLOSE CHANNEL
ClientHello → ServerHello → Certificate → ServerKeyExchange → ServerHelloDone → ClientKeyExchange → ChangeCipherSpec → Encrypted Finished (client) → ChangeCipherSpec → Encrypted Finished (server) → ApplicationData → Alert (close_notify)
Decoded ClientHello
version: TLS 1.2
random: 0b184b87db6c126752fe818a7f1f479bf1fd0b62236f6ca2b8cd77f880d437e8
session_id:
cipher_suites: Unknown_0x00AE, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256, ECDHE_ECDSA_AES_256_CBC, ECDHE_ECDSA_AES_128_CBC
compression_methods: [0]
extensions: SNI, max_fragment_length, supported_groups, ec_point_formats, signature_algorithms
SNI: eim-demo-lab.eu.tac.thalescloud.io
supported_groups: [secp256r1]
signature_algorithms: [ecdsa_sha256]
alpn: []
ec_point_formats: [uncompressed]
renegotiation_info: None
Decoded ServerHello
version: TLS 1.2
random: 5288712002d006ba7caa6023562ebecb4217167cd930acbd444f574e47524401
session_id: 6c70a628b405efbb79766abbeecb307aa32ff2725b2107877ab86fc36b68008b
cipher: TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
compression: 0
extensions: ['max_fragment_length', 'ec_point_formats']
PKI Certificate Chain (decoded)