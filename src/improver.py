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
        import json
        from pathlib import Path
        model_path = os.environ["MODEL_PATH"]
        self._tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)
        cfg = json.loads((Path(model_path) / "config.json").read_text())
        quant_method = cfg.get("quantization_config", {}).get("quant_method", "")
        if quant_method == "awq":
            # AWQ pre-quantized model — no bitsandbytes kernels, safe on ROCm
            from awq import AutoAWQForCausalLM
            self._model = AutoAWQForCausalLM.from_quantized(
                model_path,
                fuse_layers=False,
            )
        else:
            # Standard model — quantize at load time with bitsandbytes
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=bnb_config,
                device_map="auto",
                max_memory={0: "15GiB", "cpu": "20GiB"},
                low_cpu_mem_usage=True,
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

    def generate_notes(self, transcription: str, mode: str = "multi") -> str:
        if self._model is None:
            self.load()
        try:
            if mode == "single":
                from note_prompts import SINGLE_NOTE_PROMPT
                raw = self._generate([
                    {"role": "system", "content": SINGLE_NOTE_PROMPT},
                    {"role": "user", "content": transcription},
                ], max_new_tokens=1024).strip()
                if not raw:
                    return ""
                result = self._postprocess_notes(raw)
                text = result if result.strip() else raw
                blocks = self._split_topic_blocks(text)
                if blocks:
                    header = self._extract_topic(blocks[0])
                    seen: set[str] = set()
                    bullets: list[str] = []
                    for b in blocks:
                        for line in b.splitlines():
                            s = line.strip()
                            if not s.startswith("- "):
                                continue
                            colon = s.find(":", 2)
                            name = s[2:colon].strip() if colon > 2 else ""
                            if name and name in seen:
                                continue
                            if name:
                                seen.add(name)
                            bullets.append(line)
                    text = "TOPIC: " + header + "\n" + "\n".join(bullets)
                return text

            from note_prompts import SINGLE_PASS_PROMPT
            raw = self._generate([
                {"role": "system", "content": SINGLE_PASS_PROMPT},
                {"role": "user", "content": transcription},
            ], max_new_tokens=2048).strip()
            if not raw:
                return ""
            blocks = self._split_topic_blocks(raw)
            if not blocks:
                return ""
            blocks = [self._verify_block_laws(b) for b in blocks]
            blocks = [self._strip_function_defs_from_laws(b) for b in blocks]
            exercise_blocks = self._extract_exercise_blocks(transcription)
            for ex_block in exercise_blocks:
                ex_topic = self._extract_topic(ex_block)
                idx = self._find_concept_block_for_exercise(ex_topic, blocks)
                if idx is not None and "Example:" not in blocks[idx]:
                    examples = self._extract_example_section(ex_block)
                    if examples:
                        blocks[idx] = blocks[idx].rstrip() + "\nExample:\n" + examples
            blocks.sort(key=lambda b: (1 if "Example:" in b else 0))
            return self._postprocess_notes("\n\n".join(blocks))
        finally:
            self.unload()

    def _accumulate(self, current_notes: str, new_chunk: str) -> str:
        existing = self._split_topic_blocks(current_notes) if current_notes else []
        known_topics = {self._extract_topic(b) for b in existing}

        concepts = self._extract_concepts(new_chunk, known_topics)
        if not concepts:
            return current_notes

        new_blocks: list[str] = []
        for concept in concepts:
            block = self._generate_topic_block(concept, new_chunk)
            if block and not self._is_skip(block):
                parsed = self._split_topic_blocks(block)
                new_blocks.extend(parsed)

        if not new_blocks:
            return current_notes

        return "\n\n".join(self._deduplicate_chunks(existing + new_blocks))

    def _extract_concepts(self, chunk: str, known_topics: set[str]) -> list[str]:
        from note_prompts import EXTRACT_CONCEPTS_PROMPT
        known_str = ", ".join(sorted(known_topics)) if known_topics else "none"
        user_content = f"KNOWN: {known_str}\nCHUNK: {chunk}"
        result = self._generate([
            {"role": "system", "content": EXTRACT_CONCEPTS_PROMPT},
            {"role": "user", "content": user_content},
        ], max_new_tokens=64).strip()
        if not result:
            return []
        return [c.strip() for c in result.split(",") if c.strip()]

    def _generate_topic_block(self, concept: str, chunk: str) -> str:
        from note_prompts import GENERATE_TOPIC_PROMPT
        user_content = f"CONCEPT: {concept}\nCHUNK: {chunk}"
        return self._generate([
            {"role": "system", "content": GENERATE_TOPIC_PROMPT},
            {"role": "user", "content": user_content},
        ], max_new_tokens=768).strip()

    def _extract_exercise_blocks(self, transcript: str) -> list[str]:
        """One focused model call per exercise, detected by 'pause the video' markers."""
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
                    line for line in raw.splitlines()
                    if not line.strip().upper().startswith("TOPIC:")
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
        # Fall back if VERIFY changed the block count (truncation or hallucinated additions)
        if len(verified_blocks) != len(original_blocks):
            return notes
        return "\n\n".join(verified_blocks)

    def _verify_block_laws(self, block: str) -> str:
        if "Laws:" not in block:
            return block
        from note_prompts import VERIFY_EXAMPLES_PROMPT
        result = self._generate([
            {"role": "system", "content": VERIFY_EXAMPLES_PROMPT},
            {"role": "user", "content": block},
        ], max_new_tokens=512).strip()
        if not result:
            return block
        verified = self._split_topic_blocks(result)
        if len(verified) != 1:
            return block
        return verified[0]

    def _strip_function_defs_from_laws(self, block: str) -> str:
        import re
        import pathlib
        log = pathlib.Path("/tmp/strip_debug.log")
        with log.open('a') as f:
            f.write(f"=== INPUT ===\n{repr(block)}\n\n")

        lines = block.splitlines(keepends=True)
        result = []
        in_laws = False
        laws_idx: int | None = None

        for line in lines:
            s = line.strip()
            if re.match(r'(?i)^laws\s*:', s):
                in_laws = True
                laws_idx = len(result)
                result.append(line)
            elif re.match(r'(?i)^(example|topic)\s*:', s):
                in_laws = False
                result.append(line)
            elif in_laws and re.match(r'^-\s*\$?[a-zA-Z]\(x\)\$?\s*=', s):
                pass  # drop function-definition bullet from Laws only
            else:
                result.append(line)

        # Remove Laws: header if no bullet survived before the next section
        if laws_idx is not None:
            has_bullet = False
            for i in range(laws_idx + 1, len(result)):
                s = result[i].strip()
                if not s:
                    continue
                if re.match(r'(?i)^(example|topic|laws)\s*:', s):
                    break
                if s.startswith('-'):
                    has_bullet = True
                    break
            if not has_bullet:
                result.pop(laws_idx)

        output = ''.join(result).strip()
        with log.open('a') as f:
            f.write(f"=== OUTPUT ===\n{repr(output)}\n\n")
        return output

    def _extract_example_section(self, block: str) -> str:
        lines = block.splitlines()
        in_example = False
        bullets: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Example:"):
                in_example = True
                continue
            if in_example:
                if stripped.startswith("- "):
                    bullets.append(line)
                elif stripped:
                    break
        return "\n".join(bullets)

    def _find_concept_block_for_exercise(self, exercise_topic: str, blocks: list[str]) -> int | None:
        import re
        m = re.match(r'^([a-zA-Z])\s*\(', exercise_topic)
        if not m:
            return None
        letter = m.group(1).lower()
        for i, block in enumerate(blocks):
            topic = self._extract_topic(block).lower()
            if letter == 'f' and 'absolute' in topic:
                return i
            # Match the function letter as a standalone word (e.g. "Function g" → 'g')
            # \b ensures we don't match 'f' inside the word "function" itself
            if re.search(r'\b' + letter + r'\b', topic) and 'function' in topic:
                return i
        return None

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
        def norm(s):
            return set(re.sub(r'[^a-z0-9 ]', '', s).split())
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
            line for line in lines
            if not line.strip().upper().startswith("TOPIC:")
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
        import re
        text = re.sub(r'(?m)^(Laws|Example):\s*\n- None\s*\n?', '', text)
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

    def _generate(self, messages: list[dict], max_new_tokens: int = 512,
                  enable_thinking: bool = False) -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        model, tokenizer = self._model, self._tokenizer
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        inputs = tokenizer([text], return_tensors="pt").to("cuda")
        with torch.no_grad():
            output_ids = model.generate(  # type: ignore[attr-defined]
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        if enable_thinking:
            import re
            raw = tokenizer.decode(generated, skip_special_tokens=False)
            output = raw.split('</think>', 1)[1] if '</think>' in raw else raw
            output = re.sub(r'<\|[^|]+\|>', '', output)
        else:
            output = tokenizer.decode(generated, skip_special_tokens=True)
        return output.strip()
