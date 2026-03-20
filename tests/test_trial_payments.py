import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def base_env():
    """Fixture with test environment variables."""
    return {
        "ADMIN_TG_ID": "123",
        "TG_TOKEN": "test_token",
        "NAME": "testbot",
        "CHECK_FOLLOW": "0",
        "LANGUAGES": "en,ru",
        "PRICE_SWITCH_LOCATION": "10",
        "MONTH_COST": "100,200,300,400",
        "TRIAL_PERIOD": "604800",
        "FREE_SWITCH_LOCATION": "1",
        "UTC_TIME": "0",
        "REFERRAL_DAY": "1",
        "REFERRAL_PERCENT": "10",
        "MINIMUM_WITHDRAWAL_AMOUNT": "100",
        "FREE_SERVER": "0",
        "LIMIT_IP": "0",
        "LIMIT_GB": "0",
        "IMPORT_DB": "0",
        "SHOW_DONATE": "1",
        "IS_WORK_EDIT_KEY": "1",
        "POSTGRES_DB": "testdb",
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpass",
        "PGADMIN_DEFAULT_EMAIL": "admin@test.com",
        "PGADMIN_DEFAULT_PASSWORD": "adminpass",
    }


@pytest.fixture
def cleanup_bot_modules():
    """Clean up bot module imports before and after test."""
    for m in list(sys.modules.keys()):
        if m.startswith('bot'):
            del sys.modules[m]
    yield
    for m in list(sys.modules.keys()):
        if m.startswith('bot'):
            del sys.modules[m]


def test_config_loads_with_trial_fields(base_env, cleanup_bot_modules):
    """Test that CONFIG loads with trial-related env vars."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.misc.util import CONFIG
    
    assert CONFIG.trial_period == 604800
    assert hasattr(CONFIG, 'tg_token')
    assert CONFIG.tg_token == 'test_token'
    assert CONFIG.trial_period == int(base_env['TRIAL_PERIOD'])


def test_clean_subscription_token_roundtrip(base_env, cleanup_bot_modules):
    """Signed clean-subscription tokens should round-trip user/key ids."""
    os.environ.clear()
    env = dict(base_env)
    env["PUBLIC_SUBSCRIPTION_BASE"] = "https://vpn.example.com"
    os.environ.update(env)

    from bot.services.subscription_service import (
        build_clean_subscription_token,
        build_clean_subscription_url,
        parse_clean_subscription_token,
    )

    token = build_clean_subscription_token(user_id=76149983, key_id=60, issued_at=int(time.time()))
    user_id, key_id = parse_clean_subscription_token(token)
    url = build_clean_subscription_url(user_id=76149983, key_id=60)

    assert (user_id, key_id) == (76149983, 60)
    assert url is not None
    assert "/subscriptions/" in url


@pytest.mark.asyncio
async def test_mailing_main_menu_button_uses_canonical_callback(
    base_env,
    cleanup_bot_modules,
):
    """Mailing "main menu" button should use the live inline callback."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.keyboards.inline.user_inline import mailing_button_message

    markup = await mailing_button_message('en', 'general_menu_btn')

    assert markup.inline_keyboard[0][0].callback_data == 'back_general_menu_btn'


