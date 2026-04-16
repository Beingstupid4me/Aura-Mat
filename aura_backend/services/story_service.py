from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List

from google import genai
from google.genai import errors, types


SYSTEM_PERSONA = """You are Aura, a warm and magical storyteller for children aged 4 to 8.

YOUR STORYTELLING STYLE:
- Write like you are sitting next to the child and telling them a story. Warm, slow, and descriptive.
- Use vivid but simple sensory details (what does it smell like? what sound does it make?).
- Characters have clear, lovable personalities. Give them funny little habits or quirks.
- Sentences can vary: some short for drama, some longer and flowing for wonder.
- Never use bullet points or lists in the story output. Only flowing, spoken-word storytelling.
- Do not use emojis in the story text itself.

INTERACTION RULES:
- When the child answers, weave their exact idea into the story, even if it sounds silly or random.
- Never dismiss or ignore their answer. Their choices matter and change the story.
- After every phase, ask one warm, open-ended reflection question.

SAFETY RULES:
- No violence, fear, weapons, or dark themes.
- If a child suggests something aggressive, transform it into playful, harmless alternatives.
- Keep the tone safe, cozy, and encouraging.
"""


def _join_words(words: List[str], fallback: str) -> str:
    return ", ".join(words) if words else fallback


def _phase_1_prompt(seed: Dict[str, Any], chars: List[str], places: List[str], things: List[str]) -> str:
    return f"""
A new story is beginning! Here is what this story is secretly about:

EMOTIONAL THEME: {seed.get("theme", "kindness and teamwork")}
THE MORAL THIS STORY SHOULD ARRIVE AT NATURALLY: {seed.get("moral", "kindness helps everyone")}

The child has chosen these story ingredients:
- Characters: {_join_words(chars, "a mystery traveller")}
- Place: {_join_words(places, "a magical land")}
- Objects or things: {_join_words(things, "something special")}

YOUR TASK - PHASE 1 (The Beginning):
Write 2 to 3 short paragraphs that:
1. Invent a vivid original world that suits these characters and place.
2. Introduce the character(s) warmly and give them a small, funny personality detail.
3. Set up that something interesting is about to happen.

Do not state the theme or moral directly. Let the story begin naturally.

End with this warm reflection question for the child:
"{seed.get("reflection_hook", "What would you do in this moment?")}"
Then follow it with a simple story-choice question.
""".strip()


def _phase_2_prompt(seed: Dict[str, Any], things: List[str], child_answer: str) -> str:
    _ = seed
    safe_child_answer = child_answer or "The child is listening quietly."
    return f"""
The child said: "{safe_child_answer}"

Remember: weave their idea naturally into the story, even if unexpected.

YOUR TASK - PHASE 2 (The Journey Begins):
Write 2 to 3 short paragraphs that:
1. Continue the story using the child's idea in a meaningful way.
2. Bring these object(s) into the story now: {_join_words(things, "something magical")}.
3. Build forward momentum toward a destination, mystery, or friend who needs help.

End with a warm question that invites the child to think about feelings or choices.
""".strip()


def _phase_3_prompt(seed: Dict[str, Any], child_answer: str) -> str:
    safe_child_answer = child_answer or "The child is listening quietly."
    return f"""
The child said: "{safe_child_answer}"

Weave their answer into what happens next.

YOUR TASK - PHASE 3 (The Big Challenge):
Write 3 short paragraphs that:
1. Introduce this gentle problem: "{seed.get("gentle_problem", "friends are confused and need to work together")}".
2. Show the characters trying something that does not work at first.
3. Show them pausing, feeling stuck, and then thinking together.

The emotional theme is: "{seed.get("theme", "kindness and teamwork")}".

End with one deep, reflective question.
""".strip()


