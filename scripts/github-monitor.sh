#!/usr/bin/env bash
# github-monitor.sh — 监控 8676311081/cabinet 仓库变化，有变化时发飞书通知
# 用法: 配合 cron 每小时执行一次
#   0 * * * * /path/to/github-monitor.sh
set -euo pipefail

REPO="8676311081/cabinet"
STATE_FILE="/tmp/cabinet-github-stats.json"
FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/b4ba7fd0-f3b6-42e8-8a34-ba139f5e0f64"
REPORT_INTERVAL=18000  # 5 小时（秒）— 定期发送完整状态报告

# ---------- 采集当前数据 ----------

repo_json=$(gh api "repos/${REPO}" --cache 0s 2>/dev/null || echo '{}')
stars=$(echo "$repo_json" | jq -r '.stargazers_count // 0')
forks=$(echo "$repo_json" | jq -r '.forks_count // 0')

# 获取最新 release 的 DMG 下载量（合计所有 .dmg 资产）
releases_json=$(gh api "repos/${REPO}/releases" --cache 0s 2>/dev/null || echo '[]')
dmg_downloads=$(echo "$releases_json" | jq '[.[].assets[]? | select(.name | test("\\.dmg$"; "i")) | .download_count] | add // 0')
latest_release=$(echo "$releases_json" | jq -r '.[0].tag_name // "none"')

# 获取 open issues（排除 PR）
issues_json=$(gh api "repos/${REPO}/issues?state=open&per_page=100" --cache 0s 2>/dev/null || echo '[]')
open_issues=$(echo "$issues_json" | jq '[.[] | select(.pull_request == null)] | length')
# 收集 issue 标题用于通知
issue_titles=$(echo "$issues_json" | jq -r '[.[] | select(.pull_request == null) | "#\(.number) \(.title)"] | join("\n")')

# 获取 Discussions（建议/反馈）
OWNER="${REPO%%/*}"
REPO_NAME="${REPO##*/}"
discussions_json=$(gh api graphql -f query='
  query($owner:String!, $repo:String!) {
    repository(owner:$owner, name:$repo) {
      discussions(first:20, orderBy:{field:CREATED_AT, direction:DESC}) {
        totalCount
        nodes { number title createdAt category { name } }
      }
    }
  }' -f owner="$OWNER" -f repo="$REPO_NAME" 2>/dev/null || echo '{}')
discussions_count=$(echo "$discussions_json" | jq '.data.repository.discussions.totalCount // 0')
# 最新 5 条 discussion 标题，用于通知新增时展示
discussion_titles=$(echo "$discussions_json" | jq -r '[.data.repository.discussions.nodes[]? | "#\(.number) [\(.category.name)] \(.title)"] | .[0:5] | join("\n")')

# ---------- 组装当前状态 ----------

current=$(jq -n \
  --argjson stars "$stars" \
  --argjson forks "$forks" \
  --argjson dmg_downloads "$dmg_downloads" \
  --arg latest_release "$latest_release" \
  --argjson open_issues "$open_issues" \
  --arg issue_titles "$issue_titles" \
  --argjson discussions "$discussions_count" \
  --arg discussion_titles "$discussion_titles" \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{stars:$stars, forks:$forks, dmg_downloads:$dmg_downloads, latest_release:$latest_release, open_issues:$open_issues, issue_titles:$issue_titles, discussions:$discussions, discussion_titles:$discussion_titles, updated_at:$ts}')

# ---------- 对比上次 ----------

now_epoch=$(date +%s)

if [[ ! -f "$STATE_FILE" ]]; then
  current=$(echo "$current" | jq --argjson lr "$now_epoch" '. + {last_report_at: $lr}')
  echo "$current" > "$STATE_FILE"
  echo "首次运行，已保存初始状态到 $STATE_FILE"
  exit 0
fi

prev=$(cat "$STATE_FILE")
prev_stars=$(echo "$prev" | jq -r '.stars // 0')
prev_forks=$(echo "$prev" | jq -r '.forks // 0')
prev_dmg=$(echo "$prev" | jq -r '.dmg_downloads // 0')
prev_release=$(echo "$prev" | jq -r '.latest_release // "none"')
prev_issues=$(echo "$prev" | jq -r '.open_issues // 0')
prev_discussions=$(echo "$prev" | jq -r '.discussions // 0')

changes=()

if (( stars != prev_stars )); then
  diff=$((stars - prev_stars))
  sign=""; (( diff > 0 )) && sign="+"
  changes+=("⭐ Stars: ${prev_stars} → ${stars} (${sign}${diff})")
fi

if (( forks != prev_forks )); then
  diff=$((forks - prev_forks))
  sign=""; (( diff > 0 )) && sign="+"
  changes+=("🍴 Forks: ${prev_forks} → ${forks} (${sign}${diff})")
fi

if (( dmg_downloads != prev_dmg )); then
  diff=$((dmg_downloads - prev_dmg))
  sign=""; (( diff > 0 )) && sign="+"
  changes+=("📦 DMG 下载: ${prev_dmg} → ${dmg_downloads} (${sign}${diff})")
fi

if [[ "$latest_release" != "$prev_release" ]]; then
  changes+=("🚀 新 Release: ${latest_release}")
fi

if (( open_issues != prev_issues )); then
  diff=$((open_issues - prev_issues))
  if (( diff > 0 )); then
    changes+=("🐛 新增 ${diff} 个 Issue (当前 ${open_issues} 个 open)")
  else
    changes+=("✅ 关闭了 $((-diff)) 个 Issue (当前 ${open_issues} 个 open)")
  fi
fi

if (( discussions_count != prev_discussions )); then
  diff=$((discussions_count - prev_discussions))
  if (( diff > 0 )); then
    changes+=("💬 新增 ${diff} 条 Discussion (当前 ${discussions_count} 条)")
    if [[ -n "$discussion_titles" ]]; then
      changes+=("   最新: $(echo "$discussion_titles" | head -n3 | tr '\n' ' ')")
    fi
  else
    changes+=("💬 Discussions: ${prev_discussions} → ${discussions_count}")
  fi
fi

# ---------- 发送飞书卡片的通用函数 ----------

send_feishu_card() {
  local title="$1"
  local template="$2"
  local body_text="$3"

  local body_escaped
  body_escaped=$(echo -e "$body_text" | jq -Rs .)

  local card_json
  card_json=$(cat <<ENDJSON
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {
        "content": "${title}",
        "tag": "plain_text"
      },
      "template": "${template}"
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "content": ${body_escaped},
          "tag": "lark_md"
        }
      },
      {
        "tag": "note",
        "elements": [
          {
            "tag": "plain_text",
            "content": "$(date -u +%Y-%m-%d\ %H:%M\ UTC) · github-monitor.sh"
          }
        ]
      }
    ]
  }
}
ENDJSON
)

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$FEISHU_WEBHOOK" \
    -H 'Content-Type: application/json' \
    -d "$card_json")
  echo "$http_code"
}

