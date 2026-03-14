"""
Gradio Web Interface for Harbor Treatment Navigation Chatbot

Landing page offers three paths:
1. Quick Recommendations — enter a zip code, get nearby options inline
2. Talk to a Human — compact crisis callout with phone number
3. Get Personalized Advice — leads to the AI chatbot

Run locally:
    python app.py

Access in browser:
    http://localhost:7860
"""

import os
import re

import gradio as gr
from src.chat import Chatbot
from src.utils.profile import create_empty_profile
from src.utils.resources import load_resources, filter_resources, score_resources


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
/* ── Layout ── */
.harbor-wrap {
    max-width: 680px;
    margin: 0 auto;
    padding: 2.5rem 1.25rem 1.5rem;
    font-family: 'Inter', sans-serif;
}

/* ── Header ── */
.harbor-logo {
    text-align: center;
    font-size: 2.75rem;
    font-weight: 800;
    letter-spacing: -1px;
    color: #0d6e6e;
    margin-bottom: 0.2rem;
    line-height: 1;
}
.harbor-tagline {
    text-align: center;
    font-size: 1.1rem;
    color: #5a7a7a;
    margin-bottom: 2.25rem;
    font-style: italic;
}

/* ── Cards ── */
.harbor-card {
    background: #ffffff;
    border: 1.5px solid #c8e6e6;
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.1rem;
    box-shadow: 0 2px 12px rgba(13, 110, 110, 0.06);
}
.harbor-card-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #0d6e6e;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.harbor-card p {
    color: #3d5a5a;
    line-height: 1.65;
    margin: 0 0 0.75rem;
    font-size: 0.97rem;
}
.harbor-card p:last-child { margin-bottom: 0; }

