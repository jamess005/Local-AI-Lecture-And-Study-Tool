SINGLE_PASS_PROMPT = """\
Read the lecture transcript. For every mathematical concept that is explicitly introduced \
or formally defined, write one TOPIC block.

=== OUTPUT FORMAT ===
TOPIC: <concept name — use the lecturer's own words>
<2–5 sentences. Define the concept and include any domain, range, asymptote, or key properties \
the lecturer explicitly states for it. Do not generalise beyond what the transcript says. \
Concept name as grammatical subject.>
Laws:
- <algebraic law in LaTeX/Unicode notation>
Example:
- <concrete step or value from the transcript>

=== INSTRUCTIONS ===
- Omit the Laws section entirely if the lecturer lists no explicit laws for this concept.
- Omit the Example section entirely if the transcript provides no concrete numeric values.
- Do NOT extract domain/range descriptions ("all real numbers", "real positive numbers"), \
specific shared points ("(0,1)"), or closing summaries — only formally defined concepts.
- When the transcript illustrates what makes something fail to be a concept \
(a counter-example or "what this is not"), fold the stated conditions into \
that concept's definition sentences — do not create a separate TOPIC block \
for the counter-example.
- Laws must be general algebraic identities or formal rules the lecturer explicitly states \
in the transcript. Do NOT add laws from your own knowledge. If a function appears only as \
an exercise example, do not generate laws for it beyond what the transcript states. \
A law must use variables, not specific numbers — if it contains specific numbers \
(e.g. f(-1) = 1), it is an Example bullet, not a law. \
The function's own definition formula (e.g. g(x) = x² + 1) is not a law — \
it describes the function and belongs in the definition sentence, not in Laws. \
If the lecturer explicitly states that a property does NOT hold for this concept \
(e.g. "F ∘ G is not commutative"), include it as a law bullet using ≠ notation \
(e.g. F ∘ G ≠ G ∘ F in general).
- If the lecturer explicitly states a geometric or graphical property of this concept — \
even during a graph-plotting section — include it as a law bullet written as a formal statement. \
Examples: "the graphs of f and f⁻¹ are always symmetric with respect to the line y = x"; \
"the logarithmic function and exponential function are symmetric with respect to y = x". \
Write the law in the block for the concept whose properties are being described at that point. \
A graph symmetry between a function and its inverse is a law of the inverse function block.
- Write each law in LaTeX/Unicode notation (e.g. b^x · b^y = b^(x+y), log_b(1) = 0, log_b(b) = 1).
- For Examples: use only numeric values from the transcript. Write expressions in notation, not words.
- Do not extract exercise results as standalone TOPIC blocks — include them as Example bullets \
within the concept block they belong to. If the transcript introduces a concept via an exercise \
("pause the video", "try to answer"), the solution walkthrough that follows provides the \
concrete numeric values for that concept's Example section — include them, do not skip them.
- If the transcript distinguishes named variants as separate cases \
(e.g. Increasing Linear Function vs Decreasing Linear Function, \
Exponential Growth vs Exponential Decay), extract each variant as its own TOPIC block.
- When a technique or proof method explicitly names its steps or components \
(e.g. "this is called the basis", "this step is called the inductive step", \
"this assumption is called the inductive hypothesis"), extract each named component \
as its own TOPIC block using the lecturer's exact name as the TOPIC header.
- $\\mathbb{Z}$ integers, $\\mathbb{R}$ reals. $D_f$ domain, $R_f$ range.
- LaTeX only for backslash commands and subscripts. Unicode: ∈ ∉ ∅ ≤ ≥ → ↔.
- TOPIC: must be the first characters of your response. No preamble. \
Never output a section labelled Rules, Instructions, or Format."""

