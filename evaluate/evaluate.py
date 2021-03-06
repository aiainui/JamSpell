#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import random
import argparse
import typo_model
import time
import copy
from utils import normalize, loadText, generateSentences
import utils

try:
    import readline
except:
    pass


class STATE:
    NONE = 0
    LETTER = 1
    DOT = 2
    SPACE = 3


def generateTypos(text):
    return list(map(typo_model.generateTypo, text))


class Corrector(object):
    def __init__(self):
        pass

    def correct(self, sentence, position):
        pass


class DummyCorrector(Corrector):
    def __init__(self):
        super(DummyCorrector, self).__init__()

    def correct(self, sentence, position):
        return sentence[position]


class HunspellCorrector(Corrector):
    def __init__(self, modelPath):
        super(HunspellCorrector, self).__init__()
        import hunspell
        self.__model = hunspell.HunSpell(modelPath + '.dic', modelPath + '.aff')

    def correct(self, sentence, position):
        word = sentence[position]
        if self.__model.spell(word):
            return word
        return self.__model.suggest(word)


class NorvigCorrector(Corrector):
    def __init__(self, trainFile):
        super(NorvigCorrector, self).__init__()
        import norvig_spell
        norvig_spell.init(trainFile)

    def correct(self, sentence, position):
        word = sentence[position]
        import norvig_spell
        return norvig_spell.correction(word)


class ContextCorrector(Corrector):
    def __init__(self, modelPath):
        super(ContextCorrector, self).__init__()
        import context_spell
        context_spell.init(modelPath + '.txt', modelPath + '.binary')

    def correct(self, sentence, position):
        import context_spell
        return context_spell.correction(sentence, position)


class ContextPrototypeCorrector(Corrector):
    def __init__(self, modelPath):
        super(ContextPrototypeCorrector, self).__init__()
        import context_spell_prototype
        context_spell_prototype.init(modelPath + '.txt', modelPath + '.bin')

    def correct(self, sentence, position):
        import context_spell_prototype
        return context_spell_prototype.correction(sentence, position)


class JamspellCorrector(Corrector):
    def __init__(self, modelFile):
        super(JamspellCorrector, self).__init__()
        import jamspell
        self.model = jamspell.TSpellCorrector()
        # self.model.SetPenalty(16.0, 0.0)
        if not (self.model.LoadLangModel(modelFile)):
            raise Exception('wrong model file: %s' % modelFile)

    def correct(self, sentence, position):
        cands = list(self.model.GetCandidates(sentence, position))
        if len(cands) == 0:
            return sentence[position]
        return cands


def evaluateCorrector(correctorName, corrector, originalSentences, erroredSentences, maxWords=None):
    totalErrors = 0
    origErrors = 0
    fixedErrors = 0
    broken = 0
    totalNotTouched = 0
    topNtotalErrors = 0
    topNfixed = 0

    erroredSentences = copy.deepcopy(erroredSentences)

    startTime = lastTime = time.time()
    n = 0
    for sentID in range(len(originalSentences)):
        originalText = originalSentences[sentID]
        erroredText = erroredSentences[sentID]
        for pos in range(len(originalText)):
            erroredWord = erroredText[pos]
            originalWord = originalText[pos]
            fixedCandidates = corrector.correct(erroredText, pos)
            if isinstance(fixedCandidates, list):
                # 只取top7
                fixedCandidates = fixedCandidates[:7]
                fixedWord = fixedCandidates[0]
                fixedWords = set(fixedCandidates)
            else:
                fixedWord = fixedCandidates
                fixedWords = [fixedCandidates]

            # if originalWord != fixedWord:
            #    print '%s (%s=>%s):\n%s\n\n' % (originalWord, erroredWord, fixedWord, ' '.join(erroredText))

            erroredText[pos] = fixedWord
            n += 1
            # 不相等时，也就是说该单词被随机成另外一个单词了
            if erroredWord != originalWord:
                origErrors += 1
                # 如果相等，则表示随机后的单词被纠正成为正确的单词了
                if fixedWord == originalWord:
                    fixedErrors += 1
                # 如果不相等，但是在纠正后的候选列表(top7)中，则表示topN纠正对了
                if fixedWord != erroredWord and originalWord in fixedCandidates:
                    topNfixed += 1
            # 相等时，也就是说该单词随机修改后还是原来的单词
            else:
                totalNotTouched += 1
                # 如果纠正后的单词和原始单词不一样了，说明误纠了：将本来正确的单词纠错了
                if fixedWord != originalWord:
                    broken += 1
                    # print originalWord, fixedWord
            # 如果纠正后的单词和原始单词不一致，则表明这个单词是错的
            if fixedWord != originalWord:
                totalErrors += 1
            # 如果纠正后的单词列表中没有原始单词，则表明topN也没纠正对这个单词
            if originalWord not in fixedWords:
                topNtotalErrors += 1
            #
            if sentID % 1 == 0 and pos and time.time() - lastTime > 4.0:
                progress = float(sentID) / len(originalSentences)
                err_rate = float(totalErrors) / n
                if maxWords is not None:
                    progress = float(n) / maxWords
                print('[debug] %s: processed %.2f%%, error rate: %.2f%%' % \
                      (correctorName, 100.0 * progress, 100.0 * err_rate))
                lastTime = time.time()

            if maxWords is not None and n >= maxWords:
                break

        if maxWords is not None and n >= maxWords:
            break

        # if fixedWord != originalWord:
        #    print originalWord, erroredWord, fixedWord
    # 错的/整体 | 对的/错的 | 错的/对的 | top7错的/整体 | top7对的/错的 | 总耗时
    return float(totalErrors) / n, \
           float(fixedErrors) / origErrors, \
           float(broken) / totalNotTouched, \
           float(topNtotalErrors) / n, \
           float(topNfixed) / origErrors, \
           time.time() - startTime


