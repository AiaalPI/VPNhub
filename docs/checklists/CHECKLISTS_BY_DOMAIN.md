# CHECKLISTS_BY_DOMAIN — IMPLEMENTATION GUIDES BY DISCIPLINE

**Version:** 1.0
**Date:** 2026-02-24
**References:** GITHUB_ISSUES_BACKLOG.md (linked by Issue #)

---

## CHECKLIST 1: USER EXPERIENCE IMPLEMENTATION

**Linked Issues:** #401 (UX Fixes), #302 (Key Reassignment)
**Epic:** 4 — UX Optimization & Conversion
**Success Metric:** Trial→Paid conversion 3-5% → 12% within 30 days of rollout

---

### 1.1 ONBOARDING FLOW

**Goal:** Reduce new user setup from 5+ taps to <3 taps. Target: <30 seconds to first connected key.

**File References:** `docs/ux/fix_plan.md`, `bot/bot/handlers/user/main.py:93-170`

- [ ] **Read current UX spec**
  - [ ] Review `docs/ux/as_is_map.md` — understand all current screens (Section "New User Branch")
  - [ ] Identify all taps in current flow (count exact number)
  - [ ] Document which screens are blocking (where users abandon)
  - **Verify:** Current flow requires ≥5 taps to get connected key

- [ ] **Implement auto-server selection** (ISSUE #401 subtask, 3h)
  - **What:** Instead of "Choose location" screen, auto-select best server by latency
  - **File:** `bot/bot/handlers/user/main.py:150-170`
  - **Before:**
    ```python
    async def register_trial(message: Message, state: FSMState):
        # User must choose location from keyboard
        await message.answer(
            "📍 Choose VPN location:",
            reply_markup=location_keyboard()  # 10+ buttons
        )
        await state.set_state(UserState.location_selection)
    ```
  - **After:**
    ```python
    async def register_trial(message: Message, state: FSMState):
        # Auto-select best server
        best_server = await get_best_server_by_latency(user_tgid=message.from_user.id)
        trial_key = await issue_trial_key(
            tgid=message.from_user.id,
            server_id=best_server.id
        )
        await message.answer(
            f"✅ Connected to {best_server.location}!\n\n"
            f"Key: `{trial_key}`\n"
            f"⏱️ Expires in 3 days",
            reply_markup=copy_key_keyboard(trial_key)
        )
    ```
  - **Verify:**
    ```bash
    # Test: /start → should jump directly to key delivery (no location selection)
    curl -X POST http://localhost:8888/webhook \
      -H "Content-Type: application/json" \
      -d '{"message":{"text":"/start","from":{"id":123,"is_bot":false},"chat":{"id":123,"type":"private"}}}'

    # Grep logs for: "Best server selected" + server_id
    docker compose logs vpn_hub_bot | grep "Best server selected"
    ```

- [ ] **Remove unnecessary store prompt** (ISSUE #401 subtask, 2h)
  - **What:** Delete "Choose VPN store" screen — auto-assign based on user region
  - **File:** `bot/bot/handlers/user/main.py:160-180`
  - **Remove class:** `UserState.store_selection` from FSM states
  - **Search for:** `reply_markup=store_selection_keyboard()`
  - **Replace with:** Direct server connection or auto-assign from geolocation
  - **Verify:**
    ```bash
    # No state named "store_selection" should remain
    grep -r "store_selection" bot/bot/handlers/
    # Should return: (no matches)
    ```

- [ ] **Fast-path to key delivery** (ISSUE #401 subtask, 2h)
  - **File:** `bot/bot/handlers/user/keys_user.py:40-60` (newly created fast path)
  - **Logic:** `/start` → auto-grant → key delivered → done
  - **Create new handler:**
    ```python
    @registered_router.message(Command("start"))
    async def fast_onboarding_start(message: Message, state: FSMState):
        """Fast path: 1-tap onboarding for new users."""
        user = await get_user(message.from_user.id)

        if not user:
            # New user: auto-provision trial
            trial_key = await issue_trial_key(
                tgid=message.from_user.id,
                auto_select=True
            )
            await message.answer(
                f"🎉 VPNHub Trial Ready!\n\n"
                f"📋 Connection Key:\n`{trial_key}`\n\n"
                f"⏱️ Valid for 3 days\n\n"
                f"Need help? /help",
                reply_markup=quick_actions_keyboard()
            )
        else:
            # Existing user: show main menu
            await state.set_state(UserState.main_menu)
            await show_main_menu(message)
    ```
  - **Verify:**
    ```bash
    # Test with fresh telegram ID
    # Expected: /start → immediate key delivery (no intermediate screens)
    # Measure latency: message received → key delivered timing
    python -c "import time; start=time.time(); ...(send /start); print(f'Delivered in {time.time()-start}s')"
    ```

- [ ] **Measure onboarding funnel** (ISSUE #401 subtask, 2h)
  - **File:** `bot/bot/middlewares/conversion_events.py` (already logs events)
  - **Query conversion logs:**
    ```bash
    # Count new users reaching each funnel stage
    docker compose logs vpn_hub_bot | grep "event=conv.start" | wc -l
    docker compose logs vpn_hub_bot | grep "event=conv.trial_issued" | wc -l
    docker compose logs vpn_hub_bot | grep "event=conv.key_copied" | wc -l

    # Calculate drop-off %
    # If: 100 start, 95 trial_issued, 80 key_copied → 20% drop-off after trial
    ```
  - **Document:** Create `docs/ux/onboarding_metrics.md` with before/after comparison
  - **Success criteria:**
    - [ ] Onboarding time: <30 seconds (measure from /start to key delivered)
    - [ ] Drop-off rate: <10% from start to key delivered
    - [ ] Mobile performance: <5 seconds on 3G (simulate with browser DevTools)

---

### 1.2 FIRST CONNECTION EXPERIENCE

**Goal:** Make first VPN connection intuitive and fast. Target: User connects within 1 minute of receiving key.

**File References:** `bot/bot/handlers/user/keys_user.py`, `docs/ux/audit_findings.md` (P0 friction points)

- [ ] **Simplify connection instructions**
  - **Current problem:** Users don't understand how to use the key
  - **Solution:** Inline visual guide with copy button
  - **File:** `bot/bot/handlers/user/keys_user.py:52-80`
  - **Implement:**
    ```python
    async def deliver_trial_key(message: Message, key_data: str):
        """Send key with ultra-clear copy-paste instructions."""

        instructions = (
            "📖 **How to Connect:**\n\n"
            "1️⃣ Copy the key below\n"
            "2️⃣ Use WireGuard or OpenVPN app\n"
            "3️⃣ Paste the key in settings\n"
            "4️⃣ Tap 'Connect'\n\n"
            f"🔑 Your Key (Click to copy):\n\n`{key_data}`\n\n"
            "📱 **Apps:**\n"
            "• WireGuard: [iOS](https://...) [Android](...)\n"
            "• OpenVPN: [iOS](https://...) [Android](...)"
        )

        await message.answer(
            instructions,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Copy Key", callback_data="copy_key")],
                [InlineKeyboardButton(text="❓ Help", callback_data="help_connect")],
                [InlineKeyboardButton(text="💳 Upgrade", callback_data="upgrade_plan")]
            ])
        )
    ```
  - **Verify:**
    ```bash
    # Send test message with key
    # Check: Is key rendered in click-copyable format?
    # Mobile test: Can copy with single tap?
    ```

- [ ] **Add connection status checker**
  - **What:** Hook that detects if user successfully connected
  - **File:** `bot/bot/handlers/user/keys_user.py:100-150`
  - **Logic:** Monitor DNS queries, VPN connections from server side
  - **Fallback:** Ask user "Are you connected?" with Yes/No buttons after 2 minutes
  - **Implement:**
    ```python
    async def check_connection_status(user_tgid: int, key_id: str, timeout_sec: int = 120):
        """Check if user successfully connected, send encouragement if not."""
        await asyncio.sleep(timeout_sec)

        key = await get_key(key_id)
        if not key.connection_confirmed:
            # User hasn't connected yet, send help
            await send_encouragement_message(user_tgid)
    ```
  - **Verify:**
    ```bash
    # Simulate user getting key at time T
    # At T+120 seconds, system should check connection
    # If not connected, message appears
    ```

- [ ] **Test on actual devices**
  - [ ] iOS (WireGuard app)
  - [ ] Android (OpenVPN app)
  - [ ] macOS (native VPN settings)
  - **Verify:** Connection succeeds <1 minute from key delivery
  - **Document:** Add to `docs/ux/device_test_results.md`

---

### 1.3 PAYMENT FLOW

**Goal:** Show all payment options upfront. Increase visible payment methods: 1→3+. Target: +8% conversion with choice.

**File References:** `bot/bot/handlers/user/payment.py`, `docs/conversion/cta_buttons.md`, ISSUE #401

- [ ] **Audit current payment methods**
  - **What:** What payment providers are currently integrable?
  - **File:** `bot/bot/service/payment/` (search directory)
  - **Commands:**
    ```bash
    ls -la bot/bot/service/payment/
    grep -r "class.*Provider" bot/bot/service/payment/
    grep -r "def.*checkout" bot/bot/service/payment/
    ```
  - **Document findings** in issue tracker
  - **Expected:** Stripe, PayPal, CRYPTOMUS, YOOKASSA (from .env)
  - **Create list** of supported payment methods with checkout URLs

- [ ] **Implement payment method selector UI**
  - **Current:** Only 1 method shown (hidden behind provider logic)
  - **Target:** Show 3-5 methods, let user choose
  - **File:** `bot/bot/handlers/user/payment.py:80-120`
  - **Before:**
    ```python
    async def start_payment(message: Message):
        # Hardcoded to one provider
        stripe_url = await get_stripe_checkout(user_id=message.from_user.id)
        await message.answer(f"Pay here: {stripe_url}")
    ```
  - **After:**
    ```python
    async def start_payment(message: Message, state: FSMState):
        """Show all payment options, let user choose."""

        payments = [
            {"method": "stripe", "label": "💳 Stripe (Credit Card)", "icon": "🔒"},
            {"method": "paypal", "label": "🅿️ PayPal", "icon": "✅"},
            {"method": "crypto", "label": "₿ Bitcoin / USDC", "icon": "⛓️"},
        ]

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{p['icon']} {p['label']}",
                callback_data=f"pay_method_{p['method']}"
            )] for p in payments
        ])

        await message.answer(
            "💰 **Upgrade to Paid**\n\n"
            "Choose payment method:\n",
            reply_markup=keyboard
        )
        await state.set_state(UserState.payment_selection)
    ```
  - **Verify:**
    ```bash
    # Test /upgrade command
    # Should show 3 payment buttons
    # Click each one → should redirect to correct checkout flow
    grep -n "pay_method_" bot/bot/handlers/user/payment.py
    ```

- [ ] **Add payment success confirmation**
  - **File:** `bot/bot/handlers/webhooks/payment.py:200-250`
  - **What:** User gets clear success message after payment
  - **Implement:**
    ```python
    async def on_payment_success(message: Message, payment_id: str):
        """Called after successful payment (webhook from provider)."""

        user = await get_user(message.from_user.id)
        subscription = await get_subscription(user.id)

        await message.answer(
            f"✅ **Payment Successful!**\n\n"
            f"Plan: {subscription.plan_name}\n"
            f"Valid until: {subscription.expires_at.strftime('%Y-%m-%d')}\n"
            f"Speed: Unlimited\n\n"
            f"Ready to connect? /vpn_connect",
            reply_markup=main_menu_keyboard()
        )

        # Log conversion event
        logger.info(f"event=conv.payment_success user_id={user.id} plan={subscription.plan_name}")
    ```
  - **Verify:**
    ```bash
    # Simulate payment webhook
    curl -X POST http://localhost:8888/webhook/stripe \
      -H "Content-Type: application/json" \
      -d '{"event":"charge.succeeded","user":{"id":123}}'

    # Check logs for: event=conv.payment_success
    docker compose logs vpn_hub_bot | grep "conv.payment_success"
    ```

- [ ] **Test payment flow end-to-end** (ISSUE #401 subtask, 3h)
  - [ ] Test Stripe payment (can use test card numbers)
  - [ ] Test PayPal sandbox
  - [ ] Test Bitcoin/USDC flow (if available)
  - **Measure:** Payment to active VPN: <2 minutes
  - **Document:** `docs/ux/payment_test_results.md`
  - **Success criteria:**
    - [ ] All 3 methods accessible
    - [ ] Each completes payment in <2 minutes
    - [ ] Success confirmation clear and immediate
    - [ ] No broken redirect links
    - [ ] Payment refund process works

---

### 1.4 RENEWAL & EXPIRY ALERTS

**Goal:** Reduce churn by alerting users before subscription expires. Target: Reduce churned users by 20%.

**File References:** `bot/bot/misc/start_consumers.py` (background jobs), ISSUE #302

- [ ] **Implement expiry alert scheduler**
  - **File:** `bot/bot/misc/expiry_alerts.py` (create new)
  - **Logic:** Check daily for subscriptions expiring in 3, 7, 14 days
  - **Implement:**
    ```python
    async def daily_expiry_checker():
        """Send alerts for impending expiries."""

        # Find subscriptions expiring in: 3, 7, 14 days
        thresholds = [3, 7, 14]

        for threshold_days in thresholds:
            target_date = datetime.utcnow() + timedelta(days=threshold_days)
            subscriptions = await get_subscriptions_expiring_on(target_date)

            for sub in subscriptions:
                user = await get_user(sub.user_tgid)
                days_left = (sub.expires_at - datetime.utcnow()).days

                message = (
                    f"⏰ **VPN Expiring in {days_left} days!**\n\n"
                    f"Renew now to keep connected:\n"
                    f"• 1 month: ${sub.plan.monthly_price}\n"
                    f"• 3 months: ${sub.plan.quarterly_price} (-10%)\n"
                    f"• 1 year: ${sub.plan.annual_price} (-30%)"
                )

                await bot.send_message(
                    user.tgid,
                    message,
                    reply_markup=renewal_keyboard(sub.plan)
                )

                logger.info(f"event=expiry.alert user_id={user.id} days_left={days_left}")
    ```
  - **Verify:**
    ```bash
    # Manually trigger checker
    python -c "
    import asyncio
    from bot.bot.misc.expiry_alerts import daily_expiry_checker
    asyncio.run(daily_expiry_checker())
    "

    # Check logs: event=expiry.alert
    docker compose logs vpn_hub_bot | grep "expiry.alert"
    ```

- [ ] **Schedule background check**
  - **File:** `bot/bot/misc/start_consumers.py:50-80`
  - **Add task:**
    ```python
    async def start_all_background_tasks(bot, session_maker):
        """Initialize all background tasks."""

        # ... existing code ...

        # Add expiry checker
        asyncio.create_task(
            schedule_daily_task(
                daily_expiry_checker,
                run_time=datetime.time(hour=9, minute=0),  # 9 AM UTC
                session_maker=session_maker
            )
        )
    ```
  - **Verify:** No errors on bot startup
    ```bash
    docker compose up vpn_hub_bot
    # Wait 10 seconds
    # Check logs for: "Expiry alert task started"
    ```

- [ ] **Test alert delivery**
  - [ ] Set up test subscription expiring tomorrow
  - [ ] Run scheduler
  - [ ] Verify message received
  - [ ] Verify correct renewal pricing shown
  - **Document:** `docs/ux/expiry_alert_test.md`

---

### 1.5 MULTI-DEVICE SUPPORT

**Goal:** Users can connect multiple devices simultaneously. Current: 1 device, 1 key. Target: 1 plan, up to 3 devices.

**File References:** `bot/bot/database/models/subscription.py`, ISSUE #401 subtask

- [ ] **Audit current device model**
  - **What:** How are keys/devices stored?
  - **File:** `bot/bot/database/models/key.py`
  - **Commands:**
    ```bash
    grep -A 20 "class Key" bot/bot/database/models/key.py
    grep -A 10 "user_id" bot/bot/database/models/key.py | head -20
    ```
  - **Current limitation:** 1 key per user (likely FK constraint)
  - **Document:** Current schema in issue

- [ ] **Modify schema: allow multiple keys**
  - **File:** `bot/bot/alembic/versions/` (create new migration)
  - **Create migration:**
    ```bash
    cd bot && alembic revision --autogenerate -m "Add multi-device support"
    ```
  - **Migration logic:**
    ```python
    # In: bot/bot/alembic/versions/XXX_add_multi_device.py

    def upgrade():
        # Add device_name column to keys table
        op.add_column('keys', sa.Column('device_name', sa.String(100)))
        op.add_column('keys', sa.Column('device_uuid', sa.String(36)))
        # Allow user to have multiple non-expired keys
        # (before: Unique(user_id) prevented this)
        op.drop_constraint('uq_keys_user_id', table_name='keys')
        op.create_unique_constraint(
            'uq_keys_per_user_device',
            'keys',
            ['user_id', 'device_uuid']
        )

    def downgrade():
        # Reverse changes
        op.drop_constraint('uq_keys_per_user_device', table_name='keys')
        op.create_unique_constraint('uq_keys_user_id', 'keys', ['user_id'])
        op.drop_column('keys', 'device_uuid')
        op.drop_column('keys', 'device_name')
    ```
  - **Verify migration:**
    ```bash
    cd bot
    alembic upgrade head
    # Check DB schema:
    psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d keys"
    # Should show: device_name, device_uuid columns
    ```

- [ ] **Implement device management UI**
  - **File:** `bot/bot/handlers/user/devices.py` (create new)
  - **Commands:**
    ```python
    @registered_router.callback_query(Text("manage_devices"))
    async def manage_devices(callback: CallbackQuery, state: FSMState):
        """Show user's connected devices and allow adding more."""

        user = await get_user(callback.from_user.id)
        keys = await get_user_keys(user.id)

        if len(keys) >= 3:
            await callback.answer("❌ Max 3 devices per plan", show_alert=True)
            return

        message = f"📱 **Your Devices** ({len(keys)}/3)\n\n"

        for key in keys:
            message += (
                f"• {key.device_name or 'Unnamed'}\n"
                f"  Added: {key.created_at.strftime('%Y-%m-%d')}\n"
                f"  [Remove](button)\n\n"
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Device", callback_data="add_device")],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_menu")]
        ])

        await callback.message.edit_text(message, reply_markup=keyboard)

    @registered_router.callback_query(Text("add_device"))
    async def add_device(callback: CallbackQuery, state: FSMState):
        """Generate new key for device."""

        user = await get_user(callback.from_user.id)
        new_key = await issue_key(
            user_id=user.id,
            device_name="New Device"
        )

        await callback.message.answer(
            f"✅ **New Key Generated**\n\n"
            f"`{new_key.key_string}`\n\n"
            f"Device name: {new_key.device_name}\n"
            f"Valid until: {new_key.expires_at.strftime('%Y-%m-%d')}"
        )
    ```
  - **Verify:**
    ```bash
    # Test: Add 3 keys, try to add 4th
    # Should show: "Max 3 devices per plan"
    # Verify DB: SELECT COUNT(*) FROM keys WHERE user_id = 123;
    # Expected: 3
    ```

- [ ] **Test multi-device scenario**
  - [ ] Connect to VPN from PC, Phone, Tablet simultaneously
  - [ ] Verify all connections work
  - [ ] Disconnect one device
  - [ ] Check other devices still connected
  - [ ] Verify bandwidth split across devices
  - **Document:** `docs/ux/multi_device_test.md`

---

### 1.6 SUPPORT & HELP SYSTEM

**Goal:** Reduce support burden by providing self-service answers. Target: 70% of "help" questions answered via bot.

**File References:** `bot/bot/handlers/user/help.py`, ISSUE #401

- [ ] **Create help knowledge base**
  - **File:** `docs/support/faq.md` (create new)
  - **Content:**
    ```markdown
    # FAQ — Frequently Asked Questions

    ## Connection Issues

    ### Q: Connection times out
    - A: Try another server location
    - A: Check device firewall settings
    - A: Restart WireGuard app

    ### Q: Slow speeds
    - A: Distance matters (closer = faster)
    - A: Try "Ultra-Fast" server setting
    - A: Check device WiFi/4G connection

    ## Billing

    ### Q: Why did payment fail?
    - A: Check card expiry
    - A: Try different payment method
    - A: Contact support: /support

    ### Q: How to upgrade?
    - A: Click "Upgrade" button in main menu
    - A: Choose payment method
    - A: Instant access after payment

    ## Account

    ### Q: How to change password?
    - A: Settings → Security → Change Password
    - A: Or contact support: /support
    ```

- [ ] **Implement help search**
  - **File:** `bot/bot/handlers/user/help.py:20-80`
  - **Command:** `/help <keyword>`
  - **Implement:**
    ```python
    @registered_router.message(Command("help"))
    async def help_command(message: Message):
        """Show help menu with search."""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔌 Connection", callback_data="help_connection")],
            [InlineKeyboardButton(text="💳 Billing", callback_data="help_billing")],
            [InlineKeyboardButton(text="👤 Account", callback_data="help_account")],
            [InlineKeyboardButton(text="📞 Contact Support", callback_data="contact_support")],
        ])

        await message.answer(
            "❓ **Help Center**\n\n"
            "Choose a topic or search: `/help connection`",
            reply_markup=keyboard
        )

    @registered_router.message(Command("help"), RegexFilter(regex=r"/help (.+)"))
    async def help_search(message: Message):
        """Search FAQ by keyword."""

        query = message.text.replace("/help ", "").lower()
        results = search_faq(query)

        if not results:
            await message.answer(f"❌ No results for '{query}'\n\nContact support: /support")
            return

        answer_text = f"📚 Results for '{query}':\n\n"
        for result in results[:3]:
            answer_text += f"• {result['question']}\n{result['answer']}\n\n"

        await message.answer(answer_text)
    ```
  - **Verify:**
    ```bash
    # Test help search
    curl -X POST http://localhost:8888/webhook \
      -d '{"message":{"text":"/help connection"}}'

    # Should return FAQ results
    docker compose logs vpn_hub_bot | grep "Results for"
    ```

- [ ] **Implement escalation to human support**
  - **File:** `bot/bot/handlers/user/support.py` (create new)
  - **Command:** `/support <message>`
  - **Implement:**
    ```python
    @registered_router.message(Command("support"))
    async def contact_support(message: Message, state: FSMState):
        """Escalate to human support agent."""

        await message.answer(
            "📞 **Contact Support**\n\n"
            "Describe your issue:\n"
        )
        await state.set_state(UserState.support_message)

    @registered_router.message(UserState.support_message)
    async def handle_support_message(message: Message, state: FSMState):
        """Queue message for support agent."""

        user = await get_user(message.from_user.id)
        support_ticket = await create_support_ticket(
            user_id=user.id,
            message=message.text
        )

        # Notify support team
        await notify_support_team(support_ticket)

        await message.answer(
            f"✅ **Ticket #{support_ticket.id} Created**\n\n"
            f"We'll respond within 1 hour.\n"
            f"Track: /support_status {support_ticket.id}"
        )

        await state.clear()
    ```
  - **Verify:**
    ```bash
    # Test support ticket creation
    # Check DB: SELECT * FROM support_tickets WHERE user_id = 123;
    # Should show new ticket
    ```

- [ ] **Test help system**
  - [ ] Test 5 different FAQ searches
  - [ ] Test support ticket creation
  - [ ] Verify support team notified
  - [ ] Verify ticket tracking works
  - **Document:** `docs/ux/help_system_test.md`
  - **Acceptance:** 70% of help queries answered via FAQ, <5% escalation needed

---

**CHECKLIST 1 COMPLETION CRITERIA**

- [ ] All onboarding optimizations deployed (4/4 subsections complete)
- [ ] Trial→Paid conversion measured at >10% (up from baseline)
- [ ] Average setup time: <30 seconds (verified with real users)
- [ ] All 3 payment methods accessible and working
- [ ] Multi-device support tested with 3 simultaneous connections
- [ ] Help system tested: 10 searches, 8/10 answered via FAQ
- [ ] No increase in support tickets post-deployment
- [ ] Zero UX-related issues in logs

---

---

## CHECKLIST 2: CHINA READINESS IMPLEMENTATION

**Linked Issues:** #501 (Protocols), #502 (Backup Domains)
**Epic:** 5 — China Readiness
**Success Metric:** User connections from mainland China succeed >80% of attempts, latency <200ms (95th percentile)

---

### 2.1 PROTOCOL STACK: SHADOWSOCKS + OBFS4

**Goal:** Add protocol alternatives that defeat Deep Packet Inspection (DPI). Shadowsocks is faster, obfs4 is more covert.

**File References:** `bot/bot/service/vpn/protocols.py`, `docs/conversion/` (China experiments)

- [ ] **Research DPI-resistant protocols** (ISSUE #501, 2h)
  - **What:** How do current protocols fail in China?
  - **Commands:**
    ```bash
    # Test current protocol detection rate
    # (Requires GFW simulator or mainland CN IP)

    # Current protocols likely blocked:
    # - WireGuard: DPI signature pattern: "Noise protocol"
    # - OpenVPN: Certificate headers detectable

    # Shadowsocks: Encrypted payload, looks like random traffic
    # obfs4: Obfuscated handshake, indistinguishable from TLS
    ```
  - **Document:** `docs/china/dpi_analysis.md` (create new)
  - **Reference:** https://gfw.report (Great Firewall status)

- [ ] **Implement shadowsocks support** (ISSUE #501, 3h)
  - **File:** `bot/bot/service/vpn/protocols/shadowsocks.py` (create new)
  - **Library:** Use `shadowsocks-python` or `python-shadowsocks`
  - **Implement:**
    ```python
    # bot/bot/service/vpn/protocols/shadowsocks.py

    class ShadowsocksProtocol:
        """Shadowsocks protocol wrapper."""

        SUPPORTED_CIPHERS = [
            "aes-256-gcm",      # Fast + secure
            "chacha20-poly1305", # Faster
            "aes-128-gcm",       # Good enough
        ]

        SUPPORTED_PORTS = [443, 8388, 8888, 9000]  # Non-standard ports harder to block

        def __init__(self, server_ip: str, port: int, password: str, cipher: str = "aes-256-gcm"):
            self.server_ip = server_ip
            self.port = port
            self.password = password
            self.cipher = cipher

        def generate_config_json(self) -> dict:
            """Generate JSON config for client."""
            return {
                "server": self.server_ip,
                "server_port": self.port,
                "password": self.password,
                "method": self.cipher,
                "protocol": "origin",  # or "auth_sha1" for obfuscation
                "remarks": "🇨🇳 China-optimized",
            }

        async def test_connection(self, timeout_sec: int = 10) -> bool:
            """Test if shadowsocks server is reachable."""
            try:
                async with asyncio.timeout(timeout_sec):
                    # Try to establish shadowsocks connection
                    reader, writer = await asyncio.open_connection(
                        self.server_ip, self.port
                    )
                    # Send minimal SS handshake
                    # ...
                    return True
            except:
                return False
    ```
  - **Verify:**
    ```bash
    # Create test config
    python -c "
    from bot.bot.service.vpn.protocols.shadowsocks import ShadowsocksProtocol
    ss = ShadowsocksProtocol('1.2.3.4', 8888, 'mypassword')
    config = ss.generate_config_json()
    print(config)
    "

    # Expected output:
    # {'server': '1.2.3.4', 'server_port': 8888, 'password': '...', 'method': 'aes-256-gcm', ...}
    ```

- [ ] **Implement obfs4 (obfuscation) layer** (ISSUE #501, 3h)
  - **File:** `bot/bot/service/vpn/protocols/obfs4.py` (create new)
  - **Library:** `obfs4proxy` (Go binary) or pure Python implementation
  - **Purpose:** Obfuscate TLS handshake to look random
  - **Implement:**
    ```python
    # bot/bot/service/vpn/protocols/obfs4.py

    class Obfs4Transport:
        """Obfs4 obfuscation transport."""

        def __init__(self, base_protocol: str = "shadowsocks"):
            self.base_protocol = base_protocol
            self.public_key = None
            self.node_id = None

        def generate_obfs4_keys(self) -> dict:
            """Generate public/private keypair for obfs4."""
            from cryptography.hazmat.primitives.asymmetric import ed25519
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            return {
                "public_key": public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ).hex(),
                "private_key": private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                ).hex(),
            }

        def wrap_with_obfs4(self, config: dict) -> dict:
            """Wrap protocol config with obfs4 obfuscation."""
            keys = self.generate_obfs4_keys()
            return {
                **config,
                "obfs4": {
                    "public_key": keys["public_key"],
                    "node_id": self.node_id or "vpnhub-node-1",
                    "iat_mode": 1,  # IAT obfuscation mode
                }
            }
    ```
  - **Verify:**
    ```bash
    # Test obfs4 key generation
    python -c "
    from bot.bot.service.vpn.protocols.obfs4 import Obfs4Transport
    obfs4 = Obfs4Transport()
    keys = obfs4.generate_obfs4_keys()
    print('Public key:', keys['public_key'][:32] + '...')
    "
    ```

- [ ] **Add protocol selection in UI** (ISSUE #501, 2h)
  - **File:** `bot/bot/handlers/user/protocol_select.py` (create new)
  - **Handler:**
    ```python
    @registered_router.callback_query(Text("select_protocol"))
    async def select_protocol(callback: CallbackQuery, state: FSMState):
        """Let user choose VPN protocol."""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⚡ Shadowsocks (Fastest)",
                callback_data="protocol_shadowsocks"
            )],
            [InlineKeyboardButton(
                text="🎭 obfs4 (Stealthiest)",
                callback_data="protocol_obfs4"
            )],
            [InlineKeyboardButton(
                text="🔐 WireGuard (Secure)",
                callback_data="protocol_wireguard"
            )],
            [InlineKeyboardButton(
                text="🔓 OpenVPN (Universal)",
                callback_data="protocol_openvpn"
            )],
        ])

        await callback.message.edit_text(
            "🔧 **VPN Protocol**\n\n"
            "• Shadowsocks: Best for China (DPI-resistant)\n"
            "• obfs4: Most stealthy\n"
            "• WireGuard: Fastest globally\n"
            "• OpenVPN: Works everywhere\n\n"
            "Recommended: Shadowsocks for China",
            reply_markup=keyboard
        )

    @registered_router.callback_query(Text("protocol_shadowsocks"))
    async def handle_shadowsocks_select(callback: CallbackQuery, state: FSMState):
        """User selected shadowsocks."""

        user = await get_user(callback.from_user.id)
        key = await issue_key_with_protocol(
            user_id=user.id,
            protocol="shadowsocks"
        )

        await callback.message.answer(
            f"✅ **Shadowsocks Key**\n\n"
            f"`{key.config_string}`\n\n"
            f"Best for: 🇨🇳 Mainland China\n"
            f"Speed: ⚡ Very Fast\n"
            f"Stealth: ✅ High"
        )
    ```
  - **Verify:**
    ```bash
    # Test protocol selection
    # User clicks "Shadowsocks" → receives SS config
    # Grep logs: "protocol_shadowsocks selected"
    ```

- [ ] **Test protocols from China IP** (ISSUE #501, 4h)
  - **Setup:** Use mainland CN IP (or VPN to China for testing)
  - **Test steps:**
    ```bash
    # Test each protocol from CN IP:

    # 1. WireGuard (should fail ~80% of time)
    wg-quick up wg0  # Should timeout or block

    # 2. Shadowsocks (should succeed >80% of time)
    sslocal -c ss_config.json  # Should connect

    # 3. obfs4 (should succeed >90% of time)
    obfs4proxy -client -target <server> # Should connect

    # Measure latency and packet loss
    ping -c 100 vpn-server.com | grep -E "(min|avg|max|loss)"
    ```
  - **Success criteria:**
    - [ ] Shadowsocks success rate >80%
    - [ ] obfs4 success rate >90%
    - [ ] Latency <200ms (95th percentile)
    - [ ] Connection stable for >1 hour
    - [ ] Speed: >10 Mbps (domestic) / >5 Mbps (international)
  - **Document:** `docs/china/protocol_test_results.md`

---

### 2.2 BACKUP DOMAINS & RESILIENCE

**Goal:** If primary domain blocked, DNS/HTTP traffic fails over to backup domain. Target: Never lose >2 domains at once.

**File References:** `bot/bot/config/settings.py`, ISSUE #502

- [ ] **Register 5+ backup domains** (ISSUE #502, 1h ops task)
  - **Primary (existing):** vpnhub.com
  - **Backups to register:**
    - vpnhub.org (Generic)
    - vpnhub.io (Tech-friendly)
    - vpnhub.net (Mirror)
    - vpnhub.co (Short)
    - startv.com (Decoy - different brand)
    - protectvpn.org (Alt brand)
  - **Commands:**
    ```bash
    # Register with registrar (Namecheap, GoDaddy, etc)
    # Setup: All point to same API endpoint via DNS round-robin

    # Verify:
    nslookup vpnhub.com
    nslookup vpnhub.org
    nslookup vpnhub.io
    # All should resolve to same IP (or load balanced IPs)
    ```
  - **Cost:** ~$12/year per domain

- [ ] **Configure DNS load balancing** (ISSUE #502, 2h)
  - **File:** DNS provider (e.g., CloudFlare)
  - **Setup:**
    ```
    vpnhub.com    → A Record → 203.0.113.1 (primary)
    vpnhub.org    → CNAME   → vpnhub-lb.cloudflare.net
    vpnhub.io     → CNAME   → vpnhub-lb.cloudflare.net
    vpnhub.net    → CNAME   → vpnhub-lb.cloudflare.net
    vpnhub.co     → CNAME   → vpnhub-lb.cloudflare.net

    # Round-robin all to load balancer
    # Geo-routing: China → different edge location
    ```
  - **Verify:**
    ```bash
    # Test DNS resolution from different locations
    nslookup vpnhub.org 8.8.8.8
    # Should resolve within 100ms

    # Test from China IP (if possible)
    nslookup vpnhub.org 114.114.114.114
    # Should still resolve
    ```

- [ ] **Implement client-side domain rotation** (ISSUE #502, 2h)
  - **File:** `bot/bot/service/api/client.py` (modified)
  - **Logic:** Try domains in order, rotate on failure, exponential backoff
  - **Implement:**
    ```python
    class DomainRotatingClient:
        """API client that rotates through backup domains on failure."""

        DOMAINS = [
            "vpnhub.com",   # Primary
            "vpnhub.io",    # Backup 1
            "vpnhub.org",   # Backup 2
            "vpnhub.net",   # Backup 3
            "vpnhub.co",    # Backup 4
        ]

        DEFAULT_TIMEOUT = 10  # seconds

        def __init__(self):
            self.current_domain_idx = 0
            self.failed_domains = {}  # domain → timestamp last failed
            self.session = None

        async def get_api_url(self) -> str:
            """Select domain, preferring previously working ones."""

            # Skip recently failed domains
            now = time.time()
            available = [
                d for d in self.DOMAINS
                if d not in self.failed_domains or (now - self.failed_domains[d]) > 300
            ]

            if not available:
                # All failed recently, try again anyway
                available = self.DOMAINS
                self.failed_domains.clear()

            domain = available[self.current_domain_idx % len(available)]
            return f"https://{domain}/api/v1"

        async def request(self, method: str, endpoint: str, **kwargs) -> dict:
            """Make API call with domain rotation on failure."""

            max_retries = len(self.DOMAINS)
            last_error = None

            for attempt in range(max_retries):
                try:
                    url = await self.get_api_url()
                    full_url = f"{url}{endpoint}"

                    async with aiohttp.ClientSession() as session:
                        async with session.request(
                            method,
                            full_url,
                            timeout=self.DEFAULT_TIMEOUT,
                            **kwargs
                        ) as resp:
                            if resp.status == 200:
                                return await resp.json()
                            else:
                                raise Exception(f"HTTP {resp.status}")

                except Exception as e:
                    last_error = e
                    domain = self.DOMAINS[self.current_domain_idx % len(self.DOMAINS)]
                    self.failed_domains[domain] = time.time()
                    self.current_domain_idx = (self.current_domain_idx + 1) % len(self.DOMAINS)

                    logger.warning(
                        f"event=domain.failover "
                        f"failed_domain={domain} "
                        f"attempt={attempt+1}/{max_retries} "
                        f"error={str(e)}"
                    )

                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)

            raise Exception(f"All domains failed. Last error: {last_error}")
    ```
  - **Verify:**
    ```bash
    # Test domain rotation
    python -c "
    from bot.bot.service.api.client import DomainRotatingClient
    client = DomainRotatingClient()

    # Simulate first domain failure
    client.failed_domains['vpnhub.com'] = time.time()

    # Should use vpnhub.io
    url = asyncio.run(client.get_api_url())
    print('Selected domain:', url)
    # Expected: https://vpnhub.io/api/v1
    "
    ```

- [ ] **Setup domain fronting (optional, advanced)** (ISSUE #502, 4h)
  - **What:** Hide traffic as HTTPS to CDN (appears as normal CloudFlare traffic to GFW)
  - **File:** `bot/bot/service/api/client.py` (domain_fronting branch)
  - **How it works:**
    ```
    Client → HTTPS to cdn.cloudflare.com (SNI header hides true target)
     ↓ (GFW sees: normal CDN request)
    Load balancer rewrites Host header to vpnhub.com
     ↓
    VPNHub backend responds
    ```
  - **Implementation sketch:**
    ```python
    async def request_with_domain_fronting(self, endpoint: str) -> dict:
        """Use domain fronting to hide VPN connection."""

        # Set domain fronting hostname
        real_domain = "vpnhub.com"
        front_domain = "cdn.cloudflare.com"  # Public CDN, won't be blocked

        headers = {
            "Host": real_domain,  # Hidden from GFW
        }

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            # Connect to front domain, but appear as real domain
            async with session.request(
                "GET",
                f"https://{front_domain}{endpoint}",
                headers=headers,
                ssl=False
            ) as resp:
                return await resp.json()
    ```
  - **Complexity:** Requires coordination with edge proxy
  - **Status:** Conditional on load testing and GFW behavior analysis

- [ ] **Test domain resilience from mainland China** (ISSUE #502, 2h)
  - **Setup:** Mainland CN IP or GFW simulator
  - **Test plan:**
    ```bash
    # Assume vpnhub.com is blocked

    # Test primary fails, backup succeeds
    curl -v https://vpnhub.com/api/health
    # Should fail (blocked by GFW)

    curl -v https://vpnhub.io/api/health
    # Should succeed (not yet blocked)

    # Client should automatically rotate
    # Check logs: event=domain.failover → fallback to vpnhub.io
    ```
  - **Success criteria:**
    - [ ] At least 2 backup domains succeed when primary blocked
    - [ ] Client-side rotation automatic (no user intervention)
    - [ ] Failover latency <5 seconds
    - [ ] No data loss during failover
  - **Document:** `docs/china/domain_resilience_test.md`

---

### 2.3 CHINA-SPECIFIC SERVER DEPLOYMENT (OPTIONAL)

**Goal:** Host server in or near China for lower latency. Target: <100ms latency from mainland CN.

**File References:** `docker-compose.yml` (server config), ISSUE #501/#502

- [ ] **Research China hosting options**
  - **Problem:** AWS, Azure, DigitalOcean blocked in China
  - **Options:**
    - [ ] Tencent Cloud (China local, fastest)
    - [ ] Alibaba Cloud (China local, fastest)
    - [ ] Hong Kong servers (40-80ms latency)
    - [ ] Singapore servers (60-120ms latency)
  - **Note:** Requires business registration for Tencent/Alibaba
  - **Alternative:** Use existing non-CN servers, optimize protocol (shadowsocks is fast enough)

- [ ] **Deploy to HK/SG if needed** (ISSUE #501, 4h)
  - **If CN latency consistently >200ms, deploy HK/SG mirror**
  - **Setup:**
    - [ ] New VPS: DigitalOcean SG or Vultr HK
    - [ ] Same app, same database (or geo-replicated)
    - [ ] Same backup domains point to both
  - **Cost:** $5-10/month extra
  - **Verify:** Latency <150ms from mainland CN

---

### 2.4 LOCALIZATION FOR CHINA MARKET

**Goal:** Make app accessible to Chinese users. Target: Full RU/EN/CN support.

**File References:** `bot/bot/locales/` (translation files), ISSUE #401 (UX)

- [ ] **Create Chinese locale**
  - **File:** `bot/bot/locales/zh_CN.json` (create new)
  - **Content:** Translate all user-facing messages to Simplified Chinese
  - **Commands:**
    ```bash
    # Extract all strings needing translation
    grep -r "await.*message.answer" bot/bot/handlers/ | wc -l
    # Should be ~50-100 unique messages

    # Create translation file with all messages
    # Format: {"key": "中文文本"}
    ```
  - **Reference:** Use existing `ru.json` and `en.json` as template

- [ ] **Implement locale selection**
  - **File:** `bot/bot/middlewares/locale.py` (modified)
  - **Logic:**
    - [ ] Auto-detect from Telegram language setting
    - [ ] CN/Hong Kong/Taiwan → Chinese locale
    - [ ] Allow manual override in settings
  - **Verify:**
    ```bash
    # Test with Chinese Telegram client
    # Should automatically use CN locale
    # Check logs: locale=zh_CN
    ```

- [ ] **Localize payment/legal copy**
  - [ ] Payment methods in CNY (if hosting in CN)
  - [ ] Legal terms in Chinese
  - [ ] Support in Chinese (hiring needed)

---

**CHECKLIST 2 COMPLETION CRITERIA**

- [ ] Shadowsocks + obfs4 protocols implemented and accessible
- [ ] >80% connection success rate from mainland CN (tested)
- [ ] Latency <200ms (95th percentile) from CN
- [ ] 5+ backup domains registered and functional
- [ ] Client-side domain rotation automatic
- [ ] No increase in support tickets after China launch
- [ ] Revenue from China users tracked separately (success metric)
- [ ] Team trained on China-specific troubleshooting

---

---

## CHECKLIST 3: AUTO-FAILOVER & RESILIENCE IMPLEMENTATION

**Linked Issues:** #301 (Server Health), #302 (Key Reassignment)
**Epic:** 3 — Auto-Failover & Resilience
**Success Metric:** Uptime 95% → 99.5%, incident MTTR from 30 min → 30 sec

---

### 3.1 SERVER HEALTH MONITORING

**Goal:** Detect unhealthy servers automatically and remove them from user key assignments.

**File References:** `bot/bot/misc/server_health_check.py` (to be created), ISSUE #301

- [ ] **Design health check protocol** (ISSUE #301, 1h)
  - **Metrics to check:**
    - [ ] Ping (ICMP) — Is server reachable?
    - [ ] Port connectivity (TCP/UDP) — Is VPN port open?
    - [ ] Latency — How slow is response?
    - [ ] Packet loss — Are packets being dropped?
    - [ ] Resource utilization — CPU, Memory, Disk?
  - **Decision tree:**
    ```
    CHECK server:
      - PING fails × 3 → OFFLINE (mark unhealthy)
      - Latency > 5s → DEGRADED (warn)
      - Packet loss > 20% → DEGRADED (warn)
      - CPU > 90% × 5 min → DEGRADED (warn)
      - Storage > 90% → WARN (no removal yet)
      - Consecutive failures × 3 → UNHEALTHY (remove)

    Duration in DEGRADED → Auto-remove if >30 min
    Duration in OFFLINE → Auto-remove after 30 sec
    ```

- [ ] **Implement health check service** (ISSUE #301, 3h)
  - **File:** `bot/bot/misc/server_health_check.py` (create new)
  - **Class:**
    ```python
    import asyncio
    import time
    from dataclasses import dataclass
    from typing import Dict

    @dataclass
    class ServerHealthStatus:
        server_id: str
        is_healthy: bool
        last_check: float
        consecutive_failures: int
        latency_ms: float
        packet_loss_pct: float
        reason: str  # "offline", "high_latency", etc.

    class ServerHealthMonitor:
        """Monitor VPN server health and auto-remove unhealthy ones."""

        def __init__(self, check_interval_sec: int = 10):
            self.check_interval = check_interval_sec
            self.server_statuses: Dict[str, ServerHealthStatus] = {}
            self.is_running = False

        async def check_server(self, server_id: str, endpoint: str) -> ServerHealthStatus:
            """Check single server health."""

            try:
                # 1. Ping
                ping_result = await self._ping(endpoint, timeout=5)
                if not ping_result["reachable"]:
                    return ServerHealthStatus(
                        server_id=server_id,
                        is_healthy=False,
                        last_check=time.time(),
                        consecutive_failures=self.server_statuses.get(server_id).consecutive_failures + 1
                            if server_id in self.server_statuses else 1,
                        latency_ms=999,
                        packet_loss_pct=100,
                        reason="offline"
                    )

                latency_ms = ping_result["latency_ms"]
                packet_loss_pct = ping_result["packet_loss_pct"]

                # 2. Evaluate health
                is_healthy = latency_ms < 5000 and packet_loss_pct < 20
                reason = ""
                if latency_ms >= 5000:
                    reason = "high_latency"
                if packet_loss_pct >= 20:
                    reason = "packet_loss" if not reason else f"{reason}+packet_loss"

                return ServerHealthStatus(
                    server_id=server_id,
                    is_healthy=is_healthy,
                    last_check=time.time(),
                    consecutive_failures=0 if is_healthy else
                        (self.server_statuses.get(server_id).consecutive_failures + 1
                         if server_id in self.server_statuses else 1),
                    latency_ms=latency_ms,
                    packet_loss_pct=packet_loss_pct,
                    reason=reason
                )

            except Exception as e:
                return ServerHealthStatus(
                    server_id=server_id,
                    is_healthy=False,
                    last_check=time.time(),
                    consecutive_failures=self.server_statuses.get(server_id).consecutive_failures + 1
                        if server_id in self.server_statuses else 1,
                    latency_ms=999,
                    packet_loss_pct=100,
                    reason=f"check_error: {str(e)}"
                )

        async def _ping(self, endpoint: str, timeout: int = 5) -> dict:
            """Ping server and measure latency."""
            host = endpoint.split(':')[0]
            try:
                start = time.perf_counter()
                # Use ICMP ping
                proc = await asyncio.create_subprocess_exec(
                    "ping", "-c", "3", "-W", str(timeout * 1000), host,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)

                # Parse ping output
                output = stdout.decode()
                if "0 packets transmitted" in output or "100% packet loss" in output:
                    return {"reachable": False, "latency_ms": 999, "packet_loss_pct": 100}

                # Extract packet loss
                import re
                loss_match = re.search(r'(\d+)% packet loss', output)
                loss_pct = float(loss_match.group(1)) if loss_match else 0

                # Extract latency (min/avg/max/stddev).
                latency_match = re.search(r'min/avg/max/stddev = ([\d.]+)/([\d.]+)', output)
                avg_latency = float(latency_match.group(2)) if latency_match else 999

                return {
                    "reachable": True,
                    "latency_ms": avg_latency,
                    "packet_loss_pct": loss_pct
                }

            except Exception as e:
                logger.error(f"Ping failed for {host}: {e}")
                return {"reachable": False, "latency_ms": 999, "packet_loss_pct": 100}

        async def start_monitoring(self, servers: list):
            """Continuously monitor all servers."""
            self.is_running = True

            while self.is_running:
                for server in servers:
                    status = await self.check_server(server.id, server.endpoint)
                    self.server_statuses[server.id] = status

                    logger.info(
                        f"event=health.check "
                        f"server_id={server.id} "
                        f"is_healthy={status.is_healthy} "
                        f"latency_ms={status.latency_ms} "
                        f"packet_loss={status.packet_loss_pct}% "
                        f"consecutive_failures={status.consecutive_failures}"
                    )

                    # Auto-remove if too many failures
                    if status.consecutive_failures >= 3:
                        await self.mark_server_unhealthy(server.id, status.reason)

                await asyncio.sleep(self.check_interval)

        async def mark_server_unhealthy(self, server_id: str, reason: str):
            """Remove server from DNS/load balancer."""
            logger.warning(
                f"event=server.unhealthy "
                f"server_id={server_id} "
                f"reason={reason}"
            )

            # Publish NATS event for downstream systems
            await self.nats_client.publish(
                "vpnhub.server.unhealthy",
                json.dumps({"server_id": server_id, "reason": reason}).encode()
            )

            # Remove from load balancer (calls ops API)
            # This triggers auto-reassignment of user keys

        async def stop_monitoring(self):
            """Stop health checking."""
            self.is_running = False
    ```
  - **Verify:**
    ```bash
    # Test health check
    python -c "
    import asyncio
    from bot.bot.misc.server_health_check import ServerHealthMonitor

    monitor = ServerHealthMonitor()
    status = asyncio.run(monitor.check_server('server-1', '1.2.3.4:1194'))
    print(f'Server healthy: {status.is_healthy}')
    print(f'Latency: {status.latency_ms}ms')
    print(f'Packet loss: {status.packet_loss_pct}%')
    "
    ```

- [ ] **Integrate health monitor into bot startup** (ISSUE #301, 2h)
  - **File:** `bot/bot/main.py:180-200` (modified to add health monitor)
  - **Add initialization:**
    ```python
    async def startup(bot: Bot, dp: Dispatcher):
        """Bot startup tasks."""

        # ... existing startup code ...

        # Start health monitoring
        monitor = ServerHealthMonitor(check_interval_sec=10)
        all_servers = await db_session.execute(select(VPNServer).where(VPNServer.is_active == True))
        servers = all_servers.scalars().all()

        health_check_task = asyncio.create_task(
            monitor.start_monitoring(servers)
        )

        # Store in app state for shutdown cleanup
        dp.storage["health_monitor"] = monitor
        dp.storage["health_check_task"] = health_check_task

        logger.info("Server health monitor started")

    async def shutdown(bot: Bot, dp: Dispatcher):
        """Bot shutdown tasks."""

        monitor = dp.storage.get("health_monitor")
        if monitor:
            await monitor.stop_monitoring()

        logger.info("Server health monitor stopped")
    ```
  - **Verify:**
    ```bash
    # Start bot, check logs
    docker compose up vpn_hub_bot

    # Should see: "Server health monitor started"
    # Every 10 seconds: "event=health.check server_id=... is_healthy=..."
    docker compose logs vpn_hub_bot | grep "health.check"
    ```

---

### 3.2 AUTOMATIC KEY REASSIGNMENT

**Goal:** When server fails, move user's keys to healthy servers automatically. Target: <10 seconds reassignment time.

**File References:** `bot/bot/misc/key_reassignment.py` (to be created), ISSUE #302

- [ ] **Implement reassignment logic** (ISSUE #302, 2h)
  - **File:** `bot/bot/misc/key_reassignment.py` (create new)
  - **Class:**
    ```python
    class KeyReassignmentService:
        """Automatically reassign VPN keys when server fails."""

        async def reassign_keys_from_unhealthy_server(
            self,
            server_id: str,
            db_session: AsyncSession
        ):
            """Find all users with keys on unhealthy server, reassign them."""

            logger.info(f"event=reassign.start server_id={server_id}")

            # 1. Find all active keys on unhealthy server
            unhealthy_keys = await db_session.execute(
                select(VPNKey).where(
                    (VPNKey.server_id == server_id) &
                    (VPNKey.is_active == True) &
                    (VPNKey.expires_at > datetime.utcnow())
                )
            )
            keys_to_reassign = unhealthy_keys.scalars().all()

            logger.info(f"Found {len(keys_to_reassign)} keys to reassign")

            reassigned = 0
            failed = 0

            for key in keys_to_reassign:
                try:
                    # 2. Find user and their plan
                    user = await db_session.get(User, key.user_id)

                    # 3. Select best healthy server
                    # Prefer same country for latency
                    best_server = await self._select_best_healthy_server(
                        current_server_id=server_id,
                        user_country=user.detected_country,
                        db_session=db_session
                    )

                    if not best_server:
                        logger.error(f"No healthy servers available for reassignment")
                        failed += 1
                        continue

                    # 4. Generate new key on healthy server
                    new_key = await self._generate_key_on_server(
                        user=user,
                        server=best_server,
                        expiry_date=key.expires_at
                    )

                    # 5. Deactivate old key (keep record for audit)
                    key.is_active = False
                    key.deactivated_reason = f"Server {server_id} marked unhealthy, reassigned to {best_server.id}"

                    # 6. Add new key to DB
                    db_session.add(new_key)
                    await db_session.commit()

                    # 7. Notify user
                    await self._notify_user_reassignment(
                        user=user,
                        old_server=server_id,
                        new_server=best_server.id,
                        new_key=new_key
                    )

                    logger.info(
                        f"event=reassign.success "
                        f"user_id={user.id} "
                        f"old_server={server_id} "
                        f"new_server={best_server.id} "
                        f"new_key_id={new_key.id}"
                    )
                    reassigned += 1

                except Exception as e:
                    logger.error(
                        f"event=reassign.error "
                        f"key_id={key.id} "
                        f"error={str(e)}"
                    )
                    failed += 1

            logger.info(
                f"event=reassign.complete "
                f"total={len(keys_to_reassign)} "
                f"reassigned={reassigned} "
                f"failed={failed}"
            )

            return {"reassigned": reassigned, "failed": failed}

        async def _select_best_healthy_server(
            self,
            current_server_id: str,
            user_country: str,
            db_session: AsyncSession
        ):
            """Select healthiest server, preferring same country."""

            # Get all healthy servers
            healthy_servers = await db_session.execute(
                select(VPNServer).where(
                    (VPNServer.is_active == True) &
                    (VPNServer.id != current_server_id)
                )
            )
            servers = healthy_servers.scalars().all()

            if not servers:
                return None

            # Rank by: (1) Same country, (2) Load, (3) Random
            def rank_server(server):
                same_country = -1000 if server.country == user_country else 0
                load_penalty = server.active_connections * 10
                return same_country - load_penalty

            best = max(servers, key=rank_server)
            return best

        async def _notify_user_reassignment(
            self,
            user: User,
            old_server: str,
            new_server: str,
            new_key: VPNKey
        ):
            """Send in-app notification to user."""

            message = (
                f"🔄 **VPN Moved to Faster Server**\n\n"
                f"Old server was overloaded. We moved you to:\n"
                f"📍 {new_server}\n"
                f"New speed available!\n\n"
                f"No action needed, you're ready to reconnect.\n\n"
                f"New key: `{new_key.key_string[:20]}...`"
            )

            try:
                await self.bot.send_message(user.tgid, message)
            except Exception as e:
                logger.error(f"Failed to notify user {user.id}: {e}")
    ```
  - **Verify:**
    ```bash
    # Test reassignment logic
    python -c "
    import asyncio
    from bot.bot.misc.key_reassignment import KeyReassignmentService

    service = KeyReassignmentService()
    result = asyncio.run(
        service.reassign_keys_from_unhealthy_server(
            server_id='server-1-broken',
            db_session=session
        )
    )
    print(f'Reassigned: {result[\"reassigned\"]}, Failed: {result[\"failed\"]}')
    "
    ```

- [ ] **Hook reassignment to health monitor** (ISSUE #302, 1h)
  - **File:** `bot/bot/misc/server_health_check.py` (modified)
  - **Update `mark_server_unhealthy` method:**
    ```python
    async def mark_server_unhealthy(self, server_id: str, reason: str):
        """Remove server and reassign keys."""

        logger.warning(f"event=server.unhealthy server_id={server_id} reason={reason}")

        # Publish event
        await self.nats_client.publish(
            "vpnhub.server.unhealthy",
            json.dumps({"server_id": server_id, "reason": reason}).encode()
        )

        # NEW: Trigger reassignment
        reassignment_service = KeyReassignmentService(bot=self.bot, nats=self.nats_client)
        result = await reassignment_service.reassign_keys_from_unhealthy_server(
            server_id=server_id,
            db_session=self.db_session
        )

        logger.info(
            f"event=server.unhealthy_reassignment "
            f"server_id={server_id} "
            f"reassigned={result['reassigned']} "
            f"failed={result['failed']}"
        )
    ```

- [ ] **Test failover scenario** (ISSUE #302, 2h)
  - **Setup:**
    - [ ] Create 2+ test servers (or use sandbox)
    - [ ] Create test user with key on server-1
    - [ ] Simulate server-1 failure (block network)
    - [ ] Verify key automatically moved to server-2
    - [ ] Verify user notified
  - **Test steps:**
    ```bash
    # 1. Verify user has key on server-1
    psql -c "SELECT * FROM keys WHERE user_id=123;"
    # Expected: server_id=server-1

    # 2. Simulate server failure (drop firewall, or mark unhealthy manually)
    # ... make server-1 unreachable ...

    # 3. Trigger health check
    # Function will detect failure within 10 seconds

    # 4. Verify reassignment happened
    sleep 15
    psql -c "SELECT * FROM keys WHERE user_id=123 AND is_active=true;"
    # Expected: server_id=server-2

    # 5. Verify user got notification
    docker compose logs vpn_hub_bot | grep "VPN Moved to Faster Server"
    ```
  - **Success criteria:**
    - [ ] Reassignment completes in <10 seconds from failure detection
    - [ ] User receives clear notification message
    - [ ] New key works immediately
    - [ ] No data loss in key transfer
  - **Document:** `docs/ops/failover_test_results.md`

---

### 3.3 GRACEFUL DEGRADATION

**Goal:** System continues serving users even if one component partially fails.

**File References:** `bot/bot/main.py`, `bot/webhooks/base.py`

- [ ] **Implement circuit breaker pattern** (ISSUE #301, 2h)
  - **File:** `bot/bot/misc/circuit_breaker.py` (create new)
  - **Purpose:** If one service fails (e.g., payment provider), don't crash entire bot
  - **Implement:**
    ```python
    class CircuitBreaker:
        """Circuit breaker: detect failures, prevent cascading."""

        STATES = {"closed": 0, "open": 1, "half_open": 2}

        def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
            self.failure_count = 0
            self.failure_threshold = failure_threshold
            self.reset_timeout = reset_timeout
            self.last_failure_time = None
            self.state = "closed"

        async def call(self, func, *args, **kwargs):
            """Execute function with circuit breaker protection."""

            if self.state == "open":
                if time.time() - self.last_failure_time > self.reset_timeout:
                    self.state = "half_open"
                    logger.info(f"event=circuit_breaker state=half_open")
                else:
                    raise Exception(f"Circuit open, retry in {self.reset_timeout}s")

            try:
                result = await func(*args, **kwargs)
                if self.state == "half_open":
                    self.state = "closed"
                    self.failure_count = 0
                    logger.info(f"event=circuit_breaker state=closed")
                return result

            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.error(
                        f"event=circuit_breaker "
                        f"state=open "
                        f"failures={self.failure_count} "
                        f"threshold={self.failure_threshold}"
                    )

                raise
    ```
  - **Verify:**
    ```bash
    # Test circuit breaker
    python -c "
    import asyncio
    from bot.bot.misc.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(failure_threshold=3)

    # Failing function
    async def failing_func():
        raise Exception('Service down')

    # Call fails 3 times
    for i in range(3):
        try:
            asyncio.run(cb.call(failing_func))
        except: pass

    # 4th call should be blocked immediately
    try:
        asyncio.run(cb.call(failing_func))
    except Exception as e:
        print(f'Circuit open: {e}')
    "
    ```

- [ ] **Add fallback handlers**
  - **Payment fallback:** Show "Payment temporarily unavailable, try later" instead of crashing
  - **Database fallback:** Cache recent responses if DB is slow
  - **File:** `bot/bot/handlers/user/payment.py`, `bot/bot/database/cache.py`

---

**CHECKLIST 3 COMPLETION CRITERIA**

- [ ] Health check service running, monitoring all servers every 10 seconds
- [ ] Unhealthy server detected and automatically removed
- [ ] User keys automatically reassigned within 10 seconds of server failure
- [ ] Users notified of reassignment
- [ ] Failover tested end-to-end with simulated server failure
- [ ] Uptime metrics tracked: 99.5%+ target achieved in staging
- [ ] Zero data loss during failover (verified with database audit)
- [ ] Circuit breaker prevents cascading failures

---

---

## CHECKLIST 4: OBSERVABILITY & MONITORING IMPLEMENTATION

**Linked Issues:** #102 (Health Endpoint), #201 (Prometheus), #202 (DB Logging)
**Epic:** 2 — Observability & Monitoring
**Success Metric:** <1 minute MTTR (Mean Time To Repair), 100% visibility into system state

---

### 4.1 /HEALTH ENDPOINT IMPLEMENTATION

**Goal:** Single endpoint that tells Kubernetes (or any load balancer) if bot is healthy. Returns 200 only if all dependencies OK.

**File References:** `bot/webhooks/base.py`, ISSUE #102

- [ ] **Implement /health endpoint** (ISSUE #102, 1h)
  - **File:** `bot/webhooks/base.py:100-150`
  - **Code:**
    ```python
    from datetime import datetime
    from sqlalchemy import select, text

    @app.get("/health", tags=["health"])
    async def health_check(request: Request):
        """
        Health check for load balancer / Kubernetes probes.
        Returns 200 if all healthy, 503 if any service down.
        """

        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }

        try:
            # 1. Check Database
            async with app.state.session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                # Measure latency
                db_start = time.perf_counter()
                await session.execute(text("SELECT 1"))
                db_latency_ms = (time.perf_counter() - db_start) * 1000

            health_status["services"]["database"] = {
                "status": "ok",
                "latency_ms": db_latency_ms
            }

        except Exception as e:
            health_status["services"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"

        try:
            # 2. Check NATS (if connected)
            if hasattr(app.state, 'nats_client') and app.state.nats_client:
                nats_start = time.perf_counter()
                await app.state.nats_client.publish("vpnhub.health_check", b"ping")
                nats_latency_ms = (time.perf_counter() - nats_start) * 1000

                health_status["services"]["nats"] = {
                    "status": "ok",
                    "latency_ms": nats_latency_ms
                }

        except Exception as e:
            health_status["services"]["nats"] = {
                "status": "error",
                "error": str(e)
            }
            # NATS down is WARNING, not CRITICAL
            logger.warning(f"NATS health check failed: {e}")

        try:
            # 3. Check Redis (if configured)
            if hasattr(app.state, 'redis_client') and app.state.redis_client:
                redis_start = time.perf_counter()
                await app.state.redis_client.ping()
                redis_latency_ms = (time.perf_counter() - redis_start) * 1000

                health_status["services"]["redis"] = {
                    "status": "ok",
                    "latency_ms": redis_latency_ms
                }

        except Exception as e:
            health_status["services"]["redis"] = {
                "status": "error",
                "error": str(e)
            }

        # Return appropriate status code
        status_code = 200 if health_status["status"] == "healthy" else 503

        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
    ```
  - **Verify:**
    ```bash
    # Test endpoint
    curl -v http://localhost:8888/health

    # Expected (healthy):
    # HTTP/1.1 200 OK
    # {"status": "healthy", "timestamp": "...", "services": {"database": {"status": "ok", "latency_ms": 2.3}, ...}}

    # If DB down:
    # HTTP/1.1 503 Service Unavailable
    # {"status": "unhealthy", "services": {"database": {"status": "error", "error": "..."}}}
    ```

- [ ] **Update Docker healthcheck** (ISSUE #102, 0.5h)
  - **File:** `docker-compose.yml`
  - **Modify:**
    ```yaml
    services:
      vpn_hub_bot:
        # ... existing config ...

        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8888/health"]
          interval: 30s
          timeout: 5s
          retries: 3
          start_period: 10s
    ```
  - **Verify:**
    ```bash
    # Start container
    docker compose up vpn_hub_bot

    # Check health status (after ~15 seconds)
    docker ps --format "table {{.Names}}\t{{.Status}}"
    # Expected: vpn_hub_bot ... (healthy)
    ```

- [ ] **Add detailed health checks to Kubernetes** (optional)
  - **File:** `k8s/deployment.yaml` (if deploying to K8s)
  - **Config:**
    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: vpn-hub-bot
    spec:
      template:
        spec:
          containers:
          - name: vpn-hub-bot
            image: vpnhub-bot:latest
            ports:
            - containerPort: 8888

            livenessProbe:
              httpGet:
                path: /health
                port: 8888
              initialDelaySeconds: 30
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3

            readinessProbe:
              httpGet:
                path: /health
                port: 8888
              initialDelaySeconds: 10
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 2
    ```

---

### 4.2 STRUCTURED LOGGING IMPLEMENTATION

**Goal:** All database operations, errors, and events logged in structured format for easy search and analysis.

**File References:** `bot/bot/database/methods/`, `TECHNICAL_ROADMAP_2026.md` (Issue #202)

- [ ] **Add logging to database methods** (ISSUE #202, 10-12h total)
  - **Pattern:** All `get_user`, `insert_key`, `update_subscription` calls log with structured format
  - **File:** `bot/bot/database/methods/get.py:1-50`
  - **Before:**
    ```python
    async def get_user(session, tgid: int):
        result = await session.execute(
            select(User).where(User.tgid == tgid)
        )
        return result.scalar()
    ```
  - **After:**
    ```python
    import logging
    import time

    log = logging.getLogger(__name__)

    async def get_user(session, tgid: int):
        start = time.perf_counter()
        try:
            log.debug("event=db.query table=users operation=select tgid=%s", tgid)

            result = await session.execute(
                select(User).where(User.tgid == tgid)
            )
            user = result.scalar()

            duration_ms = (time.perf_counter() - start) * 1000

            if user:
                if duration_ms > 100:
                    log.warning(
                        "event=db.slow_query table=users duration_ms=%.1f tgid=%s",
                        duration_ms, tgid
                    )
                else:
                    log.debug(
                        "event=db.query_ok table=users duration_ms=%.1f tgid=%s",
                        duration_ms, tgid
                    )
            else:
                log.debug("event=db.query_no_result table=users tgid=%s", tgid)

            return user

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            log.error(
                "event=db.error table=users operation=select tgid=%s duration_ms=%.1f error=%s",
                tgid, duration_ms, str(e),
                exc_info=e
            )
            raise
    ```

- [ ] **Add logging to all CRUD operations**
  - **File:** `bot/bot/database/methods/insert.py` (2.5h)
    - Log: insert started, rows_affected, duration, any constraint violations
  - **File:** `bot/bot/database/methods/update.py` (2.5h)
    - Log: update started, affected row count, old/new values (for sensitive data: hash only)
  - **File:** `bot/bot/database/methods/delete.py` (2.5h)
    - Log: delete started, affected row count, cascade info

- [ ] **Configure log aggregation**
  - **File:** `docker-compose.yml` (add logging driver)
  - **Config:**
    ```yaml
    services:
      vpn_hub_bot:
        logging:
          driver: "json-file"
          options:
            max-size: "100m"
            max-file: "5"
    ```
  - **Query logs:**
    ```bash
    # Find slow queries
    docker compose logs vpn_hub_bot | grep "event=db.slow_query" | head -10

    # Count errors by table
    docker compose logs vpn_hub_bot | grep "event=db.error" | \
      sed -E 's/.*table=([^ ]+).*/\1/' | sort | uniq -c
    ```

- [ ] **Test logging**
  - [ ] Trigger normal query → verify debug log appears
  - [ ] Trigger slow query (>100ms) → verify warning log appears
  - [ ] Trigger error (constraint violation) → verify error log with exc_info
  - **Document:** `docs/ops/logging_guide.md`

---

### 4.3 PROMETHEUS METRICS & GRAFANA DASHBOARDS

**Goal:** Real-time visibility into system health. Measure CPU, memory, requests, errors, latency.

**File References:** `docker-compose.yml`, `prometheus/prometheus.yml` (to create), ISSUE #201

- [ ] **Add Prometheus service** (ISSUE #201, 1h)
  - **File:** `docker-compose.yml` (add service)
  - **Config:**
    ```yaml
    prometheus:
      image: prom/prometheus:latest
      container_name: vpnhub_prometheus
      ports:
        - "9090:9090"
      volumes:
        - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
        - prometheus_data:/prometheus
      command:
        - "--config.file=/etc/prometheus/prometheus.yml"
        - "--storage.tsdb.path=/prometheus"
        - "--storage.tsdb.retention.time=30d"

    grafana:
      image: grafana/grafana:latest
      container_name: vpnhub_grafana
      ports:
        - "3000:3000"
      environment:
        - GF_SECURITY_ADMIN_PASSWORD=admin
      volumes:
        - grafana_data:/var/lib/grafana
        - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
        - ./grafana/datasources:/etc/grafana/provisioning/datasources

    volumes:
      prometheus_data:
      grafana_data:
    ```

- [ ] **Configure Prometheus scrape targets** (ISSUE #201, 1h)
  - **File:** `prometheus/prometheus.yml` (create)
  - **Config:**
    ```yaml
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    scrape_configs:
      - job_name: 'vpn_hub_bot'
        static_configs:
          - targets: ['vpn_hub_bot:8888']
        metrics_path: '/metrics'

      - job_name: 'postgres'
        static_configs:
          - targets: ['db_postgres:5432']
        # Use postgres_exporter sidecar
```

- [ ] **Add /metrics endpoint to bot** (ISSUE #201, 2h)
  - **Library:** `prometheus-client` Python library
  - **File:** `bot/webhooks/base.py:200-250` (add endpoint)
  - **Code:**
    ```python
    from prometheus_client import Counter, Histogram, Gauge, generate_latest

    # Define metrics
    http_requests_total = Counter(
        'vpnhub_http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )

    http_request_duration_seconds = Histogram(
        'vpnhub_http_request_duration_seconds',
        'HTTP request latency',
        ['method', 'endpoint']
    )

    active_users = Gauge(
        'vpnhub_active_users',
        'Active connected users'
    )

    database_queries_total = Counter(
        'vpnhub_database_queries_total',
        'Database queries',
        ['table', 'operation']
    )

    # Endpoint
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return generate_latest()

    # Middleware to record request metrics
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        method = request.method
        endpoint = request.url.path

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

        return response
    ```
  - **Verify:**
    ```bash
    # Metrics should be available
    curl http://localhost:8888/metrics | head -20
    # Expected: Prometheus format output (TYPE, HELP, metrics)
    ```

- [ ] **Create Grafana dashboards** (ISSUE #201, 2h)
  - **File:** `grafana/dashboards/vpnhub-health.json` (create)
  - **Panels:**
    - [ ] Bot CPU usage (% or cores)
    - [ ] Bot memory usage (MB)
    - [ ] HTTP request rate (requests/sec)
    - [ ] HTTP error rate (errors/sec)
    - [ ] Database query latency (p50, p95, p99)
    - [ ] Active connected users
    - [ ] Disk usage on /backups
  - **Access:** http://localhost:3000 (login: admin/admin)

- [ ] **Setup alerting rules** (ISSUE #201, 2h)
  - **File:** `prometheus/alerts.yml` (create)
  - **Rules:**
    ```yaml
    groups:
      - name: vpnhub_alerts
        rules:
          - alert: BotHighCPU
            expr: rate(container_cpu_usage_seconds_total{name="vpn_hub_bot"}[5m]) > 0.8
            for: 5m
            annotations:
              summary: "Bot CPU > 80% for 5 minutes"

          - alert: BotHighMemory
            expr: container_memory_usage_bytes{name="vpn_hub_bot"} / 1024 / 1024 > 1800
            for: 5m
            annotations:
              summary: "Bot memory > 1.8GB"

          - alert: DatabaseSlow
            expr: histogram_quantile(0.95, vpnhub_database_query_duration_seconds) > 1
            for: 5m
            annotations:
              summary: "Database p95 latency > 1 second"

          - alert: HighErrorRate
            expr: rate(vpnhub_http_requests_total{status=~"5.."}[5m]) > 0.01
            for: 2m
            annotations:
              summary: "Error rate > 1% for 2 minutes"
    ```

---

### 4.4 DATABASE BACKUP & DISASTER RECOVERY

**Goal:** Automated daily backups with easy recovery. Target: RPO (Recovery Point Objective) <1 day, RTO <1 hour.

**File References:** `scripts/backup_db.sh`, ISSUE #105

- [ ] **Create backup script** (ISSUE #105, 1h)
  - **File:** `scripts/backup_db.sh` (create)
  - **Script:**
    ```bash
    #!/bin/bash
    # Backup VPNHub PostgreSQL database

    set -e

    # Config from .env
    POSTGRES_USER=${POSTGRES_USER:-postgres}
    POSTGRES_DB=${POSTGRES_DB:-vpnhub}
    BACKUP_DIR="./backups"

    # Create backup dir
    mkdir -p "$BACKUP_DIR"

    # Generate timestamped filename
    BACKUP_FILE="$BACKUP_DIR/vpnhub_$(date +%Y%m%d_%H%M%S).sql.gz"

    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting backup to $BACKUP_FILE"

    # Backup with docker compose
    docker compose exec -T db_postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

    # Verify backup
    if [ -f "$BACKUP_FILE" ]; then
        size_gb=$(du -sh "$BACKUP_FILE" | cut -f1)
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup complete: $size_gb"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Backup failed!"
        exit 1
    fi

    # Cleanup old backups (keep 30 days)
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Cleaning up old backups..."
    find "$BACKUP_DIR" -name "vpnhub_*.sql.gz" -mtime +30 -delete

    # Count remaining backups
    count=$(ls "$BACKUP_DIR"/vpnhub_*.sql.gz 2>/dev/null | wc -l)
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Retained $count backup files (30-day retention)"
    ```

- [ ] **Setup cron job** (ISSUE #105, 0.5h)
  - **Command:**
    ```bash
    # Edit crontab
    crontab -e

    # Add daily backup at 2 AM UTC
    0 2 * * * cd /opt/vpnhub && ./scripts/backup_db.sh >> /var/log/vpnhub_backup.log 2>&1
    ```
  - **Verify:**
    ```bash
    # Check crontab
    crontab -l | grep backup_db.sh

    # Check backup logs
    tail -f /var/log/vpnhub_backup.log
    ```

- [ ] **Test restore procedure** (ISSUE #105, 2h)
  - **Steps:**
    ```bash
    # 1. List available backups
    ls -lh backups/vpnhub_*.sql.gz

    # 2. Create fresh DB container
    docker compose down db_postgres
    docker volume rm vpnhub_db_data  # removes old data
    docker compose up -d db_postgres
    sleep 10

    # 3. Restore from latest backup
    gunzip < backups/vpnhub_latest.sql.gz | \
      docker compose exec -T db_postgres psql -U postgres vpnhub

    # 4. Verify data integrity
    docker compose exec db_postgres psql -U postgres vpnhub -c \
      "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM keys;"

    # Expected: Same counts as before backup
    ```
  - **Document:** `docs/ops/disaster_recovery.md`

- [ ] **Add to Makefile** (ISSUE #105, 0.5h)
  - **File:** `Makefile` (modify)
  - **Add targets:**
    ```makefile
    .PHONY: backup restore-backup backup-list

    backup:
        @./scripts/backup_db.sh

    backup-list:
        @ls -lh backups/vpnhub_*.sql.gz

    restore-backup:
        @echo "Restoring from latest backup..."
        @latest=$$(ls -t backups/vpnhub_*.sql.gz | head -1); \
        if [ -z "$$latest" ]; then echo "No backups found"; exit 1; fi; \
        gunzip < "$$latest" | docker compose exec -T db_postgres psql -U postgres vpnhub
        @echo "✅ Restore complete"
    ```
  - **Usage:**
    ```bash
    make backup          # Create backup now
    make backup-list     # List all backups
    make restore-backup  # Restore latest backup
    ```

---

**CHECKLIST 4 COMPLETION CRITERIA**

- [ ] /health endpoint returns 200 when all services OK, 503 when any service down
- [ ] Docker healthcheck configured and passing
- [ ] All database methods have structured logging (get, insert, update, delete)
- [ ] Slow queries (>100ms) logged with warnings
- [ ] Errors logged with full exception info
- [ ] Prometheus scraping metrics from bot every 15 seconds
- [ ] /metrics endpoint returns valid Prometheus format output
- [ ] Grafana accessible at http://localhost:3000
- [ ] Dashboards show: CPU, Memory, Request rate, Error rate, DB latency
- [ ] Alerting rules configured for High CPU, High Memory, Slow DB, High Error Rate
- [ ] Daily backups running automatically at 2 AM UTC
- [ ] Backups gzipped and timestamped
- [ ] 30-day retention policy enforced
- [ ] Restore test passed: data integrity verified
- [ ] make backup/restore-backup commands working
- [ ] Disaster recovery runbook documented

---

---

## CHECKLIST 5: AI AGENTS ACTIVATION IMPLEMENTATION

**Linked Issues:** #801 (QA Validation), #802 (A/B Experiments)
**Epic:** 8 — AI Agents Activation
**Success Metric:** Zero unhandled callbacks in CI/CD, 3+ A/B experiments running, +5-10% conversion lift

---

### 5.1 ENFORCE CALLBACK VALIDATION IN CI/CD

**Goal:** No PR can merge if new callbacks added but not handled. Automated check prevents dead UX flows.

**File References:** `scripts/qa/check_callbacks.py` (exists), `scripts/qa.sh` (exists), ISSUE #801

- [ ] **Review existing check_callbacks.py** (ISSUE #801, 0.5h)
  - **File:** `scripts/qa/check_callbacks.py`
  - **What it does:**
    - [ ] Parses all Python files in `bot/bot/handlers/`
    - [ ] Extracts all `callback_data` values from inline keyboards
    - [ ] Extracts all `@dp.callback_query()` handler decorators
    - [ ] Reports mismatches: (used but not handled) and (handled but not used)
  - **Test run:**
    ```bash
    python3 scripts/qa/check_callbacks.py --root bot/bot

    # Expected output:
    # Checking callbacks in bot/bot...
    # ✅ All callbacks handled
    # or
    # ❌ Unhandled callbacks:
    #   - vpn_connect_btn (used in handlers/user/main.py:45)
    #   - ...
    ```

- [ ] **Add check to qa.sh** (ISSUE #801, 0.5h)
  - **File:** `scripts/qa.sh` (verify it runs check_callbacks.py)
  - **Should contain:**
    ```bash
    if [[ -f scripts/qa/check_callbacks.py ]]; then
        echo "🔍 Checking callback coverage..."
        if ! python3 scripts/qa/check_callbacks.py --root bot/bot; then
            echo "❌ Callback validation failed"
            exit 4  # Exit code 4 = QA failure
        fi
    fi
    ```
  - **Run locally:**
    ```bash
    ./scripts/qa.sh
    # Should pass if all callbacks handled
    ```

- [ ] **Add to GitHub Actions** (ISSUE #801, 1h)
  - **File:** `.github/workflows/qa.yml` (create or modify)
  - **Workflow:**
    ```yaml
    name: QA & Validation

    on: [pull_request, push]

    jobs:
      callback-validation:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v3

          - name: Set up Python
            uses: actions/setup-python@v4
            with:
              python-version: '3.11'

          - name: Check callback coverage
            run: |
              python3 scripts/qa/check_callbacks.py --root bot/bot
            continue-on-error: false

          - name: Report
            if: failure()
            run: |
              echo "❌ PR has unhandled callbacks"
              echo "Review scripts/qa/callback_index.md for missing handlers"
              exit 1
    ```
  - **Verify:**
    - [ ] PR with unhandled callback fails CI
    - [ ] PR with all callbacks handled passes CI
    - [ ] Error messages are clear (point to exact issue)

- [ ] **Document callback naming conventions** (ISSUE #801, 1h)
  - **File:** `docs/CALLBACK_CONVENTIONS.md` (create)
  - **Content:**
    ```markdown
    # Callback Naming Conventions

    All callback_data values MUST follow naming patterns and be handled by @dp.callback_query() handlers.

    ## Pattern: {feature}_{action}_{variant}

    ### Examples:
    - `vpn_connect_btn` — User initiates VPN connection
    - `pay_stripe_monthly` — Payment with Stripe, monthly plan
    - `help_connection_troubleshoot` — Help for connection issues
    - `back_general_menu_btn` — Navigation back to main menu

    ## Required pattern parts:
    1. **feature** (required): What feature is this for? (vpn, pay, help, settings)
    2. **action** (required): What happens? (connect, select, open, back)
    3. **variant** (optional): If multiple variants, distinguish them (stripe, monthly, troubleshoot)

    ## Constraint: ALL callbacks MUST have handlers

    If you add a button with callback_data="my_button", you MUST:
    1. Create handler: `@dp.callback_query(Text("my_button"))`
    2. Implement logic in handler
    3. Run `python3 scripts/qa/check_callbacks.py --root bot/bot` to verify
    4. Submit PR (CI will check)

    If you forget, CI will REJECT the PR with: "❌ Unhandled callback: my_button"

    ## How to fix unhandled callbacks:

    1. Run: `python3 scripts/qa/check_callbacks.py --root bot/bot`
    2. Find line: "Unhandled callbacks: {list}"
    3. For each unhandled callback:
       - Either DELETE the button (if not needed)
       - Or CREATE a handler for it

    ## Examples of valid handlers:

    ```python
    @registered_router.callback_query(Text("vpn_connect_btn"))
    async def handle_vpn_connect(callback: CallbackQuery, state: FSMState):
        # ... implementation ...
        await callback.message.answer("Connecting...")

    @registered_router.callback_query(Text("back_general_menu_btn"))
    async def back_to_menu(callback: CallbackQuery):
        await show_main_menu(callback.message)
    ```
    ```

- [ ] **Test callback validation in real PR** (ISSUE #801, 1h)
  - **Steps:**
    - [ ] Add new button with unhandled callback
    - [ ] Push to feature branch
    - [ ] Create PR
    - [ ] Verify CI rejects with clear error
    - [ ] Add handler
    - [ ] Push fix
    - [ ] Verify CI accepts

---

### 5.2 RUN A/B EXPERIMENTS FOR CONVERSION

**Goal:** Test UX changes and measure impact on conversion. Target: +5-10% conversion improvement from experiments.

**File References:** `bot/bot/misc/experiments.py` (to create), ISSUE #802

- [ ] **Setup experiment framework** (ISSUE #802, 2h)
  - **File:** `bot/bot/misc/experiments.py` (create)
  - **Class:**
    ```python
    import hashlib
    from typing import Dict, Optional, List
    from dataclasses import dataclass
    from datetime import datetime

    @dataclass
    class Experiment:
        name: str
        variants: List[str]  # e.g. ["control", "treatment"]
        filter_users: bool = True  # Only new users?
        start_date: datetime = None
        end_date: datetime = None
        weight: Dict[str, float] = None  # e.g. {"control": 0.5, "treatment": 0.5}

    class ExperimentManager:
        """Manage A/B experiments."""

        ACTIVE_EXPERIMENTS = {
            "onboarding_copy": Experiment(
                name="onboarding_copy",
                variants=["control", "urgent", "friendly"],
                weight={"control": 0.34, "urgent": 0.33, "friendly": 0.33},
                # control: old copy
                # urgent: "Limited time! Activate now!"
                # friendly: "Ready to browse freely?"
            ),
            "trial_length": Experiment(
                name="trial_length",
                variants=["3_days", "7_days"],
                weight={"3_days": 0.5, "7_days": 0.5},
            ),
            "payment_cta": Experiment(
                name="payment_cta",
                variants=["calm", "urgent"],
                weight={"calm": 0.5, "urgent": 0.5},
                # calm: "Upgrade to Paid"
                # urgent: "Upgrade Now - Limited Offer"
            ),
        }

        @staticmethod
        def get_user_variant(
            user_tgid: int,
            experiment_name: str
        ) -> Optional[str]:
            """
            Deterministically assign user to variant.
            Same user always gets same variant (consistent hashing).
            """

            if experiment_name not in ExperimentManager.ACTIVE_EXPERIMENTS:
                return None

            exp = ExperimentManager.ACTIVE_EXPERIMENTS[experiment_name]

            # Hash user ID + experiment name
            hash_input = f"{user_tgid}:{experiment_name}"
            hash_value = int(
                hashlib.md5(hash_input.encode()).hexdigest(),
                16
            ) % 100

            # Use weights to select variant
            cumulative = 0
            for variant, weight in exp.weight.items():
                cumulative += int(weight * 100)
                if hash_value < cumulative:
                    return variant

            return exp.variants[0]  # Fallback

    # Usage in handlers:
    async def register_trial(message: Message):
        variant = ExperimentManager.get_user_variant(
            user_tgid=message.from_user.id,
            experiment_name="onboarding_copy"
        )

        if variant == "urgent":
            copy = "⏰ Activate your VPN trial NOW — limited time!"
        elif variant == "friendly":
            copy = "😊 Ready to browse freely? Activate your VPN trial!"
        else:  # control
            copy = "Click to activate your VPN trial"

        await message.answer(copy)

        # Log experiment assignment for analytics
        logger.info(
            f"event=exp.assignment "
            f"experiment=onboarding_copy "
            f"user_id={message.from_user.id} "
            f"variant={variant}"
        )
    ```
  - **Verify:**
    ```bash
    # Test bucketing consistency
    python -c "
    from bot.bot.misc.experiments import ExperimentManager

    user_id = 12345
    for i in range(3):
        variant = ExperimentManager.get_user_variant(user_id, 'onboarding_copy')
        print(f'Try {i+1}: {variant}')

    # Expected: Same variant all 3 times (consistent)
    # e.g. 'urgent', 'urgent', 'urgent'
    "
    ```

- [ ] **Implement experiment-aware handlers** (ISSUE #802, 2h)
  - **Files:** `bot/bot/handlers/user/main.py`, `bot/bot/handlers/user/payment.py` (modified)
  - **Example 1 — Onboarding copy experiment:**
    ```python
    @registered_router.message(Command("start"))
    async def start_command(message: Message, state: FSMState):
        user = await get_or_create_user(message.from_user.id)

        # Get experiment variant
        variant = ExperimentManager.get_user_variant(
            user.tgid, "onboarding_copy"
        )

        # Prepare copy based on variant
        copies = {
            "control": "Welcome! Activate your trial →",
            "urgent": "⏰ LIMITED TIME: Activate trial now!",
            "friendly": "😊 Ready to browse? Activate trial →",
        }

        copy_text = copies.get(variant, copies["control"])

        await message.answer(
            f"{copy_text}\n\n/activate_trial",
            reply_markup=trial_keyboard()
        )

        # Log assignment
        logger.info(
            f"event=exp.assignment experiment=onboarding_copy "
            f"user_id={user.id} variant={variant}"
        )
    ```
  - **Example 2 — Trial length experiment:**
    ```python
    async def issue_trial_key(user_tgid: int, session: AsyncSession):
        # Get variant
        variant = ExperimentManager.get_user_variant(
            user_tgid, "trial_length"
        )

        # Set expiry based on variant
        if variant == "7_days":
            trial_days = 7
        else:  # "3_days"
            trial_days = 3

        expires_at = datetime.utcnow() + timedelta(days=trial_days)

        key = VPNKey(
            user_tgid=user_tgid,
            expires_at=expires_at,
            trial_days=trial_days,  # Track for analytics
        )

        await db_session.add(key)
        await db_session.commit()

        logger.info(
            f"event=exp.assignment experiment=trial_length "
            f"user_id={user_tgid} variant={variant} trial_days={trial_days}"
        )

        return key
    ```

- [ ] **Run A/A test (sanity check)** (ISSUE #802, 1h)
  - **Purpose:** Verify bucketing is working and doesn't bias one variant
  - **Steps:**
    ```bash
    # Create equal-weight experiment with same variant
    # Expected: Each variant gets ~50% of users

    # Test with 100 user IDs
    python -c "
    from bot.bot.misc.experiments import ExperimentManager

    # Create test experiment
    ExperimentManager.ACTIVE_EXPERIMENTS['aa_test'] = {
        'variants': ['v1', 'v1'],  # Both same variant
        'weight': {'v1': 1.0}
    }

    # Assign 100 users
    variants = []
    for user_id in range(1, 101):
        v = ExperimentManager.get_user_variant(user_id, 'aa_test')
        variants.append(v)

    # All should be 'v1'
    assert all(v == 'v1' for v in variants)
    print('✅ A/A test passed: consistent assignment')
    "
    ```

- [ ] **Launch experiment at reduced traffic** (ISSUE #802, 0.5h)
  - **First launch:** 10% traffic
  - **Steps:**
    ```python
    # Modify weight in experiment config
    ACTIVE_EXPERIMENTS["onboarding_copy"] = Experiment(
        name="onboarding_copy",
        variants=["control", "urgent"],
        weight={"control": 0.90, "urgent": 0.10},  # 90-10 split
    )
    ```
  - **Monitor:** Check logs for even distribution across variants
    ```bash
    docker compose logs vpn_hub_bot | grep "exp.assignment" | \
      sed -E 's/.*variant=([^ ]+).*/\1/' | sort | uniq -c
    # Expected (rough): 9 control, 1 urgent
    ```

- [ ] **Measure experiment results** (ISSUE #802, 2h)
  - **Metrics to track:**
    - Conversion rate by variant: `conv.start → conv.payment_success`
    - Trial activation rate by variant
    - Payment completion time by variant
  - **Query logs:**
    ```bash
    # Count conversion starts by variant
    docker compose logs vpn_hub_bot | grep "exp.assignment experiment=onboarding_copy" | \
      sed -E 's/.*variant=([^ ]+).*/\1/' | sort | uniq -c

    # Count conversions by variant
    # (requires linking experiment log to conversion log by user_id)

    # For now: manual dashboard in Grafana
    ```

- [ ] **Calculate statistical significance** (ISSUE #802, 1h)
  - **Tool:** Python scipy.stats
  - **Script:**
    ```python
    from scipy.stats import chi2_contingency

    # Contingency table: variant × conversion (yes/no)
    data = [
        [45, 5],    # control: 45 conversions, 5 non-conversions
        [52, 8],    # urgent: 52 conversions, 8 non-conversions
    ]

    chi2, p_value, dof, expected = chi2_contingency(data)

    if p_value < 0.05:
        print(f"✅ Significant difference (p={p_value:.4f})")
    else:
        print(f"❌ Not significant (p={p_value:.4f}), need more data")
    ```

- [ ] **Rollout winner to 100%** (ISSUE #802, 0.5h)
  - **If "urgent" variant wins:**
    ```python
    ACTIVE_EXPERIMENTS["onboarding_copy"] = Experiment(
        name="onboarding_copy",
        variants=["urgent"],
        weight={"urgent": 1.0},  # 100% traffic
    )
    ```
  - **Update handler:**
    - Remove conditional logic, use "urgent" copy for all users

- [ ] **Repeat cycle for more experiments** (ISSUE #802, ongoing)
  - **Monthly cadence:**
    - Month 1: onboarding_copy experiment (results: ±5% conversion)
    - Month 2: trial_length experiment (results: ±8% conversion)
    - Month 3: payment_cta experiment (results: ±6% conversion)
    - Month 4: server_selector experiment (auto vs. manual)
  - **Cumulative impact:** 5% × 8% × 6% × 3% ≈ +20% conversion improvement over 4 months

- [ ] **Document experiment results** (ISSUE #802, 1h)
  - **File:** `docs/experiments/report.md` (create)
  - **Template:**
    ```markdown
    # Experiment Report: {name}

    **Dates:** {start} to {end}
    **Variants:** control, treatment
    **Sample Size:** {n_control}, {n_treatment}
    **Hypothesis:** {expected outcome}

    ## Results

    | Variant | Conversions | Conversion Rate | CI (95%) |
    |---------|-------------|-----------------|---------|
    | Control | 50/1000 | 5.0% | [4.0%, 6.0%] |
    | Treatment | 65/1000 | 6.5% | [5.3%, 7.7%] |

    **Difference:** +1.5 percentage points (+30% relative)
    **P-value:** 0.032 (significant at p<0.05)
    **Decision:** ROLLOUT to 100%
    ```

---

### 5.3 DEVOPS AUTOMATION AGENT (OPTIONAL, ADVANCED)

**Goal:** Bot that monitors alerts and auto-fixes common issues. Target: 80% of issues fixed automatically, no human intervention.

**File References:** `bot/agents/` (create new directory), ISSUE #701

**Note:** This is complex and optional. Focus on simpler experiments first.

- [ ] **Design DevOps Agent scope** (0.5h planning)
  - **What to auto-fix:**
    - [ ] DB connection pool exhausted → slow queries, restart bot
    - [ ] NATS lag > 1000 messages → scale consumer workers
    - [ ] Disk usage > 80% → cleanup old logs
    - [ ] Server latency spike → mark degraded, auto-reassign keys
    - [ ] Memory leak detected → graceful restart
  - **What to escalate to humans:**
    - [ ] Server offline >10 minutes
    - [ ] Database corruption detected
    - [ ] Security alert
    - [ ] Revenue impact detected

- [ ] **Implement auto-fix for DB connection pool** (2h)
  - **Trigger:** Alert: "db_connections_exhausted"
  - **Action:** Restart bot gracefully
  - **Script:**
    ```python
    class DevOpsAgent:
        async def on_alert_db_connections_exhausted(self):
            logger.warning("DB connection pool exhausted, restarting...")

            # Drain: stop accepting new connections
            app.state["accepting_connections"] = False

            # Wait for existing requests to finish (grace period)
            await asyncio.sleep(30)

            # Restart bot process
            os.execv(sys.executable, [sys.executable] + sys.argv)
    ```

---

**CHECKLIST 5 COMPLETION CRITERIA**

- [ ] check_callbacks.py runs without errors, all callbacks handled
- [ ] GitHub Actions workflow rejects PR with unhandled callbacks
- [ ] Callback naming conventions documented and enforced
- [ ] Experiment framework implemented (ExperimentManager class)
- [ ] A/A test passed: consistent user bucketing verified
- [ ] All handlers updated to use experiment variants
- [ ] First experiment (onboarding_copy) launched at 10% traffic
- [ ] No increase in error rate post-experiment
- [ ] Experiment results measured: statistical significance calculated
- [ ] Winner variant identified and rolled out to 100% (or found no significant difference)
- [ ] Second experiment (trial_length) launched at 50% traffic
- [ ] Experiment reports documented with results + decisions
- [ ] Cumulative conversion improvement tracked: target +5-10% over 90 days

---

---

## SUMMARY BY DOMAIN

| Checklist | Epic | Issues | Effort | Completion Criteria |
|-----------|------|--------|--------|-------------------|
| **1: UX** | 4 | #401, #302 | 13-17h | Conversion 3-5% → 12%, <30sec onboarding |
| **2: China** | 5 | #501, #502 | 18-22h | >80% success from CN, <200ms latency |
| **3: Auto-Failover** | 3 | #301, #302 | 10-12h | Uptime 95% → 99.5%, <10sec failover |
| **4: Observability** | 2 | #102, #201, #202 | 18-21h | 100% visibility, <1min MTTR |
| **5: AI Agents** | 8 | #801, #802 | 10-13h | Zero unhandled callbacks, +5-10% conversion |
| **TOTAL** | — | 20 | 88-97h | All P0/P1/P2 issues resolved |

---

**Next Documents in Sequence:**
- **PART 4: SPRINT_PLAN** (4 x 2-week sprints)
- **PART 5: NEXT_10_EXECUTION_STEPS** (immediate actions today)
<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[
  {
    "content": "Create CHECKLISTS_BY_DOMAIN.md with 5 implementation checklists",
    "status": "in_progress",
    "activeForm": "Creating implementation checklists by domain"
  },
  {
    "content": "Complete Checklist 1 (User Experience)",
    "status": "completed",
    "activeForm": "Completed User Experience checklist"
  },
  {
    "content": "Complete Checklist 2 (China Readiness)",
    "status": "completed",
    "activeForm": "Completed China Readiness checklist"
  },
  {
    "content": "Complete Checklist 3 (Auto-Failover & Resilience)",
    "status": "completed",
    "activeForm": "Completed Auto-Failover checklist"
  },
  {
    "content": "Complete Checklist 4 (Observability & Monitoring)",
    "status": "pending",
    "activeForm": "Creating Observability checklist"
  },
  {
    "content": "Complete Checklist 5 (AI Agents Activation)",
    "status": "pending",
    "activeForm": "Creating AI Agents checklist"
  },
  {
    "content": "Create PART 4: SPRINT_PLAN (4 x 2-week sprints)",
    "status": "pending",
    "activeForm": "Planning 4 two-week sprints"
  },
  {
    "content": "Create PART 5: NEXT_10_EXECUTION_STEPS (immediate actions)",
    "status": "pending",
    "activeForm": "Defining 10 execution steps"
  }
]