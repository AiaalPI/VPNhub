import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('apply_public_addresses',
    Path(__file__).resolve().parents[1] / 'scripts/apply_public_addresses.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_apply_preserves_credentials_backs_up_once_and_can_disable(tmp_path):
    config, env, backups = tmp_path/'map.json', tmp_path/'bot.env', tmp_path/'backups'
    original = 'TG_TOKEN=dummy\n# keep this\nXUI_PUBLIC_ADDRESSES={}\nOTHER=dummy\n'
    env.write_text(original)
    config.write_text('{"1":"89.125.136.14"}')
    assert module.apply(config, env, backups)
    assert next(backups.iterdir()).read_text() == original
    assert next(backups.iterdir()).stat().st_mode & 0o777 == 0o600
    assert env.stat().st_mode & 0o777 == 0o600
    assert 'TG_TOKEN=dummy\n# keep this\nOTHER=dummy\n' in env.read_text()
    assert json.loads(env.read_text().split('XUI_PUBLIC_ADDRESSES=')[1]) == {'1':'89.125.136.14'}
    assert not module.apply(config, env, backups)
    assert len(list(backups.iterdir())) == 1
    config.write_text('{}')
    assert module.apply(config, env, backups)
    assert env.read_text().endswith('XUI_PUBLIC_ADDRESSES={}\n')


def test_invalid_map_does_not_change_env_or_create_backup(tmp_path):
    config, env, backups = tmp_path/'map.json', tmp_path/'bot.env', tmp_path/'backups'
    config.write_text('{"1":"https://bad.example"}')
    env.write_text('OTHER=unchanged\n')
    with pytest.raises(ValueError):
        module.apply(config, env, backups)
    assert env.read_text() == 'OTHER=unchanged\n'
    assert not backups.exists()
