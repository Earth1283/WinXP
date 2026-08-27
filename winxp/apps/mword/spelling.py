"""Spelling and grammar: the red and green squiggles, and the engine behind
Tools > Spelling and Grammar.

The squiggles are drawn by a QSyntaxHighlighter rather than by editing char
formats, which matters: highlighter formats live in the block's layout, not in
the document, so they never leak into toHtml() and never end up saved in the
file. That is also how Word behaves -- the squiggle is a view artefact.
"""
from __future__ import annotations

import os
import re

from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from .model import settings

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")

SYSTEM_DICTS = (
    "/usr/share/dict/words",
    "/usr/dict/words",
    "/usr/share/dict/american-english",
)

CACHE_PATH = os.path.join(os.path.expanduser("~/.winxp_sim"), "mword_dict.txt")

#: Fallback lexicon for machines with no system word list. Small on purpose --
#: it is the common core plus the vocabulary this simulated desktop uses about
#: itself, which keeps a fresh document from turning entirely red.
FALLBACK_WORDS = """
a able about above accept according account across act action activity actually add
address after afternoon again against age ago agree ahead air all allow almost alone
along already also although always am american among amount an and animal another
answer any anyone anything appear apply approach are area argue arm around arrive art
article as ask assume at attack attention author available avoid away back bad bag
ball bank bar base be beat beautiful because become bed been before begin behavior
behind believe benefit best better between beyond big bill billion bit black blood
blue board body book born both box boy break bring brother budget build building
business but buy by call camera campaign can cancel cannot capital car card care
career carry case catch cause cell center central century certain certainly chair
challenge chance change character charge check child choice choose church citizen
city civil claim class clear clearly click close coach cold collection college color
column come commercial common community company compare computer concern condition
conference congress consider consumer contain continue control copy corner cost could
country couple course court cover create crime cultural culture cup current customer
cut dark data daughter day dead deal death debate decade decide decision deep default
defense degree delete democratic describe design despite detail determine develop
development die difference different difficult dinner direction director discover
discuss discussion disease do doctor dog door double down draw dream drive drop drug
during each early east easy eat economic economy edge edit education effect effort
eight either election else employee end energy enjoy enough enter entire environment
error especially establish even evening event ever every everybody everyone everything
evidence exactly example executive exist expect experience expert explain export eye
face fact factor fail fall family far fast father fear federal feel feeling few field
fight figure file fill film final finally financial find fine finger finish fire firm
first fish five floppy floor fly focus folder follow food foot for force foreign forget
form format former forward found four free friend from front full fund future game
garden gas general generation get girl give glass go goal good government great green
ground group grow growth guess gun guy hair half hand hang happen happy hard have he
head health hear heart heat heavy help her here herself high him himself his history
hit hold home hope hospital hot hotel hour house how however huge human hundred husband
i icon idea identify if image imagine impact important improve in include including
increase indeed indicate individual industry information insert inside install instead
institution interest interesting international interview into invalid investment involve
is issue it item its itself job join just keep key kid kill kind kitchen knowledge know
land language large last late later laugh law lawyer lay lead leader learn least leave
left leg legal less let letter level lie life light like likely line list listen little
live local long look lose loss lot love low machine magazine main maintain major majority
make man manage management manager many margin market marriage material matter may maybe
me mean measure media medical meet meeting member memory mention message method middle
might military million mind minute miss mission model modern moment money month more
morning most mother mouse move movement movie much music must my myself name nation
national natural nature near nearly necessary need network never new news newspaper
next nice night no none nor north not note nothing notice now number occur of off offer
office officer official often oh oil ok old on once one only onto open operation opportunity
option or order organization other others our out outside over own owner page pain paint
paper paragraph parent part participant particular particularly partner party pass past
patient pattern pay peace people per perform performance perhaps period person personal
phone physical pick picture piece place plan plant play player please point police policy
political politics poor popular population position positive possible power practice
prepare present president press pressure pretty prevent price print private probably
problem process produce product production professional professor program project property
protect prove provide public pull purpose push put quality question quickly quite race
radio raise range rate rather reach read ready real reality realize really reason receive
recent recently recognize record red reduce reflect region relate relationship religious
remain remember remove repeat replace report represent require research resource respond
response responsibility rest result return reveal rich right rise risk road rock role
room rule run safe same save say scale scene school science scientist score screen scroll
sea search season seat second section security see seek seem select sell send senior sense
series serious serve service set settings seven several sex shake share she shoot short
shot should shoulder show side sign significant similar simple simply since sing single
sister sit site situation six size skill skin small smile so social society soldier some
somebody someone something sometimes son song soon sort sound source south space speak
special specific speech spell spend sport spring staff stage stand standard star start
state statement station stay step still stock stop store story strategy street strong
structure student study stuff style subject success successful such suddenly suffer
suggest summer support sure surface system table take talk task tax teach teacher team
technology television tell ten tend term test text than thank that the their them themselves
then theory there these they thing think third this those though thought thousand threat
three through throughout throw thus time to today together tone tonight too tool top total
tough toward town trade traditional training travel treat treatment tree trial trip trouble
true truth try turn tv two type under understand undo unit until up upon us use used user
usually value various version very victim video view violence virus visit voice vote wait
walk wall want war watch water way we weapon wear web week weight welcome well west what
whatever when where whether which while white who whole whom whose why wide wife will win
window wish with within without woman women word work worker world worry would write writer
wrong yard yeah year yes yet you young your yourself zoom
"""


