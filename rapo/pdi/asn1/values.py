"""Contains what the value of a primitive TLV reads as.

With a grammar a value is decoded by its type: the names of the types passed
to reach it (`chain`, e.g. IMSI, TBCD-STRING, OCTET STRING) pick a decoder,
else its universal type does. Without one, a UNIVERSAL tag gives the type and
any other tag gets the readings that fit its bytes (integer, text, TBCD,
address, 3GPP time), the likeliest one as its preview.
"""

import datetime as dt
import ipaddress
import re

PREVIEW_CHARS = 80
HEX_BYTES = 24
TEXT_TYPES = {'UTF8String', 'NumericString', 'PrintableString',
              'TeletexString', 'T61String', 'VideotexString', 'IA5String',
              'GraphicString', 'VisibleString', 'ISO646String',
              'GeneralString', 'UniversalString', 'BMPString',
              'ObjectDescriptor', 'UTCTime', 'GeneralizedTime', 'DATE',
              'TIME-OF-DAY', 'DATE-TIME', 'DURATION', 'TIME', 'AsciiString'}
# Types (and the names of types defined as them) that decode a certain way.
TBCD_TYPES = {'TBCD-STRING', 'TBCDSTRING', 'TBCD-String', 'IMSI', 'IMEI',
              'IMEISV', 'MSIN'}
ADDRESS_TYPES = {'AddressString', 'ISDN-AddressString',
                 'FTN-AddressString', 'BCDDirectoryNumber'}
BCD_TYPES = {'BCDString', 'BCD-STRING', 'BcdString'}
PLMN_TYPES = {'PLMN-Id', 'PLMNId', 'PLMN-ID'}
TIMESTAMP_TYPES = {'TimeStamp', 'Timestamp'}
ASCII = re.compile(rb'[\x20-\x7e\t\r\n]+')
UNIVERSAL_DECODERS = {}


def read(data, cls, number, info=None, length=None):
    """Get what a value reads as.

    Parameters
    ----------
    data : bytes
        The value, or its first bytes when `length` is larger.
    cls, number : int
        The TLV's tag.
    info : dict
        What the grammar says of it (Grammar.describe), or None.
    length : int
        The whole value's length.

    Returns
    -------
    result : dict
        `{preview, readings: [{label, value}]}`; the preview is None when
        nothing reads well.
    """
    length = len(data) if length is None else length
    partial = length > len(data)
    readings = []
    if info and info.get('chain') and not partial:
        readings = _typed(data, info)
    if not readings and cls == 0 and not partial:
        decoder = UNIVERSAL_DECODERS.get(number)
        if decoder:
            readings = _safe(decoder, data)
    preview = readings[0]['value'] if readings else None
    typed = bool(info and info.get('chain'))
    if not readings or not typed:
        guessed = [] if partial else guesses(data)
        readings += [item for item in guessed
                     if item not in readings]
        # A type the grammar gives and no decoder reads shows its bytes.
        if preview is None and guessed and cls != 0 and not typed:
            preview = _likely(data, guessed)
    if preview is None and partial and ASCII.fullmatch(data):
        preview = data.decode('ascii') + '…'
    if preview is not None and len(preview) > PREVIEW_CHARS:
        preview = preview[:PREVIEW_CHARS] + '…'
    return {'preview': preview, 'readings': readings}


def hex_text(data, limit=HEX_BYTES, length=None):
    length = len(data) if length is None else length
    text = data[:limit].hex(' ').upper()
    return text + (' …' if length > limit else '')


