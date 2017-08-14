from __future__ import unicode_literals
import unicodedata
import re, sys, os, glob, argparse
from pathlib import Path
from tqdm import tqdm
from multiprocessing import Pool


def delete_html_tag_with_contents(tag: str, src: str):
    return delete_regexps(
                "<{tag}[^>]*>[\s\S]*?<\s*/{tag}\s*>".format(tag=tag), src)


def delete_regexps(regexp: str, src: str):
    I = [(i.start(), i.end()) for i in re.finditer(regexp, src)]
    if len(I) == 0:
        return src
    res = src[:I[0][0]]
    for i in range(len(I)-1):
        res += src[I[i][1]:I[i+1][0]]
    res += src[I[-1][1]:]
    return res


def unicode_normalize(cls, s):
    pt = re.compile('([{}]+)'.format(cls))

    def norm(c):
        return unicodedata.normalize('NFKC', c) if pt.match(c) else c

    s = ''.join(norm(x) for x in re.split(pt, s))
    s = re.sub('－', '-', s)
    return s


def remove_extra_spaces(s):
    s = re.sub('[ 　]+', ' ', s)
    blocks = ''.join(('\u4E00-\u9FFF',  # CJK UNIFIED IDEOGRAPHS
                      '\u3040-\u309F',  # HIRAGANA
                      '\u30A0-\u30FF',  # KATAKANA
                      '\u3000-\u303F',  # CJK SYMBOLS AND PUNCTUATION
                      '\uFF00-\uFFEF'   # HALFWIDTH AND FULLWIDTH FORMS
                      ))
    basic_latin = '\u0000-\u007F'

    def remove_space_between(cls1, cls2, s):
        p = re.compile('([{}]) ([{}])'.format(cls1, cls2))
        while p.search(s):
            s = p.sub(r'\1\2', s)
        return s

    s = remove_space_between(blocks, blocks, s)
    s = remove_space_between(blocks, basic_latin, s)
    s = remove_space_between(basic_latin, blocks, s)
    return s


def normalize_neologd(s):
    s = s.strip()
    s = unicode_normalize('０-９Ａ-Ｚａ-ｚ｡-ﾟ', s)

    def maketrans(f, t):
        return {ord(x): ord(y) for x, y in zip(f, t)}

    s = re.sub('[˗֊‐‑‒–⁃⁻₋−]+', '-', s)  # normalize hyphens
    s = re.sub('[﹣－ｰ—―─━ー]+', 'ー', s)  # normalize choonpus
    s = re.sub('[~∼∾〜〰～]', '', s)  # remove tildes
    s = s.translate(
        maketrans('!"#$%&\'()*+,-./:;<=>?@[¥]^_`{|}~｡､･｢｣',
              '！”＃＄％＆’（）＊＋，－．／：；＜＝＞？＠［￥］＾＿｀｛｜｝〜。、・「」'))

    s = remove_extra_spaces(s)
    s = unicode_normalize('！”＃＄％＆’（）＊＋，－．／：；＜＞？＠［￥］＾＿｀｛｜｝〜', s)  # keep ＝,・,「,」
    s = re.sub('[’]', '\'', s)
    s = re.sub('[”]', '"', s)
    return s


def postprocess(filename: str):
    file_path = Path(filename)
    with file_path.open() as f:
        s = f.read()
    # delete HTML tags with their contents
    # (deleting HTML tags WITHOUT their contents can be done with
    #  WikiExtractor's -it option.)
    s = delete_html_tag_with_contents('ref', s)
    # TODO This is tentative. It may be better to delete this tags without
    # their contents.
    s = delete_html_tag_with_contents('table', s)
    # ruby
    s = delete_html_tag_with_contents('rp', s)
    s = delete_html_tag_with_contents('rt', s)
    # delete HTML tags WITHOUT their contents
    s = delete_regexps("<[^>]*>", s)
    for _ in range(5): # to handle nested brackets
        s = delete_regexps("[(（][^()（）]*[)）]", s)
        s = delete_regexps("(|)|（|）", s)
    s = normalize_neologd(s)
    with (file_path.parent / ('modified_' + file_path.name)).open('w') as f:
        f.write(s)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--extract', action='store_true')
    parser.add_argument('-o', '--out', default='extracted')
    parser.add_argument('-p', '--processes', default=None)
    parser.add_argument('-w', '--wiki', default='~/data/wiki/jawiki-20160820-pages-articles-multistream.xml.bz2')
    args = parser.parse_args()
    out_dir = Path(args.out)

    if args.extract:
        # WikiExtractor
        os.system("./WikiExtractor.py -b 20M -o {out} --filter_disambig_pages"
               " -it abbr,b,big,br,div,tt,sup,sub,small,span,source,u,nowiki,"
               "blockquote,li,ol,ul,ruby -de gallery,timeline,noinclude "
               "{jawiki} > extractor.log".format(jawiki=args.wiki, out=args.out))

    fs = glob.glob(str(out_dir / '*/*'))
    with Pool(int(args.processes)) as p:
        p.map(postprocess, fs)

if __name__ == '__main__':
    main()