@pytest.mark.asyncio
async def test_trial_eligibility_happy_path(base_env, cleanup_bot_modules):
    """Test trial eligibility logic (user not in trial, not banned)."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.services.trial_service import is_trial_eligible
    from bot.database.models.main import Persons
    
    person = Persons()
    person.trial_period = False
    person.banned = False
    person.keys = []
    
    with patch('bot.services.trial_service._get_person') as mock_get_person:
        mock_get_person.return_value = person
        session = AsyncMock()
        
        result = await is_trial_eligible(123, session)
        assert result is True


@pytest.mark.asyncio
async def test_new_user_trial_prioritizes_marzban(base_env, cleanup_bot_modules):
    """New-user trial should prefer Marzban when it is available."""
    os.environ.clear()
    os.environ.update(base_env)

    fake_prometheus = SimpleNamespace(
        CONTENT_TYPE_LATEST="text/plain",
        Counter=lambda *args, **kwargs: SimpleNamespace(labels=lambda *a, **k: SimpleNamespace(inc=lambda *x, **y: None)),
        Histogram=lambda *args, **kwargs: SimpleNamespace(labels=lambda *a, **k: SimpleNamespace(observe=lambda *x, **y: None)),
        generate_latest=lambda *args, **kwargs: b"",
    )

    with patch.dict(sys.modules, {"prometheus_client": fake_prometheus}):
        from bot.handlers.user.main import get_first_available_trial_target
        from bot.misc.util import CONFIG

        person = SimpleNamespace(group="default")
        marzban_type = CONFIG.TypeVpn.MARZBAN.value
        vless_type = CONFIG.TypeVpn.VLESS.value

        with patch('bot.handlers.user.main.get_type_vpn', new=AsyncMock(return_value=[vless_type, marzban_type])):
            with patch('bot.handlers.user.main.get_free_servers', new=AsyncMock(side_effect=[
                [SimpleNamespace(id=11)],
                [SimpleNamespace(id=22)],
            ])):
                target = await get_first_available_trial_target(AsyncMock(), person)

    assert target == (marzban_type, 11)


@pytest.mark.asyncio
async def test_marzban_resolves_first_vless_inbound(base_env, cleanup_bot_modules):
    """Marzban provisioning should use a live VLESS inbound from the panel."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.misc.VPN.Marzban import Marzban

    server = MagicMock()
    server.free_server = False
    server.panel = "https://panel.example.com:8001"
    server.login = "admin"
    server.password = "secret"

    marzban = Marzban(server)
    marzban.client = AsyncMock()
    inbound_response = MagicMock()
    inbound_response.json.return_value = {
        "vless": [
            {"tag": "CUSTOM_VLESS"},
        ]
    }
    inbound_response.raise_for_status.return_value = None
    marzban.client.get.return_value = inbound_response

    tag = await marzban._resolve_inbound_tag()

    assert tag == "CUSTOM_VLESS"


@pytest.mark.asyncio
async def test_marzban_normalizes_reality_export_link(base_env, cleanup_bot_modules):
    """Marzban REALITY export should strip :443 from host/sni values."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.misc.VPN.Marzban import Marzban

    raw_link = (
        "vless://uuid@example.com:443?security=reality&type=tcp&"
        "host=github.com%3A443&sni=github.com%3A443&fp=chrome"
    )

    normalized = Marzban.normalize_export_link(raw_link)

    assert "host=github.com&" in normalized
    assert "sni=github.com&" in normalized or normalized.endswith("sni=github.com")
    assert "%3A443" not in normalized


@pytest.mark.asyncio
async def test_marzban_brands_finland_export_labels(base_env, cleanup_bot_modules):
    """Clean Marzban exports should use branded Finland labels."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.misc.VPN.Marzban import Marzban

    raw_link_1 = (
        "vless://uuid@65.108.91.192:443?security=reality&host=github.com%3A443&"
        "sni=github.com%3A443#Finland-Node-1%20%2876149983_60_mz%29%20%5BVLESS-tcp%5D"
    )
    raw_link_2 = (
        "vless://uuid@78.40.209.162:443?security=reality&host=github.com%3A443&"
        "sni=github.com%3A443#QWINS-Node-1%20%2876149983_60_mz%29%20%5BVLESS-tcp%5D"
    )
    raw_link_3 = (
        "vless://uuid@138.124.64.192:443?security=reality&host=&"
        "sni=github.com#Poland-Node-1%20%2876149983_87_mz%29%20%5BVLESS-tcp%5D"
    )

    normalized_1 = Marzban.normalize_export_link(raw_link_1)
    normalized_2 = Marzban.normalize_export_link(raw_link_2)
    normalized_3 = Marzban.normalize_export_link(raw_link_3)

    assert "#%F0%9F%87%AB%F0%9F%87%AE KYN %7C Finland - 1" in normalized_1
    assert "#%F0%9F%87%AB%F0%9F%87%AE KYN %7C Finland - 2" in normalized_2
    assert "#%F0%9F%87%B5%F0%9F%87%B1 KYN %7C Poland - 1" in normalized_3
    assert "76149983_60_mz" in normalized_1
    assert "76149983_60_mz" in normalized_2
    assert "76149983_87_mz" in normalized_3