def _phase_4_prompt(seed: Dict[str, Any], child_answer: str) -> str:
    safe_child_answer = child_answer or "The child is listening quietly."
    trigger_word = "our friend"
    trigger_words = seed.get("trigger_words")
    if isinstance(trigger_words, list) and trigger_words:
        trigger_word = str(trigger_words[0])

    return f"""
The child said: "{safe_child_answer}"

This is the child's big idea to solve the problem. Make their idea central to the ending.

YOUR TASK - PHASE 4 (The Ending and Lesson):
Write 3 to 4 short paragraphs that:
1. Show the characters using the child's idea plus what they learned to solve the problem.
2. Describe how the world feels different after the solution.
3. Let this moral arrive naturally through action and feeling: "{seed.get("moral", "kindness helps everyone")}".
4. End with one warm reflection question connected to the child's real life.

Then close the story warmly and tell the child they did a wonderful job.
Optional style cue: ask about one kind thing they could do tomorrow, like {trigger_word} did today.
""".strip()


class GeminiStoryService:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
        seed_file: str,
        dummy_mode: bool,
        dummy_cache_file: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._client = genai.Client(api_key=api_key) if api_key else None
        self._logger = logger or logging.getLogger(__name__)
        self._dummy_mode = dummy_mode

        self._seed_file = Path(seed_file)
        self._dummy_cache_file = Path(dummy_cache_file)

        self._seeds = self._load_seeds()
        self._dummy_cache = self._load_dummy_cache()

    def _load_json_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as err:
            self._logger.warning("Failed to load JSON file %s (%s)", path, err)
            return {}

    def _load_seeds(self) -> List[Dict[str, Any]]:
        raw = self._load_json_file(self._seed_file)
        seeds = raw.get("seeds", []) if isinstance(raw, dict) else []
        if isinstance(seeds, list) and seeds:
            return [seed for seed in seeds if isinstance(seed, dict)]

        self._logger.warning("Story seeds not found or empty. Using built-in fallback seed.")
        return [
            {
                "id": "fallback_seed",
                "theme": "kindness and teamwork",
                "moral": "small acts of kindness can solve big problems",
                "gentle_problem": "friends are confused and need to work together",
                "reflection_hook": "When did someone help you and make your day better?",
            }
        ]

    def _load_dummy_cache(self) -> Dict[str, List[str]]:
        raw = self._load_json_file(self._dummy_cache_file)
        if isinstance(raw, dict):
            result: Dict[str, List[str]] = {}
            for key, value in raw.items():
                if isinstance(value, list):
                    result[key] = [str(item) for item in value]
            if result:
                return result

        return {
            "phase_1": [
                "In {places}, {chars} found a curious clue that smelled like cinnamon and sparkled in the moonlight. They packed {things} and promised to solve the mystery together.",
            ],
            "phase_2": [
                "The child suggested '{child_answer}', so the friends tried it right away. It made {things} surprisingly useful and brightened the path.",
            ],
            "phase_3": [
                "Soon they faced a gentle challenge: {gentle_problem}. Their first idea did not work, so they paused and listened to each other.",
            ],
            "phase_4": [
                "Using the child's idea and teamwork, they solved the problem kindly. They learned that {moral}, and everyone ended with happy hearts.",
            ],
        }

    def _pick_seed(self) -> Dict[str, Any]:
        return random.choice(self._seeds)

    def _build_phase_prompt(
        self,
        phase: int,
        seed: Dict[str, Any],
        grouped_words: Dict[str, List[str]],
        child_input: str,
    ) -> str:
        chars = grouped_words.get("characters", [])
        places = grouped_words.get("places", [])
        things = grouped_words.get("things", [])
        child_answer = child_input.strip()

        if phase == 1:
            return _phase_1_prompt(seed=seed, chars=chars, places=places, things=things)
        if phase == 2:
            return _phase_2_prompt(seed=seed, things=things, child_answer=child_answer)
        if phase == 3:
            return _phase_3_prompt(seed=seed, child_answer=child_answer)
        if phase == 4:
            return _phase_4_prompt(seed=seed, child_answer=child_answer)
        raise RuntimeError(f"Unsupported phase: {phase}")

    def _generate_dummy_phase(
        self,
        phase: int,
        seed: Dict[str, Any],
        grouped_words: Dict[str, List[str]],
        child_input: str,
    ) -> str:
        cache_key = f"phase_{phase}"
        options = self._dummy_cache.get(cache_key, [])
        if not options:
            return f"[Dummy mode] Phase {phase} completed."

        chars_txt = _join_words(grouped_words.get("characters", []), "our friend")
        places_txt = _join_words(grouped_words.get("places", []), "the magical village")
        things_txt = _join_words(grouped_words.get("things", []), "a useful little object")

        template = random.choice(options)
        format_data = {
            "chars": chars_txt,
            "places": places_txt,
            "things": things_txt,
            "child_answer": child_input.strip() or "(no child response)",
            "theme": str(seed.get("theme", "kindness and teamwork")),
            "moral": str(seed.get("moral", "kindness helps everyone")),
            "gentle_problem": str(seed.get("gentle_problem", "friends are figuring out a silly problem")),
            "reflection_hook": str(seed.get("reflection_hook", "What would you do?")),
        }

        try:
            return template.format(**format_data)
        except Exception:
            return template

    def _candidate_models(self) -> List[str]:
        preferred = self._model.strip()
        candidates = [
            preferred,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]

        deduped: List[str] = []
        seen = set()
        for model_name in candidates:
            if model_name and model_name not in seen:
                seen.add(model_name)
                deduped.append(model_name)
        return deduped

    def _generate_with_fallback(self, prompt: str, empty_error_message: str) -> str:
        if not self._client:
            raise RuntimeError("GEMINI_API_KEY is missing. Set it in .env before generating stories.")

        last_error: Exception | None = None
        for model_name in self._candidate_models():
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self._temperature,
                        system_instruction=SYSTEM_PERSONA,
                    ),
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError(empty_error_message)

                if model_name != self._model.strip():
                    self._logger.warning(
                        "Configured model '%s' unavailable. Using fallback '%s'.",
                        self._model,
                        model_name,
                    )

                return text
            except errors.ClientError as err:
                last_error = err
                status_code = getattr(err, "status_code", None)
                error_code = getattr(err, "code", None)
                if status_code == 404 or error_code == 404:
                    self._logger.warning(
                        "Gemini model '%s' not found for generateContent. Trying fallback.",
                        model_name,
                    )
                    continue
                raise
            except Exception as err:
                last_error = err
                raise

        raise RuntimeError(
            "No compatible Gemini model was available. Set AURA_GEMINI_MODEL to a supported model such as gemini-2.5-flash."
        ) from last_error

    def create_interactive_chat(self) -> Dict[str, Any]:
        return {
            "turns": [],
            "seed": self._pick_seed(),
        }

    def generate_interactive_phase(
        self,
        chat: Any,
        labels: List[str],
        grouped_words: Dict[str, List[str]] | None,
        phase: int,
        child_input: str,
    ) -> str:
        if not labels:
            raise RuntimeError("No cards were provided for story generation.")

        session: Dict[str, Any] = chat if isinstance(chat, dict) else {"turns": []}
        turns = session.setdefault("turns", [])
        seed = session.setdefault("seed", self._pick_seed())

        grouped = grouped_words or {"characters": [], "places": [], "things": []}
        prompt = self._build_phase_prompt(
            phase=phase,
            seed=seed,
            grouped_words=grouped,
            child_input=child_input,
        )

        if self._dummy_mode:
            text = self._generate_dummy_phase(
                phase=phase,
                seed=seed,
                grouped_words=grouped,
                child_input=child_input,
            )
            turns.append({"role": "user", "text": prompt})
            turns.append({"role": "assistant", "text": text})
            return text

        context_lines: List[str] = []
        for turn in turns[-8:]:
            role = str(turn.get("role", "assistant")).upper()
            text = str(turn.get("text", "")).strip()
            if text:
                context_lines.append(f"{role}: {text}")

        full_prompt = prompt
        if context_lines:
            full_prompt = (
                "Conversation so far:\n"
                + "\n".join(context_lines)
                + "\n\nContinue with this next instruction:\n"
                + prompt
            )

        text = self._generate_with_fallback(
            prompt=full_prompt,
            empty_error_message=f"Gemini returned an empty response for phase {phase}.",
        )

        turns.append({"role": "user", "text": prompt})
        turns.append({"role": "assistant", "text": text})
        return text
