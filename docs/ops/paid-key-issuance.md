# Bot payment issuance recovery (2026-09-29)

## Incident

Key 157 existed in PostgreSQL after manual YooMoney approval but was absent from
3x-ui. A disabled diagnostic client reproduced the panel rejection:
`cannot unmarshal string into Go struct field Client.client.tgId of type int64`.
`pyxui_async.Client` defaults `tgId` to an empty string. Converting it to integer
zero and supplying nonempty `security` makes the global API accept creation.
The diagnostic client was deleted. Key 157 was restored on inbounds 1 and 2 with
its existing expiration; real TCP/REALITY and XHTTP/REALITY requests returned 204.

The old payment poller stopped after 60 seconds and requested manual approval
whether or not any payment existed. The old renewal API returned 404, and
creation failures could be swallowed before reporting activation.

## New behavior

- New `vb2_` invoices are committed before exposing a payment URL. YooMoney's
  documented `button`/`AC` form replaces the legacy `shop`/`SB` parameters.
- A scheduler checks up to 30 due orders every 15 seconds. Young unpaid orders
  repeat every 30 seconds; invoices older than one hour repeat hourly without
  being discarded. Provider/panel failures back off to a maximum 15 minutes.
- Authenticated wallet history must return the exact random label, successful
  incoming status and a unique operation ID. HTTP redirects and webhook bodies
  cannot approve these invoices. TLS verification stays enabled.
- History returns net proceeds. The AC form's documented 3% receiving commission
  is accounted for with Decimal and kopeck rounding; receipts below those net
  proceeds are rejected. This is a net-receipt check, not independent proof of a
  payer's gross amount. Native signed notifications are required for exact gross
  verification; this change uses the existing authorized wallet token.
- Receipt identity is durable before server selection. Payment, purchased time,
  allowance, and referral entitlement commit together under PostgreSQL row locks.
- Provisioning retries reuse the same key and absolute current expiration/quota.
  Global panel APIs verify the same identity on both configured inbounds. Used
  traffic is never reset by reconciliation. Legacy quota is captured on renewal.
- User/admin/referral delivery is retried separately. Telegram delivery is
  at-least-once: a crash just after sending may repeat a message, never a credit.
- Legacy manual buttons use their message ID as stable receipt identity. Old
  invoices are not automatically backfilled: previously moderated transfers
  cannot safely be re-credited by amount/time matching.

## Inspection and deployment

Deploy through the normal main-branch GitHub Actions workflow and
`/opt/vpnhub/deploy.sh`. Migration `20b3c4d5e6f7` adds the durable order table and
nullable key allowance. No new provider secrets or infrastructure are required.

Read-only operational query:

```sql
SELECT id, user_tgid, key_id, paid_at, fulfilled, completed,
       attempts, last_error, to_timestamp(next_attempt)
FROM bot_payment_orders
WHERE NOT completed
ORDER BY next_attempt;
```

`operation_id IS NOT NULL AND paid_at IS NULL` means verified receipt awaiting
entitlement creation (for example no available server). `paid_at IS NOT NULL AND
NOT fulfilled` means panel provisioning pending. `fulfilled AND NOT completed`
means notification/referral delivery pending. Do not delete orders or clear
receipt IDs to retry: the scheduler already retries them without extending again.
Never manually credit an unlabelled transfer solely by matching its amount.

Sources: [YooMoney payment form and fees](https://yoomoney.ru/docs/payment-buttons/using-api/forms),
[wallet operation history](https://yoomoney.ru/docs/wallet/user-account/operation-history),
[3x-ui global client API](https://github.com/MHSanaei/3x-ui/blob/main/docs/content/docs/en/reference/api/clients.mdx).
