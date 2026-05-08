IDENTIFY_TOPIC_PROMPT = """\
Read the start of this lecture transcript and output the subject being taught. \
Three words maximum. Output only the subject name, nothing else. \
Examples: "Functions", "Proof by Contradiction", "Binary Trees"."""

ACCUMULATE_PROMPT = """\
You are building lecture notes incrementally. \
The user message contains CURRENT NOTES (in TOPIC: block format) and a NEW CHUNK from the same lecture.

Examine the new chunk and decide:

1. If the chunk introduces one or more concepts not yet in the current notes → output one TOPIC block \
   per new concept. A single chunk may produce multiple blocks. Never collapse two distinct concepts \
   into one block.
2. If the chunk provides a clear illustrative example for a concept already in the notes \
   BUT that concept block has no Example section → output ONLY the updated block, \
   with the Example section added. Change nothing else in the block. \
   CRITICAL: the NEW CHUNK section is your only permitted source for example values. \
   Copy values EXACTLY as they appear word-for-word in the NEW CHUNK — same function, same numbers, \
   same notation. Values that appear only in the CURRENT NOTES section must not be used. \
   Do not substitute, paraphrase, or use values from training knowledge. \
   If the exact values are not present verbatim in the NEW CHUNK, write no Example section. \
   Use values from one example only — do not mix values from two different examples in the chunk \
   (e.g. do not use the co-domain from the 2x+1 example with the domain from the string example).
3. If the concept is already in the notes AND already has an Example section → output nothing for that concept. \
   Each TOPIC block may contain at most one Example section.
3b. If the chunk introduces a numbered or enumerated list of laws, identities, or properties for any \
   concept (whether or not it is already in the notes), output that concept's block in this exact format:
   TOPIC: <concept name>
   <One sentence stating what these laws govern.>
   Laws:
   - <law 1, as a mathematical statement>
   - <law 2>
   (continue for ALL laws — never truncate)
   Example:
   - <one concrete numerical application from the NEW CHUNK>
4. If the chunk is a standalone exercise (contains "pause the video", is a summary, \
   logistics, or greetings) → output nothing.

Do not combine two distinct concepts into one block.

=== TOPIC RULES ===
Domain, Co-domain, and Range are three separate topics — never combine them. \
Image and Pre-image are two separate topics — never combine them. \
Exponential Growth (b > 1) and Exponential Decay (b < 1) are two separate topics — never combine them. \
Increasing Linear Function and Decreasing Linear Function are two separate topics — never combine them. \
TOPIC names are short noun phrases that use the lecturer's own terminology — \
e.g. "Linear Function", "Exponential Decay", "Laws of Exponential Functions", "Domain". \
Never write "Definition of X" — just "X". \
Do not comment on source text quality or transcription errors. \
The TOPIC name must accurately reflect the mathematical content of the block — a property of \
quadratic functions cannot be named as a property of linear functions, and vice versa.

Write every definition sentence with the concept name as the grammatical subject. \
Say "Co-domain is the set of all possible outputs" — NOT "The co-domain of f is ℤ". \
Say "Pre-image of y is the set of all inputs that map to y" — NOT "The pre-images of 5 for g are...". \
Define the concept in general terms; never state specific example values as the definition.

=== OUTPUT FORMAT ===
TOPIC: <concept name>
<2-4 sentences. Start with concept name as subject. No teacher phrases. General definition only.>
Example:
- <step>
- <conclusion>

=== FORMATTING ===
$\\mathbb{Z}$ integers, $\\mathbb{R}$ reals. $D_f$ domain, $R_f$ range, co-$D_f$ co-domain.
LaTeX only for backslash commands and subscripts. Plain text: f(x), f: A → B. Unicode: ∈ ∉ ∅ ≤ ≥ → ↔.
No preamble. TOPIC: must be the first characters of every block. Output nothing if nothing is new."""

VERIFY_EXAMPLES_PROMPT = """\
You are reviewing student lecture notes for mathematical correctness. \
The notes below are in TOPIC: block format. Each block may contain an Example section.

For each Example section:
- Check that all values are internally consistent within the example \
  (e.g. if the co-domain is {1,2,3,4,5,6}, no output value can be 9 or 7).
- Check that the example actually illustrates the concept named in the TOPIC heading.
- Check that the TOPIC name accurately describes the mathematical content of the block. \
  If the definition and example describe quadratic behaviour but the TOPIC says "Linear", \
  correct the TOPIC name to match the content.
- If you find an error, correct only the specific wrong value or line.
- If an example mixes values from two different problems, remove the inconsistent values \
  or replace them with consistent ones derived from the example's own stated facts.
- Check cross-block consistency: if the same function appears in multiple blocks, \
  its values must agree across all of them. \
  For example, if the Image block states f(sea) = 3, \
  then the Pre-image block must not state that the pre-image of 1 is 'sea'.
- Do not add new content, new examples, or new TOPIC blocks.
- Do not remove TOPIC blocks or Example sections — only correct errors within them.

CRITICAL OUTPUT RULES:
- Output ONLY the corrected TOPIC: blocks. Nothing else.
- No explanations, notes, parenthetical comments, asterisks, or correction logs.
- No lines starting with *, (, Note:, Correction:, or any commentary.
- Every line must be either a TOPIC: header, a definition sentence, or an Example bullet.
- Return ALL input TOPIC blocks, in order, even if unchanged."""

EXERCISE_EXTRACT_PROMPT = """\
The text below contains a worked exercise from a lecture. \
Ignore any introductory preamble ("now I'm going to ask you to attempt...", \
"pause the video", "in this lecture") and extract only the exercise itself.

TOPIC: <function expression, e.g. f(x) = |x|, g(x) = x^2+1>
Example: <restate the problem — function, domain, what to find>
- <step or finding>
- <conclusion>

Rules:
- TOPIC must be the function expression. For absolute value: f(x) = |x|. \
  For squaring: g(x) = x^2+1.
- Simplify all numeric results — write 2 and -2, not √4 and -√4.
- $\\mathbb{Z}$ integers, $\\mathbb{R}$ reals. $D_f$ domain, $R_f$ range.
- LaTeX only for backslash commands and subscripts. Unicode: ∈ ∉ ∅ ≤ ≥.
- No preamble. TOPIC: must be the first characters."""





