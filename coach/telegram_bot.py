#!/usr/bin/env python3
"""
私人健身教练 - Telegram Bot 交互服务
长轮询接收用户消息，根据指令和关键词自动回复训练/饮食建议。

用法: python3 coach/telegram_bot.py [--once]  # --once 只处理一轮后退出
"""

import json
import time
import sys
import urllib.request
from datetime import datetime

from coach.daily_reminder import (
    TELEGRAM_API,
    WEEKLY_PLAN,
    MEAL_PLAN,
    build_telegram_text,
)

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def tg_api(method: str, params: dict | None = None) -> dict:
    url = f"{TELEGRAM_API}/{method}"
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def reply(chat_id: int, text: str, parse_mode: str = "Markdown"):
    tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })


# ── 指令处理 ─────────────────────────────────────────────

def handle_start(chat_id: int):
    reply(chat_id, (
        "💪 *你好！我是你的私人健身教练。*\n\n"
        "我可以帮你：\n"
        "📋 /today — 查看今日训练+饮食计划\n"
        "📅 /week — 查看本周训练安排\n"
        "🍽️ /diet — 查看今日饮食方案\n"
        "🔄 /day1 ~ /day7 — 查看指定日计划（1=周一）\n"
        "❓ 直接发消息问我健身/饮食问题\n\n"
        "每天早8点我会自动推送当日计划卡片 🏋️"
    ))


def handle_today(chat_id: int):
    day = datetime.now().isoweekday()
    text = build_telegram_text(day)
    reply(chat_id, text)


def handle_week(chat_id: int):
    lines = ["📅 *本周训练安排*\n"]
    today = datetime.now().isoweekday()
    for d in range(1, 8):
        plan = WEEKLY_PLAN[d]
        is_rest = plan.get("is_rest", False)
        marker = "👈 今天" if d == today else ""
        emoji = "🛋️" if is_rest else "🏋️"
        lines.append(f"{emoji} *{WEEKDAY_NAMES[d-1]}*: {plan['title']} {marker}")
    lines.append("\n发送 /day1 ~ /day7 查看具体某天的计划")
    reply(chat_id, "\n".join(lines))


def handle_diet(chat_id: int):
    day = datetime.now().isoweekday()
    is_rest = WEEKLY_PLAN[day].get("is_rest", False)
    meal = MEAL_PLAN["rest"] if is_rest else MEAL_PLAN["training"]
    text = (
        f"🍽️ *今日饮食方案（目标 {meal['target']}）*\n\n"
        f"{meal['meals'].replace('**', '*')}"
    )
    reply(chat_id, text)


def handle_day_n(chat_id: int, day: int):
    if 1 <= day <= 7:
        text = build_telegram_text(day)
        reply(chat_id, text)
    else:
        reply(chat_id, "请输入 /day1 到 /day7（1=周一，7=周日）")


def handle_help(chat_id: int):
    handle_start(chat_id)


# ── 关键词匹配回复 ────────────────────────────────────────

