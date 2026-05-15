import re
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from note_reader import DEFAULT_NOTES_DIR


def _normalize_math_delims(text: str) -> str:
    # 1. Convert \(...\) and \[...\] to $...$
    text = re.sub(r"\\\((.+?)\\\)", r"$\1$", text, flags=re.DOTALL)
    text = re.sub(r"\\\[(.+?)\\\]", r"$\1$", text, flags=re.DOTALL)
    # 2. Normalise every $...$ region:
    #    - strip surrounding spaces ("$ f $" → "f", "$ \mathbb{R} $" → "$\mathbb{R}$")
    #    - keep only if content contains a backslash command (real LaTeX);
    #      plain-text content ("$f$", "$A$", "$x = 2$") is unwrapped
    def _fix_dollar(m: re.Match) -> str:
        content = m.group(1).strip()
        return f"${content}$" if "\\" in content else content
    text = re.sub(r"\$([^$]+)\$", _fix_dollar, text)
    # 3. Wrap any remaining bare \commands not already inside $...$
    parts = re.split(r"(\$[^$]+\$)", text)
    fixed = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            fixed.append(part)
        else:
            fixed.append(re.sub(r"(\\[a-zA-Z]+(?:\{[^{}]*\})*)", r"$\1$", part))
    return "".join(fixed)

_NEW_SUBJECT = "＋ New subject"
_STANDALONE = "(standalone)"
_NO_LINK = "(none)"
_SECTION_LABELS = ["Example", "Sub-topic", "Technique", "Definition", "Related"]

IDLE = "idle"
RECORDING = "recording"
GENERATING = "generating"


