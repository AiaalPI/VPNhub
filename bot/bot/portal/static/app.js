/* No analytics, third-party scripts, or credentials in localStorage. */
"use strict";
const $ = (selector) => document.querySelector(selector);
let settings = null;
let signedIn = false;
let chosenPlan = null;
let challenge = null;
let noticeTimer;
let refreshTimer;
const money = (kopecks) => new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(kopecks / 100) + " ₽";
const date = (timestamp) => new Date(timestamp * 1000).toLocaleDateString("ru-RU");
const duration = (months) => ({ 1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "12 месяцев" }[months]);
function trialDescription(trial) {
  const hours = trial.seconds / 3600;
  const days = hours / 24;
  return (Number.isInteger(days) ? days + " дн." : hours + " ч.") + " · " + trial.quota_gb + " ГБ";
}

function notify(message) {
  clearTimeout(noticeTimer);
  $("#notice").textContent = message;
  $("#notice").hidden = false;
  noticeTimer = setTimeout(() => { $("#notice").hidden = true; }, 6500);
}

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch("/web/api" + path, {
      method: body === undefined ? "GET" : "POST", credentials: "same-origin",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
      cache: "no-store",
    });
    let data;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      const error = new Error(typeof data.detail === "string" ? data.detail : "Не удалось выполнить запрос. Попробуйте ещё раз.");
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Сервер отвечает дольше обычного. Попробуйте ещё раз.");
    if (error instanceof TypeError) throw new Error("Нет связи с сервером. Проверьте интернет и повторите попытку.");
    throw error;
  } finally { clearTimeout(timeout); }
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function safeLink(node, value) {
  if (!value) return;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return;
    node.href = url.href;
    node.target = "_blank";
    node.rel = "noopener noreferrer";
    node.hidden = false;
  } catch { /* A missing legal URL keeps checkout unavailable. */ }
}

function renderPlans() {
  const grid = $("#plans-grid");
  grid.replaceChildren();
  for (const plan of settings.plans) {
    const featured = plan.months === 3;
    const card = element("article", "plan" + (featured ? " featured" : ""));
    card.append(element("span", "plan-tag", featured ? "НАЧНИТЕ С КОМФОРТА" : "KYN VPN"));
    card.append(element("h3", "", duration(plan.months)));
    card.append(element("div", "plan-price", money(plan.amount_kopecks)));
    card.append(element("p", "plan-period", "за весь срок · " + money(Math.round(plan.amount_kopecks / plan.months)) + "/мес."));
    const list = element("ul", "plan-list");
    [plan.quota_gb + " ГБ на срок подписки", "Основной + XHTTP", "Телефон и компьютер", "Без автосписаний"].forEach((text) => list.append(element("li", "", text)));
    card.append(list);
    const button = element("button", "button " + (featured ? "button-primary" : "button-outline"), "Выбрать тариф ↗");
    button.addEventListener("click", () => { chosenPlan = plan; signedIn ? showCheckout() : showLogin(); });
    card.append(button);
    grid.append(card);
  }
  if (!settings.plans.length) grid.append(element("p", "loading-plans muted", "Тарифы временно недоступны. Попробуйте позже."));
}

function showLogin() {
  $("#auth-error").textContent = "";
  if (!settings || settings.launch_pending) {
    notify("Вход пока недоступен. Попробуйте позже.");
    return;
  }
  $("#choose-email").disabled = !settings.login_available;
  $("#email-unavailable").hidden = !!settings.login_available;
  if (!$("#auth-dialog").open) $("#auth-dialog").showModal();
  // The invitation page has already asked for a channel on the #email path.
  setAuthMode(location.hash === "#email" && settings.login_available ? (challenge ? "code" : "email") : "choice");
}

function setAuthMode(mode) {
  $("#auth-choices").hidden = mode !== "choice";
  $("#email-form").hidden = mode !== "email";
  $("#code-form").hidden = mode !== "code";
  $("#auth-back").hidden = mode === "choice";
  $("#auth-error").textContent = "";
  $("#auth-title").textContent = mode === "choice" ? "Как вам удобнее войти?" : "Вход на сайт по email";
  $("#auth-description").textContent = mode === "choice"
    ? "Выберите сайт или Telegram. Подписки управляются отдельно."
    : mode === "email" ? "Отправим код на вашу почту. Для входа на сайт Telegram не нужен."
    : "Код отправлен на " + $("#email").value + ". Он действует 10 минут. Проверьте также папку «Спам».";
  if ($("#auth-dialog").open) $(mode === "choice" ? (settings.login_available ? "#choose-email" : "#choose-telegram") : mode === "email" ? "#email" : "#code").focus();
}

function showCheckout() {
  if (!chosenPlan) return;
  $("#checkout-summary").textContent = duration(chosenPlan.months) + " · " + money(chosenPlan.amount_kopecks) + " · " + chosenPlan.quota_gb + " ГБ";
  $("#checkout-error").textContent = settings.checkout_available ? "" : "Приём платежей пока не открыт. Попробуйте позже.";
  $("#checkout-consent").checked = false;
  $("#pay").disabled = true;
  $("#checkout-dialog").showModal();
}

