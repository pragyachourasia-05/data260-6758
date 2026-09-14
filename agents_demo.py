import argparse, json, os, re, sys, time
from dataclasses import dataclass
from typing import List, Dict, Any, Iterable, Tuple

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# Common low-signal words to drop before ranking tag candidates.
STOP = {
    "the", "and", "for", "that", "with", "this", "from", "into", "than", "your", "you",
    "are", "was", "were", "have", "has", "had", "use", "used", "using", "about", "how",
    "can", "will", "more", "less", "very", "over", "under", "their", "there", "then",
    "our", "out", "on", "in", "of", "to", "by", "a", "an", "is", "it", "as",
}


# -------------------------
# Text cleanup + extraction
# -------------------------

def strip_code_and_md(s: str) -> str:
    """
    Strips fenced code blocks and inline backticks a local model
    sometimes adds despite instructions not to, drops a few markdown
    emphasis characters, and collapses runs of whitespace into single
    spaces so the result reads as plain prose.
    """
    text = str(s)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # fenced blocks first
    text = re.sub(r"`([^`]*)`", r"\1", text)                  # then inline backticks
    text = re.sub(r"[*_#>]+", " ", text)                      # stray markdown emphasis
    return " ".join(text.split())


def extract_json_block(text: str) -> str:
    """
    Walks the raw reply looking for the first balanced {...} span and
    verifies it actually parses as JSON before returning it. Local
    models occasionally wrap valid JSON in a sentence or two of prose
    even when told not to, so a naive json.loads(text) would fail.
    If nothing valid is found, the cleaned text is wrapped as
    {"message": "<cleaned text>"} so downstream code always gets JSON.
    """
    raw = str(text)
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        break  # not valid JSON after all; fall through
    return json.dumps({"message": strip_code_and_md(raw)})


def tokens(txt: str) -> List[str]:
    """
    Lowercases the text and pulls out word-like tokens (letters plus
    internal hyphens), dropping stopwords and anything under 3
    characters so single letters/junk don't pollute tag candidates.
    """
    words = re.findall(r"[a-z][a-z\-]+", str(txt).lower())
    return [w for w in words if w not in STOP and len(w) > 2]


def ngrams(words: List[str], n: int) -> Iterable[Tuple[str, ...]]:
    """Yields every contiguous n-word window from a token list."""
    for i in range(len(words) - n + 1):
        yield tuple(words[i:i + n])


