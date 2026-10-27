// Exercise the actual browser script using a minimal DOM and local API doubles.
// No real browser, customer account, credentials, or network is involved.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

test("account refresh retains the selected active profile and removes revoked access", async () => {
  const nodes = new Map();
  function node() {
    return {
      hidden: true, children: [], textContent: "", href: "", listeners: {},
      classList: { toggle() {} },
      append(...children) { this.children.push(...children); },
      prepend() {}, replaceChildren(...children) { this.children = children; },
      addEventListener(name, callback) { this.listeners[name] = callback; },
      setAttribute(name, value) { this[name] = value; },
      getAttribute(name) { return this[name] || null; },
      removeAttribute(name) { delete this[name]; },
      scrollIntoView() {}, focus() {}, select() {}, querySelector() { return null; },
    };
  }
  const get = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, node());
    return nodes.get(selector);
  };
  const account = {email: "example@example.test", telegram: {linked: true},
    telegram_subscriptions: [{id: 42, expires_at: 2000000000, active: true}],
    subscription: null, trial: {}, history: [], orders: []};
  const context = vm.createContext({
    document: {querySelector: get, querySelectorAll: () => [], createElement: node, addEventListener() {},
      getElementById: get, body: {prepend() {}}, hidden: false},
    window: {addEventListener() {}, scrollTo() {}},
    location: {hash: "#account", assign() {}},
    fetch: async (url) => ({ok: true, json: async () =>
      url.endsWith("/config") ? {plans: [], login_available: true} :
      url.endsWith("/profiles") || url.endsWith("/subscription") ?
        {links: ["vless://example@node.test:443?type=tcp&security=reality"]} : account}),
    URL, Date, Intl, AbortController, setTimeout: () => 1, clearTimeout() {},
  });
  const source = fs.readFileSync(path.join(__dirname, "../bot/bot/portal/static/app.js"), "utf8");
  vm.runInContext(source, context);
  await new Promise((resolve) => setImmediate(resolve));
  await vm.runInContext('loadProfiles("/telegram/subscriptions/42/profiles")', context);
  assert.equal(get("#profiles").hidden, false);
  assert.equal(get("#profile-list").children.length, 1);
  await vm.runInContext("loadAccount()", context);
  assert.equal(get("#profiles").hidden, false);
  assert.equal(get("#profile-list").children.length, 1);
  assert.equal(get("#profile-download").hidden, true);

  account.telegram_subscriptions[0].active = false;
  await vm.runInContext("loadAccount()", context);
  assert.equal(get("#profiles").hidden, true);
  assert.equal(get("#profile-list").children.length, 0);

  account.subscription = {active: true, ready: true, expires_at: 2000000000};
  await vm.runInContext('loadProfiles("/subscription")', context);
  await vm.runInContext("loadAccount()", context);
  assert.equal(get("#profiles").hidden, false);
  assert.equal(get("#profile-download").hidden, false);
  account.subscription.active = false;
  await vm.runInContext("loadAccount()", context);
  assert.equal(get("#profiles").hidden, true);
});
