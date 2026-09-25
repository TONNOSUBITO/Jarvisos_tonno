import pytest

from jarvis.routing.router import RuleRouter

R = RuleRouter()


@pytest.mark.parametrize("text,kind,slots", [
    ("apri calcolatrice", "open_app", {"app": "calcolatrice"}),
    ("Jarvis, avvia Blocco Note.", "open_app", {"app": "Blocco Note"}),
    ("cerca meteo Roma", "web_search", {"query": "meteo Roma"}),
    ("cerca su internet ricetta carbonara", "web_search", {"query": "ricetta carbonara"}),
    ("cerca e apri documentazione Python", "web_search_open", {"query": "documentazione Python"}),
    ("Cerca i apri documentazioni.", "web_search_open", {"query": "documentazioni"}),
    ("Cerca e apprì documentazione.", "web_search_open", {"query": "documentazione"}),
    ("cerca ed apri meteo", "web_search_open", {"query": "meteo"}),
    ("apri il primo risultato per orari treni", "web_search_open", {"query": "orari treni"}),
    ("apri il sito example.com", "web_open", {"url": "example.com"}),
    ("apri https://example.com/a", "web_open", {"url": "https://example.com/a"}),
    ("prepara una nota: comprare latte", "note", {"text": "comprare latte"}),
    ("scrivi un report sulla riunione di oggi", "note", {"text": "riunione di oggi"}),
    ("stop", "stop", {}),
    ("Fermati!", "stop", {}),
])
def test_known_intents(text, kind, slots):
    i = R.route(text)
    assert i.kind == kind
    assert i.slots == slots


def test_unknown_intent():
    assert R.route("che tempo farà domani secondo te?").kind == "unknown"


@pytest.mark.parametrize("text,kind", [
    ("Apri la calcolatrice.", "open_app"), ("Puoi aprire la calcolatrice?", "open_app"),
    ("Mi apri la calcolatrice per favore", "open_app"), ("Avvia il Blocco note!", "open_app"),
    ("Cercami le notizie di oggi", "web_search"), ("Potresti cercare meteo Roma?", "web_search"),
    ("Vai su youtube.com", "web_open"), ("Ricordati che domani ho il dentista", "remember"),
    ("Cosa ricordi di me?", "memory_list"), ("Ferma tutto", "stop"),
])
def test_spoken_phrasing(text, kind):
    """Frasi come escono dalla trascrizione: cortesia, infiniti, articoli, punteggiatura."""
    assert R.route(text).kind == kind


def test_app_names_with_articles():
    from jarvis.tools.apps import MockAppAdapter, OpenAppTool
    t = OpenAppTool({"calcolatrice": ["calc.exe"], "blocco note": ["notepad.exe"]}, MockAppAdapter())
    assert t.resolve("la calcolatrice") == ["calc.exe"] and t.resolve("il Blocco note") == ["notepad.exe"]
    assert t.resolve("l'calcolatrice") == ["calc.exe"] and t.resolve("regedit") is None
