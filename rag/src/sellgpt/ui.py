"""Local Gradio interface for streaming catalog chat and user profile memory."""

import argparse
import atexit
from html import escape
import re
from pathlib import Path
from time import perf_counter
from tempfile import TemporaryDirectory
from uuid import uuid4

import gradio as gr

from .assistant import introduce, prepare_answer
from .config import load_config
from .index import Index
from .memory import Memory, create_user_profile
from .ollama import Ollama
from .products import mentioned_product_urls, product_name_pattern


TYPING_INDICATOR = """
<div class="typing-dots" role="status" aria-label="SellGPT is typing">
  <span></span><span></span><span></span>
</div>
"""
NEW_USER_PROFILE = "__new_user_profile__"
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

# Reuse the native footer link's classes so GitHub matches Gradio's theme.
GITHUB_FOOTER_JS = """
() => {
    const footer = document.querySelector('.gradio-container footer');
    const credit = footer?.querySelector('a.built-with');
    if (!credit || footer.querySelector('.github-link')) return;
    const link = credit.cloneNode(false);
    link.classList.add('github-link');
    link.href = 'https://github.com/TaisiaKozharina/sell_gpt';
    link.rel = 'noopener noreferrer';
    link.innerHTML = `GitHub
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"
             aria-hidden="true" style="margin-left:4px">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
                0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
                -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
                .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
                -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09
                2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82
                2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01
                2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/>
        </svg>`;
    footer.prepend(link);
}
"""


def link_products(response, products, known_products=()):
    """Link known names and use current-turn citations as a reliable fallback.

    Parameters: answer text, ordered current sources, optional earlier products.
    Return: HTML/Markdown, preserving existing links, code, and invalid citations.
    Earlier products supply name matches only; citation numbers always use products.
    """
    by_pattern = {}
    for product in sorted([*products, *known_products],
                          key=lambda product: len(product["name"]), reverse=True):
        pattern = product_name_pattern(product["name"])
        if not pattern or not product["url"].startswith(("https://", "http://")):
            continue
        if pattern in by_pattern and by_pattern[pattern] != product["url"]:
            # A name shared by different URLs cannot identify one product safely.
            by_pattern[pattern] = None
        else:
            by_pattern[pattern] = product["url"]
    matches = [(pattern, url) for pattern, url in by_pattern.items() if url]
    pattern = re.compile("|".join(f"(?P<product_{index}>{name})"
                                  for index, (name, _) in enumerate(matches)), re.IGNORECASE) if matches else None
    linked_urls = set()

    def anchor(label, url):
        """Build a product link and record its URL to avoid duplicate citation links."""
        linked_urls.add(url)
        return (f'<a href="{escape(url, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{escape(label)}</a>')

    def replace(match):
        """Link one named product. Parameter: regex match. Return: escaped anchor HTML."""
        url = matches[int(match.lastgroup.removeprefix("product_"))][1]
        return anchor(match[0], url)

    def cite(match):
        """Resolve a current source number, keeping unknown citations visible."""
        position = int(match[2]) - 1
        if not 0 <= position < len(products):
            return match[0]
        product = products[position]
        if not product["url"].startswith(("https://", "http://")):
            return match[0]
        if product["url"] in linked_urls:
            return ""
        return match[1] + anchor(product["name"], product["url"])

    # Leave existing links, HTML tags, and code unchanged.
    protected = (r"(\[[^\]\n]*\]\([^\n]*?\)|<a\b[^>]*>.*?</a>|<[^>]*>|"
                 r"```[\s\S]*?```|`[^`\n]*`)")
    parts = re.split(protected, response, flags=re.IGNORECASE)
    named = "".join(pattern.sub(replace, part) if pattern and index % 2 == 0 else part
                    for index, part in enumerate(parts))
    # Protect newly generated anchors as well before resolving citations.
    parts = re.split(protected, named, flags=re.IGNORECASE)
    return "".join(part if index % 2 else re.sub(r"([ \t]*)(?<![\[!])\[(\d+)\](?![\](])", cite, part)
                   for index, part in enumerate(parts))


