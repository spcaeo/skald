"""Country codes, as a reader would want to see them: a flag and a short code.

The log carries an ISO 3166-1 alpha-2 code (from a CDN header or a GeoIP
database). History stores the code; this only decides how it is shown:
the flag and the ISO 3166-1 alpha-3 code ("🇺🇸 USA", owner 2026-10-18), with
the full name beside it where the medium has room for a tooltip (name()).
"Unknown" (stored) is a visit whose country the log did not record - shown
as "Not recorded" (labels.py), never guessed.
"""
from __future__ import annotations

from .labels import shown

UNKNOWN = "Unknown"

_NAMES = """
AD Andorra|AE United Arab Emirates|AF Afghanistan|AG Antigua and Barbuda|AI Anguilla
AL Albania|AM Armenia|AO Angola|AQ Antarctica|AR Argentina|AS American Samoa|AT Austria
AU Australia|AW Aruba|AX Aland Islands|AZ Azerbaijan|BA Bosnia and Herzegovina
BB Barbados|BD Bangladesh|BE Belgium|BF Burkina Faso|BG Bulgaria|BH Bahrain|BI Burundi
BJ Benin|BL Saint Barthelemy|BM Bermuda|BN Brunei|BO Bolivia|BQ Caribbean Netherlands
BR Brazil|BS Bahamas|BT Bhutan|BW Botswana|BY Belarus|BZ Belize|CA Canada
CC Cocos Islands|CD DR Congo|CF Central African Republic|CG Congo|CH Switzerland
CI Cote d'Ivoire|CK Cook Islands|CL Chile|CM Cameroon|CN China|CO Colombia|CR Costa Rica
CU Cuba|CV Cape Verde|CW Curacao|CX Christmas Island|CY Cyprus|CZ Czechia|DE Germany
DJ Djibouti|DK Denmark|DM Dominica|DO Dominican Republic|DZ Algeria|EC Ecuador|EE Estonia
EG Egypt|EH Western Sahara|ER Eritrea|ES Spain|ET Ethiopia|FI Finland|FJ Fiji
FK Falkland Islands|FM Micronesia|FO Faroe Islands|FR France|GA Gabon|GB United Kingdom
GD Grenada|GE Georgia|GF French Guiana|GG Guernsey|GH Ghana|GI Gibraltar|GL Greenland
GM Gambia|GN Guinea|GP Guadeloupe|GQ Equatorial Guinea|GR Greece|GT Guatemala|GU Guam
GW Guinea-Bissau|GY Guyana|HK Hong Kong|HN Honduras|HR Croatia|HT Haiti|HU Hungary
ID Indonesia|IE Ireland|IL Israel|IM Isle of Man|IN India|IQ Iraq|IR Iran|IS Iceland
IT Italy|JE Jersey|JM Jamaica|JO Jordan|JP Japan|KE Kenya|KG Kyrgyzstan|KH Cambodia
KI Kiribati|KM Comoros|KN Saint Kitts and Nevis|KP North Korea|KR South Korea|KW Kuwait
KY Cayman Islands|KZ Kazakhstan|LA Laos|LB Lebanon|LC Saint Lucia|LI Liechtenstein
LK Sri Lanka|LR Liberia|LS Lesotho|LT Lithuania|LU Luxembourg|LV Latvia|LY Libya
MA Morocco|MC Monaco|MD Moldova|ME Montenegro|MF Saint Martin|MG Madagascar
MH Marshall Islands|MK North Macedonia|ML Mali|MM Myanmar|MN Mongolia|MO Macao
MP Northern Mariana Islands|MQ Martinique|MR Mauritania|MS Montserrat|MT Malta
MU Mauritius|MV Maldives|MW Malawi|MX Mexico|MY Malaysia|MZ Mozambique|NA Namibia
NC New Caledonia|NE Niger|NF Norfolk Island|NG Nigeria|NI Nicaragua|NL Netherlands
NO Norway|NP Nepal|NR Nauru|NU Niue|NZ New Zealand|OM Oman|PA Panama|PE Peru
PF French Polynesia|PG Papua New Guinea|PH Philippines|PK Pakistan|PL Poland
PM Saint Pierre and Miquelon|PN Pitcairn|PR Puerto Rico|PS Palestine|PT Portugal|PW Palau
PY Paraguay|QA Qatar|RE Reunion|RO Romania|RS Serbia|RU Russia|RW Rwanda|SA Saudi Arabia
SB Solomon Islands|SC Seychelles|SD Sudan|SE Sweden|SG Singapore|SH Saint Helena
SI Slovenia|SK Slovakia|SL Sierra Leone|SM San Marino|SN Senegal|SO Somalia|SR Suriname
SS South Sudan|ST Sao Tome and Principe|SV El Salvador|SX Sint Maarten|SY Syria
SZ Eswatini|TC Turks and Caicos|TD Chad|TG Togo|TH Thailand|TJ Tajikistan|TK Tokelau
TL Timor-Leste|TM Turkmenistan|TN Tunisia|TO Tonga|TR Turkey|TT Trinidad and Tobago
TV Tuvalu|TW Taiwan|TZ Tanzania|UA Ukraine|UG Uganda|US United States|UY Uruguay
UZ Uzbekistan|VA Vatican City|VC Saint Vincent and the Grenadines|VE Venezuela
VG British Virgin Islands|VI US Virgin Islands|VN Vietnam|VU Vanuatu
WF Wallis and Futuna|WS Samoa|XK Kosovo|YE Yemen|YT Mayotte|ZA South Africa|ZM Zambia
ZW Zimbabwe|EU European Union|AP Asia/Pacific|BV Bouvet Island
GS South Georgia and the South Sandwich Islands|HM Heard and McDonald Islands
IO British Indian Ocean Territory|SJ Svalbard and Jan Mayen|TF French Southern Territories
UM US Outlying Islands
"""

