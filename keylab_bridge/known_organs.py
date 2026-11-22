"""What well-known sample-set organs were built for (from the builders' / sample makers' own pages), used to fill an organ's
"character" in its organ map the first time. Ratings (0-5) are an interpretation of those pages: edit them in the Setter Editing tab.

Sources: https://piotrgrabowski.pl/friesach/ , https://piotrgrabowski.pl/cracow-st-john-cantius/

CHANGELOG
2026-11-22  New: KNOWN, character_for().
"""

KNOWN = {
    "friesach": {
        "period": {"baroque": 4, "classical": 3, "romantic": 5, "modern": 4},
        "tradition": {"catholic": 3, "early_protestant": 4, "modern_church": 3},
        "composers": ["Buxtehude", "Bach", "Mendelssohn", "Franck", "Widor", "Dupre", "Messiaen"],
        "built_for": ("Parish church of St. Bartholomaeus, Friesach (Austria). Orgelbau Eisenbarth, Passau, 2000; 3 manuals + pedal, 44 stops, "
                      "tracker action. Eclectic: solid German Hauptwerk, Schwellwerk as French Recit and baroque Positiv, French Solowerk; "
                      "voiced rather strongly for a large church. Suits Luebeck / Buxtehude / Bach through Mendelssohn, Franck, Widor to Dupre / Messiaen."),
        "layering": "Hauptwerk is the foundation (Praestant 16', Principal 8', Mixturen, Trompeten); Schwellwerk gives Recit colour (Viola, Vox celeste, "
                    "Trompete harmonique, Hautbois) and Positiv colour (Nazard, Tierce, Larigot, Plein Jeu); Solowerk for solos (Cornet, Chamade, Englischhorn).",
    },
    "cracow": {
        "period": {"baroque": 2, "classical": 3, "romantic": 5, "modern": 3},
        "tradition": {"catholic": 4, "early_protestant": 2, "modern_church": 3},
        "composers": ["Franck", "Vierne", "Widor", "Guilmant"],
        "built_for": ("St. John Cantius, Cracow (Poland). Jacek Siedlar, Modlnica, 2004, financed by the parishioners; 3 manuals + pedal, 40 stops, "
                      "mechanical key action, electrical stop action. Stylistic concept: French romanticism."),
        "layering": "Manual I: Montre / Prestant / Doublette with Cornet or Plein Jeu and Trompette / Clairon (Grand Choeur); Manual II: Cor de Nuit, "
                    "Salicional, Unda Maris, Nazard / Tierce (Cornet de recit) and Cromorne / Clarinette; Manual III (Recit expressif): Voix Celeste, "
                    "Aeoline, Trompette harmonique, Hautbois, Basson. Tremulants on II and III.",
    },
}


def character_for(organ_name, organ_file=""):
    """The known character of an organ (a deep copy) or {} when it is not one of the known sample sets."""
    import copy
    text = f"{organ_name} {organ_file}".casefold()
    for key, value in KNOWN.items():
        if key in text:
            return copy.deepcopy(value)
    return {}