/* ── Quick Rec card — larger, featured ── */
.harbor-card-featured {
    background: linear-gradient(145deg, #f0fafa, #e6f7f7);
    border: 2px solid #0d9e8f;
}
.harbor-card-featured .harbor-card-title {
    font-size: 1.25rem;
}

/* ── Crisis callout — compact ── */
.harbor-callout {
    background: #f8fffd;
    border: 1.5px solid #c8e6e6;
    border-radius: 12px;
    padding: 0.9rem 1.25rem;
    margin-bottom: 1.1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    box-shadow: 0 1px 6px rgba(13, 110, 110, 0.05);
}
.harbor-callout-text {
    flex: 1;
    min-width: 200px;
    font-size: 0.9rem;
    color: #3d5a5a;
    line-height: 1.5;
}
.harbor-callout-text strong { color: #0d6e6e; }
.harbor-phone-inline {
    font-size: 1.2rem;
    font-weight: 800;
    color: #0d6e6e;
    white-space: nowrap;
}
.harbor-phone-inline a { color: inherit; text-decoration: none; }
.harbor-phone-inline a:hover { text-decoration: underline; }

/* ── Zip results area ── */
.harbor-results {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #c8e6e6;
}
.harbor-results-title {
    font-size: 1rem;
    font-weight: 600;
    color: #0d6e6e;
    margin-bottom: 0.5rem;
}
.harbor-error {
    color: #c0392b;
    font-size: 0.9rem;
    margin-top: 0.4rem;
}
#zip-results .pending,
#zip-results .generating,
#zip-results > .wrap,
#zip-results > .svelte-spinner,
#zip-results .eta-bar {
    display: none !important;
}

/* ── Buttons ── */
.harbor-start-btn button,
.harbor-zip-btn button {
    background: linear-gradient(135deg, #0d9e8f, #0d6e6e) !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.2px !important;
    padding: 0.85rem 1.5rem !important;
    transition: opacity 0.2s ease !important;
    box-shadow: 0 4px 14px rgba(13, 110, 110, 0.25) !important;
}
.harbor-start-btn button:hover,
.harbor-zip-btn button:hover { opacity: 0.9 !important; }

/* ── Footer ── */
.harbor-footer {
    text-align: center;
    font-size: 0.8rem;
    color: #8fa8a8;
    margin-top: 1.75rem;
    line-height: 1.6;
}

/* ── Chat page ── */
.chat-header {
    max-width: 680px;
    margin: 0 auto;
    padding: 1.25rem 1.25rem 0;
}
.chat-back-btn button {
    background: transparent !important;
    border: 1.5px solid #c8e6e6 !important;
    color: #0d6e6e !important;
    border-radius: 8px !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 0.4rem 0.9rem !important;
}
.chat-back-btn button:hover { background: #f0fafa !important; }
"""

# ── Theme ─────────────────────────────────────────────────────────────────────

THEME = gr.themes.Soft(
    primary_hue="teal",
    secondary_hue="cyan",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "sans-serif"],
).set(
    button_primary_background_fill="linear-gradient(135deg, #0d9e8f, #0d6e6e)",
    button_primary_background_fill_hover="linear-gradient(135deg, #0bb8a8, #0d9e8f)",
    button_primary_text_color="#ffffff",
    block_border_color="#c8e6e6",
    block_shadow="0 2px 12px rgba(13,110,110,0.06)",
)

# ── Static HTML snippets ───────────────────────────────────────────────────────

HEADER_MD = """
<div class='harbor-logo'>⚓ Harbor</div>
<div class='harbor-tagline'>Come in from the storm.</div>
"""

CRISIS_CALLOUT_HTML = """
<div class='harbor-callout'>
  <div class='harbor-callout-text'>
    <strong>🤝 Talk to a Human</strong> — Trained counselors available
    <strong>24/7</strong> through the Behavioral Health Help Line.<br>
    <span style='font-size:0.82rem; color:#6b8e8e;'>
      In immediate danger? <strong style='color:#6b4e4e;'>Call 911.</strong>
    </span>
  </div>
  <div class='harbor-phone-inline'><a href='tel:8337732445'>📞 833-773-2445</a></div>
</div>
"""

CHATBOT_CARD_MD = """
<div class='harbor-card-title'>💬 Get Personalized Guidance</div>
<p>
  Want to explore options in more depth? Our chatbot can factor in your insurance,
  preferences, treatment history, and more — no judgment, no pressure.
</p>
"""

FOOTER_MD = """
<div class='harbor-footer'>
  Harbor does not provide medical advice, diagnosis, or treatment.<br>
  If you are in crisis, please call 911 or the BHHL at 833-773-2445.
</div>
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

ZIPCODE_RE = re.compile(r"^\d{5}$")


def is_valid_zip(zipcode: str) -> bool:
    """Return True if zipcode is exactly 5 digits."""
    return bool(ZIPCODE_RE.match(zipcode.strip()))


def _load_resources_once():
    """Load resource CSVs once and cache."""
    if not hasattr(_load_resources_once, "_cache"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(current_dir, "references", "knowledge", "ma_resources.csv"),
            os.path.join(current_dir, "references", "knowledge", "resources", "boston_resources.csv"),
        ]
        _load_resources_once._cache = load_resources(paths)
    return _load_resources_once._cache


def get_recommendations(zipcode: str) -> list[dict]:
    """
    Return a list of treatment recommendations for the given zip code.

    Uses the same filter/score logic as the chatbot, but with a minimal
    profile containing only the zipcode.
    """
    profile = create_empty_profile()
    profile["logistics"]["zipcode"] = zipcode.strip()

    resources = _load_resources_once()
    filtered = filter_resources(resources, profile)
    top = score_resources(filtered, profile)
    return top


def format_recommendations(zipcode: str, results: list[dict]) -> str:
    """Render recommendations as an HTML snippet for display."""
    if not results:
        return (
            f"<div class='harbor-results'>"
            f"<div class='harbor-results-title'>Results near {zipcode}</div>"
            f"<p style='color:#5a7a7a; font-size:0.93rem;'>"
            f"No results found for that zip code yet. Try the chatbot below for "
            f"more personalised help.</p>"
            f"</div>"
        )

    items_html = ""
    for r in results:
        name = r.get("name", "Unknown Facility")
        # Build address from parts
        addr_parts = [r.get("address", ""), r.get("city", ""),
                      r.get("state", ""), r.get("zip", "")]
        address = ", ".join(p.strip() for p in addr_parts if p.strip())
        phone = r.get("phone", "").strip()
        # Type from primary_focus
        focus = r.get("primary_focus", "").strip()
        type_label = ", ".join(
            v.strip().replace("_", " ").title() for v in focus.split("|")
        ) if focus else ""

        items_html += (
            f"<div style='margin-bottom:0.75rem; padding:0.75rem; background:#f8fffd; "
            f"border-radius:10px; border:1px solid #c8e6e6;'>"
            f"<strong style='color:#0d6e6e;'>{name}</strong><br>"
        )
        if type_label or address:
            items_html += (
                f"<span style='font-size:0.88rem; color:#5a7a7a;'>"
                f"{type_label + ' · ' if type_label else ''}{address}</span><br>"
            )
        if phone:
            items_html += (
                f"<a href='tel:{phone}' style='font-size:0.88rem; color:#0d9e8f;'>{phone}</a>"
            )
        items_html += "</div>"
    return (
        f"<div class='harbor-results'>"
        f"<div class='harbor-results-title'>📍 Options near {zipcode}</div>"
        f"{items_html}"
        f"</div>"
    )


# ── App ───────────────────────────────────────────────────────────────────────

def create_chatbot():
    """Creates the Harbor interface with a landing page and chatbot."""
    _load_resources_once()          # pre-load CSVs so first zip lookup is fast
    chatbot = Chatbot()

    def chat(message, history):
        """
        Generate a response for the current message.

        Args:
            message (str): The current message from the user
            history (list): List of previous [user, assistant] message pairs

        Returns:
            str: The assistant's response
        """
        return chatbot.get_response(message)

    def handle_zip_submit(zipcode: str):
        """Validate zip and return inline results HTML."""
        zipcode = zipcode.strip()
        if not is_valid_zip(zipcode):
            return gr.update(
                value="<div class='harbor-error'>⚠️ Please enter a valid 5-digit zip code.</div>",
                visible=True,
            )
        results = get_recommendations(zipcode)

        # Log recommendations to console
        if results:
            print(f"[Harbor] Zip lookup ({zipcode}) — {len(results)} recommendation(s):")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.get('name', 'Unknown')} — {r.get('city', '')}, {r.get('state', '')} {r.get('zip', '')}")
        else:
            print(f"[Harbor] Zip lookup ({zipcode}) — no results found.")

        return gr.update(value=format_recommendations(zipcode, results), visible=True)

    def show_chat():
        return gr.update(visible=False), gr.update(visible=True)

    def show_landing():
        return gr.update(visible=True), gr.update(visible=False)

    with gr.Blocks(title="Harbor", theme=THEME, css=CSS) as demo:

        # ── Landing Page ──────────────────────────────────────────────
        with gr.Column(visible=True) as landing_page:
            with gr.Column(elem_classes="harbor-wrap"):
                gr.HTML(HEADER_MD)

                # Card 1 — Quick Recommendations (featured)
                with gr.Group(elem_classes="harbor-card harbor-card-featured"):
                    gr.HTML("<div class='harbor-card-title'>📍 Find Options Near You</div>")
                    gr.HTML(
                        "<p>Enter your zip code and we'll show you nearby treatment "
                        "programs right away — no account needed.</p>"
                    )
                    with gr.Row():
                        zip_input = gr.Textbox(
                            placeholder="e.g. 02134",
                            max_lines=1,
                            show_label=False,
                            container=False,
                            scale=3,
                        )
                        zip_btn = gr.Button(
                            "Find Options →",
                            variant="primary",
                            scale=1,
                            elem_classes="harbor-zip-btn",
                        )
                # Results rendered outside the card so the loading spinner
                # does not overlay the input card above.
                results_html = gr.HTML(visible=False, elem_id="zip-results")

                # Card 2 — Crisis callout (compact)
                gr.HTML(CRISIS_CALLOUT_HTML)

                # Card 3 — Chatbot
                with gr.Group(elem_classes="harbor-card"):
                    gr.HTML(CHATBOT_CARD_MD)
                    start_chat_btn = gr.Button(
                        "Start a Conversation →",
                        variant="primary",
                        size="lg",
                        elem_classes="harbor-start-btn",
                    )

                gr.HTML(FOOTER_MD)

        # ── Chat Page ─────────────────────────────────────────────────
        with gr.Column(visible=False) as chat_page:
            with gr.Column(elem_classes="chat-header"):
                back_btn = gr.Button(
                    "← Back to Home",
                    size="sm",
                    variant="secondary",
                    elem_classes="chat-back-btn",
                )
            gr.ChatInterface(
                chat,
                title="⚓ Harbor",
                description=(
                    "Tell me a little about your situation and I'll help you find "
                    "treatment options that match your needs. Everything is confidential."
                ),
                examples=[
                    "What treatment options are available near me?",
                    "I'm looking for outpatient help with alcohol use.",
                    "I need support but I don't have insurance.",
                    "How do I know which type of program is right for me?",
                ],
            )

        # ── Events ────────────────────────────────────────────────────
        zip_btn.click(handle_zip_submit, inputs=zip_input, outputs=results_html)
        zip_input.submit(handle_zip_submit, inputs=zip_input, outputs=results_html)
        start_chat_btn.click(show_chat, outputs=[landing_page, chat_page])
        back_btn.click(show_landing, outputs=[landing_page, chat_page])

    return demo


if __name__ == "__main__":
    demo = create_chatbot()
    demo.launch()