def render_reply(response, sources, stages, verbose, products=(), known_products=()):
    """Render a chat bubble.

    Parameters: answer, sources HTML, stage strings, verbose flag, current and earlier products.
    Return: HTML/Markdown text with clickable product citations.
    """
    content = link_products(response, products, known_products) if response else TYPING_INDICATOR
    if verbose:
        content += ('\n\n<div class="chat-progress">'
                    + "<br>".join(escape(stage) for stage in stages) + sources + "</div>")
    return content


def build_ui(config, root):
    """Build the interface. Parameters: Config, config directory Path. Return: Blocks."""
    user_profiles_dir = root / "user_profiles"
    temporary = TemporaryDirectory(prefix="sellgpt-session-")
    atexit.register(temporary.cleanup)
    browser_sessions = {}
    client = Ollama(config)
    index = None

    def profiles():
        """Discover selectable profiles. Parameters: none. Return: label/path pairs."""
        paths = set(user_profiles_dir.glob("*.json"))
        if config.user_profile:
            paths.add(config.user_profile)
        return [("None", ""), *[(path.stem, str(path)) for path in sorted(paths)],
                ("New user profile", NEW_USER_PROFILE)]

    def load_session(selected, enabled, previous=None):
        """Load a single profile. Parameters: selection, flag, optional previous session. Return: session dictionary."""
        anonymous_path = (previous["anonymous_path"] if previous else
                          Path(temporary.name) / f"{uuid4().hex}.json")
        destination = Path(selected) if selected else anonymous_path
        if selected and not destination.is_file():
            raise ValueError(f"User profile file does not exist: {destination}")
        memory = Memory(destination) if selected or enabled else None
        return {"selected": selected, "enabled": enabled, "memory": memory,
                "history": [], "used_products": previous["used_products"] if previous else set(),
                "known_products": previous["known_products"] if previous else {},
                "anonymous_path": anonymous_path, "closed": False}

    def cleanup_session(session):
        """Remove anonymous memory. Parameter: optional session dictionary. Return: None."""
        if session:
            session["closed"] = True
            session["anonymous_path"].unlink(missing_ok=True)

    def unload_session(request: gr.Request):
        """Clean up a closed browser tab. Parameter: Gradio request. Return: None."""
        cleanup_session(browser_sessions.pop(request.session_hash, None))

    def select_user_profile(selected, enabled, session):
        """Handle selection. Parameters: path, flag, session. Return: session, chat, status, form, name, selection."""
        if selected is None:
            return (gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
                    gr.update(value=session["selected"] if session else None))
        if selected == NEW_USER_PROFILE:
            previous = session["selected"] if session else None
            return (gr.skip(), gr.skip(), "", gr.update(visible=True), "",
                    gr.update(value=previous))
        try:
            cleanup_session(session)
            return load_session(selected, enabled), [], "", gr.update(visible=False), "", gr.skip()
        except (ValueError, TypeError, KeyError, OSError) as error:
            return None, [], f"Cannot load user profile: {error}", gr.update(visible=False), "", gr.skip()

    def toggle_memory(selected, enabled, session):
        """Change learning mode. Parameters: selection, flag, session. Return: session, status."""
        if session is None:
            return gr.skip(), gr.skip()
        try:
            updated = load_session(selected, enabled, session)
            if session:
                updated["history"] = session["history"]
                if not enabled:
                    updated["memory"] = session["memory"] if selected else None
            return updated, ""
        except (ValueError, TypeError, KeyError, OSError) as error:
            return None, f"Cannot load memory: {error}"

    def new_user_profile(name, session):
        """Create a profile. Parameters: name string, current session. Return: selection, flag, session, chat, status, form, name."""
        try:
            name = name.strip()
            if not name or len(name) > 80:
                raise ValueError("Name must contain 1 to 80 characters.")
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "user-profile"
            path = user_profiles_dir / f"{slug}.json"
            if any(Path(value).stem == slug for _, value in profiles() if value and value != NEW_USER_PROFILE):
                raise ValueError("That user profile already exists. Select it or use a different name.")
            create_user_profile(path, name)
            cleanup_session(session)
            return (gr.update(choices=profiles(), value=str(path)), True,
                    load_session(str(path), True), [], "", gr.update(visible=False), "")
        except (ValueError, TypeError, KeyError, OSError) as error:
            return (gr.skip(), gr.skip(), gr.skip(), gr.skip(), f"Cannot create user profile: {error}",
                    gr.update(visible=True), gr.skip())

    def clear_chat(session):
        """Clear turns and product tracking. Parameter: session. Return: session, empty chat, status."""
        if session:
            session["history"] = []
            session["used_products"].clear()
            session["known_products"].clear()
        return session, [], ""

    def start_chat(selected, enabled, session, transcript, verbose, status, request: gr.Request):
        """Stream the opening greeting for an empty conversation.

        Parameters: user profile selection, memory flag, session, transcript, verbose flag,
        status text, and Gradio request. Return: iterator of chat and control updates.
        """
        if session is None or selected is None or transcript or status:
            yield tuple(gr.skip() for _ in range(11))
            return
        controls = [gr.update(interactive=False) for _ in range(7)]
        stages = ["Introduction…"]
        transcript = [{"role": "assistant", "content": render_reply("", "", stages, verbose)}]
        yield (session, transcript, gr.update(interactive=False), "", *controls)
        try:
            browser_sessions[request.session_hash] = session
            response = ""
            started = perf_counter()
            for fragment in introduce(config, client, session["history"], session["memory"]):
                response += fragment
                transcript[0]["content"] = render_reply(response, "", stages, verbose)
                yield (session, transcript, gr.update(interactive=False), "", *controls)
            stages[0] = f"Introduction: {perf_counter() - started:.2f}s"
            transcript[0]["content"] = render_reply(response, "", stages, verbose)
        except (ValueError, TypeError, KeyError, OSError) as error:
            transcript = []
            status = f"Could not introduce SellGPT: {error}"
        finally:
            if session and session["closed"]:
                cleanup_session(session)
            yield (session, transcript, gr.update(interactive=True), status,
                   *[gr.update(interactive=True) for _ in range(7)])

    def chat(question, selected, enabled, session, transcript, verbose, request: gr.Request):
        """Stream a reply. Parameters: question, selection, memory flag, session, transcript, verbose flag, request. Return: output iterator."""
        nonlocal index
        if session is None or selected is None:
            yield (gr.skip(), gr.skip(), gr.skip(), "Choose a user profile or None to start.",
                   *[gr.skip() for _ in range(7)])
            return
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
            messages, sources, retrieval_seconds = prepare_answer(
                config, index, question, session["history"], session["memory"],
                session["used_products"])
            stages = [f"Retrieval: {retrieval_seconds:.2f}s", "Answer generation…"]
            transcript[-1] = {"role": "assistant", "content": render_reply("", "", stages, verbose)}
            yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            response = ""
            known_products = list(session["known_products"].values())
            generation_started = perf_counter()
            for fragment in client.chat(messages):
                if not fragment:
                    continue
                response += fragment
                transcript[-1] = {"role": "assistant", "content": render_reply(
                    response, "", stages, verbose, sources, known_products)}
                yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            stages[-1] = f"Answer generation: {perf_counter() - generation_started:.2f}s"
            session["used_products"].update(mentioned_product_urls(response, sources))
            session["known_products"].update(
                (source["url"], {"name": source["name"], "url": source["url"]}) for source in sources)
            links = "".join(f'<li>{link_products(source["name"] + f" [{number}]", sources)} — {escape(source["url"])}</li>'
                            for number, source in enumerate(sources, 1))
            sources_html = "<details><summary>Retrieved sources</summary><ul>" + links + "</ul></details>"
            session["history"].extend([{"role": "user", "content": question}, {"role": "assistant", "content": response}])
            del session["history"][:-2 * config.history_turns]
            if enabled:
                stages.append("Memory update…")
            transcript[-1] = {"role": "assistant", "content": render_reply(
                response, sources_html, stages, verbose, sources, known_products)}
            yield (session, transcript, gr.update(value="", interactive=False), "", *controls)
            if enabled:
                memory_started = perf_counter()
                try:
                    if not session["closed"]:
                        session["memory"].update(client, question)
                    stages[-1] = f"Memory update: {perf_counter() - memory_started:.2f}s"
                except (ValueError, TypeError, KeyError, OSError) as error:
                    stages[-1] = f"Memory update failed: {perf_counter() - memory_started:.2f}s"
                    status = f"Answer complete; memory update failed. Previous profile preserved: {error}"
                transcript[-1] = {"role": "assistant", "content": render_reply(
                    response, sources_html, stages, verbose, sources, known_products)}
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
        demo.load(fn=None, js=GITHUB_FOOTER_JS)
        with gr.Row():
            selected = gr.Dropdown(profiles(), value=None, label="User profile")
            with gr.Column():
                enabled = gr.Checkbox(value=config.memory_enabled, label="Enable memory",
                                      info="Off: use the selected profile without learning or saving.")
                verbose = gr.Checkbox(value=False, label="Verbose mode")
        with gr.Row(visible=False) as new_user_profile_form:
            name = gr.Textbox(label="Name", max_lines=1)
            create = gr.Button("Create profile")
        chatbot = gr.Chatbot(label="Chat", height=480)
        question = gr.Textbox(label="Message", placeholder="Type a message…", interactive=False)
        with gr.Row():
            send = gr.Button("Send", variant="primary", interactive=False)
            clear = gr.Button("Clear chat", interactive=False)
        status = gr.Markdown("Choose a user profile or None to start.")
        events = {"concurrency_id": "sellgpt", "concurrency_limit": 1,
                  "api_visibility": "private", "show_progress": "hidden"}
        user_profile_event = selected.input(
            select_user_profile, [selected, enabled, session],
            [session, chatbot, status, new_user_profile_form, name, selected], **events)
        enabled.input(toggle_memory, [selected, enabled, session], [session, status], **events)
        verbose.input(toggle_verbose, [verbose], [chatbot], **events)
        create_event = gr.on([create.click, name.submit], new_user_profile, [name, session],
                             [selected, enabled, session, chatbot, status, new_user_profile_form, name], **events)
        clear_event = clear.click(clear_chat, [session], [session, chatbot, status], **events)
        inputs = [question, selected, enabled, session, chatbot, verbose]
        outputs = [session, chatbot, question, status, selected, enabled, name, create, send, clear, verbose]
        gr.on([send.click, question.submit], chat, inputs, outputs, **events)
        introduction_inputs = [selected, enabled, session, chatbot, verbose, status]
        for event in (user_profile_event, create_event, clear_event):
            event.then(start_chat, introduction_inputs, outputs, **events)
    return demo.queue(default_concurrency_limit=1, api_open=False)


def main():
    """Launch local chat. Parameters: none (reads argv). Return: None."""
    parser = argparse.ArgumentParser(description="Local SellGPT Gradio chat")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "config.toml")
    args = parser.parse_args()
    path = args.config.expanduser().resolve()
    config = load_config(path, {})
    build_ui(config, path.parent).launch(server_name="127.0.0.1", share=False, inbrowser=True,
                                        css=TYPING_CSS, footer_links=["gradio"])


if __name__ == "__main__":
    main()