def phrase_candidates(title: str, content: str, maxn: int = 12) -> List[str]:
    """
    Ranks tag candidates derived only from title + content:
      1. tokenize both fields together
      2. count trigram and bigram frequency across the combined text
      3. rank longer, more frequent phrases first
      4. top up with the most common single words if still short of maxn
    Returns up to maxn candidate phrases, most promising first.
    """
    words = tokens(f"{title} {content}")
    if not words:
        return []

    phrase_counts: Dict[str, int] = {}
    for n in (3, 2):
        for gram in ngrams(words, n):
            phrase = " ".join(gram)
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    ranked = sorted(phrase_counts.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    candidates = [phrase for phrase, _ in ranked]

    if len(candidates) < maxn:
        seen = set(candidates)
        unigram_counts: Dict[str, int] = {}
        for w in words:
            unigram_counts[w] = unigram_counts.get(w, 0) + 1
        for word, _ in sorted(unigram_counts.items(), key=lambda kv: -kv[1]):
            if word not in seen:
                candidates.append(word)
                seen.add(word)
            if len(candidates) >= maxn:
                break

    return candidates[:maxn]


# -------------------------
# Output schema coercion
# -------------------------

def coerce_reply(raw_obj: Any, title: str, content: str, strict: bool) -> Dict[str, Any]:
    """
    Normalizes whatever the model produced into the required schema:
      {
        "thought": str,
        "message": str (non-empty, <= 60 words),
        "data": {
          "tags": [str, str, str],
          "summary": str (<= 25 words, ends with '.'),
          "issues": [str, ...]
        }
      }
    Anything missing or malformed is backfilled from phrase_candidates()
    or the raw content instead of left blank, so a weak or truncated
    model reply still produces a valid, usable result.
    """
    obj = raw_obj if isinstance(raw_obj, dict) else {}
    data_in = obj.get("data") if isinstance(obj.get("data"), dict) else {}

    candidates = phrase_candidates(title, content)

    tags_in = data_in.get("tags")
    if isinstance(tags_in, list) and all(isinstance(t, str) and t.strip() for t in tags_in):
        tags = [t.strip() for t in tags_in][:3]
    else:
        tags = []

    for phrase in candidates:
        if len(tags) >= 3:
            break
        if phrase not in tags:
            tags.append(phrase)
    while len(tags) < 3:
        tags.append(f"topic-{len(tags) + 1}")

    if strict:
        # Prefer at least two multi-word tags where candidates allow it.
        multiword = sum(1 for t in tags if " " in t)
        for phrase in candidates:
            if multiword >= 2:
                break
            if " " in phrase and phrase not in tags:
                for i, t in enumerate(tags):
                    if " " not in t:
                        tags[i] = phrase
                        break
                multiword = sum(1 for t in tags if " " in t)

    summary = data_in.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = " ".join(strip_code_and_md(content).split()[:25])
    summary = summary.strip()
    summary_words = summary.split()
    if len(summary_words) > 25:
        summary = " ".join(summary_words[:25])
    if not summary.endswith("."):
        summary = summary.rstrip(".") + "."

    issues = data_in.get("issues")
    issues = issues if isinstance(issues, list) else []

    message = obj.get("message")
    if not isinstance(message, str) or not message.strip():
        message = "Reviewed the listing details and prepared tags and a summary."
    message_words = message.split()
    if len(message_words) > 60:
        message = " ".join(message_words[:60])

    thought = obj.get("thought") if isinstance(obj.get("thought"), str) else ""

    return {
        "thought": thought,
        "message": message,
        "data": {
            "tags": tags[:3],
            "summary": summary,
            "issues": issues,
        },
    }


def parse_and_coerce(text: str, title: str, content: str, strict: bool) -> Dict[str, Any]:
    """
    Pulls a JSON object out of the raw model reply, parses it, and
    normalizes it into the required schema. Any failure along the way
    (bad JSON, missing fields) degrades gracefully into coerce_reply()'s
    fallback behavior rather than raising.
    """
    block = extract_json_block(text)
    try:
        obj = json.loads(block)
    except Exception:
        obj = {"message": strip_code_and_md(text)}
    return coerce_reply(obj, title, content, strict)


# -------------------------
# Agent wrapper
# -------------------------

@dataclass
class SimpleAgent:
    name: str
    system: str
    model: Any  # LangChain ChatModel

    def respond(
        self,
        conversation: List[Dict[str, str]],
        task: str,
        title: str,
        content: str,
        strict: bool,
    ) -> Dict[str, Any]:
        """
        Builds a prompt from this agent's system role + the shared task
        and running transcript, runs it through the model, and coerces
        the raw reply into the required schema before returning it.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system),
            ("human",
             "Task:\n{task}\n\nConversation so far:\n{history}\n\n"
             "Return ONLY one JSON object (no code fences, no markdown, no explanations). "
             "Keys: thought (string), message (non-empty, <=60 words, no code), "
             "data.tags (array of exactly 3 topical tags), "
             "data.summary (<=25 words, no ellipses), data.issues (array).\n"
             "Do not add extra text outside JSON."
            ),
        ])

        history_text = "\n".join([f'{m["role"]}: {m["content"]}' for m in conversation]) or "(empty)"
        chain = prompt | self.model | StrOutputParser()

        raw = chain.invoke({"task": task, "history": history_text})
        return parse_and_coerce(raw, title, content, strict)


# -------------------------
# CLI entrypoint
# -------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="1400 Sq Ft 2BR Apartment Near Downtown San Jose")
    ap.add_argument("--content", default=(
        "Bright 2 bedroom, 1 bath apartment on the second floor, updated kitchen "
        "with new appliances, in-unit laundry, one covered parking spot, small "
        "balcony, walking distance to light rail. No smoking. Cats allowed with "
        "deposit."
    ))
    ap.add_argument("--email", default="pragya.chourasia@sjsu.edu")
    ap.add_argument("--model", default=os.environ.get("SMOL_MODEL", "qwen3:8b"))
    ap.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--turns", type=int, default=1)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        llm = ChatOllama(
            model=args.model,
            temperature=float(os.environ.get("OLLAMA_TEMPERATURE", "0.0")),
            base_url=args.base_url,
            num_ctx=2048,
            format="json",
        )
    except Exception:
        print(
            "Failed to initialize ChatOllama. Is Ollama running and the model available?\n"
            "Try: `ollama serve` and `ollama pull <your-model-tag>`.",
            file=sys.stderr,
        )
        raise

    planner = SimpleAgent(
        name="Planner",
        system="Propose exactly 3 distinct, topical tags (prefer multi-word phrases) and a one-line summary for the rental listing.",
        model=llm,
    )
    reviewer = SimpleAgent(
        name="Reviewer",
        system=(
            "Validate: tags topical and not generic; summary <= 25 words; no code or markdown. "
            "If issues, list in data.issues; otherwise echo cleaned tags/summary."
        ),
        model=llm,
    )
    finalizer = SimpleAgent(
        name="Finalizer",
        system=(
            "Use reviewer feedback to finalize. Output exactly 3 tags in data.tags and the final summary in data.summary. "
            "Set data.issues to []."
        ),
        model=llm,
    )

    task = (
        f'Given rental listing title "{args.title}" and description "{args.content}", produce exactly 3 topical tags '
        f'and a one-sentence summary in your own words. Submitter email is {args.email}.'
    )

    transcript: List[Dict[str, str]] = []

    t0 = time.time()
    a = planner.respond(transcript, task, args.title, args.content, args.strict)
    t1 = time.time()
    transcript.append({"role": "Planner", "content": a.get("message", "")})
    print(f"\n--- Planner ({int((t1 - t0) * 1000)} ms) ---\n{json.dumps(a, indent=2)}")

    t0 = time.time()
    b = reviewer.respond(transcript, task, args.title, args.content, args.strict)
    t1 = time.time()
    transcript.append({"role": "Reviewer", "content": b.get("message", "")})
    print(f"\n--- Reviewer ({int((t1 - t0) * 1000)} ms) ---\n{json.dumps(b, indent=2)}")

    final = finalizer.respond(transcript, task, args.title, args.content, args.strict)
    print(f"\n Finalized Output \n{json.dumps(final, indent=2)}")

    package = {
        "title": args.title,
        "email": args.email,
        "content": args.content,
        "agents": {"transcript": transcript, "final": final.get("data", {})},
        "submissionDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(f"\n Publish Package \n{json.dumps(package, indent=2)}")


if __name__ == "__main__":
    main()
