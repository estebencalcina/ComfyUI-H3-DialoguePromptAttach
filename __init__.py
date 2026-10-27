import json
import re

class H3DialoguePromptAttach:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "visual_prompt": ("STRING", {"forceInput": True}),
            "spanish_dialogue": ("STRING", {"forceInput": True}),
            "translated_segments_json": ("STRING", {"forceInput": True})
        }}
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "merge"
    CATEGORY = "H3/Audio"

    def merge(self, visual_prompt, spanish_dialogue, translated_segments_json):
        prompt = str(visual_prompt or "").strip()
        segments = []
        try:
            obj = json.loads(translated_segments_json or "[]")
            if isinstance(obj, dict):
                obj = obj.get("segments", obj.get("translated_segments", []))
            if isinstance(obj, list):
                for s in obj:
                    if not isinstance(s, dict):
                        continue
                    phrase = str(s.get("translated_text") or s.get("spanish_text") or s.get("text") or "").strip()
                    if not phrase or phrase.lower() in ("[music]", "[silence]", "[noise]", "[applause]"):
                        continue
                    try:
                        start, end = float(s.get("start", s.get("start_time"))), float(s.get("end", s.get("end_time")))
                        time_hint = f"At {start:.2f}s–{end:.2f}s, "
                    except (ValueError, TypeError):
                        time_hint = ""
                    segments.append((time_hint, phrase))
        except (ValueError, TypeError):
            pass
        if not segments:
            plain = str(spanish_dialogue or "").strip()
            if plain:
                segments = [("", plain)]
        if not segments:
            return (prompt + "\nNo intelligible spoken dialogue was transcribed. Do not invent speech.",)
        # Canonical MiniMax H3 syntax: speaking action and (S1) outside <d>.
        # Speaker labels in multi-person material must be separated upstream;
        # these single-speaker defaults should not be used for multiple speakers.
        lines=[]
        for interval,phrase in segments:
            phrase=re.sub(r"</?d>", "", phrase, flags=re.I)
            phrase=re.sub(r"^\s*\[Spanish\]\s*", "", phrase, flags=re.I).strip()
            if not phrase:
                continue
            if phrase[-1] not in '.?!':
                phrase += '.'
            lines.append(f"{interval}<Subject 1> (S1) speaks in Spanish with a natural, character-appropriate voice: <d>[Spanish] {phrase}</d>")
        if not lines:
            return (prompt,)
        note=("\nDialogue is spoken by the swapped on-screen character <Subject 1> (S1). "
              "<Picture 1> is the face reference, <Picture 2> is the body reference, "
              "and the identity RefMod reinforces the same character. "
              "<Video 1> supplies the original motion, mouth action, setting, camera, and approximate speaking times. "
              "Synchronize the new Spanish dialogue with the visible performer as closely as possible. "
              "Generate audible dialogue with the H3 audio decoder; do not speak the labels, timestamps, or instructions. "
              "Do not invent additional dialogue or reuse the original performer's voice.\n"
              + "\n".join(lines) + "\n")
        # H3 Ref2VA prompt: dialogue belongs in detailed_description, NOT after
        # non_diegetic_music, where it is more likely to be ignored.
        match=re.search(r"(?im)^\s*(?:overall_soundscape|non_diegetic_music)\s*:",prompt)
        if match:
            prompt=prompt[:match.start()].rstrip() + "\n" + note + "\n" + prompt[match.start():]
        else:
            prompt += "\n" + note
        return (prompt,)

NODE_CLASS_MAPPINGS = {'H3DialoguePromptAttach': H3DialoguePromptAttach}
NODE_DISPLAY_NAME_MAPPINGS = {'H3DialoguePromptAttach': 'H3 — Whisper/Ollama to <d>[Spanish] dialogue'}
