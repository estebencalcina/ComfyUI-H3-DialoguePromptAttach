import json
import re
import urllib.request

ENGLISH = re.compile(r"\b(?:so nice|very nice|oh my god|thank you|thanks|hello|hi there|how are you|good morning|good night|let's go|i love you|i'm|you're|she's|he's|don't|can't|beautiful|amazing|awesome|that's|what|where|why|please|sorry|yes|no way)\b", re.I)
NON_SPEECH = {'[music]', '[silence]', '[noise]', '[applause]', '(music)', '(silence)'}

def clean(t):
    s = str(t or '').strip()
    s = re.sub(r'</?d>', '', s, flags=re.I)
    s = re.sub(r'\[(?:Spanish|English|Español)\]', '', s, flags=re.I)
    s = re.sub(r'^\s*(?:\(S\d+\)|<Subject\s+\d+>)\s*', '', s, flags=re.I)
    return s.strip(' "\'\n\r')

def translate_if_needed(text, model='gemma3:4b'):
    text = clean(text)
    if not text or text.lower() in NON_SPEECH: return ''
    # This catches known English leakage, including the reported 'so nice'.
    # It does NOT claim to be a complete language detector.
    if not ENGLISH.search(text): return text
    prompt = ('Translate this spoken phrase into natural Latin American Spanish. '
              'Return ONLY the Spanish translation, without English, tags, explanation, alternatives or quotes. '
              'Translate EVERY English word. Example: so nice -> Qué bonito.\n\n' + text)
    body=json.dumps({'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0}},ensure_ascii=False).encode('utf-8')
    try:
        req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=body,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=90) as response:
            out=json.load(response).get('response','')
        out=clean(out)
    except Exception as exc:
        raise RuntimeError('El texto para MiniMax H3 sigue en inglés (por ejemplo, "so nice") y la traducción de respaldo por Ollama local falló. Verifica el nodo 90007 y Ollama en localhost:11434: '+str(exc)) from exc
    if not out or ENGLISH.search(out):
        raise RuntimeError('Ollama no devolvió español limpio para el diálogo: '+repr(out[:200]))
    return out

class H3DialoguePromptAttach:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'visual_prompt': ('STRING',{'forceInput':True}),
            'spanish_dialogue': ('STRING',{'forceInput':True}),
            'translated_segments_json': ('STRING',{'forceInput':True})
        }}
    RETURN_TYPES=('STRING',)
    RETURN_NAMES=('prompt',)
    FUNCTION='merge'
    CATEGORY='H3/Audio'

    def merge(self,visual_prompt,spanish_dialogue,translated_segments_json):
        prompt=str(visual_prompt or '').strip()
        segments=[]
        try:
            obj=json.loads(translated_segments_json or '[]')
            if isinstance(obj,dict):obj=obj.get('segments',obj.get('translated_segments',[]))
            if isinstance(obj,list):
                for s in obj:
                    if not isinstance(s,dict):continue
                    phrase=clean(s.get('translated_text') or s.get('spanish_text') or s.get('text'))
                    if not phrase or phrase.lower() in NON_SPEECH:continue
                    try:
                        a=float(s.get('start',s.get('start_time')))
                        b=float(s.get('end',s.get('end_time')))
                        timing=f'At {a:.2f}s-{b:.2f}s, '
                    except (TypeError,ValueError):timing=''
                    segments.append((timing,phrase))
        except (TypeError,ValueError,json.JSONDecodeError):pass
        consolidated=clean(spanish_dialogue)
        if not segments and consolidated:segments=[('',consolidated)]
        # When there is one segment, the consolidated Spanish output is preferred
        # over the segment JSON if the JSON still contains untranslated English.
        if len(segments)==1 and consolidated and ENGLISH.search(segments[0][1]) and not ENGLISH.search(consolidated):
            segments[0]=(segments[0][0],consolidated)
        if not segments:
            return (prompt+'\nNo dialogue was detected; do not invent speech.',)
        lines=[]
        for time_hint,phrase in segments:
            phrase=translate_if_needed(phrase)
            if not phrase:continue
            if phrase[-1] not in '.?!¡¿':phrase+='.'
            lines.append(f'{time_hint}<Subject 1> (S1) speaks ONLY in Spanish: <d>[Spanish] {phrase}</d>')
        if not lines:return (prompt,)
        note=('\nMANDATORY LANGUAGE OVERRIDE FOR ALL SPOKEN AUDIO: Spanish only (es-PE / Latin American Spanish). '
              'Generate no English speech, no English fillers and no English repetitions. '
              'The words inside <d>[Spanish] ... </d> are the ONLY words that may be spoken. '
              'Follow <Video 1> movement and timing; <Picture 1> defines face, <Picture 2> body, identity RefMod reinforces them. '
              'Do not speak prompt text, section headings, timestamps or language tags.\n'
              +'\n'.join(lines)+'\n')
        m=re.search(r'(?im)^\s*(?:overall_soundscape|non_diegetic_music)\s*:',prompt)
        if m:prompt=prompt[:m.start()].rstrip()+'\n'+note+'\n'+prompt[m.start():]
        else:prompt+='\n'+note
        return (prompt,)

NODE_CLASS_MAPPINGS={'H3DialoguePromptAttach':H3DialoguePromptAttach}
NODE_DISPLAY_NAME_MAPPINGS={'H3DialoguePromptAttach':'H3 — Español obligatorio (Whisper/Ollama) V76'}