# ---------- 检查是否需要定期报告 ----------

last_report_at=$(echo "$prev" | jq -r '.last_report_at // 0')
time_since_report=$((now_epoch - last_report_at))
need_report=false
if (( time_since_report >= REPORT_INTERVAL )); then
  need_report=true
fi

# ---------- 发送变化通知 ----------

if (( ${#changes[@]} > 0 )); then
  body=""
  for c in "${changes[@]}"; do
    body="${body}${c}\n"
  done
  body="${body}\n📊 当前: ⭐${stars}  🍴${forks}  📦${dmg_downloads} 下载  💬${discussions_count} 讨论"

  http_code=$(send_feishu_card "Cabinet GitHub 动态" "blue" "$body")
  if [[ "$http_code" == "200" ]]; then
    echo "$(date): 变化通知已发送 — ${#changes[@]} 项变化"
  else
    echo "$(date): 飞书通知失败 (HTTP $http_code)" >&2
  fi
else
  echo "$(date): 无变化"
fi

# ---------- 定期全量报告（每 5 小时） ----------

if [[ "$need_report" == "true" ]]; then
  report="**📊 Cabinet GitHub 状态报告**\n\n"
  report+="⭐ Stars: ${stars}\n"
  report+="🍴 Forks: ${forks}\n"
  report+="📦 DMG 下载总量: ${dmg_downloads}\n"
  report+="🚀 最新 Release: ${latest_release}\n"
  report+="🐛 Open Issues: ${open_issues}\n"
  report+="💬 Discussions: ${discussions_count}\n"

  if [[ -n "$issue_titles" ]]; then
    report+="\n**Open Issues:**\n${issue_titles}\n"
  fi
  if [[ -n "$discussion_titles" ]]; then
    report+="\n**最新 Discussions:**\n${discussion_titles}\n"
  fi

  report+="\n---\n_定期报告，每 5 小时发送一次_"

  http_code=$(send_feishu_card "Cabinet GitHub 状态报告" "green" "$report")
  if [[ "$http_code" == "200" ]]; then
    echo "$(date): 定期状态报告已发送"
    now_epoch=$(date +%s)  # 刷新时间
  else
    echo "$(date): 定期报告发送失败 (HTTP $http_code)" >&2
  fi
fi

# ---------- 保存状态 ----------
current=$(echo "$current" | jq --argjson lr "$now_epoch" '. + {last_report_at: $lr}')
echo "$current" > "$STATE_FILE"
