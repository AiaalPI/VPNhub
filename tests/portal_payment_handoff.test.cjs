// Exercise the shipped frontend's native form handoff without contacting a PSP.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const submitted = [];
  const forms = [];
  const document = {
    addEventListener() {},
    querySelector: () => ({ addEventListener() {} }),
    querySelectorAll: () => [],
    createElement: (tag) => ({ tag, children: [], append(child) { this.children.push(child); },
      submit() { submitted.push({ method: this.method, action: this.action,
        fields: Object.fromEntries(this.children.map((input) => [input.name, input.value])) }); },
      remove() { this.removed = true; } }),
    body: { append(form) { forms.push(form); } },
  };
  const source = fs.readFileSync(path.join(__dirname, '../bot/bot/portal/static/app.js'), 'utf8');
  // Suppress only the automatic API boot; all real event handlers/functions load.
  assert.match(source, /\nstart\(\);\s*$/);
  const context = { document, window: { addEventListener() {} }, URL, console };
  vm.createContext(context);
  vm.runInContext(source.replace(/\nstart\(\);\s*$/, ''), context);
  return { submit: context.submitPayment, submitted, forms };
}

function payment() {
  return { method: 'POST', action: 'https://yoomoney.ru/quickpay/confirm', fields: {
    receiver: '41000000000000', 'quickpay-form': 'button', paymentType: 'SB',
    sum: '150.00', label: 'kw1_test-order', successURL: 'https://vpn.test/web/payment-return',
  } };
}

test('native POST preserves amount, order attribution and exact return URL', () => {
  const h = harness();
  h.submit(payment());
  assert.deepEqual(h.submitted, [payment()]);
  assert.equal(h.forms[0].removed, undefined);
});

test('rejects external destinations, GET handoffs and missing fields before submission', () => {
  for (const mutate of [p => p.action = 'https://example.org/steal', p => p.method = 'GET',
    p => delete p.fields.successURL, p => p.fields.sum = 1]) {
    const h = harness(); const p = payment(); mutate(p);
    assert.throws(() => h.submit(p));
    assert.equal(h.submitted.length, 0);
  }
});
