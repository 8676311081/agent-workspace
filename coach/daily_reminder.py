#!/usr/bin/env python3
"""
私人健身教练 - 每日飞书提醒
按周几自动生成对应的训练+饮食计划，发送到飞书 webhook。
用法: python3 coach/daily_reminder.py [--day 1-7] [--webhook URL]
"""

import json
import urllib.request
import argparse
from datetime import datetime

WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/4d3e23b0-6eee-4bdb-83f7-0164f0a3d135"

# 7天训练计划：肌群轮换，周三/日休息
WEEKLY_PLAN = {
    1: {
        "title": "胸 + 三头日（周一）",
        "color": "green",
        "warmup": "- 开合跳 2×30秒\n- 手臂环绕 2×15次\n- 俯卧撑 1×10次（激活胸肌）",
        "workout": (
            "1. 平板杠铃卧推 4×8（60-70kg）\n"
            "2. 上斜哑铃卧推 3×10（20kg）\n"
            "3. 上斜哑铃飞鸟 3×12（12kg）\n"
            "4. 绳索夹胸 3×15\n"
            "5. 窄距卧推 3×10（40kg）\n"
            "6. 绳索下压 3×12\n"
            "7. 仰卧臂屈伸 3×12（10kg）"
        ),
        "stretch": "- 胸部门框拉伸 30秒×2\n- 三头过头拉伸 30秒×2\n- 肩部交叉拉伸 30秒×2",
        "duration": 50,
    },
    2: {
        "title": "背 + 二头日（周二）",
        "color": "blue",
        "warmup": "- 跳绳 2分钟\n- 猫牛式 1×10次\n- 弹力带下拉 2×15次",
        "workout": (
            "1. 引体向上 4×力竭\n"
            "2. 杠铃划船 4×8（50kg）\n"
            "3. 坐姿下拉 3×12\n"
            "4. 单臂哑铃划船 3×10（18kg）\n"
            "5. 杠铃弯举 3×10（25kg）\n"
            "6. 锤式弯举 3×12（12kg）\n"
            "7. 反向飞鸟 3×15"
        ),
        "stretch": "- 背阔肌拉伸 30秒×2\n- 二头前臂拉伸 30秒×2\n- 悬挂放松 30秒",
        "duration": 50,
    },
    3: {
        "title": "休息日 - 主动恢复（周三）",
        "color": "purple",
        "warmup": "",
        "workout": (
            "今天是 **主动恢复日**，不做大重量训练：\n\n"
            "1. 轻度有氧（散步/骑车）30分钟\n"
            "2. 全身泡沫轴放松 15分钟\n"
            "3. 静态拉伸 15分钟\n"
            "4. 可选：瑜伽/冥想 20分钟"
        ),
        "stretch": "",
        "duration": 45,
        "is_rest": True,
    },
    4: {
        "title": "肩 + 核心日（周四）",
        "color": "orange",
        "warmup": "- 手臂环绕 2×15次\n- 弹力带外旋 2×15次\n- 肩部 YTW 1×8次",
        "workout": (
            "1. 站姿杠铃推举 4×8（35kg）\n"
            "2. 哑铃侧平举 4×12（8kg）\n"
            "3. 俯身哑铃飞鸟 3×12（8kg）\n"
            "4. 哑铃前平举 3×12（8kg）\n"
            "5. 面拉 3×15\n"
            "6. 悬垂举腿 3×12\n"
            "7. 平板支撑 3×45秒"
        ),
        "stretch": "- 肩部交叉拉伸 30秒×2\n- 颈部侧拉伸 30秒×2\n- 婴儿式 30秒",
        "duration": 45,
    },
    5: {
        "title": "腿日（周五）",
        "color": "red",
        "warmup": "- 动态弓步 2×10次\n- 空蹲 2×15次\n- 臀桥 2×15次",
        "workout": (
            "1. 杠铃深蹲 4×8（70kg）\n"
            "2. 罗马尼亚硬拉 4×8（60kg）\n"
            "3. 腿举 3×12\n"
            "4. 保加利亚分腿蹲 3×10（每侧）\n"
            "5. 腿弯举 3×12\n"
            "6. 坐姿腿屈伸 3×15\n"
            "7. 提踵 4×15"
        ),
        "stretch": "- 股四头肌拉伸 30秒×2\n- 腘绳肌拉伸 30秒×2\n- 臀部鸽子式 30秒×2\n- 小腿拉伸 30秒×2",
        "duration": 55,
    },
    6: {
        "title": "手臂 + 有氧日（周六）",
        "color": "turquoise",
        "warmup": "- 跳绳 3分钟\n- 手腕环绕 1×20次\n- 轻重量弯举 1×15次",
        "workout": (
            "**Part A - 手臂（25分钟）**\n"
            "1. EZ杠弯举 3×10（20kg）\n"
            "2. 碎颅者 3×10（15kg）\n"
            "3. 交替哑铃弯举 3×12（10kg）\n"
            "4. 绳索下压 3×12\n"
            "5. 集中弯举 2×12（8kg）\n\n"
            "**Part B - 有氧（25分钟）**\n"
            "1. 跑步机/椭圆机 HIIT：30秒冲刺 + 90秒恢复 × 8轮\n"
            "2. 跳绳 3×2分钟"
        ),
        "stretch": "- 前臂拉伸 30秒×2\n- 三头拉伸 30秒×2\n- 全身放松拉伸 3分钟",
        "duration": 55,
    },
    7: {
        "title": "休息日 - 完全休息（周日）",
        "color": "purple",
        "warmup": "",
        "workout": (
            "今天是 **完全休息日**，让身体充分恢复：\n\n"
            "1. 充足睡眠（7-9小时）\n"
            "2. 轻度散步 20-30分钟\n"
            "3. 全身泡沫轴 10分钟（可选）\n"
            "4. 准备下周训练装备和食材"
        ),
        "stretch": "",
        "duration": 0,
        "is_rest": True,
    },
}