class _SearchableCombo(ctk.CTkFrame):
    """Entry + Toplevel popup replacement for CTkComboBox(state='readonly').

    Supports real-time filtering by typing, scrollable list, keyboard navigation.
    Exposes .get() / .set() so call sites need no changes.
    """

    def __init__(self, parent, values, variable=None, command=None,
                 width=180, font=("Helvetica", 11), placeholder_text="", **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._all = values
        self._var = variable or ctk.StringVar()
        self._cmd = command
        self._popup: tk.Toplevel | None = None
        self._lb: tk.Listbox | None = None

        self._entry = ctk.CTkEntry(self, width=width, font=font, textvariable=self._var,
                                   placeholder_text=placeholder_text)
        self._entry.pack()
        self._entry.bind("<KeyRelease>", self._on_key)
        self._entry.bind("<Button-1>",  self._show_popup)
        self._entry.bind("<FocusOut>",  self._on_focus_out)
        self._entry.bind("<Return>",    self._on_enter)
        self._entry.bind("<Escape>",    lambda e: self._close())
        self._entry.bind("<Down>",      self._focus_list)
        self.bind("<Unmap>", lambda e: self._close())

    def get(self) -> str:
        return self._var.get()

    def set(self, v: str):
        self._var.set(v)

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._all = kwargs.pop("values")
        if kwargs:
            super().configure(**kwargs)

    def _filtered(self) -> list[str]:
        q = self._var.get().lower()
        if not q or q in (_NO_LINK.lower(), _STANDALONE.lower()):
            return self._all
        return [v for v in self._all if q in v.lower()]

    def _show_popup(self, _=None):
        self._close()
        opts = self._filtered()
        if not opts:
            return
        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.wm_attributes("-topmost", True)
        x = self._entry.winfo_rootx()
        y = self._entry.winfo_rooty() + self._entry.winfo_height()
        top.wm_geometry(f"+{x}+{y}")

        lb = tk.Listbox(top, height=min(8, len(opts)), font=("Helvetica", 11),
                        selectmode="single", activestyle="dotbox")
        sb = tk.Scrollbar(top, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for v in opts:
            lb.insert("end", v)
        lb.bind("<ButtonRelease-1>", lambda e: self._pick(lb))
        lb.bind("<Return>",          lambda e: self._pick(lb))
        lb.bind("<Escape>",          lambda e: self._close())
        lb.bind("<FocusOut>",        self._on_focus_out)

        self._popup, self._lb = top, lb

    def _on_focus_out(self, _=None):
        self.after(150, self._maybe_close)

    def _maybe_close(self):
        if not self._popup:
            return
        try:
            fw = self.winfo_toplevel().focus_get()
        except Exception:
            fw = None
        if fw is not self._lb:
            self._close()

    def _close(self):
        if self._popup:
            self._popup.destroy()
            self._popup = None
            self._lb = None

    def _on_key(self, _=None):
        self._show_popup()

    def _focus_list(self, _=None):
        if self._lb:
            self._lb.focus_set()
            self._lb.selection_set(0)

    def _on_enter(self, _=None):
        if self._lb and (sel := self._lb.curselection()):
            self._pick(self._lb)

    def _pick(self, lb: tk.Listbox):
        sel = lb.curselection()
        if sel:
            self._var.set(lb.get(sel))
        self._close()
        if self._cmd:
            self._cmd(self._var.get())


class NotesTab:
    def __init__(self, parent: ctk.CTkFrame, recorder, transcriber, improver):
        self._recorder = recorder
        self._transcriber = transcriber
        self._improver = improver
        self._state = IDLE
        self._blocks: list[dict] = []
        self._notes_shown = False
        self._main_topic: str | None = None
        self._cancel_generation = False
        self._note_mode = ctk.StringVar(value="Multi")

        self._build_ui(parent)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _subject_list(self) -> list[str]:
        base = Path(DEFAULT_NOTES_DIR)
        if not base.exists():
            return [_NEW_SUBJECT]
        dirs = sorted(
            d.name for d in base.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and ((d / ".obsidian").exists() or any(d.glob("*.md")))
        )
        return dirs + [_NEW_SUBJECT]

    def _subject_note_names(self, subject: str) -> list[str]:
        path = Path(DEFAULT_NOTES_DIR) / subject
        if not path.exists():
            return []
        return sorted(
            f.stem for f in path.iterdir()
            if f.suffix == ".md" and not f.name.startswith(".")
        )

    def _scroll(self, delta: int):
        try:
            self._notes_scroll._parent_canvas.yview_scroll(delta, "units")
        except AttributeError:
            pass

    def _bind_scroll(self, widget):
        widget.bind("<Button-4>", lambda _e: self._scroll(-1))
        widget.bind("<Button-5>", lambda _e: self._scroll(1))
        for attr in ("_textbox", "_canvas", "_entry"):
            inner = getattr(widget, attr, None)
            if inner is not None:
                try:
                    inner.bind("<Button-4>", lambda _e: self._scroll(-1))
                    inner.bind("<Button-5>", lambda _e: self._scroll(1))
                except Exception:
                    pass
        for child in widget.winfo_children():
            self._bind_scroll(child)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, parent: ctk.CTkFrame):
        self._frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._frame.pack(fill="both", expand=True, padx=12, pady=12)

        self._status = ctk.CTkLabel(
            self._frame, text="", font=("Helvetica", 12), text_color="gray", anchor="w"
        )
        self._status.pack(anchor="w", pady=(0, 6))

        # Subject selector
        setup = ctk.CTkFrame(self._frame, fg_color="transparent")
        setup.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(setup, text="Subject:", font=("Helvetica", 12)).grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        subjects = self._subject_list()
        self._subject_var = ctk.StringVar(value=subjects[0])
        self._subject_menu = ctk.CTkOptionMenu(
            setup, values=subjects, variable=self._subject_var,
            width=220, font=("Helvetica", 12),
            command=self._on_subject_change,
        )
        self._subject_menu.grid(row=0, column=1, sticky="w", padx=(0, 8))

        self._new_subject_entry = ctk.CTkEntry(
            setup, placeholder_text="New subject name", width=200, font=("Helvetica", 12)
        )
        if subjects[0] == _NEW_SUBJECT:
            self._new_subject_entry.grid(row=0, column=2, sticky="w")

        self._mode_btn = ctk.CTkSegmentedButton(
            setup, values=["Multi", "Single"],
            variable=self._note_mode, width=120,
        )
        self._mode_btn.grid(row=0, column=3, padx=(12, 0))

        # Transcription input
        ctk.CTkLabel(
            self._frame, text="Lecture transcription", font=("Helvetica", 11),
            text_color="gray",
        ).pack(anchor="w")
        self._transcription_box = ctk.CTkTextbox(
            self._frame, height=150, font=("Helvetica", 13), wrap="word",
        )
        self._transcription_box.pack(fill="x", pady=(2, 6))

        # Buttons
        self._btn_row = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._btn_row.pack(anchor="w", pady=(0, 8))

        self._record_btn = ctk.CTkButton(
            self._btn_row, text="● Record", width=120, height=40,
            font=("Helvetica", 13, "bold"), command=self._on_record,
        )
        self._record_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = ctk.CTkButton(
            self._btn_row, text="■ Stop", width=100, height=40,
            font=("Helvetica", 13, "bold"), fg_color="#2980b9",
            command=self._on_stop,
        )

        self._generate_btn = ctk.CTkButton(
            self._btn_row, text="Generate notes →", width=150, height=40,
            font=("Helvetica", 13, "bold"), command=self._on_generate,
        )
        self._generate_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self._btn_row, text="Clear", width=80, height=40,
            fg_color="#555", command=self._on_clear_transcription,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self._btn_row, text="Copy", width=80, height=40,
            fg_color="#555", command=self._on_copy_transcript,
        ).pack(side="left", padx=(0, 6))

        # Generated notes area — hidden until first generation
        self._notes_header = ctk.CTkFrame(self._frame, fg_color="transparent")
        ctk.CTkLabel(
            self._notes_header, text="Generated notes", font=("Helvetica", 11),
            text_color="gray",
        ).pack(side="left")
        self._save_btn = ctk.CTkButton(
            self._notes_header, text="Save all to Obsidian", width=160, height=34,
            font=("Helvetica", 12, "bold"), command=self._on_save,
        )
        self._save_btn.pack(side="right")

        ctk.CTkButton(
            self._notes_header, text="Copy all", width=90, height=34,
            fg_color="#555", font=("Helvetica", 12),
            command=self._on_copy_all_notes,
        ).pack(side="right", padx=(0, 6))

        self._link_all_btn = ctk.CTkButton(
            self._notes_header, text="Link all", width=90, height=34,
            font=("Helvetica", 12), command=self._on_link_all,
        )
        self._link_all_btn.pack(side="right", padx=(0, 4))

        self._link_entry = _SearchableCombo(
            self._notes_header, values=[],
            width=160, font=("Helvetica", 12),
            placeholder_text="Link topic…",
        )
        self._link_entry.pack(side="right", padx=(0, 4))

        self._notes_scroll = ctk.CTkScrollableFrame(self._frame, fg_color="transparent")
        self._notes_scroll.bind("<Button-4>", lambda _e: self._scroll(-1))
        self._notes_scroll.bind("<Button-5>", lambda _e: self._scroll(1))
        self._notes_scroll._parent_canvas.bind("<Button-4>", lambda _e: self._scroll(-1))
        self._notes_scroll._parent_canvas.bind("<Button-5>", lambda _e: self._scroll(1))

    # ── Subject selector ──────────────────────────────────────────────────────

    def _on_subject_change(self, value: str):
        if value == _NEW_SUBJECT:
            self._new_subject_entry.grid(row=0, column=2, sticky="w", padx=(0, 6))
        else:
            self._new_subject_entry.grid_forget()
        if self._blocks:
            self._refresh_merge_menus(value)

    # ── Button state helpers ──────────────────────────────────────────────────

    def _set_busy(self):
        self._record_btn.configure(state="disabled")
        self._generate_btn.configure(text="Cancel", command=self._on_cancel, state="normal")
        if self._blocks:
            self._save_btn.configure(state="disabled")

    def _set_idle(self):
        self._record_btn.configure(state="normal")
        self._generate_btn.configure(text="Generate notes →", command=self._on_generate, state="normal")
        if self._blocks:
            self._save_btn.configure(state="normal")

    def _on_cancel(self):
        self._cancel_generation = True
        self._generate_btn.configure(state="disabled")
        self._status.configure(text="Cancelling…")

    # ── Recording ─────────────────────────────────────────────────────────────

    def _on_record(self):
        self._state = RECORDING
        self._record_btn.pack_forget()
        self._stop_btn.pack(side="left", padx=(0, 6), before=self._generate_btn)
        self._set_busy()
        self._status.configure(text="Recording...")
        self._recorder.start()

    def _on_stop(self):
        if self._state != RECORDING:
            return
        audio = self._recorder.stop()
        self._stop_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 6), before=self._generate_btn)
        self._record_btn.configure(state="disabled")
        self._generate_btn.configure(state="disabled")
        self._status.configure(text="Transcribing...")
        threading.Thread(target=self._do_transcribe, args=(audio,), daemon=True).start()

    def _do_transcribe(self, audio):
        if self._transcriber._model is None:
            self._frame.after(0, lambda: self._status.configure(text="Loading transcriber..."))
            self._transcriber.load()
        text = self._transcriber.transcribe(audio)
        self._frame.after(0, lambda: self._on_transcribed(text))

    def _on_transcribed(self, text: str):
        if text:
            current = self._transcription_box.get("1.0", "end").strip()
            separator = "\n\n" if current else ""
            self._transcription_box.insert("end", separator + text)
        self._set_idle()
        self._state = IDLE
        self._status.configure(text="")

    # ── Generation ────────────────────────────────────────────────────────────

    def _on_generate(self):
        transcription = self._transcription_box.get("1.0", "end").strip()
        if not transcription:
            self._status.configure(text="Add a lecture transcription first.")
            return
        self._state = GENERATING
        self._set_busy()
        self._status.configure(text="Generating notes...")
        mode = self._note_mode.get().lower()
        threading.Thread(target=self._do_generate, args=(transcription, mode), daemon=True).start()

    def _do_generate(self, transcription: str, mode: str = "multi"):
        try:
            if self._improver._model is None:
                self._frame.after(0, lambda: self._status.configure(text="Loading model..."))
                self._improver.load()
            notes = self._improver.generate_notes(transcription, mode=mode)
            if self._cancel_generation:
                self._cancel_generation = False
                self._frame.after(0, self._set_idle)
                self._frame.after(0, lambda: self._status.configure(text="Cancelled."))
                self._frame.after(2000, lambda: self._status.configure(text="Ready."))
                return
            self._frame.after(0, lambda: self._on_notes_ready(notes))
        except Exception as exc:
            self._cancel_generation = False
            msg = str(exc)
            self._frame.after(0, lambda: self._on_generate_error(msg))

    def _on_notes_ready(self, raw: str):
        sections = self._parse_topics(raw)
        if not raw.strip() or all(not content.strip() for _, content in sections):
            self._set_idle()
            self._state = IDLE
            self._status.configure(text="Model returned no content — try regenerating.")
            return
        # Strip LaTeX delimiters the model adds (\( ... \), $...$)
        sections = [(name, _normalize_math_delims(content)) for name, content in sections]

        generated_names = [s[0] for s in sections]
        subject = self._subject_var.get()
        existing = self._subject_note_names(subject) if subject != _NEW_SUBJECT else []
        all_names = sorted(set(generated_names) | set(existing))
        link_options = [_NO_LINK] + all_names

        for w in self._notes_scroll.winfo_children():
            w.destroy()
        self._blocks = []
        self._main_topic = None
        self._link_entry.set("")
        self._link_entry.configure(values=all_names)

        for topic_name, content in sections:
            other_generated = [n for n in generated_names if n != topic_name]
            merge_options = [_STANDALONE] + sorted(set(existing) | set(other_generated))
            block = self._build_block(topic_name, content, merge_options, link_options)
            block.update_idletasks()
            self._bind_scroll(block)

        if not self._notes_shown:
            self._notes_header.pack(fill="x", pady=(8, 2))
            self._notes_scroll.pack(fill="both", expand=True)
            self._notes_shown = True

        self._set_idle()
        self._state = IDLE
        n = len(sections)
        self._status.configure(
            text=f"{n} note{'s' if n != 1 else ''} generated — configure and Save all."
        )

    def _on_generate_error(self, message: str):
        self._set_idle()
        self._state = IDLE
        msg_lower = message.lower()
        if "out of memory" in msg_lower or "cuda" in msg_lower or "oom" in msg_lower:
            friendly = "GPU out of memory — try a shorter transcript or restart the app."
        else:
            friendly = message[:80] + ("…" if len(message) > 80 else "")
        self._status.configure(text=f"Error: {friendly}", text_color="red")
        self._frame.after(5000, lambda: self._status.configure(text="Ready.", text_color="gray"))

    def _build_block(
        self,
        topic_name: str,
        content: str,
        merge_options: list[str],
        link_options: list[str],
    ) -> ctk.CTkFrame:
        block = ctk.CTkFrame(
            self._notes_scroll, fg_color=("gray88", "gray22"), corner_radius=8
        )
        block.pack(fill="x", pady=(0, 8), padx=2)

        # ── Header row: Topic | Include in | as (conditional) ─────────────────
        row1 = ctk.CTkFrame(block, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(8, 2))

        topic_label = ctk.CTkLabel(row1, text="Topic:", font=("Helvetica", 11), text_color="gray")
        topic_label.pack(side="left", padx=(0, 4))
        entry = ctk.CTkEntry(row1, width=190, font=("Helvetica", 12))
        entry.insert(0, topic_name)
        entry.pack(side="left", padx=(0, 14))

        inc_label = ctk.CTkLabel(row1, text="Include in:", font=("Helvetica", 11), text_color="gray")
        inc_label.pack(side="left", padx=(0, 4))
        merge_var = ctk.StringVar(value=_STANDALONE)

        # "as:" controls created before the merge menu so the closure can reference them
        as_label = ctk.CTkLabel(row1, text="as:", font=("Helvetica", 11), text_color="gray")
        label_var = ctk.StringVar(value=_SECTION_LABELS[0])
        as_menu = ctk.CTkOptionMenu(
            row1, values=_SECTION_LABELS, variable=label_var,
            width=120, font=("Helvetica", 11),
        )
        # Hidden by default (starts as standalone)

        def on_merge_change(value: str):
            if value == _STANDALONE:
                as_label.pack_forget()
                as_menu.pack_forget()
                topic_label.pack(side="left", padx=(0, 4), before=inc_label)
                entry.pack(side="left", padx=(0, 14), before=inc_label)
            else:
                topic_label.pack_forget()
                entry.pack_forget()
                as_label.pack(side="left", padx=(0, 4))
                as_menu.pack(side="left")

        merge_menu = _SearchableCombo(
            row1, values=merge_options, variable=merge_var,
            width=180, font=("Helvetica", 11), command=on_merge_change,
        )
        merge_menu.set(_STANDALONE)
        merge_menu.pack(side="left", padx=(0, 8))

        # ── Note textbox — sized to content so all text is visible without internal scroll ──
        line_count = max(len(content.splitlines()), 1)
        box_height = min(max(line_count * 22, 80), 600)
        box = ctk.CTkTextbox(block, height=box_height, font=("Helvetica", 13), wrap="word")
        box.insert("1.0", content)
        box.pack(fill="x", padx=8, pady=(4, 4))

        # ── Link row ─────────────────────────────────────────────────────────
        row3 = ctk.CTkFrame(block, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(
            row3, text="Insert link:", font=("Helvetica", 11), text_color="gray"
        ).pack(side="left", padx=(0, 4))

        link_combo = _SearchableCombo(
            row3, values=link_options, width=220,
            font=("Helvetica", 11),
        )
        link_combo.set(_NO_LINK)
        link_combo.pack(side="left", padx=(0, 6))

        def insert_link():
            val = link_combo.get()
            if val and val != _NO_LINK:
                box.insert("insert", f"[[{val}]]")

        ctk.CTkButton(
            row3, text="Insert", width=70, height=28,
            font=("Helvetica", 11), command=insert_link,
        ).pack(side="left", padx=(0, 6))

        def _do_copy():
            self._frame.clipboard_clear()
            self._frame.clipboard_append(box.get("1.0", "end").strip())

        ctk.CTkButton(
            row3, text="Copy", width=70, height=28,
            font=("Helvetica", 11), command=_do_copy,
        ).pack(side="left", padx=(0, 6))

        block_dict: dict = {}

        main_btn = ctk.CTkButton(
            row3, text="◯ Main", width=80, height=28,
            fg_color="#555", font=("Helvetica", 11),
            command=lambda: self._on_set_main(block_dict),
        )
        main_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row3, text="Delete", width=70, height=28,
            fg_color="#8B2020", font=("Helvetica", 11),
            command=lambda: self._on_delete_block(block, block_dict),
        ).pack(side="left")

        block_dict.update({
            "topic_entry": entry,
            "merge_var": merge_var,
            "merge_menu": merge_menu,
            "as_label": as_label,
            "as_menu": as_menu,
            "label_var": label_var,
            "textbox": box,
            "main_btn": main_btn,
        })
        self._blocks.append(block_dict)
        return block

    def _parse_topics(self, text: str) -> list[tuple[str, str]]:
        import re
        # Match any of: "TOPIC: X", "**Topic: X**", "# Topic: X", "### TOPIC: X", "1. **Topic: X**"
        _TOPIC_RE = re.compile(
            r"^(?:#{1,6}\s*)?(?:\d+\.\s*)?(?:\*{1,2})?(?:TOPIC|Topic|topic)\s*:\s*(?:\*{1,2})?\s*(.+?)\s*\*{0,2}$"
        )

        sections: list[tuple[str, str]] = []
        current_topic: str | None = None
        current_lines: list[str] = []

        for line in text.splitlines():
            m = _TOPIC_RE.match(line.strip())
            if m:
                if current_topic is not None:
                    sections.append((current_topic, "\n".join(current_lines).strip()))
                current_topic = m.group(1)
                current_lines = []
            else:
                current_lines.append(line)

        if current_topic is not None:
            sections.append((current_topic, "\n".join(current_lines).strip()))

        if not sections:
            sections = [("Note", text.strip())]
        return sections

    # ── Save ──────────────────────────────────────────────────────────────────

    def _refresh_merge_menus(self, subject: str):
        existing = self._subject_note_names(subject) if subject != _NEW_SUBJECT else []
        generated_names = [b["topic_entry"].get().strip() for b in self._blocks]
        for b in self._blocks:
            topic_name = b["topic_entry"].get().strip()
            other_generated = [n for n in generated_names if n != topic_name]
            options = [_STANDALONE] + sorted(set(existing) | set(other_generated))
            b["merge_menu"].configure(values=options)
            if b["merge_var"].get() not in options:
                b["merge_var"].set(_STANDALONE)
                b["merge_menu"].set(_STANDALONE)
        self._link_entry.configure(values=sorted(set(generated_names) | set(existing)))

    def _on_save(self):
        if self._subject_var.get() == _NEW_SUBJECT:
            subject = self._new_subject_entry.get().strip()
        else:
            subject = self._subject_var.get()

        if not subject:
            self._status.configure(text="Enter a subject name.")
            return

        block_data = [
            {
                "topic": b["topic_entry"].get().strip(),
                "merge_into": b["merge_var"].get(),
                "section_label": b["label_var"].get(),
                "content": b["textbox"].get("1.0", "end").strip(),
            }
            for b in self._blocks
        ]

        # Standalone notes form the base files; prepend [[main_topic]] wikilink if set
        final: dict[str, str] = {}
        for bd in block_data:
            if bd["merge_into"] == _STANDALONE and bd["topic"] and bd["content"]:
                content = bd["content"]
                if self._main_topic and bd["topic"] != self._main_topic:
                    content = f"[[{self._main_topic}]]\n\n{content}"
                subject_link = f"[[{subject}]]"
                if subject_link not in content:
                    content = f"{subject_link}\n\n{content}"
                final[bd["topic"]] = content

        # Merged notes are appended as sub-sections
        for bd in block_data:
            target = bd["merge_into"]
            if target != _STANDALONE and target in final and bd["content"]:
                final[target] += (
                    f"\n\n## {bd['section_label']}: {bd['topic']}\n{bd['content']}"
                )

        saved = []
        for topic, content in final.items():
            if not topic or "/" in topic or "\\" in topic or ".." in topic:
                continue
            path = Path(DEFAULT_NOTES_DIR) / subject / f"{topic}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            index_path = Path(DEFAULT_NOTES_DIR) / f"{subject}.md"
            if not index_path.exists():
                index_path.write_text(f"# {subject}\n", encoding="utf-8")
            path.write_text(content, encoding="utf-8")
            saved.append(topic)

        # Append into existing on-disk notes
        for bd in block_data:
            target = bd["merge_into"]
            if target == _STANDALONE or target in final or not bd["content"]:
                continue
            target_path = Path(DEFAULT_NOTES_DIR) / subject / f"{target}.md"
            if not target_path.exists():
                continue
            existing_text = target_path.read_text(encoding="utf-8")
            target_path.write_text(
                existing_text.rstrip() + f"\n\n## {bd['section_label']}: {bd['topic']}\n{bd['content']}",
                encoding="utf-8",
            )
            saved.append(f"{bd['topic']} → {target}")

        if not saved:
            self._status.configure(text="No valid notes to save.")
            return

        if self._subject_var.get() == _NEW_SUBJECT:
            subjects = self._subject_list()
            self._subject_menu.configure(values=subjects)
            self._subject_var.set(subject)
            self._new_subject_entry.grid_forget()

        self._refresh_merge_menus(subject)
        plural = "s" if len(saved) != 1 else ""
        self._status.configure(text=f"Saved {len(saved)} note{plural} → {subject}/")

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _on_copy_transcript(self):
        text = self._transcription_box.get("1.0", "end").strip()
        if text:
            self._frame.clipboard_clear()
            self._frame.clipboard_append(text)

    def _on_copy_all_notes(self):
        parts = []
        for b in self._blocks:
            topic = b["topic_entry"].get().strip()
            content = b["textbox"].get("1.0", "end").strip()
            if topic and content:
                parts.append(f"## {topic}\n\n{content}")
        if parts:
            self._frame.clipboard_clear()
            self._frame.clipboard_append("\n\n---\n\n".join(parts))

    def _on_link_all(self):
        topic = self._link_entry.get().strip()
        if not topic:
            return
        wikilink = f"[[{topic}]]\n\n"
        for b in self._blocks:
            if b["merge_var"].get() != _STANDALONE:
                continue
            box = b["textbox"]
            current = box.get("1.0", "end").rstrip("\n")
            if not current.startswith(f"[[{topic}]]"):
                box.delete("1.0", "end")
                box.insert("1.0", wikilink + current)
        self._link_all_btn.configure(text="Linked ✓")
        self._frame.after(1500, lambda: self._link_all_btn.configure(text="Link all"))

    def _on_delete_block(self, block_frame: ctk.CTkFrame, block_dict: dict):
        topic = block_dict["topic_entry"].get().strip() or "this block"
        if not tk.messagebox.askyesno("Delete block", f"Delete '{topic}'?", parent=self._frame):
            return
        if self._main_topic == topic:
            self._main_topic = None
        if block_dict in self._blocks:
            self._blocks.remove(block_dict)
        block_frame.destroy()
        subject = self._subject_var.get()
        self._refresh_merge_menus(subject)

    def _on_set_main(self, block_dict: dict):
        topic = block_dict["topic_entry"].get().strip()
        if self._main_topic == topic:
            self._main_topic = None
            block_dict["main_btn"].configure(text="◯ Main")
        else:
            self._main_topic = topic
            for b in self._blocks:
                b["main_btn"].configure(text="◯ Main")
            block_dict["main_btn"].configure(text="✓ Main")

    def _on_clear_transcription(self):
        self._transcription_box.delete("1.0", "end")