NAMES = {entry[:2]: entry[3:] for row in _NAMES.split("\n") for entry in
         (part.strip() for part in row.split("|")) if len(entry) > 3}

# ISO 3166-1 alpha-2 -> alpha-3, every assigned code (and XK Kosovo's common XKX).
# The twin is webapp/js/countries.js; tests/test_country_codes.py keeps them equal.
# EU and AP are not countries: they have no alpha-3 and are shown as they are.
_ALPHA3 = """
AD AND|AE ARE|AF AFG|AG ATG|AI AIA|AL ALB|AM ARM|AO AGO|AQ ATA|AR ARG|AS ASM|AT AUT
AU AUS|AW ABW|AX ALA|AZ AZE|BA BIH|BB BRB|BD BGD|BE BEL|BF BFA|BG BGR|BH BHR|BI BDI
BJ BEN|BL BLM|BM BMU|BN BRN|BO BOL|BQ BES|BR BRA|BS BHS|BT BTN|BV BVT|BW BWA|BY BLR
BZ BLZ|CA CAN|CC CCK|CD COD|CF CAF|CG COG|CH CHE|CI CIV|CK COK|CL CHL|CM CMR|CN CHN
CO COL|CR CRI|CU CUB|CV CPV|CW CUW|CX CXR|CY CYP|CZ CZE|DE DEU|DJ DJI|DK DNK|DM DMA
DO DOM|DZ DZA|EC ECU|EE EST|EG EGY|EH ESH|ER ERI|ES ESP|ET ETH|FI FIN|FJ FJI|FK FLK
FM FSM|FO FRO|FR FRA|GA GAB|GB GBR|GD GRD|GE GEO|GF GUF|GG GGY|GH GHA|GI GIB|GL GRL
GM GMB|GN GIN|GP GLP|GQ GNQ|GR GRC|GS SGS|GT GTM|GU GUM|GW GNB|GY GUY|HK HKG|HM HMD
HN HND|HR HRV|HT HTI|HU HUN|ID IDN|IE IRL|IL ISR|IM IMN|IN IND|IO IOT|IQ IRQ|IR IRN
IS ISL|IT ITA|JE JEY|JM JAM|JO JOR|JP JPN|KE KEN|KG KGZ|KH KHM|KI KIR|KM COM|KN KNA
KP PRK|KR KOR|KW KWT|KY CYM|KZ KAZ|LA LAO|LB LBN|LC LCA|LI LIE|LK LKA|LR LBR|LS LSO
LT LTU|LU LUX|LV LVA|LY LBY|MA MAR|MC MCO|MD MDA|ME MNE|MF MAF|MG MDG|MH MHL|MK MKD
ML MLI|MM MMR|MN MNG|MO MAC|MP MNP|MQ MTQ|MR MRT|MS MSR|MT MLT|MU MUS|MV MDV|MW MWI
MX MEX|MY MYS|MZ MOZ|NA NAM|NC NCL|NE NER|NF NFK|NG NGA|NI NIC|NL NLD|NO NOR|NP NPL
NR NRU|NU NIU|NZ NZL|OM OMN|PA PAN|PE PER|PF PYF|PG PNG|PH PHL|PK PAK|PL POL|PM SPM
PN PCN|PR PRI|PS PSE|PT PRT|PW PLW|PY PRY|QA QAT|RE REU|RO ROU|RS SRB|RU RUS|RW RWA
SA SAU|SB SLB|SC SYC|SD SDN|SE SWE|SG SGP|SH SHN|SI SVN|SJ SJM|SK SVK|SL SLE|SM SMR
SN SEN|SO SOM|SR SUR|SS SSD|ST STP|SV SLV|SX SXM|SY SYR|SZ SWZ|TC TCA|TD TCD|TF ATF
TG TGO|TH THA|TJ TJK|TK TKL|TL TLS|TM TKM|TN TUN|TO TON|TR TUR|TT TTO|TV TUV|TW TWN
TZ TZA|UA UKR|UG UGA|UM UMI|US USA|UY URY|UZ UZB|VA VAT|VC VCT|VE VEN|VG VGB|VI VIR
VN VNM|VU VUT|WF WLF|WS WSM|XK XKX|YE YEM|YT MYT|ZA ZAF|ZM ZMB|ZW ZWE
"""