async function openAccount() {
  try {
    await loadAccount();
    location.hash = "account";
    $("#landing").hidden = true;
    $("#account").hidden = false;
    window.scrollTo({ top: 0, behavior: "instant" });
  } catch (error) {
    if (error.status === 401) { signedIn = false; showLogin(); }
    else notify(error.message);
  }
}

async function loadAccount() {
  const data = await api("/account");
  signedIn = true;
  $("#account-email").textContent = data.email;
  const sub = data.subscription;
  const trial = data.trial || {};
  $("#trial-activate").hidden = !trial.eligible;
  $("#trial-note").hidden = !trial.eligible;
  $("#trial-activate").textContent = "Попробовать бесплатно · " + trialDescription(trial);
  $("#subscription-title").textContent = !sub ? "Подписки пока нет" : sub.active ? (sub.ready ? (trial.is_trial ? "Пробный доступ активен" : "Подписка активна") : "Готовим подключение") : (trial.is_trial ? "Пробный период закончился" : "Подписка закончилась");
  $("#subscription-description").textContent = !sub ? (trial.eligible ? "Проверьте VPN в своей сети бесплатно. Карта не нужна." : "Выберите подходящий срок, чтобы подключиться.") : "Доступ до " + date(sub.expires_at) + ". Объём на срок подписки: " + sub.quota_gb + " ГБ.";
  $("#renew").textContent = sub ? "Продлить подписку ↗" : "Выбрать тариф ↗";
  $("#retry").hidden = !(sub && sub.active && !sub.ready);
  $("#load-profiles").hidden = !(sub && sub.active && sub.ready);
  $("#profiles-description").textContent = sub && sub.active && sub.ready ? "Скопируйте основной или резервный профиль и добавьте его в VPN-приложение." : "Основной и резервный профили появятся здесь после активации.";
  if (!(sub && sub.active && sub.ready)) { $("#profiles").hidden = true; $("#profile-list").replaceChildren(); }
  $("#no-orders").hidden = data.orders.length > 0;
  $("#orders-table").hidden = data.orders.length === 0;
  $("#orders").replaceChildren();
  for (const order of data.orders) {
    const row = element("tr");
    row.append(element("td", "", date(order.created_at)), element("td", "", duration(order.months)), element("td", "", money(order.amount_kopecks)), element("td", order.status, order.status === "paid" ? "Оплачен" : "Ожидает оплаты"));
    $("#orders").append(row);
  }
  clearTimeout(refreshTimer);
  if (location.hash === "#account" && data.orders.some((o) => o.status === "pending" && Date.now() / 1000 - o.created_at < 3600)) {
    refreshTimer = setTimeout(() => { if (!document.hidden && location.hash === "#account") loadAccount().catch(() => {}); }, 15000);
  }
}

$("#email-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  $("#auth-error").textContent = "";
  try {
    const result = await api("/auth/code", { email: $("#email").value });
    challenge = result.challenge;
    setAuthMode("code");
  } catch (error) { $("#auth-error").textContent = error.message; }
  finally { button.disabled = false; }
});

$("#code-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    await api("/auth/verify", { challenge, code: $("#code").value });
    signedIn = true;
    challenge = null;
    $("#code").value = "";
    $("#auth-dialog").close();
    resetEmailForm();
    if (chosenPlan) showCheckout(); else await openAccount();
  } catch (error) { $("#auth-error").textContent = error.message; }
  finally { button.disabled = false; }
});