def _safe(decoder, data, info=None):
    try:
        value = decoder(data, info) if info is not None else decoder(data)
    except Exception:
        return []
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _typed(data, info):
    names = set(info['chain'])
    base = info['chain'][-1] if info['chain'] else None
    for types, decoder in ((ADDRESS_TYPES, address), (TBCD_TYPES, tbcd),
                           (BCD_TYPES, bcd), (PLMN_TYPES, plmn),
                           (TIMESTAMP_TYPES, timestamp)):
        if names & types:
            reading = _safe(decoder, data)
            if reading:
                return reading
    if any('IPBinV4' in name or 'IPBinV6' in name for name in names) or (
            base == 'OCTET STRING' and len(data) in (4, 16) and
            any(name.endswith('Address') for name in names)):
        reading = _safe(ip, data)
        if reading:
            return reading
    if base in ('INTEGER', 'ENUMERATED'):
        return _safe(integer_named, data, info)
    if base == 'BIT STRING':
        return _safe(bits_named, data, info)
    if base == 'BOOLEAN':
        return _safe(boolean, data)
    if base == 'NULL':
        return [{'label': 'NULL', 'value': ''}]
    if base in ('OBJECT IDENTIFIER', 'RELATIVE-OID'):
        return _safe(oid, data)
    if base in TEXT_TYPES:
        return _safe(text, data)
    if base == 'REAL':
        return []
    if base == 'OCTET STRING' and data and ASCII.fullmatch(data):
        return _safe(text, data)
    return []


def guesses(data):
    """Get the readings that fit a value of unknown type."""
    found = []
    if not data:
        return [{'label': 'Empty', 'value': ''}]
    if len(data) <= 8:
        unsigned = int.from_bytes(data, 'big')
        found.append({'label': 'Unsigned integer', 'value': str(unsigned)})
        if data[0] & 0x80:
            found.append({'label': 'Signed integer',
                          'value': str(int.from_bytes(data, 'big',
                                                      signed=True))})
    if ASCII.fullmatch(data):
        found.append({'label': 'Text', 'value': data.decode('ascii')})
    for decoder in (tbcd, address, bcd, timestamp, plmn, ip):
        found.extend(item for item in _safe(decoder, data)
                     if item not in found)
    return found


def _likely(data, guessed):
    labels = {item['label']: item['value'] for item in guessed}
    if 'Text' in labels and len(data) >= 2:
        return labels['Text']
    for label in ('3GPP time stamp', 'TBCD digits', 'Address'):
        if label in labels and len(data) >= 3:
            return labels[label]
    if 'Unsigned integer' in labels:
        return labels['Unsigned integer']
    return None


# Decoders: a reading `{label, value}` (or a list of them), None when the
# bytes are not one.

def integer(data):
    if not data:
        return None
    return {'label': 'Integer', 'value': str(int.from_bytes(data, 'big',
                                                            signed=True))}


def integer_named(data, info=None):
    reading = integer(data)
    if reading is None:
        return None
    names = (info or {}).get('named_numbers') or {}
    name = names.get(int(reading['value']))
    if name:
        reading = {'label': 'Integer', 'value': f'{name} ({reading["value"]})'}
    return reading


def boolean(data):
    if len(data) != 1:
        return None
    return {'label': 'Boolean', 'value': 'FALSE' if data[0] == 0 else 'TRUE'}


def bits(data):
    if not data or data[0] > 7:
        return None
    unused, rest = data[0], data[1:]
    text = ''.join(f'{byte:08b}' for byte in rest)
    return text[:len(text) - unused] if unused else text


def bits_named(data, info=None):
    value = bits(data)
    if value is None:
        return None
    names = (info or {}).get('named_bits') or {}
    readings = [{'label': 'Bits', 'value': value or '(none)'}]
    if names:
        set_names = [names.get(index, str(index))
                     for index, bit in enumerate(value) if bit == '1']
        readings.insert(0, {'label': 'Bits set',
                            'value': ', '.join(set_names) or '(none)'})
    return readings


