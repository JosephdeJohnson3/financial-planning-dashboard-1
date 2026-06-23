from fpdf import FPDF
from datetime import date


GREEN = (0, 180, 130)
YELLOW = (220, 170, 30)
RED = (220, 70, 70)
BLUE = (60, 110, 220)
DARK = (30, 35, 50)
MID = (100, 105, 130)
LIGHT_BG = (248, 249, 252)
WHITE = (255, 255, 255)


def _prob_color(p: float):
    if p >= 0.70: return GREEN
    if p >= 0.40: return YELLOW
    return RED


def _status(p: float) -> str:
    if p >= 0.70: return "On Track"
    if p >= 0.40: return "Needs Attention"
    return "At Risk"


def _action(g_name: str, p: float, boost_p: float, boost: int) -> str:
    delta = (boost_p - p) * 100
    if p >= 0.70:
        return f"You are well-positioned for {g_name}. Maintain your current savings rate."
    if p >= 0.40:
        gain = f" Saving ${boost:,}/mo more would improve your odds by {delta:.0f} percentage points." if delta > 2 else ""
        return f"Your {g_name} goal needs attention. Consider increasing contributions or adjusting your target.{gain}"
    gain = f" Adding ${boost:,}/mo would improve your odds by {delta:.0f} percentage points." if delta > 2 else ""
    return f"Your {g_name} goal is at risk. A meaningful change in savings rate or timeline is recommended.{gain}"


class PlanPDF(FPDF):
    def header(self):
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*WHITE)
        self.set_xy(10, 5)
        self.cell(0, 8, "Financial Planning Report", align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(180, 185, 200)
        self.set_xy(0, 5)
        self.cell(200, 8, f"Generated {date.today().strftime('%B %d, %Y')}", align="R")
        self.ln(16)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*MID)
        self.cell(0, 6, "For educational purposes only. Not financial advice.    |    Page " + str(self.page_no()), align="C")


def generate_pdf(
    current_age: int,
    current_savings: float,
    monthly_contribution: float,
    allocation: str,
    goals: list,
    boost_amount: int,
    boost_probs: dict,
) -> bytes:
    pdf = PlanPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(14, 22, 14)

    # ── Profile section ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MID)
    pdf.cell(0, 6, "YOUR PROFILE", ln=True)
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.4)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    profile_items = [
        ("Current Age", f"{current_age}"),
        ("Current Savings", f"${current_savings:,.0f}"),
        ("Monthly Contribution", f"${monthly_contribution:,.0f}/mo"),
        ("Asset Allocation", allocation),
    ]
    pdf.set_font("Helvetica", "", 9)
    col_w = 45
    for i, (label, val) in enumerate(profile_items):
        x = 14 + (i % 4) * col_w
        y = pdf.get_y()
        pdf.set_xy(x, y)
        pdf.set_text_color(*MID)
        pdf.cell(col_w, 5, label)
        pdf.set_xy(x, y + 5)
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(col_w, 5, val)
        pdf.set_font("Helvetica", "", 9)
    pdf.ln(16)

    # ── Goals summary table ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MID)
    pdf.cell(0, 6, "GOAL SUMMARY", ln=True)
    pdf.set_draw_color(*BLUE)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    # Table header
    col_widths = [45, 38, 28, 30, 37]
    headers = ["Goal", "Target Amount", "By Year", "Probability", "Status"]
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 8)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for i, g in enumerate(goals):
        fill_color = LIGHT_BG if i % 2 == 0 else WHITE
        pdf.set_fill_color(*fill_color)
        color = _prob_color(g.probability)
        status = _status(g.probability)

        pdf.set_text_color(*DARK)
        pdf.cell(col_widths[0], 7, g.name, fill=True)
        pdf.cell(col_widths[1], 7, f"${g.target_amount:,.0f}", fill=True)
        pdf.cell(col_widths[2], 7, str(g.target_year), fill=True)

        # Colored probability cell
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_widths[3], 7, f"{g.probability*100:.0f}%", fill=True)

        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(col_widths[4], 7, status, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.ln()

    pdf.ln(6)

    # ── Action plan ──────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MID)
    pdf.cell(0, 6, "YOUR ACTION PLAN", ln=True)
    pdf.set_draw_color(*BLUE)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(4)

    for g in goals:
        bp = boost_probs.get(g.name, g.probability)
        action_text = _action(g.name, g.probability, bp, boost_amount)
        color = _prob_color(g.probability)

        # Colored bullet
        pdf.set_fill_color(*color)
        pdf.rect(14, pdf.get_y() + 1.5, 3, 3, "F")

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*DARK)
        pdf.set_x(20)
        pdf.cell(0, 6, g.name, ln=True)

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(60, 65, 80)
        pdf.set_x(20)
        pdf.multi_cell(170, 5, action_text)
        pdf.ln(2)

    # ── Sensitivity note ─────────────────────────────────────────────────────
    pdf.ln(2)
    pdf.set_fill_color(235, 241, 255)
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.3)
    x0, y0 = 14, pdf.get_y()
    pdf.set_xy(x0, y0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 6, f"Is it worth saving ${boost_amount:,} more per month?", ln=True)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(60, 65, 80)
    lines = []
    for g in goals:
        bp = boost_probs.get(g.name, g.probability)
        delta = (bp - g.probability) * 100
        sign = "+" if delta >= 0 else ""
        lines.append(f"  {g.name}: {g.probability*100:.0f}% -> {bp*100:.0f}% ({sign}{delta:.0f}pp)")
    pdf.multi_cell(0, 5, "\n".join(lines))
    pdf.rect(14, y0 - 1, 182, pdf.get_y() - y0 + 4, "D")

    return bytes(pdf.output())
