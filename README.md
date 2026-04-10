# Agent Workspace - 私人健身教练

通过飞书发送每日健身训练+饮食计划提醒的私人教练工具。

## 功能

- 7 天训练计划自动轮换（胸/背/肩/腿/手臂 + 2天休息）
- 训练日 vs 休息日差异化饮食方案
- 飞书卡片消息格式，结构化展示训练和饮食内容
- 支持自定义 webhook 和指定日期

## 使用

```bash
# 发送今天的计划到飞书
python3 coach/daily_reminder.py

# 指定周几（1=周一 ... 7=周日）
python3 coach/daily_reminder.py --day 1

# 仅输出 JSON，不发送
python3 coach/daily_reminder.py --dry-run

# 自定义 webhook
python3 coach/daily_reminder.py --webhook https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_HOOK_ID
```

## 周训练安排

| 周几 | 训练内容 | 时长 |
|------|---------|------|
| 周一 | 胸 + 三头 | 50min |
| 周二 | 背 + 二头 | 50min |
| 周三 | 休息（主动恢复） | 45min |
| 周四 | 肩 + 核心 | 45min |
| 周五 | 腿 | 55min |
| 周六 | 手臂 + 有氧 | 55min |
| 周日 | 休息（完全休息） | - |
