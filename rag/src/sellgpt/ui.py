"""Local Gradio interface for streaming catalog chat and persona memory."""

import argparse
import atexit
from html import escape
import re
from pathlib import Path
from time import perf_counter
from tempfile import TemporaryDirectory
from uuid import uuid4

import gradio as gr

from .assistant import prepare_answer
from .config import load_config
from .index import Index
from .memory import Memory, create_persona
from .ollama import Ollama


TYPING_INDICATOR = """
<div class="typing-dots" role="status" aria-label="SellGPT is typing">
  <span></span><span></span><span></span>
</div>
"""
NEW_PERSON = "__new_person__"
TYPING_CSS = """
.typing-dots { display: inline-flex; gap: 5px; padding: 12px 16px;
               border-radius: 18px; background: var(--background-fill-secondary); }
.typing-dots span { width: 7px; height: 7px; border-radius: 50%;
                    background: var(--body-text-color-subdued);
                    animation: typing-hop 1.2s ease-in-out infinite; }
.typing-dots span:nth-child(2) { animation-delay: .15s; }
.typing-dots span:nth-child(3) { animation-delay: .3s; }
.chat-progress { color: var(--body-text-color-subdued); font-size: .8em;
                 line-height: 1.5; margin-top: 8px; }
.chat-progress details { margin-top: 8px; }
@keyframes typing-hop {
  0%, 60%, 100% { transform: translateY(0); opacity: .5; }
  30% { transform: translateY(-5px); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .typing-dots span { animation: none; }
}
"""


def render_reply(response, sources, stages, verbose):
    """Render a chat bubble. Parameters: answer, sources HTML, stage strings, verbose flag. Return: HTML/Markdown text."""
    content = response or TYPING_INDICATOR
    if verbose:
        content += ('\n\n<div class="chat-progress">'
                    + "<br>".join(escape(stage) for stage in stages) + sources + "</div>")
    return content