SINGLE_NOTE_PROMPT = """\
Read the lecture transcript. For every concept, technology, or system \
the lecturer names, write one bullet in a single TOPIC block.

=== OUTPUT FORMAT ===
TOPIC: <subject — the lecturer's own words>
- <name>: <what the transcript says it is, does, or how it differs — 1–2 sentences>
- <name>: <definition>

=== INSTRUCTIONS ===
- Output exactly ONE TOPIC block.
- A bullet qualifies if the lecturer (a) gives it a distinct name AND \
(b) says anything about it — its purpose, role, relationship to other items, or how it's used.
- List qualifying items in the order they first appear in the transcript.
- One bullet per distinct name. If the same name appears more than once in the transcript, \
write one bullet combining all descriptions — never two bullets for the same name.
- Proper nouns used only as locations, companies, or analogies are not concepts — omit them.
- If the lecturer explicitly says they will not cover something, omit it.
- Use only information stated in the transcript. Do not add outside knowledge.
- TOPIC: must be the first characters of your response. No preamble."""

IDENTIFY_TOPIC_PROMPT = """\
Read the start of this lecture transcript and output the subject being taught. \
Three words maximum. Output only the subject name, nothing else. \
Examples: "Functions", "Proof by Contradiction", "Binary Trees"."""

EXTRACT_CONCEPTS_PROMPT = """\
You are reading a lecture transcript chunk.
List every mathematical concept introduced or defined for the first time in this chunk.

Rules:
- Output ONLY a comma-separated list of short noun phrases (2-5 words each), one per concept.
- Use the lecturer's own terminology exactly as it appears.
- Do NOT include any concept that appears in the KNOWN list.
- Dense paragraphs often introduce several concepts — list ALL of them, never collapse two into one.
- When a section contrasts two sub-cases, extract both as separate entries: \
Exponential Growth and Exponential Decay are two entries; \
Increasing Linear Function and Decreasing Linear Function are two entries.
- Do NOT extract specific numeric constants, named points (e.g. "(0,1)"), base values, \
asymptote equations, or gradient signs as standalone concepts — \
these are properties of a larger concept, not concepts in their own right.
- Do NOT extract the name of a mathematical notation element (such as "base", "exponent", \
"gradient", "coefficient", "slope") as a standalone concept unless the lecturer gives it \
a formal definition entirely separate from its parent function type.
- Do NOT extract specific value sets or range descriptions \
(such as "real positive numbers", "all real numbers", "non-negative integers") \
as standalone concepts — these are properties of functions.
- Do NOT extract a property of a concept that is already in the KNOWN list as a new concept.
- If no new concepts are introduced (summary, logistics, greetings, exercise solution): output nothing.
- No definitions, examples, or explanations. Concept names only."""

GENERATE_TOPIC_PROMPT = """\
Write a single TOPIC block for the named concept. Use ONLY the CHUNK below — no other source.

=== OUTPUT FORMAT (standard concept) ===
TOPIC: <concept name — copy exactly from CONCEPT: line>
<2-4 sentences. Concept name as grammatical subject. General definition only. \
No specific example values in the definition.>
Example:
- <step>
- <conclusion>

=== OUTPUT FORMAT (laws / enumerated properties) ===
TOPIC: <concept name>
<One sentence stating what these laws govern.>
Laws:
- <law 1, as a mathematical statement>
- <law 2>
(continue for ALL laws present in the CHUNK — never truncate)
Example:
- <one concrete numerical application from the CHUNK>

=== RULES ===
- ONLY use specific values (numbers, expressions) verbatim from the CHUNK. Never from training knowledge.
- If the CHUNK contains no concrete example values, omit the Example section entirely.
- Only use the Laws: format when the CHUNK explicitly contains a numbered or bulleted list of \
mathematical laws, identities, or algebraic properties. \
Do not create a Laws: section from prose descriptions — if there is no enumerated list in the CHUNK, \
use the standard concept format instead. \
A law must be a general algebraic statement or identity (e.g. b^x · b^y = b^(x+y)). \
Specific numeric function instances (e.g. f(x) = (1/2)x²) are examples, not laws — \
put them in the Example section, not the Laws section. \
Copy each law as a mathematical statement exactly as it appears in the CHUNK — \
do not rephrase, reconstruct from memory, or alter the notation.
- Do not write meta-commentary about the source text. \
Do not say "the text mentions", "the chunk describes", "the transcript does not provide", etc. \
Write the definition directly from what you know about the concept. \
If the CHUNK provides no example values, simply omit the Example section.
- Say "Linear Function is a function of the form..." — NOT "The linear function f(x) = 3x+2 is...".
- Never write "Definition of X" — just "X".
- $\\mathbb{Z}$ integers, $\\mathbb{R}$ reals. $D_f$ domain, $R_f$ range, co-$D_f$ co-domain.
- LaTeX only for backslash commands and subscripts. Unicode: ∈ ∉ ∅ ≤ ≥ → ↔.
- No preamble. TOPIC: must be the first characters."""

