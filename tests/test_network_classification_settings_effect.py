import os
import sys
import pytest

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_config
from xti_viewer.xti_parser import XTIParser


def _session_signature(session):
    # Stable, config-independent session identity for comparisons
    return (
        session.channel_id,
        session.opened_at,
        session.closed_at,
        session.protocol,
        session.port,
        tuple(sorted(session.ips)),
        tuple(sorted(session.traceitem_indexes)),
    )


def _parse_and_collect(xti_path: str):
    parser = XTIParser()
    parser.parse_file(xti_path)

    sigs = sorted(_session_signature(s) for s in parser.channel_sessions)
    groups = parser.get_channel_groups()
    return sigs, groups


def test_network_classification_lists_do_not_change_sessions_but_change_labels(monkeypatch):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xti_path = os.path.join(repo_root, 'traces.xti')
    if not os.path.exists(xti_path):
        pytest.skip('traces.xti not found')

    # Use a TAC IP that is known to appear in traces.xti
    probe_ip = '13.38.212.83'

    # Config A: treat probe_ip as DP+ (by putting TAC IPs into dp_plus_ips)
    def load_config_a():
        return {
            'classification': {
                'tac_ips': [],
                'dp_plus_ips': [
                    '13.38.212.83',
                    '52.47.40.152',
                    '13.39.169.102',
                ],
                'dns_ips': ['8.8.8.8', '8.8.4.4'],
            }
        }

    # Config B: treat probe_ip as TAC
    def load_config_b():
        return {
            'classification': {
                'tac_ips': [
                    '13.38.212.83',
                    '52.47.40.152',
                    '13.39.169.102',
                ],
                'dp_plus_ips': [],
                'dns_ips': ['8.8.8.8', '8.8.4.4'],
            }
        }

    monkeypatch.setattr(app_config, 'load_config', load_config_a)
    sigs_a, groups_a = _parse_and_collect(xti_path)

    labels_a = {g.get('server') for g in groups_a if probe_ip in (g.get('ips') or [])}
    assert labels_a, 'Expected at least one channel session with the probe IP'
    assert labels_a == {'DP+'}

    monkeypatch.setattr(app_config, 'load_config', load_config_b)
    sigs_b, groups_b = _parse_and_collect(xti_path)

    # Session reconstruction should not change when only classification lists change
    assert sigs_a == sigs_b

    labels_b = {g.get('server') for g in groups_b if probe_ip in (g.get('ips') or [])}
    assert labels_b, 'Expected at least one channel session with the probe IP'
    assert labels_b == {'TAC'}
