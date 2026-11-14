"""Numbers in Vietnamese words, as contracts write them: "Một tỷ chín trăm hai mươi triệu đồng"."""
from decimal import Decimal, InvalidOperation

DIGITS = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']
# Each group of three digits, from the right; past "tỷ" the names repeat ("nghìn tỷ", "triệu tỷ").
GROUPS = ['', 'nghìn', 'triệu']


def _three(number, full):
    """0-999 in words. `full` when a higher group came before: then 5 reads "không trăm linh năm"."""
    hundreds, tens, units = number // 100, number // 10 % 10, number % 10
    words = []
    if hundreds or full:
        words += [DIGITS[hundreds], 'trăm']
    if tens == 0:
        if units and words:
            words.append('linh')
    elif tens == 1:
        words.append('mười')
    else:
        words += [DIGITS[tens], 'mươi']
    if units:
        if units == 1 and tens >= 2:
            words.append('mốt')
        elif units == 5 and tens >= 1:
            words.append('lăm')
        elif units == 4 and tens >= 2:
            words.append('tư')
        else:
            words.append(DIGITS[units])
    return words


def integer_words(number):
    if number == 0:
        return 'không'
    groups = []
    while number:
        groups.append(number % 1000)
        number //= 1000
    words = []
    for index in range(len(groups) - 1, -1, -1):
        value = groups[index]
        if not value:
            continue
        words += _three(value, full=bool(words))
        # 10^9 is "tỷ"; larger groups are read as multiples of a billion ("nghìn tỷ").
        name = ' '.join(filter(None, [GROUPS[index % 3]] + ['tỷ'] * (index // 3)))
        if name:
            words.append(name)
    return ' '.join(words)


def number_words(value):
    """An integer or decimal (int, Decimal or text such as '120.5' or '1,500,000') in words; None if not a number."""
    try:
        number = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None
    if number < 0:
        return None
    whole, _, fraction = format(number, 'f').partition('.')
    words = integer_words(int(whole))
    fraction = fraction.rstrip('0')
    if fraction:
        words += ' phẩy ' + integer_words(int(fraction))
    return words


def capitalize(text):
    return text[:1].upper() + text[1:] if text else text


def amount_words(value, unit='đồng'):
    """'1920000000' -> 'Một tỷ chín trăm hai mươi triệu đồng'; '' if the value is not a number."""
    words = number_words(value) if value not in (None, '') else None
    return capitalize('%s %s' % (words, unit)) if words else ''
