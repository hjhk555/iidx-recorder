import requests, re, html

def handle_html(string) -> str:
    return html.unescape(re.sub('<[^>]*>', '', string)).strip()

def escape_chars_for_sql(string) -> str:
    return re.sub('\'', '\'\'', string)

def get_js(url) -> str:
    req = requests.get(url)
    req.encoding = 'Shift-JIS'
    return req.text

def set_to_sorted_list(target: set, key = None) -> list:
     res = list(target)
     res.sort(key = key)
     return res

if __name__ == '__main__':
    print(escape_chars_for_sql('\''))