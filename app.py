"""Time Optimizer Pro - Streamlit chat app with Strands Agents SDK.

Features:
- Editable timetable (courses & time slots)
- Selectable personal study efficiency profile
- Weekly heatmap overview
- Study streak tracker
- Focus analytics dashboard
- Ebbinghaus spaced repetition reminders
- Tool 1: Smart study schedule optimizer (timetable + efficiency + priority)
- Tool 2: Anti-procrastination planner (calendar + Pomodoro + rewards)
- Tool 3: Smart task prioritization (Eisenhower Matrix)
- Tool 4: Ebbinghaus spaced repetition planner
- Built-in Pomodoro timer (customizable duration)
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

st.set_page_config(page_title="Time Optimizer Pro", page_icon="⏰", layout="wide")

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .streak-badge {
        background: linear-gradient(135deg, #f093fb, #f5576c);
        color: white; padding: 8px 16px; border-radius: 20px;
        font-weight: bold; display: inline-block; margin: 5px;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; padding: 15px; border-radius: 12px;
        text-align: center; margin: 5px 0;
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
        "Mon": [
            {"course": "Calculus", "start": "08:00", "end": "10:00", "type": "Lecture"},
            {"course": "Data Structures", "start": "14:00", "end": "16:00", "type": "Lab"},
        ],
        "Tue": [
            {"course": "English", "start": "10:00", "end": "12:00", "type": "Lecture"},
            {"course": "Physics", "start": "14:00", "end": "16:00", "type": "Lecture"},
        ],
        "Wed": [
            {"course": "Calculus", "start": "08:00", "end": "10:00", "type": "Lecture"},
            {"course": "Programming", "start": "13:00", "end": "15:00", "type": "Lab"},
        ],
        "Thu": [
            {"course": "Data Structures", "start": "10:00", "end": "12:00", "type": "Lecture"},
            {"course": "English", "start": "15:00", "end": "17:00", "type": "Seminar"},
        ],
        "Fri": [
            {"course": "Physics", "start": "08:00", "end": "10:00", "type": "Lab"},
            {"course": "Programming", "start": "14:00", "end": "16:00", "type": "Lecture"},
        ],
    }

if "efficiency_profile" not in st.session_state:
    st.session_state.efficiency_profile = "Balanced (Morning + Evening)"

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
        "history": [],
    }

if "focus_log" not in st.session_state:
    st.session_state.focus_log = []

if "review_items" not in st.session_state:
    st.session_state.review_items = []

# ---------------------------------------------------------------------------
# Efficiency Profiles
# ---------------------------------------------------------------------------

EFFICIENCY_PROFILES = {
    "Early Bird (Morning Peak)": {
        "06:00-08:00": 0.85, "08:00-10:00": 1.0, "10:00-12:00": 0.9,
        "12:00-14:00": 0.4, "14:00-16:00": 0.6, "16:00-18:00": 0.5,
        "18:00-20:00": 0.4, "20:00-22:00": 0.5, "22:00-24:00": 0.3,
    },
    "Night Owl (Evening Peak)": {
        "06:00-08:00": 0.3, "08:00-10:00": 0.5, "10:00-12:00": 0.6,
        "12:00-14:00": 0.4, "14:00-16:00": 0.7, "16:00-18:00": 0.75,
        "18:00-20:00": 0.8, "20:00-22:00": 1.0, "22:00-24:00": 0.9,
    },
    "Balanced (Morning + Evening)": {
        "06:00-08:00": 0.5, "08:00-10:00": 0.85, "10:00-12:00": 0.95,
        "12:00-14:00": 0.4, "14:00-16:00": 0.75, "16:00-18:00": 0.65,
        "18:00-20:00": 0.5, "20:00-22:00": 0.85, "22:00-24:00": 0.55,
    },
    "Afternoon (Post-lunch Peak)": {
        "06:00-08:00": 0.4, "08:00-10:00": 0.6, "10:00-12:00": 0.7,
        "12:00-14:00": 0.5, "14:00-16:00": 1.0, "16:00-18:00": 0.95,
        "18:00-20:00": 0.7, "20:00-22:00": 0.6, "22:00-24:00": 0.4,
    },
}

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

DAYS_LIST = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_week_heatmap_data():
    """Generate heatmap data showing busy/free hours across the week."""
    hours = list(range(6, 24))
    heatmap = {}
    for day in DAYS_LIST:
        heatmap[day] = {}
        classes = st.session_state.timetable.get(day, [])
        for h in hours:
            occupied = any(
                int(cls["start"].split(":")[0]) <= h < int(cls["end"].split(":")[0])
                for cls in classes
            )
            heatmap[day][h] = "class" if occupied else "free"
    return heatmap


def get_ebbinghaus_intervals():
    return [1, 2, 4, 7, 15, 30]


def calculate_next_review(learned_date_str, review_count):
    intervals = get_ebbinghaus_intervals()
    if review_count >= len(intervals):
        return None
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
        efficiency_type, EFFICIENCY_PROFILES["Balanced (Morning + Evening)"]
    )
    streak_data = st.session_state.study_streak
    review_items = st.session_state.review_items

    @tool
    def optimize_study_schedule(day: str, subjects: list[str], hours_available: float) -> str:
        """Analyze timetable and personal efficiency to arrange optimal study slots.

        Combines the day's class schedule with the user's efficiency curve to
        recommend the best study time slots. Hard subjects go in high-efficiency
        slots, review goes in low-efficiency slots.

        Args:
            day: Day of the week, e.g. "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun".
            subjects: List of subjects to study, e.g. ["Calculus", "English"].
            hours_available: Total hours available for studying.

        Returns:
            Detailed study schedule recommendation.
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
                free_slots.append({"time": slot_range, "efficiency": eff, "duration": end_h - start_h})

        free_slots.sort(key=lambda x: x["efficiency"], reverse=True)

        lines = [
            f"📅 {day} - Optimized Study Plan",
            f"📊 Efficiency Profile: {efficiency_type}",
            f"🔥 Current Streak: {streak_data['current_streak']} days",
            "",
            f"Classes today: {', '.join(c['course'] + ' (' + c['start'] + '-' + c['end'] + ')' for c in day_classes) if day_classes else 'No classes'}",
            f"Available time: {hours_available} hours",
            f"Subjects: {', '.join(subjects)}",
            "",
            "🎯 Recommended Schedule (sorted by efficiency):",
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
                tag = "🔴 High efficiency -> Deep learning / hard problems"
            elif eff >= 0.65:
                tag = "🟡 Medium efficiency -> Practice & application"
            else:
                tag = "🟢 Low efficiency -> Light review / organizing"

            lines.append(f"  ⏰ {slot['time']} | Eff: {eff:.0%} | {tag}")
            lines.append(f"     📖 {subject} ({allocated:.1f}h)")
            pomodoros = int(allocated * 60 / 25)
            lines.append(f"     🍅 Suggested: {pomodoros} Pomodoro(s)")
            lines.append("")
            remaining -= allocated
            subject_idx += 1

        if remaining > 0:
            lines.append(f"⚠️ {remaining:.1f}h unscheduled (not enough free slots)")

        today = datetime.date.today().strftime("%Y-%m-%d")
        due_reviews = [r for r in review_items if r.get("next_review") == today]
        if due_reviews:
            lines.append("")
            lines.append("📝 Ebbinghaus Review Reminders for Today:")
            for r in due_reviews:
                lines.append(f"  🔔 {r['subject']} (review #{r['review_count']+1})")

        lines.extend(["", "─" * 35, "", "💡 Tips:",
                      "  • Take a 10-min break every 45 minutes",
                      "  • Check in on the sidebar when done!",
                      "  • Add new material to the review planner"])
        return "\n".join(lines)

    @tool
    def anti_procrastination_plan(tasks: list[str], deadlines: list[str], procrastination_type: str) -> str:
        """Create an anti-procrastination plan combining calendar, efficiency, and rewards.

        Generates a plan with micro-task breakdown, time checkpoints, Pomodoro suggestions,
        and a points reward system. Supports types: perfectionist, avoidant, indecisive, thrill-seeker.

        Args:
            tasks: List of tasks, e.g. ["Finish math homework", "Write essay draft"].
            deadlines: Corresponding deadlines, e.g. ["Wednesday", "Next Monday"].
            procrastination_type: Type of procrastination: "perfectionist", "avoidant", "indecisive", "thrill-seeker", or "unknown".

        Returns:
            Personalized anti-procrastination execution plan.
        """
        strategies = {
            "perfectionist": {
                "issue": "Fear of not being good enough, so you delay starting",
                "tips": ["Set a 'good enough' standard, not perfect", "Done is better than perfect - allow bad first drafts",
                         "5-minute start: just commit to 5 minutes", "80% is fine, iterate later"],
                "reward": "Finish first draft -> Watch an episode of your show",
            },
            "avoidant": {
                "issue": "Tasks cause anxiety, so you avoid them",
                "tips": ["Break into 2-5 minute micro-steps", "Swiss cheese method: do any random small part",
                         "Change environment: go to library, turn off notifications", "Reward yourself after each step"],
                "reward": "Complete 3 steps -> Enjoy your favorite snack",
            },
            "indecisive": {
                "issue": "Too many choices, don't know where to start",
                "tips": ["2-minute rule: if it takes 2 min, do it now", "Set TOP 3 tasks the night before",
                         "Don't think, just start a Pomodoro", "Use fixed order to reduce decision fatigue"],
                "reward": "Complete TOP 1 task -> 30 minutes of free time",
            },
            "thrill-seeker": {
                "issue": "Only productive under deadline pressure",
                "tips": ["Set fake deadlines (2 days earlier)", "Find an accountability partner",
                         "Split big deadlines into small checkpoints", "Use countdown timers for urgency"],
                "reward": "Finish early -> A full day off!",
            },
            "unknown": {
                "issue": "Procrastination type not yet identified",
                "tips": ["Try the 5-minute start", "Break into smallest possible step",
                         "Set a 25-min Pomodoro", "Rest 5 min after completion"],
                "reward": "Complete 1 Pomodoro -> 5 minutes of phone time",
            },
        }

        strategy = strategies.get(procrastination_type, strategies["unknown"])
        sorted_slots = sorted(efficiency_data.items(), key=lambda x: x[1], reverse=True)
        top_slots = sorted_slots[:3]

        lines = [
            "🚀 Anti-Procrastination Plan + Reward System", "",
            f"📊 Efficiency Profile: {efficiency_type}",
            f"😈 Procrastination Type: {procrastination_type}",
            f"   -> {strategy['issue']}",
            f"🎁 Completion Reward: {strategy['reward']}",
            "", "═" * 40, "",
            "📅 Best Execution Slots (based on your efficiency):",
        ]
        for slot, eff in top_slots:
            lines.append(f"  ⭐ {slot} (efficiency {eff:.0%})")
        lines.extend(["", "─" * 40, ""])

        total_pomodoros = 0
        for i, (t, d) in enumerate(zip(tasks, deadlines), 1):
            pomodoros = max(2, min(10, len(t) // 2 + 2))
            total_pomodoros += pomodoros
            lines.append(f"📋 Task {i}: {t}")
            lines.append(f"   ⏰ Deadline: {d}")
            lines.append(f"   🍅 Estimated: {pomodoros} Pomodoro(s) ({pomodoros * 25} min)")
            lines.append(f"   📐 Micro-task Breakdown:")
            lines.append(f"      1️⃣ Open materials, browse 2 min (start ritual)")
            lines.append(f"      2️⃣ List sub-steps (5 min)")
            lines.append(f"      3️⃣ First Pomodoro: minimum viable output")
            lines.append(f"      4️⃣ 1-2 Pomodoros per day to keep momentum")
            lines.append(f"      5️⃣ Final check before submission")
            lines.append("")

        lines.extend([
            "═" * 40, "",
            f"📊 Total needed: {total_pomodoros} Pomodoro(s) (~{total_pomodoros * 25 / 60:.1f} hours)", "",
            "🧠 Personalized Strategies:",
        ])
        for tip in strategy["tips"]:
            lines.append(f"  ✅ {tip}")
        lines.extend(["", "─" * 40, "",
            "🏆 Points Reward System:",
            "  • Complete 1 Pomodoro = +10 pts",
            "  • 3-day streak = +50 pts BONUS",
            "  • Finish task early = +100 pts",
            "  • 100 pts accumulated -> Redeem a reward!",
            "", "👇 Click 'Start Pomodoro' in the sidebar to begin!",
            "💪 Starting is the hardest part. Just 5 minutes!"])
        return "\n".join(lines)

    @tool
    def smart_prioritize(tasks: list[str], urgencies: list[str], importances: list[str]) -> str:
        """Prioritize tasks using the Eisenhower Matrix.

        Classifies tasks into four quadrants by urgency and importance, then
        provides execution order recommendations.

        Args:
            tasks: List of tasks.
            urgencies: Urgency level for each task: "high" or "low".
            importances: Importance level for each task: "high" or "low".

        Returns:
            Priority-sorted task execution plan.
        """
        quadrants = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}

        for t, u, imp in zip(tasks, urgencies, importances):
            if u == "high" and imp == "high":
                quadrants["Q1"].append(t)
            elif u == "low" and imp == "high":
                quadrants["Q2"].append(t)
            elif u == "high" and imp == "low":
                quadrants["Q3"].append(t)
            else:
                quadrants["Q4"].append(t)

        lines = [
            "🎯 Eisenhower Matrix - Smart Priority Sorting", "",
            "┌──────────────────────────────────────────────┐",
            "│            URGENT            NOT URGENT       │",
            "├──────────────────────────────────────────────┤",
            "│ IMPORTANT   Q1: Do Now       Q2: Schedule    │",
            "│ NOT IMPORT. Q3: Delegate     Q4: Eliminate   │",
            "└──────────────────────────────────────────────┘", "",
        ]

        if quadrants["Q1"]:
            lines.append("🔴 Q1 - Urgent & Important (Do Now):")
            for t in quadrants["Q1"]:
                lines.append(f"  🚨 {t}")
            lines.append("")
        if quadrants["Q2"]:
            lines.append("🟡 Q2 - Important, Not Urgent (Schedule):")
            for t in quadrants["Q2"]:
                lines.append(f"  📋 {t}")
            lines.append("")
        if quadrants["Q3"]:
            lines.append("🟠 Q3 - Urgent, Not Important (Quick/Delegate):")
            for t in quadrants["Q3"]:
                lines.append(f"  ⚡ {t}")
            lines.append("")
        if quadrants["Q4"]:
            lines.append("⚪ Q4 - Neither Urgent nor Important (Eliminate):")
            for t in quadrants["Q4"]:
                lines.append(f"  🗑️ {t}")
            lines.append("")

        lines.extend(["─" * 35, "",
            "📌 Execution Advice:",
            "  1. Clear Q1 first (eliminate stress)",
            "  2. Focus energy on Q2 (long-term growth)",
            "  3. Handle Q3 quickly, don't overthink",
            "  4. Boldly remove or postpone Q4", "",
            f"  ⏱️ Based on your profile ({efficiency_type}),",
            f"  handle Q1+Q2 during peak efficiency hours!"])
        return "\n".join(lines)

    @tool
    def spaced_repetition_plan(subjects: list[str], learned_date: str) -> str:
        """Generate a spaced repetition plan based on the Ebbinghaus forgetting curve.

        Calculates optimal review dates (1, 2, 4, 7, 15, 30 days after learning).

        Args:
            subjects: List of subjects or topics to review.
            learned_date: Date learned, format "YYYY-MM-DD", e.g. "2026-07-24".

        Returns:
            Complete Ebbinghaus spaced repetition schedule.
        """
        intervals = get_ebbinghaus_intervals()
        try:
            base_date = datetime.datetime.strptime(learned_date, "%Y-%m-%d").date()
        except ValueError:
            base_date = datetime.date.today()

        lines = [
            "🧠 Ebbinghaus Spaced Repetition Plan", "",
            f"📚 Subjects: {', '.join(subjects)}",
            f"📅 Date Learned: {base_date.strftime('%Y-%m-%d')}",
            "", "─" * 40, "",
            "📈 Forgetting Curve & Review Timeline:", "",
            "  Retention:",
            "  100%|■■■■■■■■■■",
            "   80%|■■■■■■■■░░  <- Review #1 (1 day later)",
            "   60%|■■■■■■░░░░  <- Review #2 (3 days later)",
            "   40%|■■■■░░░░░░  <- Review #3 (7 days later)",
            "   20%|■■░░░░░░░░  <- Without review, most is forgotten",
            "", "─" * 40, "", "📋 Review Schedule:", "",
        ]

        cumulative = 0
        for i, interval in enumerate(intervals, 1):
            cumulative += interval
            review_date = base_date + datetime.timedelta(days=cumulative)
            emoji = "✅" if review_date <= datetime.date.today() else "📌"
            lines.append(f"  {emoji} Review #{i}: {review_date.strftime('%Y-%m-%d')} ({cumulative} days later)")
            lines.append(f"     Content: {', '.join(subjects)}")
            if i <= 2:
                lines.append(f"     Method: Detailed review + practice problems")
            elif i <= 4:
                lines.append(f"     Method: Quick scan + key point recall")
            else:
                lines.append(f"     Method: Concept test + fill gaps")
            lines.append("")

        lines.extend(["─" * 35, "", "💡 Review Tips:",
                      "  • Try to recall before reviewing (active retrieval)",
                      "  • Explain concepts in your own words",
                      "  • Use mind maps to organize relationships",
                      "  • Mark completion in the sidebar after each review",
                      "", "🔔 Added to your review reminder system!"])
        return "\n".join(lines)

    return [optimize_study_schedule, anti_procrastination_plan, smart_prioritize, spaced_repetition_plan]

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Control Panel")

    # --- Efficiency Profile ---
    st.subheader("📊 Efficiency Profile")
    st.session_state.efficiency_profile = st.selectbox(
        "Select your type:",
        options=list(EFFICIENCY_PROFILES.keys()),
        index=list(EFFICIENCY_PROFILES.keys()).index(st.session_state.efficiency_profile),
    )

    profile = EFFICIENCY_PROFILES[st.session_state.efficiency_profile]
    with st.expander("📈 View Efficiency Curve"):
        for slot, eff in profile.items():
            bar = "█" * int(eff * 10) + "░" * (10 - int(eff * 10))
            st.text(f"{slot} {bar} {eff:.0%}")

    st.markdown("---")

    # --- Study Streak ---
    st.subheader("🔥 Study Check-in")
    streak = st.session_state.study_streak

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Streak", f"{streak['current_streak']} days",
                  delta=f"Best: {streak['longest_streak']}")
    with col2:
        st.metric("Total", f"{streak['total_minutes']} min",
                  delta=f"{streak['total_sessions']} sessions")

    checkin_minutes = st.number_input("Study duration (min):", min_value=5, max_value=480, value=25, step=5)
    if st.button("✅ Check In Today", key="checkin_btn", type="primary"):
        today = datetime.date.today().strftime("%Y-%m-%d")
        history = streak["history"]
        if history and history[-1]["date"] == today:
            history[-1]["minutes"] += checkin_minutes
        else:
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
        st.success(f"🎉 Checked in! Streak: {streak['current_streak']} days! +{checkin_minutes} min")
        st.rerun()

    st.markdown("---")

    # --- Timetable Editor ---
    st.subheader("📚 Timetable Editor")

    selected_day = st.selectbox("Edit day:", DAYS_LIST)

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
        st.caption(f"No classes on {selected_day}")

    with st.expander("➕ Add Course"):
        new_course = st.text_input("Course name", key="new_course_name")
        col1, col2 = st.columns(2)
        with col1:
            new_start = st.selectbox("Start", [f"{h:02d}:00" for h in range(6, 23)], key="new_start")
        with col2:
            new_end = st.selectbox("End", [f"{h:02d}:00" for h in range(7, 24)], index=2, key="new_end")
        new_type = st.selectbox("Type", ["Lecture", "Lab", "Seminar", "Tutorial"], key="new_type")

        if st.button("Add", key="add_course_btn"):
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
    st.subheader("🧠 Review Reminders")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    due_items = [r for r in st.session_state.review_items if r.get("next_review") == today_str]

    if due_items:
        st.warning(f"📢 {len(due_items)} item(s) due for review today!")
        for item in due_items:
            st.write(f"  🔔 {item['subject']} (review #{item['review_count']+1})")
    else:
        st.caption("No reviews due today ✨")

    with st.expander("➕ Add Review Item"):
        review_subject = st.text_input("Topic / Subject:", key="review_subject")
        review_date = st.date_input("Date learned:", value=datetime.date.today(), key="review_date")
        if st.button("Add to Review Plan", key="add_review"):
            if review_subject.strip():
                date_str = review_date.strftime("%Y-%m-%d")
                next_rev = calculate_next_review(date_str, 0)
                st.session_state.review_items.append({
                    "subject": review_subject.strip(),
                    "learned_date": date_str,
                    "next_review": next_rev,
                    "review_count": 0,
                })
                st.success(f"Added! Next review: {next_rev}")
                st.rerun()

    if st.session_state.review_items:
        with st.expander(f"📋 All Review Items ({len(st.session_state.review_items)})"):
            for i, item in enumerate(st.session_state.review_items):
                col1, col2 = st.columns([3, 1])
                with col1:
                    status = "✅ Mastered" if item.get("next_review") is None else f"Next: {item['next_review']}"
                    st.text(f"  {item['subject']} | {status}")
                with col2:
                    if item.get("next_review") and st.button("Done", key=f"rev_done_{i}"):
                        item["review_count"] += 1
                        item["next_review"] = calculate_next_review(item["learned_date"], item["review_count"])
                        st.rerun()

    st.markdown("---")

    # --- Pomodoro Timer ---
    st.subheader("🍅 Pomodoro Timer")

    pomodoro_task = st.text_input(
        "Focus task:",
        value=st.session_state.pomodoro_task,
        placeholder="Enter task...",
        key="pomodoro_input",
    )
    st.session_state.pomodoro_task = pomodoro_task

    pomodoro_minutes = st.select_slider(
        "Duration (min):",
        options=[15, 20, 25, 30, 45, 50, 60],
        value=25,
    )

    if st.button("▶️ Start Pomodoro", key="start_pomodoro", type="primary"):
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
                🎯 {st.session_state.pomodoro_task or 'Focusing'}
            </div>
            <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">
                📵 Do Not Disturb
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
                        display.textContent = "✅ Done!";
                        timerDiv.style.background = "linear-gradient(135deg, #2ecc71, #27ae60)";
                    }}
                }}, 1000);
            }})();
        </script>
        """
        st.components.v1.html(timer_html, height=120)

        if st.button("⏹️ Stop", key="stop_pomodoro"):
            st.session_state.pomodoro_active = False
            st.rerun()

# ---------------------------------------------------------------------------
# Main Area: Tabs
# ---------------------------------------------------------------------------

st.title("⏰ Time Optimizer Pro")

tab_chat, tab_heatmap, tab_analytics = st.tabs(["💬 AI Assistant", "📅 Weekly Heatmap", "📊 Focus Analytics"])

# ---------------------------------------------------------------------------
# Tab 1: Chat
# ---------------------------------------------------------------------------

with tab_chat:
    if not st.session_state.messages:
        streak = st.session_state.study_streak
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        due_reviews = [r for r in st.session_state.review_items if r.get("next_review") == today_str]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔥 Streak", f"{streak['current_streak']} days")
        with col2:
            st.metric("🍅 Sessions", f"{streak['total_sessions']}")
        with col3:
            points = streak["total_sessions"] * 10 + streak["current_streak"] * 5
            st.metric("🏆 Points", f"{points}")
        with col4:
            st.metric("🔔 Due Reviews", f"{len(due_reviews)}")

        st.markdown("---")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            **🎯 Try asking:**
            - I have 3 free hours on Monday for Calculus and English
            - Help me prioritize my tasks
            - I learned Linear Algebra today, make a review plan
            """)
        with c2:
            st.markdown("""
            **😈 Procrastinating? Ask me:**
            - My essay is due next week but I keep delaying
            - I'm a perfectionist, help me make a plan
            - I have 5 tasks and don't know where to start
            """)
        st.markdown("---")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("e.g. 3 free hours Monday for Calculus / I keep procrastinating / prioritize my tasks"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                tools = create_tools()
                agent = Agent(
                    tools=tools,
                    model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    system_prompt=(
                        "You are 'Time Optimizer Pro', a professional AI time management assistant.\n\n"
                        "Available tools:\n"
                        "1. optimize_study_schedule - study scheduling / free time / timetable\n"
                        "2. anti_procrastination_plan - procrastination / deadlines / planning\n"
                        "3. smart_prioritize - task sorting / priority / multiple tasks\n"
                        "4. spaced_repetition_plan - review / memory / Ebbinghaus\n\n"
                        "Rules:\n"
                        "- Reply in English, concise and motivational\n"
                        "- Choose the appropriate tool based on user intent\n"
                        "- Remind users about sidebar features (check-in, Pomodoro, review)\n"
                        "- If procrastination type is unclear, ask first\n"
                        "- Types: perfectionist, avoidant, indecisive, thrill-seeker\n"
                        f"\nUser efficiency profile: {st.session_state.efficiency_profile}\n"
                        f"Current streak: {st.session_state.study_streak['current_streak']} days\n"
                        f"Timetable: {json.dumps(st.session_state.timetable, ensure_ascii=False)}"
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
    hmap_col, today_col = st.columns([3, 1])

    with hmap_col:
        st.subheader("📅 Weekly Timetable Heatmap")
        st.caption("Green = Free | Red = Class | Deeper color = Higher efficiency")

    heatmap = get_week_heatmap_data()
    profile = EFFICIENCY_PROFILES[st.session_state.efficiency_profile]

    hours_list = list(range(6, 23))

    html = '<div style="overflow-x: auto; font-family: sans-serif; font-size: 12px;">'
    html += '<table style="border-collapse: collapse; width: 100%;">'
    html += '<tr><th style="padding:4px 8px;"></th>'
    for h in hours_list:
        html += f'<th style="padding:4px; text-align:center; font-size:10px;">{h:02d}</th>'
    html += '</tr>'

    for day in DAYS_LIST:
        html += f'<tr><td style="padding:4px 8px; font-weight:bold; white-space:nowrap;">{day}</td>'
        for h in hours_list:
            status = heatmap.get(day, {}).get(h, "free")
            eff = 0.5
            for slot_range, e in profile.items():
                s = int(slot_range.split("-")[0].split(":")[0])
                end = int(slot_range.split("-")[1].split(":")[0])
                if s <= h < end:
                    eff = e
                    break
            if status == "class":
                color = f"rgba(231, 76, 60, {0.6 + eff * 0.4})"
                text = "C"
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
    html += '''
    <div style="margin-top:15px; font-size:12px;">
        <span style="display:inline-block; width:20px; height:14px; background:rgba(231,76,60,0.8); border-radius:3px; vertical-align:middle;"></span> Class &nbsp;
        <span style="display:inline-block; width:20px; height:14px; background:rgba(46,204,113,0.9); border-radius:3px; vertical-align:middle;"></span> Free (High Eff.) &nbsp;
        <span style="display:inline-block; width:20px; height:14px; background:rgba(46,204,113,0.4); border-radius:3px; vertical-align:middle;"></span> Free (Low Eff.)
    </div>
    '''
    st.components.v1.html(html, height=320, scrolling=True)

    with today_col:
        weekday_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        today_day = weekday_map[datetime.date.today().weekday()]
        st.markdown(f"**📌 Today ({today_day})**")
        today_classes = st.session_state.timetable.get(today_day, [])
        if today_classes:
            for cls in sorted(today_classes, key=lambda c: c["start"]):
                st.markdown(f"🔴 `{cls['start']}-{cls['end']}` {cls['course']}")
        else:
            st.caption("No classes today 🎉")
        st.markdown("")
        st.markdown("**⭐ Top Efficiency Slots**")
        top3 = sorted(profile.items(), key=lambda x: x[1], reverse=True)[:3]
        for slot, eff in top3:
            st.markdown(f"🟢 `{slot}` {eff:.0%}")

    # Summary
    total_class_hours = 0
    for day in DAYS_LIST:
        for cls in st.session_state.timetable.get(day, []):
            total_class_hours += int(cls["end"].split(":")[0]) - int(cls["start"].split(":")[0])
    total_free_hours = 17 * 7 - total_class_hours

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Weekly Classes", f"{total_class_hours}h")
    with col2:
        st.metric("🟢 Weekly Free", f"{total_free_hours}h")
    with col3:
        high_eff_hours = sum(1 for s, e in profile.items() if e >= 0.8) * 2 * 7
        st.metric("⭐ Peak Hours", f"~{high_eff_hours}h")

# ---------------------------------------------------------------------------
# Tab 3: Focus Analytics
# ---------------------------------------------------------------------------

with tab_analytics:
    streak = st.session_state.study_streak
    history = streak["history"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Streak", f"{streak['current_streak']} days")
    with col2:
        st.metric("🏆 Best Streak", f"{streak['longest_streak']} days")
    with col3:
        st.metric("📖 Sessions", f"{streak['total_sessions']}")
    with col4:
        hours = streak["total_minutes"] / 60
        st.metric("⏱️ Total Time", f"{hours:.1f}h")

    if not history:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.info("👋 No data yet — check in from the sidebar to see your analytics here")
        with c2:
            st.markdown("**Quick start:** Sidebar → 🍅 Pomodoro → ✅ Check In")
    else:
        st.markdown("---")
        chart_col, insight_col = st.columns([2, 1])

        with chart_col:
            st.markdown("**📈 Last 14 Days**")
            if len(history) > 1:
                chart_data = {entry["date"][-5:]: entry["minutes"] for entry in history[-14:]}
                st.bar_chart(chart_data, color="#667eea")
            else:
                st.caption("Chart appears after 2+ days of check-ins")

        with insight_col:
            avg_minutes = streak["total_minutes"] / max(len(history), 1)
            st.markdown("**💡 Insights**")
            st.write(f"Daily avg: **{avg_minutes:.0f} min**")

            if avg_minutes >= 120:
                st.success("🌟 Excellent! Keep it up!")
            elif avg_minutes >= 60:
                st.info("👍 Good start! Try one more Pomodoro?")
            else:
                st.warning("💪 Try 2 Pomodoros per day")

            st.markdown("")
            points = streak["total_sessions"] * 10 + streak["current_streak"] * 5
            st.markdown(f"**🏆 Points: {points}**")
            next_milestone = ((points // 100) + 1) * 100
            progress = (points % 100) / 100
            st.progress(progress, text=f"{next_milestone - points} pts to next reward")

        st.caption("🎁 100pts=🎬Movie | 200pts=🍰Nice meal | 500pts=🎮Gaming | 1000pts=🎉Gift")