@pytest.mark.asyncio
async def test_marzban_skips_degraded_tokyo_link(base_env, cleanup_bot_modules):
    """Marzban should avoid the known degraded Tokyo export when alternatives exist."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.misc.VPN.Marzban import Marzban

    server = MagicMock()
    server.free_server = False
    server.panel = "https://panel.example.com:8001"
    server.login = "admin"
    server.password = "secret"

    marzban = Marzban(server)
    marzban.client = AsyncMock()
    user_response = {
        "links": [
            "vless://uuid@45.77.176.143:443?security=reality&host=github.com%3A443&sni=github.com%3A443#Tokyo-Node-2",
            "vless://uuid@65.108.91.192:443?security=reality&host=github.com%3A443&sni=github.com%3A443#Finland-Node-1",
        ]
    }
    marzban.get_client = AsyncMock(return_value=user_response)

    link = await marzban.get_primary_link("76149983.60.mz")

    assert "65.108.91.192" in link
    assert "45.77.176.143" not in link
    assert "sni=github.com" in link


@pytest.mark.asyncio
async def test_payment_picker_prefers_marzban_for_user_without_legacy_access(
    base_env,
    cleanup_bot_modules,
):
    """New users without active legacy keys should default to Marzban."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.handlers.user.edit_or_get_key import _pick_primary_payment_server_for_user
    from bot.misc.util import CONFIG

    legacy_server = SimpleNamespace(type_vpn=CONFIG.TypeVpn.VLESS.value)
    marzban_server = SimpleNamespace(type_vpn=CONFIG.TypeVpn.MARZBAN.value)

    with patch(
        'bot.handlers.user.edit_or_get_key.get_key_user',
        new=AsyncMock(return_value=[]),
    ):
        selected = await _pick_primary_payment_server_for_user(
            AsyncMock(),
            123,
            [legacy_server, marzban_server],
        )

    assert selected is marzban_server


@pytest.mark.asyncio
async def test_connect_vpn_menu_groups_marzban_keys_into_single_subscription(
    base_env,
    cleanup_bot_modules,
):
    """Multi-server Marzban access should render as one subscription row."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.keyboards.inline.user_inline import connect_vpn_menu
    from bot.misc.util import CONFIG

    def make_key(key_id: int, subscription: int, type_vpn: int, location_name: str):
        return SimpleNamespace(
            id=key_id,
            subscription=subscription,
            server=key_id,
            server_table=SimpleNamespace(
                type_vpn=type_vpn,
                vds_table=SimpleNamespace(
                    location_table=SimpleNamespace(name=location_name)
                ),
            ),
        )

    now = int(time.time()) + 5 * 24 * 60 * 60
    keys = [
        make_key(1, now, CONFIG.TypeVpn.MARZBAN.value, '🇫🇮Финляндия'),
        make_key(2, now + 1000, CONFIG.TypeVpn.MARZBAN.value, '🇵🇱Польша'),
        make_key(3, now, CONFIG.TypeVpn.VLESS.value, '🇳🇱Нидерланды'),
    ]

    markup = await connect_vpn_menu('ru', keys)
    texts = [
        button.text
        for row in markup.inline_keyboard
        for button in row
    ]

    europe_rows = [text for text in texts if '🇪🇺 Европа • 3 сервера' in text]
    netherlands_rows = [text for text in texts if 'Нидер' in text]

    assert len(europe_rows) == 1
    assert len(netherlands_rows) == 1


@pytest.mark.asyncio
async def test_connect_vpn_menu_keeps_group_header_visible_in_detail_mode(
    base_env,
    cleanup_bot_modules,
):
    """Expanded multi-server subscription should still show its own header row."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.keyboards.inline.user_inline import connect_vpn_menu
    from bot.misc.util import CONFIG

    key = SimpleNamespace(
        id=10,
        subscription=int(time.time()) + 5 * 24 * 60 * 60,
        server=10,
        server_table=SimpleNamespace(
            type_vpn=CONFIG.TypeVpn.MARZBAN.value,
            vds_table=SimpleNamespace(
                location_table=SimpleNamespace(name='🇫🇮Финляндия')
            ),
        ),
    )

    markup = await connect_vpn_menu('ru', [key], id_detail=10)
    texts = [
        button.text
        for row in markup.inline_keyboard
        for button in row
    ]

    assert any('🇪🇺 Европа • 3 сервера' in text for text in texts)
    assert any('Получить' in text for text in texts)

    header_button = next(
        button
        for row in markup.inline_keyboard
        for button in row
        if '🇪🇺 Европа • 3 сервера' in button.text
    )
    assert header_button.callback_data == 'show_key_user:10'


