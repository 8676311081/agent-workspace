#!/usr/bin/env bash
set -euo pipefail

# Daily tabcode.cc balance check → Feishu webhook.
# Triggered by launchd (com.user.tabcode-balance) at 09:00.

WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/fc913e65-797e-4db0-b11b-0cbd1e04a09b"
EMAIL="867631108@qq.com"
PASSWORD='N6872fj9pl2!'
LOG_DIR="$HOME/Library/Logs/tabcode-balance"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }

bb() { npx -y bb-browser "$@"; }

send_feishu() {
  local text="$1"
  curl -s -X POST "$WEBHOOK" \
    -H 'Content-Type: application/json' \
    --data-binary @<(jq -n --arg t "$text" '{msg_type:"text", content:{text:$t}}') \
    >> "$LOG" 2>&1
  echo "" >> "$LOG"
}

read_balance_json() {
  bb eval '(() => {
    const main = document.querySelector("main");
    if (!main) return JSON.stringify({ok:false, error:"no main"});
    const txt = main.innerText;
    const grab = (label) => {
      const idx = txt.indexOf(label);
      if (idx < 0) return null;
      const after = txt.slice(idx + label.length).trim();
      const m = after.match(/\$[0-9.,]+/);
      return m ? m[0] : null;
    };
    const today = grab("今日费用");
    const month = grab("本月费用");
    const remain = grab("今日剩余额度（含加油包）");
    const breakdown = (txt.match(/套餐\s*([0-9.]+)\s*[·•]\s*加油包\s*([0-9.]+)/) || []);
    const callsM = txt.match(/调用\s*(\d+)\s*次/);
    return JSON.stringify({
      ok: true,
      today, month, remain,
      plan: breakdown[1] || null,
      gas:  breakdown[2] || null,
      calls: callsM ? callsM[1] : null,
      url: location.href,
    });
  })()' 2>&1
}

login() {
  log "Need login. Filling credentials."
  bb open "https://tabcode.cc" >> "$LOG" 2>&1
  sleep 2
  # Open login modal
  bb eval '(() => { const b = Array.from(document.querySelectorAll("button")).find(el => el.textContent.trim() === "开始使用"); if (b) b.click(); return "ok"; })()' >> "$LOG" 2>&1
  sleep 2
  # Fill via JS to avoid ref-number drift
  bb eval "(() => {
    const setVal = (el, v) => {
      const proto = Object.getPrototypeOf(el);
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(el, v);
      el.dispatchEvent(new Event('input', {bubbles:true}));
      el.dispatchEvent(new Event('change', {bubbles:true}));
    };
    const email = document.querySelector('input[type=\"email\"], input[placeholder*=\"name@\" i], input[placeholder*=\"邮箱\"]');
    const pw = document.querySelector('input[type=\"password\"]');
    if (email) setVal(email, '$EMAIL');
    if (pw) setVal(pw, ${PASSWORD@Q});
    return JSON.stringify({email: !!email, pw: !!pw});
  })()" >> "$LOG" 2>&1
  sleep 1
  # Click the submit button (the one inside the modal labelled 登录)
  bb eval '(() => {
    const btns = Array.from(document.querySelectorAll("button")).filter(el => el.textContent.trim() === "登录");
    // The submit button is usually the last one with type=submit or inside a form
    const submit = btns.find(b => b.type === "submit") || btns[btns.length - 1];
    if (submit) submit.click();
    return submit ? "clicked" : "no submit";
  })()' >> "$LOG" 2>&1
  sleep 5
}

main() {
  log "=== Run start ==="
  bb open "https://tabcode.cc/dashboard" >> "$LOG" 2>&1
  sleep 3
  local url
  url=$(bb get url 2>/dev/null | tail -1)
  log "Initial URL: $url"
  if [[ "$url" != *"/dashboard"* ]]; then
    login
    bb open "https://tabcode.cc/dashboard" >> "$LOG" 2>&1
    sleep 3
    url=$(bb get url 2>/dev/null | tail -1)
    log "URL after login: $url"
  fi

  local raw json
  raw=$(read_balance_json)
  log "Raw balance JSON line: $raw"
  json=$(printf '%s' "$raw" | tail -1)

  if ! echo "$json" | jq -e '.ok' >/dev/null 2>&1; then
    send_feishu "【tabcode 余额查询失败】$(date '+%F %T')\n抓取失败，请人工检查。\n原始响应：$raw"
    log "Failed to parse balance"
    exit 1
  fi

  local plan gas remain today month calls
  plan=$(echo "$json" | jq -r '.plan // "0.00"')
  gas=$(echo "$json"  | jq -r '.gas  // "0.00"')
  remain=$(echo "$json" | jq -r '.remain // "$0.00"')
  today=$(echo "$json"  | jq -r '.today  // "$0.00"')
  month=$(echo "$json"  | jq -r '.month  // "$0.00"')
  calls=$(echo "$json"  | jq -r '.calls  // "0"')

  local total
  total=$(awk -v a="$plan" -v b="$gas" 'BEGIN{printf "%.2f", a+b}')

  local msg
  msg=$(printf '【tabcode.cc 余额】%s\n账号：%s\n\n剩余总额：$%s\n  套餐：$%s\n  加油包：$%s\n\n今日费用：%s（%s 次调用）\n本月费用：%s' \
    "$(date '+%F %H:%M')" "$EMAIL" "$total" "$plan" "$gas" "$today" "$calls" "$month")

  send_feishu "$msg"
  log "Sent: $msg"
  log "=== Run end ==="
}

main "$@"