# 饮食方案：训练日 vs 休息日
MEAL_PLAN = {
    "training": {
        "target": "2200kcal / 蛋白质 150g",
        "meals": (
            "☀️ **早餐** (450kcal)\n"
            "鸡蛋3个 + 全麦吐司2片 + 牛奶250ml\n\n"
            "🌤️ **午餐** (550kcal)\n"
            "鸡胸肉200g + 糙米150g + 西兰花200g\n\n"
            "🍌 **训练后加餐** (280kcal)\n"
            "香蕉1根 + 乳清蛋白粉1勺（训练后30min内）\n\n"
            "🌙 **晚餐** (520kcal)\n"
            "三文鱼150g + 紫薯200g + 生菜沙拉\n\n"
            "🥜 **睡前** (200kcal)\n"
            "希腊酸奶150g + 核桃3颗\n\n"
            "💧 **喝水目标**: 2.5L（训练中至少500ml）"
        ),
    },
    "rest": {
        "target": "1800kcal / 蛋白质 130g",
        "meals": (
            "☀️ **早餐** (380kcal)\n"
            "鸡蛋2个 + 燕麦粥200ml + 蓝莓50g\n\n"
            "🌤️ **午餐** (500kcal)\n"
            "牛肉150g + 荞麦面100g + 时蔬200g\n\n"
            "🍎 **加餐** (150kcal)\n"
            "苹果1个 + 杏仁10颗\n\n"
            "🌙 **晚餐** (470kcal)\n"
            "虾仁150g + 豆腐100g + 菠菜200g + 糙米80g\n\n"
            "💧 **喝水目标**: 2L"
        ),
    },
}


def build_card(day_of_week: int) -> dict:
    """根据周几生成飞书卡片消息。day_of_week: 1=周一 ... 7=周日"""
    plan = WEEKLY_PLAN[day_of_week]
    is_rest = plan.get("is_rest", False)
    meal = MEAL_PLAN["rest"] if is_rest else MEAL_PLAN["training"]

    elements = []

    # 训练日：热身 + 正式训练 + 拉伸
    if not is_rest:
        elements.append({"tag": "markdown", "content": f"**🔥 热身（5分钟）**\n{plan['warmup']}"})
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": f"**💪 正式训练（约{plan['duration']}分钟）**\n{plan['workout']}"})
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": f"**🧘 拉伸（5分钟）**\n{plan['stretch']}"})
    else:
        # 休息日
        elements.append({"tag": "markdown", "content": plan["workout"]})

    elements.append({"tag": "hr"})

    # 饮食方案
    elements.append({
        "tag": "markdown",
        "content": f"**🍽️ 今日饮食（目标 {meal['target']}）**\n\n{meal['meals']}",
    })

    # 训练日额外提示
    if not is_rest:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": (
                "⏰ **训练提示**\n"
                "- 组间休息60-90秒\n"
                "- 注意动作标准，控制离心阶段\n"
                "- 每组最后2次应感到吃力但能完成\n"
                "- 训练后30分钟内补充蛋白质"
            ),
        })

    emoji = "🛋️" if is_rest else "🏋️"
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{emoji} {plan['title']}"},
            "template": plan["color"],
        },
        "elements": elements,
    }
    return {"msg_type": "interactive", "card": card}


def send_to_feishu(webhook_url: str, payload: dict) -> dict:
    """发送卡片消息到飞书 webhook"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="私人教练 - 每日飞书健身提醒")
    parser.add_argument(
        "--day",
        type=int,
        choices=range(1, 8),
        default=None,
        help="指定周几 (1=周一..7=周日)，默认自动检测",
    )
    parser.add_argument(
        "--webhook",
        type=str,
        default=WEBHOOK_URL,
        help="飞书 webhook URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出卡片 JSON，不发送",
    )
    args = parser.parse_args()

    day = args.day or datetime.now().isoweekday()  # 1=Mon..7=Sun
    payload = build_card(day)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    result = send_to_feishu(args.webhook, payload)
    status = "✅ 发送成功" if result.get("code") == 0 else f"❌ 发送失败: {result}"
    plan_title = WEEKLY_PLAN[day]["title"]
    print(f"{status} | {plan_title}")


if __name__ == "__main__":
    main()