def _load_lexicon() -> set[str]:
    words: set[str] = set()
    for path in (CACHE_PATH,) + SYSTEM_DICTS:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    token = line.strip().lower()
                    if token and token.isalpha():
                        words.add(token)
        except OSError:
            continue
        if words:
            break
    if not words:
        words = {w for w in FALLBACK_WORDS.split() if w}
    words.update(FALLBACK_WORDS.split())
    return words


class SpellChecker:
    """Dictionary lookup with the usual inflection tolerance, plus Word's
    "suggest by edit distance" behaviour for the Spelling dialog."""

    _lexicon: set[str] | None = None
    _common: set[str] | None = None

    def __init__(self):
        if SpellChecker._lexicon is None:
            SpellChecker._lexicon = _load_lexicon()
            SpellChecker._common = {w for w in FALLBACK_WORDS.split() if w}
        self.lexicon = SpellChecker._lexicon
        self.common = SpellChecker._common
        self.session_ignored: set[str] = set()

    # -- lookup ---------------------------------------------------------

    def known(self, word: str) -> bool:
        low = word.lower().strip("'’-")
        if not low:
            return True
        if low in self.session_ignored or low in settings.custom_dictionary:
            return True
        if low in self.lexicon:
            return True
        # possessives and contractions
        for tail in ("'s", "’s", "'ll", "'re", "'ve", "'d", "n't"):
            if low.endswith(tail) and low[: -len(tail)] in self.lexicon:
                return True
        # regular inflections a plain word list usually omits
        for suffix, stems in (
            ("s", ("",)), ("es", ("", "e")), ("ed", ("", "e")), ("d", ("",)),
            ("ing", ("", "e")), ("ly", ("",)), ("er", ("", "e")), ("est", ("", "e")),
            ("ies", ("y",)), ("ied", ("y",)),
        ):
            if low.endswith(suffix):
                stem = low[: -len(suffix)]
                if len(stem) < 3:
                    continue    # a word list full of two-letter fragments
                for repl in stems:
                    if (stem + repl) in self.lexicon:
                        return True
                if len(stem) > 2 and stem[-1] == stem[-2] and stem[:-1] in self.lexicon:
                    return True  # doubled consonant: stopped, running
        if "-" in low:
            return all(self.known(part) for part in low.split("-") if part)
        return False

    def should_check(self, word: str) -> bool:
        if len(word) < 3:
            return False
        if any(ch.isdigit() for ch in word):
            return False
        if word.isupper():
            return False           # acronyms, as Word does by default
        stripped = word.strip("'’-")
        if not stripped or not stripped[0].isalpha():
            return False
        # Word skips InterCaps ("MacroHard", "PhotoChop") as probable names
        inner = stripped[1:]
        return not any(ch.isupper() for ch in inner)

    def ignore_all(self, word: str):
        self.session_ignored.add(word.lower())

    # -- suggestions ----------------------------------------------------

    ALPHABET = "abcdefghijklmnopqrstuvwxyz"

    def _edits1(self, word: str) -> set[str]:
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        out = set()
        for left, right in splits:
            if right:
                out.add(left + right[1:])
                if len(right) > 1:
                    out.add(left + right[1] + right[0] + right[2:])
                for ch in self.ALPHABET:
                    out.add(left + ch + right[1:])
            for ch in self.ALPHABET:
                out.add(left + ch + right)
        return out

    def suggest(self, word: str, limit: int = 8) -> list[str]:
        low = word.lower()
        replacement = settings.autocorrect.get(low)
        ordered: list[str] = []
        if replacement:
            ordered.append(replacement)
        def rank(candidate: str) -> tuple:
            # Word leads with the everyday word, not the first one alphabetically.
            return (0 if candidate in self.common else 1,
                    abs(len(candidate) - len(low)), candidate)

        near = sorted((w for w in self._edits1(low) if w in self.lexicon), key=rank)
        if len(near) < limit:
            two = set()
            for candidate in self._edits1(low):
                if len(two) > 4000:
                    break
                two.update(e for e in self._edits1(candidate) if e in self.lexicon)
            near += sorted(two - set(near), key=rank)
        for candidate in near:
            if candidate not in ordered:
                ordered.append(candidate)
            if len(ordered) >= limit:
                break
        if word[:1].isupper():
            ordered = [s.capitalize() for s in ordered]
        return ordered