def oid(data):
    if not data or data[-1] & 0x80:
        return None
    parts, value = [], 0
    for byte in data:
        value = (value << 7) | (byte & 0x7f)
        if not byte & 0x80:
            parts.append(value)
            value = 0
    first = min(parts[0] // 40, 2)
    return {'label': 'Object identifier',
            'value': '.'.join(map(str, [first, parts[0] - first * 40] +
                                  parts[1:]))}


def text(data):
    try:
        value = data.decode('utf-8')
    except UnicodeDecodeError:
        value = data.decode('latin-1')
    return {'label': 'Text', 'value': value}


def bmp(data):
    if len(data) % 2:
        return None
    return {'label': 'Text', 'value': data.decode('utf-16-be', 'replace')}


def universal_string(data):
    if len(data) % 4:
        return None
    return {'label': 'Text', 'value': data.decode('utf-32-be', 'replace')}


def _digits(data, swapped):
    """Get the BCD digits of bytes (`swapped`: the low nibble first, TBCD),
    a filler F only at the end; None when they are not digits."""
    digits = []
    for byte in data:
        first, second = (byte & 0x0f, byte >> 4) if swapped else (
            byte >> 4, byte & 0x0f)
        digits += [first, second]
    while digits and digits[-1] == 0x0f:
        digits.pop()
    if not digits or any(digit > 9 for digit in digits):
        return None
    return ''.join(map(str, digits))


def tbcd(data):
    if len(data) < 2:
        return None
    digits = _digits(data, True)
    return None if digits is None else {'label': 'TBCD digits',
                                        'value': digits}


def bcd(data):
    if len(data) < 2:
        return None
    digits = _digits(data, False)
    return None if digits is None else {'label': 'BCD digits',
                                        'value': digits}


def address(data):
    """An AddressString: TON/NPI, then TBCD digits."""
    if len(data) < 2 or not data[0] & 0x80:
        return None
    digits = _digits(data[1:], True)
    if digits is None:
        return None
    nature = (data[0] >> 4) & 0x07
    prefix = '+' if nature == 1 else ''
    return {'label': 'Address',
            'value': f'{prefix}{digits} (TON {nature}, NPI {data[0] & 0x0f})'}


def timestamp(data):
    """A 3GPP TS 32.298 time stamp: YYMMDDhhmmss in BCD, sign, hhmm."""
    if len(data) != 9 or chr(data[6]) not in '+-':
        return None
    digits = _digits(data[:6], False)
    offset = _digits(data[7:], False)
    if digits is None or offset is None or len(digits) != 12 or \
            len(offset) != 4:
        return None
    try:
        moment = dt.datetime.strptime(digits, '%y%m%d%H%M%S')
    except ValueError:
        return None
    return {'label': '3GPP time stamp',
            'value': f'{moment:%Y-%m-%d %H:%M:%S} {chr(data[6])}'
                     f'{offset[:2]}:{offset[2:]}'}


def plmn(data):
    """A PLMN identity: MCC and MNC in TBCD, F filling a 2-digit MNC."""
    if len(data) != 3:
        return None
    nibbles = [data[0] & 0x0f, data[0] >> 4, data[1] & 0x0f, data[2] & 0x0f,
               data[2] >> 4, data[1] >> 4]
    if any(nibble > 9 for nibble in nibbles[:5]) or (
            nibbles[5] > 9 and nibbles[5] != 0x0f):
        return None
    mcc = ''.join(map(str, nibbles[:3]))
    mnc = ''.join(str(nibble) for nibble in nibbles[3:] if nibble <= 9)
    return {'label': 'PLMN', 'value': f'MCC {mcc}, MNC {mnc}'}


def ip(data):
    if len(data) == 4:
        return {'label': 'IPv4 address',
                'value': str(ipaddress.IPv4Address(data))}
    if len(data) == 16:
        return {'label': 'IPv6 address',
                'value': str(ipaddress.IPv6Address(data))}
    return None


UNIVERSAL_DECODERS.update({
    1: boolean, 2: integer, 3: lambda data: (
        None if bits(data) is None else
        {'label': 'Bits', 'value': bits(data) or '(none)'}),
    5: lambda data: {'label': 'NULL', 'value': ''}, 6: oid, 10: integer,
    12: text, 13: oid, 18: text, 19: text, 20: text, 21: text, 22: text,
    23: text, 24: text, 25: text, 26: text, 27: text, 28: universal_string,
    30: bmp, 7: text, 14: text, 31: text, 32: text, 33: text, 34: text})