def build_ui(config, root):
    """Build the interface. Parameters: Config, config directory Path. Return: Blocks."""
    persona_dir = root / "personas"
    temporary = TemporaryDirectory(prefix="sellgpt-session-")
    atexit.register(temporary.cleanup)
    browser_sessions = {}
    client = Ollama(config)
    index = None

    def profiles():
        """Discover selectable profiles. Parameters: none. Return: label/path pairs."""
        paths = set(persona_dir.glob("*.json"))
        if config.persona:
            paths.add(config.persona)
        return [("None", ""), *[(path.stem, str(path)) for path in sorted(paths)],
                ("New person", NEW_PERSON)]

    def load_session(selected, enabled, previous=None):
        """Load a single profile. Parameters: selection, flag, optional previous session. Return: session dictionary."""
        anonymous_path = (previous["anonymous_path"] if previous else
                          Path(temporary.name) / f"{uuid4().hex}.json")
        destination = Path(selected) if selected else anonymous_path
        if selected and not destination.is_file():
            raise ValueError(f"Persona file does not exist: {destination}")
        memory = Memory(destination) if selected or enabled else None
        return {"selected": selected, "enabled": enabled, "memory": memory,
                "history": [], "anonymous_path": anonymous_path, "closed": False}

    def cleanup_session(session):
        """Remove anonymous memory. Parameter: optional session dictionary. Return: None."""
        if session:
            session["closed"] = True
            session["anonymous_path"].unlink(missing_ok=True)

    def unload_session(request: gr.Request):
        """Clean up a closed browser tab. Parameter: Gradio request. Return: None."""
        cleanup_session(browser_sessions.pop(request.session_hash, None))

    def select_persona(selected, enabled, session):
        """Handle selection. Parameters: path, flag, session. Return: session, chat, status, form, name, selection."""
        if selected == NEW_PERSON:
            previous = session["selected"] if session else str(config.persona or "")
            return (gr.skip(), gr.skip(), "", gr.update(visible=True), "",
                    gr.update(value=previous))
        try:
            cleanup_session(session)
            return load_session(selected, enabled), [], "", gr.update(visible=False), "", gr.skip()
        except (ValueError, TypeError, KeyError, OSError) as error:
            return None, [], f"Cannot load persona: {error}", gr.update(visible=False), "", gr.skip()

    def toggle_memory(selected, enabled, session):
        """Change learning mode. Parameters: selection, flag, session. Return: session, status."""
        try:
            updated = load_session(selected, enabled, session)
            if session:
                updated["history"] = session["history"]
                if not enabled:
                    updated["memory"] = session["memory"] if selected else None
            return updated, ""
        except (ValueError, TypeError, KeyError, OSError) as error:
            return None, f"Cannot load memory: {error}"

    def new_persona(name, session):
        """Create a profile. Parameters: name string, current session. Return: selection, flag, session, chat, status, form, name."""
        try:
            name = name.strip()
            if not name or len(name) > 80:
                raise ValueError("Name must contain 1 to 80 characters.")
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "persona"
            path = persona_dir / f"{slug}.json"
            if any(Path(value).stem == slug for _, value in profiles() if value and value != NEW_PERSON):
                raise ValueError("That persona already exists. Select it or use a different name.")
            create_persona(path, name)
            cleanup_session(session)
            return (gr.update(choices=profiles(), value=str(path)), True,
                    load_session(str(path), True), [], "", gr.update(visible=False), "")
        except (ValueError, TypeError, KeyError, OSError) as error:
            return (gr.skip(), gr.skip(), gr.skip(), gr.skip(), f"Cannot create persona: {error}",
                    gr.update(visible=True), gr.skip())

    def clear_chat(session):
        """Clear recent turns. Parameter: session dictionary. Return: session, empty chat, status."""
        if session:
            session["history"] = []
        return session, [], ""

    def chat(question, selected, enabled, session, transcript, verbose, request: gr.Request):
        """Stream a reply. Parameters: question, selection, memory flag, session, transcript, verbose flag, request. Return: output iterator."""
        nonlocal index
        question = question.strip()
        if not question:
            yield (session, transcript, question, "", *[gr.update(interactive=True) for _ in range(7)])
            return
        transcript = list(transcript or [])
        previous = list(transcript)
        stages = ["Preparing chat…"]
        transcript.extend([{"role": "user", "content": question},
                           {"role": "assistant", "content": render_reply("", "", stages, verbose)}])
        status = ""
        controls = [gr.update(interactive=False) for _ in range(7)]
        yield (session, transcript, gr.update(value="", interactive=False), status, *controls)
        try:
            if session is None:
                session = load_session(selected, enabled)
            browser_sessions[request.session_hash] = session
            if index is None:
                client.model_digest(config.answer_model)
                index = Index(config, client)
            # Reload writable profiles before a turn so separate tabs do not overwrite stale facts.
            if enabled:
                session["memory"] = load_session(selected, enabled, session)["memory"]
            stages = ["Retrieval…"]
            transcript[-1] = {"role": "assistant", "content": render_reply("", "", stages, verbose)}
            yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            messages, sources, retrieval_seconds = prepare_answer(config, index, question, session["history"], session["memory"])
            stages = [f"Retrieval: {retrieval_seconds:.2f}s", "Answer generation…"]
            transcript[-1] = {"role": "assistant", "content": render_reply("", "", stages, verbose)}
            yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            response = ""
            generation_started = perf_counter()
            for fragment in client.chat(messages):
                if not fragment:
                    continue
                response += fragment
                transcript[-1] = {"role": "assistant", "content": render_reply(response, "", stages, verbose)}
                yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            stages[-1] = f"Answer generation: {perf_counter() - generation_started:.2f}s"
            links = "".join(f'<li>[{number}] {escape(source["name"])} — {escape(source["url"])}</li>'
                            for number, source in enumerate(sources, 1))
            sources_html = "<details><summary>Retrieved sources</summary><ul>" + links + "</ul></details>"
            session["history"].extend([{"role": "user", "content": question}, {"role": "assistant", "content": response}])
            del session["history"][:-2 * config.history_turns]
            if enabled:
                stages.append("Memory update…")
            transcript[-1] = {"role": "assistant", "content": render_reply(response, sources_html, stages, verbose)}
            yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            if enabled:
                memory_started = perf_counter()
                try:
                    if not session["closed"]:
                        session["memory"].update(client, question, response, sources)
                    stages[-1] = f"Memory update: {perf_counter() - memory_started:.2f}s"
                except (ValueError, TypeError, KeyError, OSError) as error:
                    stages[-1] = f"Memory update failed: {perf_counter() - memory_started:.2f}s"
                    status = f"Answer complete; memory update failed. Previous profile preserved: {error}"
                transcript[-1] = {"role": "assistant", "content": render_reply(response, sources_html, stages, verbose)}
        except (ValueError, TypeError, KeyError, OSError) as error:
            transcript = previous
            status = f"Could not answer: {error}"
            # Keep the question available for retry; incomplete output is not retained.
            yield (session, transcript, gr.update(value=question, interactive=False), status, *controls)
        finally:
            if session and session["closed"]:
                cleanup_session(session)
            yield (session, transcript, gr.update(value=question if transcript == previous else "", interactive=True), status,
                   *[gr.update(interactive=True) for _ in range(7)])

    def toggle_verbose(verbose):
        """Set the chat label. Parameter: verbose flag. Return: Chatbot label update."""
        return gr.update(label=config.answer_model if verbose else "Chat")

    with gr.Blocks(title="SellGPT") as demo:
        gr.Markdown("# SellGPT\nCommercial-steering demonstration: this assistant may suggest catalog products.")
        session = gr.State(None, delete_callback=cleanup_session)
        demo.unload(unload_session)
        with gr.Row():
            selected = gr.Dropdown(profiles(), value=str(config.persona) if config.persona else "", label="Persona")
            with gr.Column():
                enabled = gr.Checkbox(value=config.memory_enabled, label="Enable memory",
                                      info="Off: use the selected profile without learning or saving.")
                verbose = gr.Checkbox(value=False, label="Verbose mode")
        with gr.Row(visible=False) as new_person_form:
            name = gr.Textbox(label="New person's name", max_lines=1)
            create = gr.Button("Create person")
        chatbot = gr.Chatbot(label="Chat", height=480)
        question = gr.Textbox(label="Message", placeholder="Type a message…")
        with gr.Row():
            send = gr.Button("Send", variant="primary")
            clear = gr.Button("Clear chat")
        status = gr.Markdown()
        events = {"concurrency_id": "sellgpt", "concurrency_limit": 1,
                  "api_visibility": "private", "show_progress": "hidden"}
        selected.input(select_persona, [selected, enabled, session],
                       [session, chatbot, status, new_person_form, name, selected], **events)
        enabled.input(toggle_memory, [selected, enabled, session], [session, status], **events)
        verbose.input(toggle_verbose, [verbose], [chatbot], **events)
        gr.on([create.click, name.submit], new_persona, [name, session],
              [selected, enabled, session, chatbot, status, new_person_form, name], **events)
        clear.click(clear_chat, [session], [session, chatbot, status], **events)
        inputs = [question, selected, enabled, session, chatbot, verbose]
        outputs = [session, chatbot, question, status, selected, enabled, name, create, send, clear, verbose]
        gr.on([send.click, question.submit], chat, inputs, outputs, **events)
    return demo.queue(default_concurrency_limit=1, api_open=False)


def main():
    """Launch local chat. Parameters: none (reads argv). Return: None."""
    parser = argparse.ArgumentParser(description="Local SellGPT Gradio chat")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "config.toml")
    args = parser.parse_args()
    path = args.config.expanduser().resolve()
    config = load_config(path, {})
    build_ui(config, path.parent).launch(server_name="127.0.0.1", share=False, inbrowser=True, css=TYPING_CSS)


if __name__ == "__main__":
    main()