# --------------------------------------------------------------- grammar ---

GRAMMAR_RULES = [
    (re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE), "Repeated Word"),
    (re.compile(r"[ ]{2,}(?=\S)"), "Extra Space Between Words"),
    (re.compile(r"\s+[,;:](?=\s|$)"), "Space Before Punctuation"),
    (re.compile(r"\ba\s+(?=[aeiou])", re.IGNORECASE), "Article Use"),
    (re.compile(r"\ban\s+(?=[bcdfgjklmnpqrstvwxyz])", re.IGNORECASE), "Article Use"),
    (re.compile(r"\b(should|could|would|must|might)\s+of\b", re.IGNORECASE),
     "Commonly Confused Words"),
    (re.compile(r"\bthere\s+(is|was)\s+(many|several|few)\b", re.IGNORECASE),
     "Subject-Verb Agreement"),
    (re.compile(r"\bits'\B"), "Possessive Use"),
    (re.compile(r"[.!?]\s+[a-z]"), "Capitalization"),
]


class WordHighlighter(QSyntaxHighlighter):
    """Red squiggles under words the dictionary rejects, green under the
    grammar rules -- both live, both repainted as you type, neither saved."""

    def __init__(self, document, checker: SpellChecker):
        super().__init__(document)
        self.checker = checker
        self.spelling_enabled = True
        self.grammar_enabled = True

        self.spell_format = QTextCharFormat()
        self.spell_format.setUnderlineColor(QColor("#e01b1b"))
        self.spell_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.WaveUnderline)

        self.grammar_format = QTextCharFormat()
        self.grammar_format.setUnderlineColor(QColor("#1f9d3a"))
        self.grammar_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.WaveUnderline)

    def set_enabled(self, spelling=None, grammar=None):
        if spelling is not None:
            self.spelling_enabled = spelling
        if grammar is not None:
            self.grammar_enabled = grammar
        self.rehighlight()

    def highlightBlock(self, text: str):
        if self.spelling_enabled:
            for match in WORD_RE.finditer(text):
                word = match.group()
                if self.checker.should_check(word) and not self.checker.known(word):
                    self.setFormat(match.start(), len(word), self.spell_format)
        if self.grammar_enabled:
            for rule, _label in GRAMMAR_RULES:
                for match in rule.finditer(text):
                    start, end = match.span()
                    self.setFormat(start, max(1, end - start), self.grammar_format)


def scan_document(document, checker: SpellChecker, check_spelling=True, check_grammar=True):
    """Walk the whole document once and yield every issue in reading order --
    what the Spelling and Grammar dialog steps through.

    Yields (kind, position, length, word_or_phrase, label).
    """
    block = document.begin()
    while block.isValid():
        text = block.text()
        base = block.position()
        found: list[tuple] = []
        if check_spelling:
            for match in WORD_RE.finditer(text):
                word = match.group()
                if checker.should_check(word) and not checker.known(word):
                    found.append(("spelling", base + match.start(), len(word),
                                  word, "Not in Dictionary"))
        if check_grammar:
            for rule, label in GRAMMAR_RULES:
                for match in rule.finditer(text):
                    start, end = match.span()
                    found.append(("grammar", base + start, max(1, end - start),
                                  match.group().strip(), label))
        for issue in sorted(found, key=lambda i: i[1]):
            yield issue
        block = block.next()
