from xti_viewer.protocol_analyzer import DnsAnalyzer

payload = bytes.fromhex('0203010000010000000000000c65696d2d64656d6f2d6c6162026575037461630b7468616c6573636c6f756404696f00001c0001')

print("Manual domain parse:")
pos = 12
labels = []
while pos < len(payload):
    length = payload[pos]
    print(f'At {pos}: length={length} (0x{length:02x})')
    if length == 0:
        break
    pos += 1
    if pos + length > len(payload):
        break
    label = payload[pos:pos+length].decode('utf-8', errors='ignore')
    print(f'  Label: {label}')
    labels.append(label)
    pos += length

print(f'Domain: {".".join(labels)}')
print(f'Ended at pos: {pos}')

print("\nCalling _parse_domain_name:")
try:
    name, new_pos = DnsAnalyzer._parse_domain_name(payload, 12)
    print(f'Result: {name}')
    print(f'New pos: {new_pos}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

print("\nCalling parse_dns_message:")
dns = DnsAnalyzer.parse_dns_message(payload, True)
print(f'DNS Info: {dns}')
if dns:
    print(f'Questions: {dns.questions}')