@pytest.mark.asyncio
async def test_choose_type_vpn_uses_classic_and_multi_labels(
    base_env,
    cleanup_bot_modules,
):
    """Protocol picker should show user-facing Classic/Multi labels."""
    os.environ.clear()
    os.environ.update(base_env)

    from bot.keyboards.inline.user_inline import choose_type_vpn
    from bot.misc.util import CONFIG

    markup = await choose_type_vpn(
        [CONFIG.TypeVpn.VLESS.value, CONFIG.TypeVpn.MARZBAN.value],
        'ru',
    )
    texts = [
        button.text
        for row in markup.inline_keyboard
        for button in row
    ]

    assert 'VLESS Classic' in texts
    assert 'VLESS Multi' in texts


@pytest.mark.asyncio
async def test_trial_eligibility_already_in_trial(base_env, cleanup_bot_modules):
    """Test that user already in trial cannot activate again."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.services.trial_service import is_trial_eligible
    from bot.database.models.main import Persons
    
    person = Persons()
    person.trial_period = True
    person.banned = False
    person.keys = []
    
    with patch('bot.services.trial_service._get_person') as mock_get_person:
        mock_get_person.return_value = person
        session = AsyncMock()
        
        result = await is_trial_eligible(123, session)
        assert result is False


@pytest.mark.asyncio
async def test_trial_eligibility_user_banned(base_env, cleanup_bot_modules):
    """Test that banned user cannot activate trial."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.services.trial_service import is_trial_eligible
    from bot.database.models.main import Persons
    
    person = Persons()
    person.trial_period = False
    person.banned = True
    person.keys = []
    
    with patch('bot.services.trial_service._get_person') as mock_get_person:
        mock_get_person.return_value = person
        session = AsyncMock()
        
        result = await is_trial_eligible(123, session)
        assert result is False


@pytest.mark.asyncio
async def test_payment_webhook_idempotency(base_env, cleanup_bot_modules):
    """Test that webhook is processed correctly on first call."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.services.cryptomus_payment_service import handle_cryptomus_webhook
    from bot.database.models.main import Persons
    
    webhook_data = {
        'uuid': 'test-uuid-123',
        'order_id': '123_1707123456_3',
        'status': 'paid',
        'amount': '300.00'
    }
    
    session = AsyncMock()
    
    # Mock session.execute: payment doesn't exist yet
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    
    # Mock person
    mock_person = Persons()
    mock_person.keys = []
    mock_person.tgid = 123
    
    with patch('bot.services.cryptomus_payment_service._get_person') as mock_get:
        mock_get.return_value = mock_person
        with patch('bot.services.cryptomus_payment_service.extend_subscription') as mock_ext:
            mock_key = MagicMock()
            mock_key.id = 1
            mock_ext.return_value = mock_key
            with patch('bot.services.cryptomus_payment_service.db_add_payment'):
                with patch('bot.services.cryptomus_payment_service.update_payment_status'):
                    response = await handle_cryptomus_webhook(session, webhook_data)
                    assert response is True


@pytest.mark.asyncio
async def test_payment_webhook_duplicate_confirmed(base_env, cleanup_bot_modules):
    """Test that webhook for already-confirmed payment is idempotent."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.services.cryptomus_payment_service import handle_cryptomus_webhook
    from bot.database.models.main import Payments
    
    webhook_data = {
        'uuid': 'test-uuid-123',
        'order_id': '123_1707123456_3',
        'status': 'paid',
        'amount': '300.00'
    }
    
    session = AsyncMock()
    
    # Simulate: payment already exists and is confirmed
    existing_payment = Payments()
    existing_payment.id_payment = '123_1707123456_3'
    existing_payment.status = 'confirmed'
    
    # Mock session.execute to return existing confirmed payment
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_payment
    session.execute = AsyncMock(return_value=result)
    
    response = await handle_cryptomus_webhook(session, webhook_data)
    assert response is True


@pytest.mark.asyncio
async def test_extend_subscription_creates_new_key(base_env, cleanup_bot_modules):
    """Test that extend_subscription creates new key if none exists."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.services.subscription_mutation_service import extend_subscription
    from bot.database.models.main import Persons
    
    session = AsyncMock()
    
    # Mock person with no keys
    person = Persons()
    person.keys = []
    person.tgid = 123
    
    # Mock _get_person to return person
    mock_key = MagicMock()
    mock_key.id = 42
    
    with patch('bot.services.subscription_mutation_service._get_person') as mock_get:
        mock_get.return_value = person
        with patch('bot.services.subscription_mutation_service.add_key') as mock_add:
            mock_add.return_value = mock_key
            with patch('bot.services.subscription_mutation_service.get_free_server_id'):
                result = await extend_subscription(
                    123,
                    30,
                    'test_reason',
                    session
                )
                assert result == mock_key
