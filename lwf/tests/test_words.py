from django.test import SimpleTestCase

from lwf.words import amount_words, number_words


class WordsTests(SimpleTestCase):
    def test_amounts_read_like_a_contract(self):
        cases = {
            0: 'Không đồng', 15: 'Mười lăm đồng', 21: 'Hai mươi mốt đồng', 24: 'Hai mươi tư đồng',
            105: 'Một trăm linh năm đồng', 1_000_005: 'Một triệu không trăm linh năm đồng',
            1_500_000: 'Một triệu năm trăm nghìn đồng', 1_920_000_000: 'Một tỷ chín trăm hai mươi triệu đồng',
            2_000_000_000_000: 'Hai nghìn tỷ đồng',
        }
        for number, text in cases.items():
            self.assertEqual(amount_words(number), text)

    def test_text_and_decimals(self):
        self.assertEqual(amount_words('1,500,000'), 'Một triệu năm trăm nghìn đồng')
        self.assertEqual(amount_words('120.5', 'mét vuông'), 'Một trăm hai mươi phẩy năm mét vuông')
        self.assertEqual(number_words('abc'), None)
        self.assertEqual(amount_words(''), '')
