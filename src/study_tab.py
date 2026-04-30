import threading
import customtkinter as ctk

from note_reader import load_notes, pick_random_note
from confidence import load_scores, save_scores, update_score, pick_by_confidence, score_key

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
        self._start_btn.pack(anchor="w")

        # ── Session widgets ──────────────────────────────────────────────────
        self._session_frame = ctk.CTkFrame(self._frame, fg_color="transparent")

        self._question_label = ctk.CTkLabel(
            self._session_frame, text="", font=("Helvetica", 15, "bold"),
            wraplength=580, justify="left",
        )
        self._question_label.pack(anchor="w", pady=(0, 4))

        self._source_label = ctk.CTkLabel(
            self._session_frame, text="", font=("Helvetica", 11), text_color="gray",
        )
        self._source_label.pack(anchor="w", pady=(0, 12))

        self._record_row = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        self._record_row.pack(anchor="w", pady=(0, 12))

        self._record_btn = ctk.CTkButton(
            self._record_row, text="● Record", width=130, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_record,
        )
        self._record_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = ctk.CTkButton(
            self._record_row, text="■ Stop", width=110, height=44,
            font=("Helvetica", 14, "bold"), fg_color="#2980b9",
            command=self._on_stop,
        )

        self._result_box = ctk.CTkTextbox(
            self._session_frame, width=580, height=160,
            font=("Helvetica", 13), wrap="word", state="disabled",
        )

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

        self._nav_row = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        ctk.CTkButton(
            self._nav_row, text="Next →", width=110, height=40,
            command=self._on_next,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self._nav_row, text="Change topic", width=130, height=40,
            fg_color="#555", command=self._show_setup,
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
        self._result_box.pack_forget()
        self._conf_frame.pack_forget()
        self._nav_row.pack_forget()
        self._stop_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 8))
        self._session_frame.pack(fill="both", expand=True)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_start(self):
        if not self._notes:
            self._status.configure(text="No notes found in ~/uni/")
            return
        mode = self._sel_var.get()
        if mode == "Manual":
            self._current = pick_random_note(self._notes, subject=self._subject_var.get())
        elif mode == "Random":
            self._current = pick_random_note(self._notes)
        else:
            self._current = pick_by_confidence(self._notes, self._scores)
        self._show_session()
        self._generate_question()

    def _generate_question(self):
        self._state = GENERATING
        self._status.configure(text="Generating question...")
        self._record_btn.configure(state="disabled")
        subject, topic, content = self._current
        style = self._qtype_var.get()
        threading.Thread(
            target=self._do_generate, args=(content, style), daemon=True
        ).start()

    def _do_generate(self, content: str, style: str):
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
        self._state = READY
        self._status.configure(text="Record your answer")
        self._record_btn.configure(state="normal")

    def _on_record(self):
        self._state = RECORDING
        self._record_btn.pack_forget()
        self._stop_btn.pack(side="left")
        self._status.configure(text="Recording...")
        self._recorder.start()

    def _on_stop(self):
        if self._state != RECORDING:
            return
        self._state = EVALUATING
        audio = self._recorder.stop()
        self._stop_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 8))
        self._record_btn.configure(state="disabled")
        self._status.configure(text="Transcribing...")
        threading.Thread(
            target=self._do_transcribe_and_evaluate, args=(audio,), daemon=True
        ).start()

    def _do_transcribe_and_evaluate(self, audio):
        text = self._transcriber.transcribe(audio)
        self._frame.after(0, lambda: self._status.configure(text="Evaluating..."))
        _, _, content = self._current
        result = self._improver.evaluate_answer(self._current_question, content, text)
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

        self._result_box.configure(state="normal")
        self._result_box.delete("1.0", "end")
        self._result_box.insert("1.0", result)
        self._result_box.configure(state="disabled")
        self._result_box.pack(pady=(0, 8))
        self._conf_frame.pack(anchor="w", pady=(0, 8))
        self._nav_row.pack(anchor="w")

        self._state = RESULT
        self._status.configure(text="")
        self._record_btn.configure(state="normal")

    def _on_next(self):
        self._result_box.pack_forget()
        self._conf_frame.pack_forget()
        self._nav_row.pack_forget()
        mode = self._sel_var.get()
        if mode == "Manual":
            self._current = pick_random_note(self._notes, subject=self._subject_var.get())
        elif mode == "Random":
            self._current = pick_random_note(self._notes)
        else:
            self._current = pick_by_confidence(self._notes, self._scores)
        self._generate_question()
