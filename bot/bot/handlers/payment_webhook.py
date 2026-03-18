"""
Legacy compatibility import path for Cryptomus payment helper.

Production webhook runtime is mounted from `bot.webhooks.*`; the canonical home
for this helper is now `bot.services.cryptomus_payment_service`.
"""

from bot.services.cryptomus_payment_service import handle_cryptomus_webhook

__all__ = ['handle_cryptomus_webhook']
