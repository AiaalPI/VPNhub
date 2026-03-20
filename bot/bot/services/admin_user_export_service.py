from bot.misc.language import Localization

_ = Localization.text


async def list_columns_user(lang):
    return [
        '№',
        _('user_fullname', lang),
        _('user_username', lang),
        _('user_tgid', lang),
        _('user_lang_tg', lang),
        _('user_referral_balance', lang),
        _('user_group', lang),
        _('user_key', lang),
    ]


async def list_user(client, count, not_key=False):
    if not not_key:
        count_key = 0
        for key in client.keys:
            if key.free_key or key.trial_period:
                continue
            count_key += 1
    else:
        count_key = ''
    return [
        count,
        client.fullname,
        client.username,
        int(client.tgid),
        client.lang_tg or '❌',
        client.referral_balance,
        client.group if client.group is not None else '',
        count_key
    ]
