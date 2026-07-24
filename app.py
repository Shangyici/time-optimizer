"""时间优化器 Pro – Streamlit chat app with Strands Agents SDK.

升级版功能:
- 可编辑课程表（课程内容和时段）
- 可选学习效率类型
- 周视图热力图（一眼看全周忙闲）
- 学习连续打卡记录（streak tracker）
- 专注数据分析面板
- 艾宾浩斯遗忘曲线复习提醒
- Tool 1: 智能学习时段优化器（课程表+效率+优先级）
- Tool 2: 反拖延计划生成器（日历+番茄钟+奖励系统）
- Tool 3: 智能任务优先级排序（Eisenhower矩阵）
- Tool 4: 艾宾浩斯复习计划生成器
- 内置番茄钟（可自定义时长）
"""

import json
import datetime
import os
import streamlit as st
from strands import Agent, tool

# ---------------------------------------------------------------------------
# Load AWS credentials from Streamlit secrets (for cloud deployment)
# ---------------------------------------------------------------------------

if hasattr(st, "secrets"):
    for key in ["AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]:
        if key in st.secrets:
            os.environ[key] = st.secrets[key]

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="时间优化器 Pro", page_icon="⏰", layout="wide")

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .stApp { }
    .heatmap-cell {
        display: inline-block;
        width: 60px;
        height: 35px;
        margin: 2px;
        border-radius: 5px;
        text-align: center;
        line-height: 35px;
        font-size: 0.7em;
        color: white;
        font-weight: bold;
    }
    .streak-badge {
        background: linear-gradient(135deg, #f093fb, #f5576c);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        margin: 5px;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "timetable" not in st.session_state:
    st.session_state.timetable = {
        "周一": [
            {"course": "高等数学", "start": "08:00", "end": "10:00", "type": "讲座"},
            {"course": "数据结构", "start": "14:00", "end": "16:00", "type": "实验"},
        ],
        "周二": [
            {"course": "英语", "start": "10:00", "end": "12:00", "type": "讲座"},
            {"course": "物理", "start": "14:00", "end": "16:00", "type": "讲座"},
        ],
        "周三": [
            {"course": "高等数学", "start": "08:00", "end": "10:00", "type": "讲座"},
            {"course": "编程实践", "start": "13:00", "end": "15:00", "type": "实验"},
        ],
        "周四": [
            {"course": "数据结构", "start": "10:00", "end": "12:00", "type": "讲座"},
            {"course": "英语", "start": "15:00", "end": "17:00", "type": "研讨"},
        ],
        "周五": [
            {"course": "物理", "start": "08:00", "end": "10:00", "type": "实验"},
            {"course": "编程实践", "start": "14:00", "end": "16:00", "type": "讲座"},
        ],
    }

if "efficiency_profile" not in st.session_state:
    st.session_state.efficiency_profile = "均衡型（上午+晚间）"

if "pomodoro_active" not in st.session_state:
    st.session_state.pomodoro_active = False

if "pomodoro_task" not in st.session_state:
    st.session_state.pomodoro_task = ""

if "study_streak" not in st.session_state:
    st.session_state.study_streak = {
        "current_streak": 0,
        "longest_streak": 0,
        "total_sessions": 0,
        "total_minutes": 0,
        "history": [],  # list of {"date": "YYYY-MM-DD", "minutes": int, "tasks": [...]}
    }

if "focus_log" not in st.session_state:
    st.session_state.focus_log = []  # list of {"date", "start_time", "duration", "task", "completed"}

if "review_items" not in st.session_state:
    st.session_state.review_items = []  # list of {"subject", "learned_date", "next_review", "review_count"}

# ---------------------------------------------------------------------------
# Efficiency Profiles
# ---------------------------------------------------------------------------

EFFICIENCY_PROFILES = {
    "早起型（早晨高效）": {
        "06:00-08:00": 0.85, "08:00-10:00": 1.0, "10:00-12:00": 0.9,
        "12:00-14:00": 0.4, "14:00-16:00": 0.6, "16:00-18:00": 0.5,
        "18:00-20:00": 0.4, "20:00-22:00": 0.5, "22:00-24:00": 0.3,
    },
    "夜猫型（晚间高效）": {
        "06:00-08:00": 0.3, "08:00-10:00": 0.5, "10:00-12:00": 0.6,
        "12:00-14:00": 0.4, "14:00-16:00": 0.7, "16:00-18:00": 0.75,
        "18:00-20:00": 0.8, "20:00-22:00": 1.0, "22:00-24:00": 0.9,
    },
    "均衡型（上午+晚间）": {
        "06:00-08:00": 0.5, "08:00-10:00": 0.85, "10:00-12:00": 0.95,
        "12:00-14:00": 0.4, "14:00-16:00": 0.75, "16:00-18:00": 0.65,
        "18:00-20:00": 0.5, "20:00-22:00": 0.85, "22:00-24:00": 0.55,
    },
    "下午型（午后高效）": {
        "06:00-08:00": 0.4, "08:00-10:00": 0.6, "10:00-12:00": 0.7,
        "12:00-14:00": 0.5, "14:00-16:00": 1.0, "16:00-18:00": 0.95,
        "18:00-20:00": 0.7, "20:00-22:00": 0.6, "22:00-24:00": 0.4,
    },
}

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def get_week_heatmap_data():
    """Generate heatmap data showing busy/free hours across the week."""
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    hours = list(range(6, 24))
    heatmap = {}
    for day in days:
        heatmap[day] = {}
        classes = st.session_state.timetable.get(day, [])
        for h in hours:
            occupied = False
            for cls in classes:
                start_h = int(cls["start"].split(":")[0])
                end_h = int(cls["end"].split(":")[0])
                if start_h <= h < end_h:
                    occupied = True
                    break
            heatmap[day][h] = "class" if occupied else "free"
    return heatmap


def get_ebbinghaus_intervals():
    """Return review intervals based on Ebbinghaus forgetting curve."""
    return [1, 2, 4, 7, 15, 30]  # days after learning


def calculate_next_review(learned_date_str, review_count):
    """Calculate next review date based on review count."""
    intervals = get_ebbinghaus_intervals()
    if review_count >= len(intervals):
        return None  # mastered
    learned = datetime.datetime.strptime(learned_date_str, "%Y-%m-%d").date()
    delta = sum(intervals[:review_count + 1])
    return (learned + datetime.timedelta(days=delta)).strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------------------------


def create_tools():
    """Create tools with access to current session state."""

    timetable_data = json.dumps(st.session_state.timetable, ensure_ascii=False)
    efficiency_type = st.session_state.efficiency_profile
    efficiency_data = EFFICIENCY_PROFILES.get(
        efficiency_type, EFFICIENCY_PROFILES["均衡型（上午+晚间）"]
    )
    streak_data = st.session_state.study_streak
    review_items = st.session_state.review_items

    @tool
    def optimize_study_schedule(day: str, subjects: list[str], hours_available: float) -> str:
        """分析课程表和个人学习效率，安排最佳学习时段。

        结合指定日期的课程安排和用户效率曲线（早起型/夜猫型/均衡型/下午型），
        智能推荐最优学习时段。高效时段安排高难度科目，低效时段安排轻松复习。
        还会结合艾宾浩斯复习提醒。

        Args:
            day: 星期几，如"周一"到"周日"。
            subjects: 需要学习的科目列表。
            hours_available: 可用于学习的总小时数。

        Returns:
            详细的学习时段安排建议。
        """
        timetable = json.loads(timetable_data)
        day_classes = timetable.get(day, [])

        occupied_hours = set()
        for cls in day_classes:
            start_h = int(cls["start"].split(":")[0])
            end_h = int(cls["end"].split(":")[0])
            for h in range(start_h, end_h):
                occupied_hours.add(h)

        free_slots = []
        for slot_range, eff in efficiency_data.items():
            start_h = int(slot_range.split("-")[0].split(":")[0])
            end_h = int(slot_range.split("-")[1].split(":")[0])
            slot_hours = set(range(start_h, end_h))
            if not slot_hours.intersection(occupied_hours):
                free_slots.append({
                    "time": slot_range,
                    "efficiency": eff,
                    "duration": end_h - start_h,
                })

        free_slots.sort(key=lambda x: x["efficiency"], reverse=True)

        lines = [
            f"📅 {day} 学习时段优化方案",
            f"📊 效率类型: {efficiency_type}",
            f"🔥 当前连续学习天数: {streak_data['current_streak']} 天",
            "",
            f"当日课程: {', '.join(c['course'] + '(' + c['start'] + '-' + c['end'] + ')' for c in day_classes) if day_classes else '无课程'}",
            f"可用学习时间: {hours_available} 小时",
            f"待学习科目: {', '.join(subjects)}",
            "",
            "🎯 推荐学习安排（按效率优先）:",
            "",
        ]

        remaining = hours_available
        subject_idx = 0

        for slot in free_slots:
            if remaining <= 0:
                break
            if subject_idx >= len(subjects):
                subject_idx = 0

            allocated = min(slot["duration"], remaining)
            subject = subjects[subject_idx]
            eff = slot["efficiency"]

            if eff >= 0.85:
                tag = "🔴 高效 → 深度学习/难题攻克"
            elif eff >= 0.65:
                tag = "🟡 中效 → 练习和应用"
            else:
                tag = "🟢 低效 → 轻松复习/整理"

            lines.append(f"  ⏰ {slot['time']} | 效率: {eff:.0%} | {tag}")
            lines.append(f"     📖 {subject}（{allocated:.1f}h）")
            pomodoros = int(allocated * 60 / 25)
            lines.append(f"     🍅 建议 {pomodoros} 个番茄钟")
            lines.append("")

            remaining -= allocated
            subject_idx += 1

        if remaining > 0:
            lines.append(f"⚠️ 还有 {remaining:.1f}h 未安排，建议调整或分配到其他天")

        # Check for review reminders
        today = datetime.date.today().strftime("%Y-%m-%d")
        due_reviews = [r for r in review_items if r.get("next_review") == today]
        if due_reviews:
            lines.append("")
            lines.append("📝 今日艾宾浩斯复习提醒:")
            for r in due_reviews:
                lines.append(f"  🔔 {r['subject']}（第{r['review_count']+1}次复习）")

        lines.extend([
            "", "─" * 35, "",
            "💡 建议:", "  • 每45分钟休息10分钟",
            "  • 完成后记得在侧边栏打卡！",
            "  • 新学内容记得添加到复习计划中",
        ])

        return "\n".join(lines)

    @tool
    def anti_procrastination_plan(tasks: list[str], deadlines: list[str], procrastination_type: str) -> str:
        """结合日历、效率曲线和奖励系统制定反拖延计划。

        生成包含微任务分解、时间节点、番茄钟建议和积分奖励的执行计划。
        支持拖延类型：完美主义型、逃避型、决策困难型、刺激依赖型。

        Args:
            tasks: 任务列表，如["完成数学作业", "写论文初稿"]。
            deadlines: 对应截止日期，如["周三", "下周一"]。
            procrastination_type: 拖延类型。如不确定填"未知"。

        Returns:
            个性化反拖延执行计划。
        """
        strategies = {
            "完美主义型": {
                "issue": "害怕做得不够好，迟迟不开始",
                "tips": [
                    "设'足够好'标准，不追求完美",
                    "先完成再完善 — 允许糟糕的初稿",
                    "5分钟启动法：只承诺做5分钟",
                    "80%即可，迭代改进",
                ],
                "reward": "完成初稿 → 奖励自己看一集剧",
            },
            "逃避型": {
                "issue": "任务让你焦虑，选择回避",
                "tips": [
                    "拆成2-5分钟极小步骤",
                    "瑞士奶酪法：随机完成任何小部分",
                    "改变环境：图书馆，关通知",
                    "每步完成给自己小奖励",
                ],
                "reward": "完成3个小步骤 → 吃点喜欢的零食",
            },
            "决策困难型": {
                "issue": "选择太多不知从何下手",
                "tips": [
                    "2分钟规则：能2分钟做完的立刻做",
                    "前一晚定TOP 3任务",
                    "不想，直接开番茄钟",
                    "固定顺序减少决策消耗",
                ],
                "reward": "完成TOP 1任务 → 奖励30分钟自由时间",
            },
            "刺激依赖型": {
                "issue": "只有deadline压力下才能行动",
                "tips": [
                    "设假deadline（提前2天）",
                    "找问责伙伴每天汇报",
                    "大deadline拆成多个checkpoint",
                    "用倒计时增加紧迫感",
                ],
                "reward": "提前完成 → 给自己一天完全自由",
            },
            "未知": {
                "issue": "尚未明确拖延类型",
                "tips": ["5分钟启动法", "拆最小步骤", "设25分钟番茄钟", "完成后休息5分钟"],
                "reward": "完成一个番茄钟 → 奖励5分钟手机时间",
            },
        }

        strategy = strategies.get(procrastination_type, strategies["未知"])
        sorted_slots = sorted(efficiency_data.items(), key=lambda x: x[1], reverse=True)
        top_slots = sorted_slots[:3]

        lines = [
            "🚀 反拖延执行计划 + 奖励系统",
            "",
            f"📊 效率类型: {efficiency_type}",
            f"😈 拖延类型: {procrastination_type}",
            f"   → {strategy['issue']}",
            f"🎁 完成奖励: {strategy['reward']}",
            "",
            "═" * 40,
            "",
            "📅 最佳执行时段（基于效率曲线）:",
        ]
        for slot, eff in top_slots:
            lines.append(f"  ⭐ {slot}（效率 {eff:.0%}）")

        lines.extend(["", "─" * 40, ""])

        total_pomodoros = 0
        for i, (t, d) in enumerate(zip(tasks, deadlines), 1):
            pomodoros = max(2, min(10, len(t) // 2 + 2))
            total_pomodoros += pomodoros
            lines.append(f"📋 任务 {i}: {t}")
            lines.append(f"   ⏰ 截止: {d}")
            lines.append(f"   🍅 预计: {pomodoros} 个番茄钟（{pomodoros * 25}分钟）")
            lines.append(f"   📐 微任务分解:")
            lines.append(f"      1️⃣ 打开材料浏览2分钟（启动仪式）")
            lines.append(f"      2️⃣ 列子步骤清单（5分钟）")
            lines.append(f"      3️⃣ 第一个番茄钟：最小可交付单元")
            lines.append(f"      4️⃣ 每天1-2个番茄钟推进")
            lines.append(f"      5️⃣ 提交前检查")
            lines.append("")

        lines.extend([
            "═" * 40, "",
            f"📊 总计需要: {total_pomodoros} 个番茄钟（约 {total_pomodoros * 25 / 60:.1f} 小时）",
            "",
            "🧠 个性化策略:",
        ])
        for tip in strategy["tips"]:
            lines.append(f"  ✅ {tip}")

        lines.extend([
            "", "─" * 40, "",
            "🏆 积分奖励系统:",
            "  • 完成1个番茄钟 = +10分",
            "  • 连续3天学习 = +50分 BONUS",
            "  • 提前完成任务 = +100分",
            "  • 累计100分 → 兑换一次大奖励！",
            "",
            "👇 点击侧边栏「启动番茄钟」开始执行！",
            "💪 开始是最难的，只做5分钟！",
        ])

        return "\n".join(lines)

    @tool
    def smart_prioritize(tasks: list[str], urgencies: list[str], importances: list[str]) -> str:
        """使用艾森豪威尔矩阵智能排序任务优先级。

        将任务按照紧急程度和重要程度分为四个象限，给出执行顺序建议。

        Args:
            tasks: 任务列表。
            urgencies: 每个任务的紧急程度，"高"或"低"。
            importances: 每个任务的重要程度，"高"或"低"。

        Returns:
            按优先级排序的任务执行建议。
        """
        quadrants = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}

        for t, u, imp in zip(tasks, urgencies, importances):
            if u == "高" and imp == "高":
                quadrants["Q1"].append(t)
            elif u == "低" and imp == "高":
                quadrants["Q2"].append(t)
            elif u == "高" and imp == "低":
                quadrants["Q3"].append(t)
            else:
                quadrants["Q4"].append(t)

        lines = [
            "🎯 艾森豪威尔矩阵 - 智能优先级排序",
            "",
            "┌─────────────────────────────────────────┐",
            "│         紧急              不紧急          │",
            "├─────────────────────────────────────────┤",
            "│ 重要  Q1:立即做        Q2:计划做         │",
            "│ 不重要 Q3:委托/快速做   Q4:考虑删除       │",
            "└─────────────────────────────────────────┘",
            "",
        ]

        if quadrants["Q1"]:
            lines.append("🔴 Q1 - 紧急且重要（立即执行）:")
            for t in quadrants["Q1"]:
                lines.append(f"  🚨 {t}")
            lines.append("")

        if quadrants["Q2"]:
            lines.append("🟡 Q2 - 重要不紧急（安排计划）:")
            for t in quadrants["Q2"]:
                lines.append(f"  📋 {t}")
            lines.append("")

        if quadrants["Q3"]:
            lines.append("🟠 Q3 - 紧急不重要（快速处理或委托）:")
            for t in quadrants["Q3"]:
                lines.append(f"  ⚡ {t}")
            lines.append("")

        if quadrants["Q4"]:
            lines.append("⚪ Q4 - 不紧急不重要（考虑是否需要做）:")
            for t in quadrants["Q4"]:
                lines.append(f"  🗑️ {t}")
            lines.append("")

        lines.extend([
            "─" * 35, "",
            "📌 执行建议:",
            "  1. 先清空 Q1（消除压力源）",
            "  2. 主要精力放 Q2（长期成长）",
            "  3. Q3 快速处理不纠结",
            "  4. Q4 大胆删除或推迟",
            "",
            f"  ⏱️ 按你的效率曲线（{efficiency_type}），",
            f"  建议在高效时段处理 Q1+Q2 任务！",
        ])

        return "\n".join(lines)

    @tool
    def spaced_repetition_plan(subjects: list[str], learned_date: str) -> str:
        """基于艾宾浩斯遗忘曲线生成间隔复习计划。

        根据学习日期和科目，自动计算最佳复习时间点（1天、2天、4天、7天、15天、30天后）。

        Args:
            subjects: 需要复习的科目或知识点列表。
            learned_date: 学习日期，格式"YYYY-MM-DD"，如"2026-07-24"。

        Returns:
            完整的艾宾浩斯间隔复习计划。
        """
        intervals = get_ebbinghaus_intervals()

        try:
            base_date = datetime.datetime.strptime(learned_date, "%Y-%m-%d").date()
        except ValueError:
            base_date = datetime.date.today()

        lines = [
            "🧠 艾宾浩斯间隔复习计划",
            "",
            f"📚 科目: {', '.join(subjects)}",
            f"📅 学习日期: {base_date.strftime('%Y-%m-%d')}",
            "",
            "─" * 40,
            "",
            "📈 遗忘曲线复习时间表:",
            "",
            "  记忆保持率:",
            "  100%|■■■■■■■■■■",
            "   80%|■■■■■■■■░░  ← 第1次复习（1天后）",
            "   60%|■■■■■■░░░░  ← 第2次复习（3天后）",
            "   40%|■■■■░░░░░░  ← 第3次复习（7天后）",
            "   20%|■■░░░░░░░░  ← 不复习将遗忘大部分",
            "",
            "─" * 40,
            "",
            "📋 具体复习日程:",
            "",
        ]

        cumulative = 0
        for i, interval in enumerate(intervals, 1):
            cumulative += interval
            review_date = base_date + datetime.timedelta(days=cumulative)
            emoji = "✅" if review_date <= datetime.date.today() else "📌"
            lines.append(f"  {emoji} 第{i}次复习: {review_date.strftime('%Y-%m-%d')}（{cumulative}天后）")
            lines.append(f"     复习内容: {', '.join(subjects)}")
            if i <= 2:
                lines.append(f"     方式: 详细回顾 + 做练习题")
            elif i <= 4:
                lines.append(f"     方式: 快速浏览 + 关键点默写")
            else:
                lines.append(f"     方式: 概念检测 + 查漏补缺")
            lines.append("")

        lines.extend([
            "─" * 35, "",
            "💡 复习技巧:",
            "  • 复习前先尝试回忆（主动检索）",
            "  • 用自己的话复述知识点",
            "  • 结合思维导图整理关系",
            "  • 每次复习后在侧边栏标记完成",
            "",
            "🔔 提示: 已添加到复习提醒系统！",
        ])

        return "\n".join(lines)

    return [optimize_study_schedule, anti_procrastination_plan, smart_prioritize, spaced_repetition_plan]

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ 控制面板")

    # --- Efficiency Profile ---
    st.subheader("📊 学习效率类型")
    st.session_state.efficiency_profile = st.selectbox(
        "选择效率类型:",
        options=list(EFFICIENCY_PROFILES.keys()),
        index=list(EFFICIENCY_PROFILES.keys()).index(st.session_state.efficiency_profile),
    )

    profile = EFFICIENCY_PROFILES[st.session_state.efficiency_profile]
    with st.expander("📈 查看效率曲线"):
        for slot, eff in profile.items():
            bar = "█" * int(eff * 10) + "░" * (10 - int(eff * 10))
            st.text(f"{slot} {bar} {eff:.0%}")

    st.markdown("---")

    # --- Study Streak ---
    st.subheader("🔥 学习打卡")
    streak = st.session_state.study_streak

    col1, col2 = st.columns(2)
    with col1:
        st.metric("连续天数", f"{streak['current_streak']}天", 
                  delta=f"最长{streak['longest_streak']}天")
    with col2:
        st.metric("总学习时长", f"{streak['total_minutes']}分钟",
                  delta=f"{streak['total_sessions']}次")

    checkin_minutes = st.number_input("今日学习时长(分钟):", min_value=5, max_value=480, value=25, step=5)
    if st.button("✅ 今日打卡", key="checkin_btn", type="primary"):
        today = datetime.date.today().strftime("%Y-%m-%d")
        history = streak["history"]
        # Check if already checked in today
        if history and history[-1]["date"] == today:
            history[-1]["minutes"] += checkin_minutes
        else:
            # Check streak continuity
            if history:
                last_date = datetime.datetime.strptime(history[-1]["date"], "%Y-%m-%d").date()
                if (datetime.date.today() - last_date).days == 1:
                    streak["current_streak"] += 1
                elif (datetime.date.today() - last_date).days > 1:
                    streak["current_streak"] = 1
            else:
                streak["current_streak"] = 1

            history.append({"date": today, "minutes": checkin_minutes, "tasks": []})

        streak["total_sessions"] += 1
        streak["total_minutes"] += checkin_minutes
        streak["longest_streak"] = max(streak["longest_streak"], streak["current_streak"])
        st.success(f"🎉 打卡成功！连续 {streak['current_streak']} 天！+{checkin_minutes}分钟")
        st.rerun()

    st.markdown("---")

    # --- Timetable Editor ---
    st.subheader("📚 课程表编辑")

    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    selected_day = st.selectbox("编辑日期:", days)

    if selected_day not in st.session_state.timetable:
        st.session_state.timetable[selected_day] = []

    day_courses = st.session_state.timetable[selected_day]

    if day_courses:
        for i, cls in enumerate(day_courses):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"  {cls['course']} {cls['start']}-{cls['end']}")
            with col2:
                if st.button("❌", key=f"del_{selected_day}_{i}"):
                    day_courses.pop(i)
                    st.rerun()
    else:
        st.caption(f"{selected_day} 暂无课程")

    with st.expander("➕ 添加课程"):
        new_course = st.text_input("课程名称", key="new_course_name")
        col1, col2 = st.columns(2)
        with col1:
            new_start = st.selectbox("开始", [f"{h:02d}:00" for h in range(6, 23)], key="new_start")
        with col2:
            new_end = st.selectbox("结束", [f"{h:02d}:00" for h in range(7, 24)], index=2, key="new_end")
        new_type = st.selectbox("类型", ["讲座", "实验", "研讨", "辅导"], key="new_type")

        if st.button("添加", key="add_course_btn"):
            if new_course.strip():
                day_courses.append({
                    "course": new_course.strip(),
                    "start": new_start,
                    "end": new_end,
                    "type": new_type,
                })
                st.rerun()

    st.markdown("---")

    # --- Spaced Repetition Manager ---
    st.subheader("🧠 复习提醒")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    due_items = [r for r in st.session_state.review_items if r.get("next_review") == today_str]

    if due_items:
        st.warning(f"📢 今日有 {len(due_items)} 项需要复习！")
        for item in due_items:
            st.write(f"  🔔 {item['subject']}（第{item['review_count']+1}次）")
    else:
        st.caption("今日无复习任务 ✨")

    with st.expander("➕ 添加复习项"):
        review_subject = st.text_input("知识点/科目:", key="review_subject")
        review_date = st.date_input("学习日期:", value=datetime.date.today(), key="review_date")
        if st.button("添加到复习计划", key="add_review"):
            if review_subject.strip():
                date_str = review_date.strftime("%Y-%m-%d")
                next_rev = calculate_next_review(date_str, 0)
                st.session_state.review_items.append({
                    "subject": review_subject.strip(),
                    "learned_date": date_str,
                    "next_review": next_rev,
                    "review_count": 0,
                })
                st.success(f"已添加！下次复习: {next_rev}")
                st.rerun()

    if st.session_state.review_items:
        with st.expander(f"📋 全部复习项（{len(st.session_state.review_items)}个）"):
            for i, item in enumerate(st.session_state.review_items):
                col1, col2 = st.columns([3, 1])
                with col1:
                    status = "✅" if item.get("next_review") is None else f"下次: {item['next_review']}"
                    st.text(f"  {item['subject']} | {status}")
                with col2:
                    if item.get("next_review") and st.button("完成", key=f"rev_done_{i}"):
                        item["review_count"] += 1
                        item["next_review"] = calculate_next_review(
                            item["learned_date"], item["review_count"]
                        )
                        st.rerun()

    st.markdown("---")

    # --- Pomodoro Timer ---
    st.subheader("🍅 番茄钟")

    pomodoro_task = st.text_input(
        "专注任务:",
        value=st.session_state.pomodoro_task,
        placeholder="输入任务...",
        key="pomodoro_input",
    )
    st.session_state.pomodoro_task = pomodoro_task

    pomodoro_minutes = st.select_slider(
        "时长（分钟）:",
        options=[15, 20, 25, 30, 45, 50, 60],
        value=25,
    )

    if st.button("▶️ 启动番茄钟", key="start_pomodoro", type="primary"):
        st.session_state.pomodoro_active = True
        st.session_state.pomodoro_minutes = pomodoro_minutes

    if st.session_state.pomodoro_active:
        timer_minutes = st.session_state.get("pomodoro_minutes", 25)
        timer_html = f"""
        <div id="pomodoro-timer" style="
            text-align: center;
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white; padding: 20px; border-radius: 15px;
            margin: 10px 0; font-family: 'Courier New', monospace;
        ">
            <div style="font-size: 2.2em; font-weight: bold;" id="timer-display">
                {timer_minutes:02d}:00
            </div>
            <div style="font-size: 0.85em; margin-top: 5px;">
                🎯 {st.session_state.pomodoro_task or '专注中'}
            </div>
            <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">
                📵 请勿打扰
            </div>
        </div>
        <script>
            (function() {{
                let totalSeconds = {timer_minutes * 60};
                const display = document.getElementById('timer-display');
                const timerDiv = document.getElementById('pomodoro-timer');
                function updateDisplay() {{
                    const m = Math.floor(totalSeconds / 60);
                    const s = totalSeconds % 60;
                    display.textContent = String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
                }}
                const interval = setInterval(function() {{
                    totalSeconds--;
                    updateDisplay();
                    if (totalSeconds <= 0) {{
                        clearInterval(interval);
                        display.textContent = "✅ 完成!";
                        timerDiv.style.background = "linear-gradient(135deg, #2ecc71, #27ae60)";
                    }}
                }}, 1000);
            }})();
        </script>
        """
        st.components.v1.html(timer_html, height=120)

        if st.button("⏹️ 停止", key="stop_pomodoro"):
            st.session_state.pomodoro_active = False
            st.rerun()

# ---------------------------------------------------------------------------
# Main Area: Tabs (Chat / Weekly Heatmap / Focus Analytics)
# ---------------------------------------------------------------------------

st.title("⏰ 时间优化器 Pro")

tab_chat, tab_heatmap, tab_analytics = st.tabs(["💬 AI助手", "📅 周视图热力图", "📊 专注数据"])

# ---------------------------------------------------------------------------
# Tab 1: Chat
# ---------------------------------------------------------------------------

with tab_chat:
    # Quick stats banner (fills the empty space before chat starts)
    if not st.session_state.messages:
        streak = st.session_state.study_streak
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        due_reviews = [r for r in st.session_state.review_items if r.get("next_review") == today_str]

        # Welcome dashboard
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔥 连续学习", f"{streak['current_streak']}天")
        with col2:
            st.metric("🍅 总专注", f"{streak['total_sessions']}次")
        with col3:
            points = streak["total_sessions"] * 10 + streak["current_streak"] * 5
            st.metric("🏆 积分", f"{points}分")
        with col4:
            st.metric("🔔 待复习", f"{len(due_reviews)}项")

        st.markdown("---")

        # Quick action hints in columns
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            **🎯 试试问我:**
            - 周一3小时空闲学高数和英语
            - 帮我排一下任务优先级
            - 我学了线性代数，制定复习计划
            """)
        with c2:
            st.markdown("""
            **😈 拖延症？问我:**
            - 论文下周交但我总拖延
            - 我是完美主义型，帮我制定计划
            - 有5个任务不知从何下手
            """)

        st.markdown("---")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("例如: 周一3小时空闲学高数和英语 / 我总拖延怎么办 / 帮我排任务优先级"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("正在思考..."):
                tools = create_tools()
                agent = Agent(
                    tools=tools,
                    model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    system_prompt=(
                        "你是'时间优化器 Pro'，专业AI时间管理助手。\n\n"
                        "可用工具:\n"
                        "1. optimize_study_schedule - 学习安排/空闲时间/课表相关\n"
                        "2. anti_procrastination_plan - 拖延/deadline/计划相关\n"
                        "3. smart_prioritize - 任务排序/优先级/多任务选择相关\n"
                        "4. spaced_repetition_plan - 复习/记忆/遗忘/艾宾浩斯相关\n\n"
                        "规则:\n"
                        "- 中文回答，简洁友好有激励性\n"
                        "- 根据用户意图选择合适工具\n"
                        "- 提醒用户侧边栏有打卡/番茄钟/复习管理功能\n"
                        "- 如不确定拖延类型可先询问\n"
                        f"\n用户效率类型: {st.session_state.efficiency_profile}\n"
                        f"连续学习天数: {st.session_state.study_streak['current_streak']}\n"
                        f"课程表: {json.dumps(st.session_state.timetable, ensure_ascii=False)}"
                    ),
                    callback_handler=None,
                )
                result = agent(prompt)
                response_text = result.message["content"][0]["text"]

            st.markdown(response_text)

        st.session_state.messages.append({"role": "assistant", "content": response_text})

# ---------------------------------------------------------------------------
# Tab 2: Weekly Heatmap
# ---------------------------------------------------------------------------

with tab_heatmap:
    # Two columns: heatmap + today's schedule
    hmap_col, today_col = st.columns([3, 1])

    with hmap_col:
        st.subheader("📅 一周课程热力图")
        st.caption("绿色=空闲 | 红色=有课 | 颜色深浅=效率高低")

    heatmap = get_week_heatmap_data()
    profile = EFFICIENCY_PROFILES[st.session_state.efficiency_profile]

    # Build heatmap HTML
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    hours_list = list(range(6, 23))

    html = '<div style="overflow-x: auto; font-family: sans-serif; font-size: 12px;">'
    html += '<table style="border-collapse: collapse; width: 100%;">'

    # Header row
    html += '<tr><th style="padding:4px 8px;"></th>'
    for h in hours_list:
        html += f'<th style="padding:4px; text-align:center; font-size:10px;">{h:02d}</th>'
    html += '</tr>'

    for day in days_list:
        html += f'<tr><td style="padding:4px 8px; font-weight:bold; white-space:nowrap;">{day}</td>'
        for h in hours_list:
            status = heatmap.get(day, {}).get(h, "free")
            # Get efficiency for this hour
            eff = 0.5
            for slot_range, e in profile.items():
                s = int(slot_range.split("-")[0].split(":")[0])
                end = int(slot_range.split("-")[1].split(":")[0])
                if s <= h < end:
                    eff = e
                    break

            if status == "class":
                color = f"rgba(231, 76, 60, {0.6 + eff * 0.4})"
                text = "课"
            else:
                color = f"rgba(46, 204, 113, {0.3 + eff * 0.6})"
                text = ""

            html += (
                f'<td style="padding:2px; text-align:center;">'
                f'<div style="background:{color}; border-radius:4px; '
                f'width:32px; height:28px; line-height:28px; margin:auto; '
                f'font-size:10px; color:white;">{text}</div></td>'
            )
        html += '</tr>'

    html += '</table></div>'

    # Legend
    html += '''
    <div style="margin-top:15px; font-size:12px;">
        <span style="display:inline-block; width:20px; height:14px; background:rgba(231,76,60,0.8); border-radius:3px; vertical-align:middle;"></span> 有课 &nbsp;
        <span style="display:inline-block; width:20px; height:14px; background:rgba(46,204,113,0.9); border-radius:3px; vertical-align:middle;"></span> 空闲(高效) &nbsp;
        <span style="display:inline-block; width:20px; height:14px; background:rgba(46,204,113,0.4); border-radius:3px; vertical-align:middle;"></span> 空闲(低效)
    </div>
    '''

    st.components.v1.html(html, height=320, scrolling=True)

    with today_col:
        # Today's quick view
        weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        today_day = weekday_map[datetime.date.today().weekday()]
        st.markdown(f"**📌 今日（{today_day}）**")
        today_classes = st.session_state.timetable.get(today_day, [])
        if today_classes:
            for cls in sorted(today_classes, key=lambda c: c["start"]):
                st.markdown(f"🔴 `{cls['start']}-{cls['end']}` {cls['course']}")
        else:
            st.caption("今日无课 🎉")

        st.markdown("")
        st.markdown("**⭐ 今日高效时段**")
        profile_now = EFFICIENCY_PROFILES[st.session_state.efficiency_profile]
        top3 = sorted(profile_now.items(), key=lambda x: x[1], reverse=True)[:3]
        for slot, eff in top3:
            st.markdown(f"🟢 `{slot}` {eff:.0%}")

    # Summary stats row
    total_class_hours = 0
    for day in days_list:
        classes = st.session_state.timetable.get(day, [])
        for cls in classes:
            start_h = int(cls["start"].split(":")[0])
            end_h = int(cls["end"].split(":")[0])
            total_class_hours += (end_h - start_h)
    total_free_hours = 17 * 7 - total_class_hours

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 周课程", f"{total_class_hours}h")
    with col2:
        st.metric("🟢 周空闲", f"{total_free_hours}h")
    with col3:
        high_eff_hours = sum(1 for s, e in profile.items() if e >= 0.8) * 2 * 7
        st.metric("⭐ 高效时段", f"~{high_eff_hours}h")

# ---------------------------------------------------------------------------
# Tab 3: Focus Analytics
# ---------------------------------------------------------------------------

with tab_analytics:
    streak = st.session_state.study_streak
    history = streak["history"]

    # Always show summary cards at top
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 连续天数", f"{streak['current_streak']}天")
    with col2:
        st.metric("🏆 最长连续", f"{streak['longest_streak']}天")
    with col3:
        st.metric("📖 总次数", f"{streak['total_sessions']}次")
    with col4:
        hours = streak["total_minutes"] / 60
        st.metric("⏱️ 总时长", f"{hours:.1f}h")

    if not history:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.info("👋 暂无数据 — 在侧边栏打卡后这里会显示你的学习分析")
        with c2:
            st.markdown("""
            **快速开始:** 侧边栏 → 🍅番茄钟 → ✅打卡
            """)
    else:

        st.markdown("---")

        # Two columns: chart + insights
        chart_col, insight_col = st.columns([2, 1])

        with chart_col:
            st.markdown("**📈 近14天学习时长**")
            if len(history) > 1:
                chart_data = {entry["date"][-5:]: entry["minutes"] for entry in history[-14:]}
                st.bar_chart(chart_data, color="#667eea")
            else:
                st.caption("打卡2天后显示趋势图")

        with insight_col:
            avg_minutes = streak["total_minutes"] / max(len(history), 1)
            st.markdown("**💡 效率洞察**")
            st.write(f"日均: **{avg_minutes:.0f}分钟**")

            if avg_minutes >= 120:
                st.success("🌟 优秀！保持！")
            elif avg_minutes >= 60:
                st.info("👍 不错，再加一个番茄钟？")
            else:
                st.warning("💪 试试每天2个番茄钟")

            st.markdown("")
            # Points
            points = streak["total_sessions"] * 10 + streak["current_streak"] * 5
            st.markdown(f"**🏆 积分: {points}分**")
            next_milestone = ((points // 100) + 1) * 100
            progress = (points % 100) / 100
            st.progress(progress, text=f"下一奖励还需{next_milestone - points}分")

        st.caption("🎁 100分=🎬电影 | 200分=🍰美食 | 500分=🎮游戏 | 1000分=🎉礼物")
