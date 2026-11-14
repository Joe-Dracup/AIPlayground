from typing import Literal

Category = Literal["cafe", "pub", "restaurant", "park", "station"]

Tag = Literal[
    "wifi",
    "dog_friendly",
    "outdoor_seating",
    "real_ale",
    "vegan_options",
    "step_free",
    "playground",
]

TAG_DESCRIPTIONS: dict[Tag, str] = {
    "wifi": "free wifi for customers",
    "dog_friendly": "dogs are welcome",
    "outdoor_seating": "has seating outside",
    "real_ale": "serves cask (real) ale",
    "vegan_options": "has vegan food on the menu",
    "step_free": "can be reached without steps, e.g. by wheelchair or pushchair",
    "playground": "has a children's play area",
}
