
"""Fifty synthetic, manually labeled vehicle customer statements."""

FIELDS = (
    "max_budget",
    "make",
    "model",
    "min_year",
    "max_mileage_km",
    "body_style",
    "drivetrain",
)


def case(number, text, *, explicit=None, ambiguous=(), preference=()):
    explicit = dict(explicit or {})
    ambiguous = set(ambiguous)
    preference = set(preference)

    all_labeled = set(explicit) | ambiguous | preference

    if not all_labeled <= set(FIELDS):
        raise ValueError(f"Unknown field in case {number}")

    if (
        (set(explicit) & ambiguous)
        or (set(explicit) & preference)
        or (ambiguous & preference)
    ):
        raise ValueError(f"Conflicting labels in case {number}")

    if any(value is None for value in explicit.values()):
        raise ValueError(f"Explicit field is null in case {number}")

    return {
        "id": f"C{number:02d}",
        "text": text,
        "requirements": {
            field: explicit.get(field)
            for field in FIELDS
        },
        "field_states": {
            field: (
                "explicit" if field in explicit else
                "ambiguous" if field in ambiguous else
                "preference" if field in preference else
                "missing"
            )
            for field in FIELDS
        },
    }


CASES = [
    case(
        1,
        "I need a Toyota SUV under 30000 CAD, 2020 or newer, with AWD.",
        explicit={
            "max_budget": 30000,
            "make": "Toyota",
            "min_year": 2020,
            "body_style": "SUV",
            "drivetrain": "AWD",
        },
    ),
    case(
        2,
        "Looking for a Honda Civic, 2019 or newer, at most 90,000 km.",
        explicit={
            "make": "Honda",
            "model": "Civic",
            "min_year": 2019,
            "max_mileage_km": 90000,
        },
    ),
    case(
        3,
        "Cash budget is no more than $18,500 CAD. I want a sedan.",
        explicit={"max_budget": 18500, "body_style": "Sedan"},
    ),
    case(
        4,
        "Find me an AWD SUV with mileage below 70,000 km.",
        explicit={
            "drivetrain": "AWD",
            "body_style": "SUV",
            "max_mileage_km": 70000,
        },
    ),
    case(
        5,
        "A Ford F-150 from 2018 or later, max cash price $32,000 CAD.",
        explicit={
            "make": "Ford",
            "model": "F-150",
            "min_year": 2018,
            "max_budget": 32000,
        },
    ),
    case(
        6,
        "I need a hatchback under $16,000 CAD cash, FWD only.",
        explicit={
            "body_style": "Hatchback",
            "max_budget": 16000,
            "drivetrain": "FWD",
        },
    ),
    case(
        7,
        "Need a 2022 or newer Mazda CX-5.",
        explicit={
            "min_year": 2022,
            "make": "Mazda",
            "model": "CX-5",
        },
    ),
    case(
        8,
        "The most I can spend in cash is 25 grand CAD; under 100k km.",
        explicit={
            "max_budget": 25000,
            "max_mileage_km": 100000,
        },
    ),
    case(
        9,
        "Please show me a minivan with less than 120,000 km.",
        explicit={
            "body_style": "Minivan",
            "max_mileage_km": 120000,
        },
    ),
    case(
        10,
        "Only Toyota, and I need a Corolla.",
        explicit={"make": "Toyota", "model": "Corolla"},
    ),
    case(
        11,
        "I need rear-wheel drive, not AWD.",
        explicit={"drivetrain": "RWD"},
    ),
    case(
        12,
        "I'm shopping for a Chevrolet Silverado 1500, 2021 or newer.",
        explicit={
            "make": "Chevrolet",
            "model": "Silverado 1500",
            "min_year": 2021,
        },
    ),
    case(
        13,
        "Need a Subaru Impreza, $22,000 CAD maximum cash price.",
        explicit={
            "make": "Subaru",
            "model": "Impreza",
            "max_budget": 22000,
        },
    ),
    case(
        14,
        "An SUV with 4WD, 2017 or newer, up to 140000 km.",
        explicit={
            "body_style": "SUV",
            "drivetrain": "4WD",
            "min_year": 2017,
            "max_mileage_km": 140000,
        },
    ),
    case(
        15,
        "I need a Hyundai Elantra, 2020 or newer, for $19,000 CAD cash or less.",
        explicit={
            "make": "Hyundai",
            "model": "Elantra",
            "min_year": 2020,
            "max_budget": 19000,
        },
    ),
    case(
        16,
        "My price ceiling is 28000 CAD cash and 80000 km maximum.",
        explicit={
            "max_budget": 28000,
            "max_mileage_km": 80000,
        },
    ),
    case(
        17,
        "Looking for a sedan, front-wheel drive only.",
        explicit={
            "body_style": "Sedan",
            "drivetrain": "FWD",
        },
    ),
    case(
        18,
        "I must have a 2023 or newer car.",
        explicit={"min_year": 2023},
    ),
    case(
        19,
        "The car must be a Honda.",
        explicit={"make": "Honda"},
    ),
    case(
        20,
        "I need a pickup truck with a max of 150,000 km.",
        explicit={
            "body_style": "Truck",
            "max_mileage_km": 150000,
        },
    ),
    case(
        21,
        "I need a Kia Sportage with AWD and a max $26,000 CAD cash price.",
        explicit={
            "make": "Kia",
            "model": "Sportage",
            "drivetrain": "AWD",
            "max_budget": 26000,
        },
    ),
    case(
        22,
        "Only a Volkswagen Golf, at most 50,000 km.",
        explicit={
            "make": "Volkswagen",
            "model": "Golf",
            "max_mileage_km": 50000,
        },
    ),
    case(
        23,
        "Budget is $14,000 CAD cash max; I need a 2016 or newer hatchback.",
        explicit={
            "max_budget": 14000,
            "min_year": 2016,
            "body_style": "Hatchback",
        },
    ),
    case(
        24,
        "Need a Nissan Rogue with fewer than 110,000 km, preferably AWD.",
        explicit={
            "make": "Nissan",
            "model": "Rogue",
            "max_mileage_km": 110000,
        },
        preference=("drivetrain",),
    ),
    case(
        25,
        "A Lexus RX with AWD is required. Cash max $40,000 CAD.",
        explicit={
            "make": "Lexus",
            "model": "RX",
            "drivetrain": "AWD",
            "max_budget": 40000,
        },
    ),
    case(
        26,
        "I prefer Toyota but I'm open to other brands. I need an SUV.",
        explicit={"body_style": "SUV"},
        preference=("make",),
    ),
    case(
        27,
        "Something good for winter, maybe around 25 grand.",
        ambiguous=("max_budget", "drivetrain"),
    ),
    case(
        28,
        "I'm considering AWD but it's not a requirement. Need an SUV.",
        explicit={"body_style": "SUV"},
        preference=("drivetrain",),
    ),
    case(
        29,
        "I'd love a 2020 model if possible, but older is fine. Must be a sedan.",
        explicit={"body_style": "Sedan"},
        preference=("min_year",),
    ),
    case(
        30,
        "A Honda would be nice; any make is okay, under 22000 CAD cash.",
        explicit={"max_budget": 22000},
        preference=("make",),
    ),
    case(
        31,
        "Around 100,000 km would be nice; not a strict limit.",
        preference=("max_mileage_km",),
    ),
    case(
        32,
        "I'm looking to spend roughly $30,000 CAD cash, flexible either way.",
        ambiguous=("max_budget",),
    ),
    case(
        33,
        "I need a car under 100k on the odometer.",
        ambiguous=("max_mileage_km",),
    ),
    case(
        34,
        "Monthly payments under $450, no cash budget stated. I need AWD.",
        explicit={"drivetrain": "AWD"},
    ),
    case(
        35,
        "I can put down $5,000 and want an SUV.",
        explicit={"body_style": "SUV"},
    ),
    case(
        36,
        "I like the RAV4, but a CR-V works too. Need an SUV.",
        explicit={"body_style": "SUV"},
        preference=("model",),
    ),
    case(
        37,
        "I want a white car and good fuel economy, ideally a sedan.",
        preference=("body_style",),
    ),
    case(
        38,
        "Don't care about drivetrain, but SUV is a must.",
        explicit={"body_style": "SUV"},
    ),
    case(
        39,
        "I think a 2020 or 2021 would be great, but 2018 is okay.",
        preference=("min_year",),
    ),
    case(
        40,
        "It has to be a Toyota, but model doesn't matter.",
        explicit={"make": "Toyota"},
    ),
    case(
        41,
        "An SUV for winter — maybe AWD, haven't decided.",
        explicit={"body_style": "SUV"},
        ambiguous=("drivetrain",),
    ),
    case(
        42,
        "Need less than 60,000 miles.",
        ambiguous=("max_mileage_km",),
    ),
    case(
        43,
        "I haven't decided whether my cash cap is $20,000 or $30,000 CAD.",
        ambiguous=("max_budget",),
    ),
    case(
        44,
        "Maybe a Honda or Toyota, but any brand is fine.",
        preference=("make",),
    ),
    case(
        45,
        "Not sure whether I want a sedan or an SUV.",
        ambiguous=("body_style",),
    ),
    case(
        46,
        "2020 or newer, but my partner said 2016 or newer; haven't decided.",
        ambiguous=("min_year",),
    ),
    case(
        47,
        "All-wheel drive is a must, with cash budget at most 27k CAD.",
        explicit={
            "drivetrain": "AWD",
            "max_budget": 27000,
        },
    ),
    case(
        48,
        "我只考虑丰田 SUV，现金预算不超过 3 万加元，2020 年或更新。",
        explicit={
            "make": "Toyota",
            "body_style": "SUV",
            "max_budget": 30000,
            "min_year": 2020,
        },
    ),
    case(
        49,
        "冬天开车要稳一点，最好是四驱，但不是必须。",
        preference=("drivetrain",),
    ),
    case(
        50,
        "Need a Mazda sedan, 里程不要超过 8 万公里, and cash budget max 24000 CAD.",
        explicit={
            "make": "Mazda",
            "body_style": "Sedan",
            "max_mileage_km": 80000,
            "max_budget": 24000,
        },
    ),
]


assert len(CASES) == 50
assert len({row["id"] for row in CASES}) == 50
