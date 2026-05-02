import os
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("HIP_VISIBLE_DEVICES", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

MODEL_PATH = os.getenv("MODEL_PATH", "/home/james/ml-proj/models/llama-3.1-8b-instruct")

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
        self._model = None
        self._tokenizer = None

    def load(self):
        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        bnb_config = BitsAndBytesConfig(load_in_8bit=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            quantization_config=bnb_config,
            device_map={"": "cuda:0"},
        )
        self._model.eval()

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
        from note_prompts import GENERATE_NOTES
        messages = [
            {"role": "system", "content": GENERATE_NOTES},
            {"role": "user", "content": transcription},
        ]
        return self._generate(messages, max_new_tokens=2560)

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
        if self._model is None:
            raise RuntimeError("Model not loaded")
        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer([text], return_tensors="pt").to("cuda")
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated, skip_special_tokens=True).strip()
