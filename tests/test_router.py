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
    assert i.level == 1


def test_unknown_goes_to_clarification_level():
    i = R.route("che tempo farà domani secondo te?")
    assert i.kind == "unknown" and i.level == 2