KEYWORD_RESPONSES = [
    # 训练完成反馈
    (["完成", "练完", "做完", "打卡"], (
        "💯 *太棒了！今天的训练完成得很好！*\n\n"
        "记得：\n"
        "- 30分钟内补充蛋白质（蛋白粉/鸡蛋/鸡胸肉）\n"
        "- 充分补水（至少500ml）\n"
        "- 今晚保证7-8小时睡眠\n\n"
        "明天继续加油 🔥"
    )),
    # 跳过训练
    (["跳过", "不练", "休息", "太累", "没时间"], (
        "没关系，偶尔休息一天不会影响整体进度 👌\n\n"
        "建议今天做些轻度活动：\n"
        "- 散步 20-30 分钟\n"
        "- 简单拉伸 10 分钟\n"
        "- 保持饮食计划不变\n\n"
        "明天回来继续练 💪"
    )),
    # 调整计划
    (["调整", "换一下", "太重", "太轻", "加重", "减重"], (
        "🔧 *计划调整建议*\n\n"
        "如果觉得*太重*：\n"
        "- 每个动作减 10-20% 重量\n"
        "- 保持动作标准最重要\n\n"
        "如果觉得*太轻*：\n"
        "- 每周增加 5-10% 重量\n"
        "- 或增加 1-2 组\n\n"
        "告诉我具体哪个动作需要调整？"
    )),
    # 饮食相关
    (["吃什么", "饮食", "食谱", "热量", "蛋白", "碳水"], None),  # 触发 handle_diet
    # 体重/身体变化
    (["体重", "瘦了", "胖了", "增重", "减重", "变化"], (
        "📊 *关于体重变化*\n\n"
        "- 短期波动（1-2kg）是正常的，受水分和饮食影响\n"
        "- 关注*周平均值*的趋势，而非单日数据\n"
        "- 建议每周同一时间称重（晨起空腹）\n"
        "- 增肌期每周增 0.2-0.5kg 为宜\n"
        "- 减脂期每周降 0.3-0.7kg 为宜\n\n"
        "把你的体重发给我，我帮你记录 📝"
    )),
    # 肌肉酸痛
    (["酸痛", "疼", "痛", "受伤", "不舒服"], (
        "⚠️ *关于身体不适*\n\n"
        "*延迟性肌肉酸痛（DOMS）*是正常的：\n"
        "- 训练后 24-72 小时出现\n"
        "- 轻度拉伸和泡沫轴可缓解\n"
        "- 不影响下一次训练\n\n"
        "*如果是关节疼痛或锐痛*：\n"
        "- 立即停止相关动作\n"
        "- 冰敷 15-20 分钟\n"
        "- 持续超过 3 天请就医\n\n"
        "安全第一！具体是哪里不舒服？"
    )),
    # 补剂
    (["蛋白粉", "补剂", "肌酸", "维生素", "鱼油"], (
        "💊 *补剂建议（优先级排序）*\n\n"
        "1. *乳清蛋白粉* — 训练后补充，方便快捷\n"
        "2. *肌酸*（5g/天）— 提升力量和耐力，性价比最高\n"
        "3. *维生素D* — 大部分人缺乏，影响恢复\n"
        "4. *鱼油* — 抗炎，促进恢复\n\n"
        "以上都不是必需品，优先保证饮食到位 🥩🥚🥦"
    )),
]


def handle_text(chat_id: int, text: str):
    """根据关键词匹配回复"""
    lower = text.lower().strip()

    for keywords, response in KEYWORD_RESPONSES:
        if any(kw in lower for kw in keywords):
            if response is None:
                handle_diet(chat_id)
            else:
                reply(chat_id, response)
            return

    # 默认回复
    reply(chat_id, (
        "我是你的健身教练 🏋️ 试试这些指令：\n\n"
        "/today — 今日计划\n"
        "/week — 本周安排\n"
        "/diet — 今日饮食\n\n"
        "或者直接告诉我：\n"
        "- \"练完了\" → 训练完成反馈\n"
        "- \"太累了\" → 休息建议\n"
        "- \"吃什么\" → 饮食方案\n"
        "- \"酸痛\" → 恢复建议"
    ))


# ── 消息分发 ──────────────────────────────────────────────

def process_message(msg: dict):
    """处理单条消息"""
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if not text:
        return

    # 命令处理
    cmd = text.split()[0].lower()
    if cmd == "/start":
        handle_start(chat_id)
    elif cmd == "/today":
        handle_today(chat_id)
    elif cmd == "/week":
        handle_week(chat_id)
    elif cmd == "/diet":
        handle_diet(chat_id)
    elif cmd == "/help":
        handle_help(chat_id)
    elif cmd.startswith("/day") and len(cmd) == 5 and cmd[4].isdigit():
        handle_day_n(chat_id, int(cmd[4]))
    else:
        handle_text(chat_id, text)


# ── 轮询主循环 ────────────────────────────────────────────

def poll(once: bool = False):
    """长轮询接收消息"""
    offset = None
    print("🤖 私人教练 Telegram Bot 启动，等待消息...")

    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            result = tg_api("getUpdates", params)
            updates = result.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message")
                if msg:
                    user = msg["from"].get("first_name", "?")
                    text = msg.get("text", "")
                    print(f"📩 {user}: {text}")
                    process_message(msg)

            if once:
                break

        except KeyboardInterrupt:
            print("\n👋 Bot 已停止")
            break
        except Exception as e:
            print(f"⚠️ 错误: {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    once = "--once" in sys.argv
    poll(once=once)
