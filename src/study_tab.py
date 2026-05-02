import re
import threading
import customtkinter as ctk

from note_reader import load_notes, pick_random_note
from confidence import (
    load_scores, save_scores, update_score, pick_by_confidence, score_key,
    load_exclusions, save_exclusions,
)

_LATEX_SYMBOLS = [
    # Set operations
    (r"\cup", "∪"), (r"\cap", "∩"), (r"\setminus", "∖"), (r"\emptyset", "∅"),
    (r"\bigoplus", "⊕"), (r"\oplus", "⊕"), (r"\triangle", "△"),
    # Relations
    (r"\subseteq", "⊆"), (r"\supseteq", "⊇"), (r"\subset", "⊂"), (r"\supset", "⊃"),
    (r"\in", "∈"), (r"\notin", "∉"),
    # Logic
    (r"\forall", "∀"), (r"\exists", "∃"), (r"\neg", "¬"), (r"\land", "∧"), (r"\lor", "∨"),
    (r"\Rightarrow", "⟹"), (r"\rightarrow", "→"),
    (r"\Leftrightarrow", "⟺"), (r"\leftrightarrow", "↔"),
    # Misc math
    (r"\times", "×"), (r"\infty", "∞"), (r"\mathbb{N}", "ℕ"), (r"\mathbb{Z}", "ℤ"),
    (r"\mathbb{R}", "ℝ"), (r"\mathbb{Q}", "ℚ"),
    # Braces
    (r"\{", "{"), (r"\}", "}"),
]


