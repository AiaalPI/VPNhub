#!/usr/bin/env python3
"""Guarded XUI listener switch; never change client IDs, ports or REALITY keys."""
import argparse
import json
import sqlite3
from pathlib import Path


def switch(db_path, snapshot_path, restore=False):
    db = sqlite3.connect(db_path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT listen, port, stream_settings FROM inbounds WHERE id=1').fetchone()
        if not row or row[1] != 443:
            raise RuntimeError('Expected inbound 1 on port 443')
        stream = json.loads(row[2])
        if stream.get('security') != 'reality' or stream.get('network') not in ('tcp', 'raw'):
            raise RuntimeError('Expected RAW/TCP REALITY inbound')
        if restore:
            original = json.loads(Path(snapshot_path).read_text())
            listen, serialized = original['listen'], original['stream_settings']
        else:
            transport = 'tcpSettings' if stream['network'] == 'tcp' else 'rawSettings'
            if row[0] == '127.0.0.1' and stream.get(transport, {}).get('acceptProxyProtocol'):
                db.rollback()
                return
            if row[0] not in ('', '0.0.0.0', '::'):
                raise RuntimeError('Unexpected existing listener; refusing to overwrite')
            snapshot = Path(snapshot_path)
            # Must be new: preserve the original listener for this attempt.
            with snapshot.open('x') as out:
                json.dump({'listen': row[0], 'stream_settings': row[2]}, out)
            snapshot.chmod(0o600)
            stream.setdefault(transport, {})['acceptProxyProtocol'] = True
            listen, serialized = '127.0.0.1', json.dumps(stream)
        db.execute('UPDATE inbounds SET listen=?, stream_settings=? WHERE id=1', (listen, serialized))
        db.commit()
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot')
    parser.add_argument('--db', default='/etc/x-ui/x-ui.db')
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    switch(args.db, args.snapshot, args.restore)
