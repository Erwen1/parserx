import json
from pathlib import Path
from tls_flow_from_report import load_tls_report, to_dict


def main():
    repo = Path(__file__).parent
    report_path = repo / "tac_session_report.md"
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        return
    data = load_tls_report(str(report_path))
    obj = to_dict(data)

    print("== TLS Summary ==")
    s = obj["summary"]
    print(f"SNI: {s['sni']}")
    print(f"Version: {s['version']}")
    print(f"Chosen Cipher: {s['chosen_cipher']}")
    print(f"Certificates: {s['certificates']}")
    print("Offered Ciphers:")
    for c in s["offered_ciphers"]:
        print(f" - {c}")

    print("\n== TLS Flow Events ==")
    for e in obj["flow_events"]:
        print(f"{e['timestamp']} {e['direction']}: {e['label']} | {e['details']}")

    print("\n== Handshake Sequence ==")
    print(" -> ".join(obj["handshake"]["sequence"]))

    print("\n== RAW APDUs (first 5) ==")
    for line in obj["raw_apdus"][:5]:
        print(line)


if __name__ == "__main__":
    main()
