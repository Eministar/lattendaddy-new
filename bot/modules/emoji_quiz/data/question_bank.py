from __future__ import annotations

def expand_aliases(*values: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        variant = str(value or "").strip()
        key = variant.casefold()
        if not variant or key in seen:
            continue
        seen.add(key)
        result.append(variant)
    return result

EMOJI_QUIZ_BANK: dict[str, dict] = {
    "städte": {
        "label": "Städte",
        "emoji": "🏙️",
        "items": [
            {"prompt": "🗼🥐❤️", "answer": "Paris", "aliases": expand_aliases("Paris")},
            {"prompt": "☔👑🕰️", "answer": "London", "aliases": expand_aliases("London")},
            {"prompt": "🍕🏛️⛲", "answer": "Rom", "aliases": expand_aliases("Rom", "Rome")},
            {"prompt": "🎡🍺🥨", "answer": "München", "aliases": expand_aliases("München", "Munich")},
            {"prompt": "🍣🗼🌸", "answer": "Tokio", "aliases": expand_aliases("Tokio", "Tokyo")},
            {"prompt": "🧀⌚🏔️", "answer": "Zürich", "aliases": expand_aliases("Zürich", "Zurich")},
            {"prompt": "🎭🚤🏞️", "answer": "Venedig", "aliases": expand_aliases("Venedig", "Venice")},
            {"prompt": "🌉🚋🍫", "answer": "San Francisco", "aliases": expand_aliases("San Francisco")},
            {"prompt": "🧸🧱🇩🇪", "answer": "Berlin", "aliases": expand_aliases("Berlin")},
            {"prompt": "⚓🌊🐟", "answer": "Hamburg", "aliases": expand_aliases("Hamburg")},
            {"prompt": "⚽🍺🎡", "answer": "Dortmund", "aliases": expand_aliases("Dortmund")},
            {"prompt": "💼🏦🇩🇪", "answer": "Frankfurt", "aliases": expand_aliases("Frankfurt", "Frankfurt am Main")},
            {"prompt": "🖼️🚲🌷", "answer": "Amsterdam", "aliases": expand_aliases("Amsterdam")},
            {"prompt": "🕌🐈🌉", "answer": "Istanbul", "aliases": expand_aliases("Istanbul")},
            {"prompt": "🎰🌵☀️", "answer": "Las Vegas", "aliases": expand_aliases("Las Vegas", "Vegas")},
            {"prompt": "🏖️🎬🌴", "answer": "Los Angeles", "aliases": expand_aliases("Los Angeles", "LA")},
            {"prompt": "🗽🚕🍎", "answer": "New York", "aliases": expand_aliases("New York", "New York City", "NYC")},
            {"prompt": "💃🌞🐂", "answer": "Madrid", "aliases": expand_aliases("Madrid")},
            {"prompt": "🌊🐬⚽", "answer": "Barcelona", "aliases": expand_aliases("Barcelona")},
            {"prompt": "🏛️🫒🌞", "answer": "Athen", "aliases": expand_aliases("Athen", "Athens")},
            {"prompt": "🏰🍺⚓", "answer": "Köln", "aliases": expand_aliases("Köln", "Cologne")},
            {"prompt": "⚓🏟️🌧️", "answer": "Bremen", "aliases": expand_aliases("Bremen")},
            {"prompt": "🎻☕🏰", "answer": "Wien", "aliases": expand_aliases("Wien", "Vienna")},
            {"prompt": "📚🏰🧪", "answer": "Heidelberg", "aliases": expand_aliases("Heidelberg")},
            {"prompt": "🚢🌊🎶", "answer": "Kiel", "aliases": expand_aliases("Kiel")},
            {"prompt": "🌉🚴👑", "answer": "Kopenhagen", "aliases": expand_aliases("Kopenhagen", "Copenhagen")},
            {"prompt": "🏯🌸🎎", "answer": "Kyoto", "aliases": expand_aliases("Kyoto")},
            {"prompt": "🐉🏯🍜", "answer": "Peking", "aliases": expand_aliases("Peking", "Beijing")},
            {"prompt": "🌆🐉🚋", "answer": "Hongkong", "aliases": expand_aliases("Hongkong", "Hong Kong")},
            {"prompt": "🏜️🛢️🌆", "answer": "Dubai", "aliases": expand_aliases("Dubai")},
            {"prompt": "🐫🌴🕌", "answer": "Kairo", "aliases": expand_aliases("Kairo", "Cairo")},
            {"prompt": "🕌🌉🐈", "answer": "Ankara", "aliases": expand_aliases("Ankara")},
            {"prompt": "🏖️🍸🌇", "answer": "Miami", "aliases": expand_aliases("Miami")},
            {"prompt": "🎬🌉☀️", "answer": "Sydney", "aliases": expand_aliases("Sydney")},
            {"prompt": "🌁🌉🦀", "answer": "Seattle", "aliases": expand_aliases("Seattle")},
            {"prompt": "🏀🌵☀️", "answer": "Phoenix", "aliases": expand_aliases("Phoenix")},
            {"prompt": "🎷🎺🌊", "answer": "New Orleans", "aliases": expand_aliases("New Orleans")},
            {"prompt": "🛕🌶️🚕", "answer": "Mumbai", "aliases": expand_aliases("Mumbai", "Bombay")},
            {"prompt": "🐍🌊🍛", "answer": "Bangkok", "aliases": expand_aliases("Bangkok")},
            {"prompt": "🌉🐟🍁", "answer": "Vancouver", "aliases": expand_aliases("Vancouver")},
            {"prompt": "🏒❄️🏙️", "answer": "Toronto", "aliases": expand_aliases("Toronto")},
            {"prompt": "🧀🏰⌚", "answer": "Genf", "aliases": expand_aliases("Genf", "Geneva")},
            {"prompt": "🏛️🛵🌋", "answer": "Neapel", "aliases": expand_aliases("Neapel", "Naples")},
            {"prompt": "🏟️🛵🍕", "answer": "Mailand", "aliases": expand_aliases("Mailand", "Milan")},
            {"prompt": "🎭🚤🌊", "answer": "Valencia", "aliases": expand_aliases("Valencia")},
            {"prompt": "🥘💃🏖️", "answer": "Sevilla", "aliases": expand_aliases("Sevilla", "Seville")},
            {"prompt": "🍷🗼🦁", "answer": "Lyon", "aliases": expand_aliases("Lyon")},
            {"prompt": "🍟🧇🇧🇪", "answer": "Brüssel", "aliases": expand_aliases("Brüssel", "Brussels")},
            {"prompt": "🏰🍫🇧🇪", "answer": "Brügge", "aliases": expand_aliases("Brügge", "Bruges")},
            {"prompt": "☘️🍺🎻", "answer": "Dublin", "aliases": expand_aliases("Dublin")},
            {"prompt": "🎻🏰☕", "answer": "Prag", "aliases": expand_aliases("Prag", "Prague")},
            {"prompt": "🌉🏰🎻", "answer": "Budapest", "aliases": expand_aliases("Budapest")},
            {"prompt": "🏰🚋🍺", "answer": "Leipzig", "aliases": expand_aliases("Leipzig")},
            {"prompt": "⚙️🏭🎶", "answer": "Stuttgart", "aliases": expand_aliases("Stuttgart")},
            {"prompt": "🚢🌧️⚓", "answer": "Rostock", "aliases": expand_aliases("Rostock")},
            {"prompt": "🏛️🌊🍋", "answer": "Lissabon", "aliases": expand_aliases("Lissabon", "Lisbon")},
            {"prompt": "🌉🍷🏛️", "answer": "Porto", "aliases": expand_aliases("Porto")},
            {"prompt": "🏜️🌆🛍️", "answer": "Abu Dhabi", "aliases": expand_aliases("Abu Dhabi")},
            {"prompt": "🏛️🔥🌋", "answer": "Athen", "aliases": expand_aliases("Athen", "Athens")},
            {"prompt": "🍺⚽🌉", "answer": "Düsseldorf", "aliases": expand_aliases("Düsseldorf")},
            {"prompt": "🌭⚓🎶", "answer": "Leipzig", "aliases": expand_aliases("Leipzig")},
            {"prompt": "🏰🧠⚽", "answer": "Nürnberg", "aliases": expand_aliases("Nürnberg")},
            {"prompt": "🎓🚲🌧️", "answer": "Münster", "aliases": expand_aliases("Münster")},
            {"prompt": "⚓🐟🏟️", "answer": "Bremerhaven", "aliases": expand_aliases("Bremerhaven")},
            {"prompt": "🧪🏰🚶", "answer": "Jena", "aliases": expand_aliases("Jena")},
            {"prompt": "🌉🏛️🍝", "answer": "Florenz", "aliases": expand_aliases("Florenz", "Florence")},
            {"prompt": "🏰🛶🌊", "answer": "Stockholm", "aliases": expand_aliases("Stockholm")},
            {"prompt": "🧊🌊🎨", "answer": "Oslo", "aliases": expand_aliases("Oslo")},
            {"prompt": "☀️🏛️🏖️", "answer": "Alicante", "aliases": expand_aliases("Alicante")},
        ],
    },
    "länder": {
        "label": "Länder",
        "emoji": "🌍",
        "items": [
            {"prompt": "🍁🏒❄️", "answer": "Kanada", "aliases": expand_aliases("Kanada", "Canada")},
            {"prompt": "🦘🏄☀️", "answer": "Australien", "aliases": expand_aliases("Australien", "Australia")},
            {"prompt": "🎌🍣🗻", "answer": "Japan", "aliases": expand_aliases("Japan")},
            {"prompt": "🌮🌵☀️", "answer": "Mexiko", "aliases": expand_aliases("Mexiko", "Mexico")},
            {"prompt": "☕⚽🎭", "answer": "Brasilien", "aliases": expand_aliases("Brasilien", "Brazil")},
            {"prompt": "🧀⌚🏔️", "answer": "Schweiz", "aliases": expand_aliases("Schweiz", "Switzerland")},
            {"prompt": "🛵🍝🏛️", "answer": "Italien", "aliases": expand_aliases("Italien", "Italy")},
            {"prompt": "🍷🗼🥐", "answer": "Frankreich", "aliases": expand_aliases("Frankreich", "France")},
            {"prompt": "🥨🍺🏰", "answer": "Deutschland", "aliases": expand_aliases("Deutschland", "Germany")},
            {"prompt": "🐂💃🥘", "answer": "Spanien", "aliases": expand_aliases("Spanien", "Spain")},
            {"prompt": "🌷🚲🧀", "answer": "Niederlande", "aliases": expand_aliases("Niederlande", "Netherlands", "Holland")},
            {"prompt": "🧊🛋️🎮", "answer": "Schweden", "aliases": expand_aliases("Schweden", "Sweden")},
            {"prompt": "⛽🛢️❄️", "answer": "Norwegen", "aliases": expand_aliases("Norwegen", "Norway")},
            {"prompt": "🏜️🕌🐫", "answer": "Ägypten", "aliases": expand_aliases("Ägypten", "Egypt")},
            {"prompt": "🕌🧿🍵", "answer": "Türkei", "aliases": expand_aliases("Türkei", "Turkey")},
            {"prompt": "☘️🍺🎻", "answer": "Irland", "aliases": expand_aliases("Irland", "Ireland")},
            {"prompt": "❄️🧖🦌", "answer": "Finnland", "aliases": expand_aliases("Finnland", "Finland")},
            {"prompt": "🏰🎻☕", "answer": "Österreich", "aliases": expand_aliases("Österreich", "Austria")},
            {"prompt": "🍫🇪🇺🧇", "answer": "Belgien", "aliases": expand_aliases("Belgien", "Belgium")},
            {"prompt": "🐉🍜🥢", "answer": "China", "aliases": expand_aliases("China")},
            {"prompt": "🦅🗽🍔", "answer": "Vereinigte Staaten", "aliases": expand_aliases("Vereinigte Staaten", "USA", "United States", "Amerika", "US")},
            {"prompt": "🧊🌋♨️", "answer": "Island", "aliases": expand_aliases("Island", "Iceland")},
            {"prompt": "🥟🐼🏯", "answer": "Nepal", "aliases": expand_aliases("Nepal")},
            {"prompt": "🕌🐫🛢️", "answer": "Saudi-Arabien", "aliases": expand_aliases("Saudi-Arabien", "Saudi Arabia")},
            {"prompt": "🦙🏔️🌽", "answer": "Peru", "aliases": expand_aliases("Peru")},
            {"prompt": "🌶️⚽💃", "answer": "Argentinien", "aliases": expand_aliases("Argentinien", "Argentina")},
            {"prompt": "🧉🏔️☀️", "answer": "Chile", "aliases": expand_aliases("Chile")},
            {"prompt": "☕🦙🏞️", "answer": "Kolumbien", "aliases": expand_aliases("Kolumbien", "Colombia")},
            {"prompt": "🐑🏔️🥝", "answer": "Neuseeland", "aliases": expand_aliases("Neuseeland", "New Zealand")},
            {"prompt": "🛕🌶️🐘", "answer": "Indien", "aliases": expand_aliases("Indien", "India")},
            {"prompt": "🐘🌴🕌", "answer": "Thailand", "aliases": expand_aliases("Thailand")},
            {"prompt": "🐉🏮🍜", "answer": "Vietnam", "aliases": expand_aliases("Vietnam")},
            {"prompt": "🌴🐒☀️", "answer": "Indonesien", "aliases": expand_aliases("Indonesien", "Indonesia")},
            {"prompt": "☕🦁🌍", "answer": "Äthiopien", "aliases": expand_aliases("Äthiopien", "Ethiopia")},
            {"prompt": "🦁🏜️🌴", "answer": "Marokko", "aliases": expand_aliases("Marokko", "Morocco")},
            {"prompt": "🕌🌴🏜️", "answer": "Vereinigte Arabische Emirate", "aliases": expand_aliases("Vereinigte Arabische Emirate", "VAE", "UAE")},
            {"prompt": "🐻❄️🪆", "answer": "Russland", "aliases": expand_aliases("Russland", "Russia")},
            {"prompt": "🧄🌹⚽", "answer": "Bulgarien", "aliases": expand_aliases("Bulgarien", "Bulgaria")},
            {"prompt": "🏰🌶️🧛", "answer": "Rumänien", "aliases": expand_aliases("Rumänien", "Romania")},
            {"prompt": "🧂🏰🌊", "answer": "Kroatien", "aliases": expand_aliases("Kroatien", "Croatia")},
            {"prompt": "🏖️☀️⛵", "answer": "Griechenland", "aliases": expand_aliases("Griechenland", "Greece")},
            {"prompt": "🧄🏔️🌊", "answer": "Georgien", "aliases": expand_aliases("Georgien", "Georgia")},
            {"prompt": "🐫🏜️🕌", "answer": "Jordanien", "aliases": expand_aliases("Jordanien", "Jordan")},
            {"prompt": "🕌🏜️🌙", "answer": "Iran", "aliases": expand_aliases("Iran")},
            {"prompt": "🏔️☪️🧵", "answer": "Pakistan", "aliases": expand_aliases("Pakistan")},
            {"prompt": "🪷🐅🌊", "answer": "Bangladesch", "aliases": expand_aliases("Bangladesch", "Bangladesh")},
            {"prompt": "⚓🎨🌧️", "answer": "Dänemark", "aliases": expand_aliases("Dänemark", "Denmark")},
            {"prompt": "🏰🍺🎻", "answer": "Tschechien", "aliases": expand_aliases("Tschechien", "Czech Republic", "Czechia")},
            {"prompt": "🌾🏰🎻", "answer": "Ungarn", "aliases": expand_aliases("Ungarn", "Hungary")},
            {"prompt": "🧊🐻‍❄️❄️", "answer": "Grönland", "aliases": expand_aliases("Grönland", "Greenland")},
            {"prompt": "🦁🌍💎", "answer": "Südafrika", "aliases": expand_aliases("Südafrika", "South Africa")},
            {"prompt": "🦒🌍🥁", "answer": "Kenia", "aliases": expand_aliases("Kenia", "Kenya")},
            {"prompt": "🐧❄️🌋", "answer": "Argentinien", "aliases": expand_aliases("Argentinien", "Argentina")},
            {"prompt": "🌴🎶⚽", "answer": "Jamaika", "aliases": expand_aliases("Jamaika", "Jamaica")},
            {"prompt": "🧀🍫🏔️", "answer": "Schweiz", "aliases": expand_aliases("Schweiz", "Switzerland")},
            {"prompt": "🦙☀️🌽", "answer": "Bolivien", "aliases": expand_aliases("Bolivien", "Bolivia")},
            {"prompt": "🌋🌊🐟", "answer": "Philippinen", "aliases": expand_aliases("Philippinen", "Philippines")},
            {"prompt": "🏝️☀️🐠", "answer": "Malediven", "aliases": expand_aliases("Malediven", "Maldives")},
            {"prompt": "🕍🌊☀️", "answer": "Israel", "aliases": expand_aliases("Israel")},
            {"prompt": "🕌🌊🐪", "answer": "Oman", "aliases": expand_aliases("Oman")},
            {"prompt": "🛢️🏜️🌇", "answer": "Katar", "aliases": expand_aliases("Katar", "Qatar")},
        ],
    },
    "songs": {
        "label": "Songs",
        "emoji": "🎵",
        "items": [
            {"prompt": "🎂🎉", "answer": "Happy Birthday", "aliases": expand_aliases("Happy Birthday")},
            {"prompt": "🛣️🏠🌄", "answer": "Country Roads", "aliases": expand_aliases("Country Roads", "Take Me Home Country Roads")},
            {"prompt": "🔔🔔🔔", "answer": "Jingle Bells", "aliases": expand_aliases("Jingle Bells")},
            {"prompt": "👁️🐅", "answer": "Eye of the Tiger", "aliases": expand_aliases("Eye of the Tiger")},
            {"prompt": "❄️🙋", "answer": "Let It Go", "aliases": expand_aliases("Let It Go")},
            {"prompt": "👑🏆", "answer": "We Are the Champions", "aliases": expand_aliases("We Are the Champions")},
            {"prompt": "☂️☔", "answer": "Umbrella", "aliases": expand_aliases("Umbrella")},
            {"prompt": "💃👑", "answer": "Dancing Queen", "aliases": expand_aliases("Dancing Queen")},
            {"prompt": "🟡🚤", "answer": "Yellow Submarine", "aliases": expand_aliases("Yellow Submarine")},
            {"prompt": "🧍🕯️", "answer": "Stand by Me", "aliases": expand_aliases("Stand by Me")},
            {"prompt": "🪞👨", "answer": "Man in the Mirror", "aliases": expand_aliases("Man in the Mirror")},
            {"prompt": "🌧️🟣", "answer": "Purple Rain", "aliases": expand_aliases("Purple Rain")},
            {"prompt": "🔥🏨", "answer": "Hotel California", "aliases": expand_aliases("Hotel California")},
            {"prompt": "💔🏨", "answer": "Heartbreak Hotel", "aliases": expand_aliases("Heartbreak Hotel")},
            {"prompt": "🚶🌕", "answer": "Walking on the Moon", "aliases": expand_aliases("Walking on the Moon")},
            {"prompt": "🧨🛣️", "answer": "Highway to Hell", "aliases": expand_aliases("Highway to Hell")},
            {"prompt": "🌊❤️", "answer": "My Heart Will Go On", "aliases": expand_aliases("My Heart Will Go On")},
            {"prompt": "👶🦈", "answer": "Baby Shark", "aliases": expand_aliases("Baby Shark")},
            {"prompt": "🌧️🧔", "answer": "It's Raining Men", "aliases": expand_aliases("It's Raining Men", "Its Raining Men")},
            {"prompt": "🚴‍♀️🕺", "answer": "I Want to Break Free", "aliases": expand_aliases("I Want to Break Free")},
            {"prompt": "🕺🌃", "answer": "Stayin' Alive", "aliases": expand_aliases("Stayin' Alive", "Stayin Alive", "Staying Alive")},
            {"prompt": "👑🔥", "answer": "Kings and Queens", "aliases": expand_aliases("Kings and Queens")},
            {"prompt": "🧑‍🚀🌌", "answer": "Space Oddity", "aliases": expand_aliases("Space Oddity")},
            {"prompt": "🎤🌊⭐", "answer": "Shallow", "aliases": expand_aliases("Shallow")},
            {"prompt": "🌍🎶💚", "answer": "Earth Song", "aliases": expand_aliases("Earth Song")},
            {"prompt": "💣🛤️", "answer": "TNT", "aliases": expand_aliases("TNT")},
            {"prompt": "🛣️😈", "answer": "Road to Hell", "aliases": expand_aliases("Road to Hell")},
            {"prompt": "🌙💃✨", "answer": "Dancing in the Moonlight", "aliases": expand_aliases("Dancing in the Moonlight")},
            {"prompt": "☀️🌻", "answer": "Here Comes the Sun", "aliases": expand_aliases("Here Comes the Sun")},
            {"prompt": "💔👩", "answer": "Someone Like You", "aliases": expand_aliases("Someone Like You")},
            {"prompt": "🔥🌧️", "answer": "Set Fire to the Rain", "aliases": expand_aliases("Set Fire to the Rain")},
            {"prompt": "🌧️📅", "answer": "November Rain", "aliases": expand_aliases("November Rain")},
            {"prompt": "🌈☀️", "answer": "Somewhere Over the Rainbow", "aliases": expand_aliases("Somewhere Over the Rainbow")},
            {"prompt": "👗💄👧", "answer": "Material Girl", "aliases": expand_aliases("Material Girl")},
            {"prompt": "🐒💃🎤", "answer": "Dance Monkey", "aliases": expand_aliases("Dance Monkey")},
            {"prompt": "🎉🇺🇸🪩", "answer": "Party in the U.S.A.", "aliases": expand_aliases("Party in the U.S.A.", "Party in the USA")},
            {"prompt": "👧🔥", "answer": "Girl on Fire", "aliases": expand_aliases("Girl on Fire")},
            {"prompt": "🌌⭐✨", "answer": "A Sky Full of Stars", "aliases": expand_aliases("A Sky Full of Stars")},
            {"prompt": "⚡⚡⚡", "answer": "Thunder", "aliases": expand_aliases("Thunder")},
            {"prompt": "🧊👑", "answer": "Cold as Ice", "aliases": expand_aliases("Cold as Ice")},
            {"prompt": "🍬💋", "answer": "Sugar", "aliases": expand_aliases("Sugar")},
            {"prompt": "🏃💨💔", "answer": "Runaway", "aliases": expand_aliases("Runaway")},
            {"prompt": "🕶️✨🌃", "answer": "Blinding Lights", "aliases": expand_aliases("Blinding Lights")},
            {"prompt": "🌊👀", "answer": "Ocean Eyes", "aliases": expand_aliases("Ocean Eyes")},
            {"prompt": "🚗📄💔", "answer": "Drivers License", "aliases": expand_aliases("Drivers License", "Driver's License")},
            {"prompt": "💀🕺🌕", "answer": "Thriller", "aliases": expand_aliases("Thriller")},
            {"prompt": "💋🌹", "answer": "Kiss from a Rose", "aliases": expand_aliases("Kiss from a Rose")},
            {"prompt": "👼✨", "answer": "Angels", "aliases": expand_aliases("Angels")},
            {"prompt": "🚀👨", "answer": "Rocket Man", "aliases": expand_aliases("Rocket Man")},
            {"prompt": "🔥🪩", "answer": "Disco Inferno", "aliases": expand_aliases("Disco Inferno")},
            {"prompt": "🧊🧊👶", "answer": "Ice Ice Baby", "aliases": expand_aliases("Ice Ice Baby")},
            {"prompt": "🌊🌊🌊", "answer": "Rolling in the Deep", "aliases": expand_aliases("Rolling in the Deep")},
            {"prompt": "🌻☀️", "answer": "Sunflower", "aliases": expand_aliases("Sunflower")},
            {"prompt": "💃🌧️", "answer": "Rain on Me", "aliases": expand_aliases("Rain on Me")},
            {"prompt": "🪞💃", "answer": "Dancing with Myself", "aliases": expand_aliases("Dancing with Myself")},
            {"prompt": "🧠💭❤️", "answer": "Dreams", "aliases": expand_aliases("Dreams")},
            {"prompt": "🛫🌍", "answer": "Leaving on a Jet Plane", "aliases": expand_aliases("Leaving on a Jet Plane")},
            {"prompt": "🫶👋", "answer": "Hello", "aliases": expand_aliases("Hello")},
            {"prompt": "👋🌆", "answer": "Goodbye Yellow Brick Road", "aliases": expand_aliases("Goodbye Yellow Brick Road")},
            {"prompt": "🕯️🌬️", "answer": "Candle in the Wind", "aliases": expand_aliases("Candle in the Wind")},
            {"prompt": "❤️🧊", "answer": "Cold Heart", "aliases": expand_aliases("Cold Heart")},
            {"prompt": "🚶‍♂️☀️", "answer": "Walking on Sunshine", "aliases": expand_aliases("Walking on Sunshine")},
        ],
    },
}

EMOJI_QUIZ_CATEGORY_ORDER = [
    "städte",
    "länder",
    "filme",
    "serien",
    "essen",
    "sprichwörter",
    "songs",
    "flaggen",
    "user",
    "spiele",
    "märchen",
]


def _legacy_ascii_key(value: str) -> str:
    result: list[str] = []
    for char in str(value or "").casefold():
        if char == "ä":
            result.extend(("a", "e"))
            continue
        if char == "ö":
            result.extend(("o", "e"))
            continue
        if char == "ü":
            result.extend(("u", "e"))
            continue
        if char == "ß":
            result.extend(("s", "s"))
            continue
        result.append(char)
    return "".join(result)


EMOJI_QUIZ_CATEGORY_ALIASES: dict[str, str] = {}
for category_key in EMOJI_QUIZ_CATEGORY_ORDER:
    payload = EMOJI_QUIZ_BANK.get(category_key) or {}
    label = str(payload.get("label") or category_key).casefold()
    for variant in {str(category_key).casefold(), label}:
        if not variant:
            continue
        EMOJI_QUIZ_CATEGORY_ALIASES[variant] = category_key
        fallback = _legacy_ascii_key(variant)
        if fallback and fallback != variant:
            EMOJI_QUIZ_CATEGORY_ALIASES[fallback] = category_key
