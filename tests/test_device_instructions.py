import asyncio

import pytest

from bot.handlers.instructions import _build_subscription_qr, _iphone_screenshot_album
from bot.keyboards.device_keyboard import device_instruction_keyboard


def test_iphone_keyboard_lists_three_clients_in_recommended_order():
    keyboard = asyncio.run(
        device_instruction_keyboard(
            lang="ru",
            key_id=152,
            device="iphone",
            subscription_link="https://sub.example.com/test",
        )
    )
    buttons = [row[0] for row in keyboard.inline_keyboard]
    app_buttons = buttons[:3]

    assert [button.url for button in app_buttons] == [
        "https://apps.apple.com/app/id6504287215",
        "https://apps.apple.com/app/id6596777532",
        "https://apps.apple.com/app/id6450534064",
    ]
    assert "Happ" in app_buttons[0].text
    assert "Hiddify" in app_buttons[1].text
    assert "Streisand" in app_buttons[2].text


def test_iphone_screenshot_album_has_one_image_per_client():
    album = _iphone_screenshot_album("ru")

    assert len(album) == 3
    assert "Happ" in album[0].caption
    assert "Hiddify" in album[1].caption
    assert "Streisand" in album[2].caption


def test_subscription_qr_is_still_generated():
    pytest.importorskip("qrcode")
    qr = _build_subscription_qr("https://sub.example.com/test")

    assert qr.filename == "kynvpn-subscription-qr.png"
    assert len(qr.data) > 100
