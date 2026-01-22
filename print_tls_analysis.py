import re
import sys
from pathlib import Path


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="latin-1", errors="ignore")


def extract_code_block(md: str, title_keyword: str) -> str:
    # Find section starting with ## title_keyword
    m = re.search(rf"^##\s+{re.escape(title_keyword)}.*$", md, re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    m2 = re.search(r"^##\s+", md[start:], re.MULTILINE)
    end = start + (m2.start() if m2 else len(md) - start)
    sec = md[start:end]
    cb = re.search(r"```text\n(.*?)\n```", sec, re.DOTALL)
    return cb.group(1) if cb else ""


def extract_tls_flow_lines(md: str) -> list[str]:
    m = re.search(r"^##\s+TLS Flow.*$", md, re.MULTILINE)
    if not m:
        return []
    start = m.end()
    m2 = re.search(r"^##\s+", md[start:], re.MULTILINE)
    end = start + (m2.start() if m2 else len(md) - start)
    sec = md[start:end]
    cb = re.search(r"```text\n(.*?)\n```", sec, re.DOTALL)
    if not cb:
        return []
    return [ln.strip() for ln in cb.group(1).splitlines() if ln.strip()]


def extract_summary(md: str) -> dict:
    lines = extract_tls_flow_lines(md)
    sni = version = ciphers = ""
    for ln in lines:
        if ln.startswith("[TLS] Summary"):
            sni_m = re.search(r"SNI:\s*([^|]+)", ln)
            ver_m = re.search(r"Version:\s*([^|]+)", ln)
            ciph_m = re.search(r"Ciphers:\s*(.*)$", ln)
            if sni_m:
                sni = sni_m.group(1).strip()
            if ver_m:
                version = ver_m.group(1).strip()
            if ciph_m:
                ciphers = ciph_m.group(1).strip()
            break
    # Chosen cipher and cert count from Full TLS Analysis section
    chosen_m = re.search(r"Chosen Cipher:\s*(.*)", md)
    certs_m = re.search(r"Certificates:\s*(\d+)", md)
    return {
        "sni": sni,
        "version": version,
        "ciphers_offered": ciphers,
        "chosen_cipher": chosen_m.group(1).strip() if chosen_m else "",
        "cert_count": certs_m.group(1).strip() if certs_m else "",
    }


def extract_handshake_seq(md: str) -> list[str]:
    m = re.search(r"\*\*Full TLS Handshake Reconstruction\*\*\s*\n-\s*(.*)", md)
    if not m:
        return []
    seq = m.group(1)
    return [p.strip() for p in seq.split("→")]


def main() -> int:
    # Determine report path
    if len(sys.argv) > 1:
        md_path = Path(sys.argv[1])
    else:
        cwd = Path.cwd()
        candidates = [cwd / "tac_session_report.md", cwd / "tac_session_raw.md"]
        md_path = next((p for p in candidates if p.exists()), candidates[0])

    if not md_path.exists():
        print(f"[ERROR] Markdown report not found: {md_path}")
        return 2

    md = load_text(md_path)

    print(f"[INFO] Loaded report: {md_path}")

    # RAW APDUs
    raw_apdus = extract_code_block(md, "RAW APDUs")
    print("\n=== RAW APDUs (OPEN → CLOSE) ===")
    print(raw_apdus if raw_apdus else "[No RAW APDUs block found]")

    # TLS Flow
    tls_flow = extract_tls_flow_lines(md)
    print("\n=== TLS Flow (OPEN → TLS → CLOSE) ===")
    for ln in tls_flow:
        print(ln)
    if not tls_flow:
        print("[No TLS Flow block found]")

    # Summary
    summary = extract_summary(md)
    print("\n=== Normalized TLS Analysis — Summary ===")
    print(f"SNI: {summary['sni']}")
    print(f"Version: {summary['version']}")
    print(f"Ciphers (offered): {summary['ciphers_offered']}")
    print(f"Chosen Cipher: {summary['chosen_cipher']}")
    print(f"Certificates: {summary['cert_count']}")

    # Handshake Reconstruction
    hs = extract_handshake_seq(md)
    print("\n=== Full TLS Handshake Reconstruction ===")
    print(" → ".join(hs) if hs else "[No handshake sequence found]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