ALPHA3 = {entry[:2]: entry[3:] for row in _ALPHA3.split("\n") for entry in
          (part.strip() for part in row.split("|")) if len(entry) == 6}


def flag(code: str) -> str:
    """The flag emoji for a two-letter code: two regional indicator letters.
    Empty for anything that is not two ASCII letters, and for the codes ISO
    keeps for private use (AA, QM-QZ, XA-XZ but XK Kosovo, ZZ): "XX" or "ZZ"
    means unknown, not a place. AP (an old "Asia/Pacific") has no flag."""
    code = (code or "").upper()
    if len(code) != 2 or not code.isascii() or not code.isalpha():
        return ""
    if (code in ("AA", "AP", "ZZ") or (code[0] == "Q" and code[1] >= "M")
            or (code[0] == "X" and code != "XK")):
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)


def code3(code: str) -> str:
    """'USA' for 'US'; a code without an alpha-3 (EU, AP) as it is."""
    code = (code or "").upper()
    return ALPHA3.get(code, code)


def name(code: str) -> str:
    """The full name ('United States'), for a tooltip, a search or a CSV;
    'Not recorded' for a country the log did not record."""
    if not code or code == UNKNOWN:
        return shown(UNKNOWN)
    if len(code) != 2:
        return code
    return NAMES.get(code.upper(), code.upper())


def label(code: str) -> str:
    """'🇨🇦 CAN', 'Not recorded' (stored as Unknown), or the code itself
    with its flag if it has no alpha-3. The full name is name(code)."""
    if not code or code == UNKNOWN:
        return shown(UNKNOWN)
    if len(code) != 2:
        return code            # a folded "(all others)" row, say
    code = code.upper()
    return f"{flag(code)} {code3(code)}".strip()


# Continents, from the country (ISO 3166-1 alpha-2): the compare report's
# "regions". The address database is country-level, so nothing finer.
_CONTINENTS = {
    "Africa": "DZ AO BJ BW BF BI CV CM CF TD KM CG CD CI DJ EG GQ ER SZ ET GA GM GH GN GW KE LS LR "
              "LY MG MW ML MR MU YT MA MZ NA NE NG RE RW SH ST SN SC SL SO ZA SS SD TZ TG TN UG EH "
              "ZM ZW",
    "Antarctica": "AQ BV GS HM TF",
    "Asia": "AF AM AZ BH BD BT BN KH CN CY GE HK IN ID IR IQ IL JP JO KZ KW KG LA LB MO MY MV MN "
            "MM NP KP OM PK PS PH QA SA SG KR LK SY TW TJ TH TL TR TM AE UZ VN YE IO CC CX",
    "Europe": "AX AL AD AT BY BE BA BG HR CZ DK EE FO FI FR DE GI GR GG HU IS IE IM IT JE XK LV "
              "LI LT LU MT MD MC ME NL MK NO PL PT RO RU SM RS SK SI ES SJ SE CH UA GB VA",
    "North America": "AI AG AW BS BB BZ BM BQ VG CA KY CR CU CW DM DO SV GL GD GP GT HT HN JM MQ "
                     "MX MS NI PA PR BL KN LC MF PM VC SX TT TC US VI UM",
    "Oceania": "AS AU CK FJ PF GU KI MH FM NR NC NZ NU NF MP PW PG PN WS SB TK TO TV VU WF",
    "South America": "AR BO BR CL CO EC FK GF GY PY PE SR UY VE",
}
CONTINENT = {code: name for name, codes in _CONTINENTS.items() for code in codes.split()}


def continent(code: str) -> str:
    """The continent of a country code, or "Unknown"."""
    return CONTINENT.get((code or "").upper(), UNKNOWN)