function resetEmailForm() {
  challenge = null;
  $("#code").value = "";
  setAuthMode("email");
}
$("#change-email").addEventListener("click", resetEmailForm);
$("#choose-email").addEventListener("click", () => setAuthMode(challenge ? "code" : "email"));
$("#auth-back").addEventListener("click", () => setAuthMode("choice"));
document.querySelectorAll("[data-account]").forEach((button) => button.addEventListener("click", () => { chosenPlan = null; openAccount(); }));
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
$("#checkout-consent").addEventListener("change", () => { $("#pay").disabled = !$("#checkout-consent").checked || !settings.checkout_available; });
$("#pay").addEventListener("click", async () => {
  $("#pay").disabled = true;
  try {
    const order = await api("/orders", { months: chosenPlan.months, accepted_terms: true });
    const url = new URL(order.url);
    if (url.protocol !== "https:" || url.hostname !== "yoomoney.ru") throw new Error("Не удалось открыть платёжную страницу.");
    location.assign(url.href);
  } catch (error) {
    $("#checkout-error").textContent = error.message;
    $("#pay").disabled = false;
    if (error.status === 401) { $("#checkout-dialog").close(); signedIn = false; showLogin(); }
  }
});
$("#logout").addEventListener("click", async () => {
  try {
    await api("/auth/logout", {});
    signedIn = false;
    chosenPlan = null;
    clearTimeout(refreshTimer);
    $("#account-email").textContent = "";
    $("#orders").replaceChildren();
    $("#profile-list").replaceChildren();
    $("#profiles").hidden = true;
    location.hash = "home";
  } catch (error) { notify(error.message); }
});
$("#renew").addEventListener("click", () => { location.hash = "plans"; });
$("#refresh").addEventListener("click", async () => {
  $("#refresh").disabled = true;
  try { await loadAccount(); notify("Статус обновлён"); }
  catch (error) { notify(error.message); }
  finally { $("#refresh").disabled = false; }
});
$("#retry").addEventListener("click", async () => {
  $("#retry").disabled = true;
  try { await api("/subscription/retry", {}); await loadAccount(); notify("Подключение готово"); }
  catch (error) { notify(error.message); }
  finally { $("#retry").disabled = false; }
});
$("#trial-activate").addEventListener("click", async () => {
  const button = $("#trial-activate");
  button.disabled = true;
  button.textContent = "Готовим пробное подключение…";
  try {
    await api("/trial", {});
    await openAccount();
    await loadProfiles();
    notify("Пробный доступ активирован. Выберите инструкцию для своего устройства.");
  } catch (error) {
    // A panel timeout may follow a committed grant; expose its retry action.
    try { await loadAccount(); } catch { /* Preserve the original error. */ }
    notify(error.message);
    if (error.status === 401) { signedIn = false; showLogin(); }
  } finally { button.disabled = false; }
});
async function loadProfiles() {
  $("#load-profiles").disabled = true;
  try {
    const data = await api("/subscription");
    $("#profile-list").replaceChildren();
    for (const link of data.links) {
      const parsed = new URL(link);
      if (parsed.protocol !== "vless:") continue;
      const xhttp = parsed.searchParams.get("type") === "xhttp";
      const card = element("article", "profile");
      const description = element("div");
      description.append(element("h3", "", xhttp ? "MTS XHTTP · резервный" : "Основной профиль"), element("p", "", xhttp ? "Требуется приложение с поддержкой XHTTP" : "VLESS / REALITY"));
      const copy = element("button", "button button-outline button-small", "Скопировать");
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(link); notify("Профиль скопирован. Добавьте его в VPN-приложение."); }
        catch {
          let field = card.querySelector("textarea");
          if (!field) { field = element("textarea", "manual-copy"); field.readOnly = true; field.setAttribute("aria-label", "Профиль для ручного копирования"); field.value = link; card.append(field); }
          field.focus(); field.select(); notify("Скопируйте выделенный профиль вручную.");
        }
      });
      card.append(description, copy); $("#profile-list").append(card);
    }
    $("#profiles").hidden = false;
    $("#profiles").scrollIntoView({ behavior: "smooth" });
  } catch (error) { notify(error.message); }
  finally { $("#load-profiles").disabled = false; }
}
$("#load-profiles").addEventListener("click", loadProfiles);

function route() {
  if (["#account", "#email"].includes(location.hash)) { openAccount(); return; }
  $("#account").hidden = true;
  $("#landing").hidden = false;
  clearTimeout(refreshTimer);
  const section = document.getElementById(location.hash.slice(1));
  if (section) section.scrollIntoView();
}
window.addEventListener("hashchange", route);
window.addEventListener("pageshow", (event) => { if (event.persisted && ["#account", "#email"].includes(location.hash)) openAccount(); });

async function start() {
  $("#year").textContent = new Date().getFullYear();
  try {
    settings = await api("/config");
    if (settings.preview && !$("#preview-banner")) {
      const banner = element("div", "preview-banner", "Локальный просмотр · примерные данные · письма и оплата отключены");
      banner.id = "preview-banner";
      document.body.prepend(banner);
    }
    if (settings.launch_pending && !$("#launch-banner")) {
      const banner = element("div", "preview-banner", "Сайт готовится к запуску · вход по email и покупка пока недоступны");
      banner.id = "launch-banner";
      document.body.prepend(banner);
    }
    renderPlans();
    $("#trial-offer").hidden = !settings.trial?.available;
    if (settings.trial?.available) $("#trial-offer-details").textContent = trialDescription(settings.trial) + " для проверки в вашей сети. Один раз после подтверждения email. Без карты и автосписаний.";
    ["#privacy-link", "#auth-privacy-link", "#checkout-privacy"].forEach((id) => safeLink($(id), settings.privacy_url));
    ["#terms-link", "#checkout-terms"].forEach((id) => safeLink($(id), settings.terms_url));
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(settings.support_email)) { $("#support-link").href = "mailto:" + settings.support_email; $("#support-link").hidden = false; }
    try { if (!settings.launch_pending) await loadAccount(); } catch (error) { if (error.status !== 401) console.warn("Account unavailable"); }
  } catch {
    const text = element("p", "loading-plans muted", "Не удалось загрузить тарифы. ");
    const retry = element("button", "text-link", "Повторить загрузку ↻");
    retry.addEventListener("click", start);
    text.append(retry); $("#plans-grid").replaceChildren(text);
  }
  route();
}
start();
