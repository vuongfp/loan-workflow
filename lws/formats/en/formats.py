# Vietnamese-style dates (dd/mm/yyyy) for the en-us UI. Django uses these
# instead of its built-in en formats because FORMAT_MODULE_PATH points here.
DATE_FORMAT = 'd/m/Y'
SHORT_DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
DATE_INPUT_FORMATS = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
DATETIME_INPUT_FORMATS = [
    '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y',
    '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
]
