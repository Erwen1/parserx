# TAC TLS Flow Summary (OPEN → TLS → CLOSE)

Source XTI: `HL7812_fallback_NOK.xti`

## Group[2] — TAC TCP:443 (IPs: ['13.38.212.83'])
- Session: `Session[0]` window: `11/06/2025 16:55:33 → 16:55:42`

### TLS Flow
```text
[TLS] ME->SIM | 11/06/2025 16:55:34:811.000000 | TLS Handshake (other)
[TLS] ME->SIM | 11/06/2025 16:55:35:534.000000 | TLS Handshake (other)
[TLS] ME->SIM | 11/06/2025 16:55:37:180.000000 | TLS Change Cipher Spec
[TLS] ME->SIM | 11/06/2025 16:55:38:646.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:55:40:942.000000 | TLS Application Data
[TLS] ME->SIM | 11/06/2025 16:55:41:173.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:55:41:367.000000 | TLS Alert
```

### Notes
- The initial SEND DATA at `11/06/2025 16:55:33:739` (item [67]) contains `16 03 03` (TLS Handshake / TLS1.2) and is a ClientHello, but it is not listed above; see "Verification".
- The two "Handshake (other)" entries align with server handshake records (ServerHello/certificates) observed across RECEIVE DATA APDUs.
- Change Cipher Spec followed by Application Data in both directions indicates keys established; the final Alert likely signals termination/failure.

---

## Group[5] — TAC TCP:443 (IPs: ['52.47.40.152'])
- Session: `Session[0]` window: `11/06/2025 16:58:19 → 16:58:29`

### TLS Flow
```text
[TLS] ME->SIM | 11/06/2025 16:58:20:525.000000 | TLS Handshake (other)
[TLS] ME->SIM | 11/06/2025 16:58:21:207.000000 | TLS Handshake (other)
[TLS] ME->SIM | 11/06/2025 16:58:22:824.000000 | TLS Change Cipher Spec
[TLS] SIM->ME | 11/06/2025 16:58:23:826.000000 | TLS Application Data
[TLS] ME->SIM | 11/06/2025 16:58:25:196.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:58:25:969.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:58:26:659.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:58:27:174.000000 | TLS Application Data
[TLS] ME->SIM | 11/06/2025 16:58:27:822.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:58:28:710.000000 | TLS Application Data
[TLS] ME->SIM | 11/06/2025 16:58:28:921.000000 | TLS Application Data
[TLS] SIM->ME | 11/06/2025 16:58:29:118.000000 | TLS Alert
```

### Notes
- As with Group[2], the ClientHello appears earlier in SEND DATA but is not listed in this flow summary.
- Sequence shows handshake records, CCS, then sustained Application Data and a terminal Alert.

---

## Verification
- ClientHello presence: Confirmed in raw APDUs — e.g. Group[2] item [67] `... 16 03 03 00 7B ...` (TLS1.2 Handshake Record; Handshake type at +5 = 0x01 ClientHello). This should be reflected in the flow as "TLS Handshake (ClientHello)" at `16:55:33:739`.
- Server handshake: The two "Handshake (other)" entries correspond to ServerHello/Certificate records carried in RECEIVE DATA around `16:55:34.811` and `16:55:35.534`.
- CCS and App Data: Ordering is consistent — CCS from ME->SIM, then App Data flows both directions.
- Alert: Final SIM->ME Alert indicates shutdown/error, consistent with a failed or closed session (file name suggests fallback NOK).

### Conclusion
- The overall TLS sequence is correct. The current flow output omits the explicit ClientHello line; adding ClientHello detection for SEND DATA would make the flow complete. If you want, I can patch the script/UI analyzer to log ClientHello and decode Alert descriptions.
