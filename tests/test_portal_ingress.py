import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('portal_ingress', Path(__file__).parents[1] / 'scripts/portal_ingress.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_switch_preserves_clients_keys_and_ports_and_restores_only_listener(tmp_path):
    path = tmp_path / 'panel.db'
    snapshot = tmp_path / 'listener.json'
    stream = {'network': 'tcp', 'security': 'reality', 'tcpSettings': {'header': {'type': 'none'}},
              'realitySettings': {'privateKey': 'test-key', 'shortIds': ['abc']}}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE inbounds (id INTEGER, listen TEXT, port INTEGER, stream_settings TEXT, clients TEXT)')
        db.execute('INSERT INTO inbounds VALUES (1, ?, 443, ?, ?)', ('', json.dumps(stream), 'original'))
        db.execute('INSERT INTO inbounds VALUES (2, ?, 2087, ?, ?)', ('', '{}', 'xhttp'))
    module.switch(path, snapshot)
    module.switch(path, snapshot)  # Idempotence must not overwrite the original snapshot.
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT * FROM inbounds WHERE id=1').fetchone()
        assert row[1:3] == ('127.0.0.1', 443)
        changed = json.loads(row[3])
        assert changed['realitySettings'] == stream['realitySettings']
        assert changed['tcpSettings']['acceptProxyProtocol']
        assert row[4] == 'original'
        assert db.execute('SELECT listen,port FROM inbounds WHERE id=2').fetchone() == ('', 2087)
        db.execute("UPDATE inbounds SET clients='new client' WHERE id=1")
    module.switch(path, snapshot, restore=True)
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT * FROM inbounds WHERE id=1').fetchone()
        assert row[1:3] == ('', 443)
        assert json.loads(row[3]) == stream
        assert row[4] == 'new client'


def test_switch_rejects_unexpected_inbound(tmp_path):
    path = tmp_path / 'panel.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE inbounds (id INTEGER, listen TEXT, port INTEGER, stream_settings TEXT)')
        db.execute("INSERT INTO inbounds VALUES (1, '', 8443, '{}')")
    with pytest.raises(RuntimeError, match='port 443'):
        module.switch(path, tmp_path / 'snapshot')
