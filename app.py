"""
Gradio Web Interface for Harbor Treatment Navigation Chatbot

Landing page offers two paths:
1. Talk to a human — immediate phone number and crisis support link
2. Get personalized advice — leads to the AI chatbot

Run locally:
    python app.py

Access in browser:
    http://localhost:7860
"""

import gradio as gr
from src.chat import Chatbot


def create_chatbot():
    """
    Creates the Harbor interface with a landing page and chatbot.
    """
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
        # TODO: Generate and return response
        pass

    with gr.Blocks(
        title="Harbor",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
        css="""
        .landing-container { max-width: 700px; margin: 0 auto; padding: 2rem 1rem; }
        .harbor-title { text-align: center; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.25rem; }
        .harbor-subtitle { text-align: center; font-size: 1.1rem; color: #555; margin-bottom: 2rem; }
        .option-card { border: 1px solid #ddd; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
        .option-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }
        .phone-number { font-size: 1.5rem; font-weight: 700; color: #1a73e8; }
        .footer-note { text-align: center; font-size: 0.85rem; color: #888; margin-top: 2rem; }
        """,
    ) as demo:

        # ── Landing Page ──────────────────────────────────────────────
        with gr.Column(visible=True, elem_classes="landing-container") as landing_page:
            gr.Markdown(
                "<div class='harbor-title'>Harbor</div>"
                "<div class='harbor-subtitle'>Come in from the storm.</div>"
            )

            # Option 1 — Talk to a Human
            with gr.Group(elem_classes="option-card"):
                gr.Markdown(
                    "### Talk to a Human\n"
                    "If you'd like to speak with someone right now, trained counselors "
                    "are available **24 hours a day, 7 days a week, 365 days a year** "
                    "through the Behavioral Health Help Line (BHHL)."
                )
                gr.Markdown(
                    "<div class='phone-number'>Call or text: 833-773-2445</div>"
                )
                gr.Markdown(
                    "If you or someone near you may be in immediate danger, "
                    "please **call 911**."
                )

            # Option 2 — Get Personalized Advice
            with gr.Group(elem_classes="option-card"):
                gr.Markdown(
                    "### Get Personalized Advice\n"
                    "Not sure what treatment options are available to you? "
                    "Our chatbot can help you explore what's out there based on "
                    "your situation — including location, insurance, preferences, and more."
                )
                start_chat_btn = gr.Button(
                    "Start a Conversation",
                    variant="primary",
                    size="lg",
                )

            gr.Markdown(
                "<div class='footer-note'>"
                "Harbor does not provide medical advice, diagnosis, or treatment. "
                "If you are in crisis, please call 911 or the BHHL at 833-773-2445."
                "</div>"
            )

        # ── Chatbot Page ──────────────────────────────────────────────
        with gr.Column(visible=False) as chat_page:
            back_btn = gr.Button("← Back", size="sm", variant="secondary")
            gr.ChatInterface(
                chat,
                title="Harbor",
                description=(
                    "Tell me a little about your situation and I'll help you find "
                    "treatment options that match your needs."
                ),
                examples=[
                    "What options are available for someone in my situation?",
                    "I'm looking for outpatient treatment for alcohol use.",
                    "I need help but I don't have insurance.",
                ],
            )

        # ── Navigation ────────────────────────────────────────────────
        def show_chat():
            return gr.update(visible=False), gr.update(visible=True)

        def show_landing():
            return gr.update(visible=True), gr.update(visible=False)

        start_chat_btn.click(
            show_chat,
            outputs=[landing_page, chat_page],
        )
        back_btn.click(
            show_landing,
            outputs=[landing_page, chat_page],
        )

    return demo


if __name__ == "__main__":
    demo = create_chatbot()
    demo.launch()