def _render_latex(text: str) -> str:
    """Replace common LaTeX math commands with Unicode equivalents."""
    for latex, symbol in _LATEX_SYMBOLS:
        text = text.replace(latex, symbol)
    # Strip \(...\) and \[...\] delimiters
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\\[|\\\]", "", text)
    # Strip $...$ and $$...$$ delimiters
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
        self._current: tuple | None = None  # (subject, topic, content)
        self._current_question: str = ""
        self._state: str = SETUP

        self._load_data()
        self._build_ui(parent)
        self._show_setup()

    def _load_data(self):
        self._notes = load_notes()
        self._scores = load_scores()
        self._excluded: set[str] = load_exclusions()

    def _filtered_notes(self) -> dict:
        return {
            subject: {t: c for t, c in topics.items()
                      if score_key(subject, t) not in self._excluded}
            for subject, topics in self._notes.items()
            if any(score_key(subject, t) not in self._excluded for t in topics)
        }

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

        sel_row = ctk.CTkFrame(self._setup_frame, fg_color="transparent")
        sel_row.pack(anchor="w", pady=(0, 8))

        self._sel_var = ctk.StringVar(value="Manual")
        for mode in ("Manual", "Random", "Confidence"):
            ctk.CTkRadioButton(
                sel_row, text=mode, variable=self._sel_var, value=mode,
                command=self._on_selection_mode_change, font=("Helvetica", 12),
            ).pack(side="left", padx=6)

        subjects = list(self._notes.keys()) or ["(no notes found)"]
        self._subject_var = ctk.StringVar(value=subjects[0])
        self._subject_menu = ctk.CTkOptionMenu(
            self._setup_frame, values=subjects, variable=self._subject_var,
            width=240, font=("Helvetica", 12),
        )
        self._subject_menu.pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            self._setup_frame, text="Question type", font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(0, 4))
        self._qtype_var = ctk.StringVar(value="Flashcard")
        ctk.CTkSegmentedButton(
            self._setup_frame, values=["Flashcard", "Extended"],
            variable=self._qtype_var, width=200, font=("Helvetica", 12),
        ).pack(anchor="w", pady=(0, 16))

        self._start_btn = ctk.CTkButton(
            self._setup_frame, text="Start →", width=140, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_start,
        )
        self._start_btn.pack(side="left", anchor="w")

        self._manage_btn = ctk.CTkButton(
            self._setup_frame, text="Manage exclusions", width=160, height=44,
            fg_color="#555", command=self._open_exclusions_window,
        )
        self._manage_btn.pack(side="left", anchor="w", padx=(12, 0))

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
            self._nav_row, text="Exclude note", width=120, height=40,
            fg_color="#8B0000", command=self._on_exclude,
        ).pack(side="left")

    def _on_selection_mode_change(self):
        if self._sel_var.get() == "Manual":
            self._subject_menu.pack(anchor="w", pady=(0, 12))
        else:
            self._subject_menu.pack_forget()

    # ── Phase transitions ────────────────────────────────────────────────────

    def _show_setup(self):
        self._session_frame.pack_forget()
        self._setup_frame.pack(fill="both", expand=True)
        self._state = SETUP
        self._status.configure(text="Choose a topic and question type")
        if self._sel_var.get() != "Manual":
            self._subject_menu.pack_forget()

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
                text="No notes available — all excluded or ~/uni/ is empty."
            )
            return
        mode = self._sel_var.get()
        if mode == "Manual":
            subject = self._subject_var.get()
            if subject not in notes:
                self._status.configure(text=f"All notes in {subject!r} are excluded.")
                return
            self._current = pick_random_note(notes, subject=subject)
        elif mode == "Random":
            self._current = pick_random_note(notes)
        else:
            self._current = pick_by_confidence(notes, self._scores)
        self._show_session()
        self._generate_question()

    def _generate_question(self):
        self._state = GENERATING
        self._status.configure(text="Generating question...")
        self._record_btn.configure(state="disabled")
        self._submit_btn.configure(state="disabled")
        subject, topic, content = self._current
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
        subject, topic, _ = self._current
        self._current_question = question
        self._question_label.configure(text=question)
        self._source_label.configure(text=f"{subject} › {topic}")
        key = score_key(subject, topic)
        score = self._scores.get(key, 0.5)
        self._conf_bar.set(score)
        self._conf_label.configure(text=f"{int(score * 100)}%")
        self._answer_box.delete("1.0", "end")
        self._state = READY
        self._status.configure(text="Record your answer")
        self._record_btn.configure(state="normal")
        self._submit_btn.configure(state="normal")

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
        answer = self._answer_box.get("1.0", "end").strip()
        if not answer:
            return
        self._state = EVALUATING
        self._record_btn.configure(state="disabled")
        self._submit_btn.configure(state="disabled")
        self._status.configure(text="Evaluating...")
        _, _, content = self._current
        threading.Thread(
            target=self._do_evaluate, args=(answer, content), daemon=True
        ).start()

    def _do_evaluate(self, answer: str, content: str):
        result = self._improver.evaluate_answer(self._current_question, content, answer)
        self._frame.after(0, lambda: self._on_result(result))

    def _on_result(self, result: str):
        subject, topic, _ = self._current
        key = score_key(subject, topic)

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
            if subject not in notes:
                self._show_setup()
                self._status.configure(text=f"All notes in {subject!r} are excluded.")
                return
            self._current = pick_random_note(notes, subject=subject)
        elif mode == "Random":
            self._current = pick_random_note(notes)
        else:
            self._current = pick_by_confidence(notes, self._scores)
        self._generate_question()

    def _on_exclude(self):
        subject, topic, _ = self._current
        self._excluded.add(score_key(subject, topic))
        threading.Thread(
            target=save_exclusions, args=(self._excluded,), daemon=True
        ).start()
        self._on_next()

    def _open_exclusions_window(self):
        if not self._excluded:
            self._status.configure(text="No notes are currently excluded.")
            return

        win = ctk.CTkToplevel(self._frame)
        win.title("Excluded notes")
        win.geometry("420x400")
        win.resizable(False, True)

        ctk.CTkLabel(
            win, text="Excluded notes", font=("Helvetica", 14, "bold")
        ).pack(anchor="w", padx=16, pady=(12, 4))
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
