#!/usr/bin/env python3
"""Apply the reviewed export map before Compose reads env_file; no panel writes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
from bot.misc.vpn_public_addresses import parse_public_addresses


def apply(config: Path, environment: Path, backups: Path) -> bool:
    mapping = parse_public_addresses(config.read_text())
    target = 'XUI_PUBLIC_ADDRESSES=' + json.dumps(
        {str(k): v for k, v in mapping.items()}, sort_keys=True)
    original = environment.read_text()
    pattern = re.compile(r'^\s*(?:export\s+)?XUI_PUBLIC_ADDRESSES\s*=')
    lines = original.splitlines()
    if [line for line in lines if pattern.match(line)] == [target]:
        return False
    # Preserve all unrelated credentials/settings, and keep a private old env.
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = backups / f'public-addresses-{stamp}-{os.getpid()}.env'
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as out:
        out.write(original)
    with tempfile.NamedTemporaryFile(mode='w', dir=environment.parent, delete=False) as out:
        temporary = Path(out.name)
        out.write('\n'.join([line for line in lines if not pattern.match(line)] + [target]) + '\n')
    try:
        temporary.chmod(0o600)
        shutil.chown(temporary, environment.stat().st_uid, environment.stat().st_gid)
        os.replace(temporary, environment)
    finally:
        temporary.unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--env', type=Path, required=True)
    parser.add_argument('--backups', type=Path, required=True)
    args = parser.parse_args()
    changed = apply(args.config, args.env, args.backups)
    print('Public export map applied' if changed else 'Public export map already matches')
