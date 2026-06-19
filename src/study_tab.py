import re
import threading
import customtkinter as ctk

from note_reader import load_notes, pick_random_subtopic, list_subtopics
from confidence import (
    load_scores, save_scores, update_score,
    load_exclusions, save_exclusions,
)

_LATEX_SYMBOLS = [
    # \mathbb — before any commands that share a prefix
    (r"\mathbb{N}", "ℕ"), (r"\mathbb{Z}", "ℤ"), (r"\mathbb{R}", "ℝ"),
    (r"\mathbb{Q}", "ℚ"), (r"\mathbb{C}", "ℂ"), (r"\mathbb{P}", "ℙ"),
    # Set operations
    (r"\bigoplus", "⊕"), (r"\oplus", "⊕"),
    (r"\cup", "∪"), (r"\cap", "∩"), (r"\setminus", "∖"), (r"\emptyset", "∅"),
    (r"\triangle", "△"),
    # Relations — longer forms before any that share a prefix
    (r"\subseteq", "⊆"), (r"\supseteq", "⊇"), (r"\subset", "⊂"), (r"\supset", "⊃"),
    (r"\notin", "∉"),
    (r"\infty", "∞"),   # before \in
    (r"\int", "∫"),     # before \in
    (r"\in", "∈"),
    (r"\neq", "≠"), (r"\leq", "≤"), (r"\geq", "≥"),
    (r"\approx", "≈"), (r"\equiv", "≡"), (r"\sim", "∼"), (r"\cong", "≅"),
    # Logic & arrows — longer forms first
    (r"\Leftrightarrow", "⟺"), (r"\Rightarrow", "⟹"),
    (r"\leftrightarrow", "↔"), (r"\rightarrow", "→"), (r"\leftarrow", "←"),
    (r"\mapsto", "↦"),
    (r"\forall", "∀"), (r"\exists", "∃"),
    (r"\neg", "¬"), (r"\land", "∧"), (r"\lor", "∨"),
    # Misc math
    (r"\times", "×"), (r"\div", "÷"), (r"\pm", "±"), (r"\cdot", "·"),
    (r"\ldots", "…"), (r"\dots", "…"),
    (r"\sum", "∑"), (r"\prod", "∏"), (r"\partial", "∂"),
    (r"\sqrt", "√"),
    # Greek — var- forms before base forms
    (r"\varepsilon", "ε"), (r"\vartheta", "θ"), (r"\varphi", "φ"),
    (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"), (r"\delta", "δ"),
    (r"\epsilon", "ε"), (r"\zeta", "ζ"), (r"\eta", "η"), (r"\theta", "θ"),
    (r"\iota", "ι"), (r"\kappa", "κ"), (r"\lambda", "λ"), (r"\mu", "μ"),
    (r"\nu", "ν"), (r"\xi", "ξ"), (r"\pi", "π"), (r"\rho", "ρ"),
    (r"\sigma", "σ"), (r"\tau", "τ"), (r"\upsilon", "υ"), (r"\phi", "φ"),
    (r"\chi", "χ"), (r"\psi", "ψ"), (r"\omega", "ω"),
    (r"\Gamma", "Γ"), (r"\Delta", "Δ"), (r"\Theta", "Θ"), (r"\Lambda", "Λ"),
    (r"\Xi", "Ξ"), (r"\Pi", "Π"), (r"\Sigma", "Σ"), (r"\Upsilon", "Υ"),
    (r"\Phi", "Φ"), (r"\Psi", "Ψ"), (r"\Omega", "Ω"),
    # Braces
    (r"\{", "{"), (r"\}", "}"),
]


def _render_latex(text: str) -> str:
    # Structural commands with arguments — apply before symbol table
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√\1", text)
    text = re.sub(r"\\text\{([^{}]+)\}", r"\1", text)
    # Symbol replacements
    for latex, symbol in _LATEX_SYMBOLS:
        text = text.replace(latex, symbol)
    # Strip math delimiters
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\\[|\\\]", "", text)
    text = re.sub(r"\$\$|\$", "", text)
    return text

SETUP = "setup"
GENERATING = "generating"
READY = "ready"
RECORDING = "recording"
EVALUATING = "evaluating"
RESULT = "result"


class StudyTab:
    def __init__(self, parent: ctk.CTkFrame, recorder, transcriber, improver):
        self._recorder = recorder
        self._transcriber = transcriber
        self._improver = improver
        self._notes: dict = {}
        self._scores: dict = {}
        self._current: tuple | None = None  # (subject, subtopic, combined_content)
        self._current_question: str = ""
        self._state: str = SETUP
        self._inactivity_timer: str | None = None

        self._load_data()
        self._build_ui(parent)
        self._show_setup()

    def _load_data(self):
        self._notes = load_notes()
        self._scores = load_scores()
        self._excluded: set[str] = load_exclusions()

    def _filtered_notes(self) -> dict:
        result = {}
        for subject, subtopics in self._notes.items():
            filtered = {
                st: topics
                for st, topics in subtopics.items()
                if f"{subject}/{st}" not in self._excluded
            }
            if filtered:
                result[subject] = filtered
        return result

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self, parent: ctk.CTkFrame):
        self._frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._frame.pack(fill="both", expand=True, padx=12, pady=12)

        self._status = ctk.CTkLabel(
            self._frame, text="", font=("Helvetica", 12), text_color="gray"
        )
        self._status.pack(anchor="w", pady=(0, 6))

        # ── Setup widgets ────────────────────────────────────────────────────
        self._setup_frame = ctk.CTkFrame(self._frame, fg_color="transparent")

        ctk.CTkLabel(
            self._setup_frame, text="Topic selection", font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(0, 4))

        self._sel_row = ctk.CTkFrame(self._setup_frame, fg_color="transparent")
        sel_row = self._sel_row
        sel_row.pack(anchor="w", pady=(0, 8))

        self._sel_var = ctk.StringVar(value="Manual")
        for mode in ("Manual", "Random", "Confidence"):
            ctk.CTkRadioButton(
                sel_row, text=mode, variable=self._sel_var, value=mode,
                command=self._on_selection_mode_change, font=("Helvetica", 12),
            ).pack(side="left", padx=6)

        subjects = list(self._notes.keys()) or ["(no notes found)"]
        self._subject_var = ctk.StringVar(value=subjects[0])
        self._subject_label = ctk.CTkLabel(
            self._setup_frame, text="Subject", font=("Helvetica", 11), text_color="gray",
        )
        self._subject_label.pack(anchor="w", pady=(0, 2))
        self._subject_menu = ctk.CTkOptionMenu(
            self._setup_frame, values=subjects, variable=self._subject_var,
            width=240, font=("Helvetica", 12), command=self._on_subject_change,
        )
        self._subject_menu.pack(anchor="w", pady=(0, 4))

        subtopics = ["All"] + list_subtopics(subjects[0])
        self._subtopic_var = ctk.StringVar(value="All")
        self._subtopic_label = ctk.CTkLabel(
            self._setup_frame, text="Subtopic", font=("Helvetica", 11), text_color="gray",
        )
        self._subtopic_label.pack(anchor="w", pady=(0, 2))
        self._subtopic_menu = ctk.CTkOptionMenu(
            self._setup_frame, values=subtopics, variable=self._subtopic_var,
            width=240, font=("Helvetica", 12),
        )
        self._subtopic_menu.pack(anchor="w", pady=(0, 12))

        self._study_controls = ctk.CTkFrame(self._setup_frame, fg_color="transparent")
        self._study_controls.pack(anchor="w")

        ctk.CTkLabel(
            self._study_controls, text="Question type", font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(0, 4))
        self._qtype_var = ctk.StringVar(value="Flashcard")
        ctk.CTkSegmentedButton(
            self._study_controls, values=["Flashcard", "Extended"],
            variable=self._qtype_var, width=200, font=("Helvetica", 12),
        ).pack(anchor="w", pady=(0, 16))

        _btn_row = ctk.CTkFrame(self._study_controls, fg_color="transparent")
        _btn_row.pack(anchor="w")
        self._start_btn = ctk.CTkButton(
            _btn_row, text="Start →", width=140, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_start,
        )
        self._start_btn.pack(side="left")
        self._manage_btn = ctk.CTkButton(
            _btn_row, text="Manage exclusions", width=160, height=44,
            fg_color="#555", command=self._open_exclusions_window,
        )
        self._manage_btn.pack(side="left", padx=(12, 0))

        # ── Confidence overview (shown instead of study controls) ────────────
        self._overview_frame = ctk.CTkFrame(self._setup_frame, fg_color="transparent")
        # not packed initially

        ctk.CTkLabel(
            self._overview_frame, text="Confidence Overview",
            font=("Helvetica", 13, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        _ov_sel = ctk.CTkFrame(self._overview_frame, fg_color="transparent")
        _ov_sel.pack(anchor="w", pady=(0, 8))

        subjects_ov = list(self._notes.keys()) or ["(no notes found)"]
        self._ov_subject_var = ctk.StringVar(value=subjects_ov[0])
        ctk.CTkLabel(
            _ov_sel, text="Subject", font=("Helvetica", 11), text_color="gray",
        ).pack(anchor="w", pady=(0, 2))
        ctk.CTkOptionMenu(
            _ov_sel, values=subjects_ov, variable=self._ov_subject_var,
            width=240, font=("Helvetica", 12), command=self._on_ov_subject_change,
        ).pack(anchor="w", pady=(0, 8))

        _ov_subtopics = ["All"] + list_subtopics(subjects_ov[0])
        self._ov_subtopic_var = ctk.StringVar(value="All")
        ctk.CTkLabel(
            _ov_sel, text="Subtopic", font=("Helvetica", 11), text_color="gray",
        ).pack(anchor="w", pady=(0, 2))
        self._ov_subtopic_menu = ctk.CTkOptionMenu(
            _ov_sel, values=_ov_subtopics, variable=self._ov_subtopic_var,
            width=240, font=("Helvetica", 12), command=self._refresh_confidence_chart,
        )
        self._ov_subtopic_menu.pack(anchor="w")

        self._conf_scroll = ctk.CTkScrollableFrame(self._overview_frame, height=300)
        self._conf_scroll.pack(fill="both", expand=True, pady=(8, 0))

        # ── Session widgets ──────────────────────────────────────────────────
        self._session_frame = ctk.CTkFrame(self._frame, fg_color="transparent")

        self._question_label = ctk.CTkLabel(
            self._session_frame, text="", font=("Helvetica", 15, "bold"),
            wraplength=620, justify="center",
        )
        self._question_label.pack(pady=(8, 4))

        self._source_label = ctk.CTkLabel(
            self._session_frame, text="", font=("Helvetica", 11), text_color="gray",
        )
        self._source_label.pack(pady=(0, 8))

        # Always-visible editable answer box
        ctk.CTkLabel(
            self._session_frame, text="Your answer", font=("Helvetica", 11),
            text_color="gray",
        ).pack()
        self._answer_box = ctk.CTkTextbox(
            self._session_frame, width=600, height=90,
            font=("Helvetica", 13), wrap="word",
        )
        self._answer_box.pack(pady=(2, 8))

        # Button row: Record | Stop | Submit | Clear
        self._btn_row = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        self._btn_row.pack(pady=(0, 12))

        self._record_btn = ctk.CTkButton(
            self._btn_row, text="● Record", width=130, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_record,
        )
        self._record_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = ctk.CTkButton(
            self._btn_row, text="■ Stop", width=110, height=44,
            font=("Helvetica", 14, "bold"), fg_color="#2980b9",
            command=self._on_stop,
        )

        self._submit_btn = ctk.CTkButton(
            self._btn_row, text="Submit →", width=120, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_submit,
        )
        self._submit_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self._btn_row, text="Clear", width=80, height=44,
            fg_color="#555", command=self._on_clear_answer,
        ).pack(side="left")

        # Feedback box (read-only, shown after evaluation)
        self._feedback_label = ctk.CTkLabel(
            self._session_frame, text="Feedback", font=("Helvetica", 11),
            text_color="gray",
        )
        self._result_box = ctk.CTkTextbox(
            self._session_frame, width=600, height=140,
            font=("Helvetica", 13), wrap="word", state="disabled",
        )

        # Confidence bar
        self._conf_frame = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        ctk.CTkLabel(
            self._conf_frame, text="Confidence:", font=("Helvetica", 11)
        ).pack(side="left", padx=(0, 6))
        self._conf_bar = ctk.CTkProgressBar(self._conf_frame, width=200)
        self._conf_bar.set(0.5)
        self._conf_bar.pack(side="left")
        self._conf_label = ctk.CTkLabel(
            self._conf_frame, text="50%", font=("Helvetica", 11)
        )
        self._conf_label.pack(side="left", padx=(6, 0))

        # Next / Change topic / Exclude row
        self._nav_row = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        ctk.CTkButton(
            self._nav_row, text="Next →", width=110, height=40,
            command=self._on_next,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self._nav_row, text="Change topic", width=130, height=40,
            fg_color="#555", command=self._show_setup,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self._nav_row, text="Exclude subtopic", width=140, height=40,
            fg_color="#8B0000", command=self._on_exclude,
        ).pack(side="left")

    def _on_subject_change(self, value: str):
        subtopics = ["All"] + list_subtopics(value)
        self._subtopic_var.set("All")
        self._subtopic_menu.configure(values=subtopics)

    def _on_ov_subject_change(self, value: str):
        subs = ["All"] + list_subtopics(value)
        self._ov_subtopic_var.set("All")
        self._ov_subtopic_menu.configure(values=subs)
        self._refresh_confidence_chart()

    def _refresh_confidence_chart(self, *_):
        for w in self._conf_scroll.winfo_children():
            w.destroy()
        subject = self._ov_subject_var.get()
        subtopic = self._ov_subtopic_var.get()
        if subtopic == "All":
            pairs = [
                (subject, st)
                for st in self._notes.get(subject, {})
                if st != subject  # skip synthetic subtopic
            ]
        else:
            pairs = [(subject, subtopic)] if self._notes.get(subject, {}).get(subtopic) else []
        if not pairs:
            ctk.CTkLabel(
                self._conf_scroll, text="No notes here yet.",
                font=("Helvetica", 12), text_color="gray",
            ).pack(pady=16)
            return
        for subj, st in sorted(pairs, key=lambda x: x[1]):
            score = self._scores.get(f"{subj}/{st}", 0.5)
            color = "#c0392b" if score < 0.4 else "#f39c12" if score < 0.7 else "#27ae60"
            row = ctk.CTkFrame(self._conf_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=st, font=("Helvetica", 12), anchor="w", width=260,
            ).pack(side="left")
            bar = ctk.CTkProgressBar(row, width=180, progress_color=color)
            bar.set(score)
            bar.pack(side="left", padx=(8, 4))
            ctk.CTkLabel(
                row, text=f"{int(score * 100)}%", font=("Helvetica", 11),
            ).pack(side="left")

    def _on_selection_mode_change(self):
        mode = self._sel_var.get()
        if mode == "Confidence":
            self._subject_label.pack_forget()
            self._subject_menu.pack_forget()
            self._subtopic_label.pack_forget()
            self._subtopic_menu.pack_forget()
            self._study_controls.pack_forget()
            self._overview_frame.pack(fill="both", expand=True)
            self._refresh_confidence_chart()
        elif mode == "Manual":
            self._overview_frame.pack_forget()
            self._subject_label.pack(anchor="w", pady=(0, 2), after=self._sel_row)
            self._subject_menu.pack(anchor="w", pady=(0, 4), after=self._subject_label)
            self._subtopic_label.pack(anchor="w", pady=(0, 2), after=self._subject_menu)
            self._subtopic_menu.pack(anchor="w", pady=(0, 12), after=self._subtopic_label)
            self._study_controls.pack(anchor="w", after=self._subtopic_menu)
        else:  # Random
            self._overview_frame.pack_forget()
            self._subject_label.pack_forget()
            self._subject_menu.pack_forget()
            self._subtopic_label.pack_forget()
            self._subtopic_menu.pack_forget()
            self._study_controls.pack(anchor="w", after=self._sel_row)

    # ── Phase transitions ────────────────────────────────────────────────────

    def _show_setup(self):
        if self._inactivity_timer:
            self._frame.after_cancel(self._inactivity_timer)
            self._inactivity_timer = None
        self._session_frame.pack_forget()
        self._setup_frame.pack(fill="both", expand=True)
        self._state = SETUP
        self._status.configure(text="Choose a topic and question type")
        if self._sel_var.get() != "Manual":
            self._subject_label.pack_forget()
            self._subject_menu.pack_forget()
            self._subtopic_label.pack_forget()
            self._subtopic_menu.pack_forget()

    def _show_session(self):
        self._setup_frame.pack_forget()
        self._answer_box.delete("1.0", "end")
        self._feedback_label.pack_forget()
        self._result_box.pack_forget()
        self._conf_frame.pack_forget()
        self._nav_row.pack_forget()
        self._stop_btn.pack_forget()
        self._record_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 6), before=self._submit_btn)
        self._record_btn.configure(state="normal")
        self._submit_btn.configure(state="normal")
        self._session_frame.pack(fill="both", expand=True)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_start(self):
        notes = self._filtered_notes()
        if not notes:
            self._status.configure(
                text="No notes found — check NOTES_DIR or generate some notes first."
            )
            return
        mode = self._sel_var.get()
        if mode == "Manual":
            subject = self._subject_var.get()
            subtopic = self._subtopic_var.get()
            if subject not in notes:
                self._status.configure(text=f"All notes in {subject!r} are excluded.")
                return
            if subtopic == "All":
                self._current = pick_random_subtopic(notes, subject=subject)
            elif subtopic not in self._notes.get(subject, {}):
                self._status.configure(text=f"No notes in '{subtopic}' yet.")
                return
            elif subtopic not in notes.get(subject, {}):
                self._status.configure(text=f"All notes in '{subtopic}' are excluded.")
                return
            else:
                self._current = pick_random_subtopic(notes, subject=subject, subtopic=subtopic)
        else:
            self._current = pick_random_subtopic(notes)
        self._show_session()
        self._generate_question()

    def _generate_question(self):
        assert self._current is not None
        self._state = GENERATING
        self._status.configure(text="Generating question...")
        self._record_btn.configure(state="disabled")
        self._submit_btn.configure(state="disabled")
        _, _, content = self._current
        style = self._qtype_var.get()
        threading.Thread(
            target=self._do_generate, args=(content, style), daemon=True
        ).start()

    def _do_generate(self, content: str, style: str):
        if self._improver._model is None:
            self._frame.after(0, lambda: self._status.configure(text="Loading model..."))
            self._improver.load()
        question = self._improver.generate_question(content, style)
        self._frame.after(0, lambda: self._on_question_ready(question))

    def _on_question_ready(self, question: str):
        assert self._current is not None
        subject, subtopic, _ = self._current
        self._current_question = question
        self._question_label.configure(text=question)
        self._source_label.configure(text=f"{subject} › {subtopic}")
        key = f"{subject}/{subtopic}"
        score = self._scores.get(key, 0.5)
        self._conf_bar.set(score)
        self._conf_label.configure(text=f"{int(score * 100)}%")
        self._answer_box.delete("1.0", "end")
        self._state = READY
        self._status.configure(text="Record your answer")
        self._record_btn.configure(state="normal")
        self._submit_btn.configure(state="normal")
        if self._inactivity_timer:
            self._frame.after_cancel(self._inactivity_timer)
        self._inactivity_timer = self._frame.after(5 * 60 * 1000, self._unload_idle)

    def _on_record(self):
        self._state = RECORDING
        self._record_btn.pack_forget()
        self._stop_btn.pack(side="left", padx=(0, 6), before=self._submit_btn)
        self._submit_btn.configure(state="disabled")
        self._status.configure(text="Recording...")
        self._recorder.start()

    def _on_stop(self):
        if self._state != RECORDING:
            return
        audio = self._recorder.stop()
        self._stop_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 6), before=self._submit_btn)
        self._record_btn.configure(state="disabled")
        self._submit_btn.configure(state="disabled")
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
            current = self._answer_box.get("1.0", "end").strip()
            separator = "\n\n" if current else ""
            self._answer_box.insert("end", separator + text)
        self._record_btn.configure(state="normal")
        self._submit_btn.configure(state="normal")
        self._state = READY
        self._status.configure(text="Record more or edit, then submit.")

    def _on_clear_answer(self):
        self._answer_box.delete("1.0", "end")

    def _on_submit(self):
        if self._inactivity_timer:
            self._frame.after_cancel(self._inactivity_timer)
            self._inactivity_timer = None
        answer = self._answer_box.get("1.0", "end").strip()
        if not answer:
            return
        self._state = EVALUATING
        self._record_btn.configure(state="disabled")
        self._submit_btn.configure(state="disabled")
        self._status.configure(text="Evaluating...")
        assert self._current is not None
        _, _, content = self._current
        threading.Thread(
            target=self._do_evaluate, args=(answer, content), daemon=True
        ).start()

    def _do_evaluate(self, answer: str, content: str):
        try:
            result = self._improver.evaluate_answer(self._current_question, content, answer)
        finally:
            self._improver.unload()
        self._frame.after(0, lambda: self._on_result(result))

    def _on_result(self, result: str):
        assert self._current is not None
        subject, subtopic, _ = self._current
        key = f"{subject}/{subtopic}"

        verdict = "Partial"
        for line in result.splitlines():
            if "Verdict:" in line:
                if "Correct" in line and "Incorrect" not in line:
                    verdict = "Correct"
                elif "Incorrect" in line:
                    verdict = "Incorrect"
                break

        self._scores = update_score(self._scores, key, verdict)
        threading.Thread(target=save_scores, args=(self._scores,), daemon=True).start()

        score = self._scores.get(key, 0.5)
        self._conf_bar.set(score)
        self._conf_label.configure(text=f"{int(score * 100)}%")

        self._feedback_label.pack()
        self._result_box.configure(state="normal")
        self._result_box.delete("1.0", "end")
        self._result_box.insert("1.0", _render_latex(result))
        self._result_box.configure(state="disabled")
        self._result_box.pack(pady=(0, 8))
        self._conf_frame.pack(pady=(0, 8))
        self._nav_row.pack(pady=(0, 8))

        self._state = RESULT
        self._status.configure(text="")
        self._record_btn.configure(state="normal")
        self._submit_btn.configure(state="normal")

    def _unload_idle(self):
        self._inactivity_timer = None
        if self._state == READY:
            self._improver.unload()
            self._show_setup()
            self._status.configure(text="Session timed out — choose a topic to restart.")

    def _on_next(self):
        self._feedback_label.pack_forget()
        self._result_box.pack_forget()
        self._conf_frame.pack_forget()
        self._nav_row.pack_forget()
        notes = self._filtered_notes()
        if not notes:
            self._show_setup()
            self._status.configure(text="All notes excluded — unexclude some to continue.")
            return
        mode = self._sel_var.get()
        if mode == "Manual":
            subject = self._subject_var.get()
            subtopic = self._subtopic_var.get()
            if subject not in notes:
                self._show_setup()
                self._status.configure(text=f"All notes in {subject!r} are excluded.")
                return
            if subtopic == "All":
                self._current = pick_random_subtopic(notes, subject=subject)
            elif subtopic not in self._notes.get(subject, {}):
                self._show_setup()
                self._status.configure(text=f"No notes in '{subtopic}' yet.")
                return
            elif subtopic not in notes.get(subject, {}):
                self._show_setup()
                self._status.configure(text=f"All notes in '{subtopic}' are excluded.")
                return
            else:
                self._current = pick_random_subtopic(notes, subject=subject, subtopic=subtopic)
        else:
            self._current = pick_random_subtopic(notes)
        self._generate_question()

    def _on_exclude(self):
        assert self._current is not None
        subject, subtopic, _ = self._current
        self._excluded.add(f"{subject}/{subtopic}")
        threading.Thread(
            target=save_exclusions, args=(self._excluded,), daemon=True
        ).start()
        self._on_next()

    def _open_exclusions_window(self):
        win = ctk.CTkToplevel(self._frame)
        win.title("Excluded notes")
        win.geometry("420x400")
        win.resizable(False, True)

        ctk.CTkLabel(
            win, text="Excluded notes", font=("Helvetica", 14, "bold")
        ).pack(anchor="w", padx=16, pady=(12, 4))

        if not self._excluded:
            ctk.CTkLabel(
                win, text="No notes are currently excluded.",
                font=("Helvetica", 12), text_color="gray",
            ).pack(anchor="w", padx=16, pady=(8, 0))
            return

        ctk.CTkLabel(
            win, text="Click Restore to put a note back in the study pool.",
            font=("Helvetica", 11), text_color="gray",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(win, height=300)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        def make_restore(key: str, row: ctk.CTkFrame):
            def restore():
                self._excluded.discard(key)
                threading.Thread(
                    target=save_exclusions, args=(self._excluded,), daemon=True
                ).start()
                row.destroy()
                if not self._excluded:
                    win.destroy()
                    self._status.configure(text="All exclusions cleared.")
            return restore

        for key in sorted(self._excluded):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=key.replace("/", " › "), font=("Helvetica", 12), anchor="w"
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="Restore", width=80, height=30,
                fg_color="#2e7d32", command=make_restore(key, row),
            ).pack(side="right")
