# -*- coding:utf-8 -*-

import jieba
import jieba.posseg as pesg

jieba.load_userdict("../atomic.txt")
with open("../原始例句.txt", encoding="utf-8") as fo:
    for line in fo.readlines():
        words = pesg.cut(line.split("\t")[0])
        for w in words:
            # print(w.flag, w.word, end="/ ")
            print(w.flag, end=" ")
        print()