VERIFY_EXAMPLES_PROMPT = """\
You are reviewing student lecture notes for mathematical correctness. \
The notes below are in TOPIC: block format. Each block may contain a Laws: section and/or an Example section.

For each Laws: section:
- Check that each law is a valid, general algebraic identity or mathematical statement.
- If both sides of a law are identical or trivially equal (e.g. "a · b^x = ab^x" or \
  "a/b^x = a/b^x"), the law is mis-stated — correct it to the proper algebraic identity.
- Correct any algebraically incorrect law to its mathematically valid form. \
  Example: "a · b^x = a^x · b^x" is wrong — correct it to "(a·b)^x = a^x · b^x". \
  Example: "a · b^x = ab^x" is trivially true — replace with "(a·b)^x = a^x · b^x". \
  Example: "a / b^x = a^x / b^x" is wrong — correct it to "(a/b)^x = a^x / b^x". \
  Example: "a/b^x = a/b^x" is trivially true — replace with "(a/b)^x = a^x / b^x". \
  Example: "a/b^x = a·b^(-x)" is trivially true — replace with "(a/b)^x = a^x / b^x". \
  Example: "$\\frac{a}{b^x} = a \\cdot b^{-x}$" is trivially true — replace with "$(a/b)^x = \\frac{a^x}{b^x}$".
- Remove any bullet that is a function definition or specific instance rather than a general law. \
  A function definition of the form f(x) = expression (e.g. "f(x) = (1/2)x²", "g(x) = x²+1") \
  belongs in the definition sentence, not in Laws. \
  A general law uses symbolic variables without naming a specific function \
  (e.g. b^x · b^y = b^(x+y)).

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
- Do not remove TOPIC blocks or Example sections. If removing invalid law bullets leaves a \
Laws: section with no remaining bullets, remove the Laws: header too.

CRITICAL OUTPUT RULES:
- Output ONLY the corrected TOPIC: blocks. Nothing else.
- No explanations, notes, parenthetical comments, asterisks, or correction logs.
- No lines starting with *, (, Note:, Correction:, or any commentary.
- Every line must be either a TOPIC: header, a definition sentence, a Laws: header, \
  a law bullet, an Example: header, or an Example bullet.
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
- TOPIC must be the function expression (e.g. f(x) = |x|).
- Simplify all numeric results — write 2 and -2, not √4 and -√4.
- Include only specific function evaluations (e.g. f(-1) = 1) and pre-image sets \
  (e.g. pre-images of 1 = {-1, 1}). Do NOT include domain, co-domain, or range \
  statements — these belong in the concept definition, not the Example.
- $\\mathbb{Z}$ integers, $\\mathbb{R}$ reals. $D_f$ domain, $R_f$ range.
- LaTeX only for backslash commands and subscripts. Unicode: ∈ ∉ ∅ ≤ ≥.
- No preamble. TOPIC: must be the first characters."""





