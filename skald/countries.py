"""Country codes, as a reader would want to see them: a flag and a name.

The log carries an ISO 3166-1 alpha-2 code (from a CDN header or a GeoIP
database). History stores the code; this only decides how it is shown.
"Unknown" is a visit whose country the log did not record - shown as such,
never guessed.
"""
from __future__ import annotations

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
ZW Zimbabwe|EU European Union|AP Asia/Pacific
"""

NAMES = {entry[:2]: entry[3:] for row in _NAMES.split("\n") for entry in
         (part.strip() for part in row.split("|")) if len(entry) > 3}


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


def label(code: str) -> str:
    """'🇨🇦 Canada', 'Unknown', or the code itself with its flag if the
    name is not in the table."""
    if not code or code == UNKNOWN:
        return UNKNOWN
    if len(code) != 2:
        return code            # a folded "(all others)" row, say
    code = code.upper()
    name = NAMES.get(code)
    mark = flag(code)
    if name:
        return f"{mark} {name}".strip()
    return f"{mark} {code}".strip()


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
