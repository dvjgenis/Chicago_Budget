"""Optional official OBM glance totals, keyed by budget year.

When a new year is published, add a block here if you want the glance page
to match the Budget Overview (net of transfers). If you skip this, the
glance page is built from the ordinance file alone.
"""

from __future__ import annotations

# Dollars. Leave a year out to use ordinance-derived totals.
PUBLISHED: dict[str, dict] = {
    "2026": {
        "net": 16_554_600_000,
        "transfers": 1_796_196_626,
        "population": 2_746_388,
        "overview_url": (
            "https://www.chicago.gov/content/dam/city/depts/obm/supp_info/"
            "2026Budget/2026%20Budget%20Overview.pdf"
        ),
        "funds": {
            "corporate": 6_060_400_000,
            "special": 1_273_400_000,
            "pension": 2_760_300_000,
            "debt": 552_100_000,
            "enterprise": 3_865_400_000,
            "grant": 3_839_100_000,
        },
        "services": {
            "safety": 3_167_650_308,
            "infra": 4_625_059_101,
            "gfr": 8_053_719_737,
            "admin": 868_560_424,
            "community": 1_066_603_931,
            "develop": 352_488_438,
            "reg": 151_050_526,
            "leg": 65_635_250,
        },
        "prior": {
            "funds": {
                "corporate": 5_788_000_000,
                "special": 1_179_800_000,
                "pension": 2_906_500_000,
                "debt": 539_700_000,
                "enterprise": 3_710_700_000,
                "grant": 4_717_400_000,
            },
            "services": {
                "safety": 3_099_857_900,
                "infra": 3_952_675_728,
                "gfr": 8_065_669_719,
                "admin": 916_618_411,
                "community": 1_370_337_170,
                "develop": 442_553_586,
                "reg": 114_869_746,
                "leg": 65_313_720,
            },
        },
        "departments": {
            "safety": [
                ["Chicago Police Department", 2_114_745_912],
                ["Chicago Fire Department", 796_952_169],
                ["Office of Public Safety Administration", 135_710_283],
                ["Office of Emergency Management and Communications", 99_935_952],
                ["Civilian Office of Police Accountability", 15_781_027],
                ["Community Commission for Public Safety and Accountability", 4_026_765],
                ["Chicago Police Board", 498_200],
            ],
            "infra": [
                ["Chicago Department of Transportation", 1_836_518_885],
                ["Chicago Department of Aviation", 1_666_194_101],
                ["Department of Water Management", 774_039_573],
                ["Department of Streets and Sanitation", 348_306_542],
            ],
            "gfr": [
                ["Pension contributions", 2_760_267_271],
                ["Debt booked citywide", 1_966_323_405],
                ["Employee benefits", 1_077_168_533],
                ["Other citywide costs", 2_249_960_528],
            ],
            "admin": [
                ["Department of Fleet and Facility Management", 500_103_234],
                ["Department of Finance", 128_162_674],
                ["Department of Technology and Innovation", 76_383_040],
                ["Department of Law", 47_954_637],
                ["Office of Budget and Management", 38_560_702],
                ["Office of the Mayor", 20_354_716],
                ["Office of City Clerk", 15_267_028],
                ["Department of Procurement Services", 13_923_365],
                ["Department of Human Resources", 12_957_553],
                ["Department of Administrative Hearings", 8_389_224],
                ["City Treasurer's Office", 6_504_251],
            ],
            "community": [
                ["Department of Family and Support Services", 632_560_045],
                ["Chicago Department of Public Health", 314_870_217],
                ["Chicago Public Library", 107_229_310],
                ["Mayor's Office for People with Disabilities", 9_179_159],
                ["Chicago Commission on Human Relations", 2_765_200],
            ],
            "develop": [
                ["Department of Housing", 169_252_026],
                ["Department of Planning and Development", 121_232_815],
                ["Department of Cultural Affairs and Special Events", 62_003_597],
            ],
            "reg": [
                ["Department of Environment", 52_421_063],
                ["Department of Buildings", 39_368_782],
                ["Department of Business Affairs and Consumer Protection", 36_187_606],
                ["Office of Inspector General", 14_297_022],
                ["Chicago Animal Care and Control", 7_640_468],
                ["Board of Ethics", 925_597],
                ["License Appeal Commission", 209_988],
            ],
            "leg": [
                ["City Council", 37_767_846],
                ["Board of Election Commissioners", 27_867_404],
            ],
        },
        "gfr_explore": False,
    }
}


def published_for(year: str) -> dict | None:
    return PUBLISHED.get(str(year))