def testMode(corrector):
    while True:
        sentence = raw_input(">> ").lower().strip()
        sentence = normalize(sentence).split()
        if not sentence:
            continue
        newSentence = []
        for i in range(len(sentence)):
            fix = corrector.correct(sentence, i)
            if isinstance(fix, list):
                fix = fix[0]
            newSentence.append(fix)
        print(' '.join(newSentence))


def evaluateJamspell(modelFile, testText, alphabetFile, maxWords=50000):
    utils.loadAlphabet(alphabetFile)
    corrector = JamspellCorrector(modelFile)
    random.seed(42)
    originalText = loadText(testText)
    erroredText = generateTypos(originalText)
    assert len(originalText) == len(erroredText)
    originalSentences = generateSentences(originalText)
    erroredSentences = generateSentences(erroredText)
    errorsRate, fixRate, broken, topNerr, topNfix, execTime = \
        evaluateCorrector('jamspell', corrector, originalSentences, erroredSentences, maxWords)
    return errorsRate, fixRate, broken, topNerr, topNfix


def main():
    parser = argparse.ArgumentParser(description='spelling correctors evaluation')
    parser.add_argument('file', type=str, help='text file to use for evaluation')
    parser.add_argument('-hs', '--hunspell', type=str, help='path to hunspell model')
    parser.add_argument('-ns', '--norvig', type=str, help='path to train file for Norvig spell corrector')
    parser.add_argument('-cs', '--context', type=str, help='path to context spell model')
    parser.add_argument('-csp', '--context_prototype', type=str, help='path to context spell prototype model')
    parser.add_argument('-jsp', '--jamspell', type=str, help='path to jamspell model file')
    parser.add_argument('-t', '--test', action="store_true")
    parser.add_argument('-mx', '--max_words', type=int, help='max words to evaluate')
    parser.add_argument('-a', '--alphabet', type=str, help='alphabet file')
    args = parser.parse_args()

    if args.alphabet:
        utils.loadAlphabet(args.alphabet)

    correctors = {
        'dummy': DummyCorrector(),
    }
    # corrector = correctors['dummy']

    maxWords = args.max_words

    print('[info] loading models')

    if args.hunspell:
        corrector = correctors['hunspell'] = HunspellCorrector(args.hunspell)

    if args.norvig:
        corrector = correctors['norvig'] = NorvigCorrector(args.norvig)

    if args.context:
        corrector = correctors['context'] = ContextCorrector(args.context)

    if args.context_prototype:
        corrector = correctors['prototype'] = ContextPrototypeCorrector(args.context_prototype)

    if args.jamspell:
        corrector = correctors['jamspell'] = JamspellCorrector(args.jamspell)

    if args.test:
        return testMode(corrector)

    random.seed(42)
    print('[info] loading text')
    originalText = loadText(args.file)
    originalTextLen = len(list(originalText))

    print('[info] generating typos')
    #将原始的词随机修改，并以单个词的集合-列表返回
    erroredText = generateTypos(originalText)
    erroredTextLen = len(list(erroredText))

    assert originalTextLen == erroredTextLen
    #将原始文本分割成句子（去掉其中的非法符号和非句号）（不包含句号）
    originalSentences = generateSentences(originalText)
    erroredSentences = generateSentences(erroredText)

    assert len(originalSentences) == len(erroredSentences)

    # for s in originalSentences[:50]:
    #    print ' '.join(s) + '.'

    print('[info] total words: %d' % len(originalText))
    print('[info] evaluating')

    results = {}

    for correctorName, corrector in correctors.items():
        errorsRate, fixRate, broken, topNerr, topNfix, execTime = \
            evaluateCorrector(correctorName, corrector, originalSentences, erroredSentences, maxWords)
        results[correctorName] = errorsRate, fixRate, broken, topNerr, topNfix, execTime

    print('')

    print(
        '[info] %12s %8s  %8s  %8s  %8s  %8s  %8s' % ('', 'errRate', 'fixRate', 'broken', 'topNerr', 'topNfix', 'time'))
    # 将多个打分器的结果 resultsfixRate从大到小排序打印出来
    # 匿名函数 ~ 将x替换为results.items()即就是results.items[i][1]
    for k, _ in sorted(results.items(), key=lambda x: x[1]):
        print('[info] %10s  %8.2f%% %8.2f%% %8.2f%% %8.2f%% %8.2f%% %8.2fs' % \
              (k,
               100.0 * results[k][0],
               100.0 * results[k][1],
               100.0 * results[k][2],
               100.0 * results[k][3],
               100.0 * results[k][4],
               results[k][5]))


if __name__ == '__main__':
    main()
