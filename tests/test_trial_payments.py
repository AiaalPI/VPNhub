import os
import sys
import time
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


@pytest.mark.asyncio
async def test_trial_eligibility_happy_path(base_env, cleanup_bot_modules):
    """Test trial eligibility logic (user not in trial, not banned)."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.service.trial_service import is_trial_eligible
    from bot.database.models.main import Persons
    
    person = Persons()
    person.trial_period = False
    person.banned = False
    person.keys = []
    
    with patch('bot.service.trial_service._get_person') as mock_get_person:
        mock_get_person.return_value = person
        session = AsyncMock()
        
        result = await is_trial_eligible(123, session)
        assert result is True


@pytest.mark.asyncio
async def test_trial_eligibility_already_in_trial(base_env, cleanup_bot_modules):
    """Test that user already in trial cannot activate again."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.service.trial_service import is_trial_eligible
    from bot.database.models.main import Persons
    
    person = Persons()
    person.trial_period = True
    person.banned = False
    person.keys = []
    
    with patch('bot.service.trial_service._get_person') as mock_get_person:
        mock_get_person.return_value = person
        session = AsyncMock()
        
        result = await is_trial_eligible(123, session)
        assert result is False


@pytest.mark.asyncio
async def test_trial_eligibility_user_banned(base_env, cleanup_bot_modules):
    """Test that banned user cannot activate trial."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.service.trial_service import is_trial_eligible
    from bot.database.models.main import Persons
    
    person = Persons()
    person.trial_period = False
    person.banned = True
    person.keys = []
    
    with patch('bot.service.trial_service._get_person') as mock_get_person:
        mock_get_person.return_value = person
        session = AsyncMock()
        
        result = await is_trial_eligible(123, session)
        assert result is False


@pytest.mark.asyncio
async def test_payment_webhook_idempotency(base_env, cleanup_bot_modules):
    """Test that webhook is processed correctly on first call."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.handlers.payment_webhook import handle_cryptomus_webhook
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
    
    with patch('bot.handlers.payment_webhook._get_person') as mock_get:
        mock_get.return_value = mock_person
        with patch('bot.handlers.payment_webhook.extend_subscription') as mock_ext:
            mock_key = MagicMock()
            mock_key.id = 1
            mock_ext.return_value = mock_key
            with patch('bot.handlers.payment_webhook.db_add_payment'):
                with patch('bot.handlers.payment_webhook.update_payment_status'):
                    response = await handle_cryptomus_webhook(session, webhook_data)
                    assert response is True


@pytest.mark.asyncio
async def test_payment_webhook_duplicate_confirmed(base_env, cleanup_bot_modules):
    """Test that webhook for already-confirmed payment is idempotent."""
    os.environ.clear()
    os.environ.update(base_env)
    
    from bot.handlers.payment_webhook import handle_cryptomus_webhook
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
    
    from bot.service.subscription_service import extend_subscription
    from bot.database.models.main import Persons
    
    session = AsyncMock()
    
    # Mock person with no keys
    person = Persons()
    person.keys = []
    person.tgid = 123
    
    # Mock _get_person to return person
    mock_key = MagicMock()
    mock_key.id = 42
    
    with patch('bot.service.subscription_service._get_person') as mock_get:
        mock_get.return_value = person
        with patch('bot.service.subscription_service.add_key') as mock_add:
            mock_add.return_value = mock_key
            with patch('bot.service.subscription_service.get_free_server_id'):
                result = await extend_subscription(
                    123,
                    30,
                    'test_reason',
                    session
                )
                assert result == mock_key
