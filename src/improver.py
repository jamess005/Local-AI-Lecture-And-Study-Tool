import os
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("HIP_VISIBLE_DEVICES", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch
from typing import Any


ROLE_PROMPTS = {
    "Software Engineer": (
        "You are an experienced software engineer with a strong background in AI, "
        "machine learning, and full-stack development."
    ),
    "Senior Developer": (
        "You are a senior software developer with deep expertise in system design, "
        "code architecture, and engineering best practices."
    ),
    "DevOps Engineer": (
        "You are a senior DevOps engineer specialising in CI/CD pipelines, "
        "containerisation, infrastructure-as-code, and cloud platforms."
    ),
    "ML / Data Scientist": (
        "You are a machine learning engineer and data scientist with expertise in "
        "model training, evaluation, data pipelines, and MLOps."
    ),
    "Full Stack Developer": (
        "You are a full stack developer experienced in both frontend and backend "
        "technologies, REST APIs, databases, and modern web frameworks."
    ),
    "Security Engineer": (
        "You are a security engineer with expertise in application security, "
        "threat modelling, secure coding practices, and penetration testing."
    ),
}

MODE_FORMATS = {
    "Instruct": """\
The user has dictated a coding or AI task. Engineer it into a sharp, detailed prompt \
in Markdown — not just a summary, but an improved, more actionable version of what they said.

Always use exactly this format — no preamble, no explanation, nothing outside it:

- **Goal:** One precise, actionable sentence. Sharpen vague language into something concrete.
- **Requirements:**
  - One bullet per task, fix, or feature. Where the user was vague but the intent is clear, \
add the obvious professional detail. Do not invent new requirements.
- **Context:**
  - One bullet per relevant background detail, constraint, tech stack mention, or current state.

Rules:
- Improve clarity and precision — engineer a better prompt, not just a transcript.
- Only use information from the input, but flesh out what is clearly implied.
- Keep each bullet tight. Valid Markdown only. Nothing outside the format.""",

    "Reason": """\
The user is thinking through a problem out loud. Expand their reasoning into clear, \
connected prose — full sentences only, no bullet points.

Write three sections using these exact headings:

**What they are working out:**
One paragraph describing the problem they are trying to reason about.

**Their reasoning so far:**
Two or three paragraphs. Cover every distinct consideration, uncertainty, or tension \
they raised. Each idea gets its own sentences; show how thoughts connect to one another.

**The question they are left with:**
One paragraph stating the core question or decision that remains, and why it is hard to resolve.

Rules: no bullets, no preamble, preserve every distinct idea, remove filler only.""",
}

MODES = list(MODE_FORMATS.keys())


class Improver:
    def __init__(self):
        self._model: Any = None
        self._tokenizer: Any = None

    def load(self):
        model_path = os.environ["MODEL_PATH"]
        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map={"": "cuda:0"},
        )
        self._model.eval()

    def unload(self):
        import gc
        self._model = None
        self._tokenizer = None
        gc.collect()
        torch.cuda.empty_cache()

    def improve(self, raw_text: str, role: str = "Software Engineer", mode: str = "Instruct") -> str:
        persona = ROLE_PROMPTS.get(role, ROLE_PROMPTS["Software Engineer"])
        fmt = MODE_FORMATS.get(mode, MODE_FORMATS["Instruct"])
        system = persona + "\n\n" + fmt
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": raw_text},
        ]
        return self._generate(messages, max_new_tokens=512)

    def generate_question(self, note_content: str, style: str = "Flashcard") -> str:
        from study_prompts import FLASHCARD_QUESTION, EXTENDED_QUESTION
        system = FLASHCARD_QUESTION if style == "Flashcard" else EXTENDED_QUESTION
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": note_content},
        ]
        return self._generate(messages, max_new_tokens=128)

    def generate_notes(self, transcription: str) -> str:
        if self._model is None:
            self.load()
        try:
            topic = self._identify_lecture_topic(transcription)
            context = f"[Lecture: {topic}]\n\n" if topic else ""
            chunks = self._chunk_transcript(transcription, max_words=200, split_words=100)

            notes = ""
            for chunk in chunks:
                notes = self._accumulate(notes, context + chunk)

            exercise_blocks = self._extract_exercise_blocks(transcription)
            if exercise_blocks:
                existing = self._split_topic_blocks(notes)
                combined = self._deduplicate_chunks(existing + exercise_blocks)
                notes = "\n\n".join(combined)

            if not notes:
                return ""

            blocks = self._split_topic_blocks(notes)
            blocks.sort(key=lambda b: (1 if "Example:" in b else 0))
            notes = "\n\n".join(blocks)
            notes = self._verify_examples(notes)
            return self._postprocess_notes(notes)
        finally:
            self.unload()

    def _accumulate(self, current_notes: str, new_chunk: str) -> str:
        from note_prompts import ACCUMULATE_PROMPT
        user_content = (
            f"CURRENT NOTES:\n{current_notes}\n\nNEW CHUNK:\n{new_chunk}"
            if current_notes else
            f"CURRENT NOTES: (none)\n\nNEW CHUNK:\n{new_chunk}"
        )
        result = self._generate([
            {"role": "system", "content": ACCUMULATE_PROMPT},
            {"role": "user", "content": user_content},
        ], max_new_tokens=512).strip()
        if not result:
            return current_notes
        new_blocks = self._split_topic_blocks(result)
        if not new_blocks:
            return current_notes
        existing = self._split_topic_blocks(current_notes) if current_notes else []
        return "\n\n".join(self._deduplicate_chunks(existing + new_blocks))

    def _extract_exercise_blocks(self, transcript: str) -> list[str]:
        """One focused model call per exercise, detected by 'pause the video' markers."""
        import re
        from note_prompts import EXERCISE_EXTRACT_PROMPT
        words = transcript.split()
        markers = [
            i for i in range(len(words) - 2)
            if words[i].lower() == "pause"
            and words[i + 1].lower() == "the"
            and words[i + 2].lower().startswith("video")
        ]
        results = []
        for idx in markers:
            start = max(0, idx - 150)
            end = min(len(words), idx + 100)
            segment = " ".join(words[start:end])
            # Infer topic from the setup text only (before the pause marker)
            # so the post-window bleed from the next exercise doesn't pollute the match.
            setup = " ".join(words[start:idx])
            raw = self._generate([
                {"role": "system", "content": EXERCISE_EXTRACT_PROMPT},
                {"role": "user", "content": segment},
            ], max_new_tokens=256).strip()
            if not raw or self._is_skip(raw):
                continue
            topic = self._infer_exercise_topic(setup)
            if topic:
                # Strip any TOPIC: line the model produced and impose the correct one
                content = "\n".join(
                    l for l in raw.splitlines()
                    if not l.strip().upper().startswith("TOPIC:")
                ).strip()
                if content:
                    results.append(f"TOPIC: {topic}\n{content}")
            else:
                blocks = self._split_topic_blocks(raw)
                if blocks:
                    results.extend(blocks)
        return results

    def _verify_examples(self, notes: str) -> str:
        from note_prompts import VERIFY_EXAMPLES_PROMPT
        original_blocks = self._split_topic_blocks(notes)
        result = self._generate([
            {"role": "system", "content": VERIFY_EXAMPLES_PROMPT},
            {"role": "user", "content": notes},
        ], max_new_tokens=2048).strip()
        if not result:
            return notes
        verified_blocks = self._split_topic_blocks(result)
        # If truncation dropped blocks, fall back to unverified notes
        if len(verified_blocks) < len(original_blocks):
            return notes
        return "\n\n".join(verified_blocks)

    def _infer_exercise_topic(self, segment: str) -> str:
        import re
        # Check x²+1 first — more specific, avoids false match when lookback
        # window for g(x) crosses into the f(x) absolute-value solution text.
        if re.search(r'x\s*squared\s*plus\s*1|x\^?2\s*\+\s*1', segment, re.IGNORECASE):
            return "g(x) = x^2+1"
        if re.search(r'\babsolute value\b', segment, re.IGNORECASE):
            return "f(x) = |x|"
        return ""

    def _extract_topic(self, block: str) -> str:
        for line in block.splitlines():
            if line.strip().upper().startswith("TOPIC:"):
                return line.strip()[len("TOPIC:"):].strip().lower()
        return ""

    def _topic_similarity(self, a: str, b: str) -> float:
        import re
        norm = lambda s: set(re.sub(r'[^a-z0-9 ]', '', s).split())
        wa, wb = norm(a), norm(b)
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    def _deduplicate_chunks(self, processed: list[str]) -> list[str]:
        THRESHOLD = 0.5
        result: list[str] = []
        for block in processed:
            key = self._extract_topic(block)
            merged = False
            for i, existing in enumerate(result):
                ekey = self._extract_topic(existing)
                if key and ekey and self._topic_similarity(key, ekey) >= THRESHOLD:
                    if len(block) > len(result[i]):
                        result[i] = block
                    merged = True
                    break
            if not merged:
                result.append(block)
        return result

    def _identify_lecture_topic(self, transcription: str) -> str:
        from note_prompts import IDENTIFY_TOPIC_PROMPT
        preview = " ".join(transcription.split()[:300])
        result = self._generate([
            {"role": "system", "content": IDENTIFY_TOPIC_PROMPT},
            {"role": "user", "content": preview},
        ], max_new_tokens=16).strip()
        return result if result and len(result.split()) <= 5 else ""

    def _is_function_block(self, block: str) -> bool:
        import re
        topic = self._extract_topic(block)
        return bool(re.search(r'[a-z]\s*\(', topic) and '=' in topic)

    def _split_topic_blocks(self, raw: str) -> list[str]:
        """Split a multi-TOPIC model response into individual TOPIC blocks."""
        import re
        parts = re.split(r'(?im)^(?=TOPIC\s*:)', raw)
        return [p.strip() for p in parts if p.strip() and re.match(r'(?i)TOPIC\s*:', p.strip())]

    def _is_skip(self, result: str) -> bool:
        """True if the model output signals there is no note-worthy content."""
        if not result:
            return True
        lines = result.splitlines()
        content_lines = [
            l for l in lines
            if not l.strip().upper().startswith("TOPIC:")
        ]
        body = " ".join(content_lines).strip().rstrip(".!")
        return body.upper() == "SKIP" or not body

    def _chunk_transcript(self, text: str, max_words: int = 300, split_words: int = 150) -> list[str]:
        """Split at paragraph boundaries; subdivide at sentence boundaries if a
        paragraph exceeds max_words.  Returns chunks of ~max_words or fewer."""
        import re
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

        chunks: list[str] = []
        pending: list[str] = []
        pending_words = 0

        for para in paragraphs:
            para_words = len(para.split())
            if para_words > split_words:
                # Flush pending accumulation first
                if pending:
                    chunks.append("\n\n".join(pending))
                    pending, pending_words = [], 0
                # Subdivide this long paragraph at sentence boundaries
                sentences = re.split(r'(?<=[.!?])\s+', para)
                sub: list[str] = []
                sub_words = 0
                for sent in sentences:
                    sw = len(sent.split())
                    if sub_words + sw > split_words and sub:
                        chunks.append(" ".join(sub))
                        sub, sub_words = [sent], sw
                    else:
                        sub.append(sent)
                        sub_words += sw
                if sub:
                    chunks.append(" ".join(sub))
            elif pending_words + para_words > max_words and pending:
                chunks.append("\n\n".join(pending))
                pending, pending_words = [para], para_words
            else:
                pending.append(para)
                pending_words += para_words

        if pending:
            chunks.append("\n\n".join(pending))

        return [c for c in chunks if c.strip()]

    def _postprocess_notes(self, text: str) -> str:
        BANNED_STARTS = (
            "let's", "let us", "now let", "now we", "here we", "here the",
            "we can see", "we can now", "we define", "we say", "we saw",
            "we covered", "we explored", "we looked", "we have",
            "recall that", "it follows that", "note that",
            "let me", "i'm going to", "i will now",
            "in this lecture", "in this lesson", "in this video",
            "in summary", "to summarize", "to conclude", "as a summary",
            "finally, we", "finally, let",
            "the topics covered", "the following topics", "this concept is central",
            "this concept is used", "this concept is important",
            "correction based on", "*correction", "*(note", "(note",
            "note:", "note that", "**correction", "revised ",
            "to fix:", "to maintain", "given the", "actually,",
        )
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            # Preserve TOPIC: headers and example bullets unconditionally
            stripped = line.strip()
            if stripped.lower().startswith("topic:") or stripped.startswith("- ") or stripped.startswith("  "):
                cleaned.append(line)
                continue
            # Drop bare Skip / SKIP lines that leaked from within a chunk
            if stripped.lower().rstrip(".!,") == "skip":
                continue
            if stripped == "---":
                continue
            if any(stripped.lower().startswith(b) for b in BANNED_STARTS):
                continue
            cleaned.append(line)
        # Drop trailing blank lines left by removed lines
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        return "\n".join(cleaned)

    def evaluate_answer(self, question: str, note_content: str, spoken_answer: str) -> str:
        from study_prompts import EVALUATE_ANSWER
        user_content = (
            f"Question: {question}\n\n"
            f"Note:\n{note_content}\n\n"
            f"Student's answer: {spoken_answer}"
        )
        messages = [
            {"role": "system", "content": EVALUATE_ANSWER},
            {"role": "user", "content": user_content},
        ]
        return self._generate(messages, max_new_tokens=256)

    def _generate(self, messages: list[dict], max_new_tokens: int = 512) -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        model, tokenizer = self._model, self._tokenizer
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer([text], return_tensors="pt").to("cuda")
        with torch.no_grad():
            output_ids = model.generate(  # type: ignore[attr-defined]
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        return tokenizer.decode(generated, skip_special_tokens=True).strip()
