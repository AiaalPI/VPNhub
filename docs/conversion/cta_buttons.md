# CTA Buttons (AS-IS -> Recommended)

## Primary CTA hierarchy
1. Primary: get connected / pay now
2. Secondary: trial / promo / details
3. Recovery: back / main menu

## Main menu
- Existing callbacks (keep):
  - `vpn_connect_btn`
  - `affiliate_btn`
  - `help_btn`
  - `language_btn`
  - `about_vpn_btn`

Recommended labels:
- RU: «Подключить VPN», «Партнёрка», «Поддержка», «Язык», «О сервисе»
- EN: "Connect VPN", "Referral", "Support", "Language", "About"

## Connect flow CTAs
- Existing callbacks (keep): `ChooseTypeVpn(*)`, `ChooseLocation(*)`, `generate_new_key`, `DetailKey(*)`, `ShowKey(*)`, `ExtendKey(*)`
- Recommended CTA text style:
  - Action-first + outcome (e.g., "Получить ключ", "Продлить доступ")

## Payment CTAs
- Existing callbacks (keep): `ChoosingMonths(*)`, `ChoosingPrise(*)`, `PromoCodeChoosing(*)`
- Recommended:
  - Month buttons include value cue: "1 мес — {price} ₽"
  - Payment step title button semantics: method names only (no mixed tone)

## Referral CTAs
- Existing callbacks (keep): `withdrawal_of_funds`, `promo_code`
- Recommended:
  - RU: «Поделиться ссылкой», «Вывести средства», «Ввести промокод»
  - EN: "Share link", "Withdraw funds", "Enter promo code"

## Recovery CTAs
- Standardize visible recovery in all text-input states:
  - `back_general_menu_btn` as universal safety action
- Avoid placeholder taps for production-visible paths (`none`, `none protocol`).
